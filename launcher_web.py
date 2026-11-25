"""Launcher do PathToMesh no visual novo (pywebview + WebView2, o mesmo estilo de ui_web/).

Faz o mesmo que a janela Tkinter do launcher.py, com as mesmas funções de lá:
  1. procura atualização no GitHub (e atualiza, depois de confirmar);
  2. instala as dependências (pip: requirements-base.txt, o requirements.txt, com o pywebview, e o
     requirements-opcional.txt, com o Pillow, que só grava o log se falhar);
  3. confere o Blender do config.local.json;
  4. envia os logs de erro novos para a branch 'logs';
e "Abrir o app" abre o app como um processo independente e fecha o launcher sozinho (se o app
não abrir, o launcher fica aberto, mostra o erro e grava o log).

A tela fica em ui_web/launcher.html (+ launcher.js e o estilo.css do app). O pywebview só é
importado dentro de iniciar(): a ApiLauncher pode ser usada (e testada) sem janela. Se o pywebview
faltar ou a janela falhar, o launcher.py abre a janela Tkinter (reserva obrigatória: é o launcher
que instala o pywebview).
"""
import json
import os
import queue
import threading
import traceback

import launcher
import registro_erros as reg
import tema_janela

PASTA_WEB = os.path.join(reg.PASTA_PROJETO, "ui_web")
PAGINA = os.path.join(PASTA_WEB, "launcher.html")
ORIGEM = "launcher"

TEXTO_ABRIR = launcher.Launcher.TEXTO_ABRIR
TEXTO_ABRINDO = "Abrindo o app..."
PERGUNTA_ATUALIZAR = ("Baixar a versão nova do GitHub agora?\n"
                      "A sua configuração (config.local.json) não será mudada.")


