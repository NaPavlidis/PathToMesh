import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import registro_erros
import tema_janela

# A lógica (tabela de materiais, leitura do SVG, catálogo, configuração e Blender) fica no
# nucleo.py, que a interface web (app_web.py) também usa. Esta interface Tkinter é a reserva:
# o app.py abre ela quando o pywebview (ou o WebView2) não funciona.
import nucleo
from nucleo import extrair_informacoes_svg, mapear_catalogo, EstadoApp


# ==============================================================================
# TEMA VISUAL (único lugar com cores, fontes e espaçamentos da interface)
# ==============================================================================
# Cores e espaços do modelo de layout (docs/modelo-layout.html), em tema_janela.py, que o
# launcher também usa: assim os dois ficam iguais.
TEMA = dict(tema_janela.TEMA)
ESPACO = dict(tema_janela.ESPACO)

_FAMILIA_TITULO, _FAMILIA_UI, _FAMILIA_MONO = tema_janela.familias_fontes()


def montar_fontes(titulo, corpo, mono):
    """Fontes do modelo, em pixels (tamanho negativo no Tk), para bater com os px do HTML.
    O Tk não tem peso 600 (semibold): vira bold."""
    return {
        'marca':      (titulo, -16, "bold"),   # title-md
        'titulo':     (titulo, -28, "bold"),   # headline-lg (título da tela)
        'secao':      (titulo, -20, "bold"),   # headline-md (título do cartão)
        'subtitulo':  (corpo, -14),            # body-md
        'corpo':      (corpo, -14),            # body-md
        'corpo_negrito': (corpo, -14, "bold"),
        'rotulo':     (corpo, -12, "bold"),    # label-md
        'dica':       (corpo, -13),            # body-sm
        'legenda':    (corpo, -12, "bold"),    # label-md, caixa alta
        'botao':      (corpo, -14, "bold"),    # label-lg
        'icone':      (corpo, -16),            # ícones em title-md
        'passo':      (mono, -12, "bold"),     # mono-sm dos círculos das etapas
        'status':     (titulo, -16, "bold"),   # title-md
        'grande':     (titulo, -36, "bold"),   # display-sm
        'nav':        (corpo, -14, "normal"),  # body-md
        'nav_ativo':  (corpo, -14, "bold"),    # label-lg
        'mono':       (mono, -13),             # mono-md (análise e catálogo)
        'mono_peq':   (mono, -12),             # mono-sm (selo "SVG → 3D")
    }


FONTES = montar_fontes(_FAMILIA_TITULO, _FAMILIA_UI, _FAMILIA_MONO)

# Botões: cor normal e com o mouse em cima (fundo, texto) e a borda de 1 px
BOTOES = {
    'principal':  {'bg': 'destaque', 'fg': 'sobre_destaque', 'bg_hover': 'marca', 'fg_hover': 'sobre_marca', 'borda': 'destaque'},
    'secundario': {'bg': 'elevado', 'fg': 'texto', 'bg_hover': 'elevado_hover', 'fg_hover': 'texto', 'borda': 'borda'},
    'sucesso':    {'bg': 'sucesso', 'fg': 'sobre_sucesso', 'bg_hover': 'sucesso_fundo', 'fg_hover': 'sucesso_claro', 'borda': 'sucesso'},
    'icone':      {'bg': 'container', 'fg': 'texto_suave', 'bg_hover': 'elevado', 'fg_hover': 'texto', 'borda': 'divisor'},
}


def aplicar_estilo(janela):
    """Fontes do modelo (se instaladas), tema ttk 'clam' na paleta do app e cores padrão dos
    menus suspensos."""
    FONTES.update(montar_fontes(*tema_janela.familias_fontes(janela)))
    estilo = ttk.Style(janela)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    # Caixas de seleção: quadrado escuro com borda cinza; marcada, fica azul (primary-container)
    for nome_estilo, fundo in (("Cartao.TCheckbutton", TEMA['superficie']), ("Grupo.TCheckbutton", TEMA['container'])):
        estilo.configure(nome_estilo,
                         background=fundo, foreground=TEMA['texto'],
                         font=FONTES['corpo'], focuscolor=fundo,
                         indicatorbackground=TEMA['campo'], indicatorforeground=TEMA['texto'],
                         upperbordercolor=TEMA['borda'], lowerbordercolor=TEMA['borda'],
                         indicatormargin=(0, 0, ESPACO['pm'], 0), indicatorsize=16, padding=(0, 2))
        estilo.map(nome_estilo,
                   background=[("active", fundo)],
                   foreground=[("disabled", TEMA['texto_apagado']), ("active", TEMA['texto'])],
                   indicatorbackground=[("selected", TEMA['marca']), ("pressed", TEMA['elevado']), ("active", TEMA['elevado'])],
                   upperbordercolor=[("selected", TEMA['marca']), ("active", TEMA['destaque'])],
                   lowerbordercolor=[("selected", TEMA['marca']), ("active", TEMA['destaque'])])

    estilo.configure("Vertical.TScrollbar",
                     background=TEMA['elevado_hover'], troughcolor=TEMA['campo'],
                     bordercolor=TEMA['campo'], lightcolor=TEMA['elevado_hover'], darkcolor=TEMA['elevado_hover'],
                     arrowcolor=TEMA['texto_suave'], gripcount=0, arrowsize=12)
    estilo.map("Vertical.TScrollbar",
               background=[("pressed", TEMA['destaque']), ("active", TEMA['borda'])],
               arrowcolor=[("active", TEMA['destaque'])])

    # Menus dos campos de escolha (OptionMenu)
    janela.option_add("*Menu.background", TEMA['container'])
    janela.option_add("*Menu.foreground", TEMA['texto'])
    janela.option_add("*Menu.activeBackground", TEMA['elevado'])
    janela.option_add("*Menu.activeForeground", TEMA['destaque'])
    janela.option_add("*Menu.relief", "flat")
    janela.option_add("*Menu.borderWidth", 0)
    janela.option_add("*Menu.font", FONTES['corpo'])


