"""Lógica do PathToMesh, sem interface (usada pela interface web, app_web.py, e pela reserva em
Tkinter, app_ui.py).

- Tabela de materiais (MAPA_MATERIAIS) e leitura do SVG: as mesmas funções que ficavam no app_ui.py,
  movidas para cá sem mudar nada (as cores aceitas, o aviso de peças fora da tabela e as medidas).
- Mapeamento do catálogo e o texto do relatório do catálogo.
- Configuração do usuário (config.local.json): EstadoApp, com os valores padrão, carregar e salvar.
- Blender: monta o comando, lê a saída linha a linha (etapas e progresso dos samples) e grava o
  log de erro quando o Blender falha.

Não importa tkinter, webview nem bpy: dá para testar sem janela.
"""
import os
import re
import json
import subprocess
import textwrap
import collections
import traceback
import xml.etree.ElementTree as ET

import registro_erros

try:
    from svgpathtools import parse_path
    HAS_SVGPATH = True
except ImportError:
    HAS_SVGPATH = False

# A configuração do usuário fica no config.local.json (no .gitignore, nunca vai para o GitHub).
# Se ele não existir, é criado copiando o config.json antigo (se ainda houver) ou o
# config.exemplo.json; o app só grava no config.local.json.
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
# TEXTOS DOS RELATÓRIOS E AVISOS (os mesmos nas duas interfaces)
# ==============================================================================
TEXTO_AGUARDANDO_SVG = "Aguardando seleção de arquivo SVG..."
TEXTO_ERRO_SVG = "❌ Não foi possível extrair dados estruturais do SVG."


def montar_resumo_svg(info):
    """Texto da análise do SVG (o painel da direita da tela Upload)."""
    if info:
        resumo = f"📁 ARQUIVO: {info['nome_arquivo']}\n"
        resumo += "─" * 40 + "\n"
        resumo += "📦 MATERIAIS & QUANTIDADES:\n"
        for (tipo, nome), qtd in info['materiais_qtd'].items():
            resumo += f" • [{tipo:<12}] {nome:<22} : {qtd}\n"
        resumo += "─" * 40 + "\n"
        resumo += "📐 DIMENSÃO DO TROFÉU:\n"
        resumo += f" • Fundo    : {info['nome_fundo']}\n"
        resumo += f" • Largura  : {info['largura_mm']:.2f} mm ({info['largura_cm']:.2f} cm)\n"
        resumo += f" • Altura   : {info['altura_mm']:.2f} mm ({info['altura_cm']:.2f} cm)\n"
        if info['pecas_descartadas']:
            resumo += "─" * 40 + "\n"
            resumo += f"⚠️ PEÇAS QUE NÃO SERÃO CONVERTIDAS: {len(info['pecas_descartadas'])}\n"
        return resumo
    return TEXTO_ERRO_SVG


TITULO_AVISO_DESCARTADAS = "Atenção: cores fora da tabela"


def montar_aviso_descartadas(pecas_descartadas):
    """Mensagem do aviso de peças com cor de contorno fora da tabela (agrupadas por cor)."""
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
    return mensagem


def montar_relatorio_catalogo(modalidades, status, catalogo_dir):
    """Texto da tela Catálogo."""
    if not modalidades:
        return f"{status}\nCaminho configurado: {catalogo_dir}"

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
    relatorio += f"{catalogo_dir}\n"
    return relatorio


# ==============================================================================
# CONFIGURAÇÃO, LISTAS E VALIDAÇÃO
# ==============================================================================
class EstadoApp:
    """Configuração do usuário e o SVG escolhido. A janela do Tkinter herda daqui; a interface
    web usa um objeto desta classe."""

    def definir_padroes(self):
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


def ler_samples(texto):
    """Samples digitados nas configurações; se não for um número inteiro, 128."""
    try:
        return int(texto)
    except ValueError:
        return 128


def listar_blends(pasta):
    """Arquivos .blend da pasta dos estúdios (na ordem do sistema, como antes)."""
    return [arq for arq in os.listdir(pasta) if arq.lower().endswith(".blend")] if pasta and os.path.exists(pasta) else []


def listar_modelos_resina(pasta):
    """Modelos 3D de resina (.obj, .fbx, .stl, .blend) da pasta."""
    return [f for f in os.listdir(pasta) if f.lower().endswith(('.obj', '.fbx', '.stl', '.blend'))] if os.path.exists(pasta) else []


