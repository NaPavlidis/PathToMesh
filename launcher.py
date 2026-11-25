"""Launcher do PathToMesh (Windows).

Ao abrir:
  1. procura atualização no GitHub (git, se a pasta for um clone; senão a API pública e o zip da main);
  2. instala as dependências (pip: primeiro o requirements-base.txt, depois o requirements.txt,
     que acrescenta o pywebview; se só o pywebview falhar, avisa e o app abre na Tkinter);
  3. confere se o blender_path do config.local.json existe (criado, se faltar, a partir do
     config.json antigo ou do config.exemplo.json);
  4. envia os logs de erro novos para a branch 'logs' (se houver git com credencial).
Depois é só clicar em "Abrir o app": o app abre como um processo independente e o launcher se
fecha sozinho. Se o app não abrir, o launcher fica aberto, mostra o erro e grava o log.

Janela: o visual novo (launcher_web.py, pywebview, o mesmo estilo do app); se o pywebview não
estiver instalado (a 1ª vez: é o próprio launcher que o instala) ou a janela web falhar, a janela
Tkinter daqui, com as mesmas funções. Com --tk, abre direto a Tkinter.

A lógica fica em funções sem Tkinter, para poder ser testada sem janela.
"""
import glob
import io
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.request
import zipfile

import registro_erros as reg
import tema_janela
from tema_janela import TEMA

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:     # permite importar a lógica sem Tkinter (testes)
    tk = None
    messagebox = None

PASTA = reg.PASTA_PROJETO
# Repositório renomeado de Phy-2d-by-3d para PathToMesh: o GitHub redireciona o nome antigo
# (clones antigos, com o origin no endereço antigo, continuam atualizando)
REPO = "NaPavlidis/PathToMesh"
RAMO = "main"
URL_REPO = f"https://github.com/{REPO}.git"
URL_API_COMMIT = f"https://api.github.com/repos/{REPO}/commits/{RAMO}"
URL_ZIP = "https://codeload.github.com/" + REPO + "/zip/{sha}"

# Configuração do usuário (no .gitignore), config.json antigo (só para a migração; também no
# .gitignore desde a etapa 2), modelo versionado e cópia de segurança do config.json antigo
CONFIG_LOCAL = reg.ARQUIVO_CONFIG_LOCAL
CONFIG_BASE = reg.ARQUIVO_CONFIG_BASE
CONFIG_EXEMPLO = reg.ARQUIVO_CONFIG_EXEMPLO
CONFIG_BACKUP = "config.json.bak"
# Na atualização pelo zip estes nunca são sobrescritos (o zip da main não tem mais o config.json)
PRESERVAR = {CONFIG_BASE}
IGNORAR_NO_ZIP = {".git", "logs", ".venv", "venv", "__pycache__", reg.ARQUIVO_VERSAO,
                  CONFIG_LOCAL, CONFIG_BACKUP}

# Mesma paleta do app_ui.py (tema_janela.TEMA, tirada do docs/modelo-layout.html)
COR_FUNDO = TEMA['fundo']
COR_BARRA = TEMA['barra']
COR_CARTAO = TEMA['superficie']
COR_CAMPO = TEMA['campo']
COR_BOTAO = TEMA['elevado']
COR_BOTAO_HOVER = TEMA['elevado_hover']
COR_DESTAQUE = TEMA['destaque']
COR_SOBRE_DESTAQUE = TEMA['sobre_destaque']
COR_TITULO = TEMA['marca']
COR_SOBRE_TITULO = TEMA['sobre_marca']
COR_OK = TEMA['sucesso']
COR_AVISO = TEMA['aviso']
COR_TEXTO = TEMA['texto']
COR_SUAVE = TEMA['texto_suave']
COR_APAGADO = TEMA['texto_apagado']
COR_BORDA = TEMA['borda']
COR_LINHA = TEMA['divisor']


# ---------------------------------------------------------------- versões

def comparar_shas(local, remoto):
    """Compara o commit instalado com o da main. 'atualizado', 'disponivel' ou 'erro'."""
    remoto = (remoto or "").strip().lower()
    local = (local or "").strip().lower()
    if not remoto:
        return "erro"
    if len(local) >= 7 and (remoto.startswith(local) or local.startswith(remoto)):
        return "atualizado"
    return "disponivel"


def comparar_contagens(a_frente, atras):
    """Resultado do 'git rev-list --left-right --count HEAD...main'."""
    if atras == 0:
        return "a_frente" if a_frente > 0 else "atualizado"
    return "divergente" if a_frente > 0 else "disponivel"


def _remoto_git(pasta):
    codigo, _, _ = reg.git(pasta, "remote", "get-url", "origin")
    return "origin" if codigo == 0 else URL_REPO


