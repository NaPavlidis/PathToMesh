"""Visual compartilhado do PathToMesh (usado pelo app_ui.py e pelo launcher.py).

- TEMA: a paleta, tirada do modelo de layout (docs/modelo-layout.html, tema escuro).
- familias_fontes(): escolhe as fontes do modelo, se estiverem instaladas, ou as do sistema.
- aplicar_icone(): ícone da janela (.ico com iconbitmap; se faltar, o .png com iconphoto).
- criar_logo_cabecalho(): logo do canto esquerdo do cabeçalho (1, ou 2 com a janela larga).
- pintar_barra_titulo(): pinta a barra de título nativa do Windows (DWM) com as cores do TEMA.
- preparar_janela(): as duas coisas de uma vez.
- logo_data_uri() e hwnd_pywebview(): o logo e o HWND das janelas web (app e launcher).
- fundo_translucido_pywebview(): fundo Acrylic do Windows 11 na janela web do app (com volta
  para a cor sólida se não der).

Nada aqui importa o tkinter no topo do arquivo (os testes do launcher rodam sem ele), e tudo o
que mexe no sistema fica dentro de try/except: se não der, a janela só fica com o visual padrão.
"""
import os
import sys

NOME_APP = "PathToMesh"
PASTA_ICONES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icones")

# Função de cada imagem de assets/icones (veja assets/icones/README.md)
# PathToMash-icon = ícone principal: todas as janelas (app, launcher, configurações, mensagens),
# os atalhos e o instalador (o instalar.ps1 usa o PathToMash-icon.ico). O PathToMash-icon.png é o
# mesmo desenho (256 px, tirado do .ico), reserva para o iconphoto quando o .ico não pode ser lido.
ICONE_PRINCIPAL = "PathToMash-icon"
ICONES = {
    "app": ICONE_PRINCIPAL,
    "launcher": ICONE_PRINCIPAL,
    "atalho": ICONE_PRINCIPAL,
}
# Logo do canto esquerdo do cabeçalho (no lugar do nome digitado): o 1; com a janela larga, o 2.
LOGOS = {"normal": "1", "largo": "2"}
LARGURA_LOGO_LARGO = 1200   # px: a partir desta largura da janela, o cabeçalho usa o logo 2
# Altura do logo no cabeçalho (a barra tem 56 px). As versões já reduzidas ficam em
# assets/icones/<n>_cabecalho.png; se faltarem, o <n>.png grande é reduzido com subsample.
ALTURA_LOGO = {"1": 46, "2": 34}

# ------------------------------------------------------------------------------ paleta
# Nome no TEMA: valor do modelo  (token do modelo-layout.html)
TEMA = {
    'fundo':          '#101418',  # dark-surface: fundo da janela e das telas
    'barra':          '#101418',  # dark-surface (= fundo): faixa do logo e barra de título, sem barra separada
    'superficie':     '#181C20',  # dark-surface-container-low: cartões, menu lateral, configurações
    'campo':          '#0A0F13',  # dark-surface-container-lowest: campos, áreas de texto, trilho da barra
    'container':      '#1C2024',  # dark-surface-container: grupo de câmeras, botões de ícone, menus
    'elevado':        '#262A2F',  # dark-surface-container-high: botões secundários, item ativo
    'elevado_hover':  '#31353A',  # dark-surface-container-highest: hover dos botões secundários
    'borda':          '#89929B',  # dark-outline: borda dos cartões, campos e botões
    'divisor':        '#3F4850',  # dark-outline-variant: divisórias e bordas sutis
    'destaque':       '#93CCFF',  # dark-primary: ação principal, item ativo, progresso, títulos em destaque
    'sobre_destaque': '#003351',  # dark-on-primary: texto sobre o destaque
    'marca':          '#3198DC',  # dark-primary-container: caixa do logo e hover da ação principal
    'sobre_marca':    '#001524',  # dark-on-primary-container: texto sobre a marca
    'secundario':     '#2D4C66',  # dark-secondary-container: caixa do ícone do arquivo
    'sobre_secundario': '#9DBCDA',  # dark-on-secondary-container
    'sucesso':        '#34D399',  # success: concluído, nome do arquivo, títulos dos relatórios
    'sobre_sucesso':  '#00291B',  # on-success: texto sobre o verde
    'sucesso_fundo':  '#064E3B',  # success-container: hover do botão verde
    'sucesso_claro':  '#A7F3D0',  # on-success-container
    'aviso':          '#FBBF24',  # warning: peças que não serão convertidas, avisos do launcher
    'aviso_fundo':    '#452700',  # warning-container
    'erro':           '#FFB4AB',  # dark-error
    'texto':          '#DFE3E8',  # dark-on-surface: texto principal
    'texto_suave':    '#BFC7D2',  # dark-on-surface-variant: rótulos e texto secundário
    'texto_apagado':  '#89929B',  # dark-outline: dicas, legendas, rodapé e itens inativos
}