SEM_BLEND = "Nenhum arquivo .blend encontrado"
SEM_RESINA = "Nenhum modelo 3D encontrado"
IGNORAR_RESINA = "Nenhum (Ignorar Encaixe)"


def escolher_blend(arquivos, atual):
    """Estúdio que fica escolhido na lista: o atual, se ainda existe; senão o primeiro."""
    if arquivos:
        return atual if atual in arquivos else arquivos[0]
    return SEM_BLEND


def opcoes_resina(arquivos, atual):
    """(opções [(valor, rótulo)], valor escolhido) do campo do modelo de resina."""
    if arquivos:
        opcoes = [("Nenhum", IGNORAR_RESINA)] + [(arq, arq) for arq in arquivos]
        return opcoes, (atual if atual in arquivos else arquivos[0])
    return [(SEM_RESINA, SEM_RESINA)], SEM_RESINA


def preparar_pasta_saida(caminho_svg):
    """Pasta "imagens 3d" ao lado do SVG (criada se faltar), onde o Blender salva o resultado."""
    diretorio_svg = os.path.dirname(caminho_svg)
    saida = os.path.join(diretorio_svg, "imagens 3d")
    if not os.path.exists(saida):
        os.makedirs(saida)
    return saida


AVISO_SEM_SVG = "Por favor, selecione um arquivo SVG antes de prosseguir."
AVISO_SEM_CAMERA = "Por favor, selecione pelo menos uma câmera para renderizar."


def validar_avanco(svg_selecionado, render_auto, cam_principal, cam_esquerda, cam_direita):
    """None se pode ir para o Processing; senão, o texto do aviso."""
    if not svg_selecionado or not os.path.exists(svg_selecionado):
        return AVISO_SEM_SVG
    if render_auto and not (cam_principal or cam_esquerda or cam_direita):
        return AVISO_SEM_CAMERA
    return None


def cameras_selecionadas_str(principal, esquerda, direita):
    cams = []
    if principal: cams.append("Camera_Principal")
    if esquerda: cams.append("Camera_Esquerda")
    if direita: cams.append("Camera_Direita")
    return ",".join(cams)


# ==============================================================================
# BLENDER
# ==============================================================================
CAMINHO_ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blender_engine.py")


def montar_comando_blender(estado, resina_escolhida, render_auto, usar_textura, usar_verniz, cams_str,
                           caminho_engine=CAMINHO_ENGINE):
    """Comando do Blender (a mesma ordem de argumentos que o blender_engine.py espera)."""
    caminho_blend_escolhido = ""
    if estado.blend_dir and estado.selected_blend and not estado.selected_blend.startswith("Nenhum"):
        caminho_blend_escolhido = os.path.join(estado.blend_dir, estado.selected_blend)

    caminho_resina_completo = ""
    if resina_escolhida and not resina_escolhida.startswith("Nenhum"):
        caminho_resina_completo = os.path.join(estado.resina_dir, resina_escolhida)

    comando = [estado.blender_path]

    if render_auto:
        comando.append("--background")

    comando.extend([
        "--python", caminho_engine,
        "--",
        estado.svg_selecionado,
        estado.output_path,
        caminho_blend_escolhido,
        str(render_auto),
        str(usar_textura),
        str(estado.cycles_samples),
        str(usar_verniz),
        caminho_resina_completo,
        cams_str
    ])
    return comando


