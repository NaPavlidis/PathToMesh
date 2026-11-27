import bpy
import xml.etree.ElementTree as ET
import re
import os
import mathutils  # type: ignore[reportMissingImports]
import math 
import sys
import shutil

# O Blender roda este arquivo com --python: a pasta do projeto não entra sozinha no sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import malha_logica  # noqa: E402

# ==============================================================================
# 1. CONFIGURAÇÕES E REGRAS GERAIS
# ==============================================================================

REGRAS_MATERIAIS = {    
    # ACRÍLICOS
    '#ed3237': { 'tipo': 'ACRILICO', 'nome_material': 'acrilico_padrão', 'extrusao': 0.001, 'roughness': 0.003, 'transmission': 0.8, 'ior': 1.8 },
    '#fff212': { 'tipo': 'ACRILICO', 'nome_material': 'Acrilico_transparente', 'extrusao': 0.001, 'roughness': 0.001, 'transmission': 1.0, 'ior': 2 },
    '#d2ae6d': { 'tipo': 'ACRILICO', 'nome_material': 'Acrilico_Dourado', 'extrusao': 0.001, 'roughness': 0.003, 'transmission': 0.8, 'ior': 1.8 },
        
    # MDFs
    '#fefefe': { 'tipo': 'MDF', 'nome_material': 'MDF_3mm', 'extrusao': 0.003, 'roughness': 0.55, 'transmission': 0.03, 'ior': 1.2},
    '#e6e7e8': { 'tipo': 'MDF', 'nome_material': 'MDF_6mm', 'extrusao': 0.006, 'roughness': 0.55, 'transmission': 0.03, 'ior': 1.2},
    '#d2d3d5': { 'tipo': 'MDF', 'nome_material': 'MDF_9mm', 'extrusao': 0.009, 'roughness': 0.55, 'transmission': 0.03, 'ior': 1.2},
    '#373435': { 'tipo': 'PLOTTER', 'nome_material': 'PLOTTER', 'extrusao': 0.0001, 'roughness': 0.05, 'transmission': 0.03, 'ior': 1.2},

    # MDF COSTAS (permanece plano/deitado)
    '#00afef': { 'tipo': 'MDF_COSTAS', 'nome_material': 'MDF_Costas_3mm', 'extrusao': 0.003, 'roughness': 0.55, 'transmission': 0.2, 'ior': 1.4 },

    # RESINA (Área guia sem extrusão)
    '#00a859': { 'tipo': 'RESINA_AREA', 'nome_material': 'Area_Resina', 'extrusao': 0.0, 'roughness': 0.2 , 'transmission': 0.5, 'ior': 1.10 },

    # BASES
    "#f58634": { 'tipo': 'BASE', 'nome_material': 'Base_3MM', 'extrusao': 0.003, 'roughness': 0.55, 'transmission': 0.02, 'ior': 1.2},
    "#3e4095": { 'tipo': 'BASE', 'nome_material': 'Base_6MM', 'extrusao': 0.009, 'roughness': 0.55, 'transmission': 0.02, 'ior': 1.2},
    "#f7adaf": { 'tipo': 'BASE', 'nome_material': 'Base_9MM', 'extrusao': 0.015, 'roughness': 0.55, 'transmission': 0.02, 'ior': 1.2},
    "#84716b": { 'tipo': 'BASE', 'nome_material': 'Base_12MM', 'extrusao': 0.025, 'roughness': 0.55, 'transmission': 0.02, 'ior': 1.2},    

    # ... outros materiais ...
    '#9d98ca': { 'tipo': 'ACRILICO_GRAVADO', 'nome_material': 'Acrilico_Gravado', 'extrusao': 0.0001, 'roughness': 0.65, 'transmission': 0.15,'ior': 1.49 },

    
    # ADESIVOS
    '#ec268f': { 'tipo': 'ADESIVO', 'nome_material': 'Adesivo_Padrao', 'extrusao': 0.0005, 'roughness': 0.035, 'transmission': 0.02, 'ior': 1.08 }
    
}

FATOR_ESCURECIMENTO_ADESIVO = 0.25

# Cor padrão para MDF quando não houver preenchimento especificado no SVG (MDF Cru / Madeira)
COR_PADRAO_MDF_HEX = '#5c4033'

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

# Marcadores de progresso lidos pelo app (nucleo.ProgressoRender). Uma linha por evento, sempre
# no começo da linha e com flush, para chegar na hora:
#   PTM_ETAPA <id> <i>/<n> <descrição>      começo de uma etapa (estudio, svg, materiais, montagem,
#                                           cameras, render, final)
#   PTM_PLANO <samples> <n> <câmeras,...>   o que vai ser renderizado
#   PTM_CAMERA <i>/<n> <nome>               começo do render de uma câmera
#   PTM_CAMERA_FIM <i>/<n> <nome>           imagem da câmera renderizada e gravada
#   PTM_FIM                                 o script terminou (o Blender vai fechar)
#   PTM_PASSADAS principal[,freestyle]      passadas de cada câmera (o Freestyle renderiza de novo)
#   PTM_RENDER_INICIO / _POS / _FIM         handlers render_init / render_post / render_complete (log)
#   PTM_PASSADA freestyle                   o Cycles passou para a passada do Freestyle
#   PTM_SAMPLES <s> <m> <passada> [<seg>]   samples atuais e totais (handler render_stats) e o
#                                           "Remaining" do Cycles em segundos, se veio
#   PTM_STATS <texto do Cycles>             o texto do render_stats como chegou (diagnóstico)
# Os logs reais (Blender 5.3) mostram que o render_stats só chega com as samples 0, 1 e a última
# de cada passada; o app estima o meio pelo tempo (nucleo.ProgressoRender).
ETAPAS_MOTOR = ["estudio", "svg", "materiais", "montagem", "cameras", "render", "final"]


def marcar_etapa(id_etapa, descricao):
    i = ETAPAS_MOTOR.index(id_etapa) + 1
    print(f"PTM_ETAPA {id_etapa} {i}/{len(ETAPAS_MOTOR)} {descricao}", flush=True)

def hex_para_rgba(hex_color, alpha=1.0):
    if not hex_color or not hex_color.startswith('#'): 
        return (0.36, 0.25, 0.20, alpha) # Fallback seguro tom MDF cru
    hex_color = hex_color.lstrip('#').lower()
    if len(hex_color) == 3:
        hex_color = f"{hex_color[0]*2}{hex_color[1]*2}{hex_color[2]*2}"
    
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    
    fator_cmyk = 0.65
    r, g, b = r * fator_cmyk, g * fator_cmyk, b * fator_cmyk
    
    def srgb_para_linear(c): 
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        
    return (srgb_para_linear(r), srgb_para_linear(g), srgb_para_linear(b), alpha)

def obter_caixa_de_colisao(obj):
    bpy.context.view_layer.update()
    cantos = [obj.matrix_world @ mathutils.Vector(v) for v in obj.bound_box]
    xs = [v.x for v in cantos]
    ys = [v.y for v in cantos]
    return min(xs), max(xs), min(ys), max(ys)

def criar_uv_perfeito(obj):
    if not obj.data.uv_layers: obj.data.uv_layers.new(name="UVMap")
    uv_layer = obj.data.uv_layers.active.data
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    if not xs or not ys: return
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    largura = max_x - min_x if max_x > min_x else 0.001
    altura = max_y - min_y if max_y > min_y else 0.001
    for loop in obj.data.loops:
        v = obj.data.vertices[loop.vertex_index]
        u = (v.co.x - min_x) / largura
        v_uv = (v.co.y - min_y) / altura
        uv_layer[loop.index].uv = (u, v_uv)