def criar_botao(pai, texto, comando, tipo="secundario", **extra):
    """Botão plano com borda de 1 px e estado de hover; 'principal' destaca a ação do passo.
    A borda acende no foco do teclado (o anel azul do modelo)."""
    cores = BOTOES[tipo]
    opcoes = dict(text=texto, command=comando, bd=0, relief="flat", cursor="hand2",
                  bg=TEMA[cores['bg']], fg=TEMA[cores['fg']],
                  activebackground=TEMA[cores['bg_hover']], activeforeground=TEMA[cores['fg_hover']],
                  disabledforeground=TEMA['texto_apagado'], highlightthickness=1,
                  highlightbackground=TEMA[cores['borda']], highlightcolor=TEMA['destaque'],
                  font=FONTES['botao'], padx=ESPACO['m'], pady=ESPACO['p'])
    opcoes.update(extra)
    botao = tk.Button(pai, **opcoes)

    def entrar(_evento):
        if str(botao.cget("state")) != "disabled":
            botao.configure(bg=TEMA[cores['bg_hover']], fg=TEMA[cores['fg_hover']])

    def sair(_evento):
        botao.configure(bg=TEMA[cores['bg']], fg=TEMA[cores['fg']])

    botao.bind("<Enter>", entrar)
    botao.bind("<Leave>", sair)
    return botao


def criar_cartao(pai, titulo=None, subtitulo=None, cor_titulo='texto'):
    """Cartão (card do modelo): fundo surface-container-low, borda de 1 px, recuo de 24 px e
    cabeçalho com linha embaixo. Devolve (cartão, corpo). O corpo já tem o recuo interno."""
    cartao = tk.Frame(pai, bg=TEMA['superficie'], highlightthickness=1,
                      highlightbackground=TEMA['borda'], highlightcolor=TEMA['borda'])
    if titulo:
        cab = tk.Frame(cartao, bg=TEMA['superficie'])
        cab.pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['m'] + ESPACO['xs'], 0))
        tk.Label(cab, text=titulo, fg=TEMA[cor_titulo], bg=TEMA['superficie'],
                 font=FONTES['secao'], anchor="w").pack(fill="x")
        if subtitulo:
            tk.Label(cab, text=subtitulo, fg=TEMA['texto_suave'], bg=TEMA['superficie'],
                     font=FONTES['dica'], anchor="w", justify="left").pack(fill="x", pady=(ESPACO['xs'], 0))
        criar_divisor(cartao).pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['m'], 0))
    corpo = tk.Frame(cartao, bg=TEMA['superficie'])
    corpo.pack(fill="both", expand=True, padx=ESPACO['g'], pady=(ESPACO['m'], ESPACO['m'] + ESPACO['xs']))
    return cartao, corpo


def criar_divisor(pai, cor='divisor'):
    return tk.Frame(pai, bg=TEMA[cor], height=1)


def criar_legenda(pai, texto, bg='superficie'):
    """Legenda de seção em caixa alta (ex.: ARQUIVO, ACABAMENTO)."""
    return tk.Label(pai, text=texto.upper(), fg=TEMA['texto_suave'], bg=TEMA[bg],
                    font=FONTES['legenda'], anchor="w")


def criar_secao(pai, texto):
    """Começo de seção do cartão: linha de cima (outline-variant), 16 px e a legenda."""
    criar_divisor(pai).pack(fill="x", pady=(ESPACO['pm'], ESPACO['pm']))
    legenda = criar_legenda(pai, texto)
    legenda.pack(fill="x", pady=(0, ESPACO['p']))
    return legenda


def criar_entrada(pai, variavel, **extra):
    """Campo de texto plano (surface-container-lowest) com borda que acende no foco."""
    opcoes = dict(textvariable=variavel, bg=TEMA['campo'], fg=TEMA['texto'],
                  insertbackground=TEMA['texto'], relief="flat", bd=0, font=FONTES['corpo'],
                  highlightthickness=1, highlightbackground=TEMA['borda'], highlightcolor=TEMA['destaque'],
                  selectbackground=TEMA['marca'], selectforeground=TEMA['sobre_marca'])
    opcoes.update(extra)
    return tk.Entry(pai, **opcoes)


def estilizar_optionmenu(menu_opcoes):
    menu_opcoes.config(bg=TEMA['campo'], fg=TEMA['texto'], activebackground=TEMA['container'],
                       activeforeground=TEMA['texto'], bd=0, relief="flat", highlightthickness=1,
                       highlightbackground=TEMA['borda'], highlightcolor=TEMA['destaque'],
                       font=FONTES['corpo'], anchor="w",
                       padx=ESPACO['pm'], pady=ESPACO['p'], cursor="hand2")
    menu_opcoes["menu"].config(bg=TEMA['container'], fg=TEMA['texto'], activebackground=TEMA['elevado'],
                               activeforeground=TEMA['destaque'], bd=0, font=FONTES['corpo'])


# Cores dos relatórios (análise do SVG e catálogo), pelo começo de cada linha. Só muda a cor
# do texto que o app já escreve; o texto em si é o mesmo.
REALCES_TEXTO = (
    ("─", 'divisor'),
    ("📁", 'titulo'), ("📦", 'titulo'), ("📐", 'titulo'), ("📈", 'titulo'), ("📝", 'titulo'),
    ("⚠", 'aviso'), ("❌", 'erro'),
    ("Modalidade:", 'destaque'), ("Status: ✓", 'ok'), ("Status: ✗", 'apagado'),
)


def realcar_texto(texto):
    """Pinta as linhas do relatório: títulos em verde, avisos em amarelo, erros em vermelho,
    divisórias apagadas (como no modelo). Chamado depois de cada insert."""
    for marca in ('divisor', 'titulo', 'aviso', 'erro', 'destaque', 'ok', 'apagado'):
        texto.tag_remove(marca, "1.0", "end")
    total = int(texto.index("end-1c").split(".")[0])
    for linha in range(1, total + 1):
        conteudo = texto.get(f"{linha}.0", f"{linha}.end").lstrip()
        for comeco, marca in REALCES_TEXTO:
            if conteudo.startswith(comeco):
                texto.tag_add(marca, f"{linha}.0", f"{linha}.end")
                break


class AreaTexto(tk.Text):
    """tk.Text que pinta o relatório a cada insert (só visual)."""

    def insert(self, indice, conteudo, *extra):
        resultado = super().insert(indice, conteudo, *extra)
        try:
            realcar_texto(self)
        except tk.TclError:
            pass
        return resultado


