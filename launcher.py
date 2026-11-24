"""Launcher do Phy-2d-by-3d (Windows).

Ao abrir:
  1. procura atualização no GitHub (git, se a pasta for um clone; senão a API pública e o zip da main);
  2. instala as dependências (pip install -r requirements.txt);
  3. confere se o blender_path do config.json existe;
  4. envia os logs de erro novos para a branch 'logs' (se houver git com credencial).
Depois é só clicar em "Abrir o app".

A lógica fica em funções sem Tkinter, para poder ser testada sem janela.
"""
import io
import json
import os
import queue
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile

import registro_erros as reg

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:     # permite importar a lógica sem Tkinter (testes)
    tk = None
    messagebox = None

PASTA = reg.PASTA_PROJETO
REPO = "NaPavlidis/Phy-2d-by-3d"
RAMO = "main"
URL_REPO = f"https://github.com/{REPO}.git"
URL_API_COMMIT = f"https://api.github.com/repos/{REPO}/commits/{RAMO}"
URL_ZIP = "https://codeload.github.com/" + REPO + "/zip/{sha}"

# Na atualização pelo zip estes nunca são sobrescritos (o config.json só é criado se faltar)
PRESERVAR = {"config.json"}
IGNORAR_NO_ZIP = {".git", "logs", ".venv", "venv", "__pycache__", reg.ARQUIVO_VERSAO}

# Paleta do app_ui.py
COR_FUNDO = "#0B0F17"
COR_BARRA = "#0F141C"
COR_CARTAO = "#121824"
COR_CAMPO = "#080C14"
COR_BOTAO = "#1E2638"
COR_DESTAQUE = "#38BDF8"
COR_TITULO = "#4C9EEB"
COR_OK = "#34D399"
COR_TEXTO = "#FFFFFF"
COR_SUAVE = "#A0AEC0"
COR_APAGADO = "#4A5568"
COR_LINHA = "#1A202C"


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
        "User-Agent": "Phy-2d-by-3d-launcher", "Accept": "application/vnd.github+json"})
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

def atualizar_git(pasta=PASTA):
    """git pull --ff-only, guardando o config.json do usuário. Devolve (ok, mensagem)."""
    caminho_config = os.path.join(pasta, "config.json")
    copia = None
    if os.path.exists(caminho_config):
        with open(caminho_config, "rb") as f:
            copia = f.read()
        # Se o usuário mudou o config.json, ele sai do caminho do pull e volta depois
        reg.git(pasta, "checkout", "--", "config.json")
    try:
        codigo, saida, erro = reg.git(pasta, "pull", "--ff-only", "--no-rebase", _remoto_git(pasta), RAMO, timeout=180)
    finally:
        if copia is not None:
            with open(caminho_config, "wb") as f:
                f.write(copia)
    if codigo != 0:
        return False, "O git não conseguiu atualizar:\n" + (erro or saida)
    return True, "Atualizado pelo git."


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
                                    headers={"User-Agent": "Phy-2d-by-3d-launcher"})
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            dados = r.read()
    except (urllib.error.URLError, OSError) as e:
        return False, f"Não deu para baixar a atualização: {e}"
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


def instalar_dependencias(pasta=PASTA):
    requisitos = os.path.join(pasta, "requirements.txt")
    if not os.path.isfile(requisitos):
        return True, "Sem requirements.txt: nada para instalar."
    comando = [python_console(), "-m", "pip", "install", "--disable-pip-version-check", "-r", requisitos]
    try:
        r = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600, cwd=pasta, creationflags=reg.SEM_JANELA)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Não deu para rodar o pip: {e}"
    if r.returncode != 0:
        return False, "O pip falhou:\n" + (r.stderr or r.stdout)[-3000:]
    return True, "Dependências instaladas."


def ler_config(pasta=PASTA):
    """Devolve (dados, erro)."""
    caminho = os.path.join(pasta, "config.json")
    if not os.path.isfile(caminho):
        return None, "Não achei o config.json na pasta do projeto."
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except ValueError as e:
        return None, f"O config.json tem um erro de formato: {e}"
    except OSError as e:
        return None, f"Não deu para ler o config.json: {e}"
    if not isinstance(dados, dict):
        return None, "O config.json não está no formato esperado."
    return dados, None


def verificar_blender(pasta=PASTA):
    """Devolve (ok, mensagem)."""
    dados, erro = ler_config(pasta)
    if erro:
        return False, erro
    caminho = dados.get("blender_path")
    if not caminho or not isinstance(caminho, str):
        return False, "O config.json não tem o blender_path. Ajuste nas configurações do app (⚙)."
    if not os.path.isfile(caminho):
        return False, f"O Blender não foi encontrado em:\n{caminho}\nAjuste nas configurações do app (⚙)."
    return True, f"Blender encontrado: {caminho}"