def aplicar_textura_mdf_procedural(mat, cor_preenchimento_rgba):
    """
    Aplica a textura procedural de MDF cru com fibras visíveis e relevo tátil,
    sem clarear excessivamente e sem alterar a matiz da cor base.
    """
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # 1. Output e BSDF Principal
    output_node = nodes.new('ShaderNodeOutputMaterial')
    output_node.location = (500, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    # O MDF cru possui superfície fosca e rugosa
    #bsdf.inputs['Roughness'].default_value = 0.75

    # 2. Coordenadas de Textura 3D (Object Space)
    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-1200, 0)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-1000, 0)
    # ESCALA CORRIGIDA: 150.0 faz os veios da madeira ficarem do tamanho real do troféu
    mapping.inputs['Scale'].default_value = (150.0, 150.0, 150.0)
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    # 3. Ruído Procedural (Granulação de Fibra)
    noise_node = nodes.new('ShaderNodeTexNoise')
    noise_node.location = (-750, 100)
    noise_node.inputs['Scale'].default_value = 8.0
    noise_node.inputs['Detail'].default_value = 1.1
    noise_node.inputs['Roughness'].default_value = 1.0
    noise_node.inputs['Lacunarity'].default_value = 3.5
    noise_node.inputs['Distortion'].default_value = 0.4
    links.new(mapping.outputs['Vector'], noise_node.inputs['Vector'])

    # 4. ColorRamp em Escala de Cinza Escura (Controle estrito de luminosidade)
    color_ramp = nodes.new('ShaderNodeValToRGB')
    color_ramp.location = (-500, 100)
    
    # Define o escurecimento das fibras sem estourar no branco
    color_ramp.color_ramp.elements[0].position = 0.20
    color_ramp.color_ramp.elements[0].color = (0.60, 0.60, 0.60, 1.0) # Variação mais escura (20% cinza)
    
    color_ramp.color_ramp.elements[1].position = 0.80
    color_ramp.color_ramp.elements[1].color = (0.90, 0.90, 0.90, 1.0) # Variação máxima controlada (75% cinza)
    
    links.new(noise_node.outputs['Fac'], color_ramp.inputs['Fac'])

    # 5. Mix Multiply (Multiplica a variação de cinza pela cor original lida)
    mix_node = nodes.new('ShaderNodeMix')
    mix_node.data_type = 'RGBA'
    mix_node.blend_type = 'MULTIPLY'
    mix_node.location = (-200, 100)
    
    input_fac = mix_node.inputs.get('Factor', mix_node.inputs[0])
    input_a = mix_node.inputs.get('A', mix_node.inputs[6])
    input_b = mix_node.inputs.get('B', mix_node.inputs[7])
    saida_mix = mix_node.outputs.get('Result', mix_node.outputs[2])

    input_fac.default_value = 1.0
    links.new(color_ramp.outputs['Color'], input_a)
    input_b.default_value = cor_preenchimento_rgba
    links.new(saida_mix, bsdf.inputs['Base Color'])

    # 6. Relevo Tátil (Bump de Fibras)
    bump_node = nodes.new('ShaderNodeBump')
    bump_node.location = (-200, -200)
    bump_node.inputs['Strength'].default_value = 0.45 # Intensifica as micro-sombras táticas
    bump_node.inputs['Distance'].default_value = 0.0005
    links.new(noise_node.outputs['Fac'], bump_node.inputs['Height'])
    links.new(bump_node.outputs['Normal'], bsdf.inputs['Normal'])

def aplicar_material_acrilico_gravado(mat, cor_base_rgba=(0.95, 0.95, 0.95, 1.0)):
    """
    Cria um material difuso/esbranquiçado e fosco com relevo tátil 
    que simula a fresta e o desgaste do laser no acrílico.
    """
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output_node = nodes.new('ShaderNodeOutputMaterial')
    output_node.location = (400, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (100, 0)
    links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])

    # Propriedades físicas da gravação fosca
    bsdf.inputs['Base Color'].default_value = cor_base_rgba # Tom claro/esbranquiçado
    bsdf.inputs['Roughness'].default_value = 0.70          # Fosco
    if 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = 0.10 # Leve translucidez
    elif 'Transmission' in bsdf.inputs:
        bsdf.inputs['Transmission'].default_value = 0.10

    # Ruído de relevo (Simula o atrito do laser)
    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-800, 0)

    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-600, 0)
    mapping.inputs['Scale'].default_value = (300.0, 300.0, 300.0) # Ruído bem micro
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    noise_node = nodes.new('ShaderNodeTexNoise')
    noise_node.location = (-400, 0)
    noise_node.inputs['Scale'].default_value = 100.0
    noise_node.inputs['Detail'].default_value = 10.0
    links.new(mapping.outputs['Vector'], noise_node.inputs['Vector'])

    bump_node = nodes.new('ShaderNodeBump')
    bump_node.location = (-150, -150)
    bump_node.inputs['Strength'].default_value = 0.25 # Relevo raso
    bump_node.inputs['Distance'].default_value = 0.0005
    links.new(noise_node.outputs['Fac'], bump_node.inputs['Height'])
    links.new(bump_node.outputs['Normal'], bsdf.inputs['Normal'])   

# ==============================================================================
# 3. MÓDULOS DE PROCESSAMENTO
# ==============================================================================

def carregar_estudio_e_hdri(caminho_blend):
    if caminho_blend and os.path.exists(caminho_blend):
        print(f">>> Carregando estúdio base: {caminho_blend}", flush=True)
        bpy.ops.wm.open_mainfile(filepath=caminho_blend)
        
        if bpy.context.scene.world and bpy.context.scene.world.use_nodes:
            world_node_tree = bpy.context.scene.world.node_tree
            nodes = world_node_tree.nodes
            
            tex_coord = next((n for n in nodes if n.type == 'TEX_COORD'), None)
            mapping = next((n for n in nodes if n.type == 'MAPPING'), None)
            
            if tex_coord and mapping:
                for link in list(world_node_tree.links):
                    if link.to_node == mapping and link.to_socket.name == 'Vector':
                        world_node_tree.links.remove(link)
                world_node_tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])

            for node in nodes:
                if node.type in ['TEX_ENVIRONMENT', 'MAPPING', 'TEX_COORD', 'EMISSION', 'MIX_SHADER', 'LIGHT_PATH', 'RGB']:
                    for inp in node.inputs:
                        if hasattr(inp, 'default_value'):
                            try: inp.default_value = inp.default_value
                            except Exception: pass
            
            world_node_tree.update_tag()
            bpy.context.evaluated_depsgraph_get().update()

def analisar_e_preparar_svg(caminho_svg):
    print(f">>> Analisando e importando o arquivo SVG...", flush=True)
    ET.register_namespace('', "http://www.w3.org/2000/svg")
    try:
        tree = ET.parse(caminho_svg)
        root = tree.getroot()
    except Exception as e:
        print(f"Erro ao ler SVG: {e}")
        return None, {}, []
    
    imagens_no_svg = []
    elementos_para_remover = []
    dados_extraidos = {}
    contador = 1
    
    for pai in root.iter():
        for filho in list(pai):
            tag_filho = filho.tag.split('}')[-1]
            if tag_filho == 'image':
                for attr, val in filho.attrib.items():
                    if attr.endswith('href') and not val.startswith('data:'):
                        imagens_no_svg.append(val)
                        break
                elementos_para_remover.append((pai, filho))
                continue
            elif tag_filho in ['clipPath', 'mask']:
                elementos_para_remover.append((pai, filho))
                continue
                
            if tag_filho in ['path', 'rect', 'circle', 'ellipse', 'polygon', 'polyline', 'line']:
                style = filho.get('style', '')
                stroke = filho.get('stroke', None)
                fill = filho.get('fill', None)
                
                if style:
                    stroke_match = re.search(r'stroke:\s*([^;]+)', style)
                    if stroke_match and stroke_match.group(1) != 'none': stroke = stroke_match.group(1).strip()
                    fill_match = re.search(r'fill:\s*([^;]+)', style)
                    if fill_match and fill_match.group(1) != 'none': fill = fill_match.group(1).strip()
                
                cor_contorno = ''
                if stroke and stroke != 'none':
                    cor_limpa = stroke.replace('"', '').replace("'", "").replace('\n', '').replace(' ', '').lower()
                    if len(cor_limpa) == 4 and cor_limpa.startswith('#'):
                        cor_limpa = f"#{cor_limpa[1]*2}{cor_limpa[2]*2}{cor_limpa[3]*2}"
                    cor_contorno = cor_limpa

                if cor_contorno and cor_contorno not in REGRAS_MATERIAIS:
                    elementos_para_remover.append((pai, filho))
                elif not cor_contorno:
                    elementos_para_remover.append((pai, filho))
                else:
                    id_obj = f"trofeu_shape_{contador}"
                    filho.set('id', id_obj)
                    contador += 1
                    
                    cor_fill_real = fill.strip() if fill and fill.strip() not in ['none', ''] else 'Nenhum'
                    dados_extraidos[id_obj] = {
                        'contorno': cor_contorno, 
                        'preenchimento': cor_fill_real
                    }
                    
                    filho.set('fill', '#ffffff') 
                    if 'stroke' in filho.attrib: del filho.attrib['stroke']
                    if 'stroke-width' in filho.attrib: del filho.attrib['stroke-width']
                    if style: 
                        style_limpo = re.sub(r'stroke-[^;]+;?|stroke:[^;]+;?', '', style)
                        style_limpo = re.sub(r'fill:[^;]+;?', '', style_limpo)
                        filho.set('style', style_limpo)

    for pai, filho in elementos_para_remover:
        try: pai.remove(filho)
        except: pass

    pasta_svg = os.path.dirname(caminho_svg)
    nome_arquivo_svg = os.path.splitext(os.path.basename(caminho_svg))[0]
    pasta_imagens = os.path.join(pasta_svg, f"{nome_arquivo_svg}__Images")
    if not os.path.exists(pasta_imagens):
        pasta_imagens = os.path.join(pasta_svg, f"{nome_arquivo_svg}_Images")
        
    imagens_disponiveis = []
    if os.path.exists(pasta_imagens):
        for img_nome in imagens_no_svg:
            caminho_img = os.path.join(pasta_imagens, os.path.basename(img_nome))
            if os.path.exists(caminho_img) and caminho_img not in imagens_disponiveis:
                imagens_disponiveis.append(caminho_img)
        if not imagens_disponiveis:
            for arquivo in os.listdir(pasta_imagens):
                if arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                    imagens_disponiveis.append(os.path.join(pasta_imagens, arquivo))
                    
    caminho_temp = os.path.join(pasta_svg, "temp_import.svg")
    tree.write(caminho_temp)
    
    return caminho_temp, dados_extraidos, imagens_disponiveis