def interpretar_linha_blender(linha_limpa):
    """O que uma linha da saída do Blender muda na tela do Processing:
    ('status', texto), ('passo', concluído, novo status), ('amostras', atual, total, faltam,
    porcentagem, câmera) ou None."""
    if "Carregando estúdio base" in linha_limpa:
        return ("status", "📂 Abrindo arquivo de estúdio base...")
    elif "Analisando e importando" in linha_limpa:
        return ("passo", "✔ Estúdio carregado com sucesso!", "📐 Lendo dados do arquivo SVG...")
    elif "Convertendo curvas" in linha_limpa:
        return ("passo", "✔ SVG importado com sucesso!", "⚙ Convertendo curvas e montando camadas...")
    elif "Aplicando materiais" in linha_limpa:
        return ("passo", "✔ Malhas 3D montadas!", "🎨 Aplicando MDF, Acrílico e Texturas...")
    elif "Renderizando câmera:" in linha_limpa:
        cam_nome = linha_limpa.split("Renderizando câmera:")[-1].split("via")[0].strip()
        return ("passo", "✔ Materiais aplicados com sucesso!", f"📷 Renderizando Câmera {cam_nome}...")
    elif "[SAMPLE_PROGRESS]" in linha_limpa:
        try:
            parte_dados, parte_cam = linha_limpa.split("|CAM:")
            amostras_str = parte_dados.split(" ")[1]
            atual, total = map(int, amostras_str.split("/"))
            porcentagem = (atual / total) * 100
            faltam = total - atual
            nome_cam_atual = parte_cam.strip()
            return ("amostras", atual, total, faltam, porcentagem, nome_cam_atual)
        except Exception:
            pass
    elif "Renders salvos em:" in linha_limpa or "Modo interativo ativo" in linha_limpa:
        return ("passo", "✔ Todas as imagens renderizadas!", "✅ Finalizando processo...")
    return None


# ------------------------------------------------------------------------------
# Progresso real da renderização (barra composta e etapas)
# ------------------------------------------------------------------------------
# Pesos de cada parte na barra (somam 1). A preparação é rápida; o render das câmeras é quase todo
# o tempo; a finalização (gravar e fechar o Blender) é curta. Calibrar com os logs render-*.log.
PESO_PREPARACAO = 0.10
PESO_RENDER = 0.85
PESO_FINAL = 0.05
# Dentro de cada câmera: as samples valem esta fração; o resto (denoise e gravação da imagem) só
# conta quando a câmera termina (PTM_CAMERA_FIM), sem inventar progresso no meio.
FRACAO_SAMPLES_CAMERA = 0.90
TETO_ANTES_DO_FIM = 99.0      # a barra só chega a 100% quando o Blender termina com sucesso
# Estimativa de tempo restante: só depois de dados suficientes
ETA_MIN_SAMPLES = 3           # samples vistas na câmera atual
ETA_MIN_SEGUNDOS = 2.0        # tempo entre a 1ª e a última sample vista

ETAPAS_PREPARACAO = [
    ("estudio", "Abrir o estúdio base"),
    ("svg", "Ler e importar o SVG"),
    ("materiais", "Aplicar materiais e extrusões"),
    ("montagem", "Montar o troféu"),
    ("cameras", "Posicionar as câmeras"),
]
TEXTOS_ETAPA_ATUAL = {
    "estudio": "Abrindo o estúdio base...",
    "svg": "Lendo e importando o SVG...",
    "materiais": "Aplicando materiais, texturas e extrusões...",
    "montagem": "Montando o troféu (corpo, costas e resina)...",
    "cameras": "Posicionando as câmeras...",
}

_RE_PTM = re.compile(r"^PTM_(ETAPA|PLANO|CAMERA_FIM|CAMERA|FIM)\b\s*(.*)$")
_RE_SAMPLE = re.compile(r"\bSample (\d+)\s*/\s*(\d+)")
_RE_RENDERED = re.compile(r"\bRendered (\d+)\s*/\s*(\d+) samples", re.IGNORECASE)
_RE_TILE = re.compile(r"\bTile (\d+)\s*/\s*(\d+)|\b(\d+)\s*/\s*(\d+) Tiles", re.IGNORECASE)
_RE_FRACAO = re.compile(r"^(\d+)\s*/\s*(\d+)\s*(.*)$")


def plano_do_comando(comando):
    """(render_auto, samples, [câmeras]) a partir do comando de montar_comando_blender."""
    try:
        args = list(comando[list(comando).index("--") + 1:])
    except ValueError:
        return False, 0, []
    render_auto = len(args) > 3 and str(args[3]).strip().lower() in ("true", "1", "yes")
    try:
        samples = int(args[5]) if len(args) > 5 else 128
    except ValueError:
        samples = 128
    cams = [c.strip() for c in str(args[8]).split(",") if c.strip()] if len(args) > 8 else []
    if render_auto and not cams:
        cams = ["Camera_Principal", "Camera_Esquerda", "Camera_Direita"]
    return render_auto, samples, (cams if render_auto else [])


def formatar_duracao(segundos):
    """'45 s', '3 min 05 s', '1 h 02 min'."""
    s = int(round(max(0, segundos)))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"