class ApiLauncher:
    """Métodos chamados pelo launcher.js (window.pywebview.api.<método>). As tarefas demoradas
    rodam numa thread; o resultado chega à tela por window.ptmLauncher.evento({...})."""

    def __init__(self, tarefas=None, abrir_pasta=None):
        self._janela = None
        self._fila = queue.Queue()
        self._eventos = []                 # sem janela (testes), os eventos ficam aqui
        self._ocupado = False
        self._abrindo = False
        self._fechar_pedido = False
        self._info_atualizacao = None
        self._threads = []
        # funções do launcher.py (os testes trocam por funções de mentira)
        self._f = dict(verificar_atualizacao=launcher.verificar_atualizacao,
                       instalar_dependencias=launcher.instalar_dependencias,
                       verificar_blender=launcher.verificar_blender,
                       atualizar=launcher.atualizar, abrir_app=launcher.abrir_app,
                       logs_locais=reg.logs_locais, logs_pendentes=reg.logs_pendentes,
                       enviar_logs=reg.enviar_logs)
        self._f.update(tarefas or {})
        self._abrir_pasta = abrir_pasta or launcher.abrir_pasta
        threading.Thread(target=self._enviar_fila, name="eventos-launcher", daemon=True).start()

    # ------------------------------------------------------------ janela e eventos
    def _ligar_janela(self, janela):
        self._janela = janela

    def _enviar(self, dados):
        self._fila.put(dados)

    def _enviar_fila(self):
        while True:
            dados = self._fila.get()
            if dados is None:
                return
            janela = self._janela
            if janela is None:
                self._eventos.append(dados)
                continue
            if dados.get("tipo") == "fechar":
                try:
                    janela.destroy()
                except Exception:
                    pass
                continue
            try:
                janela.evaluate_js("window.ptmLauncher && window.ptmLauncher.evento(%s)"
                                   % json.dumps(dados, ensure_ascii=False))
            except Exception as e:
                reg.gravar_log(f"{ORIGEM} (interface web)", f"Não deu para atualizar a tela: {e}", traceback.format_exc())

    def _esperar(self, timeout=10):
        """Testes: espera as tarefas e a fila terminarem e devolve os eventos."""
        for t in list(self._threads):
            t.join(timeout)
        self._fila.put({"tipo": "_fim"})
        for _ in range(int(timeout * 100)):
            if self._eventos and self._eventos[-1].get("tipo") == "_fim":
                self._eventos.pop()
                break
            threading.Event().wait(0.01)
        return list(self._eventos)

    def _status(self, cartao, texto, ok=None):
        self._enviar({"tipo": "status", "cartao": cartao, "texto": texto, "ok": ok})

    def _mostrar(self, texto):
        self._enviar({"tipo": "mensagem", "texto": texto.rstrip()})

    def _botao(self, botao, ativo, texto=None):
        dados = {"tipo": "botao", "botao": botao, "ativo": bool(ativo)}
        if texto is not None:
            dados["texto"] = texto
        self._enviar(dados)

    def _em_segundo_plano(self, tarefa):
        """Como o _em_segundo_plano da janela Tk: uma tarefa por vez, erros viram log."""
        if self._ocupado:
            self._mostrar("Aguarde: ainda estou terminando a tarefa anterior.")
            return {"ok": False, "ocupado": True}
        self._ocupado = True

        def rodar():
            try:
                tarefa()
            except Exception as e:
                caminho = reg.gravar_excecao(ORIGEM, type(e), e, e.__traceback__)
                self._mostrar(f"Erro inesperado: {e}" + (f"\nDetalhes em {caminho}" if caminho else ""))
            finally:
                self._ocupado = False

        t = threading.Thread(target=rodar, name="tarefa-launcher", daemon=True)
        self._threads.append(t)
        t.start()
        return {"ok": True}

    # ------------------------------------------------------------ começo
    def estado_inicial(self):
        return {"nome_app": tema_janela.NOME_APP,
                "logos": {"normal": tema_janela.logo_data_uri(tema_janela.LOGOS["normal"]),
                          "largo": tema_janela.logo_data_uri(tema_janela.LOGOS["largo"])},
                "limite_logo": tema_janela.LARGURA_LOGO_LARGO,
                "texto_abrir": TEXTO_ABRIR,
                "pergunta_atualizar": PERGUNTA_ATUALIZAR}

    def verificar_tudo(self):
        return self._em_segundo_plano(self._verificar_tudo)

    # ------------------------------------------------------------ tarefas (as mesmas da janela Tk)
    def _verificar_tudo(self):
        self._verificar_versao()
        self._verificar_dependencias()
        self._verificar_blender()
        self._enviar_logs()

    def _verificar_versao(self):
        self._botao("atualizar", False)
        self._status("atualizacao", "Procurando atualização no GitHub...")
        info = self._f["verificar_atualizacao"]()
        self._info_atualizacao = info
        local = info["local"]
        origem = {"git": "clone git", "zip": "baixada em zip"}.get(local["fonte"], "sem informação de versão")
        self._enviar({"tipo": "versao", "texto": f"Versão atual: {reg.texto_versao(local)}  ·  {origem}"})
        ok = info["status"] in ("atualizado", "a_frente")
        self._status("atualizacao", info["mensagem"], ok)
        if info["status"] == "disponivel":
            self._botao("atualizar", True)

    def _verificar_dependencias(self):
        self._status("dependencias", "Instalando/conferindo (pip)...")
        ok, msg = self._f["instalar_dependencias"]()
        self._status("dependencias", msg.splitlines()[0], ok)
        if not ok:
            caminho = reg.gravar_log(ORIGEM, "pip install falhou", msg)
            self._mostrar(msg + (f"\nDetalhes em {caminho}" if caminho else ""))

    def _verificar_blender(self):
        ok, msg = self._f["verificar_blender"]()
        self._status("blender", msg, ok)

    def _enviar_logs(self):
        pendentes = self._f["logs_pendentes"]()
        if not self._f["logs_locais"]():
            self._status("logs", "Nenhum erro registrado.", True)
            return
        if not pendentes:
            self._status("logs", "Nenhum erro novo. Os anteriores já foram enviados.", True)
            return
        self._status("logs", f"Enviando {len(pendentes)} log(s) de erro para o GitHub...")
        enviados, erro = self._f["enviar_logs"]()
        if enviados:
            self._status("logs", f"{len(enviados)} log(s) de erro enviado(s) para o GitHub (branch '{reg.RAMO_LOGS}').", True)
        else:
            self._status("logs", f"{len(pendentes)} log(s) de erro guardado(s) neste PC, em:\n{reg.PASTA_LOGS}\n"
                                 f"Não foram enviados: {erro}.", False)

    # ------------------------------------------------------------ botões
    def procurar_atualizacao(self):
        return self._em_segundo_plano(self._verificar_versao)

    def instalar_dependencias(self):
        return self._em_segundo_plano(self._verificar_dependencias)

    def conferir_blender(self):
        return self._em_segundo_plano(self._verificar_blender)

    def enviar_logs(self):
        return self._em_segundo_plano(self._enviar_logs)

    def abrir_pasta_logs(self):
        try:
            self._abrir_pasta(reg.PASTA_LOGS)
            return {"ok": True}
        except OSError as e:
            self._mostrar(f"Não deu para abrir a pasta de logs: {e}")
            return {"ok": False}

    def pode_atualizar(self):
        """O JS pergunta antes de abrir a confirmação (só com atualização disponível)."""
        info = self._info_atualizacao
        return {"ok": bool(info and info.get("status") == "disponivel")}

    def atualizar(self):
        """Chamado depois que o usuário confirmou no modal da tela."""
        info = self._info_atualizacao
        if not info or info.get("status") != "disponivel":
            return {"ok": False}

        def tarefa():
            self._status("atualizacao", "Atualizando...")
            ok, msg = self._f["atualizar"](info)
            self._mostrar(msg)
            if not ok:
                caminho = reg.gravar_log(ORIGEM, "atualização falhou", msg)
                self._status("atualizacao", "A atualização falhou. Veja os detalhes abaixo.", False)
                if caminho:
                    self._mostrar(f"Detalhes em {caminho}")
                return
            self._verificar_versao()
            self._verificar_dependencias()
            self._mostrar("Pronto. Feche e abra o launcher de novo para usar a versão nova dele.")

        return self._em_segundo_plano(tarefa)

    def abrir_app(self):
        """Abre o app; se ele abrir, o launcher se fecha sozinho. Se não, fica aberto com o erro."""
        if self._abrindo:
            return {"ok": False}
        self._abrindo = True
        self._botao("abrir", False, TEXTO_ABRINDO)
        self._mostrar("Abrindo o app...")

        def tarefa():
            try:
                ok, msg = self._f["abrir_app"]()
            except Exception as e:
                ok, msg = False, f"Erro inesperado ao abrir o app: {e}\n\n{traceback.format_exc()}"
            self._resultado_abrir(ok, msg)

        t = threading.Thread(target=tarefa, name="abrir-app", daemon=True)
        self._threads.append(t)
        t.start()
        return {"ok": True}

    def _resultado_abrir(self, ok, msg):
        self._abrindo = False
        if ok:
            self._mostrar(msg + " Fechando o launcher...")
            self._fechar_quando_livre()
            return
        self._botao("abrir", True, TEXTO_ABRIR)
        caminho = reg.gravar_log(ORIGEM, "o app não abriu", msg)
        detalhe = f"\n\nDetalhes em {caminho}" if caminho else ""
        self._mostrar("O app não abriu:\n" + msg + detalhe)
        self._enviar({"tipo": "erro", "titulo": "O app não abriu",
                      "mensagem": "Não deu para abrir o app:\n\n" + msg[-1500:] + detalhe})

    def _fechar_quando_livre(self, intervalo=0.5):
        """Fecha o launcher; se ainda houver uma tarefa rodando (pip, atualização), espera ela acabar."""
        if self._ocupado:
            self._mostrar("O launcher fecha quando terminar a tarefa em andamento.")
            while self._ocupado:
                threading.Event().wait(intervalo)
        self._fechar_pedido = True
        self._enviar({"tipo": "fechar"})

    # ------------------------------------------------------------ erros do JavaScript
    def registrar_erro(self, resumo, detalhes=""):
        caminho = reg.gravar_log(f"{ORIGEM} (interface web)", str(resumo)[:500], str(detalhes)[:20000])
        return {"ok": bool(caminho)}