def importar_e_converter_svg(caminho_temp, opcoes_malha=None):
    opcoes_malha = malha_logica.normalizar(opcoes_malha)
    objetos_antes = set(bpy.context.scene.objects)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_curve.svg(filepath=caminho_temp)
    objetos_importados = list(set(bpy.context.scene.objects) - objetos_antes)
    
    colecao_ativa = bpy.context.scene.collection
    for obj in objetos_importados:
        obj.hide_set(False)
        obj.hide_viewport = False
        for col in obj.users_collection:
            try: col.objects.unlink(obj)
            except: pass
        if obj.name not in colecao_ativa.objects:
            colecao_ativa.objects.link(obj)

    malhas_convertidas = []
    for obj in objetos_importados:
        if obj.type in ['Curve', 'CURVE']:
            # Poucos pontos no SVG = trechos Bézier longos; com a resolução do importador a curva vira
            # um polígono facetado. Só aumenta, nunca reduz.
            if opcoes_malha["tratar"]:
                try:
                    obj.data.resolution_u = max(obj.data.resolution_u, opcoes_malha["resolucao_curva"])
                    for spline in obj.data.splines:
                        spline.resolution_u = max(spline.resolution_u, opcoes_malha["resolucao_curva"])
                except Exception as e:
                    print(f">>> Aviso: resolução da curva não ajustada ({e})", flush=True)
            mesh_data = bpy.data.meshes.new_from_object(obj)
            novo_mesh_obj = bpy.data.objects.new(obj.name.replace(".00", "_mesh"), mesh_data)
            novo_mesh_obj.matrix_world = obj.matrix_world.copy()
            
            colecao_ativa.objects.link(novo_mesh_obj)
            bpy.data.objects.remove(obj, do_unlink=True)
            malhas_convertidas.append(novo_mesh_obj)
        elif obj.type == 'MESH':
            malhas_convertidas.append(obj)

    bpy.context.view_layer.update()
    if os.path.exists(caminho_temp): os.remove(caminho_temp)
    return malhas_convertidas

# ------------------------------------------------------------------------------
# Tratamento da malha (depois da conversão e da extrusão): limpeza -> dissolve limitado ->
# bevel -> tampas sem triângulos finos -> normais. As decisões (limites, quais arestas) ficam em
# malha_logica.py; aqui só o que depende de bpy/bmesh.
# ------------------------------------------------------------------------------
def _aplicar_modificador(obj, mod):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except RuntimeError:
        depsgraph_eval = bpy.context.evaluated_depsgraph_get()
        mesh_eval = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph_eval))
        obj.modifiers.remove(mod)
        obj.data = mesh_eval


def _limpar_bm(bm, dist_m, orientar):
    import bmesh
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist_m)
    bmesh.ops.dissolve_degenerate(bm, dist=dist_m, edges=bm.edges[:])
    ruins = [f for f in bm.faces if f.calc_area() < 1e-12]
    if ruins:
        bmesh.ops.delete(bm, geom=ruins, context='FACES')
    soltas = [e for e in bm.edges if not e.link_faces]
    if soltas:
        bmesh.ops.delete(bm, geom=soltas, context='EDGES')
    sobras = [v for v in bm.verts if not v.link_edges]
    if sobras:
        bmesh.ops.delete(bm, geom=sobras, context='VERTS')
    if orientar and bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        # malha fechada com volume negativo = normais para dentro
        if all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])


def _marcar_arestas_bevel(bm, bordas, espessura_m):
    """Peso de bevel 1.0 só nas arestas tampa plana x parede no topo/base. Retorna quantas."""
    camada = bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")
    for e in bm.edges:
        e[camada] = 0.0
    if not bm.verts:
        return 0
    bm.normal_update()
    zs = [v.co.z for v in bm.verts]
    z_min, z_max = min(zs), max(zs)
    tol = max(espessura_m * 0.05, 1e-6)
    marcadas = 0
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        classe = malha_logica.classificar_aresta(f1.normal.z, f2.normal.z, e.verts[0].co.z, e.verts[1].co.z,
                                                 z_min, z_max, tol)
        if malha_logica.aresta_recebe_bevel(classe, bordas):
            e[camada] = 1.0
            marcadas += 1
    return marcadas


def _suavizar_so_curvas(bm, graus):
    """Faces suaves e arestas acima do ângulo viram 'sharp': as faces planas continuam retas."""
    limite = math.radians(graus)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) != 2:
            e.smooth = False
        else:
            e.smooth = e.calc_face_angle(0.0) <= limite


