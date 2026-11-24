import os
import re
import xml.etree.ElementTree as ET

try:
    from svgpathtools import parse_path
    HAS_SVGPATH = True
except ImportError:
    HAS_SVGPATH = False

CAMINHO_TROFÉUS = R"F:\\Backup Aroni 29-05-2021\\Publico\\2026\\CATALOGO\\KART\KAR25001\\SVG\\KAR25001.svg"


# ==============================================================================
# DICIONÁRIO COMPLETO DE MATERIAIS
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
        print(f"❌ Erro: O arquivo '{caminho_svg}' não foi encontrado no caminho especificado.")
        return

    nome_arquivo = os.path.basename(caminho_svg)

    try:
        tree = ET.parse(caminho_svg)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ Erro ao ler o arquivo SVG: {e}")
        return

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
        # Padrão de precisão do CorelDRAW (0.1 mm por unidade de coordenadas)
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

        # DESCOMPOSIÇÃO DE CAMINHO COMPOSTO (SUB-PATHS ISOLADOS)
        if mat_info and mat_info['tipo'] in TIPOS_CORPO_EXCLUSIVO and not eh_pagina:
            if tag == 'path':
                d = elem.attrib.get('d', '')

                if HAS_SVGPATH:
                    try:
                        # Divide o caminho composto em sub-caminhos independentes
                        path_obj = parse_path(d)
                        subpaths = path_obj.continuous_subpaths()

                        for sp in subpaths:
                            xmin, xmax, ymin, ymax = sp.bbox()
                            w_mm = (xmax - xmin) * fator_mm
                            h_mm = (ymax - ymin) * fator_mm

                            larg = min(w_mm, h_mm)
                            alt = max(w_mm, h_mm)

                            # Filtra ruídos ou furos internos (< 3cm)
                            if larg > 30.0 and alt > 30.0:
                                pecas_isoladas.append((larg, alt, mat_info['nome_material']))
                    except:
                        pass
                else:
                    # Fallback manual por comandos 'M' / 'm'
                    sub_str = re.split(r'(?=[Mm])', d)
                    for sp in sub_str:
                        if not sp.strip():
                            continue
                        coords = [float(v) for v in re_coords.findall(sp)]
                        if len(coords) >= 4:
                            xs = coords[0::2]
                            ys = coords[1::2]
                            w_mm = (max(xs) - min(xs)) * fator_mm
                            h_mm = (max(ys) - min(ys)) * fator_mm
                            larg = min(w_mm, h_mm)
                            alt = max(w_mm, h_mm)
                            if larg > 30.0 and alt > 30.0:
                                pecas_isoladas.append((larg, alt, mat_info['nome_material']))

            elif tag == 'rect':
                rw = float(elem.attrib.get('width', 0))
                rh = float(elem.attrib.get('height', 0))
                if rw > 0 and rh > 0:
                    w_mm = rw * fator_mm
                    h_mm = rh * fator_mm
                    larg = min(w_mm, h_mm)
                    alt = max(w_mm, h_mm)
                    if larg > 30.0 and alt > 30.0:
                        pecas_isoladas.append((larg, alt, mat_info['nome_material']))

    # Seleciona a maior sub-peça individual do corpo do troféu
    if pecas_isoladas:
        pecas_isoladas.sort(key=lambda p: p[1], reverse=True)
        largura_final_mm, altura_final_mm, nome_chapa_fundo = pecas_isoladas[0]
    else:
        largura_final_mm, altura_final_mm, nome_chapa_fundo = 0.0, 0.0, "N/A"

    largura_final_cm = largura_final_mm / 10.0
    altura_final_cm = altura_final_mm / 10.0

    # Retorno Formatado no Console
    print("\n" + "=" * 65)
    print(" 📊 RELATÓRIO DE ESTRUTURA DO TROFÉU (SVG)")
    print("=" * 65)
    print(f"📁 Nome do Arquivo : {nome_arquivo}")
    print("-" * 65)

    print("📦 MATERIAIS E QUANTIDADES:")
    if materiais_qtd:
        for (tipo, nome), qtd in materiais_qtd.items():
            print(f"   • Tipo: {tipo:<22} | Nome: {nome:<28} | Qtd: {qtd}")
    else:
        print("   • Nenhum material/contorno identificado no arquivo.")

    if pecas_descartadas:
        print("-" * 65)
        print(f"⚠️ PEÇAS QUE NÃO SERÃO CONVERTIDAS (cor fora da tabela ou sem contorno): {len(pecas_descartadas)}")
        for id_peca, cor in pecas_descartadas:
            print(f"   • {id_peca:<28} | Contorno: {cor if cor else 'sem contorno'}")

    print("-" * 65)
    print("📐 TAMANHO GERAL (PEÇA INDIVIDUAL DO CORPO):")
    print(f"   • Peça de Fundo: {nome_chapa_fundo}")
    print(f"   • Largura     : {largura_final_mm:.2f} mm ({largura_final_cm:.2f} cm)")
    print(f"   • Altura      : {altura_final_mm:.2f} mm ({altura_final_cm:.2f} cm)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    caminho_svg = CAMINHO_TROFÉUS
    extrair_informacoes_svg(caminho_svg)