class InterfaceIndisponivel(RuntimeError):
    """A janela web não pode ser usada: o launcher.py abre a janela Tkinter."""


def iniciar(api=None, webview=None):
    """Abre a janela do launcher (bloqueia até ela fechar). Levanta exceção se o pywebview ou o
    WebView2 não funcionarem, para o launcher.py abrir a janela Tkinter."""
    if webview is None:
        import webview
    if not os.path.isfile(PAGINA):
        raise InterfaceIndisponivel(f"não achei a tela do launcher ({os.path.relpath(PAGINA, reg.PASTA_PROJETO)})")
    api = api or ApiLauncher()
    janela = webview.create_window(f"{tema_janela.NOME_APP} - Launcher", url=PAGINA, js_api=api,
                                   width=620, height=680, min_size=(560, 600),
                                   background_color=tema_janela.TEMA["fundo"])
    api._ligar_janela(janela)
    problema = []

    def ao_mostrar():
        renderizador = str(getattr(webview, "renderer", "") or "")
        if tema_janela.eh_windows() and renderizador and renderizador != "edgechromium":
            problema.append(f"o pywebview abriu com o motor '{renderizador}' (sem o WebView2)")
            janela.destroy()
            return
        tema_janela.preparar_hwnd(tema_janela.hwnd_pywebview(janela), "launcher")

    janela.events.shown += ao_mostrar
    opcoes = {"gui": "edgechromium"} if tema_janela.eh_windows() else {}
    webview.start(**opcoes)
    if problema:
        raise InterfaceIndisponivel(problema[0])
    return api