def tratar_malha_objeto(obj, regra, tipo_material, opcoes_malha):
    """Limpeza, dissolve limitado, bevel das bordas e normais. Nunca derruba a montagem: se uma etapa
    falhar, avisa no log e segue com a malha que tem."""
    op = malha_logica.normalizar(opcoes_malha)
    if not op["tratar"] or obj.type != 'MESH' or len(obj.data.polygons) == 0:
        return
    import bmesh
    espessura = float(regra.get('extrusao', 0.0))
    nome = obj.name
    v0, f0 = len(obj.data.vertices), len(obj.data.polygons)
    v1, f1 = v0, f0
    marcadas, largura, largura_mm = 0, 0.0, 0.0
    try:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        _limpar_bm(bm, malha_logica.limitar_merge_m(op["merge_mm"], espessura), espessura > 0)
        v1, f1 = len(bm.verts), len(bm.faces)
        if op["dissolve"] and op["dissolve_graus"] > 0:
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(op["dissolve_graus"]),
                                     use_dissolve_boundaries=False, verts=bm.verts[:], edges=bm.edges[:],
                                     delimit={'MATERIAL'})
        v2, f2 = len(bm.verts), len(bm.faces)
        largura = 0.0
        if op["bevel"] and espessura > 0 and malha_logica.peca_recebe_bevel(tipo_material, op["bevel_pecas"]):
            largura = malha_logica.largura_bevel_m(op["bevel_mm"], espessura, op["bevel_bordas"])
            if largura > 0:
                marcadas = _marcar_arestas_bevel(bm, op["bevel_bordas"], espessura)
        bm.to_mesh(obj.data)
        bm.free()
    except Exception as e:
        print(f">>> Aviso: tratamento de malha (limpeza/dissolve) falhou em {nome}: {e}", flush=True)
        return
    v2, f2 = len(obj.data.vertices), len(obj.data.polygons)

    if largura > 0 and marcadas > 0:
        try:
            mod = obj.modifiers.new(name="bordas", type='BEVEL')
            mod.width = largura
            mod.segments = op["bevel_segmentos"]
            mod.limit_method = 'WEIGHT'
            mod.affect = 'EDGES'
            mod.profile = 0.5
            mod.use_clamp_overlap = True
            mod.loop_slide = True
            mod.harden_normals = True
            _aplicar_modificador(obj, mod)
            largura_mm = largura * 1000.0
        except Exception as e:
            print(f">>> Aviso: bevel falhou em {nome}: {e}", flush=True)
    v3, f3 = len(obj.data.vertices), len(obj.data.polygons)

    try:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # tampas: n-gons viram triângulos pelo método beauty (sem faces finas e longas)
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        pequenos = [f for f in ngons if len(f.verts) <= malha_logica.LIMITE_NGON_BEAUTY]
        grandes = [f for f in ngons if len(f.verts) > malha_logica.LIMITE_NGON_BEAUTY]
        if pequenos:
            bmesh.ops.triangulate(bm, faces=pequenos, quad_method='BEAUTY', ngon_method='BEAUTY')
        if grandes:
            bmesh.ops.triangulate(bm, faces=grandes, quad_method='BEAUTY', ngon_method='EAR_CLIP')
        if espessura > 0 and bm.faces:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if op["suavizar"]:
            _suavizar_so_curvas(bm, op["suavizar_graus"])
        bm.to_mesh(obj.data)
        bm.free()
        if op["suavizar"] and espessura > 0:
            mod = obj.modifiers.new(name="normais", type='WEIGHTED_NORMAL')
            mod.keep_sharp = True
            mod.weight = 50
            mod.mode = 'FACE_AREA'
            mod.thresh = 0.01
            _aplicar_modificador(obj, mod)
    except Exception as e:
        print(f">>> Aviso: triangulação/normais falharam em {nome}: {e}", flush=True)
    v4, f4 = len(obj.data.vertices), len(obj.data.polygons)
    print(f">>> Malha {nome}: vértices/faces antes {v0}/{f0} | limpeza {v1}/{f1} | dissolve {v2}/{f2} | "
          f"bevel {v3}/{f3} ({marcadas} arestas, {largura_mm:.2f} mm) | final {v4}/{f4}", flush=True)


def mapear_e_ordenar_elementos(objetos_importados, dados_extraidos):
    def obter_id_numerico(obj):
        match = re.search(r'trofeu_shape_(\d+)', obj.name)
        return int(match.group(1)) if match else 9999

    elementos_mapeados = []
    for idx, obj in enumerate(objetos_importados):
        num_id = obter_id_numerico(obj)
        nome_base = f"trofeu_shape_{num_id}" if num_id != 9999 else f"trofeu_shape_{idx+1}"
        
        dados = dados_extraidos.get(nome_base, {'contorno': '#fefefe', 'preenchimento': 'Nenhum'})
        cor_contorno = dados.get('contorno', '#fefefe').lower().strip()
        
        if cor_contorno not in REGRAS_MATERIAIS:
            cor_contorno = '#fefefe'
            
        regra = REGRAS_MATERIAIS[cor_contorno]
        tipo_material = regra['tipo']
        eh_base = tipo_material in ['BASE', 'BASE_FINA']
            
        elementos_mapeados.append({
            'obj': obj,
            'nome_base': nome_base,
            'dados': dados,
            'regra': regra,
            'tipo_material': tipo_material,
            'indice_svg': num_id if num_id != 9999 else idx,
            'eh_base': eh_base
        })

    elementos_mapeados.sort(key=lambda x: (0 if x['eh_base'] else 1, x['indice_svg']))
    return elementos_mapeados