class ProgressoRender:
    """Progresso real de uma execução do Blender, a partir das linhas da saída dele.

    Etapas: preparação (estúdio, SVG, materiais, montagem, câmeras), uma etapa por câmera e a
    finalização. Cada etapa tem estado 'pendente', 'andamento', 'concluida', 'pulada' ou 'erro'.
    A porcentagem é composta (pesos acima), nunca diminui e fica no máximo em 99% até
    concluir(True). Sem informação nova do Blender, 'trabalhando' fica True e a barra não anda.
    """

    def __init__(self, render_auto=True, samples=128, cameras=None, relogio=None):
        import time
        self._relogio = relogio or time.monotonic
        self.inicio = self._relogio()
        self.render_auto = render_auto
        self.samples = int(samples or 0)
        self.etapas = []
        for id_e, titulo in ETAPAS_PREPARACAO:
            self.etapas.append(self._nova_etapa(id_e, titulo, "preparacao"))
        self._definir_cameras(list(cameras or []))
        titulo_final = "Gravar as imagens e fechar o Blender" if render_auto else "Abrir o Blender (modo interativo)"
        self.etapas.append(self._nova_etapa("final", titulo_final, "final"))
        self._pct = 0.0
        self.concluido = False
        self.sucesso = None
        self.fim_script = False

    # ---------------------------------------------------------------- estrutura
    @staticmethod
    def _nova_etapa(id_e, titulo, grupo, nome_cam=None):
        return {"id": id_e, "titulo": titulo, "grupo": grupo, "estado": "pendente", "camera": nome_cam,
                "fase": None, "s": 0, "m": 0, "frac": 0.0, "t_ini": None, "t_fim": None,
                "t_s1": None, "s1": None, "t_su": None, "su": None}

    def _definir_cameras(self, nomes):
        antigas = {e["camera"]: e for e in self.etapas if e["grupo"] == "camera"}
        novas = []
        for nome in nomes:
            e = antigas.get(nome) or self._nova_etapa("camera:" + nome, f"Renderizar {nome}", "camera", nome)
            novas.append(e)
        resto = [e for e in self.etapas if e["grupo"] != "camera"]
        prep = [e for e in resto if e["grupo"] == "preparacao"]
        final = [e for e in resto if e["grupo"] == "final"]
        self.etapas = prep + novas + final
        n = len(novas)
        for i, e in enumerate(novas, start=1):
            e["titulo"] = f"Renderizar câmera {i} de {n} ({e['camera']})"

    def _cameras(self):
        return [e for e in self.etapas if e["grupo"] == "camera"]

    def _pesos(self):
        cams = self._cameras()
        prep = [e for e in self.etapas if e["grupo"] == "preparacao"]
        if cams:
            p_prep, p_render, p_final = PESO_PREPARACAO, PESO_RENDER, PESO_FINAL
        else:
            total = PESO_PREPARACAO + PESO_FINAL
            p_prep, p_render, p_final = PESO_PREPARACAO / total, 0.0, PESO_FINAL / total
        pesos = {}
        for e in prep:
            pesos[id(e)] = p_prep / len(prep)
        for e in cams:
            # todas as câmeras usam as mesmas samples: peso proporcional a câmeras × samples
            pesos[id(e)] = p_render / len(cams)
        for e in self.etapas:
            if e["grupo"] == "final":
                pesos[id(e)] = p_final
        return pesos

    def _atual(self):
        for e in self.etapas:
            if e["estado"] == "andamento":
                return e
        return None

    def _ativar(self, alvo):
        """Conclui tudo antes de 'alvo' (o que nem começou fica 'pulada') e põe 'alvo' em andamento."""
        agora = self._relogio()
        for e in self.etapas:
            if e is alvo:
                break
            if e["estado"] == "andamento":
                self._fechar(e, agora)
            elif e["estado"] == "pendente":
                e["estado"] = "pulada" if e["grupo"] == "camera" else "concluida"
        if alvo["estado"] == "pendente":
            alvo["estado"] = "andamento"
            alvo["t_ini"] = agora

    def _fechar(self, e, agora=None):
        e["estado"] = "concluida"
        e["t_fim"] = self._relogio() if agora is None else agora
        e["frac"] = 1.0

    # ---------------------------------------------------------------- entrada
    def linha(self, linha):
        """Lê uma linha da saída do Blender. True se o progresso mudou."""
        if self.concluido:
            return False
        texto = linha.strip()
        m = _RE_PTM.match(texto)
        if m:
            return self._marcador(m.group(1), m.group(2).strip())
        atual = self._atual()
        if not atual or atual["grupo"] != "camera":
            return False
        return self._linha_cycles(atual, texto)

    def _marcador(self, tipo, resto):
        if tipo == "ETAPA":
            partes = resto.split(None, 1)
            id_e = partes[0] if partes else ""
            if id_e == "render":
                for e in self.etapas:          # a preparação acabou; as câmeras vêm em PTM_CAMERA
                    if e["grupo"] == "preparacao" and e["estado"] in ("pendente", "andamento"):
                        self._fechar(e) if e["estado"] == "andamento" else e.update(estado="concluida")
                return True
            alvo = next((e for e in self.etapas if e["id"] == id_e), None)
            if alvo is None:
                return False
            self._ativar(alvo)
            return True
        if tipo == "PLANO":
            partes = resto.split(None, 2)
            try:
                self.samples = int(partes[0])
            except (IndexError, ValueError):
                pass
            nomes = [c for c in (partes[2].split(",") if len(partes) > 2 else []) if c.strip()]
            if [e["camera"] for e in self._cameras()] != nomes:
                self._definir_cameras(nomes)
            return True
        if tipo in ("CAMERA", "CAMERA_FIM"):
            m = _RE_FRACAO.match(resto)
            if not m:
                return False
            i, n, nome = int(m.group(1)), int(m.group(2)), m.group(3).strip()
            cams = self._cameras()
            if len(cams) != n or not (1 <= i <= n) or cams[i - 1]["camera"] != nome:
                nomes = [e["camera"] for e in cams]
                while len(nomes) < n:
                    nomes.append(f"Câmera {len(nomes) + 1}")
                nomes = nomes[:n]
                if 1 <= i <= n:
                    nomes[i - 1] = nome
                self._definir_cameras(nomes)
                cams = self._cameras()
            if not (1 <= i <= len(cams)):
                return False
            e = cams[i - 1]
            if tipo == "CAMERA":
                self._ativar(e)
                e["fase"] = "preparando"
                e["m"] = e["m"] or self.samples
            else:
                if e["estado"] == "pendente":
                    self._ativar(e)
                self._fechar(e)
                e["fase"] = "pronta"
            return True
        if tipo == "FIM":
            self.fim_script = True
            final = next(e for e in self.etapas if e["grupo"] == "final")
            self._ativar(final)
            return True
        return False

    def _linha_cycles(self, e, texto):
        mudou = False
        ms = _RE_SAMPLE.search(texto) or _RE_RENDERED.search(texto)
        if ms:
            s, m = int(ms.group(1)), int(ms.group(2))
            if m > 0:
                frac = min(1.0, s / m)
                mt = _RE_TILE.search(texto)
                if mt:
                    # "Tile i/n": o tile i está sendo renderizado; "Rendered k/n Tiles": k já prontos
                    if mt.group(1):
                        feitos, tn = int(mt.group(1)) - 1, int(mt.group(2))
                    else:
                        feitos, tn = int(mt.group(3)), int(mt.group(4))
                    if tn > 1 and 0 <= feitos <= tn:
                        frac = min(1.0, (feitos + frac) / tn)
                agora = self._relogio()
                if frac >= e["frac"]:
                    e["frac"] = frac
                    e["s"], e["m"] = s, m
                    if e["t_s1"] is None:
                        e["t_s1"], e["s1"] = agora, s
                    e["t_su"], e["su"] = agora, s
                    e["fase"] = "samples"
                    mudou = True
        # "Denoising" depois das samples (antes delas pode aparecer "Loading denoising kernels")
        if re.search(r"\bdenois", texto, re.IGNORECASE) and e["fase"] == "samples":
            e["fase"] = "denoise"
            mudou = True
        if texto.startswith("Saved:") or texto.startswith("Saved "):
            e["fase"] = "gravando"
            mudou = True
        return mudou

    def concluir(self, sucesso):
        """Fim do processo do Blender. Só com sucesso a barra vai a 100%."""
        agora = self._relogio()
        self.concluido = True
        self.sucesso = bool(sucesso)
        if sucesso:
            for e in self.etapas:
                if e["estado"] == "andamento":
                    self._fechar(e, agora)
                elif e["estado"] == "pendente":
                    e["estado"] = "pulada" if e["grupo"] == "camera" else "concluida"
            self._pct = 100.0
        else:
            atual = self._atual()
            if atual:
                atual["estado"] = "erro"
                atual["t_fim"] = agora
        self.fim = agora

    # ---------------------------------------------------------------- saída
    def porcentagem(self):
        if self.concluido and self.sucesso:
            return 100.0
        pesos = self._pesos()
        total = 0.0
        for e in self.etapas:
            if e["estado"] in ("concluida", "pulada"):
                total += pesos[id(e)]
            elif e["estado"] in ("andamento", "erro") and e["grupo"] == "camera":
                total += pesos[id(e)] * FRACAO_SAMPLES_CAMERA * e["frac"]
        pct = min(TETO_ANTES_DO_FIM, 100.0 * total)
        self._pct = max(self._pct, pct)
        return self._pct

    def trabalhando(self):
        """True quando há trabalho em andamento sem progresso medido (a barra não anda)."""
        if self.concluido:
            return False
        atual = self._atual()
        return not (atual and atual["grupo"] == "camera" and atual["fase"] == "samples")

    def texto_atual(self):
        if self.concluido:
            return STATUS_CONCLUIDO if self.sucesso else "⚠ O Blender terminou com erro."
        atual = self._atual()
        if atual is None:
            return "Iniciando o Blender..."
        if atual["grupo"] == "preparacao":
            return TEXTOS_ETAPA_ATUAL.get(atual["id"], atual["titulo"])
        if atual["grupo"] == "final":
            if not self.render_auto:
                return "Blender aberto no modo interativo (feche-o para concluir)."
            return "Gravando as imagens e fechando o Blender..."
        cams = self._cameras()
        i, n = cams.index(atual) + 1, len(cams)
        base = f"Renderizando câmera {i} de {n} ({atual['camera']})"
        fase = atual["fase"]
        if fase == "samples":
            return f"{base} — {atual['s']}/{atual['m']} samples"
        if fase == "denoise":
            return f"{base} — removendo ruído (denoise)"
        if fase == "gravando":
            return f"{base} — gravando a imagem"
        return f"{base} — preparando a cena (shaders e BVH)"

    def decorrido(self):
        fim = getattr(self, "fim", None) if self.concluido else None
        return (fim if fim is not None else self._relogio()) - self.inicio

    def restante(self):
        """Segundos que faltam pelo ritmo real das câmeras, ou None sem dados suficientes."""
        if self.concluido or self.fim_script:
            return None
        cams = self._cameras()
        atual = self._atual()
        if not cams or atual is None or atual["grupo"] != "camera":
            return None
        agora = self._relogio()
        feitas = [e for e in cams if e["estado"] == "concluida" and e["t_ini"] is not None and e["t_fim"] is not None]
        # duração da última câmera feita (a 1ª costuma ser mais lenta: carrega os kernels do Cycles)
        dur_ultima = (feitas[-1]["t_fim"] - feitas[-1]["t_ini"]) if feitas else None
        # segundos por sample: da câmera atual (se já tem dados) ou das câmeras já feitas
        tps = None
        if (atual["su"] is not None and atual["su"] - atual["s1"] >= ETA_MIN_SAMPLES
                and atual["t_su"] - atual["t_s1"] >= ETA_MIN_SEGUNDOS):
            tps = (atual["t_su"] - atual["t_s1"]) / (atual["su"] - atual["s1"])
        else:
            com_samples = [e for e in feitas if e["su"] is not None and e["su"] > e["s1"]]
            if com_samples:
                tps = (sum(e["t_su"] - e["t_s1"] for e in com_samples)
                       / sum(e["su"] - e["s1"] for e in com_samples))
        # tempo depois da última sample (denoise + gravação), medido nas câmeras feitas
        pos = [e["t_fim"] - e["t_su"] for e in feitas if e["t_su"] is not None]
        pos_media = sum(pos) / len(pos) if pos else 0.0

        if atual["fase"] == "samples" and tps is not None:
            resto_atual = max(0, atual["m"] - atual["s"]) * tps + pos_media
        elif atual["fase"] in ("denoise", "gravando") and feitas and pos:
            resto_atual = max(0.0, pos_media - (agora - atual["t_su"]))
        elif dur_ultima is not None:
            resto_atual = max(0.0, dur_ultima - (agora - atual["t_ini"]))
        else:
            return None

        pendentes = sum(1 for e in cams if e["estado"] == "pendente")
        if pendentes:
            # preparo antes da 1ª sample (shaders/BVH), medido na câmera mais recente que já tem samples
            com_s1 = [e for e in cams if e["t_s1"] is not None and e["t_ini"] is not None]
            if tps is not None and com_s1:
                pre = com_s1[-1]["t_s1"] - com_s1[-1]["t_ini"]
                por_camera = pre + (atual["m"] or self.samples) * tps + pos_media
            elif dur_ultima is not None:
                por_camera = dur_ultima
            else:
                return None
            resto_atual += pendentes * por_camera
        return resto_atual

    def estado(self):
        """Dados simples (JSON) para as interfaces."""
        restante = self.restante()
        return {
            "porcentagem": round(self.porcentagem(), 2),
            "trabalhando": self.trabalhando(),
            "atual": self.texto_atual(),
            "decorrido": round(self.decorrido(), 1),
            "restante": None if restante is None else round(restante, 1),
            "concluido": self.concluido,
            "sucesso": self.sucesso,
            "etapas": [{"id": e["id"], "titulo": e["titulo"], "estado": e["estado"]} for e in self.etapas],
        }

    def resumo_tempos(self):
        """Linhas com o tempo de cada etapa (para o log de render)."""
        linhas = []
        for e in self.etapas:
            if e["t_ini"] is None:
                linhas.append(f"  {e['titulo']}: {e['estado']}")
                continue
            fim = e["t_fim"] if e["t_fim"] is not None else self._relogio()
            extra = ""
            if e["grupo"] == "camera" and e["t_s1"] is not None:
                extra = (f" (até a 1ª sample {e['t_s1'] - e['t_ini']:.1f} s; samples {e['s1']}→{e['su']}/{e['m']} "
                         f"em {e['t_su'] - e['t_s1']:.1f} s; depois da última sample {fim - e['t_su']:.1f} s)")
            linhas.append(f"  {e['titulo']}: {e['estado']}, {fim - e['t_ini']:.1f} s{extra}")
        return linhas


