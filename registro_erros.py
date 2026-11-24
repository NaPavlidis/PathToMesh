"""Registro de erros do Phy-2d-by-3d (usado pelo app_ui.py e pelo launcher.py).

- Grava cada erro em logs/erro-AAAAMMDD-HHMMSS.log, com a versão (commit), o sistema e o traceback.
- Higieniza o texto antes de gravar: o repositório é público, então caminhos do PC viram
  <CAMINHO>/<nome-do-arquivo>, nomes de usuário viram <USUARIO> e valores do config.json viram <CONFIG>.
- Envia os logs novos para a branch 'logs' do GitHub (nunca a main), sem mexer na branch
  de trabalho, no índice nem nos arquivos do usuário: monta o commit com os comandos
  internos do git (hash-object, mktree, commit-tree) e faz push direto para refs/heads/logs.

Não usa Tkinter nem bpy, para poder ser testado sem janela.
"""
import datetime
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import traceback

PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))
PASTA_LOGS = os.path.join(PASTA_PROJETO, "logs")
ARQUIVO_VERSAO = ".versao"          # gravado pelo launcher quando atualiza sem git (zip)
ARQUIVO_ENVIADOS = ".enviados"      # dentro de logs/: nomes dos logs já enviados
RAMO_LOGS = "logs"