def aplicar_materiais_e_empilhar(elementos_mapeados, imagens_disponiveis, usar_verniz,usar_textura, opcoes_malha=None):
    print(f">>> Aplicando materiais, texturas e extrusões...", flush=True)
    idx_imagem_global = 0
    suporte_dos_objetos = {}

    for item in elementos_mapeados:
        obj = item['obj']
        nome_base = item['nome_base']
        dados = item['dados']
        regra = item['regra']
        tipo_material = item['tipo_material']

        # --- CÁLCULO DE EMPILHAMENTO E COLISÃO ---
        if tipo_material != 'MDF_COSTAS':
            min_x, max_x, min_y, max_y = obter_caixa_de_colisao(obj)
            pontos_de_teste = []
            matriz, matriz_inv = obj.matrix_world, obj.matrix_world.inverted()
            for v in obj.data.vertices:
                pontos_de_teste.append(( (matriz @ v.co).x, (matriz @ v.co).y ))
            
            passo_x = (max_x - min_x)/10.0 if max_x > min_x else 0.001
            passo_y = (max_y - min_y)/10.0 if max_y > min_y else 0.001
            for i in range(11):
                for j in range(11):
                    px, py = min_x + (i*passo_x), min_y + (j*passo_y)
                    or_loc = matriz_inv @ mathutils.Vector((px, py, 1.0))
                    tg_loc = matriz_inv @ mathutils.Vector((px, py, 0.0))
                    if obj.ray_cast(or_loc, (tg_loc - or_loc).normalized())[0]:
                        pontos_de_teste.append((px, py))

            depsgraph = bpy.context.evaluated_depsgraph_get()
            obj.hide_set(True)
            bpy.context.view_layer.update()
            altura_alvo_z = 0.0
            objeto_abaixo = None 
            
            for px, py in pontos_de_teste:
                ray_scene = bpy.context.scene.ray_cast(depsgraph, mathutils.Vector((px, py, 10.0)), mathutils.Vector((0, 0, -1)))
                if ray_scene[0] and ray_scene[1].z >= altura_alvo_z:
                    altura_alvo_z = ray_scene[1].z
                    objeto_abaixo = ray_scene[4] 
                        
            obj.hide_set(False)
            obj.location.z = altura_alvo_z
            suporte_dos_objetos[obj.name] = objeto_abaixo.name if objeto_abaixo else None
        
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.update()

        if tipo_material == 'ADESIVO': criar_uv_perfeito(obj)
        
        # --- EXTRUSÃO ---
        if regra['extrusao'] > 0:
            mod_solidify = obj.modifiers.new(name="extrusao", type='SOLIDIFY')
            mod_solidify.thickness = regra['extrusao']
            mod_solidify.offset = 1.0 
            mod_solidify.use_even_offset = True    
            mod_solidify.use_quality_normals = True 
            mod_solidify.solidify_mode = 'NON_MANIFOLD' 
            try:
                bpy.ops.object.modifier_apply(modifier=mod_solidify.name)
            except RuntimeError:
                depsgraph_eval = bpy.context.evaluated_depsgraph_get()
                object_eval = obj.evaluated_get(depsgraph_eval)
                mesh_eval = bpy.data.meshes.new_from_object(object_eval)
                obj.modifiers.remove(mod_solidify)
                obj.data = mesh_eval
                bpy.context.view_layer.update()
            
            # Garante que as coordenadas procedurais leiam a escala 1:1 real
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # --- TRATAMENTO DA MALHA (escala já aplicada: as medidas em mm valem) ---
        tratar_malha_objeto(obj, regra, tipo_material, opcoes_malha)

        # --- OBTENÇÃO DA COR DE PREENCHIMENTO ---
        preenchimento_val = dados.get('preenchimento', 'Nenhum')
        if not preenchimento_val or preenchimento_val == 'Nenhum' or preenchimento_val.lower() == '#ffffff':
            if tipo_material in ['MDF', 'MDF_COSTAS','BASE']:
                cor_preenchimento_hex = COR_PADRAO_MDF_HEX
            else:
                cor_preenchimento_hex = '#000000'
        else:
            cor_preenchimento_hex = preenchimento_val

        cor_svg_rgba = hex_para_rgba(cor_preenchimento_hex)

        obj.data.materials.clear()
        nome_mat_unico = f"Mat_{regra['nome_material']}_{cor_preenchimento_hex.replace('#', '')}"
        if tipo_material == 'ADESIVO': 
            nome_mat_unico = f"Mat_Adesivo_{nome_base}"

        mat = bpy.data.materials.get(nome_mat_unico)
        
        # --- CRIAÇÃO OU ATUALIZAÇÃO DO MATERIAL ---
        if tipo_material in ['MDF', 'MDF_COSTAS', 'BASE'] and usar_textura:
            if not mat:
                mat = bpy.data.materials.new(name=nome_mat_unico)
            aplicar_textura_mdf_procedural(mat, cor_svg_rgba)

        elif tipo_material == 'ACRILICO_GRAVADO':
            if not mat:
                mat = bpy.data.materials.new(name=nome_mat_unico)
            # Chama a função passando a cor lida do preenchimento SVG (ou esbranquiçada)
            aplicar_material_acrilico_gravado(mat, cor_svg_rgba)
            
        else:
            if not mat:
                mat = bpy.data.materials.new(name=nome_mat_unico)
                mat.use_nodes = True
                nodes, links = mat.node_tree.nodes, mat.node_tree.links

                if tipo_material == 'ACRILICO':
                    node_principled = nodes.get("Principled BSDF")
                    if node_principled: nodes.remove(node_principled)
                    bsdf = nodes.new('ShaderNodeBsdfGlossy')
                    bsdf.location = (10, 300)
                    node_output = nodes.get("Material Output")
                    links.new(bsdf.outputs['BSDF'], node_output.inputs['Surface'])
                    pino_cor = 'Color' 
                else:
                    bsdf = nodes.get("Principled BSDF")
                    pino_cor = 'Base Color' 

                if tipo_material == 'ADESIVO' and imagens_disponiveis:
                    caminho_imagem = imagens_disponiveis[idx_imagem_global % len(imagens_disponiveis)]
                    idx_imagem_global += 1 
                    img_nome_arquivo = os.path.basename(caminho_imagem)
                    img_blender = bpy.data.images.get(img_nome_arquivo) or (bpy.data.images.load(filepath=caminho_imagem) if os.path.exists(caminho_imagem) else None)
                    
                    tex_node = nodes.new('ShaderNodeTexImage')
                    if img_blender: tex_node.image = img_blender
                    tex_node.location = (-600, 300)

                    hsv_node = nodes.new(type="ShaderNodeHueSaturation")
                    hsv_node.location = (-300, 300)
                    hsv_node.inputs['Value'].default_value = FATOR_ESCURECIMENTO_ADESIVO
                    
                    links.new(tex_node.outputs['Color'], hsv_node.inputs['Color'])
                    links.new(hsv_node.outputs['Color'], bsdf.inputs[pino_cor])
                else:
                    if preenchimento_val != 'Nenhum':
                        if tipo_material == 'ADESIVO':
                            cor_escurecida = (cor_svg_rgba[0]*FATOR_ESCURECIMENTO_ADESIVO, cor_svg_rgba[1]*FATOR_ESCURECIMENTO_ADESIVO, cor_svg_rgba[2]*FATOR_ESCURECIMENTO_ADESIVO, cor_svg_rgba[3])
                            bsdf.inputs[pino_cor].default_value = cor_escurecida
                        else:
                            bsdf.inputs[pino_cor].default_value = cor_svg_rgba

        # --- APLICAÇÃO FORÇADA DE PROPRIEDADES FÍSICAS (ROUGHNESS, TRANSMISSION E IOR) ---
        # Executado SEMPRE fora do "if not mat", garantindo que materiais existentes recebam as regras ativas
        if mat and mat.use_nodes:
            nodes = mat.node_tree.nodes
            bsdf = nodes.get("Principled BSDF") or next((n for n in nodes if n.type == 'BSDF_GLOSSY'), None)

            if bsdf:
                # 1. Ajuste de Roughness (com suporte a Verniz no MDF/Base)
                roughness_final = 0.01 if (usar_verniz and tipo_material in ['MDF', 'MDF_COSTAS', 'BASE']) else regra.get('roughness', 0.5)
                if 'Roughness' in bsdf.inputs: 
                    bsdf.inputs['Roughness'].default_value = roughness_final

                # 2. Ajuste de Transmission (apenas no Principled BSDF)
                if tipo_material != 'ACRILICO':
                    if 'Transmission Weight' in bsdf.inputs: 
                        bsdf.inputs['Transmission Weight'].default_value = regra.get('transmission', 0.0)
                    elif 'Transmission' in bsdf.inputs: 
                        bsdf.inputs['Transmission'].default_value = regra.get('transmission', 0.0)

                # 3. Ajuste de IOR (Índice de Refração)
                if 'IOR' in bsdf.inputs and 'ior' in regra: 
                    bsdf.inputs['IOR'].default_value = regra['ior']

        obj.data.materials.append(mat)
        bpy.context.view_layer.update()

    return suporte_dos_objetos

def erguer_corpo_principal_do_trofeu(elementos_mapeados, suporte_dos_objetos):
    def esta_apoiado_na_base(obj_name):
        atual = obj_name
        visitados = set() 
        while atual and atual not in visitados:
            visitados.add(atual)
            for item in elementos_mapeados:
                try:
                    if item['obj'] and item['obj'].name == atual:
                        if item['tipo_material'] in ['BASE', 'BASE_FINA']: return True 
                        elif item['tipo_material'] in ['MDF', 'MDF_COSTAS']: return False 
                except (ReferenceError, AttributeError): continue
            atual = suporte_dos_objetos.get(atual)
        return False

    pecas_corpo = []
    status_rotacao = {}

    for item in elementos_mapeados:
        try:
            obj = item['obj']
            if not obj or obj.name not in bpy.data.objects: continue

            t_mat = item['tipo_material']
            nome_obj = obj.name
            deve_rotacionar = True 
            abaixo = suporte_dos_objetos.get(nome_obj)
            
            apoiado_direto_na_base = False
            if abaixo:
                for i in elementos_mapeados:
                    try:
                        if i['obj'] and i['obj'].name == abaixo and i['tipo_material'] in ['BASE', 'BASE_FINA']:
                            apoiado_direto_na_base = True
                            break
                    except ReferenceError: continue

            if t_mat in ['BASE', 'BASE_FINA', 'MDF_COSTAS']: deve_rotacionar = False  
            elif t_mat in ['ACRILICO', 'ADESIVO', 'RESINA_AREA']:
                if apoiado_direto_na_base or esta_apoiado_na_base(nome_obj): deve_rotacionar = False
                elif abaixo and abaixo in status_rotacao and not status_rotacao[abaixo]: deve_rotacionar = False
                else: deve_rotacionar = True
            else:
                if abaixo and abaixo in status_rotacao and not status_rotacao[abaixo]: deve_rotacionar = True

            status_rotacao[nome_obj] = deve_rotacionar
            if deve_rotacionar: pecas_corpo.append(obj)
        except (ReferenceError, AttributeError): pass

    if pecas_corpo:
        bpy.context.view_layer.update() 
        min_y = min_z = float('inf')
        for obj in pecas_corpo:
            for v in obj.bound_box:
                coord = obj.matrix_world @ mathutils.Vector(v)
                if coord.y < min_y: min_y = coord.y
                if coord.z < min_z: min_z = coord.z
        pivo = mathutils.Vector((0.0, min_y, min_z))
        mat_ida = mathutils.Matrix.Translation(pivo)
        mat_rotacao = mathutils.Matrix.Rotation(math.radians(90), 4, 'X')
        mat_volta = mathutils.Matrix.Translation(-pivo)
        matriz_final = mat_ida @ mat_rotacao @ mat_volta
        for obj in pecas_corpo:
            obj.matrix_world = matriz_final @ obj.matrix_world

    print("Troféu base montado e alinhado com sucesso!", flush=True)
    return pecas_corpo

