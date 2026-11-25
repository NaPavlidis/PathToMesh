"""Interface web do PathToMesh (pywebview + WebView2), fiel ao docs/modelo-layout.html.

- A tela fica em ui_web/ (index.html, estilo.css, app.js), sem nada da internet (funciona offline).
- O JavaScript chama os métodos da classe Api (js_api do pywebview); a lógica é a do nucleo.py,
  a mesma da interface Tkinter (app_ui.py), que continua como reserva.
- O Blender roda numa thread; as etapas e o progresso chegam ao JavaScript por evaluate_js, por
  uma fila com thread própria (a leitura da saída do Blender nunca espera a tela).
- Diálogos de arquivo e pasta: os nativos do Windows (window.create_file_dialog).
- Ícone principal (PathToMash-icon.ico) e barra de título nas cores do tema pelo HWND da janela (tema_janela.preparar_hwnd).

O pywebview só é importado dentro de iniciar() e dos diálogos: a Api pode ser usada (e testada)
direto do Python, sem janela.
"""
import json
import os
import queue
import threading
import traceback

import nucleo
import registro_erros
import tema_janela

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_WEB = os.path.join(PASTA, "ui_web")
INDEX = os.path.join(PASTA_WEB, "index.html")
ORIGEM = "app"

TIPOS_SVG = ("Arquivos SVG (*.svg)", "Todos (*.*)")
TIPOS_BLENDER = ("Executável do Blender (*.exe)", "Todos (*.*)")


# Logo <numero> como data URI (o mesmo do launcher web; lido do disco uma vez só)
logo_data_uri = tema_janela.logo_data_uri


def _info_para_js(info):
    """Resultado de nucleo.extrair_informacoes_svg em dados simples (JSON) para o painel de análise."""
    if not info:
        return None
    return {
        "nome_arquivo": info["nome_arquivo"],
        "materiais": [{"tipo": tipo, "nome": nome, "qtd": qtd} for (tipo, nome), qtd in info["materiais_qtd"].items()],
        "nome_fundo": info["nome_fundo"],
        "largura_mm": f"{info['largura_mm']:.2f}",
        "altura_mm": f"{info['altura_mm']:.2f}",
        "largura_cm": f"{info['largura_cm']:.2f}",
        "altura_cm": f"{info['altura_cm']:.2f}",
        "descartadas": len(info["pecas_descartadas"]),
    }


def evento_para_js(evento):
    """Evento do nucleo.executar_blender no formato que o app.js mostra (os mesmos textos do Tk)."""
    tipo = evento[0]
    if tipo == "status":
        return {"tipo": "status", "status": evento[1]}
    if tipo == "passo":
        return {"tipo": "passo", "concluido": evento[1], "status": evento[2]}
    if tipo == "amostras":
        atual, total, faltam, porcentagem, nome_cam = evento[1:]
        status, linha = nucleo.textos_amostras(atual, total, faltam, nome_cam)
        return {"tipo": "amostras", "status": status, "samples": linha, "porcentagem": porcentagem}
    if tipo == "progresso":
        # progresso real (nucleo.ProgressoRender): barra composta, etapas, etapa atual e tempos
        dados = dict(evento[1])
        dados["tipo"] = "progresso"
        dados["tempos"] = nucleo.texto_tempos(dados)
        return dados
    if tipo == "concluido":
        if len(evento) > 1 and evento[1] is False:
            # o Blender terminou com erro: a tela segue como antes, mas a barra não vai a 100%
            return {"tipo": "concluido", "status": nucleo.STATUS_CONCLUIDO, "samples": nucleo.SAMPLES_COM_ERRO,
                    "porcentagem": None, "sucesso": False}
        return {"tipo": "concluido", "status": nucleo.STATUS_CONCLUIDO, "samples": nucleo.SAMPLES_CONCLUIDO,
                "porcentagem": 100}
    if tipo == "erro":
        return {"tipo": "erro", "titulo": "Erro Crítico", "mensagem": evento[1]}
    return {"tipo": tipo}


