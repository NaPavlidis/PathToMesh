import os
import re
import sys
import json
import subprocess
import threading
import textwrap
import collections
import traceback
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import registro_erros

try:
    from svgpathtools import parse_path
    HAS_SVGPATH = True
except ImportError:
    HAS_SVGPATH = False

# A configuração do usuário fica no config.local.json (no .gitignore, nunca vai para o GitHub).
# Se ele não existir, é criado copiando o config.json; o app só grava no config.local.json.
CONFIG_FILE = registro_erros.caminho_config_local()

# ==============================================================================
# DICIONÁRIO DE MATERIAIS PADRÃO
# ==============================================================================
MAPA_MATERIAIS = {
    '#ed3237': {'tipo': 'ACRILICO', 'nome_material': 'acrilico_padrão'},
    '#fff212': {'tipo': 'ACRILICO', 'nome_material': 'Acrilico_transparente'},
    '#d2ae6d': {'tipo': 'ACRILICO', 'nome_material': 'Acrilico_Dourado'},
    '#fefefe': {'tipo': 'MDF', 'nome_material': 'MDF_3mm'},
    '#e6e7e8': {'tipo': 'MDF', 'nome_material': 'MDF_6mm'},
    '#d2d3d5': {'tipo': 'MDF', 'nome_material': 'MDF_9mm'},
    '#373435': {'tipo': 'PLOTTER', 'nome_material': 'PLOTTER'},
    '#00afef': {'tipo': 'MDF_COSTAS', 'nome_material': 'MDF_Costas_3mm'},
    '#00a859': {'tipo': 'RESINA', 'nome_material': 'RESINA 3D'},
    '#f58634': {'tipo': 'BASE', 'nome_material': 'Base_3MM'},
    '#3e4095': {'tipo': 'BASE', 'nome_material': 'Base_6MM'},
    '#f7adaf': {'tipo': 'BASE', 'nome_material': 'Base_9MM'},
    '#84716b': {'tipo': 'BASE', 'nome_material': 'Base_12MM'},
    '#ec268f': {'tipo': 'ADESIVO', 'nome_material': 'Adesivo_Padrao'},
    '#9d98ca': {'tipo': 'ACRILICO_GRAVADO', 'nome_material': 'Acrilico_Gravado'}
}