def abrir_app(pasta=PASTA):
    subprocess.Popen([sys.executable, os.path.join(pasta, "app_ui.py")], cwd=pasta)


def abrir_pasta(caminho):
    os.makedirs(caminho, exist_ok=True)
    if hasattr(os, "startfile"):
        os.startfile(caminho)


# ---------------------------------------------------------------- janela

class Launcher(tk.Tk if tk else object):
    def __init__(self):
        super().__init__()
        self.title("Phy-2d-by-3d - Launcher")
        self.geometry("620x640")
        self.minsize(560, 560)
        self.configure(bg=COR_FUNDO)
        self.report_callback_exception = reg.gancho_tk("launcher")
        self.fila = queue.Queue()
        self.info_atualizacao = None
        self.ocupado = False
        self._montar()
        self.after(100, self._ler_fila)
        self._em_segundo_plano(self._verificar_tudo)

    # ---- montagem
    def _montar(self):
        barra = tk.Frame(self, bg=COR_BARRA, padx=20, pady=10)
        barra.pack(fill="x")
        tk.Label(barra, text="Phy-2d-by-3d", fg=COR_TITULO, bg=COR_BARRA, font=("Helvetica", 14, "bold")).pack(side="left")
        tk.Label(barra, text="LAUNCHER", fg=COR_APAGADO, bg=COR_BARRA, font=("Helvetica", 8, "bold")).pack(side="left", padx=10, pady=(4, 0))

        corpo = tk.Frame(self, bg=COR_FUNDO, padx=20, pady=12)
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

        tk.Button(corpo, text="▶  Abrir o app", bg=COR_DESTAQUE, fg=COR_TEXTO, activebackground=COR_TITULO,
                  activeforeground=COR_TEXTO, bd=0, font=("Helvetica", 12, "bold"), pady=10,
                  command=self._clicar_abrir).pack(fill="x", pady=(10, 8))

        self.txt = tk.Text(corpo, height=6, bg=COR_CAMPO, fg=COR_SUAVE, font=("Consolas", 9), bd=0,
                           padx=8, pady=6, wrap="word")
        self.txt.pack(fill="both", expand=True)
        self.txt.configure(state="disabled")

    def _cartao(self, pai, titulo, sem_primeira=False):
        cartao = tk.Frame(pai, bg=COR_CARTAO, padx=14, pady=10, highlightbackground=COR_LINHA, highlightthickness=1)
        cartao.pack(fill="x", pady=5)
        tk.Label(cartao, text=titulo, fg=COR_DESTAQUE, bg=COR_CARTAO, font=("Helvetica", 10, "bold")).pack(anchor="w")
        primeira = None
        if not sem_primeira:
            primeira = tk.Label(cartao, text="", fg=COR_TEXTO, bg=COR_CARTAO, font=("Helvetica", 9), anchor="w", justify="left")
            primeira.pack(fill="x")
        segunda = tk.Label(cartao, text="Aguarde...", fg=COR_SUAVE, bg=COR_CARTAO, font=("Helvetica", 9),
                           anchor="w", justify="left", wraplength=540)
        segunda.pack(fill="x", pady=(2, 6))
        linha = tk.Frame(cartao, bg=COR_CARTAO)
        linha.pack(fill="x")
        return primeira, segunda, linha

    def _botao(self, pai, texto, comando, destaque=False):
        b = tk.Button(pai, text=texto, bg=COR_DESTAQUE if destaque else COR_BOTAO, fg=COR_TEXTO,
                      activebackground=COR_TITULO if destaque else COR_CAMPO, activeforeground=COR_TEXTO,
                      disabledforeground=COR_APAGADO, bd=0, padx=12, pady=4, font=("Helvetica", 9, "bold"),
                      command=comando)
        b.pack(side="left", padx=(0, 8))
        return b

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
        cor = COR_SUAVE if ok is None else (COR_OK if ok else COR_TEXTO)
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
        if not messagebox.askyesno("Atualizar", "Baixar a versão nova do GitHub agora?\nO seu config.json não será mudado."):
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
        try:
            abrir_app()
        except OSError as e:
            caminho = reg.gravar_excecao("launcher", type(e), e, e.__traceback__)
            messagebox.showerror("Erro", f"Não deu para abrir o app:\n{e}" + (f"\n\nDetalhes em {caminho}" if caminho else ""))
            return
        self._mostrar("App aberto.")


def main():
    reg.instalar_ganchos("launcher")
    if tk is None:
        print("O Tkinter não está instalado neste Python.")
        sys.exit(1)
    os.chdir(PASTA)
    Launcher().mainloop()


if __name__ == "__main__":
    main()