class Api:
    """Métodos chamados pelo JavaScript (window.pywebview.api.<método>). Todos devolvem dados
    simples (dict, list, str). Os atributos com _ não são expostos ao JavaScript."""

    def __init__(self, dialogo=None, executar=None):
        self._janela = None
        self._webview = None
        self._dialogo = dialogo            # testes: função (tipo, tipos_de_arquivo) -> caminho
        self._executar = executar or nucleo.executar_blender
        self._estado = nucleo.EstadoApp()
        self._estado.definir_padroes()
        self._resina = "Nenhum"
        self._fila = queue.Queue()
        self._eventos = []                 # sem janela (testes), os eventos ficam aqui
        self._threads = []
        threading.Thread(target=self._enviar_fila, name="eventos-js", daemon=True).start()

    # ------------------------------------------------------------ janela e eventos
    def _ligar_janela(self, janela, webview=None):
        self._janela = janela
        self._webview = webview            # o módulo pywebview usado pela janela (nos diálogos)

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
            try:
                janela.evaluate_js("window.ptm && window.ptm.evento(%s)" % json.dumps(dados, ensure_ascii=False))
            except Exception as e:
                registro_erros.gravar_log(f"{ORIGEM} (interface web)", f"Não deu para atualizar a tela: {e}",
                                          traceback.format_exc())

    def _esperar_eventos(self, timeout=10):
        """Testes: espera o Blender e a fila terminarem."""
        for t in list(self._threads):
            t.join(timeout)
        fim = threading.Event()
        self._fila.put({"tipo": "_fim"})
        while not fim.is_set():
            if self._eventos and self._eventos[-1].get("tipo") == "_fim":
                self._eventos.pop()
                fim.set()
            else:
                threading.Event().wait(0.01)
        return list(self._eventos)

    def _abrir_dialogo(self, pasta=False, tipos=()):
        if self._dialogo is not None:
            resposta = self._dialogo("pasta" if pasta else "arquivo", tipos)
        else:
            webview = self._webview
            if webview is None:
                import webview
            dialogos = getattr(webview, "FileDialog", None)
            if pasta:
                tipo = getattr(dialogos, "FOLDER", None) if dialogos else None
                tipo = tipo if tipo is not None else webview.FOLDER_DIALOG
                resposta = self._janela.create_file_dialog(tipo)
            else:
                tipo = getattr(dialogos, "OPEN", None) if dialogos else None
                tipo = tipo if tipo is not None else webview.OPEN_DIALOG
                resposta = self._janela.create_file_dialog(tipo, file_types=tipos)
        if isinstance(resposta, (list, tuple)):
            resposta = resposta[0] if resposta else ""
        return resposta or ""

    # ------------------------------------------------------------ começo
    def estado_inicial(self):
        return {
            "nome_app": tema_janela.NOME_APP,
            "logos": {"normal": logo_data_uri(tema_janela.LOGOS["normal"]),
                      "largo": logo_data_uri(tema_janela.LOGOS["largo"])},
            "limite_logo": tema_janela.LARGURA_LOGO_LARGO,
            "aguardando": nucleo.TEXTO_AGUARDANDO_SVG,
            "status_inicial": nucleo.STATUS_INICIAL,
            "samples_inicial": nucleo.SAMPLES_INICIAL,
            "resina": self.listar_resinas(),
        }

    # ------------------------------------------------------------ Upload
    def selecionar_svg(self):
        caminho = self._abrir_dialogo(tipos=TIPOS_SVG)
        if not caminho:
            return {"ok": False}
        self._estado.svg_selecionado = caminho
        self._estado.output_path = nucleo.preparar_pasta_saida(caminho)
        resultado = self.analisar_svg(caminho)
        resultado.update(ok=True, nome=os.path.basename(caminho))
        return resultado

    def analisar_svg(self, caminho):
        info = nucleo.extrair_informacoes_svg(caminho)
        aviso = None
        if info and info["pecas_descartadas"]:
            aviso = {"titulo": nucleo.TITULO_AVISO_DESCARTADAS,
                     "mensagem": nucleo.montar_aviso_descartadas(info["pecas_descartadas"])}
        return {"texto": nucleo.montar_resumo_svg(info), "dados": _info_para_js(info), "aviso": aviso}

    def listar_resinas(self, atual=None):
        if atual is not None:
            self._resina = atual
        opcoes, escolhido = nucleo.opcoes_resina(nucleo.listar_modelos_resina(self._estado.resina_dir), self._resina)
        self._resina = escolhido
        return {"opcoes": [{"valor": v, "rotulo": r} for v, r in opcoes], "selecionado": escolhido}

    def avancar(self, opcoes):
        """Botão 'Avançar para Processing'. opcoes: render_auto, cam_principal, cam_esquerda,
        cam_direita, usar_textura, usar_verniz (bool) e resina (valor do campo)."""
        opcoes = opcoes or {}
        render_auto = bool(opcoes.get("render_auto"))
        cams = (bool(opcoes.get("cam_principal")), bool(opcoes.get("cam_esquerda")), bool(opcoes.get("cam_direita")))
        aviso = nucleo.validar_avanco(self._estado.svg_selecionado, render_auto, *cams)
        if aviso:
            return {"ok": False, "aviso": {"titulo": "Atenção", "mensagem": aviso}}
        self._resina = opcoes.get("resina", self._resina)
        comando = nucleo.montar_comando_blender(self._estado, self._resina, render_auto,
                                                bool(opcoes.get("usar_textura")), bool(opcoes.get("usar_verniz")),
                                                nucleo.cameras_selecionadas_str(*cams))
        thread = threading.Thread(target=self._executar, name="blender", daemon=True,
                                  args=(comando, lambda ev: self._enviar(evento_para_js(ev))),
                                  kwargs={"origem": f"{ORIGEM} (Blender)"})
        self._threads.append(thread)
        thread.start()
        return {"ok": True, "status": nucleo.STATUS_INICIAL, "samples": nucleo.SAMPLES_INICIAL}

    # ------------------------------------------------------------ Download e Catálogo
    def abrir_pasta_saida(self):
        return {"ok": nucleo.abrir_pasta_saida(self._estado.output_path)}

    def relatorio_catalogo(self):
        modalidades, status = nucleo.mapear_catalogo(self._estado.catalogo_dir)
        return {"texto": nucleo.montar_relatorio_catalogo(modalidades, status, self._estado.catalogo_dir)}

    # ------------------------------------------------------------ Configurações
    def configuracoes(self):
        e = self._estado
        return {"blender_path": e.blender_path, "catalogo_dir": e.catalogo_dir, "resina_dir": e.resina_dir,
                "blend_dir": e.blend_dir, "cycles_samples": str(e.cycles_samples),
                "blends": self.listar_blends(e.blend_dir, e.selected_blend)}

    def listar_blends(self, pasta, atual=""):
        arquivos = nucleo.listar_blends(pasta)
        return {"opcoes": arquivos or [nucleo.SEM_BLEND], "selecionado": nucleo.escolher_blend(arquivos, atual)}

    def buscar_blender(self):
        return self._abrir_dialogo(tipos=TIPOS_BLENDER)

    def buscar_pasta(self):
        return self._abrir_dialogo(pasta=True)

    def salvar_configuracoes(self, dados):
        dados = dados or {}
        e = self._estado
        e.blender_path = dados.get("blender_path", e.blender_path)
        e.resina_dir = dados.get("resina_dir", e.resina_dir)
        e.blend_dir = dados.get("blend_dir", e.blend_dir)
        e.catalogo_dir = dados.get("catalogo_dir", e.catalogo_dir)
        e.selected_blend = dados.get("selected_blend", e.selected_blend)
        e.cycles_samples = nucleo.ler_samples(str(dados.get("cycles_samples", "")))
        e.salvar_configuracoes_disco()
        return {"ok": True, "titulo": "Sucesso", "mensagem": "Configurações salvas permanentemente!",
                "resina": self.listar_resinas()}

    # ------------------------------------------------------------ erros do JavaScript
    def registrar_erro(self, resumo, detalhes=""):
        """Erro de JavaScript na tela: vira log de erro (como os do Python)."""
        caminho = registro_erros.gravar_log(f"{ORIGEM} (interface web)", str(resumo)[:500], str(detalhes)[:20000])
        return {"ok": bool(caminho)}