# ==============================================================================
# FUNÇÕES DE EXTRAÇÃO SVG E MAPEAMENTO DO CATÁLOGO
# ==============================================================================
TAGS_PECAS = ['path', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line']
TAGS_DESCARTADAS = ['clipPath', 'mask']

def normalizar_cor(cor):
    # Mesma normalização do blender_engine: minúsculas, sem aspas/espaços e #abc vira #aabbcc
    if not cor or cor == 'none':
        return ''
    cor_limpa = cor.replace('"', '').replace("'", "").replace('\n', '').replace(' ', '').lower()
    if len(cor_limpa) == 4 and cor_limpa.startswith('#'):
        cor_limpa = f"#{cor_limpa[1]*2}{cor_limpa[2]*2}{cor_limpa[3]*2}"
    return cor_limpa

def obter_cor_contorno(elem):
    # Lê o contorno do mesmo jeito que o blender_engine (atributo stroke e style; sem CSS de classe)
    stroke = elem.attrib.get('stroke', None)
    style = elem.attrib.get('style', '')
    if style:
        m = re.search(r'stroke:\s*([^;]+)', style)
        if m and m.group(1) != 'none': stroke = m.group(1).strip()
    return normalizar_cor(stroke)

def identificar_material(cor_contorno):
    # Só vale a cor de contorno EXATA da tabela; qualquer outra é descartada pelo motor
    if not cor_contorno:
        return None
    return MAPA_MATERIAIS.get(cor_contorno)

def listar_pecas_svg(root):
    # Percorre as peças como o motor: o que está dentro de clipPath/mask é removido e não conta
    pecas = []
    def visitar(elem):
        for filho in list(elem):
            tag = filho.tag.split('}')[-1]
            if tag in TAGS_DESCARTADAS:
                continue
            if tag in TAGS_PECAS:
                pecas.append((tag, filho))
            visitar(filho)
    visitar(root)
    return pecas

def extrair_informacoes_svg(caminho_svg):
    if not os.path.exists(caminho_svg):
        return None

    try:
        tree = ET.parse(caminho_svg)
        root = tree.getroot()
    except Exception:
        return None

    materiais_qtd = {}
    pecas_descartadas = []

    vb = root.attrib.get('viewBox', '').split()
    vb_w = float(vb[2]) if len(vb) == 4 else 0.0
    vb_h = float(vb[3]) if len(vb) == 4 else 0.0

    width_str = root.attrib.get('width', '')
    if 'mm' in width_str and vb_w > 0:
        val_w = float(re.sub(r'[^\d.]', '', width_str))
        fator_mm = val_w / vb_w
    else:
        fator_mm = 0.1

    re_coords = re.compile(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?')

    TIPOS_CORPO_EXCLUSIVO = {'ACRILICO', 'ACRILICO_ESPELHADO', 'MDF'}
    pecas_isoladas = []

    for indice, (tag, elem) in enumerate(listar_pecas_svg(root), start=1):
        cor = obter_cor_contorno(elem)
        mat_info = identificar_material(cor)

        if mat_info:
            chave = (mat_info['tipo'], mat_info['nome_material'])
            materiais_qtd[chave] = materiais_qtd.get(chave, 0) + 1
        else:
            id_peca = elem.attrib.get('id') or f"{tag} nº {indice}"
            pecas_descartadas.append((id_peca, cor))

        eh_pagina = False
        if tag == 'rect' and vb_w > 0 and vb_h > 0:
            w = float(elem.attrib.get('width', 0))
            h = float(elem.attrib.get('height', 0))
            if abs(w - vb_w) < 5.0 or abs(h - vb_h) < 5.0:
                eh_pagina = True

        if mat_info and mat_info['tipo'] in TIPOS_CORPO_EXCLUSIVO and not eh_pagina:
            if tag == 'path':
                d = elem.attrib.get('d', '')
                if HAS_SVGPATH:
                    try:
                        path_obj = parse_path(d)
                        for sp in path_obj.continuous_subpaths():
                            xmin, xmax, ymin, ymax = sp.bbox()
                            w_mm = (xmax - xmin) * fator_mm
                            h_mm = (ymax - ymin) * fator_mm
                            larg = min(w_mm, h_mm)
                            alt = max(w_mm, h_mm)
                            if larg > 30.0 and alt > 30.0:
                                pecas_isoladas.append((larg, alt, mat_info['nome_material']))
                    except Exception:
                        pass
                else:
                    sub_str = re.split(r'(?=[Mm])', d)
                    for sp in sub_str:
                        if not sp.strip(): continue
                        coords = [float(v) for v in re_coords.findall(sp)]
                        if len(coords) >= 4:
                            xs, ys = coords[0::2], coords[1::2]
                            w_mm = (max(xs) - min(xs)) * fator_mm
                            h_mm = (max(ys) - min(ys)) * fator_mm
                            larg, alt = min(w_mm, h_mm), max(w_mm, h_mm)
                            if larg > 30.0 and alt > 30.0:
                                pecas_isoladas.append((larg, alt, mat_info['nome_material']))

            elif tag == 'rect':
                rw = float(elem.attrib.get('width', 0))
                rh = float(elem.attrib.get('height', 0))
                if rw > 0 and rh > 0:
                    w_mm, h_mm = rw * fator_mm, rh * fator_mm
                    larg, alt = min(w_mm, h_mm), max(w_mm, h_mm)
                    if larg > 30.0 and alt > 30.0:
                        pecas_isoladas.append((larg, alt, mat_info['nome_material']))

    if pecas_isoladas:
        pecas_isoladas.sort(key=lambda p: p[1], reverse=True)
        larg_mm, alt_mm, nome_fundo = pecas_isoladas[0]
    else:
        larg_mm, alt_mm, nome_fundo = 0.0, 0.0, "N/A"

    return {
        'nome_arquivo': os.path.basename(caminho_svg),
        'materiais_qtd': materiais_qtd,
        'largura_mm': larg_mm,
        'altura_mm': alt_mm,
        'largura_cm': larg_mm / 10.0,
        'altura_cm': alt_mm / 10.0,
        'nome_fundo': nome_fundo,
        'pecas_descartadas': pecas_descartadas
    }


def mapear_catalogo(caminho_catalogo):
    if not os.path.exists(caminho_catalogo):
        return None, "❌ Diretório do catálogo não foi encontrado."

    modalidades = {}
    try:
        itens_raiz = sorted(os.listdir(caminho_catalogo))
    except Exception as e:
        return None, f"❌ Erro ao acessar diretório: {e}"

    for item in itens_raiz:
        caminho_modalidade = os.path.join(caminho_catalogo, item)
        if os.path.isdir(caminho_modalidade):
            nome_modalidade = item.upper()
            pastas_prontas = []
            svg_count_total = 0

            try:
                modelos = sorted(os.listdir(caminho_modalidade))
                for modelo_cod in modelos:
                    caminho_modelo = os.path.join(caminho_modalidade, modelo_cod)
                    if os.path.isdir(caminho_modelo):
                        caminho_svg_dir = None
                        for sub in os.listdir(caminho_modelo):
                            if sub.upper() == "SVG" and os.path.isdir(os.path.join(caminho_modelo, sub)):
                                caminho_svg_dir = os.path.join(caminho_modelo, sub)
                                break
                        if caminho_svg_dir:
                            svgs = [f for f in os.listdir(caminho_svg_dir) if f.lower().endswith('.svg')]
                            qtd_svgs = len(svgs)
                            if qtd_svgs > 0:
                                svg_count_total += qtd_svgs
                                pastas_prontas.append(modelo_cod)
            except Exception:
                pass

            modalidades[nome_modalidade] = {
                'svg_count': svg_count_total,
                'pastas_prontas': pastas_prontas
            }

    return modalidades, "OK"


# ==============================================================================
# TEMA VISUAL (único lugar com cores, fontes e espaçamentos da interface)
# ==============================================================================
# Paleta original do app; só a forma de usar mudou.
TEMA = {
    'fundo':         '#0B0F17',  # fundo da janela e das telas
    'barra':         '#0F141C',  # barra superior
    'superficie':    '#121824',  # cartões, menu lateral, janela de configurações
    'campo':         '#080C14',  # campos, áreas de texto, trilho da barra, rodapé
    'elevado':       '#1E2638',  # botões secundários, item ativo, hover
    'divisor':       '#1A202C',  # bordas sutis e linhas divisórias
    'destaque':      '#38BDF8',  # ação principal, item ativo, progresso
    'marca':         '#4C9EEB',  # nome do app e hover da ação principal
    'sucesso':       '#34D399',  # concluído, saída dos relatórios
    'texto':         '#FFFFFF',  # texto principal
    'texto_suave':   '#A0AEC0',  # rótulos e texto secundário
    'texto_apagado': '#4A5568',  # dicas, legendas e itens inativos
}

# Grade de 8 px
ESPACO = {'xs': 4, 'p': 8, 'm': 16, 'g': 24, 'gg': 32, 'ggg': 40}

_FAMILIA_UI = "Segoe UI" if sys.platform.startswith("win") else "Helvetica"
_FAMILIA_MONO = "Consolas" if sys.platform.startswith("win") else "Courier"
FONTES = {
    'marca':      (_FAMILIA_UI, 14, "bold"),
    'titulo':     (_FAMILIA_UI, 16, "bold"),
    'secao':      (_FAMILIA_UI, 12, "bold"),
    'subtitulo':  (_FAMILIA_UI, 10),
    'corpo':      (_FAMILIA_UI, 10),
    'corpo_negrito': (_FAMILIA_UI, 10, "bold"),
    'rotulo':     (_FAMILIA_UI, 9, "bold"),
    'dica':       (_FAMILIA_UI, 8),
    'legenda':    (_FAMILIA_UI, 8, "bold"),
    'botao':      (_FAMILIA_UI, 10, "bold"),
    'icone':      (_FAMILIA_UI, 13),
    'passo':      (_FAMILIA_UI, 10, "bold"),
    'status':     (_FAMILIA_UI, 11, "bold"),
    'grande':     (_FAMILIA_UI, 32, "bold"),
    'nav':        (_FAMILIA_UI, 10, "normal"),
    'nav_ativo':  (_FAMILIA_UI, 10, "bold"),
    'mono':       (_FAMILIA_MONO, 9),
}

# Botões: cor normal e cor com o mouse em cima (fundo, texto)
BOTOES = {
    'principal':  {'bg': 'destaque', 'fg': 'fundo', 'bg_hover': 'marca', 'fg_hover': 'fundo'},
    'secundario': {'bg': 'elevado', 'fg': 'texto', 'bg_hover': 'elevado', 'fg_hover': 'destaque'},
    'sucesso':    {'bg': 'sucesso', 'fg': 'fundo', 'bg_hover': 'elevado', 'fg_hover': 'sucesso'},
    'icone':      {'bg': 'barra', 'fg': 'texto_suave', 'bg_hover': 'elevado', 'fg_hover': 'destaque'},
}


def aplicar_estilo(janela):
    """Tema ttk 'clam' na paleta do app e cores padrão dos menus suspensos."""
    estilo = ttk.Style(janela)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure("Cartao.TCheckbutton",
                     background=TEMA['superficie'], foreground=TEMA['texto_suave'],
                     font=FONTES['corpo'], focuscolor=TEMA['superficie'],
                     indicatorbackground=TEMA['campo'], indicatorforeground=TEMA['destaque'],
                     upperbordercolor=TEMA['texto_apagado'], lowerbordercolor=TEMA['texto_apagado'],
                     indicatormargin=(0, 0, ESPACO['p'], 0), padding=(0, ESPACO['xs']))
    estilo.map("Cartao.TCheckbutton",
               background=[("active", TEMA['superficie'])],
               foreground=[("disabled", TEMA['texto_apagado']), ("active", TEMA['texto']), ("selected", TEMA['texto'])],
               indicatorbackground=[("pressed", TEMA['elevado']), ("active", TEMA['elevado'])],
               upperbordercolor=[("selected", TEMA['destaque']), ("active", TEMA['destaque'])],
               lowerbordercolor=[("selected", TEMA['destaque']), ("active", TEMA['destaque'])])

    estilo.configure("Vertical.TScrollbar",
                     background=TEMA['elevado'], troughcolor=TEMA['campo'],
                     bordercolor=TEMA['campo'], lightcolor=TEMA['elevado'], darkcolor=TEMA['elevado'],
                     arrowcolor=TEMA['texto_suave'], gripcount=0, arrowsize=12)
    estilo.map("Vertical.TScrollbar",
               background=[("pressed", TEMA['destaque']), ("active", TEMA['elevado'])],
               arrowcolor=[("active", TEMA['destaque'])])

    # Menus dos campos de escolha (OptionMenu)
    janela.option_add("*Menu.background", TEMA['campo'])
    janela.option_add("*Menu.foreground", TEMA['texto'])
    janela.option_add("*Menu.activeBackground", TEMA['elevado'])
    janela.option_add("*Menu.activeForeground", TEMA['destaque'])
    janela.option_add("*Menu.relief", "flat")
    janela.option_add("*Menu.borderWidth", 0)
    janela.option_add("*Menu.font", FONTES['corpo'])


def criar_botao(pai, texto, comando, tipo="secundario", **extra):
    """Botão plano com estado de hover; 'principal' destaca a ação do passo."""
    cores = BOTOES[tipo]
    opcoes = dict(text=texto, command=comando, bd=0, relief="flat", cursor="hand2",
                  bg=TEMA[cores['bg']], fg=TEMA[cores['fg']],
                  activebackground=TEMA[cores['bg_hover']], activeforeground=TEMA[cores['fg_hover']],
                  disabledforeground=TEMA['texto_apagado'], highlightthickness=0,
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
    """Cartão com borda sutil; devolve (cartão, corpo). O corpo já tem o recuo interno."""
    cartao = tk.Frame(pai, bg=TEMA['superficie'], highlightthickness=1,
                      highlightbackground=TEMA['divisor'], highlightcolor=TEMA['divisor'])
    if titulo:
        cab = tk.Frame(cartao, bg=TEMA['superficie'])
        cab.pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['g'], 0))
        tk.Label(cab, text=titulo, fg=TEMA[cor_titulo], bg=TEMA['superficie'],
                 font=FONTES['secao'], anchor="w").pack(fill="x")
        if subtitulo:
            tk.Label(cab, text=subtitulo, fg=TEMA['texto_apagado'], bg=TEMA['superficie'],
                     font=FONTES['dica'], anchor="w", justify="left").pack(fill="x", pady=(2, 0))
        criar_divisor(cartao).pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['m'], 0))
    corpo = tk.Frame(cartao, bg=TEMA['superficie'])
    corpo.pack(fill="both", expand=True, padx=ESPACO['g'], pady=ESPACO['m'])
    return cartao, corpo