def texto_tempos(estado):
    """'Decorrido: 1 min 05 s  ·  Restante: ~3 min 10 s' (restante só com estimativa)."""
    txt = f"Decorrido: {formatar_duracao(estado['decorrido'])}"
    if estado.get("restante") is not None:
        txt += f"  ·  Restante: ~{formatar_duracao(estado['restante'])}"
    return txt


LIMITE_LINHAS_LOG_RENDER = 20000


def _gravar_log_render(comando, progresso, linhas_log, total_linhas, inicio_data, codigo, pasta_logs=None):
    """Grava logs/render-*.log (higienizado, vai para a branch logs com os logs de erro).
    Nunca levanta exceção: o log é para diagnóstico e não pode atrapalhar o app."""
    try:
        render_auto, samples, cams = plano_do_comando(comando)
        cab = [
            f"Início: {inicio_data.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duração total: {progresso.decorrido():.1f} s",
            f"Código de saída do Blender: {codigo}",
            f"Resultado: {'sucesso' if progresso.sucesso else 'falhou'}",
            f"Render automático: {render_auto}  ·  Samples: {samples}  ·  Câmeras: {', '.join(cams) or '-'}",
            f"Pesos: preparação {PESO_PREPARACAO}, render {PESO_RENDER}, final {PESO_FINAL}, "
            f"samples/câmera {FRACAO_SAMPLES_CAMERA}",
            "Comando: " + " ".join(f'"{c}"' for c in comando),
            "",
            "Tempo de cada etapa:",
        ] + progresso.resumo_tempos() + ["", "Saída do Blender (segundos desde o início | linha):"]
        if total_linhas > len(linhas_log):
            cab.append(f"(as primeiras {total_linhas - len(linhas_log)} linhas foram cortadas)")
        corpo = [f"{t:9.3f} | {l}" for t, l in linhas_log]
        return registro_erros.gravar_log_render("\n".join(cab + corpo), agora=inicio_data, pasta_logs=pasta_logs)
    except Exception:
        return None