# Identidade neutra para os commits de log (não expõe o nome nem o e-mail do usuário)
_AUTOR_LOGS = {
    "GIT_AUTHOR_NAME": "Launcher Phy-2d-by-3d",
    "GIT_AUTHOR_EMAIL": "launcher@phy-2d-by-3d.invalid",
    "GIT_COMMITTER_NAME": "Launcher Phy-2d-by-3d",
    "GIT_COMMITTER_EMAIL": "launcher@phy-2d-by-3d.invalid",
}
# Sem janelas de senha: se não houver credencial salva, o push só falha
_SEM_PERGUNTA = {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


# ---------------------------------------------------------------- git

def tem_git():
    return shutil.which("git") is not None


def git(pasta, *args, entrada=None, env_extra=None, timeout=60):
    """Roda git na pasta. Devolve (código, stdout, stderr) em texto."""
    env = os.environ.copy()
    env.update(_SEM_PERGUNTA)
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(["git", "-C", pasta] + list(args), input=entrada, capture_output=True,
                           timeout=timeout, env=env, creationflags=SEM_JANELA)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, "", str(e)
    return (r.returncode, r.stdout.decode("utf-8", "replace").strip(),
            r.stderr.decode("utf-8", "replace").strip())


def eh_clone_git(pasta=PASTA_PROJETO):
    """True se o git está instalado e a pasta é a raiz de um clone."""
    if not tem_git():
        return False
    codigo, raiz, _ = git(pasta, "rev-parse", "--show-toplevel")
    if codigo != 0 or not raiz:
        return False
    try:
        return os.path.samefile(raiz, pasta)
    except OSError:
        return os.path.normcase(os.path.abspath(raiz)) == os.path.normcase(os.path.abspath(pasta))


# ---------------------------------------------------------------- versão

def versao_atual(pasta=PASTA_PROJETO):
    """Versão instalada: {'sha', 'curto', 'data', 'fonte'} (fonte: git, zip ou desconhecida)."""
    if eh_clone_git(pasta):
        codigo, saida, _ = git(pasta, "log", "-1", "--format=%H%x09%cs")
        if codigo == 0 and "\t" in saida:
            sha, data = saida.split("\t", 1)
            return {"sha": sha, "curto": sha[:7], "data": data, "fonte": "git"}
    try:
        with open(os.path.join(pasta, ARQUIVO_VERSAO), "r", encoding="utf-8") as f:
            dados = json.load(f)
        sha = str(dados.get("sha", ""))
        if re.fullmatch(r"[0-9a-f]{7,40}", sha):
            return {"sha": sha, "curto": sha[:7], "data": str(dados.get("data", "")), "fonte": "zip"}
    except (OSError, ValueError, AttributeError):
        pass
    return {"sha": "", "curto": "desconhecida", "data": "", "fonte": "desconhecida"}


def texto_versao(v):
    return f"{v['curto']} ({v['data']})" if v.get("data") else v["curto"]


# ---------------------------------------------------------------- higienização

# Caminho com letra de unidade (C:\..., F:/..., e C:\\... dentro de repr). Vai até aspas, fim de
# linha ou o começo de outro caminho; espaços entram, porque pastas do Windows têm espaço.
_RE_UNIDADE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:(?:\\|/)(?:(?![A-Za-z]:[\\/])[^\r\n\"'<>|*?])*")
# Caminho de rede \\servidor\pasta\...
_RE_UNC = re.compile(r"\\{2,4}[A-Za-z0-9._$-]+\\{1,2}[^\r\n\"'<>|*?]*")
# Caminhos de usuário em Linux/macOS (sem espaço)
_RE_UNIX = re.compile(r"(?<![\w.:/>])/(?:home|Users|root|mnt|media|tmp|var|opt|srv)(?:/[^\s\"'<>|:]*)?")
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_RE_TOKEN = re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b")
_RE_URL_CREDENCIAL = re.compile(r"(https?://)[^/\s:@]+(?::[^/\s@]*)?@")


def _nome_final(caminho):
    sobra = caminho[len(caminho.rstrip()):]      # espaço depois do caminho volta para o texto
    partes = [p for p in re.split(r"[\\/]+", caminho.rstrip()) if p.strip()]
    if len(partes) <= 1:          # só a unidade ("C:") ou nada
        return "<CAMINHO>" + sobra
    return "<CAMINHO>/" + partes[-1].strip() + sobra


def _valores_config(pasta):
    try:
        with open(os.path.join(pasta, "config.json"), "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(dados, dict):
        return []
    return [v for v in dados.values() if isinstance(v, str) and len(v.strip()) >= 3]


def _nomes_usuario():
    nomes = set()
    for var in ("USERNAME", "USER", "LOGNAME", "COMPUTERNAME", "USERDOMAIN"):
        valor = os.environ.get(var)
        if valor:
            nomes.add(valor)
    try:
        nomes.add(getpass.getuser())
    except Exception:
        pass
    casa = os.path.basename(os.path.expanduser("~").rstrip("\\/"))
    if casa:
        nomes.add(casa)
    return sorted((n for n in nomes if len(n) >= 3), key=len, reverse=True)


def higienizar(texto, pasta=PASTA_PROJETO, valores_config=None, nomes_usuario=None):
    """Tira do texto tudo o que identifica o PC: caminhos, usuário, conteúdo do config.json."""
    if texto is None:
        return ""
    texto = str(texto)
    if valores_config is None:
        valores_config = _valores_config(pasta)
    if nomes_usuario is None:
        nomes_usuario = _nomes_usuario()

    texto = _RE_TOKEN.sub("<TOKEN>", texto)
    texto = _RE_URL_CREDENCIAL.sub(r"\1", texto)
    texto = _RE_UNIDADE.sub(lambda m: _nome_final(m.group(0)), texto)
    texto = _RE_UNC.sub(lambda m: _nome_final(m.group(0)), texto)
    texto = _RE_UNIX.sub(lambda m: _nome_final(m.group(0)), texto)
    texto = _RE_EMAIL.sub("<EMAIL>", texto)

    # Valores do config.json que sobraram (ex.: o nome da cena .blend escolhida)
    for valor in sorted(valores_config, key=len, reverse=True):
        variantes = {valor, valor.replace("\\", "/"), valor.replace("/", "\\"),
                     valor.replace("\\", "\\\\"), valor.replace("/", "\\\\")}
        for v in sorted(variantes, key=len, reverse=True):
            texto = re.sub(re.escape(v), "<CONFIG>", texto, flags=re.IGNORECASE)

    for nome in nomes_usuario:
        texto = re.sub(r"(?<![A-Za-z0-9])" + re.escape(nome) + r"(?![A-Za-z0-9])", "<USUARIO>",
                       texto, flags=re.IGNORECASE)
    return texto


# ---------------------------------------------------------------- gravar

def descricao_sistema():
    return (f"{platform.system()} {platform.release()} ({platform.version()}), "
            f"Python {platform.python_version()}")


def _nome_livre(pasta_logs, agora):
    base = "erro-" + agora.strftime("%Y%m%d-%H%M%S")
    nome = base + ".log"
    n = 2
    while os.path.exists(os.path.join(pasta_logs, nome)):
        nome = f"{base}-{n}.log"
        n += 1
    return nome


def gravar_log(origem, resumo, detalhes="", pasta=PASTA_PROJETO, pasta_logs=None, agora=None):
    """Grava um log higienizado e devolve o caminho do arquivo (ou None se não conseguir)."""
    pasta_logs = pasta_logs or os.path.join(pasta, "logs")
    agora = agora or datetime.datetime.now()
    try:
        versao = texto_versao(versao_atual(pasta))
    except Exception:
        versao = "desconhecida"
    texto = (
        "Phy-2d-by-3d - registro de erro\n"
        f"Data: {agora.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Origem: {origem}\n"
        f"Versão: {versao}\n"
        f"Sistema: {descricao_sistema()}\n"
        f"Resumo: {resumo}\n"
        "\n"
        f"{detalhes}\n"
    )
    texto = higienizar(texto, pasta)
    try:
        os.makedirs(pasta_logs, exist_ok=True)
        caminho = os.path.join(pasta_logs, _nome_livre(pasta_logs, agora))
        with open(caminho, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        return caminho
    except OSError:
        return None


def gravar_excecao(origem, tipo, valor, tb, pasta=PASTA_PROJETO):
    detalhes = "".join(traceback.format_exception(tipo, valor, tb))
    return gravar_log(origem, f"{tipo.__name__}: {valor}", detalhes, pasta)


def instalar_ganchos(origem, pasta=PASTA_PROJETO):
    """Grava em log toda exceção não tratada (thread principal e outras threads)."""
    anterior = sys.excepthook

    def gancho(tipo, valor, tb):
        if not issubclass(tipo, KeyboardInterrupt):
            gravar_excecao(origem, tipo, valor, tb, pasta)
        anterior(tipo, valor, tb)

    sys.excepthook = gancho

    anterior_thread = threading.excepthook

    def gancho_thread(args):
        if args.exc_type is not SystemExit:
            gravar_excecao(f"{origem} (thread {getattr(args.thread, 'name', '?')})",
                           args.exc_type, args.exc_value, args.exc_traceback, pasta)
        anterior_thread(args)

    threading.excepthook = gancho_thread


def gancho_tk(origem, pasta=PASTA_PROJETO):
    """Função para Tk.report_callback_exception (erros dentro de botões e eventos)."""
    def relatar(tipo, valor, tb):
        gravar_excecao(origem, tipo, valor, tb, pasta)
        traceback.print_exception(tipo, valor, tb)
    return relatar


# ---------------------------------------------------------------- enviar

def logs_locais(pasta_logs=PASTA_LOGS):
    try:
        return sorted(n for n in os.listdir(pasta_logs) if n.startswith("erro-") and n.endswith(".log"))
    except OSError:
        return []


def _ja_enviados(pasta_logs):
    try:
        with open(os.path.join(pasta_logs, ARQUIVO_ENVIADOS), "r", encoding="utf-8") as f:
            return {linha.strip() for linha in f if linha.strip()}
    except OSError:
        return set()


def logs_pendentes(pasta_logs=PASTA_LOGS):
    enviados = _ja_enviados(pasta_logs)
    return [n for n in logs_locais(pasta_logs) if n not in enviados]


def _marcar_enviados(pasta_logs, nomes):
    with open(os.path.join(pasta_logs, ARQUIVO_ENVIADOS), "a", encoding="utf-8") as f:
        for n in nomes:
            f.write(n + "\n")


def _ler_arvore(pasta, ref):
    """Entradas de uma árvore: lista de (modo, tipo, sha, nome)."""
    codigo, saida, erro = git(pasta, "ls-tree", "-z", ref)
    if codigo != 0:
        raise RuntimeError(erro or "git ls-tree falhou")
    entradas = []
    for item in saida.split("\0"):
        if not item.strip():
            continue
        cabeca, nome = item.split("\t", 1)
        modo, tipo, sha = cabeca.split()
        entradas.append((modo, tipo, sha, nome))
    return entradas


def _criar_arvore(pasta, entradas):
    entrada = "".join(f"{m} {t} {s}\t{n}\0" for m, t, s, n in entradas).encode("utf-8")
    codigo, sha, erro = git(pasta, "mktree", "-z", entrada=entrada)
    if codigo != 0:
        raise RuntimeError(erro or "git mktree falhou")
    return sha


def _criar_blob(pasta, conteudo_bytes):
    codigo, sha, erro = git(pasta, "hash-object", "-w", "--stdin", entrada=conteudo_bytes)
    if codigo != 0:
        raise RuntimeError(erro or "git hash-object falhou")
    return sha


_LEIAME_LOGS = (
    "# Logs de erro\n\n"
    "Branch só com os logs de erro enviados pelo launcher do Phy-2d-by-3d (pasta `logs/`).\n"
    "Os logs são higienizados (sem caminhos do PC, nomes de usuário nem config.json).\n"
    "Não faça merge desta branch na main.\n"
)


def enviar_logs(pasta=PASTA_PROJETO, remoto="origin", ramo=RAMO_LOGS):
    """Envia os logs pendentes para a branch de logs. Devolve (enviados, erro)."""
    pasta_logs = os.path.join(pasta, "logs")
    pendentes = logs_pendentes(pasta_logs)
    if not pendentes:
        return [], None
    if not eh_clone_git(pasta):
        return [], "sem git (ou a pasta não é um clone do repositório)"
    codigo, _, _ = git(pasta, "remote", "get-url", remoto)
    if codigo != 0:
        return [], f"o clone não tem o remoto '{remoto}'"

    try:
        for tentativa in range(2):
            codigo, saida, erro = git(pasta, "ls-remote", "--heads", remoto, ramo, timeout=60)
            if codigo != 0:
                return [], "não deu para falar com o GitHub: " + higienizar(erro, pasta)
            pai = None
            if saida.strip():
                codigo, _, erro = git(pasta, "fetch", "-q", "--no-tags", remoto, f"refs/heads/{ramo}", timeout=120)
                if codigo != 0:
                    return [], "não deu para baixar a branch de logs: " + higienizar(erro, pasta)
                _, pai, _ = git(pasta, "rev-parse", "FETCH_HEAD")

            raiz = _ler_arvore(pasta, pai) if pai else []
            entradas_logs = []
            for modo, tipo, sha, nome in raiz:
                if nome == "logs" and tipo == "tree":
                    entradas_logs = _ler_arvore(pasta, sha)
            nomes_remotos = {e[3] for e in entradas_logs}

            enviados = []
            for nome in pendentes:
                with open(os.path.join(pasta_logs, nome), "r", encoding="utf-8", errors="replace") as f:
                    conteudo = higienizar(f.read(), pasta)        # higieniza de novo, por segurança
                destino, n = nome, 2
                while destino in nomes_remotos:
                    destino = nome[:-4] + f"-{n}.log"
                    n += 1
                nomes_remotos.add(destino)
                blob = _criar_blob(pasta, conteudo.encode("utf-8"))
                entradas_logs.append(("100644", "blob", blob, destino))
                enviados.append(nome)

            arvore_logs = _criar_arvore(pasta, entradas_logs)
            nova_raiz = [e for e in raiz if e[3] != "logs"]
            nova_raiz.append(("040000", "tree", arvore_logs, "logs"))
            if not any(e[3] == "README.md" for e in nova_raiz):
                nova_raiz.append(("100644", "blob", _criar_blob(pasta, _LEIAME_LOGS.encode("utf-8")), "README.md"))
            arvore = _criar_arvore(pasta, nova_raiz)

            args = ["commit-tree", arvore, "-m", f"Logs de erro: {len(enviados)} novo(s)"]
            if pai:
                args += ["-p", pai]
            codigo, commit, erro = git(pasta, *args, env_extra=_AUTOR_LOGS)
            if codigo != 0:
                return [], "não deu para montar o commit de logs: " + higienizar(erro, pasta)

            codigo, _, erro = git(pasta, "push", "-q", "--no-verify", remoto, f"{commit}:refs/heads/{ramo}", timeout=180)
            if codigo == 0:
                _marcar_enviados(pasta_logs, enviados)
                return enviados, None
            if tentativa == 0 and ("rejected" in erro or "fetch first" in erro or "non-fast-forward" in erro):
                continue        # alguém enviou logs ao mesmo tempo: tenta de novo por cima
            return [], "o GitHub recusou o envio (sem credencial ou sem permissão): " + higienizar(erro, pasta)
        return [], "o GitHub recusou o envio"
    except (OSError, RuntimeError, ValueError) as e:
        return [], "erro ao preparar o envio: " + higienizar(str(e), pasta)