def consultar_api(timeout=15):
    """Último commit da main pela API pública: {'sha', 'data', 'mensagem'}."""
    pedido = urllib.request.Request(URL_API_COMMIT, headers={
        "User-Agent": "PathToMesh-launcher", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(pedido, timeout=timeout) as r:
        dados = json.loads(r.read().decode("utf-8"))
    commit = dados.get("commit", {})
    return {"sha": dados["sha"],
            "data": (commit.get("committer", {}).get("date") or "")[:10],
            "mensagem": (commit.get("message") or "").splitlines()[0] if commit.get("message") else ""}


def verificar_atualizacao(pasta=PASTA):
    """Devolve um dict com 'modo' (git/zip), 'status', 'mensagem' e os dados do commit remoto."""
    local = reg.versao_atual(pasta)
    info = {"local": local, "remoto_sha": "", "remoto_data": "", "remoto_msg": "", "atras": 0}

    if reg.eh_clone_git(pasta):
        info["modo"] = "git"
        _, ramo, _ = reg.git(pasta, "rev-parse", "--abbrev-ref", "HEAD")
        info["ramo"] = ramo
        codigo, _, erro = reg.git(pasta, "fetch", "-q", "--no-tags", _remoto_git(pasta), RAMO, timeout=120)
        if codigo != 0:
            info.update(status="erro", mensagem="Não deu para procurar atualização (sem internet?).")
            return info
        _, sha, _ = reg.git(pasta, "rev-parse", "FETCH_HEAD")
        _, linha, _ = reg.git(pasta, "log", "-1", "--format=%cs%x09%s", sha)
        data, _, msg = linha.partition("\t")
        info.update(remoto_sha=sha, remoto_data=data, remoto_msg=msg)
        codigo, contagem, _ = reg.git(pasta, "rev-list", "--left-right", "--count", f"HEAD...{sha}")
        try:
            a_frente, atras = (int(x) for x in contagem.split())
        except ValueError:
            info.update(status="erro", mensagem="Não deu para comparar as versões.")
            return info
        info["atras"] = atras
        status = comparar_contagens(a_frente, atras)
        if ramo != RAMO and status != "atualizado":
            info.update(status="outra_branch",
                        mensagem=f"Você está na branch '{ramo}'. A atualização automática só funciona na main.")
            return info
        info["status"] = status
    else:
        info["modo"] = "zip"
        try:
            remoto = consultar_api()
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            info.update(status="erro", mensagem=f"Não deu para procurar atualização (sem internet?): {e}")
            return info
        info.update(remoto_sha=remoto["sha"], remoto_data=remoto["data"], remoto_msg=remoto["mensagem"])
        info["status"] = comparar_shas(local["sha"], remoto["sha"])

    mensagens = {
        "atualizado": "Você está na versão mais nova.",
        "disponivel": "Há uma atualização: " + (info["remoto_msg"] or info["remoto_sha"][:7]),
        "a_frente": "A sua cópia tem commits que ainda não estão no GitHub.",
        "divergente": "A sua cópia e o GitHub têm mudanças diferentes. Atualize pelo git (pull) manualmente.",
        "erro": "Não deu para comparar as versões.",
    }
    info["mensagem"] = mensagens[info["status"]]
    if info["status"] == "disponivel" and info["atras"]:
        info["mensagem"] += f" ({info['atras']} commit(s) novo(s))"
    return info


# ---------------------------------------------------------------- atualizar

def _ler_bytes(caminho):
    try:
        with open(caminho, "rb") as f:
            return f.read()
    except OSError:
        return None


def proteger_config(pasta=PASTA):
    """Antes do git pull: tira do caminho as mudanças locais do config.json sem perder nada.

    - config.json sem mudanças locais: não faz nada.
    - config.local.json ainda não existe: copia o config.json (os valores do usuário) para ele.
    - config.local.json já existe e o config.json tem outro conteúdo: guarda o config.json em
      config.json.bak, para nada se perder.
    Depois descarta a mudança local do config.json (volta à versão do commit). Assim o git pull
    funciona também quando o GitHub apagou o config.json (etapa 2: ele virou config.exemplo.json):
    o pull só apaga o config.json sem mudanças, e os valores do usuário já estão a salvo.
    Devolve (ok, lista de avisos).
    """
    codigo, saida, _ = reg.git(pasta, "ls-tree", "--name-only", "HEAD", "--", CONFIG_BASE)
    if codigo != 0 or not saida.strip():
        return True, []                      # config.json não está no commit atual: nada a proteger
    codigo, _, _ = reg.git(pasta, "diff", "--quiet", "HEAD", "--", CONFIG_BASE)
    if codigo == 0:
        return True, []                      # sem mudanças locais
    avisos = []
    caminho_base = os.path.join(pasta, CONFIG_BASE)
    try:
        existia_base = os.path.isfile(caminho_base)
        local, criado = reg.garantir_config_local(pasta)
        if criado and existia_base:
            avisos.append(f"Os seus valores do {CONFIG_BASE} foram copiados para o {CONFIG_LOCAL}.")
        elif criado:
            avisos.append(f"O {CONFIG_LOCAL} foi criado a partir do {CONFIG_EXEMPLO}.")
        else:
            atual = _ler_bytes(caminho_base)
            if atual is not None and atual != _ler_bytes(local):
                with open(os.path.join(pasta, CONFIG_BACKUP), "wb") as f:
                    f.write(atual)
                avisos.append(f"O {CONFIG_BASE} alterado foi guardado em {CONFIG_BACKUP} "
                              f"(a configuração usada é a do {CONFIG_LOCAL}).")
    except OSError as e:
        return False, [f"Não deu para guardar o {CONFIG_BASE} antes de atualizar: {e}"]
    codigo, saida, erro = reg.git(pasta, "checkout", "HEAD", "--", CONFIG_BASE)
    if codigo != 0:
        return False, [f"Não deu para descartar a mudança local do {CONFIG_BASE}:\n" + (erro or saida)]
    return True, avisos


def atualizar_git(pasta=PASTA):
    """git pull --ff-only, protegendo antes o config do usuário. Devolve (ok, mensagem)."""
    ok, avisos = proteger_config(pasta)
    if not ok:
        return False, "\n".join(avisos)
    try:
        # config.json sem mudanças locais: o config.local.json nasce dele (ou do exemplo) antes do pull
        origem = reg.origem_config(pasta)
        if reg.garantir_config_local(pasta)[1]:
            avisos.append(f"O {CONFIG_LOCAL} foi criado a partir do {os.path.basename(origem)}.")
    except OSError as e:
        return False, f"Não deu para criar o {CONFIG_LOCAL} antes de atualizar: {e}"
    codigo, saida, erro = reg.git(pasta, "pull", "--ff-only", "--no-rebase", _remoto_git(pasta), RAMO, timeout=180)
    if codigo != 0:
        return False, "\n".join(avisos + ["O git não conseguiu atualizar:\n" + (erro or saida)])
    return True, "\n".join(avisos + ["Atualizado pelo git."])


def _caminho_seguro(nome_no_zip):
    """Tira a pasta de topo do zip e recusa caminhos absolutos ou com '..'."""
    partes = nome_no_zip.replace("\\", "/").split("/")[1:]
    if not partes or partes[-1] == "":
        return None
    if any(p in ("", ".", "..") or ":" in p for p in partes):
        return None
    if partes[0] in IGNORAR_NO_ZIP or partes[-1] == "__pycache__":
        return None
    return partes


def aplicar_zip(dados_zip, pasta=PASTA):
    """Copia o conteúdo do zip da main para a pasta. Devolve a lista de arquivos alterados."""
    alterados = []
    with zipfile.ZipFile(io.BytesIO(dados_zip)) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            partes = _caminho_seguro(item.filename)
            if partes is None:
                continue
            relativo = "/".join(partes)
            destino = os.path.join(pasta, *partes)
            if relativo in PRESERVAR and os.path.exists(destino):
                continue
            conteudo = z.read(item)
            if os.path.isfile(destino):
                with open(destino, "rb") as f:
                    if f.read() == conteudo:
                        continue        # igual: não regrava (evita mexer no .bat aberto)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            temporario = destino + ".novo"
            with open(temporario, "wb") as f:
                f.write(conteudo)
            os.replace(temporario, destino)
            alterados.append(relativo)
    return alterados


def gravar_versao_zip(sha, data, pasta=PASTA):
    with open(os.path.join(pasta, reg.ARQUIVO_VERSAO), "w", encoding="utf-8") as f:
        json.dump({"sha": sha, "data": data}, f)


def atualizar_zip(info, pasta=PASTA, timeout=60):
    pedido = urllib.request.Request(URL_ZIP.format(sha=info["remoto_sha"]),
                                    headers={"User-Agent": "PathToMesh-launcher"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            dados = r.read()
    except (urllib.error.URLError, OSError) as e:
        return False, f"Não deu para baixar a atualização: {e}"
    try:
        reg.garantir_config_local(pasta)     # os valores do usuário saem do config.json antes
    except OSError as e:
        return False, f"Não deu para criar o {CONFIG_LOCAL} antes de atualizar: {e}"
    alterados = aplicar_zip(dados, pasta)
    gravar_versao_zip(info["remoto_sha"], info["remoto_data"], pasta)
    return True, f"Atualizado pelo zip ({len(alterados)} arquivo(s) novo(s) ou alterado(s))."


def atualizar(info, pasta=PASTA):
    if info.get("modo") == "git":
        return atualizar_git(pasta)
    return atualizar_zip(info, pasta)


# ---------------------------------------------------------------- dependências e config

def python_console():
    """python.exe no lugar do pythonw.exe (o pip precisa de console, que fica escondido)."""
    exe = sys.executable
    pasta, nome = os.path.split(exe)
    if nome.lower() == "pythonw.exe" and os.path.isfile(os.path.join(pasta, "python.exe")):
        return os.path.join(pasta, "python.exe")
    return exe


AVISO_INTERFACE = "A interface nova não pôde ser instalada; o app abre na versão clássica."


def _pip(requisitos, pasta, executar):
    """Roda 'pip install -r <requisitos>'. Devolve None se deu certo, ou o texto do erro."""
    comando = [python_console(), "-m", "pip", "install", "--disable-pip-version-check", "-r", requisitos]
    try:
        r = executar(comando, capture_output=True, text=True, encoding="utf-8", errors="replace",
                     timeout=600, cwd=pasta, **reg.opcoes_sem_janela())
    except (OSError, subprocess.SubprocessError) as e:
        return f"Não deu para rodar o pip: {e}"
    if r.returncode != 0:
        return (r.stderr or r.stdout or "")[-3000:]
    return None


def instalar_dependencias(pasta=PASTA, executar=subprocess.run):
    """Instala primeiro as dependências essenciais (requirements-base.txt) e depois o resto do
    requirements.txt (o pywebview, da interface nova). Se só a segunda parte falhar (ex.: o
    pythonnet sem pacote para a versão do Python), avisa e segue: o app.py abre a Tkinter."""
    base = os.path.join(pasta, "requirements-base.txt")
    completo = os.path.join(pasta, "requirements.txt")
    if os.path.isfile(base):
        erro = _pip(base, pasta, executar)
        if erro is not None:
            return False, "O pip não instalou as dependências essenciais:\n" + erro
    if not os.path.isfile(completo):
        if os.path.isfile(base):
            return True, "Dependências instaladas."
        return True, "Sem requirements.txt: nada para instalar."
    erro = _pip(completo, pasta, executar)
    if erro is not None:
        if os.path.isfile(base):
            return False, (AVISO_INTERFACE + "\nAs dependências essenciais foram instaladas. "
                           "Erro do pip na interface nova (pywebview):\n" + erro)
        return False, "O pip falhou:\n" + erro
    return True, "Dependências instaladas."


def ler_config(pasta=PASTA):
    """Lê o config.local.json (criado a partir do config.json antigo ou do config.exemplo.json,
    se faltar). Devolve (dados, erro)."""
    try:
        caminho, _ = reg.garantir_config_local(pasta)
    except OSError as e:
        return None, f"Não deu para criar o {CONFIG_LOCAL}: {e}"
    if not os.path.isfile(caminho):
        return None, f"Não achei o {CONFIG_LOCAL} nem o {CONFIG_EXEMPLO} na pasta do projeto."
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except ValueError as e:
        return None, f"O {CONFIG_LOCAL} tem um erro de formato: {e}"
    except OSError as e:
        return None, f"Não deu para ler o {CONFIG_LOCAL}: {e}"
    if not isinstance(dados, dict):
        return None, f"O {CONFIG_LOCAL} não está no formato esperado."
    return dados, None


def verificar_blender(pasta=PASTA):
    """Devolve (ok, mensagem)."""
    dados, erro = ler_config(pasta)
    if erro:
        return False, erro
    caminho = dados.get("blender_path")
    if not caminho or not isinstance(caminho, str):
        return False, f"O {CONFIG_LOCAL} não tem o blender_path. Ajuste nas configurações do app (⚙)."
    if not os.path.isfile(caminho):
        return False, f"O Blender não foi encontrado em:\n{caminho}\nAjuste nas configurações do app (⚙)."
    return True, f"Blender encontrado: {caminho}"


# Segundos esperando o app: se ele ainda estiver aberto depois disso, abriu bem
ESPERA_ABRIR = 4.0
# Saída do app (prints e erros do Python antes de a janela abrir), para mostrar se ele falhar
ARQUIVO_SAIDA_APP = os.path.join(tempfile.gettempdir(), "pathtomesh-app-saida.txt")


def python_janela():
    """pythonw.exe (sem a janela preta do console) ao lado do Python atual, se existir."""
    exe = sys.executable
    pasta, nome = os.path.split(exe)
    if os.name == "nt" and nome.lower() == "python.exe" and os.path.isfile(os.path.join(pasta, "pythonw.exe")):
        return os.path.join(pasta, "pythonw.exe")
    return exe


def opcoes_independente():
    """Opções do Popen para o app seguir rodando depois que o launcher fechar."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)}
    return {"start_new_session": True}


def _ler_saida(caminho, limite=3000):
    try:
        with open(caminho, "r", encoding="utf-8", errors="replace") as f:
            return f.read()[-limite:].strip()
    except OSError:
        return ""


def _pastas_blender():
    raizes = []
    for raiz in (os.environ.get("ProgramFiles"), r"C:\Program Files"):
        if raiz and os.path.normcase(raiz) not in [os.path.normcase(r) for r in raizes]:
            raizes.append(raiz)
    return [os.path.join(r, "Blender Foundation") for r in raizes]


def _versao_da_pasta(nome):
    m = re.search(r"(\d+(?:\.\d+)*)", nome)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def procurar_blender(pastas=None):
    """Procura <Program Files>/Blender Foundation/Blender */blender.exe e devolve o da versão
    mais nova (ou "" se não achar)."""
    achados = []
    for base in (pastas if pastas is not None else _pastas_blender()):
        for exe in glob.glob(os.path.join(glob.escape(base), "Blender *", "blender.exe")):
            if os.path.isfile(exe):
                achados.append((_versao_da_pasta(os.path.basename(os.path.dirname(exe))), exe))
    if not achados:
        return ""
    achados.sort()
    return achados[-1][1].replace("\\", "/")


def preparar_config(pasta=PASTA, pastas_blender=None):
    """Usado pelo instalador: cria o config.local.json (se faltar) e, se o blender_path dele não
    existir, procura o Blender instalado e grava o caminho. Nunca muda um blender_path que existe.
    Devolve um dict com o resultado."""
    resultado = {"config": reg.caminho_config_local(pasta), "criado": False, "blender": "",
                 "blender_achado": False, "blender_ok": False, "erro": "",
                 "pythonw": python_janela()}
    try:
        _, resultado["criado"] = reg.garantir_config_local(pasta)
    except OSError as e:
        resultado["erro"] = f"Não deu para criar o {CONFIG_LOCAL}: {e}"
        return resultado
    dados, erro = ler_config(pasta)
    if erro:
        resultado["erro"] = erro
        return resultado
    atual = dados.get("blender_path")
    if isinstance(atual, str) and atual and os.path.isfile(atual):
        resultado.update(blender=atual, blender_ok=True)
        return resultado
    achado = procurar_blender(pastas_blender)
    if not achado:
        resultado["blender"] = atual if isinstance(atual, str) else ""
        return resultado
    dados["blender_path"] = achado
    try:
        caminho = reg.caminho_config_local(pasta)
        with open(caminho + ".novo", "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        os.replace(caminho + ".novo", caminho)
    except OSError as e:
        resultado["erro"] = f"Não deu para gravar o {CONFIG_LOCAL}: {e}"
        return resultado
    resultado.update(blender=achado, blender_achado=True, blender_ok=True)
    return resultado


def abrir_app(pasta=PASTA, espera=ESPERA_ABRIR, comando=None, arquivo_saida=None):
    """Abre o app como um processo independente e confere se ele abriu.

    Espera alguns segundos: se o app ainda estiver rodando (ou fechou sem erro), deu certo.
    Se não deu para iniciar, ou se ele fechou com erro logo no começo, devolve a mensagem de
    erro com a saída do app. Devolve (ok, mensagem).
    """
    arquivo_saida = arquivo_saida or ARQUIVO_SAIDA_APP
    if comando is None:
        # app.py abre a interface web (pywebview) e cai sozinho na Tkinter (app_ui.py) se ela falhar
        script = os.path.join(pasta, "app.py")
        if not os.path.isfile(script):
            script = os.path.join(pasta, "app_ui.py")
        if not os.path.isfile(script):
            return False, "Não achei o app.py na pasta do programa. Rode o instalador de novo."
        comando = [python_janela(), script]
    try:
        saida = open(arquivo_saida, "wb")
    except OSError:
        saida = None
    try:
        try:
            processo = subprocess.Popen(comando, cwd=pasta, stdin=subprocess.DEVNULL,
                                        stdout=saida or subprocess.DEVNULL,
                                        stderr=subprocess.STDOUT if saida else subprocess.DEVNULL,
                                        close_fds=True, **opcoes_independente())
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            return False, f"Não deu para iniciar o app: {e}"
        try:
            codigo = processo.wait(timeout=espera)
        except subprocess.TimeoutExpired:
            return True, "App aberto."
    finally:
        if saida:
            saida.close()
    if codigo == 0:
        return True, "O app abriu e já foi fechado."
    texto = _ler_saida(arquivo_saida)
    return False, (f"O app fechou logo ao abrir (código {codigo})."
                   + (f"\n\nMensagem do app:\n{texto}" if texto else ""))


def abrir_pasta(caminho):
    os.makedirs(caminho, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(caminho)


# ---------------------------------------------------------------- janela

class Launcher(tk.Tk if tk else object):
    TEXTO_ABRIR = "▶  Abrir o app"

    def __init__(self):
        super().__init__()
        self.title(f"{tema_janela.NOME_APP} - Launcher")
        self.geometry("620x680")
        self.minsize(560, 600)
        self.configure(bg=COR_FUNDO)
        self.report_callback_exception = reg.gancho_tk("launcher")
        titulo, corpo, mono = tema_janela.familias_fontes(self)
        # Mesmas fontes do app (tamanhos em pixels, como no modelo)
        self.fontes = {"marca": (titulo, -16, "bold"), "cartao": (corpo, -12, "bold"),
                       "texto": (corpo, -14), "suave": (corpo, -13), "botao": (corpo, -14, "bold"),
                       "abrir": (titulo, -16, "bold"), "mono": (mono, -12), "selo": (mono, -12),
                       "icone": (corpo, -16)}
        # Ícone (vale também para as mensagens) e barra de título nas cores do tema
        tema_janela.preparar_janela(self, "launcher", padrao=True)
        self.fila = queue.Queue()
        self.info_atualizacao = None
        self.ocupado = False
        self.abrindo = False
        self._montar()
        self.after(100, self._ler_fila)
        self._em_segundo_plano(self._verificar_tudo)

    # ---- montagem
    def _montar(self):
        f = self.fontes
        # Barra de 56 px igual à do app: logo (ícone 1; 2 com a janela larga), selo e linha embaixo
        barra = tk.Frame(self, bg=COR_BARRA, height=56, padx=24)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        tema_janela.criar_logo_cabecalho(barra, self, COR_BARRA, COR_DESTAQUE, f["marca"]).pack(side="left")
        selo = tk.Frame(barra, bg=COR_LINHA, padx=1, pady=1)
        selo.pack(side="left", padx=(12, 0))
        tk.Label(selo, text="LAUNCHER", fg=COR_SUAVE, bg=COR_BOTAO, font=f["selo"], padx=8, pady=2).pack()
        tk.Frame(self, bg=COR_BORDA, height=1).pack(fill="x")

        corpo = tk.Frame(self, bg=COR_FUNDO, padx=24, pady=16)
        corpo.pack(fill="both", expand=True)

        self.lbl_versao, self.lbl_atualizacao, linha = self._cartao(corpo, "⬆ Versão")
        self.btn_atualizar = self._botao(linha, "Atualizar agora", self._clicar_atualizar, destaque=True)
        self.btn_atualizar.configure(state="disabled")
        self._botao(linha, "Procurar de novo", lambda: self._em_segundo_plano(self._verificar_versao))

        _, self.lbl_dependencias, linha = self._cartao(corpo, "📦 Dependências", sem_primeira=True)
        self._botao(linha, "Instalar de novo", lambda: self._em_segundo_plano(self._verificar_dependencias))

        _, self.lbl_blender, linha = self._cartao(corpo, "🧊 Blender", sem_primeira=True)
        self._botao(linha, "Conferir de novo", lambda: self._em_segundo_plano(self._verificar_blender))

        _, self.lbl_logs, linha = self._cartao(corpo, "📝 Logs de erro", sem_primeira=True)
        self._botao(linha, "Abrir pasta de logs", lambda: abrir_pasta(reg.PASTA_LOGS))
        self._botao(linha, "Enviar agora", lambda: self._em_segundo_plano(self._enviar_logs))

        # Ação principal: botão azul (primary) que escurece no hover, como o "Próximo" do app
        self.btn_abrir = tk.Button(corpo, text=self.TEXTO_ABRIR, bg=COR_DESTAQUE, fg=COR_SOBRE_DESTAQUE,
                                   activebackground=COR_TITULO, activeforeground=COR_SOBRE_TITULO,
                                   disabledforeground=COR_APAGADO, bd=0, relief="flat", cursor="hand2",
                                   highlightthickness=1, highlightbackground=COR_DESTAQUE, highlightcolor=COR_TEXTO,
                                   font=f["abrir"], pady=12, command=self._clicar_abrir)
        self.btn_abrir.pack(fill="x", pady=(12, 12))
        self._hover(self.btn_abrir, (COR_DESTAQUE, COR_SOBRE_DESTAQUE), (COR_TITULO, COR_SOBRE_TITULO))

        moldura = tk.Frame(corpo, bg=COR_CAMPO, highlightthickness=1, highlightbackground=COR_BORDA)
        moldura.pack(fill="both", expand=True)
        self.txt = tk.Text(moldura, height=6, bg=COR_CAMPO, fg=COR_SUAVE, font=f["mono"], bd=0,
                           padx=12, pady=8, wrap="word", highlightthickness=0,
                           selectbackground=COR_TITULO, selectforeground=COR_SOBRE_TITULO)
        self.txt.pack(fill="both", expand=True)
        self.txt.configure(state="disabled")

    def _cartao(self, pai, titulo, sem_primeira=False):
        # Cartão igual aos do app: fundo surface-container-low, borda de 1 px, título em azul
        f = self.fontes
        cartao = tk.Frame(pai, bg=COR_CARTAO, padx=16, pady=12, highlightbackground=COR_BORDA, highlightthickness=1)
        cartao.pack(fill="x", pady=(0, 12))
        tk.Label(cartao, text=titulo, fg=COR_DESTAQUE, bg=COR_CARTAO, font=f["cartao"]).pack(anchor="w")
        primeira = None
        if not sem_primeira:
            primeira = tk.Label(cartao, text="", fg=COR_TEXTO, bg=COR_CARTAO, font=f["texto"], anchor="w", justify="left")
            primeira.pack(fill="x", pady=(4, 0))
        segunda = tk.Label(cartao, text="Aguarde...", fg=COR_SUAVE, bg=COR_CARTAO, font=f["suave"],
                           anchor="w", justify="left", wraplength=540)
        segunda.pack(fill="x", pady=(2, 8))
        linha = tk.Frame(cartao, bg=COR_CARTAO)
        linha.pack(fill="x")
        return primeira, segunda, linha

    def _botao(self, pai, texto, comando, destaque=False):
        # destaque: botão principal (primary); senão, secundário (surface-container-high com borda)
        normal = (COR_DESTAQUE, COR_SOBRE_DESTAQUE) if destaque else (COR_BOTAO, COR_TEXTO)
        hover = (COR_TITULO, COR_SOBRE_TITULO) if destaque else (COR_BOTAO_HOVER, COR_TEXTO)
        b = tk.Button(pai, text=texto, bg=normal[0], fg=normal[1],
                      activebackground=hover[0], activeforeground=hover[1],
                      disabledforeground=COR_APAGADO, bd=0, relief="flat", cursor="hand2", padx=16, pady=6,
                      highlightthickness=1, highlightbackground=COR_DESTAQUE if destaque else COR_BORDA,
                      highlightcolor=COR_DESTAQUE, font=self.fontes["botao"], command=comando)
        b.pack(side="left", padx=(0, 8))
        self._hover(b, normal, hover)
        return b

    @staticmethod
    def _hover(botao, normal, hover):
        """Troca as cores com o mouse em cima (como os botões do app); desativado, não muda."""
        def entrar(_evento):
            if str(botao.cget("state")) != "disabled":
                botao.configure(bg=hover[0], fg=hover[1])

        def sair(_evento):
            botao.configure(bg=normal[0], fg=normal[1])

        botao.bind("<Enter>", entrar)
        botao.bind("<Leave>", sair)

    # ---- comunicação com as threads (Tkinter só na thread principal)
    def _ui(self, funcao, *args):
        self.fila.put((funcao, args))

    def _ler_fila(self):
        try:
            while True:
                funcao, args = self.fila.get_nowait()
                funcao(*args)
        except queue.Empty:
            pass
        self.after(100, self._ler_fila)

    def _em_segundo_plano(self, tarefa):
        if self.ocupado:
            self._mostrar("Aguarde: ainda estou terminando a tarefa anterior.")
            return
        self.ocupado = True

        def rodar():
            try:
                tarefa()
            except Exception as e:
                caminho = reg.gravar_excecao("launcher", type(e), e, e.__traceback__)
                self._ui(self._mostrar, f"Erro inesperado: {e}" + (f"\nDetalhes em {caminho}" if caminho else ""))
            finally:
                self.ocupado = False

        threading.Thread(target=rodar, daemon=True).start()

    def _mostrar(self, texto):
        self.txt.configure(state="normal")
        self.txt.insert("end", texto.rstrip() + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _status(self, rotulo, texto, ok=None):
        cor = COR_SUAVE if ok is None else (COR_OK if ok else COR_AVISO)
        icone = "" if ok is None else ("✅ " if ok else "⚠ ")
        rotulo.configure(text=icone + texto, fg=cor)

    # ---- tarefas
    def _verificar_tudo(self):
        self._verificar_versao()
        self._verificar_dependencias()
        self._verificar_blender()
        self._enviar_logs()

    def _verificar_versao(self):
        self._ui(self.btn_atualizar.configure, {"state": "disabled"})
        self._ui(self._status, self.lbl_atualizacao, "Procurando atualização no GitHub...")
        info = verificar_atualizacao()
        self.info_atualizacao = info
        local = info["local"]
        origem = {"git": "clone git", "zip": "baixada em zip"}.get(local["fonte"], "sem informação de versão")
        self._ui(self.lbl_versao.configure, {"text": f"Versão atual: {reg.texto_versao(local)}  ·  {origem}"})
        ok = info["status"] in ("atualizado", "a_frente")
        self._ui(self._status, self.lbl_atualizacao, info["mensagem"], ok)
        if info["status"] == "disponivel":
            self._ui(self.btn_atualizar.configure, {"state": "normal"})

    def _verificar_dependencias(self):
        self._ui(self._status, self.lbl_dependencias, "Instalando/conferindo (pip)...")
        ok, msg = instalar_dependencias()
        self._ui(self._status, self.lbl_dependencias, msg.splitlines()[0], ok)
        if not ok:
            caminho = reg.gravar_log("launcher", "pip install falhou", msg)
            self._ui(self._mostrar, msg + (f"\nDetalhes em {caminho}" if caminho else ""))

    def _verificar_blender(self):
        ok, msg = verificar_blender()
        self._ui(self._status, self.lbl_blender, msg, ok)

    def _enviar_logs(self):
        pendentes = reg.logs_pendentes()
        if not reg.logs_locais():
            self._ui(self._status, self.lbl_logs, "Nenhum erro registrado.", True)
            return
        if not pendentes:
            self._ui(self._status, self.lbl_logs, "Nenhum erro novo. Os anteriores já foram enviados.", True)
            return
        self._ui(self._status, self.lbl_logs, f"Enviando {len(pendentes)} log(s) de erro para o GitHub...")
        enviados, erro = reg.enviar_logs()
        if enviados:
            self._ui(self._status, self.lbl_logs,
                     f"{len(enviados)} log(s) de erro enviado(s) para o GitHub (branch '{reg.RAMO_LOGS}').", True)
        else:
            self._ui(self._status, self.lbl_logs,
                     f"{len(pendentes)} log(s) de erro guardado(s) neste PC, em:\n{reg.PASTA_LOGS}\n"
                     f"Não foram enviados: {erro}.", False)

    # ---- botões
    def _clicar_atualizar(self):
        info = self.info_atualizacao
        if not info or info.get("status") != "disponivel":
            return
        if not messagebox.askyesno("Atualizar", "Baixar a versão nova do GitHub agora?\nA sua configuração (config.local.json) não será mudada."):
            return

        def tarefa():
            self._ui(self._status, self.lbl_atualizacao, "Atualizando...")
            ok, msg = atualizar(info)
            self._ui(self._mostrar, msg)
            if not ok:
                caminho = reg.gravar_log("launcher", "atualização falhou", msg)
                self._ui(self._status, self.lbl_atualizacao, "A atualização falhou. Veja os detalhes abaixo.", False)
                if caminho:
                    self._ui(self._mostrar, f"Detalhes em {caminho}")
                return
            self._verificar_versao()
            self._verificar_dependencias()
            self._ui(self._mostrar, "Pronto. Feche e abra o launcher de novo para usar a versão nova dele.")

        self._em_segundo_plano(tarefa)

    def _clicar_abrir(self):
        """Abre o app; se ele abrir, o launcher se fecha sozinho. Se não, fica aberto com o erro."""
        if self.abrindo:
            return
        self.abrindo = True
        self.btn_abrir.configure(state="disabled", text="Abrindo o app...")
        self._mostrar("Abrindo o app...")

        def tarefa():
            try:
                ok, msg = abrir_app()
            except Exception as e:
                ok, msg = False, f"Erro inesperado ao abrir o app: {e}\n\n{traceback.format_exc()}"
            self._ui(self._resultado_abrir, ok, msg)

        threading.Thread(target=tarefa, daemon=True).start()

    def _resultado_abrir(self, ok, msg):
        self.abrindo = False
        if ok:
            self._mostrar(msg + " Fechando o launcher...")
            self._fechar_quando_livre()
            return
        self.btn_abrir.configure(state="normal", text=self.TEXTO_ABRIR)
        caminho = reg.gravar_log("launcher", "o app não abriu", msg)
        detalhe = f"\n\nDetalhes em {caminho}" if caminho else ""
        self._mostrar("O app não abriu:\n" + msg + detalhe)
        messagebox.showerror("O app não abriu", "Não deu para abrir o app:\n\n" + msg[-1500:] + detalhe, parent=self)

    def _fechar_quando_livre(self, avisou=False):
        """Fecha o launcher; se ainda houver uma tarefa rodando (pip, atualização), espera ela acabar."""
        if self.ocupado:
            if not avisou:
                self._mostrar("O launcher fecha quando terminar a tarefa em andamento.")
            self.after(500, self._fechar_quando_livre, True)
            return
        self.destroy()


def abrir_launcher_web():
    """Janela no visual novo (launcher_web.py, pywebview). Levanta exceção se não der."""
    import launcher_web
    launcher_web.iniciar()


def abrir_launcher_tk():
    """Janela Tkinter (a de sempre): reserva obrigatória, porque é o launcher que instala o pywebview."""
    if tk is None:
        print("O Tkinter não está instalado neste Python.")
        sys.exit(1)
    Launcher().mainloop()


def motivo_sem_web(importar=None, webview2_instalado=None):
    """None se a janela web pode ser tentada; senão, (motivo, detalhes) para o log."""
    importar = importar or __import__
    try:
        importar("webview")
    except Exception as e:
        return (f"o pywebview não está instalado ou não carregou ({type(e).__name__}: {e})", traceback.format_exc())
    if webview2_instalado is None:
        import app
        webview2_instalado = app.webview2_instalado
    if not webview2_instalado():
        return ("o WebView2 (motor do Edge usado pela janela) não está instalado neste Windows",
                "Instale o 'Microsoft Edge WebView2 Runtime' (gratuito, da Microsoft).")
    return None


def main(argv=None, abrir_web=abrir_launcher_web, abrir_tk=abrir_launcher_tk, sem_web=motivo_sem_web):
    """Abre o launcher: o visual novo (pywebview) ou, se ele faltar ou falhar, a janela Tkinter.
    Devolve 'web', 'tk' ou 'config' (--preparar-config)."""
    argv = sys.argv[1:] if argv is None else argv
    if "--preparar-config" in argv:
        # Chamado pelo instalador (instalar.ps1): resposta em JSON só com ASCII, para o
        # PowerShell ler sem problema de acentos
        print(json.dumps(preparar_config(), ensure_ascii=True))
        return "config"
    reg.instalar_ganchos("launcher")
    os.chdir(PASTA)
    if "--tk" not in argv:
        problema = sem_web()
        if problema is None:
            try:
                abrir_web()
                return "web"
            except Exception as e:
                problema = (f"a janela web do launcher não abriu ({type(e).__name__}: {e})", traceback.format_exc())
        # Sem o pywebview (ainda não instalado) é o caminho normal da 1ª vez: sem log de erro
        if not problema[0].startswith("o pywebview não está instalado"):
            reg.gravar_log("launcher", "Launcher web indisponível: " + problema[0],
                           "O launcher abriu a janela Tkinter (reserva).\n\n" + problema[1])
    abrir_tk()
    return "tk"


if __name__ == "__main__":
    main()