def executar_blender(comando, ao_evento, origem="app_ui (Blender)", popen=None, relogio=None, pasta_logs=None):
    """Roda o Blender e chama ao_evento(evento) para cada mudança da tela (veja
    interpretar_linha_blender) e ao_evento(('progresso', estado)) com o progresso real
    (ProgressoRender.estado), depois ao_evento(('concluido',)) se deu certo ou
    ao_evento(('concluido', False)) se o Blender terminou com erro. Se o Blender terminar com
    erro, grava o log de erro; se nem der para rodar, grava o log e chama ao_evento(('erro', mensagem)).
    Toda execução grava a saída do Blender, com o horário de cada linha, em logs/render-*.log.
    Roda na thread de quem chamou (as interfaces chamam numa thread separada)."""
    import time
    import datetime
    popen = popen or subprocess.Popen
    relogio = relogio or time.monotonic
    render_auto, samples, cams = plano_do_comando(comando)
    progresso = ProgressoRender(render_auto, samples, cams, relogio=relogio)
    linhas_log = collections.deque(maxlen=LIMITE_LINHAS_LOG_RENDER)
    total_linhas = 0
    inicio_data = datetime.datetime.now()
    t0 = relogio()
    codigo = None
    try:
        processo = popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore')
        ultimas_linhas = collections.deque(maxlen=200)   # para o log de erro
        teve_traceback = False
        for linha in processo.stdout:
            linha_limpa = linha.strip()
            ultimas_linhas.append(linha.rstrip("\r\n"))
            total_linhas += 1
            linhas_log.append((relogio() - t0, linha.rstrip("\r\n")))
            if linha_limpa.startswith("Traceback (most recent call last)") or linha_limpa.startswith("Error: Python:"):
                teve_traceback = True
            evento = interpretar_linha_blender(linha_limpa)
            if evento:
                ao_evento(evento)
            # a 1ª linha (o Blender respondeu) já manda a lista de etapas para a tela
            if progresso.linha(linha_limpa) or total_linhas == 1:
                ao_evento(("progresso", progresso.estado()))

        processo.wait()
        codigo = processo.returncode
        falhou = processo.returncode != 0 or teve_traceback
        progresso.concluir(not falhou)
        _gravar_log_render(comando, progresso, linhas_log, total_linhas, inicio_data, codigo, pasta_logs)
        if falhou:
            registro_erros.gravar_log(
                origem,
                f"Blender terminou com código {processo.returncode}" + (" e com erro de Python" if teve_traceback else ""),
                "Comando: " + " ".join(f'"{c}"' for c in comando) + "\n\nÚltimas linhas do Blender:\n" + "\n".join(ultimas_linhas))
        ao_evento(("progresso", progresso.estado()))
        ao_evento(("concluido", False) if falhou else ("concluido",))
    except Exception as e:
        if total_linhas:
            progresso.concluir(False)
            _gravar_log_render(comando, progresso, linhas_log, total_linhas, inicio_data, codigo, pasta_logs)
        registro_erros.gravar_log(origem, f"Não foi possível rodar o Blender: {e}",
                                  "Comando: " + " ".join(f'"{c}"' for c in comando) + "\n\n" + traceback.format_exc())
        ao_evento(("erro", f"Não foi possível rodar o Blender:\n{e}"))


# Textos da tela do Processing (iguais nas duas interfaces)
STATUS_INICIAL = "🔄 Iniciando importação e montagem de malhas..."
SAMPLES_INICIAL = "Aguardando início do Cycles..."
STATUS_CONCLUIDO = "✅ Processamento Concluído!"
SAMPLES_CONCLUIDO = "Renderização Finalizada (100% Concluído)"
SAMPLES_COM_ERRO = "O Blender terminou com erro (o log de erro foi gravado)"


def textos_amostras(atual, total, faltam, nome_cam):
    """(status, linha dos samples) enquanto o Cycles renderiza uma câmera."""
    return (f"📷 Renderizando: {nome_cam}",
            f"[{nome_cam}] Samples: {atual} / {total}  |  Faltam: {faltam}")


def abrir_pasta_saida(output_path):
    """Abre a pasta das imagens no Explorer (se ela existir)."""
    if os.path.exists(output_path):
        os.startfile(output_path)
        return True
    return False