# Grade do modelo (px): xs 4, sm 8, md 12, lg 16, xl 24, 2xl 32, 3xl 48
ESPACO = {'xs': 4, 'p': 8, 'pm': 12, 'm': 16, 'g': 24, 'gg': 32, 'ggg': 48}

# Fontes do modelo e as do sistema, na ordem de preferência
_TITULOS = ("Red Hat Text", "Segoe UI Semibold", "Segoe UI", "Helvetica")
_CORPO = ("Instrument Sans", "Segoe UI", "Helvetica")
_MONO = ("Red Hat Mono", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier")


def _padrao(lista_windows, lista_outros):
    return lista_windows if sys.platform.startswith("win") else lista_outros


def familias_fontes(janela=None):
    """(títulos, corpo, mono). Com uma janela aberta, usa as fontes do modelo que estiverem
    instaladas; sem janela (ou se der erro), Segoe UI/Consolas no Windows e Helvetica/Courier fora."""
    padrao = (_padrao("Segoe UI", "Helvetica"), _padrao("Segoe UI", "Helvetica"), _padrao("Consolas", "Courier"))
    if janela is None:
        return padrao
    try:
        from tkinter import font as tkfont
        instaladas = {f.lower() for f in tkfont.families(janela)}
    except Exception:
        return padrao
    escolhidas = []
    for lista, reserva in zip((_TITULOS, _CORPO, _MONO), padrao):
        escolhidas.append(next((f for f in lista if f.lower() in instaladas), reserva))
    return tuple(escolhidas)


# ------------------------------------------------------------------------------ cores
def hex_para_colorref(cor):
    """'#RRGGBB' (ou '#RGB') para o COLORREF do Windows, 0x00BBGGRR. ValueError se não for uma cor."""
    if not isinstance(cor, str):
        raise ValueError(f"cor inválida: {cor!r}")
    texto = cor.strip().lstrip("#")
    if len(texto) == 3:
        texto = "".join(c * 2 for c in texto)
    if len(texto) != 6 or any(c not in "0123456789abcdefABCDEF" for c in texto):
        raise ValueError(f"cor inválida: {cor!r}")
    r, g, b = int(texto[0:2], 16), int(texto[2:4], 16), int(texto[4:6], 16)
    return (b << 16) | (g << 8) | r


# Atributos do DwmSetWindowAttribute
DWMWA_USE_IMMERSIVE_DARK_MODE = 20          # Windows 10 20H1 em diante e Windows 11
DWMWA_USE_IMMERSIVE_DARK_MODE_ANTIGO = 19   # Windows 10 antes do 20H1
DWMWA_BORDER_COLOR = 34                     # 34, 35 e 36: Windows 11
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def eh_windows():
    return sys.platform == "win32"


def _hwnd(janela):
    """HWND da moldura da janela (o pai do widget raiz do Tk)."""
    import ctypes
    janela.update_idletasks()
    interno = janela.winfo_id()
    externo = ctypes.windll.user32.GetParent(interno)
    return externo or interno


def pintar_barra_titulo(janela, fundo=None, texto=None, borda=None, escuro=True):
    """Pinta a barra de título nativa do Windows com as cores dadas (padrão: as do TEMA).

    Modo escuro (atributo 20, ou 19 nos Windows 10 antigos), cor da barra (35), do texto (36) e
    da borda (34). As cores só funcionam no Windows 11; no 10 fica só o modo escuro. Fora do
    Windows, ou se der qualquer erro, não faz nada. Devolve a lista dos atributos aplicados.
    """
    if not eh_windows():
        return []
    try:
        hwnd = _hwnd(janela)
    except Exception:
        return []
    return pintar_barra_titulo_hwnd(hwnd, fundo, texto, borda, escuro)


def pintar_barra_titulo_hwnd(hwnd, fundo=None, texto=None, borda=None, escuro=True):
    """O mesmo que pintar_barra_titulo, a partir do HWND da janela (usado também pela janela do
    pywebview, que não é do Tk). Fora do Windows, sem HWND ou com erro, não faz nada."""
    if not eh_windows() or not hwnd:
        return []
    # barra de título com a cor do fundo da página (continuidade com o cabeçalho) e a borda da
    # janela também da cor do fundo (sem contorno colorido)
    fundo = TEMA['barra'] if fundo is None else fundo
    texto = TEMA['texto'] if texto is None else texto
    borda = TEMA['fundo'] if borda is None else borda
    aplicados = []
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.windll.dwmapi

        def definir(atributo, valor):
            dado = ctypes.c_uint32(valor)
            try:
                return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_uint32(atributo),
                                                 ctypes.byref(dado), ctypes.sizeof(dado)) == 0
            except Exception:
                return False

        if escuro:
            if definir(DWMWA_USE_IMMERSIVE_DARK_MODE, 1):
                aplicados.append(DWMWA_USE_IMMERSIVE_DARK_MODE)
            elif definir(DWMWA_USE_IMMERSIVE_DARK_MODE_ANTIGO, 1):
                aplicados.append(DWMWA_USE_IMMERSIVE_DARK_MODE_ANTIGO)
        for atributo, cor in ((DWMWA_CAPTION_COLOR, fundo), (DWMWA_TEXT_COLOR, texto), (DWMWA_BORDER_COLOR, borda)):
            if cor and definir(atributo, hex_para_colorref(cor)):
                aplicados.append(atributo)
    except Exception:
        return aplicados
    return aplicados