def criar_divisor(pai):
    return tk.Frame(pai, bg=TEMA['divisor'], height=1)


def criar_legenda(pai, texto, bg='superficie'):
    """Legenda de seção em caixa alta (ex.: ARQUIVO, ACABAMENTO)."""
    return tk.Label(pai, text=texto.upper(), fg=TEMA['texto_apagado'], bg=TEMA[bg],
                    font=FONTES['legenda'], anchor="w")


def criar_entrada(pai, variavel, **extra):
    """Campo de texto plano com borda que acende no foco."""
    opcoes = dict(textvariable=variavel, bg=TEMA['campo'], fg=TEMA['texto'],
                  insertbackground=TEMA['texto'], relief="flat", bd=0, font=FONTES['corpo'],
                  highlightthickness=1, highlightbackground=TEMA['divisor'], highlightcolor=TEMA['destaque'],
                  selectbackground=TEMA['elevado'], selectforeground=TEMA['texto'])
    opcoes.update(extra)
    return tk.Entry(pai, **opcoes)


def estilizar_optionmenu(menu_opcoes):
    menu_opcoes.config(bg=TEMA['campo'], fg=TEMA['texto'], activebackground=TEMA['elevado'],
                       activeforeground=TEMA['texto'], bd=0, relief="flat", highlightthickness=1,
                       highlightbackground=TEMA['divisor'], font=FONTES['corpo'], anchor="w",
                       padx=ESPACO['p'], pady=ESPACO['xs'], cursor="hand2")
    menu_opcoes["menu"].config(bg=TEMA['campo'], fg=TEMA['texto'], activebackground=TEMA['elevado'],
                               activeforeground=TEMA['destaque'], bd=0, font=FONTES['corpo'])