def criar_area_texto(pai):
    """Área de saída/log: fonte mono, painel surface-container-lowest com borda, com barra de
    rolagem. Devolve (moldura, texto)."""
    moldura = tk.Frame(pai, bg=TEMA['campo'], highlightthickness=1,
                       highlightbackground=TEMA['borda'], highlightcolor=TEMA['borda'])
    texto = AreaTexto(moldura, bg=TEMA['campo'], fg=TEMA['texto'], font=FONTES['mono'], bd=0,
                      relief="flat", padx=ESPACO['m'], pady=ESPACO['m'], highlightthickness=0,
                      insertbackground=TEMA['texto'], selectbackground=TEMA['marca'],
                      selectforeground=TEMA['sobre_marca'], spacing1=2, spacing3=2)
    texto.tag_configure('divisor', foreground=TEMA['divisor'])
    texto.tag_configure('titulo', foreground=TEMA['sucesso'], font=(FONTES['mono'][0], FONTES['mono'][1], "bold"))
    texto.tag_configure('aviso', foreground=TEMA['aviso'], background=TEMA['aviso_fundo'])
    texto.tag_configure('erro', foreground=TEMA['erro'])
    texto.tag_configure('destaque', foreground=TEMA['destaque'])
    texto.tag_configure('ok', foreground=TEMA['sucesso'])
    texto.tag_configure('apagado', foreground=TEMA['texto_apagado'])
    rolagem = ttk.Scrollbar(moldura, orient="vertical", command=texto.yview)
    texto.configure(yscrollcommand=rolagem.set)
    rolagem.pack(side="right", fill="y")
    texto.pack(side="left", fill="both", expand=True)
    return moldura, texto


def criar_cabecalho_tela(pai, titulo, subtitulo):
    """Título (headline-lg) e subtítulo (body-md) no topo de cada tela."""
    cab = tk.Frame(pai, bg=TEMA['fundo'])
    tk.Label(cab, text=titulo, fg=TEMA['texto'], bg=TEMA['fundo'], font=FONTES['titulo'], anchor="w").pack(fill="x")
    tk.Label(cab, text=subtitulo, fg=TEMA['texto_suave'], bg=TEMA['fundo'], font=FONTES['subtitulo'], anchor="w").pack(fill="x", pady=(ESPACO['xs'], 0))
    return cab


def criar_circulo(pai, texto, fundo, cor_texto, borda=None, tamanho=28, bg='fundo', fonte='passo'):
    """Círculo de verdade (Canvas) com o texto no meio: as etapas 1-2-3 do modelo."""
    canvas = tk.Canvas(pai, width=tamanho, height=tamanho, bg=TEMA[bg], highlightthickness=0, bd=0)
    canvas.create_oval(1, 1, tamanho - 1, tamanho - 1, fill=TEMA[fundo],
                       outline=TEMA[borda] if borda else TEMA[fundo], width=1)
    canvas.create_text(tamanho / 2, tamanho / 2, text=texto, fill=TEMA[cor_texto], font=FONTES[fonte])
    return canvas


def criar_selo(pai, texto, cor_texto='texto_suave', fundo='elevado', borda='divisor', fonte='mono_peq'):
    """Selo pequeno com borda (ex.: "SVG → 3D" ao lado do nome)."""
    moldura = tk.Frame(pai, bg=TEMA[borda], padx=1, pady=1)
    tk.Label(moldura, text=texto, fg=TEMA[cor_texto], bg=TEMA[fundo], font=FONTES[fonte],
             padx=ESPACO['p'], pady=ESPACO['xs'] - 2).pack()
    return moldura