def processar_mdf_costas(elementos_mapeados, pecas_corpo, suporte_dos_objetos):
    for item in elementos_mapeados:
        if item['tipo_material'] == 'MDF_COSTAS':
            obj_costas = item['obj']
            if not obj_costas or obj_costas.name not in bpy.data.objects: continue
                
            bpy.context.view_layer.update()
            obj_costas.hide_set(False)
            obj_costas.hide_viewport = False
            
            bpy.ops.object.select_all(action='DESELECT')
            obj_costas.select_set(True)
            bpy.context.view_layer.objects.active = obj_costas
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
            bpy.context.view_layer.update()

            pecas_rotacionadas = [p for p in pecas_corpo if p and p.name in bpy.data.objects]
            
            if pecas_rotacionadas:
                max_y_traseiro = float('-inf')
                for p_obj in pecas_rotacionadas:
                    cantos_p = [p_obj.matrix_world @ mathutils.Vector(v) for v in p_obj.bound_box]
                    max_y_traseiro = max(max_y_traseiro, max(v.y for v in cantos_p))
                
                cantos_costas = [obj_costas.matrix_world @ mathutils.Vector(v) for v in obj_costas.bound_box]
                min_y_costas = min(v.y for v in cantos_costas)
                
                min_y_global_svg = min(min(v.y for v in [p.matrix_world @ mathutils.Vector(v_b) for v_b in p.bound_box]) for p in pecas_rotacionadas)
                altura_z = abs(min_y_costas - min_y_global_svg)
                
                old_y = obj_costas.location.y
                old_z = obj_costas.location.z
                
                obj_costas.location.y += (max_y_traseiro - min_y_costas) + 0.001
                obj_costas.location.z = altura_z
                bpy.context.view_layer.update()
                
                delta_y = obj_costas.location.y - old_y
                delta_z = obj_costas.location.z - old_z
                
                for item_dep in elementos_mapeados:
                    if item_dep['obj'] and suporte_dos_objetos.get(item_dep['obj'].name) == obj_costas.name:
                        obj_filho = item_dep['obj']
                        obj_filho.location.y += delta_y
                        obj_filho.location.z += delta_z
                        bpy.context.view_layer.update()

def processar_resina_3d(elementos_mapeados, suporte_dos_objetos, caminho_modelo_resina, objetos_importados):
    dados_resina_pendente = next((i for i in elementos_mapeados if i['tipo_material'] == 'RESINA_AREA'), None)

    if not dados_resina_pendente or not caminho_modelo_resina or not os.path.exists(caminho_modelo_resina):
        return

    obj_marcado_svg = dados_resina_pendente['obj']
    if not obj_marcado_svg or obj_marcado_svg.name not in bpy.data.objects: return
        
    bpy.context.view_layer.update()
    sup_nome = suporte_dos_objetos.get(obj_marcado_svg.name)
    obj_sup = bpy.data.objects.get(sup_nome) if sup_nome else None

    rot_z_original = obj_marcado_svg.rotation_euler.z

    cantos_guia = [obj_marcado_svg.matrix_world @ mathutils.Vector(v) for v in obj_marcado_svg.bound_box]
    dx = max(v.x for v in cantos_guia) - min(v.x for v in cantos_guia)
    dy = max(v.y for v in cantos_guia) - min(v.y for v in cantos_guia)
    dz = max(v.z for v in cantos_guia) - min(v.z for v in cantos_guia)
    
    dimensoes = sorted([dx, dy, dz], reverse=True)
    largura_svg = dimensoes[0]
    altura_svg = dimensoes[1]
    
    centro_x_guia = sum(v.x for v in cantos_guia) / 8.0
    centro_y_guia = sum(v.y for v in cantos_guia) / 8.0
    centro_z_guia = sum(v.z for v in cantos_guia) / 8.0

    extensao = os.path.splitext(caminho_modelo_resina)[1].lower()
    objs_antes_import = set(bpy.context.scene.objects)
    
    try:
        if extensao in ['.obj', '.wavefront']:
            try: bpy.ops.import_scene.obj(filepath=caminho_modelo_resina)
            except AttributeError:
                janelas = bpy.context.window_manager.windows
                if janelas:
                    window = janelas[0]
                    area_3d = next((a for a in window.screen.areas if a.type == 'VIEW_3D'), window.screen.areas[0])
                    with bpy.context.temp_override(window=window, area=area_3d):
                        bpy.ops.wm.obj_import(filepath=caminho_modelo_resina)
                else:
                    bpy.ops.wm.obj_import(filepath=caminho_modelo_resina)
        elif extensao == '.fbx': bpy.ops.import_scene.fbx(filepath=caminho_modelo_resina, use_custom_props=False)
        elif extensao == '.stl': bpy.ops.wm.stl_import(filepath=caminho_modelo_resina)
        elif extensao == '.blend':
            with bpy.data.libraries.load(caminho_modelo_resina, link=False) as (data_from, data_to):
                data_to.objects = data_from.objects
            for obj_carregado in data_to.objects:
                if obj_carregado: bpy.context.scene.collection.objects.link(obj_carregado)
    except Exception as e_import:
        print(f"❌ Erro ao importar resina: {e_import}", flush=True)

    novos_objs = list(set(bpy.context.scene.objects) - objs_antes_import)
    malhas_resina = [o for o in novos_objs if o.type == 'MESH']
    
    if malhas_resina:
        resina_3d_obj = malhas_resina[0]
        
        preenchimento_val = dados_resina_pendente['dados'].get('preenchimento', 'Nenhum')
        regra_resina = dados_resina_pendente['regra']
        resina_3d_obj.data.materials.clear()
        nome_mat_resina = f"Mat_Resina_{dados_resina_pendente['nome_base']}"
        mat_resina = bpy.data.materials.new(name=nome_mat_resina)
        mat_resina.use_nodes = True
        nodes = mat_resina.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            if preenchimento_val != 'Nenhum': bsdf.inputs['Base Color'].default_value = hex_para_rgba(preenchimento_val)
            if 'Roughness' in bsdf.inputs: bsdf.inputs['Roughness'].default_value = regra_resina.get('roughness', 0.05)
            if 'Transmission Weight' in bsdf.inputs: bsdf.inputs['Transmission Weight'].default_value = regra_resina.get('transmission', 0.9)
            elif 'Transmission' in bsdf.inputs: bsdf.inputs['Transmission'].default_value = regra_resina.get('transmission', 0.9)
            if 'IOR' in bsdf.inputs and 'ior' in regra_resina: bsdf.inputs['IOR'].default_value = regra_resina['ior']
        
        resina_3d_obj.data.materials.append(mat_resina)
        resina_3d_obj.hide_set(False)
        resina_3d_obj.hide_viewport = False
        bpy.ops.object.select_all(action='DESELECT')
        resina_3d_obj.select_set(True)
        bpy.context.view_layer.objects.active = resina_3d_obj
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        bpy.context.view_layer.update()

        eh_na_base = False
        sup_atual = obj_marcado_svg.name
        visitados = set()
        while sup_atual and sup_atual not in visitados:
            visitados.add(sup_atual)
            pai_nome = suporte_dos_objetos.get(sup_atual)
            if pai_nome:
                item_pai = next((i for i in elementos_mapeados if i['obj'] and i['obj'].name == pai_nome), None)
                if item_pai and 'BASE' in item_pai['tipo_material'].upper():
                    eh_na_base = True
                    break
                sup_atual = pai_nome
            else: break

        correcao_frente = 0.0

        if eh_na_base:
            resina_3d_obj.rotation_euler = (0.0, 0.0, -rot_z_original + correcao_frente)
            bpy.context.view_layer.update()

            cantos_kart = [resina_3d_obj.matrix_world @ mathutils.Vector(v) for v in resina_3d_obj.bound_box]
            larg_kart = max(v.x for v in cantos_kart) - min(v.x for v in cantos_kart)
            prof_kart = max(v.y for v in cantos_kart) - min(v.y for v in cantos_kart)

            if larg_kart > 0.0001 and prof_kart > 0.0001:
                escala = min(largura_svg / larg_kart, altura_svg / prof_kart)
                resina_3d_obj.scale = (resina_3d_obj.scale.x * escala, resina_3d_obj.scale.y * escala, resina_3d_obj.scale.z * escala)
                bpy.context.view_layer.update()

            cantos_finais = [resina_3d_obj.matrix_world @ mathutils.Vector(v) for v in resina_3d_obj.bound_box]
            cx = sum(v.x for v in cantos_finais) / 8.0
            cy = sum(v.y for v in cantos_finais) / 8.0
            min_z_res = min(v.z for v in cantos_finais)
            max_z_sup = max((obj_sup.matrix_world @ mathutils.Vector(v)).z for v in obj_sup.bound_box) if obj_sup else centro_z_guia

            resina_3d_obj.location.x += (centro_x_guia - cx)
            resina_3d_obj.location.y += (centro_y_guia - cy)
            resina_3d_obj.location.z += (max_z_sup - min_z_res) + 0.001

        else:
            resina_3d_obj.rotation_euler = (math.radians(90), 0.0, -rot_z_original + correcao_frente)
            bpy.context.view_layer.update()

            cantos_kart = [resina_3d_obj.matrix_world @ mathutils.Vector(v) for v in resina_3d_obj.bound_box]
            larg_kart = max(v.x for v in cantos_kart) - min(v.x for v in cantos_kart)
            alt_kart = max(v.z for v in cantos_kart) - min(v.z for v in cantos_kart)

            if larg_kart > 0.0001 and alt_kart > 0.0001:
                escala = min(largura_svg / larg_kart, altura_svg / alt_kart)
                resina_3d_obj.scale = (resina_3d_obj.scale.x * escala, resina_3d_obj.scale.y * escala, resina_3d_obj.scale.z * escala)
                bpy.context.view_layer.update()

            cantos_finais = [resina_3d_obj.matrix_world @ mathutils.Vector(v) for v in resina_3d_obj.bound_box]
            cx = sum(v.x for v in cantos_finais) / 8.0
            cz = sum(v.z for v in cantos_finais) / 8.0
            max_y_res = max(v.y for v in cantos_finais)
            min_y_sup = min((obj_sup.matrix_world @ mathutils.Vector(v)).y for v in obj_sup.bound_box) if obj_sup else centro_y_guia

            resina_3d_obj.location.x += (centro_x_guia - cx)
            resina_3d_obj.location.z += (centro_z_guia - cz)
            resina_3d_obj.location.y += (min_y_sup - max_y_res) - 0.001

        bpy.context.view_layer.update()
        objetos_importados.append(resina_3d_obj)

    try:
        if obj_marcado_svg and obj_marcado_svg.name in bpy.data.objects:
            bpy.data.objects.remove(obj_marcado_svg, do_unlink=True)
    except (ReferenceError, KeyError): pass