# ------------------------------------------------------------------------------ ícones
def caminhos_icone(nome):
    """(caminho do .ico, caminho do .png) do ícone 'app', 'launcher' ou 'atalho'."""
    base = os.path.join(PASTA_ICONES, ICONES.get(nome, nome))
    return base + ".ico", base + ".png"


def aplicar_icone(janela, nome="app", padrao=False):
    """Põe o ícone na janela: o .ico com iconbitmap; se ele não existir ou não puder ser lido
    (fora do Windows o Tk não lê .ico), o .png com iconphoto. Com padrao=True, vale também para as
    janelas abertas depois (Toplevel). Devolve 'ico', 'png' ou '' (sem ícone)."""
    ico, png = caminhos_icone(nome)
    if os.path.isfile(ico):
        try:
            if padrao:
                janela.iconbitmap(default=ico)
            else:
                janela.iconbitmap(ico)
            return "ico"
        except Exception:
            pass
    if os.path.isfile(png):
        try:
            import tkinter
            imagem = tkinter.PhotoImage(master=janela, file=png)
            fator = -(-imagem.width() // 256)       # os .png são grandes: reduz para até 256 px
            if fator > 1:
                imagem = imagem.subsample(fator, fator)
            janela.iconphoto(padrao, imagem)
            janela._icone_pathtomesh = imagem       # guarda a referência (senão o Tk apaga a imagem)
            return "png"
        except Exception:
            pass
    return ""


WM_SETICON = 0x0080
ICON_SMALL, ICON_BIG = 0, 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010


def aplicar_icone_hwnd(hwnd, nome="app"):
    """Põe o .ico na janela pelo HWND (WM_SETICON, ícone pequeno e grande), para janelas que não
    são do Tk (a do pywebview). Só no Windows; nunca levanta erro. Devolve True se aplicou."""
    if not eh_windows() or not hwnd:
        return False
    ico, _ = caminhos_icone(nome)
    if not os.path.isfile(ico):
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        aplicou = False
        for tipo, tamanho in ((ICON_SMALL, 16), (ICON_BIG, 32)):
            icone = user32.LoadImageW(None, ico, IMAGE_ICON, tamanho, tamanho, LR_LOADFROMFILE)
            if icone:
                user32.SendMessageW(ctypes.c_void_p(hwnd), WM_SETICON, ctypes.c_void_p(tipo), ctypes.c_void_p(icone))
                aplicou = True
        return aplicou
    except Exception:
        return False


def preparar_hwnd(hwnd, icone="app"):
    """Ícone + barra de título nas cores do TEMA, pelo HWND (janela do pywebview). Nunca levanta erro."""
    resultado = {"icone": False, "barra": []}
    try:
        resultado["icone"] = aplicar_icone_hwnd(hwnd, icone)
    except Exception:
        pass
    try:
        resultado["barra"] = pintar_barra_titulo_hwnd(hwnd)
    except Exception:
        pass
    return resultado


# ------------------------------------------------------------------------------ fundo translúcido (Windows 11)
# Fundo da janela do app com o efeito do sistema (Acrylic: o que está atrás da janela, desfocado
# e escurecido), visto através do fundo da página com alfa alto (0.85 no tema.css, classe
# "translucido"): a cor continua quase a mesma e a legibilidade não muda (os cartões são opacos).
# Como é feito: DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE=38, Acrylic=3) e
# DwmExtendFrameIntoClientArea(-1) no HWND; no WinForms do pywebview, o Form com fundo preto (o DWM
# troca o preto da área estendida pelo efeito) e o WebView2 com DefaultBackgroundColor transparente.
# NÃO usa o transparent=True do pywebview: no Windows ele faz a janela recortada por cor
# (TransparencyKey), sem desfoque e com cliques passando para trás.
# Só no Windows 11 22H2 (build 22621) ou mais novo e com "Efeitos de transparência" ligado; senão,
# ou se qualquer passo falhar, tudo volta como estava (a cor sólida de sempre). Para desligar à
# mão: variável de ambiente PTM_SEM_TRANSPARENCIA=1.
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMSBT_NENHUM = 1
DWMSBT_MICA = 2
DWMSBT_ACRILICO = 3
FUNDO_SISTEMA = DWMSBT_ACRILICO
BUILD_MINIMO_FUNDO = 22621


def build_windows():
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        return 0


def transparencia_ligada():
    """'Efeitos de transparência' do Windows (Personalização > Cores). Sem conseguir ler: True."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as chave:
            valor, _ = winreg.QueryValueEx(chave, "EnableTransparency")
        return bool(valor)
    except Exception:
        return True


class _DwmReal:
    """As duas chamadas do DWM usadas no fundo translúcido (ctypes)."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._c, self._w, self._dwm = ctypes, wintypes, ctypes.windll.dwmapi

        class MARGINS(ctypes.Structure):
            _fields_ = [("esquerda", ctypes.c_int), ("direita", ctypes.c_int), ("cima", ctypes.c_int), ("baixo", ctypes.c_int)]
        self._margens = MARGINS

    def estender(self, hwnd, margem):
        m = self._margens(margem, margem, margem, margem)
        return self._dwm.DwmExtendFrameIntoClientArea(self._w.HWND(hwnd), self._c.byref(m)) == 0

    def atributo(self, hwnd, atributo, valor):
        dado = self._c.c_uint32(valor)
        return self._dwm.DwmSetWindowAttribute(self._w.HWND(hwnd), self._c.c_uint32(atributo),
                                               self._c.byref(dado), self._c.sizeof(dado)) == 0


def _dotnet_cores():
    """(Action, Color) do .NET (pythonnet, já carregado pelo pywebview), ou None."""
    try:
        import clr  # noqa: F401
        from System import Action
        from System.Drawing import Color
        return Action, Color
    except Exception:
        return None


def _achar_webview2(controle, nivel=0):
    """O controle WebView2 dentro do Form (procura nos filhos, até 4 níveis)."""
    try:
        filhos = list(controle.Controls)
    except Exception:
        return None
    for filho in filhos:
        try:
            if filho.GetType().Name == "WebView2":
                return filho
        except Exception:
            continue
    if nivel < 4:
        for filho in filhos:
            achado = _achar_webview2(filho, nivel + 1)
            if achado is not None:
                return achado
    return None


def fundo_translucido_pywebview(janela, hwnd=None, dwm=None, dotnet=None, build=None, transparencia=None,
                                ambiente=None, windows=None):
    """Liga o fundo translúcido (Acrylic) na janela do pywebview. Devolve {'ok': bool, 'motivo': str}.
    Com ok=False nada mudou (ou foi desfeito): a página fica com a cor sólida."""
    ambiente = os.environ if ambiente is None else ambiente
    if ambiente.get("PTM_SEM_TRANSPARENCIA"):
        return {"ok": False, "motivo": "desligado pela variável PTM_SEM_TRANSPARENCIA"}
    if not (eh_windows() if windows is None else windows):
        return {"ok": False, "motivo": "só no Windows"}
    build = build_windows() if build is None else build
    if build < BUILD_MINIMO_FUNDO:
        return {"ok": False, "motivo": f"precisa do Windows 11 22H2 ou mais novo (build {build})"}
    if not (transparencia_ligada() if transparencia is None else transparencia):
        return {"ok": False, "motivo": "'Efeitos de transparência' desligado no Windows"}
    form = getattr(janela, "native", None)
    webview2 = _achar_webview2(form) if form is not None else None
    net = dotnet or _dotnet_cores()
    if form is None or webview2 is None or net is None:
        return {"ok": False, "motivo": "janela sem WinForms/WebView2 acessível"}
    Action, Color = net
    hwnd = hwnd if hwnd is not None else hwnd_pywebview(janela)
    if not hwnd:
        return {"ok": False, "motivo": "sem o HWND da janela"}
    try:
        dwm = dwm or _DwmReal()
        if not dwm.atributo(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, FUNDO_SISTEMA):
            return {"ok": False, "motivo": "o Windows recusou o efeito de fundo"}
        if not dwm.estender(hwnd, -1):
            dwm.atributo(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_NENHUM)
            return {"ok": False, "motivo": "o Windows recusou estender o fundo"}
    except Exception as e:
        return {"ok": False, "motivo": f"DWM: {e}"}

    erro = []
    antes = {}

    def no_form():
        try:
            antes["form"] = form.BackColor
            antes["web"] = webview2.DefaultBackgroundColor
            form.BackColor = Color.Black                          # o DWM mostra o efeito no preto
            webview2.DefaultBackgroundColor = Color.Transparent   # a página deixa ver o fundo
        except Exception as e:
            erro.append(e)
            try:                                                  # desfaz o que deu
                if "form" in antes:
                    form.BackColor = antes["form"]
                if "web" in antes:
                    webview2.DefaultBackgroundColor = antes["web"]
            except Exception:
                pass

    try:
        form.Invoke(Action(no_form))                              # na thread da janela
    except Exception as e:
        erro.append(e)
    if erro:
        try:
            dwm.estender(hwnd, 0)
            dwm.atributo(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_NENHUM)
        except Exception:
            pass
        return {"ok": False, "motivo": f"WebView2: {erro[0]}"}
    return {"ok": True, "motivo": "Acrylic"}


# ------------------------------------------------------------------------------ janelas do pywebview
_CACHE_LOGOS = {}


def logo_data_uri(numero):
    """Logo <numero> (assets/icones) como data URI, para o <img> do cabeçalho das telas web. O
    .png grande fica nítido em telas com zoom; se faltar, o <numero>_cabecalho.png. '' se nenhum
    existir. Lido do disco uma vez só (fica guardado)."""
    if numero in _CACHE_LOGOS:
        return _CACHE_LOGOS[numero]
    import base64
    uri = ""
    for nome in (f"{numero}.png", f"{numero}_cabecalho.png"):
        try:
            with open(os.path.join(PASTA_ICONES, nome), "rb") as f:
                uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
            break
        except OSError:
            continue
    if uri:
        _CACHE_LOGOS[numero] = uri
    return uri


def hwnd_pywebview(janela):
    """HWND da janela do pywebview no Windows (Form do WinForms), ou 0."""
    try:
        return int(janela.native.Handle.ToInt64())
    except Exception:
        pass
    try:
        import ctypes
        return ctypes.windll.user32.FindWindowW(None, janela.title) or 0
    except Exception:
        return 0


# ------------------------------------------------------------------------------ logo do cabeçalho
def carregar_logo(janela, numero):
    """PhotoImage do logo <numero> no tamanho do cabeçalho, ou None se não der.
    Usa o <numero>_cabecalho.png (já reduzido); se faltar, reduz o <numero>.png com subsample."""
    import tkinter
    altura = ALTURA_LOGO.get(numero, 40)
    pronto = os.path.join(PASTA_ICONES, f"{numero}_cabecalho.png")
    grande = os.path.join(PASTA_ICONES, f"{numero}.png")
    for caminho in (pronto, grande):
        if not os.path.isfile(caminho):
            continue
        try:
            imagem = tkinter.PhotoImage(master=janela, file=caminho)
            fator = -(-imagem.height() // altura)    # arredonda para cima: nunca passa da altura
            if fator > 1:
                imagem = imagem.subsample(fator, fator)
            return imagem
        except Exception:
            continue
    return None


def versao_logo(largura, limite=LARGURA_LOGO_LARGO):
    """'largo' (logo 2) a partir da largura limite; senão 'normal' (logo 1)."""
    return "largo" if largura >= limite else "normal"


def trocar_logo(rotulo, largura, limite=LARGURA_LOGO_LARGO):
    """Troca só a imagem do rótulo quando a largura cruza o limite (mesmo widget, sem piscar).
    Devolve True se trocou."""
    imagens = getattr(rotulo, "_imagens_logo", None)
    if not imagens:
        return False
    versao = versao_logo(largura, limite)
    if versao == rotulo._versao_logo:
        return False
    rotulo.configure(image=imagens[versao])
    rotulo._versao_logo = versao
    return True


def criar_logo_cabecalho(pai, janela, bg, fg=None, fonte=None, limite=LARGURA_LOGO_LARGO):
    """Rótulo com o logo do cabeçalho (1; o 2 quando a janela passa de 'limite' px de largura).
    As duas imagens são carregadas uma vez só e a troca acontece no <Configure> da janela.
    Sem nenhuma imagem, devolve o nome digitado (como antes). O chamador faz o pack."""
    import tkinter
    imagens = {chave: carregar_logo(janela, numero) for chave, numero in LOGOS.items()}
    imagens["normal"] = imagens["normal"] or imagens["largo"]
    imagens["largo"] = imagens["largo"] or imagens["normal"]
    if imagens["normal"] is None:
        return tkinter.Label(pai, text=NOME_APP, fg=fg, bg=bg, font=fonte)
    rotulo = tkinter.Label(pai, image=imagens["normal"], bg=bg, bd=0, highlightthickness=0)
    rotulo._imagens_logo = imagens          # guarda as referências (senão o Tk apaga as imagens)
    rotulo._versao_logo = "normal"

    def ao_redimensionar(evento):
        if evento.widget is janela:         # o <Configure> da janela chega também dos filhos
            trocar_logo(rotulo, evento.width, limite)
    janela.bind("<Configure>", ao_redimensionar, add="+")
    return rotulo


def preparar_janela(janela, icone="app", padrao=False):
    """Ícone + barra de título nas cores do TEMA. Nunca levanta erro."""
    resultado = {"icone": "", "barra": []}
    try:
        resultado["icone"] = aplicar_icone(janela, icone, padrao)
    except Exception:
        pass
    try:
        resultado["barra"] = pintar_barra_titulo(janela)
    except Exception:
        pass
    return resultado