# ==============================================================================
# JANELAS DA INTERFACE
# ==============================================================================
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(f"Configurações do Sistema - {tema_janela.NOME_APP}")
        # O tamanho da janela é calculado pelo conteúdo no fim do _build_ui (_ajustar_tamanho)
        self.configure(bg=TEMA['fundo'])
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.parent_app = parent
        self.blender_path_var = tk.StringVar(value=parent.blender_path)
        self.resina_dir_var = tk.StringVar(value=parent.resina_dir)
        self.blend_dir_var = tk.StringVar(value=parent.blend_dir)
        self.catalogo_dir_var = tk.StringVar(value=parent.catalogo_dir)
        self.selected_blend_var = tk.StringVar(value=parent.selected_blend)
        self.cycles_samples_var = tk.StringVar(value=str(parent.cycles_samples))
        self._build_ui()
        # Ícone e barra de título nas cores do tema (no Windows; fora dele, só o ícone)
        tema_janela.preparar_janela(self, "app")

    def _build_ui(self):
        sup = TEMA['superficie']

        # Ação principal: o rodapé entra primeiro e fica preso embaixo, para o botão
        # Salvar estar sempre visível (antes ele ficava fora da janela, junto com o
        # campo de samples, porque o conteúdo é mais alto que a janela).
        rodape = tk.Frame(self, bg=TEMA['fundo'])
        rodape.pack(side="bottom", fill="x", padx=ESPACO['g'], pady=(ESPACO['m'], ESPACO['g']))
        criar_botao(rodape, "Salvar Configurações", self._save_settings, "principal", padx=ESPACO['g']).pack(side="right")

        # Conteúdo com barra de rolagem (telas baixas ou com zoom do Windows)
        area = tk.Frame(self, bg=TEMA['fundo'])
        area.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(area, bg=TEMA['fundo'], highlightthickness=0, bd=0)
        rolagem = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        conteudo = tk.Frame(canvas, bg=TEMA['fundo'])
        item_conteudo = canvas.create_window((0, 0), window=conteudo, anchor="nw")
        conteudo.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item_conteudo, width=e.width))

        def rolar(evento):
            if getattr(evento, "num", None) == 4 or getattr(evento, "delta", 0) > 0:
                canvas.yview_scroll(-1, "units")
            else:
                canvas.yview_scroll(1, "units")
        self.bind("<MouseWheel>", rolar)
        self.bind("<Button-4>", rolar)
        self.bind("<Button-5>", rolar)
        self._area_conteudo, self._rodape = conteudo, rodape

        # Cabeçalho
        cab = tk.Frame(conteudo, bg=TEMA['fundo'])
        cab.pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['g'], ESPACO['m']))
        tk.Label(cab, text="⚙ Configurações e Diretórios", fg=TEMA['texto'], bg=TEMA['fundo'], font=FONTES['titulo'], anchor="w").pack(fill="x")
        tk.Label(cab, text="Caminhos e opções usados pelo app. Ficam salvos para as próximas vezes.",
                 fg=TEMA['texto_suave'], bg=TEMA['fundo'], font=FONTES['subtitulo'], anchor="w").pack(fill="x", pady=(2, 0))

        def campo_com_busca(pai, rotulo, dica, variavel, comando):
            bloco = tk.Frame(pai, bg=sup)
            bloco.pack(fill="x", pady=(0, ESPACO['m']))
            tk.Label(bloco, text=rotulo, fg=TEMA['texto'], bg=sup, font=FONTES['rotulo'], anchor="w").pack(fill="x")
            tk.Label(bloco, text=dica, fg=TEMA['texto_apagado'], bg=sup, font=FONTES['dica'], anchor="w").pack(fill="x", pady=(0, ESPACO['xs']))
            linha = tk.Frame(bloco, bg=sup)
            linha.pack(fill="x")
            criar_entrada(linha, variavel).pack(side="left", fill="x", expand=True, ipady=ESPACO['xs'] + 2, padx=(0, ESPACO['p']))
            criar_botao(linha, "Buscar...", comando, "secundario", font=FONTES['corpo'], pady=ESPACO['xs']).pack(side="right")

        # Cartão: programas e pastas
        cartao_pastas, corpo_pastas = criar_cartao(conteudo, "Programas e pastas")
        cartao_pastas.pack(fill="x", padx=ESPACO['g'], pady=(0, ESPACO['m']))

        # Executável do Blender
        campo_com_busca(corpo_pastas, "Executável do Blender (blender.exe):",
                        "O programa que monta e renderiza o troféu em 3D.",
                        self.blender_path_var, self._select_blender)

        # Diretório do Catálogo
        campo_com_busca(corpo_pastas, "Pasta Raiz do Catálogo:",
                        "Pasta com as modalidades: <MODALIDADE>\\<MODELO>\\SVG.",
                        self.catalogo_dir_var, self._select_catalogo_dir)

        # Pasta de Modelos 3D (Resina)
        campo_com_busca(corpo_pastas, "Pasta dos Modelos 3D (Resina):",
                        "Arquivos .obj, .fbx, .stl ou .blend para o encaixe de resina.",
                        self.resina_dir_var, self._select_resina_dir)

        # Pasta dos Arquivos .Blend
        campo_com_busca(corpo_pastas, "Pasta dos Estúdios Base (.blend):",
                        "Pasta onde ficam as cenas de estúdio (.blend).",
                        self.blend_dir_var, self._select_blend_dir)

        # Cartão: renderização
        cartao_render, corpo_render = criar_cartao(conteudo, "Renderização")
        cartao_render.pack(fill="x", padx=ESPACO['g'], pady=(0, ESPACO['m']))

        # Dropdown Blend
        f_sel = tk.Frame(corpo_render, bg=sup)
        f_sel.pack(fill="x", pady=(0, ESPACO['m']))
        tk.Label(f_sel, text="Estúdio Base (.blend) Ativo:", fg=TEMA['destaque'], bg=sup, font=FONTES['rotulo'], anchor="w").pack(fill="x", pady=(0, ESPACO['xs']))
        self.blend_dropdown_menu = tk.OptionMenu(f_sel, self.selected_blend_var, "")
        estilizar_optionmenu(self.blend_dropdown_menu)
        self.blend_dropdown_menu.pack(fill="x")
        self._atualizar_lista_blends()

        # Cycles Samples
        f_samp = tk.Frame(corpo_render, bg=sup)
        f_samp.pack(fill="x")
        tk.Label(f_samp, text="Qtd de Samples do Cycles:", fg=TEMA['texto'], bg=sup, font=FONTES['rotulo'], anchor="w").pack(fill="x")
        tk.Label(f_samp, text="Mais samples deixam a imagem mais limpa, mas o render demora mais.",
                 fg=TEMA['texto_apagado'], bg=sup, font=FONTES['dica'], anchor="w").pack(fill="x", pady=(0, ESPACO['xs']))
        criar_entrada(f_samp, self.cycles_samples_var, width=15).pack(anchor="w", ipady=ESPACO['xs'] + 2)

        self._ajustar_tamanho()

    def _ajustar_tamanho(self):
        """Altura da janela = altura do conteúdo + rodapé, sem passar da tela (aí entra a rolagem)."""
        self.update_idletasks()
        largura = 640
        altura = self._area_conteudo.winfo_reqheight() + self._rodape.winfo_reqheight() + ESPACO['m'] + ESPACO['g']
        altura = max(360, min(altura, self.winfo_screenheight() - 120))
        self.geometry(f"{largura}x{altura}")
        self.minsize(560, min(altura, 360))

    def _select_blender(self):
        f = filedialog.askopenfilename(title="Selecione o executável do Blender", filetypes=[("Executável Blender", "blender.exe"), ("Todos", "*.*")])
        if f: self.blender_path_var.set(f)

    def _select_catalogo_dir(self):
        f = filedialog.askdirectory(title="Selecione a Pasta Raiz do Catálogo")
        if f: self.catalogo_dir_var.set(f)

    def _select_resina_dir(self):
        f = filedialog.askdirectory(title="Selecione a Pasta de Modelos 3D (Resina)")
        if f: self.resina_dir_var.set(f)

    def _select_blend_dir(self):
        f = filedialog.askdirectory(title="Selecione a Pasta contendo os arquivos .blend")
        if f:
            self.blend_dir_var.set(f)
            self._atualizar_lista_blends()

    def _atualizar_lista_blends(self):
        pasta = self.blend_dir_var.get()
        menu = self.blend_dropdown_menu["menu"]
        menu.delete(0, "end")
        arquivos_blend = nucleo.listar_blends(pasta)
        if arquivos_blend:
            for arq in arquivos_blend:
                menu.add_command(label=arq, command=lambda value=arq: self.selected_blend_var.set(value))
            if self.selected_blend_var.get() not in arquivos_blend:
                self.selected_blend_var.set(arquivos_blend[0])
        else:
            self.selected_blend_var.set("Nenhum arquivo .blend encontrado")
            menu.add_command(label="Nenhum arquivo .blend encontrado", command=lambda: None)

    def _save_settings(self):
        self.parent_app.blender_path = self.blender_path_var.get()
        self.parent_app.resina_dir = self.resina_dir_var.get()
        self.parent_app.blend_dir = self.blend_dir_var.get()
        self.parent_app.catalogo_dir = self.catalogo_dir_var.get()
        self.parent_app.selected_blend = self.selected_blend_var.get()
        self.parent_app.cycles_samples = nucleo.ler_samples(self.cycles_samples_var.get())
        self.parent_app.salvar_configuracoes_disco()
        if hasattr(self.parent_app, "_atualizar_hud_resina"):
            self.parent_app._atualizar_hud_resina()
        messagebox.showinfo("Sucesso", "Configurações salvas permanentemente!", parent=self)
        self.destroy()


