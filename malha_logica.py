"""Lógica pura (sem bpy) do tratamento de malha: opções, limites e decisões.

O blender_engine.py usa estas funções com bmesh; aqui fica o que dá para testar fora do Blender:
valores padrão, limites (clamp), texto passado ao Blender, quanto de bevel/merge cada peça aguenta
e quais arestas recebem bevel.
"""
import math

# Valores padrão e limites (mínimo, máximo). Larguras e distâncias em milímetros, ângulos em graus.
PADROES = {
    "tratar": False,           # DESLIGADO por padrão; liga o tratamento inteiro (limpeza, dissolve, bevel, normais)
    "merge_mm": 0.01,          # merge by distance
    "dissolve": True,          # dissolve limitado
    "dissolve_graus": 5.0,
    "arredondar": False,       # "Arredondar bordas da base" (bevel leve): DESLIGADO por padrão e INDEPENDENTE de "tratar"
    "bevel_mm": 0.5,
    "bevel_segmentos": 5,
    "bevel_bordas": "ambos",   # topo | base | ambos
    "bevel_pecas": "base",     # base (só a peça de base) | todas
    "suavizar": True,          # sombreamento suave só nas partes curvas + Weighted Normal
    "suavizar_graus": 30.0,
    "resolucao_curva": 24,     # resolução (pontos por trecho) das curvas do SVG; nunca abaixo da do importador
}
LIMITES = {
    "merge_mm": (0.0, 0.5),
    "dissolve_graus": (0.0, 20.0),
    "bevel_mm": (0.0, 2.0),
    "bevel_segmentos": (1, 12),
    "suavizar_graus": (5.0, 80.0),
    "resolucao_curva": (4, 64),
}
OPCOES_BORDAS = ("topo", "base", "ambos")
OPCOES_PECAS = ("base", "todas")
BEVEL_MIN_MM = 0.05            # abaixo disso o bevel não vale a pena (peça muito fina): pula
FRACAO_ESPESSURA_MERGE = 0.1   # o merge nunca passa de 10% da espessura da peça
FRACAO_ESPESSURA_BEVEL = 0.4   # bevel de um lado: <= 40% da parede (ambos os lados: 2 x 40% < 100%)
LIMITE_NGON_BEAUTY = 64        # n-gons maiores usam ear clip (beauty é lento)

_BOOLS = ("tratar", "dissolve", "arredondar", "suavizar")


def _num(valor, padrao, minimo, maximo, tipo=float):
    try:
        v = tipo(float(str(valor).replace(",", ".")))
    except (TypeError, ValueError):
        return padrao
    if v != v or v in (float("inf"), float("-inf")):
        return padrao
    return max(minimo, min(maximo, v))


def _bool(valor, padrao):
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return padrao
    t = str(valor).strip().lower()
    if t in ("1", "true", "sim", "yes", "on"):
        return True
    if t in ("0", "false", "nao", "não", "no", "off"):
        return False
    return padrao


def normalizar(dados=None):
    """Dicionário completo e válido (o que faltar ou vier errado volta ao padrão; números ficam nos limites)."""
    if not isinstance(dados, dict):
        dados = {}
    r = {}
    for k, padrao in PADROES.items():
        v = dados.get(k, padrao)
        if k in _BOOLS:
            r[k] = _bool(v, padrao)
        elif k == "bevel_bordas":
            r[k] = str(v).strip().lower() if str(v).strip().lower() in OPCOES_BORDAS else padrao
        elif k == "bevel_pecas":
            r[k] = str(v).strip().lower() if str(v).strip().lower() in OPCOES_PECAS else padrao
        else:
            mn, mx = LIMITES[k]
            tipo = int if isinstance(padrao, int) and not isinstance(padrao, bool) else float
            r[k] = _num(v, padrao, mn, mx, tipo)
    return r


def para_texto(dados=None):
    """Texto 'chave=valor;chave=valor' (um só argumento da linha de comando do Blender)."""
    n = normalizar(dados)
    return ";".join(f"{k}={int(v) if isinstance(v, bool) else v}" for k, v in n.items())


def de_texto(texto):
    dados = {}
    for parte in str(texto or "").split(";"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            dados[k.strip()] = v.strip()
    return normalizar(dados)


def limitar_merge_m(merge_mm, espessura_m):
    """Distância do merge em metros, sem passar de 10% da espessura (senão uma peça de 0,1 mm colapsa)."""
    m = merge_mm / 1000.0
    if espessura_m and espessura_m > 0:
        m = min(m, espessura_m * FRACAO_ESPESSURA_MERGE)
    return max(0.0, m)


def bordas_ativas(bordas):
    """(topo, base) conforme a opção."""
    return bordas in ("topo", "ambos"), bordas in ("base", "ambos")


def largura_bevel_m(largura_mm, espessura_m, bordas="ambos"):
    """Largura do bevel em metros, limitada pela parede (0 = não fazer bevel).
    Com topo e base juntos, cada bevel pega no máximo 40% da parede (sobra reto no meio)."""
    if largura_mm <= 0 or espessura_m <= 0:
        return 0.0
    topo, base = bordas_ativas(bordas)
    if not (topo or base):
        return 0.0
    fracao = FRACAO_ESPESSURA_BEVEL if (topo and base) else FRACAO_ESPESSURA_BEVEL * 2
    w = min(largura_mm / 1000.0, espessura_m * fracao)
    return w if w * 1000.0 >= BEVEL_MIN_MM else 0.0


def peca_recebe_bevel(tipo_material, bordas_pecas):
    if bordas_pecas == "todas":
        return True
    return tipo_material in ("BASE", "BASE_FINA")


def classificar_aresta(nz1, nz2, z1, z2, z_min, z_max, tol_z, cos_tampa=0.98, max_nz_parede=0.2):
    """'topo', 'base' ou None para uma aresta entre duas faces (nz = componente Z da normal de cada uma,
    z1/z2 = Z dos extremos da aresta). Vale só a aresta entre uma tampa plana (|nz| ~ 1) e uma parede
    (|nz| ~ 0) que esteja no plano do topo ou da base. Não depende da orientação das normais."""
    a1, a2 = abs(nz1), abs(nz2)
    cap_parede = (a1 >= cos_tampa and a2 <= max_nz_parede) or (a2 >= cos_tampa and a1 <= max_nz_parede)
    if not cap_parede:
        return None
    if abs(z1 - z_min) <= tol_z and abs(z2 - z_min) <= tol_z:
        return "base"
    if abs(z1 - z_max) <= tol_z and abs(z2 - z_max) <= tol_z:
        return "topo"
    return None


def aresta_recebe_bevel(classe, bordas):
    topo, base = bordas_ativas(bordas)
    return (classe == "topo" and topo) or (classe == "base" and base)


def angulo_minimo_triangulo(p1, p2, p3):
    """Menor ângulo interno (graus) de um triângulo 2D/3D; perto de 0 = triângulo fino e longo."""
    def d(a, b):
        return math.dist(a, b)
    a, b, c = d(p2, p3), d(p1, p3), d(p1, p2)
    if min(a, b, c) <= 0:
        return 0.0
    def ang(x, y, z):  # ângulo oposto ao lado x
        v = (y * y + z * z - x * x) / (2 * y * z)
        return math.degrees(math.acos(max(-1.0, min(1.0, v))))
    return min(ang(a, b, c), ang(b, a, c), ang(c, a, b))