def configurar_cameras(objetos_importados, cameras_para_renderizar=None):
    objetos_validos_cena = []
    
    # Filtra estritamente apenas as malhas ativas do troféu
    for obj in objetos_importados:
        try:
            if obj and hasattr(obj, "name") and obj.name in bpy.data.objects and obj.type == 'MESH':
                nome_lc = obj.name.lower()
                if not any(ign in nome_lc for ign in ["estudio", "chao", "ground", "studio", "wall", "fundo", "cenario"]):
                    objetos_validos_cena.append(obj)
        except (ReferenceError, RuntimeError): continue

    if not objetos_validos_cena:
        for obj in bpy.context.scene.objects:
            try:
                if obj.type == 'MESH' and not obj.hide_get() and hasattr(obj, "bound_box"):
                    nome_lc = obj.name.lower()
                    if not any(ign in nome_lc for ign in ["estudio", "chao", "ground", "studio", "wall", "fundo", "cenario"]):
                        objetos_validos_cena.append(obj)
            except (ReferenceError, RuntimeError): continue

    if not objetos_validos_cena:
        print("⚠️ Nenhuma malha do troféu encontrada para enquadramento das câmeras.", flush=True)
        return []

    bpy.context.view_layer.update()
    render = bpy.context.scene.render
    render.resolution_x = 1080
    render.resolution_y = 1350
    aspect_ratio = render.resolution_x / render.resolution_y
    
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')

    for obj in objetos_validos_cena:
        try:
            for v in obj.bound_box:
                coord = obj.matrix_world @ mathutils.Vector(v)
                min_x = min(min_x, coord.x)
                max_x = max(max_x, coord.x)
                min_y = min(min_y, coord.y)
                max_y = max(max_y, coord.y)
                min_z = min(min_z, coord.z)
                max_z = max(max_z, coord.z)
        except (ReferenceError, RuntimeError): continue

    if min_x == float('inf') or max_z == float('-inf'):
        print("⚠️ Não foi possível calcular o centro dos objetos.", flush=True)
        return []

    alvo_centro = mathutils.Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
    tamanho_x, tamanho_y, tamanho_z = max_x - min_x, max_y - min_y, max_z - min_z

    dummy_cam_data = bpy.data.cameras.new("temp_cam")
    fov = dummy_cam_data.angle
    bpy.data.cameras.remove(dummy_cam_data)

    tamanho_real = max(tamanho_z, tamanho_x / aspect_ratio) if aspect_ratio > 1 else max(tamanho_x, tamanho_z * aspect_ratio)
    
    MARGEM_ENQUADRAMENTO = 1.6
    distancia_base = (tamanho_real / 2.0) / math.tan(fov / 2.0) * MARGEM_ENQUADRAMENTO

    ponto_focal_alvo = alvo_centro.copy()   
    ponto_focal_alvo.z += tamanho_z * 0.00  
    altura_camera = alvo_centro.z + (tamanho_z * 0.15)  

    def criar_e_apontar_camera(nome, local_vetor, focal_vetor):
        cam_obj = bpy.data.objects.get(nome)
        if not cam_obj:
            cam_data = bpy.data.cameras.new(name=nome)
            cam_obj = bpy.data.objects.new(nome, cam_data)
            bpy.context.scene.collection.objects.link(cam_obj)
        cam_obj.data.type = 'PERSP'
        cam_obj.location = local_vetor
        direcao = focal_vetor - cam_obj.location
        cam_obj.rotation_euler = direcao.to_track_quat('-Z', 'Y').to_euler()
        return cam_obj

    pos_cam_principal = mathutils.Vector((alvo_centro.x, min_y - distancia_base, altura_camera))
    cam_principal = criar_e_apontar_camera("Camera_Principal", pos_cam_principal, ponto_focal_alvo) 

    angulo_diag = math.radians(35)
    dist_lateral = distancia_base * 1.2

    criar_e_apontar_camera(
        "Camera_Esquerda",
        mathutils.Vector((alvo_centro.x - (dist_lateral * math.sin(angulo_diag)), alvo_centro.y - (dist_lateral * math.cos(angulo_diag)), altura_camera)),
        ponto_focal_alvo
    )
    
    criar_e_apontar_camera(
        "Camera_Direita",
        mathutils.Vector((alvo_centro.x + (dist_lateral * math.sin(angulo_diag)), alvo_centro.y - (dist_lateral * math.cos(angulo_diag)), altura_camera)),
        ponto_focal_alvo
    )

    bpy.context.scene.camera = cam_principal
    todas_cameras_criadas = ["Camera_Principal", "Camera_Esquerda", "Camera_Direita"]

    if cameras_para_renderizar:
        if isinstance(cameras_para_renderizar, str):
            if cameras_para_renderizar.strip().lower() in ['todas', 'all', '']:
                return todas_cameras_criadas
            else:
                lista_desejada = [c.strip() for c in cameras_para_renderizar.split(',')]
                return [c for c in todas_cameras_criadas if c in lista_desejada]
        elif isinstance(cameras_para_renderizar, (list, tuple)):
            return [c for c in todas_cameras_criadas if c in cameras_para_renderizar]

    return todas_cameras_criadas