class VectorConvertProApp(EstadoApp, tk.Tk):
    # A configuração (valores padrão, carregar_configuracoes_disco e salvar_configuracoes_disco)
    # vem do nucleo.EstadoApp
    def __init__(self):
        super().__init__()
        self.title(tema_janela.NOME_APP)
        self.geometry("1150x820")
        self.minsize(980, 700)
        self.configure(bg=TEMA['fundo'])
        aplicar_estilo(self)
        # Ícone (vale também para as janelas que abrem depois) e barra de título nas cores do tema
        tema_janela.preparar_janela(self, "app", padrao=True)

        # Configurações Padrão e as do config.local.json
        self.definir_padroes()

        self.render_auto_var = tk.BooleanVar(value=True)
        self.usar_textura_var = tk.BooleanVar(value=True)
        self.usar_verniz_var = tk.BooleanVar(value=False)
        self.modelo_resina_selecionado = tk.StringVar(value="Nenhum")

        # SELEÇÃO DE CÂMERAS (Padrão: Todas 3 ativadas)
        self.cam_principal_var = tk.BooleanVar(value=True)
        self.cam_esquerda_var = tk.BooleanVar(value=True)
        self.cam_direita_var = tk.BooleanVar(value=True)

        self.sidebar_buttons = {}
        self.screens = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_navbar()
        self._build_sidebar()
        
        self.main_container = tk.Frame(self, bg=TEMA['fundo'])
        self.main_container.grid(row=1, column=1, sticky="nsew", padx=ESPACO['gg'], pady=ESPACO['m'])
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self._build_upload_screen()
        self._build_processing_screen()
        self._build_download_screen()
        self._build_catalogo_screen()

        self._build_footer()
        self._show_screen("upload")

    def _obter_cameras_selecionadas_str(self):
        return nucleo.cameras_selecionadas_str(self.cam_principal_var.get(), self.cam_esquerda_var.get(),
                                               self.cam_direita_var.get())

    def _build_navbar(self):
        # Barra de 56 px (surface-container-low) com linha embaixo (outline)
        navbar = tk.Frame(self, bg=TEMA['barra'], height=56, padx=ESPACO['g'])
        navbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        navbar.pack_propagate(False)
        # Logo (ícone 1; ícone 2 com a janela larga) no lugar do nome digitado
        tema_janela.criar_logo_cabecalho(navbar, self, TEMA['barra'], TEMA['destaque'], FONTES['marca']).pack(side="left")
        criar_selo(navbar, "SVG → 3D").pack(side="left", padx=(ESPACO['pm'], 0))

        right_icons_frame = tk.Frame(navbar, bg=TEMA['barra'])
        right_icons_frame.pack(side="right")
        criar_botao(right_icons_frame, "⚙", lambda: SettingsWindow(self), "icone",
                    font=FONTES['icone'], padx=ESPACO['p'], pady=ESPACO['xs']).pack(side="left")
        # Linha separando a barra do conteúdo
        tk.Frame(self, bg=TEMA['borda'], height=1).grid(row=0, column=0, columnspan=2, sticky="sew")

    def _build_sidebar(self):
        # Menu lateral de 240 px (surface-container-low), recuo de 16 px e borda direita (outline)
        sidebar = tk.Frame(self, bg=TEMA['superficie'], width=240)
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.pack_propagate(False)
        self._sidebar = sidebar
        tk.Frame(sidebar, bg=TEMA['borda'], width=1).pack(side="right", fill="y")

        header_frame = tk.Frame(sidebar, bg=TEMA['superficie'], padx=ESPACO['p'])
        header_frame.pack(fill="x", padx=ESPACO['m'], pady=(ESPACO['m'] + ESPACO['xs'], 0))
        tk.Label(header_frame, text="SVG Converter", fg=TEMA['texto'], bg=TEMA['superficie'], font=FONTES['marca'], anchor="w").pack(fill="x")
        tk.Label(header_frame, text="HIGH PRECISION TOOL", fg=TEMA['texto_apagado'], bg=TEMA['superficie'], font=FONTES['legenda'], anchor="w").pack(fill="x")
        criar_divisor(sidebar).pack(fill="x", padx=ESPACO['m'], pady=(ESPACO['m'], 0))
        legenda_nav = criar_legenda(sidebar, "Navegação")
        legenda_nav.configure(fg=TEMA['texto_apagado'])
        legenda_nav.pack(fill="x", padx=ESPACO['m'] + ESPACO['pm'], pady=(ESPACO['g'], ESPACO['xs']))

        menu_items = {
            "upload": " Upload",
            "processing": " Processing",
            "download": " Download",
            "catalogo": " 📊 Catálogo"
        }
        for key, text in menu_items.items():
            # Item: 12 px de recuo, 8 px em cima e embaixo; o ativo ganha fundo, borda e texto azul
            btn = tk.Button(sidebar, text=text, fg=TEMA['texto_suave'], bg=TEMA['superficie'], bd=0, relief="flat",
                            anchor="w", padx=ESPACO['pm'], pady=ESPACO['p'], font=FONTES['nav'], cursor="hand2",
                            activebackground=TEMA['container'], activeforeground=TEMA['texto'],
                            highlightthickness=1, highlightbackground=TEMA['superficie'], highlightcolor=TEMA['destaque'],
                            command=lambda k=key: self._show_screen(k))
            btn.pack(fill="x", padx=ESPACO['m'], pady=(0, ESPACO['xs']))
            # Hover só nos itens inativos (o ativo fica com o texto em destaque)
            btn.bind("<Enter>", lambda _e, b=btn: b.cget("fg") != TEMA['destaque'] and b.configure(bg=TEMA['container'], fg=TEMA['texto']))
            btn.bind("<Leave>", lambda _e, b=btn: b.cget("fg") != TEMA['destaque'] and b.configure(bg=TEMA['superficie'], fg=TEMA['texto_suave']))
            self.sidebar_buttons[key] = btn

    def _show_screen(self, screen_key):
        for key, btn in self.sidebar_buttons.items():
            if key == screen_key:
                btn.configure(bg=TEMA['elevado'], fg=TEMA['destaque'], font=FONTES['nav_ativo'],
                              highlightbackground=TEMA['borda'])
            else:
                btn.configure(bg=TEMA['superficie'], fg=TEMA['texto_suave'], font=FONTES['nav'],
                              highlightbackground=TEMA['superficie'])

        if screen_key == "catalogo":
            self._atualizar_relatorio_catalogo()

        self.screens[screen_key].tkraise()

    def _create_stepper(self, parent, active_step):
        # Etapas lado a lado (círculo de 28 px + nome), linha de 80 px entre elas e linha embaixo
        stepper_frame = tk.Frame(parent, bg=TEMA['fundo'])
        stepper_frame.pack(fill="x", pady=(0, ESPACO['m']))

        steps = [("1", "UPLOAD"), ("2", "PROCESSING"), ("3", "DOWNLOAD")]
        stepper_inner = tk.Frame(stepper_frame, bg=TEMA['fundo'])
        stepper_inner.pack(anchor="center", pady=(0, ESPACO['pm']))
        criar_divisor(stepper_frame).pack(fill="x")

        for idx, (num, label) in enumerate(steps, start=1):
            if idx > 1:
                # Linha ligando os passos: acesa até o passo atual
                cor_linha = TEMA['destaque'] if idx <= active_step else TEMA['borda']
                tk.Frame(stepper_inner, bg=cor_linha, width=80, height=1).pack(side="left", padx=ESPACO['g'])
            step_item = tk.Frame(stepper_inner, bg=TEMA['fundo'])
            step_item.pack(side="left")
            completed = idx <= active_step
            atual = idx == active_step
            text_color = TEMA['texto'] if atual else TEMA['texto_suave']
            symbol = "✓" if idx < active_step else num

            if completed:
                criar_circulo(step_item, symbol, 'destaque', 'sobre_destaque').pack(side="left")
            else:
                criar_circulo(step_item, symbol, 'elevado', 'texto_suave', borda='borda').pack(side="left")
            tk.Label(step_item, text=label, fg=text_color, bg=TEMA['fundo'], font=FONTES['legenda']).pack(side="left", padx=(ESPACO['p'], 0))

    def _atualizar_hud_resina(self):
        menu = self.menu_resina["menu"]
        menu.delete(0, "end")
        arquivos = nucleo.listar_modelos_resina(self.resina_dir)
        if arquivos:
            menu.add_command(label="Nenhum (Ignorar Encaixe)", command=lambda: self.modelo_resina_selecionado.set("Nenhum"))
            for arq in arquivos:
                menu.add_command(label=arq, command=lambda v=arq: self.modelo_resina_selecionado.set(v))
            if self.modelo_resina_selecionado.get() not in arquivos:
                self.modelo_resina_selecionado.set(arquivos[0])
        else:
            self.modelo_resina_selecionado.set("Nenhum modelo 3D encontrado")
            menu.add_command(label="Nenhum modelo 3D encontrado", command=lambda: None)

    def _build_upload_screen(self):
        sup = TEMA['superficie']
        screen = tk.Frame(self.main_container, bg=TEMA['fundo'])
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens["upload"] = screen

        self._create_stepper(screen, active_step=1)
        criar_cabecalho_tela(screen, "Novo troféu",
                             "Escolha o arquivo SVG, ajuste as opções e avance para o Blender.").pack(fill="x", pady=(0, ESPACO['m']))

        main_frame = tk.Frame(screen, bg=TEMA['fundo'])
        main_frame.pack(fill="both", expand=True)
        # Duas colunas de mesma largura que acompanham o redimensionamento (24 px entre elas)
        main_frame.grid_columnconfigure(0, weight=1, uniform="colunas")
        main_frame.grid_columnconfigure(1, weight=1, uniform="colunas")
        main_frame.grid_rowconfigure(0, weight=1)

        # Lado Esquerdo: Formulário de Upload e Opções
        card_left, corpo_left = criar_cartao(main_frame, "Upload e Parâmetros do SVG")
        card_left.grid(row=0, column=0, sticky="nsew", padx=(0, ESPACO['pm']))

        # Botão Próximo (ação principal do passo, no rodapé do cartão, com linha em cima). O
        # rodapé é empacotado primeiro, preso embaixo: se faltar altura, ele nunca é cortado.
        rodape_left = tk.Frame(corpo_left, bg=sup)
        rodape_left.pack(side="bottom", fill="x")
        criar_divisor(rodape_left, 'borda').pack(fill="x", pady=(ESPACO['pm'], ESPACO['pm']))
        btn_proximo = criar_botao(rodape_left, "Próximo ➔", self._avancar_para_processamento, "principal",
                                  padx=ESPACO['g'], pady=ESPACO['pm'] - 2)
        btn_proximo.pack(side="right")

        # Seção: arquivo (painel surface-container-lowest com borda e 12 px de recuo)
        criar_legenda(corpo_left, "Arquivo").pack(fill="x", pady=(0, ESPACO['p']))
        zona_arquivo = tk.Frame(corpo_left, bg=TEMA['campo'], highlightthickness=1, highlightbackground=TEMA['borda'])
        zona_arquivo.pack(fill="x")
        icone_arquivo = tk.Frame(zona_arquivo, bg=TEMA['secundario'], width=32, height=32)
        icone_arquivo.pack(side="left", padx=(ESPACO['pm'], 0), pady=ESPACO['p'])
        icone_arquivo.pack_propagate(False)
        tk.Label(icone_arquivo, text="⌁", fg=TEMA['sobre_secundario'], bg=TEMA['secundario'], font=FONTES['icone']).pack(expand=True)
        self.lbl_arquivo_selecionado = tk.Label(zona_arquivo, text="Nenhum arquivo selecionado", fg=TEMA['texto_suave'], bg=TEMA['campo'], font=FONTES['mono'], anchor="w")
        self.lbl_arquivo_selecionado.pack(side="left", fill="x", expand=True, padx=ESPACO['pm'], pady=ESPACO['p'])

        btn_select = criar_botao(zona_arquivo, "Selecionar Arquivo SVG", self._selecionar_svg, "secundario", pady=ESPACO['xs'] + 2)
        btn_select.pack(side="right", padx=ESPACO['pm'], pady=ESPACO['p'])

        # Seção: renderização
        criar_secao(corpo_left, "Renderização")
        chk_render = ttk.Checkbutton(corpo_left, text="Renderizar automaticamente no Blender", variable=self.render_auto_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_render.pack(anchor="w")

        # SELEÇÃO DAS CÂMERAS (grupo em surface-container, com borda e 12 px de recuo)
        grupo = TEMA['container']
        frame_cams = tk.Frame(corpo_left, bg=grupo, highlightthickness=1, highlightbackground=TEMA['borda'],
                              padx=ESPACO['pm'], pady=ESPACO['xs'] + 2)
        frame_cams.pack(fill="x", pady=(ESPACO['xs'], 0))
        tk.Label(frame_cams, text="📷 Câmeras a Renderizar:", fg=TEMA['destaque'], bg=grupo, font=FONTES['rotulo']).pack(anchor="w", pady=(0, ESPACO['xs']))

        sub_cams = tk.Frame(frame_cams, bg=grupo)
        sub_cams.pack(anchor="w")

        chk_cam_p = ttk.Checkbutton(sub_cams, text="Principal", variable=self.cam_principal_var, style="Grupo.TCheckbutton", cursor="hand2")
        chk_cam_p.pack(side="left", padx=(0, ESPACO['g']))

        chk_cam_e = ttk.Checkbutton(sub_cams, text="Esquerda", variable=self.cam_esquerda_var, style="Grupo.TCheckbutton", cursor="hand2")
        chk_cam_e.pack(side="left", padx=(0, ESPACO['g']))

        chk_cam_d = ttk.Checkbutton(sub_cams, text="Direita", variable=self.cam_direita_var, style="Grupo.TCheckbutton", cursor="hand2")
        chk_cam_d.pack(side="left")

        # Seção: acabamento
        criar_secao(corpo_left, "Acabamento")
        chk_textura = ttk.Checkbutton(corpo_left, text="Aplicar texturas (madeira no MDF)", variable=self.usar_textura_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_textura.pack(anchor="w")

        chk_verniz = ttk.Checkbutton(corpo_left, text="Aplicar Verniz na madeira", variable=self.usar_verniz_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_verniz.pack(anchor="w")

        criar_divisor(corpo_left).pack(fill="x", pady=(ESPACO['pm'], ESPACO['pm']))
        frame_resina = tk.Frame(corpo_left, bg=sup)
        frame_resina.pack(fill="x")
        tk.Label(frame_resina, text="💎 Modelo 3D de Resina para Encaixe:", fg=TEMA['destaque'], bg=sup, font=FONTES['rotulo']).pack(anchor="w", pady=(0, ESPACO['p']))
        self.menu_resina = tk.OptionMenu(frame_resina, self.modelo_resina_selecionado, "")
        estilizar_optionmenu(self.menu_resina)
        self.menu_resina.pack(fill="x")
        self._atualizar_hud_resina()

        # Lado Direito: Card de Análise Rápida do SVG
        card_right, corpo_right = criar_cartao(main_frame, "📊 Análise Estrutural do SVG",
                                               "Materiais, quantidades e medidas lidas do arquivo.", cor_titulo='destaque')
        card_right.grid(row=0, column=1, sticky="nsew", padx=(ESPACO['pm'], 0))

        moldura_analise, self.txt_analise_svg = criar_area_texto(corpo_right)
        moldura_analise.pack(fill="both", expand=True)
        self.txt_analise_svg.insert("1.0", "Aguardando seleção de arquivo SVG...")
        self.txt_analise_svg.configure(state="disabled")

    def _selecionar_svg(self):
        file_path = filedialog.askopenfilename(title="Selecionar SVG", filetypes=[("Arquivos SVG", "*.svg"), ("Todos", "*.*")])
        if file_path:
            self.svg_selecionado = file_path
            self.lbl_arquivo_selecionado.configure(text=os.path.basename(file_path), fg="#34D399")

            self.output_path = nucleo.preparar_pasta_saida(file_path)

            self._analisar_e_exibir_svg(file_path)

    def _avancar_para_processamento(self):
        aviso = nucleo.validar_avanco(self.svg_selecionado, self.render_auto_var.get(), self.cam_principal_var.get(),
                                      self.cam_esquerda_var.get(), self.cam_direita_var.get())
        if aviso:
            messagebox.showwarning("Atenção", aviso)
            return

        self.lbl_status_processamento.configure(text=nucleo.STATUS_INICIAL)
        for widget in self.frame_historico.winfo_children():
            widget.destroy()
            
        self._show_screen("processing")
        self._iniciar_processamento_background()

    def _analisar_e_exibir_svg(self, caminho_svg):
        info = extrair_informacoes_svg(caminho_svg)
        self.txt_analise_svg.configure(state="normal")
        self.txt_analise_svg.delete("1.0", "end")

        self.txt_analise_svg.insert("1.0", nucleo.montar_resumo_svg(info))

        self.txt_analise_svg.configure(state="disabled")

        if info and info['pecas_descartadas']:
            self._avisar_pecas_descartadas(info['pecas_descartadas'])

    def _avisar_pecas_descartadas(self, pecas_descartadas):
        messagebox.showwarning(nucleo.TITULO_AVISO_DESCARTADAS, nucleo.montar_aviso_descartadas(pecas_descartadas))

    def _build_catalogo_screen(self):
        sup = TEMA['superficie']
        screen = tk.Frame(self.main_container, bg=TEMA['fundo'])
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens["catalogo"] = screen

        card = tk.Frame(screen, bg=sup, highlightthickness=1, highlightbackground=TEMA['borda'])
        card.pack(fill="both", expand=True)

        header = tk.Frame(card, bg=sup)
        header.pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['g'], ESPACO['m']))

        titulos = tk.Frame(header, bg=sup)
        titulos.pack(side="left", fill="x", expand=True)
        tk.Label(titulos, text="📊 Mapeamento do Catálogo de Troféus", fg=TEMA['destaque'], bg=sup, font=FONTES['secao'], anchor="w").pack(fill="x")
        tk.Label(titulos, text="Modalidades e modelos do catálogo que já têm SVG pronto.", fg=TEMA['texto_suave'], bg=sup, font=FONTES['dica'], anchor="w").pack(fill="x", pady=(ESPACO['xs'], 0))
        criar_botao(header, "🔄 Atualizar Catálogo", self._atualizar_relatorio_catalogo, "secundario").pack(side="right", anchor="n")

        criar_divisor(card).pack(fill="x", padx=ESPACO['g'])
        moldura_catalogo, self.txt_catalogo = criar_area_texto(card)
        moldura_catalogo.pack(fill="both", expand=True, padx=ESPACO['g'], pady=ESPACO['g'])

    def _atualizar_relatorio_catalogo(self):
        modalidades, status = mapear_catalogo(self.catalogo_dir)
        self.txt_catalogo.configure(state="normal")
        self.txt_catalogo.delete("1.0", "end")
        self.txt_catalogo.insert("1.0", nucleo.montar_relatorio_catalogo(modalidades, status, self.catalogo_dir))
        self.txt_catalogo.configure(state="disabled")

    def _iniciar_processamento_background(self):
        threading.Thread(target=self._executar_blender_subprocess, daemon=True).start()

    def atualizar_amostras_camera_ui(self, atual, total, faltam, porcentagem, nome_cam):
        status, linha_samples = nucleo.textos_amostras(atual, total, faltam, nome_cam)
        self.lbl_status_processamento.configure(text=status)
        self.lbl_samples_info.configure(text=linha_samples)
        self.atualizar_barra_progresso(porcentagem)

    def _executar_blender_subprocess(self):
        # Comando, leitura da saída e log de erro ficam no nucleo; aqui só se mostra na tela
        comando = nucleo.montar_comando_blender(self, self.modelo_resina_selecionado.get(), self.render_auto_var.get(),
                                                self.usar_textura_var.get(), self.usar_verniz_var.get(),
                                                self._obter_cameras_selecionadas_str())
        nucleo.executar_blender(comando, self._ao_evento_blender, origem="app_ui (Blender)")

    def _ao_evento_blender(self, evento):
        # Chamado na thread do Blender: a tela só muda pelo after (na thread do Tk)
        tipo = evento[0]
        if tipo == "status":
            self.after(0, lambda t=evento[1]: self.lbl_status_processamento.configure(text=t))
        elif tipo == "passo":
            self.after(0, lambda c=evento[1], n=evento[2]: self.adicionar_passo_concluido(c, n))
        elif tipo == "amostras":
            self.after(0, lambda e=evento: self.atualizar_amostras_camera_ui(*e[1:]))
        elif tipo == "concluido":
            self.after(0, lambda: self.tag_concluido())
        elif tipo == "erro":
            messagebox.showerror("Erro Crítico", evento[1])

    def atualizar_barra_progresso(self, porcentagem):
        largura_atual = self.canvas_barra.winfo_width()
        if largura_atual < 10:
            largura_atual = 440
        largura_preenchimento = (porcentagem / 100.0) * largura_atual
        self.canvas_barra.coords(self.retangulo_progresso, 0, 0, largura_preenchimento, 16)
        self.lbl_porcentagem.configure(text=f"{int(porcentagem)}%")

    def adicionar_passo_concluido(self, texto_concluido, novo_status):
        lbl_hist = tk.Label(self.frame_historico, text=texto_concluido, fg=TEMA['sucesso'], bg=TEMA['superficie'], font=FONTES['corpo_negrito'], anchor="w")
        lbl_hist.pack(fill="x", pady=2)
        self.lbl_status_processamento.configure(text=novo_status)

    def tag_concluido(self):
        self.lbl_status_processamento.configure(text=nucleo.STATUS_CONCLUIDO)
        self.atualizar_barra_progresso(100)
        self.lbl_samples_info.configure(text=nucleo.SAMPLES_CONCLUIDO)
        self._show_screen("download")

    def _build_processing_screen(self):
        sup = TEMA['superficie']
        screen = tk.Frame(self.main_container, bg=TEMA['fundo'])
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens["processing"] = screen

        self._create_stepper(screen, active_step=2)
        card, corpo = criar_cartao(screen)
        card.pack(fill="both", expand=True)

        conteudo = tk.Frame(corpo, bg=sup)
        conteudo.pack(fill="x", padx=ESPACO['gg'], pady=(ESPACO['g'], 0))

        tk.Label(conteudo, text="Processando Troféu no Blender...", fg=TEMA['texto'], bg=sup, font=FONTES['titulo'], anchor="w").pack(fill="x")
        self.lbl_status_processamento = tk.Label(conteudo, text="🔄 Iniciando importação e montagem de malhas...", fg=TEMA['destaque'], bg=sup, font=FONTES['status'], anchor="w")
        self.lbl_status_processamento.pack(fill="x", pady=(ESPACO['p'], 0))

        frame_progresso_container = tk.Frame(conteudo, bg=sup)
        frame_progresso_container.pack(fill="x", pady=(ESPACO['g'], 0))

        # Linha de informação: samples à esquerda, porcentagem à direita
        linha_info = tk.Frame(frame_progresso_container, bg=sup)
        linha_info.pack(fill="x", pady=(0, ESPACO['p']))
        self.lbl_samples_info = tk.Label(linha_info, text="Aguardando início do Cycles...", fg=TEMA['texto_suave'], bg=sup, font=FONTES['rotulo'], anchor="w")
        self.lbl_samples_info.pack(side="left", fill="x", expand=True)

        self.lbl_porcentagem = tk.Label(linha_info, text="0%", fg=TEMA['destaque'], bg=sup, font=FONTES['status'])
        self.lbl_porcentagem.pack(side="right")

        # Trilho da barra com borda de 1 px (outline)
        f_bar_bg = tk.Frame(frame_progresso_container, bg=TEMA['borda'], padx=1, pady=1)
        f_bar_bg.pack(fill="x")

        self.canvas_barra = tk.Canvas(f_bar_bg, bg=TEMA['campo'], height=16, highlightthickness=0, bd=0)
        self.canvas_barra.pack(fill="x")
        self.retangulo_progresso = self.canvas_barra.create_rectangle(0, 0, 0, 16, fill=TEMA['destaque'], width=0)

        # Etapas concluídas
        criar_divisor(conteudo).pack(fill="x", pady=(ESPACO['g'], ESPACO['m']))
        criar_legenda(conteudo, "Etapas concluídas").pack(fill="x", pady=(0, ESPACO['p']))
        self.frame_historico = tk.Frame(conteudo, bg=sup)
        self.frame_historico.pack(fill="x")

    def _build_download_screen(self):
        sup = TEMA['superficie']
        screen = tk.Frame(self.main_container, bg=TEMA['fundo'])
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens["download"] = screen

        self._create_stepper(screen, active_step=3)
        card, corpo = criar_cartao(screen)
        card.pack(fill="both", expand=True)

        # Bloco centralizado na vertical e na horizontal
        centro = tk.Frame(corpo, bg=sup)
        centro.place(relx=0.5, rely=0.45, anchor="center")

        criar_circulo(centro, "✓", 'sucesso', 'sobre_sucesso', tamanho=88, bg='superficie', fonte='grande').pack(pady=(0, ESPACO['g']))
        tk.Label(centro, text="Processamento Concluído!", fg=TEMA['sucesso'], bg=sup, font=FONTES['titulo']).pack()
        tk.Label(centro, text="Abra a pasta para ver as imagens e os arquivos gerados.", fg=TEMA['texto_suave'], bg=sup, font=FONTES['subtitulo']).pack(pady=(ESPACO['xs'], 0))
        criar_botao(centro, "Abrir Pasta de Imagens / Arquivos", lambda: nucleo.abrir_pasta_saida(self.output_path), "sucesso",
                    padx=ESPACO['g'], pady=ESPACO['p'] + 2).pack(pady=(ESPACO['g'], 0))

    def _build_footer(self):
        # Como no modelo: o rodapé fica no pé do menu lateral, com linha em cima (outline)
        footer = tk.Frame(self._sidebar, bg=TEMA['superficie'])
        footer.pack(side="bottom", fill="x", padx=ESPACO['m'], pady=(0, ESPACO['m']))
        tk.Frame(footer, bg=TEMA['borda'], height=1).pack(fill="x")
        tk.Label(footer, text=f"© 2026 {tema_janela.NOME_APP}. All rights reserved.", fg=TEMA['texto_apagado'], bg=TEMA['superficie'],
                 font=FONTES['dica'], anchor="w", justify="left", wraplength=190).pack(fill="x", padx=ESPACO['p'], pady=(ESPACO['m'], 0))


def executar():
    """Abre a interface Tkinter (chamado aqui embaixo e pelo app.py, como reserva)."""
    app = VectorConvertProApp()
    app.report_callback_exception = registro_erros.gancho_tk("app_ui")
    app.mainloop()


if __name__ == "__main__":
    registro_erros.instalar_ganchos("app_ui")
    executar()