# ---------------------------------------------------------------- janela
# HWND da janela do pywebview no Windows (Form do WinForms), ou 0
_hwnd_da_janela = tema_janela.hwnd_pywebview


class InterfaceIndisponivel(RuntimeError):
    """A janela web não pode ser usada (sem WebView2): o app.py abre a interface Tkinter."""


def iniciar(api=None, webview=None):
    """Abre a janela (bloqueia até ela ser fechada). Levanta exceção se o pywebview ou o
    WebView2 não funcionarem, para o app.py cair na interface Tkinter."""
    if webview is None:
        import webview
    if not os.path.isfile(INDEX):
        raise InterfaceIndisponivel(f"não achei a interface web ({os.path.relpath(INDEX, PASTA)})")
    api = api or Api()
    janela = webview.create_window(tema_janela.NOME_APP, url=INDEX, js_api=api, width=1150, height=820,
                                   min_size=(980, 700), background_color=tema_janela.TEMA["fundo"])
    api._ligar_janela(janela, webview)
    problema = []

    def ao_mostrar():
        renderizador = str(getattr(webview, "renderer", "") or "")
        if tema_janela.eh_windows() and renderizador and renderizador != "edgechromium":
            # Sem o WebView2 o pywebview usaria o motor antigo do Internet Explorer, que não roda a tela
            problema.append(f"o pywebview abriu com o motor '{renderizador}' (sem o WebView2)")
            janela.destroy()
            return
        tema_janela.preparar_hwnd(_hwnd_da_janela(janela), "app")

    janela.events.shown += ao_mostrar
    opcoes = {"gui": "edgechromium"} if tema_janela.eh_windows() else {}
    webview.start(**opcoes)
    if problema:
        raise InterfaceIndisponivel(problema[0])