def renderizar_cena(cameras_nomes, pasta_saida_renders, cycles_samples):
    pasta_dest = pasta_saida_renders
    if not os.path.exists(pasta_dest): os.makedirs(pasta_dest)
    
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    
    try:
        cycles_prefs = bpy.context.preferences.addons['cycles'].preferences
        cycles_prefs.compute_device_type = 'NONE'
        scene.cycles.device = 'CPU'
    except Exception: pass
        
    total_samples = int(cycles_samples)
    scene.cycles.samples = total_samples
    scene.cycles.use_denoising = True

    cameras_validas = [(nome, bpy.data.objects.get(nome)) for nome in cameras_nomes if bpy.data.objects.get(nome)]
    n_cams = len(cameras_validas)
    print(f"PTM_PLANO {total_samples} {n_cams} {','.join(nome for nome, _ in cameras_validas)}", flush=True)
    print(f"PTM_PASSADAS {'principal,freestyle' if _freestyle_ligado(scene) else 'principal'}", flush=True)

    # O Blender 5.3 em --background não imprime mais as linhas "Fra:... | Sample N/M" (e o que ele
    # imprime pelo C chega atrasado, em bloco). Os handlers do render (render_init, render_stats,
    # render_complete) imprimem os marcadores PTM_* com flush, sem depender da saída do Cycles.
    registrados = []
    for nome_handler, funcao in _HANDLERS_RENDER:
        lista = getattr(bpy.app.handlers, nome_handler, None)
        if lista is not None and funcao not in lista:
            lista.append(funcao)
            registrados.append((lista, funcao))
    try:
        for idx_cam, (nome_cam, cam) in enumerate(cameras_validas):
            scene.camera = cam
            scene.render.filepath = os.path.join(pasta_dest, f"{nome_cam}.png")
            _estado_render.update(passada="principal", ultimo=None)
            print(f"PTM_CAMERA {idx_cam + 1}/{n_cams} {nome_cam}", flush=True)
            print(f">>> Renderizando câmera: {nome_cam} via Cycles...", flush=True)
            # As samples são as que o próprio Cycles informa ao render_stats; nada é simulado aqui.
            bpy.ops.render.render(write_still=True)
            print(f"PTM_CAMERA_FIM {idx_cam + 1}/{n_cams} {nome_cam}", flush=True)
    finally:
        for lista, funcao in registrados:
            if funcao in lista:
                lista.remove(funcao)

    print(f"Renders salvos em: {pasta_dest}", flush=True)


def _freestyle_ligado(scene):
    """O Freestyle (contornos) faz o Cycles renderizar cada câmera numa 2ª passada."""
    try:
        if not getattr(scene.render, "use_freestyle", False):
            return False
        camadas = list(getattr(scene, "view_layers", []) or [])
        return not camadas or any(getattr(c, "use_freestyle", True) for c in camadas)
    except Exception:
        return False


# passada atual da câmera ('principal' ou 'freestyle') e o último texto do render_stats
_estado_render = {"passada": "principal", "ultimo": None}
_RE_SAMPLE_STATS = re.compile(r"\bSample (\d+)\s*/\s*(\d+)")
_RE_RESTANTE_STATS = re.compile(r"Remaining:\s*(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)")


def _ptm_render_init(*args):
    """Handler render_init: começo do render de uma câmera."""
    try:
        _estado_render.update(passada="principal", ultimo=None)
        print("PTM_RENDER_INICIO", flush=True)
    except Exception:
        pass


def _ptm_render_post(*args):
    """Handler render_post: fim do render do quadro (para o log)."""
    try:
        print("PTM_RENDER_POS", flush=True)
    except Exception:
        pass


def _ptm_render_complete(*args):
    """Handler render_complete: o render da câmera terminou (a imagem já foi gravada)."""
    try:
        print("PTM_RENDER_FIM", flush=True)
    except Exception:
        pass


def _ptm_render_stats(*args):
    """Handler render_stats: as samples do Cycles viram PTM_SAMPLES (atuais, totais, passada e o
    'Remaining' em segundos); o texto vai também como PTM_STATS (sem repetir o mesmo texto)."""
    try:
        texto = next((a for a in args if isinstance(a, str)), "")
        texto = " ".join(texto.split())
        if not texto or texto == _estado_render["ultimo"]:
            return
        _estado_render["ultimo"] = texto
        if "Freestyle" in texto and _estado_render["passada"] != "freestyle":
            _estado_render["passada"] = "freestyle"
            print("PTM_PASSADA freestyle", flush=True)
        m = _RE_SAMPLE_STATS.search(texto)
        if m:
            linha = f"PTM_SAMPLES {int(m.group(1))} {int(m.group(2))} {_estado_render['passada']}"
            r = _RE_RESTANTE_STATS.search(texto)
            if r:
                seg = int(r.group(1) or 0) * 3600 + int(r.group(2)) * 60 + float(r.group(3))
                linha += f" {seg:.2f}"
            print(linha, flush=True)
        print(f"PTM_STATS {texto}", flush=True)
    except Exception:
        pass


_HANDLERS_RENDER = [("render_init", _ptm_render_init), ("render_stats", _ptm_render_stats),
                    ("render_post", _ptm_render_post), ("render_complete", _ptm_render_complete)]

# ==============================================================================
# 4. FUNÇÃO PRINCIPAL (ORQUESTRADOR)
# ==============================================================================

def processar_svg_no_blender(
    caminho_svg, 
    pasta_saida_renders, 
    caminho_blend="", 
    renderizar=True, 
    usar_textura=True, 
    cycles_samples=128, 
    usar_verniz=False, 
    caminho_modelo_resina="",
    cameras_para_renderizar=None,
    opcoes_malha=None
):
    opcoes_malha = malha_logica.normalizar(opcoes_malha)
    marcar_etapa("estudio", "Abrindo o estúdio base")
    carregar_estudio_e_hdri(caminho_blend)
    marcar_etapa("svg", "Lendo e importando o SVG")
    caminho_temp, dados_extraidos, imagens_disponiveis = analisar_e_preparar_svg(caminho_svg)
    if not caminho_temp: return

    objetos_importados = importar_e_converter_svg(caminho_temp, opcoes_malha)
    elementos_mapeados = mapear_e_ordenar_elementos(objetos_importados, dados_extraidos)
    marcar_etapa("materiais", "Aplicando materiais, texturas e extrusões")
    suporte_dos_objetos = aplicar_materiais_e_empilhar(elementos_mapeados, imagens_disponiveis, usar_verniz,usar_textura, opcoes_malha)
    marcar_etapa("montagem", "Montando o troféu (corpo, costas e resina)")
    pecas_corpo = erguer_corpo_principal_do_trofeu(elementos_mapeados, suporte_dos_objetos)
    processar_mdf_costas(elementos_mapeados, pecas_corpo, suporte_dos_objetos)
    processar_resina_3d(elementos_mapeados, suporte_dos_objetos, caminho_modelo_resina, objetos_importados)

    marcar_etapa("cameras", "Posicionando as câmeras")
    cameras_filtradas = configurar_cameras(objetos_importados, cameras_para_renderizar)

    if renderizar and pasta_saida_renders and cameras_filtradas:
        marcar_etapa("render", "Renderizando as câmeras")
        renderizar_cena(cameras_filtradas, pasta_saida_renders, cycles_samples)
    else:
        print(">>> Modo interativo ativo ou nenhuma câmera válida foi selecionada.", flush=True)
    marcar_etapa("final", "Finalizando")
    print("PTM_FIM", flush=True)

if __name__ == "__main__":
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
        caminho_svg = argv[0] if len(argv) > 0 else ""
        pasta_saida = argv[1] if len(argv) > 1 else ""
        caminho_blend = argv[2] if len(argv) > 2 else ""
        
        renderizar_automaticamente = True
        if len(argv) > 3: renderizar_automaticamente = argv[3].strip().lower() in ['true', '1', 'yes']
            
        usar_textura = True
        if len(argv) > 4: usar_textura = argv[4].strip().lower() in ['true', '1', 'yes']
            
        cycles_samples = 128
        if len(argv) > 5:
            try: cycles_samples = int(argv[5])
            except: cycles_samples = 128
            
        usar_verniz = True
        if len(argv) > 6: usar_verniz = argv[6].strip().lower() in ['true', '1', 'yes']
            
        caminho_modelo_resina = ""
        if len(argv) > 7: caminho_modelo_resina = argv[7]

        cameras_para_renderizar = None
        if len(argv) > 8 and argv[8].strip():
            cameras_para_renderizar = argv[8]

        opcoes_malha = malha_logica.de_texto(argv[9]) if len(argv) > 9 else malha_logica.normalizar()

        processar_svg_no_blender(
            caminho_svg, 
            pasta_saida, 
            caminho_blend, 
            renderizar_automaticamente, 
            usar_textura, 
            cycles_samples, 
            usar_verniz, 
            caminho_modelo_resina,
            cameras_para_renderizar,
            opcoes_malha
        )