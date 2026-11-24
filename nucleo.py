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


def executar_blender(comando, ao_evento, origem="app_ui (Blender)", popen=None):
    """Roda o Blender e chama ao_evento(evento) para cada mudança da tela (veja
    interpretar_linha_blender), depois ao_evento(('concluido',)). Se o Blender terminar com erro,
    grava o log; se nem der para rodar, grava o log e chama ao_evento(('erro', mensagem)).
    Roda na thread de quem chamou (as interfaces chamam numa thread separada)."""
    popen = popen or subprocess.Popen
    try:
        processo = popen(comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore')
        ultimas_linhas = collections.deque(maxlen=200)   # para o log de erro
        teve_traceback = False
        for linha in processo.stdout:
            linha_limpa = linha.strip()
            ultimas_linhas.append(linha.rstrip("\r\n"))
            if linha_limpa.startswith("Traceback (most recent call last)") or linha_limpa.startswith("Error: Python:"):
                teve_traceback = True
            evento = interpretar_linha_blender(linha_limpa)
            if evento:
                ao_evento(evento)

        processo.wait()
        if processo.returncode != 0 or teve_traceback:
            registro_erros.gravar_log(
                origem,
                f"Blender terminou com código {processo.returncode}" + (" e com erro de Python" if teve_traceback else ""),
                "Comando: " + " ".join(f'"{c}"' for c in comando) + "\n\nÚltimas linhas do Blender:\n" + "\n".join(ultimas_linhas))
        ao_evento(("concluido",))
    except Exception as e:
        registro_erros.gravar_log(origem, f"Não foi possível rodar o Blender: {e}",
                                  "Comando: " + " ".join(f'"{c}"' for c in comando) + "\n\n" + traceback.format_exc())
        ao_evento(("erro", f"Não foi possível rodar o Blender:\n{e}"))


# Textos da tela do Processing (iguais nas duas interfaces)
STATUS_INICIAL = "🔄 Iniciando importação e montagem de malhas..."
SAMPLES_INICIAL = "Aguardando início do Cycles..."
STATUS_CONCLUIDO = "✅ Processamento Concluído!"
SAMPLES_CONCLUIDO = "Renderização Finalizada (100% Concluído)"


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