def criar_area_texto(pai):
    """Área de saída/log: fonte mono, com barra de rolagem. Devolve (moldura, texto)."""
    moldura = tk.Frame(pai, bg=TEMA['campo'], highlightthickness=1,
                       highlightbackground=TEMA['divisor'], highlightcolor=TEMA['divisor'])
    texto = tk.Text(moldura, bg=TEMA['campo'], fg=TEMA['sucesso'], font=FONTES['mono'], bd=0,
                    relief="flat", padx=ESPACO['m'], pady=ESPACO['m'], highlightthickness=0,
                    insertbackground=TEMA['texto'], selectbackground=TEMA['elevado'],
                    selectforeground=TEMA['texto'], spacing1=1, spacing3=1)
    rolagem = ttk.Scrollbar(moldura, orient="vertical", command=texto.yview)
    texto.configure(yscrollcommand=rolagem.set)
    rolagem.pack(side="right", fill="y")
    texto.pack(side="left", fill="both", expand=True)
    return moldura, texto


def criar_cabecalho_tela(pai, titulo, subtitulo):
    """Título e subtítulo no topo de cada tela."""
    cab = tk.Frame(pai, bg=TEMA['fundo'])
    tk.Label(cab, text=titulo, fg=TEMA['texto'], bg=TEMA['fundo'], font=FONTES['titulo'], anchor="w").pack(fill="x")
    tk.Label(cab, text=subtitulo, fg=TEMA['texto_suave'], bg=TEMA['fundo'], font=FONTES['subtitulo'], anchor="w").pack(fill="x", pady=(2, 0))
    return cab


# ==============================================================================
# JANELAS DA INTERFACE
# ==============================================================================
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configurações do Sistema")
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
        arquivos_blend = [arq for arq in os.listdir(pasta) if arq.lower().endswith(".blend")] if pasta and os.path.exists(pasta) else []
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
        try:
            self.parent_app.cycles_samples = int(self.cycles_samples_var.get())
        except ValueError:
            self.parent_app.cycles_samples = 128
        self.parent_app.salvar_configuracoes_disco()
        if hasattr(self.parent_app, "_atualizar_hud_resina"):
            self.parent_app._atualizar_hud_resina()
        messagebox.showinfo("Sucesso", "Configurações salvas permanentemente!", parent=self)
        self.destroy()


class VectorConvertProApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VectorConvert Pro")
        self.geometry("1150x820")
        self.minsize(980, 700)
        self.configure(bg=TEMA['fundo'])
        aplicar_estilo(self)

        # Configurações Padrão
        self.blender_path = r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
        self.output_path = os.path.join(os.getcwd(), "imagens")
        self.resina_dir = os.path.join(os.getcwd(), "resina_models")
        self.blend_dir = os.getcwd()
        self.catalogo_dir = r"F:\Backup Aroni 29-05-2021\Publico\2026\CATALOGO"
        self.selected_blend = ""
        self.svg_selecionado = ""
        self.cycles_samples = 128

        self.carregar_configuracoes_disco()

        if not os.path.exists(self.resina_dir):
            os.makedirs(self.resina_dir)

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
        self.main_container.grid(row=1, column=1, sticky="nsew", padx=ESPACO['gg'], pady=ESPACO['g'])
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self._build_upload_screen()
        self._build_processing_screen()
        self._build_download_screen()
        self._build_catalogo_screen()

        self._build_footer()
        self._show_screen("upload")

    def carregar_configuracoes_disco(self):
        try:
            registro_erros.garantir_config_local(os.path.dirname(CONFIG_FILE))
        except OSError as e:
            print(f"Erro ao criar o {registro_erros.ARQUIVO_CONFIG_LOCAL}: {e}")
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    self.blender_path = dados.get("blender_path", self.blender_path)
                    self.resina_dir = dados.get("resina_dir", self.resina_dir)
                    self.blend_dir = dados.get("blend_dir", self.blend_dir)
                    self.catalogo_dir = dados.get("catalogo_dir", self.catalogo_dir)
                    self.selected_blend = dados.get("selected_blend", self.selected_blend)
                    self.cycles_samples = int(dados.get("cycles_samples", self.cycles_samples))
            except Exception as e:
                print(f"Erro ao carregar configurações: {e}")

    def salvar_configuracoes_disco(self):
        dados = {
            "blender_path": self.blender_path,
            "resina_dir": self.resina_dir,
            "blend_dir": self.blend_dir,
            "catalogo_dir": self.catalogo_dir,
            "selected_blend": self.selected_blend,
            "cycles_samples": self.cycles_samples
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar configurações no disco: {e}")

    def _obter_cameras_selecionadas_str(self):
        cams = []
        if self.cam_principal_var.get(): cams.append("Camera_Principal")
        if self.cam_esquerda_var.get(): cams.append("Camera_Esquerda")
        if self.cam_direita_var.get(): cams.append("Camera_Direita")
        return ",".join(cams)

    def _build_navbar(self):
        navbar = tk.Frame(self, bg=TEMA['barra'], height=56, padx=ESPACO['g'], pady=ESPACO['p'])
        navbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(navbar, text="VectorConvert Pro", fg=TEMA['marca'], bg=TEMA['barra'], font=FONTES['marca']).pack(side="left")
        tk.Label(navbar, text="SVG → 3D", fg=TEMA['texto_apagado'], bg=TEMA['barra'], font=FONTES['rotulo']).pack(side="left", padx=(ESPACO['p'], 0), pady=(ESPACO['xs'], 0))

        right_icons_frame = tk.Frame(navbar, bg=TEMA['barra'])
        right_icons_frame.pack(side="right")
        criar_botao(right_icons_frame, "⚙", lambda: SettingsWindow(self), "icone",
                    font=FONTES['icone'], padx=ESPACO['p'], pady=0).pack(side="left")
        # Linha sutil separando a barra do conteúdo
        tk.Frame(self, bg=TEMA['divisor'], height=1).grid(row=0, column=0, columnspan=2, sticky="sew")

    def _build_sidebar(self):
        sidebar = tk.Frame(self, bg=TEMA['superficie'], width=220)
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.pack_propagate(False)
        # Borda direita sutil
        tk.Frame(sidebar, bg=TEMA['divisor'], width=1).pack(side="right", fill="y")

        header_frame = tk.Frame(sidebar, bg=TEMA['superficie'], pady=ESPACO['g'], padx=ESPACO['g'])
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="SVG Converter", fg=TEMA['texto'], bg=TEMA['superficie'], font=FONTES['secao'], anchor="w").pack(fill="x")
        tk.Label(header_frame, text="HIGH PRECISION TOOL", fg=TEMA['texto_apagado'], bg=TEMA['superficie'], font=FONTES['legenda'], anchor="w").pack(fill="x", pady=(2, 0))
        criar_divisor(sidebar).pack(fill="x", padx=ESPACO['m'])
        criar_legenda(sidebar, "Navegação").pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['m'], ESPACO['p']))

        menu_items = {
            "upload": " Upload",
            "processing": " Processing",
            "download": " Download",
            "catalogo": " 📊 Catálogo"
        }
        for key, text in menu_items.items():
            btn = tk.Button(sidebar, text=text, fg=TEMA['texto_suave'], bg=TEMA['superficie'], bd=0, relief="flat",
                            anchor="w", padx=ESPACO['m'], pady=ESPACO['p'] + 2, font=FONTES['nav'], cursor="hand2",
                            activebackground=TEMA['elevado'], activeforeground=TEMA['destaque'], highlightthickness=0,
                            command=lambda k=key: self._show_screen(k))
            btn.pack(fill="x", padx=ESPACO['p'], pady=2)
            # Hover só nos itens inativos (o ativo fica com o texto em destaque)
            btn.bind("<Enter>", lambda _e, b=btn: b.cget("fg") != TEMA['destaque'] and b.configure(bg=TEMA['elevado'], fg=TEMA['texto']))
            btn.bind("<Leave>", lambda _e, b=btn: b.cget("fg") != TEMA['destaque'] and b.configure(bg=TEMA['superficie'], fg=TEMA['texto_suave']))
            self.sidebar_buttons[key] = btn

    def _show_screen(self, screen_key):
        for key, btn in self.sidebar_buttons.items():
            if key == screen_key:
                btn.configure(bg=TEMA['elevado'], fg=TEMA['destaque'], font=FONTES['nav_ativo'])
            else:
                btn.configure(bg=TEMA['superficie'], fg=TEMA['texto_suave'], font=FONTES['nav'])

        if screen_key == "catalogo":
            self._atualizar_relatorio_catalogo()

        self.screens[screen_key].tkraise()

    def _create_stepper(self, parent, active_step):
        stepper_frame = tk.Frame(parent, bg=TEMA['fundo'])
        stepper_frame.pack(fill="x", pady=(0, ESPACO['g']))

        steps = [("1", "UPLOAD"), ("2", "PROCESSING"), ("3", "DOWNLOAD")]
        stepper_inner = tk.Frame(stepper_frame, bg=TEMA['fundo'])
        stepper_inner.pack(anchor="center")

        for idx, (num, label) in enumerate(steps, start=1):
            if idx > 1:
                # Linha ligando os passos: acesa até o passo atual
                cor_linha = TEMA['destaque'] if idx <= active_step else TEMA['elevado']
                tk.Frame(stepper_inner, bg=cor_linha, width=72, height=2).pack(side="left", anchor="n", pady=(13, 0))
            step_item = tk.Frame(stepper_inner, bg=TEMA['fundo'])
            step_item.pack(side="left", padx=ESPACO['m'])
            completed = idx <= active_step
            atual = idx == active_step
            circle_color = TEMA['destaque'] if completed else TEMA['elevado']
            symbol_color = TEMA['fundo'] if completed else TEMA['texto_apagado']
            text_color = TEMA['texto'] if atual else (TEMA['texto_suave'] if completed else TEMA['texto_apagado'])
            symbol = "✓" if idx < active_step else num

            tk.Label(step_item, text=symbol, fg=symbol_color, bg=circle_color, width=3, height=1, font=FONTES['passo']).pack()
            tk.Label(step_item, text=label, fg=text_color, bg=TEMA['fundo'], font=FONTES['legenda']).pack(pady=(ESPACO['xs'], 0))

    def _atualizar_hud_resina(self):
        menu = self.menu_resina["menu"]
        menu.delete(0, "end")
        arquivos = [f for f in os.listdir(self.resina_dir) if f.lower().endswith(('.obj', '.fbx', '.stl', '.blend'))] if os.path.exists(self.resina_dir) else []
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
        # Duas colunas de mesma largura que acompanham o redimensionamento
        main_frame.grid_columnconfigure(0, weight=1, uniform="colunas")
        main_frame.grid_columnconfigure(1, weight=1, uniform="colunas")
        main_frame.grid_rowconfigure(0, weight=1)

        # Lado Esquerdo: Formulário de Upload e Opções
        card_left, corpo_left = criar_cartao(main_frame, "Upload e Parâmetros do SVG")
        card_left.grid(row=0, column=0, sticky="nsew", padx=(0, ESPACO['p']))

        # Seção: arquivo
        criar_legenda(corpo_left, "Arquivo").pack(fill="x", pady=(0, ESPACO['p']))
        zona_arquivo = tk.Frame(corpo_left, bg=TEMA['campo'], highlightthickness=1, highlightbackground=TEMA['divisor'])
        zona_arquivo.pack(fill="x")
        self.lbl_arquivo_selecionado = tk.Label(zona_arquivo, text="Nenhum arquivo selecionado", fg=TEMA['texto_suave'], bg=TEMA['campo'], font=FONTES['corpo'], anchor="w")
        self.lbl_arquivo_selecionado.pack(side="left", fill="x", expand=True, padx=ESPACO['m'], pady=ESPACO['m'])

        btn_select = criar_botao(zona_arquivo, "Selecionar Arquivo SVG", self._selecionar_svg, "secundario")
        btn_select.pack(side="right", padx=ESPACO['p'], pady=ESPACO['p'])

        # Seção: renderização
        criar_legenda(corpo_left, "Renderização").pack(fill="x", pady=(ESPACO['g'], ESPACO['xs']))
        chk_render = ttk.Checkbutton(corpo_left, text="Renderizar automaticamente no Blender", variable=self.render_auto_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_render.pack(anchor="w")

        # SELEÇÃO DAS CÂMERAS
        frame_cams = tk.Frame(corpo_left, bg=sup)
        frame_cams.pack(fill="x", pady=(ESPACO['p'], 0))
        tk.Label(frame_cams, text="📷 Câmeras a Renderizar:", fg=TEMA['destaque'], bg=sup, font=FONTES['rotulo']).pack(anchor="w", pady=(0, 2))

        sub_cams = tk.Frame(frame_cams, bg=sup)
        sub_cams.pack(anchor="w")

        chk_cam_p = ttk.Checkbutton(sub_cams, text="Principal", variable=self.cam_principal_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_cam_p.pack(side="left", padx=(0, ESPACO['m']))

        chk_cam_e = ttk.Checkbutton(sub_cams, text="Esquerda", variable=self.cam_esquerda_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_cam_e.pack(side="left", padx=(0, ESPACO['m']))

        chk_cam_d = ttk.Checkbutton(sub_cams, text="Direita", variable=self.cam_direita_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_cam_d.pack(side="left")

        # Seção: acabamento
        criar_legenda(corpo_left, "Acabamento").pack(fill="x", pady=(ESPACO['g'], ESPACO['xs']))
        chk_textura = ttk.Checkbutton(corpo_left, text="Aplicar texturas (madeira no MDF)", variable=self.usar_textura_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_textura.pack(anchor="w")

        chk_verniz = ttk.Checkbutton(corpo_left, text="Aplicar Verniz na madeira", variable=self.usar_verniz_var, style="Cartao.TCheckbutton", cursor="hand2")
        chk_verniz.pack(anchor="w")

        frame_resina = tk.Frame(corpo_left, bg=sup)
        frame_resina.pack(fill="x", pady=(ESPACO['m'], 0))
        tk.Label(frame_resina, text="💎 Modelo 3D de Resina para Encaixe:", fg=TEMA['destaque'], bg=sup, font=FONTES['rotulo']).pack(anchor="w", pady=(0, ESPACO['xs']))
        self.menu_resina = tk.OptionMenu(frame_resina, self.modelo_resina_selecionado, "")
        estilizar_optionmenu(self.menu_resina)
        self.menu_resina.pack(fill="x")
        self._atualizar_hud_resina()

        # Botão Próximo (ação principal do passo, no rodapé do cartão)
        rodape_left = tk.Frame(corpo_left, bg=sup)
        rodape_left.pack(side="bottom", fill="x")
        criar_divisor(rodape_left).pack(fill="x", pady=(ESPACO['m'], ESPACO['m']))
        btn_proximo = criar_botao(rodape_left, "Próximo ➔", self._avancar_para_processamento, "principal",
                                  padx=ESPACO['g'], pady=ESPACO['p'] + 2)
        btn_proximo.pack(side="right")

        # Lado Direito: Card de Análise Rápida do SVG
        card_right, corpo_right = criar_cartao(main_frame, "📊 Análise Estrutural do SVG",
                                               "Materiais, quantidades e medidas lidas do arquivo.", cor_titulo='destaque')
        card_right.grid(row=0, column=1, sticky="nsew", padx=(ESPACO['p'], 0))

        moldura_analise, self.txt_analise_svg = criar_area_texto(corpo_right)
        moldura_analise.pack(fill="both", expand=True)
        self.txt_analise_svg.insert("1.0", "Aguardando seleção de arquivo SVG...")
        self.txt_analise_svg.configure(state="disabled")

    def _selecionar_svg(self):
        file_path = filedialog.askopenfilename(title="Selecionar SVG", filetypes=[("Arquivos SVG", "*.svg"), ("Todos", "*.*")])
        if file_path:
            self.svg_selecionado = file_path
            self.lbl_arquivo_selecionado.configure(text=os.path.basename(file_path), fg="#34D399")
            
            diretorio_svg = os.path.dirname(file_path)
            self.output_path = os.path.join(diretorio_svg, "imagens 3d")
            if not os.path.exists(self.output_path):
                os.makedirs(self.output_path)

            self._analisar_e_exibir_svg(file_path)

    def _avancar_para_processamento(self):
        if not self.svg_selecionado or not os.path.exists(self.svg_selecionado):
            messagebox.showwarning("Atenção", "Por favor, selecione um arquivo SVG antes de prosseguir.")
            return

        if self.render_auto_var.get() and not (self.cam_principal_var.get() or self.cam_esquerda_var.get() or self.cam_direita_var.get()):
            messagebox.showwarning("Atenção", "Por favor, selecione pelo menos uma câmera para renderizar.")
            return

        self.lbl_status_processamento.configure(text="🔄 Iniciando importação e montagem de malhas...")
        for widget in self.frame_historico.winfo_children():
            widget.destroy()
            
        self._show_screen("processing")
        self._iniciar_processamento_background()

    def _analisar_e_exibir_svg(self, caminho_svg):
        info = extrair_informacoes_svg(caminho_svg)
        self.txt_analise_svg.configure(state="normal")
        self.txt_analise_svg.delete("1.0", "end")

        if info:
            resumo = f"📁 ARQUIVO: {info['nome_arquivo']}\n"
            resumo += "─" * 40 + "\n"
            resumo += "📦 MATERIAIS & QUANTIDADES:\n"
            for (tipo, nome), qtd in info['materiais_qtd'].items():
                resumo += f" • [{tipo:<12}] {nome:<22} : {qtd}\n"
            resumo += "─" * 40 + "\n"
            resumo += f"📐 DIMENSÃO DO TROFÉU:\n"
            resumo += f" • Fundo    : {info['nome_fundo']}\n"
            resumo += f" • Largura  : {info['largura_mm']:.2f} mm ({info['largura_cm']:.2f} cm)\n"
            resumo += f" • Altura   : {info['altura_mm']:.2f} mm ({info['altura_cm']:.2f} cm)\n"
            if info['pecas_descartadas']:
                resumo += "─" * 40 + "\n"
                resumo += f"⚠️ PEÇAS QUE NÃO SERÃO CONVERTIDAS: {len(info['pecas_descartadas'])}\n"
            self.txt_analise_svg.insert("1.0", resumo)
        else:
            self.txt_analise_svg.insert("1.0", "❌ Não foi possível extrair dados estruturais do SVG.")

        self.txt_analise_svg.configure(state="disabled")

        if info and info['pecas_descartadas']:
            self._avisar_pecas_descartadas(info['pecas_descartadas'])

    def _avisar_pecas_descartadas(self, pecas_descartadas):
        por_cor = {}
        for id_peca, cor in pecas_descartadas:
            chave = cor if cor else "sem contorno"
            por_cor.setdefault(chave, []).append(id_peca)

        linhas = []
        for cor, ids in por_cor.items():
            ids_txt = ", ".join(ids[:8])
            if len(ids) > 8:
                ids_txt += f" (+{len(ids) - 8})"
            linhas.append(f" • {cor}: {len(ids)} peça(s) — {ids_txt}")

        mensagem = (f"{len(pecas_descartadas)} peça(s) deste SVG têm cor de contorno fora da tabela de materiais "
                    "(ou não têm contorno) e NÃO serão convertidas: vão sumir do 3D.\n\n")
        mensagem += "\n".join(linhas)
        mensagem += "\n\nSó a cor de contorno exata da tabela de materiais é aceita."
        messagebox.showwarning("Atenção: cores fora da tabela", mensagem)

    def _build_catalogo_screen(self):
        sup = TEMA['superficie']
        screen = tk.Frame(self.main_container, bg=TEMA['fundo'])
        screen.grid(row=0, column=0, sticky="nsew")
        self.screens["catalogo"] = screen

        card = tk.Frame(screen, bg=sup, highlightthickness=1, highlightbackground=TEMA['divisor'])
        card.pack(fill="both", expand=True)

        header = tk.Frame(card, bg=sup)
        header.pack(fill="x", padx=ESPACO['g'], pady=(ESPACO['g'], ESPACO['m']))

        titulos = tk.Frame(header, bg=sup)
        titulos.pack(side="left", fill="x", expand=True)
        tk.Label(titulos, text="📊 Mapeamento do Catálogo de Troféus", fg=TEMA['destaque'], bg=sup, font=FONTES['titulo'], anchor="w").pack(fill="x")
        tk.Label(titulos, text="Modalidades e modelos do catálogo que já têm SVG pronto.", fg=TEMA['texto_suave'], bg=sup, font=FONTES['subtitulo'], anchor="w").pack(fill="x", pady=(2, 0))
        criar_botao(header, "🔄 Atualizar Catálogo", self._atualizar_relatorio_catalogo, "secundario").pack(side="right", anchor="n")

        criar_divisor(card).pack(fill="x", padx=ESPACO['g'])
        moldura_catalogo, self.txt_catalogo = criar_area_texto(card)
        moldura_catalogo.pack(fill="both", expand=True, padx=ESPACO['g'], pady=ESPACO['g'])

    def _atualizar_relatorio_catalogo(self):
        modalidades, status = mapear_catalogo(self.catalogo_dir)
        self.txt_catalogo.configure(state="normal")
        self.txt_catalogo.delete("1.0", "end")

        if not modalidades:
            self.txt_catalogo.insert("1.0", f"{status}\nCaminho configurado: {self.catalogo_dir}")
            self.txt_catalogo.configure(state="disabled")
            return

        relatorio = ""
        totais_por_modalidade = {}
        total_geral_trofeus = 0

        for mod, dados in modalidades.items():
            svg_count = dados['svg_count']
            pastas = dados['pastas_prontas']
            pronto = svg_count > 0

            status_str = "✓ Pronto" if pronto else "✗ Não pronto"
            if pronto:
                pastas_str = ", ".join(pastas)
                totais_por_modalidade[mod] = len(pastas)
                total_geral_trofeus += len(pastas)
            else:
                pastas_str = "—"

            pastas_formatadas = textwrap.fill(f"Pastas Prontas: {pastas_str}", width=80, subsequent_indent="     ")

            relatorio += f"Modalidade: {mod}\n"
            relatorio += f"Status: {status_str}\n"
            relatorio += f"SVG Count: {svg_count}\n"
            relatorio += f"{pastas_formatadas}\n"
            relatorio += "────────────────────────────────────────\n"

        relatorio += "📈 Totais\n"
        relatorio += f"- Total pronto para catalogar: {total_geral_trofeus} troféus\n"
        for mod, qtd in totais_por_modalidade.items():
            relatorio += f"- {mod}: {qtd}\n"

        relatorio += "\n📝 Observações\n"
        relatorio += "- O critério de \"pronto\" é a presença de pelo menos um arquivo .svg em alguma subpasta\n"
        relatorio += "- Todos os relatórios padronizam em Português Brasileiro (PT-BR)\n"

        relatorio += "\n📁 Diretório do Catálogo\n"
        relatorio += f"{self.catalogo_dir}\n"

        self.txt_catalogo.insert("1.0", relatorio)
        self.txt_catalogo.configure(state="disabled")

    def _iniciar_processamento_background(self):
        threading.Thread(target=self._executar_blender_subprocess, daemon=True).start()

    def atualizar_amostras_camera_ui(self, atual, total, faltam, porcentagem, nome_cam):
        self.lbl_status_processamento.configure(text=f"📷 Renderizando: {nome_cam}")
        self.lbl_samples_info.configure(text=f"[{nome_cam}] Samples: {atual} / {total}  |  Faltam: {faltam}")
        self.atualizar_barra_progresso(porcentagem)

    def _executar_blender_subprocess(self):
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_engine = os.path.join(diretorio_atual, "blender_engine.py")

        caminho_blend_escolhido = ""
        if self.blend_dir and self.selected_blend and not self.selected_blend.startswith("Nenhum"):
            caminho_blend_escolhido = os.path.join(self.blend_dir, self.selected_blend)

        resina_escolhida = self.modelo_resina_selecionado.get()
        caminho_resina_completo = ""
        if resina_escolhida and not resina_escolhida.startswith("Nenhum"):
            caminho_resina_completo = os.path.join(self.resina_dir, resina_escolhida)

        cams_str = self._obter_cameras_selecionadas_str()

        comando = [self.blender_path]

        if self.render_auto_var.get():
            comando.append("--background")

        comando.extend([
            "--python", caminho_engine,
            "--",
            self.svg_selecionado,
            self.output_path,
            caminho_blend_escolhido,
            str(self.render_auto_var.get()),
            str(self.usar_textura_var.get()),
            str(self.cycles_samples),
            str(self.usar_verniz_var.get()),
            caminho_resina_completo,
            cams_str
        ])

        try:
            processo = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore')
            ultimas_linhas = collections.deque(maxlen=200)   # para o log de erro
            teve_traceback = False
            for linha in processo.stdout:
                linha_limpa = linha.strip()
                ultimas_linhas.append(linha.rstrip("\r\n"))
                if linha_limpa.startswith("Traceback (most recent call last)") or linha_limpa.startswith("Error: Python:"):
                    teve_traceback = True
                if "Carregando estúdio base" in linha_limpa:
                    self.after(0, lambda: self.lbl_status_processamento.configure(text="📂 Abrindo arquivo de estúdio base..."))
                elif "Analisando e importando" in linha_limpa:
                    self.after(0, lambda: self.adicionar_passo_concluido("✔ Estúdio carregado com sucesso!", "📐 Lendo dados do arquivo SVG..."))
                elif "Convertendo curvas" in linha_limpa:
                    self.after(0, lambda: self.adicionar_passo_concluido("✔ SVG importado com sucesso!", "⚙ Convertendo curvas e montando camadas..."))
                elif "Aplicando materiais" in linha_limpa:
                    self.after(0, lambda: self.adicionar_passo_concluido("✔ Malhas 3D montadas!", "🎨 Aplicando MDF, Acrílico e Texturas..."))
                elif "Renderizando câmera:" in linha_limpa:
                    cam_nome = linha_limpa.split("Renderizando câmera:")[-1].split("via")[0].strip()
                    self.after(0, lambda c=cam_nome: self.adicionar_passo_concluido("✔ Materiais aplicados com sucesso!", f"📷 Renderizando Câmera {c}..."))
                elif "[SAMPLE_PROGRESS]" in linha_limpa:
                    try:
                        parte_dados, parte_cam = linha_limpa.split("|CAM:")
                        amostras_str = parte_dados.split(" ")[1]
                        atual, total = map(int, amostras_str.split("/"))
                        porcentagem = (atual / total) * 100
                        faltam = total - atual
                        nome_cam_atual = parte_cam.strip()
                        self.after(0, lambda a=atual, t=total, f=faltam, p=porcentagem, c=nome_cam_atual: self.atualizar_amostras_camera_ui(a, t, f, p, c))
                    except Exception:
                        pass
                elif "Renders salvos em:" in linha_limpa or "Modo interativo ativo" in linha_limpa:
                    self.after(0, lambda: self.adicionar_passo_concluido("✔ Todas as imagens renderizadas!", "✅ Finalizando processo..."))

            processo.wait()
            if processo.returncode != 0 or teve_traceback:
                registro_erros.gravar_log(
                    "app_ui (Blender)",
                    f"Blender terminou com código {processo.returncode}" + (" e com erro de Python" if teve_traceback else ""),
                    "Comando: " + " ".join(f'"{c}"' for c in comando) + "\n\nÚltimas linhas do Blender:\n" + "\n".join(ultimas_linhas))
            self.after(0, lambda: self.tag_concluido())
        except Exception as e:
            registro_erros.gravar_log("app_ui (Blender)", f"Não foi possível rodar o Blender: {e}",
                                      "Comando: " + " ".join(f'"{c}"' for c in comando) + "\n\n" + traceback.format_exc())
            messagebox.showerror("Erro Crítico", f"Não foi possível rodar o Blender:\n{e}")

    def atualizar_barra_progresso(self, porcentagem):
        largura_atual = self.canvas_barra.winfo_width()
        if largura_atual < 10:
            largura_atual = 440
        largura_preenchimento = (porcentagem / 100.0) * largura_atual
        self.canvas_barra.coords(self.retangulo_progresso, 0, 0, largura_preenchimento, 16)
        self.lbl_porcentagem.configure(text=f"{int(porcentagem)}%")

    def adicionar_passo_concluido(self, texto_concluido, novo_status):
        lbl_hist = tk.Label(self.frame_historico, text=texto_concluido, fg="#34D399", bg="#121824", font=("Helvetica", 9, "bold"), anchor="w")
        lbl_hist.pack(fill="x", pady=2)
        self.lbl_status_processamento.configure(text=novo_status)

    def tag_concluido(self):
        self.lbl_status_processamento.configure(text="✅ Processamento Concluído!")
        self.atualizar_barra_progresso(100)
        self.lbl_samples_info.configure(text="Renderização Finalizada (100% Concluído)")
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

        # Trilho da barra com borda sutil de 1 px
        f_bar_bg = tk.Frame(frame_progresso_container, bg=TEMA['divisor'], padx=1, pady=1)
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

        tk.Label(centro, text="✓", fg=TEMA['fundo'], bg=TEMA['sucesso'], font=FONTES['grande'], width=2).pack(pady=(0, ESPACO['g']))
        tk.Label(centro, text="Processamento Concluído!", fg=TEMA['sucesso'], bg=sup, font=FONTES['titulo']).pack()
        tk.Label(centro, text="Abra a pasta para ver as imagens e os arquivos gerados.", fg=TEMA['texto_suave'], bg=sup, font=FONTES['subtitulo']).pack(pady=(ESPACO['xs'], 0))
        criar_botao(centro, "Abrir Pasta de Imagens / Arquivos", lambda: os.startfile(self.output_path) if os.path.exists(self.output_path) else None, "sucesso",
                    padx=ESPACO['g'], pady=ESPACO['p'] + 2).pack(pady=(ESPACO['g'], 0))

    def _build_footer(self):
        footer = tk.Frame(self, bg=TEMA['campo'], height=32, padx=ESPACO['g'])
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        tk.Frame(self, bg=TEMA['divisor'], height=1).grid(row=2, column=0, columnspan=2, sticky="new")
        tk.Label(footer, text="© 2026 VectorConvert Pro. All rights reserved.", fg=TEMA['texto_apagado'], bg=TEMA['campo'], font=FONTES['dica']).pack(side="left", pady=ESPACO['p'])


if __name__ == "__main__":
    registro_erros.instalar_ganchos("app_ui")
    app = VectorConvertProApp()
    app.report_callback_exception = registro_erros.gancho_tk("app_ui")
    app.mainloop()