"""Galeria das imagens geradas pelo Blender (pasta "imagens 3d" ao lado do SVG), sem interface.

- listar_imagens(pasta): as imagens da pasta, com câmera, tamanho, dimensões e data.
- miniatura(caminho): a imagem reduzida (com o Pillow, opcional, do requirements-opcional.txt)
  ou, sem o Pillow, a original (a tela limita o tamanho por CSS), como data URI para o <img> da
  tela web. As reduzidas ficam em cache no disco (.cache_miniaturas/, no .gitignore), com a data
  e o tamanho do arquivo no nome: imagem regravada pelo Blender gera uma miniatura nova.
- imagem_completa(caminho): a original como data URI (para a imagem ampliada).
- Última pasta de saída (.ultimo_render.json, no .gitignore): a galeria mostra o último render
  também quando o app abre.

Não importa tkinter nem webview; o Pillow só é importado na primeira miniatura.
"""
import base64
import datetime
import hashlib
import json
import os
import struct
import threading

import registro_erros

EXTENSOES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
TIPOS_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".bmp": "image/bmp"}
# Ordem das câmeras do blender_engine (as imagens se chamam <câmera>.png)
ORDEM_CAMERAS = ("Camera_Principal", "Camera_Esquerda", "Camera_Direita")
LADO_MINIATURA = 320                      # px do lado maior da miniatura
LIMITE_ORIGINAL = 40 * 1024 * 1024        # sem o Pillow, a original só vai à tela até este tamanho
ARQUIVO_ULTIMO = ".ultimo_render.json"
PASTA_CACHE = ".cache_miniaturas"         # na pasta do projeto (no .gitignore)
MAXIMO_CACHE = 600                        # miniaturas no disco; passando disso, apaga as mais antigas


# ------------------------------------------------------------------ última pasta de saída
PASTA_PROJETO = registro_erros.PASTA_PROJETO    # onde fica o .ultimo_render.json (os testes trocam)


def caminho_ultimo(pasta_projeto=None):
    return os.path.join(pasta_projeto or PASTA_PROJETO, ARQUIVO_ULTIMO)


def gravar_ultima_saida(pasta_saida, pasta_projeto=None):
    """Guarda a pasta do render que começou (para a galeria mostrar ao abrir o app). Nunca levanta erro."""
    try:
        caminho = caminho_ultimo(pasta_projeto)
        with open(caminho + ".novo", "w", encoding="utf-8") as f:
            json.dump({"pasta": pasta_saida}, f, ensure_ascii=False)
        os.replace(caminho + ".novo", caminho)
        return True
    except (OSError, TypeError, ValueError):
        return False


def ler_ultima_saida(pasta_projeto=None):
    """Pasta do último render, se ela ainda existir; senão ''."""
    try:
        with open(caminho_ultimo(pasta_projeto), "r", encoding="utf-8") as f:
            pasta = json.load(f).get("pasta", "")
    except (OSError, ValueError, AttributeError):
        return ""
    return pasta if isinstance(pasta, str) and pasta and os.path.isdir(pasta) else ""


def pasta_da_galeria(svg_selecionado, output_path, pasta_projeto=None):
    """Com um SVG escolhido, a pasta de saída dele; senão, a do último render ('' se nenhuma)."""
    if svg_selecionado and output_path and os.path.isdir(output_path):
        return output_path
    return ler_ultima_saida(pasta_projeto)


# ------------------------------------------------------------------ dimensões sem o Pillow
def dimensoes(caminho):
    """(largura, altura) lidas do cabeçalho do PNG, JPEG, WEBP ou BMP; (0, 0) se não der."""
    try:
        with open(caminho, "rb") as f:
            cab = f.read(32)
            if cab[:8] == b"\x89PNG\r\n\x1a\n" and cab[12:16] == b"IHDR":
                return struct.unpack(">II", cab[16:24])
            if cab[:2] == b"BM" and len(cab) >= 26:
                largura, altura = struct.unpack("<ii", cab[18:26])
                return largura, abs(altura)
            if cab[:4] == b"RIFF" and cab[8:12] == b"WEBP":
                f.seek(12)
                bloco = f.read(30)
                tipo = bloco[:4]
                if tipo == b"VP8 ":
                    w, h = struct.unpack("<HH", bloco[14:18])
                    return w & 0x3FFF, h & 0x3FFF
                if tipo == b"VP8L":
                    b = bloco[9:13]
                    w = 1 + (((b[1] & 0x3F) << 8) | b[0])
                    h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
                    return w, h
                if tipo == b"VP8X":
                    return 1 + int.from_bytes(bloco[12:15], "little"), 1 + int.from_bytes(bloco[15:18], "little")
                return 0, 0
            if cab[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    marca = f.read(2)
                    if len(marca) < 2 or marca[0] != 0xFF:
                        return 0, 0
                    tipo = marca[1]
                    if tipo in (0xD8, 0x01) or 0xD0 <= tipo <= 0xD7:
                        continue
                    tam = struct.unpack(">H", f.read(2))[0]
                    if tipo in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        altura, largura = struct.unpack(">xHH", f.read(5))
                        return largura, altura
                    f.seek(tam - 2, 1)
    except (OSError, struct.error, IndexError, ValueError):
        pass
    return 0, 0


# ------------------------------------------------------------------ lista
def texto_tamanho(n):
    """'850 KB', '2,4 MB' (vírgula, como no Brasil)."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{round(n / 1024)} KB"
    return f"{n / (1024 * 1024):.1f} MB".replace(".", ",")


def nome_camera(arquivo):
    """'Camera_Principal.png' -> 'Camera Principal'."""
    return os.path.splitext(arquivo)[0].replace("_", " ").strip()


def _ordem(nome):
    base = os.path.splitext(nome)[0]
    return (ORDEM_CAMERAS.index(base) if base in ORDEM_CAMERAS else len(ORDEM_CAMERAS), nome.lower())


def listar_imagens(pasta):
    """Imagens da pasta (câmeras na ordem do Blender, depois as outras por nome). Cada uma:
    {'chave', 'caminho', 'arquivo', 'camera', 'bytes', 'tamanho', 'largura', 'altura',
    'dimensoes', 'data', 'mtime'}. A chave muda quando a imagem é regravada."""
    if not pasta or not os.path.isdir(pasta):
        return []
    try:
        nomes = os.listdir(pasta)
    except OSError:
        return []
    itens = []
    for nome in sorted(nomes, key=_ordem):
        if not nome.lower().endswith(EXTENSOES) or nome.startswith("."):
            continue
        caminho = os.path.join(pasta, nome)
        try:
            st = os.stat(caminho)
        except OSError:
            continue
        if not os.path.isfile(caminho) or st.st_size == 0:
            continue
        largura, altura = dimensoes(caminho)
        itens.append({
            "chave": f"{nome}|{st.st_mtime_ns}|{st.st_size}",
            "caminho": caminho,
            "arquivo": nome,
            "camera": nome_camera(nome),
            "bytes": st.st_size,
            "tamanho": texto_tamanho(st.st_size),
            "largura": largura,
            "altura": altura,
            "dimensoes": f"{largura} × {altura}" if largura and altura else "",
            "data": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M"),
            "mtime": st.st_mtime,
        })
    return itens


def para_js(item):
    """O que a tela recebe de cada imagem (sem o caminho do PC)."""
    return {k: item[k] for k in ("chave", "arquivo", "camera", "tamanho", "dimensoes", "data", "largura", "altura")}


# ------------------------------------------------------------------ imagens para a tela
_PIL = {"carregado": False, "Image": None}
_TRAVA_PIL = threading.Lock()


def pillow():
    """O módulo PIL.Image, se o Pillow estiver instalado; senão None (importado uma vez só)."""
    with _TRAVA_PIL:
        if not _PIL["carregado"]:
            _PIL["carregado"] = True
            try:
                from PIL import Image
                _PIL["Image"] = Image
            except Exception:
                _PIL["Image"] = None
    return _PIL["Image"]


def _data_uri(dados, mime):
    return f"data:{mime};base64," + base64.b64encode(dados).decode("ascii")


def _mime(caminho):
    return TIPOS_MIME.get(os.path.splitext(caminho)[1].lower(), "application/octet-stream")


# ------------------------------------------------------------------ cache das miniaturas no disco
def pasta_cache(pasta_projeto=None):
    return os.path.join(pasta_projeto or PASTA_PROJETO, PASTA_CACHE)


def _nomes_cache(caminho, lado, so_png):
    """(prefixo, versão) do arquivo no cache: o prefixo identifica a imagem e o tamanho pedido;
    a versão é a data e o tamanho do arquivo (muda quando a imagem é regravada)."""
    st = os.stat(caminho)
    ident = f"{os.path.normcase(os.path.abspath(caminho))}|{lado}|{'png' if so_png else 'auto'}"
    prefixo = hashlib.sha1(ident.encode("utf-8", "surrogatepass")).hexdigest()[:20]
    return prefixo, f"{st.st_mtime_ns}-{st.st_size}"


def _ler_cache(pasta, prefixo, versao):
    for ext, mime in ((".jpg", "image/jpeg"), (".png", "image/png")):
        try:
            with open(os.path.join(pasta, f"{prefixo}-{versao}{ext}"), "rb") as f:
                dados = f.read()
            if dados:
                return dados, mime
        except OSError:
            continue
    return None


def _gravar_cache(pasta, prefixo, versao, dados, mime):
    """Grava a miniatura e apaga as versões velhas da mesma imagem (e as mais antigas, se o
    cache passar do máximo). Erros (disco cheio, pasta sem permissão) são ignorados."""
    try:
        os.makedirs(pasta, exist_ok=True)
        destino = os.path.join(pasta, f"{prefixo}-{versao}{'.png' if mime == 'image/png' else '.jpg'}")
        with open(destino + ".novo", "wb") as f:
            f.write(dados)
        os.replace(destino + ".novo", destino)
        nomes = os.listdir(pasta)
        for nome in nomes:
            if nome.startswith(prefixo + "-") and os.path.join(pasta, nome) != destino:
                try:
                    os.remove(os.path.join(pasta, nome))
                except OSError:
                    pass
        if len(nomes) > MAXIMO_CACHE:
            arquivos = []
            for nome in os.listdir(pasta):
                try:
                    arquivos.append((os.path.getmtime(os.path.join(pasta, nome)), nome))
                except OSError:
                    pass
            arquivos.sort()
            for _, nome in arquivos[:max(0, len(arquivos) - MAXIMO_CACHE * 5 // 6)]:
                try:
                    os.remove(os.path.join(pasta, nome))
                except OSError:
                    pass
    except OSError:
        pass


def _reduzir(caminho, lado, image, so_png):
    try:
        import io
        with image.open(caminho) as img:
            img.thumbnail((lado, lado))
            saida = io.BytesIO()
            if so_png or img.mode in ("RGBA", "LA", "P"):
                img.save(saida, "PNG", optimize=True)
                return saida.getvalue(), "image/png"
            img.convert("RGB").save(saida, "JPEG", quality=85)
            return saida.getvalue(), "image/jpeg"
    except Exception:
        return None


def bytes_miniatura(caminho, lado=LADO_MINIATURA, image=None, so_png=False, cache=None):
    """(bytes, mime) da imagem reduzida com o Pillow (PNG se tiver transparência ou com so_png,
    para o PhotoImage do Tk; senão JPEG), ou None sem o Pillow ou se ele não abrir a imagem.
    Usa o cache do disco (cache: a pasta; padrão .cache_miniaturas na pasta do projeto)."""
    image = image if image is not None else pillow()
    if image is None:
        return None
    pasta = cache or pasta_cache()
    try:
        prefixo, versao = _nomes_cache(caminho, lado, so_png)
    except OSError:
        return None
    guardada = _ler_cache(pasta, prefixo, versao)
    if guardada is not None:
        return guardada
    reduzida = _reduzir(caminho, lado, image, so_png)
    if reduzida is not None:
        _gravar_cache(pasta, prefixo, versao, *reduzida)
    return reduzida


class Cache:
    """Guarda as últimas imagens já convertidas (chave -> data URI), para não reler do disco."""

    def __init__(self, maximo=24):
        self.maximo = maximo
        self._dados = {}
        self._trava = threading.Lock()

    def pegar(self, chave):
        with self._trava:
            valor = self._dados.pop(chave, None)
            if valor is not None:
                self._dados[chave] = valor         # vai para o fim (o mais recente)
            return valor

    def guardar(self, chave, valor):
        with self._trava:
            self._dados.pop(chave, None)
            self._dados[chave] = valor
            while len(self._dados) > self.maximo:
                self._dados.pop(next(iter(self._dados)))


def miniatura(caminho, lado=LADO_MINIATURA, image=None, limite=LIMITE_ORIGINAL, cache=None):
    """{'ok', 'src', 'reduzida'}: a miniatura feita no Python (Pillow, com cache no disco) ou,
    sem ele, a original."""
    reduzida = bytes_miniatura(caminho, lado, image, cache=cache)
    if reduzida is not None:
        return {"ok": True, "src": _data_uri(*reduzida), "reduzida": True}
    resultado = imagem_completa(caminho, limite)
    resultado["reduzida"] = False
    return resultado


def imagem_completa(caminho, limite=LIMITE_ORIGINAL):
    """{'ok', 'src'}: a imagem original como data URI (se não passar do limite)."""
    try:
        if os.path.getsize(caminho) > limite:
            return {"ok": False, "erro": "imagem grande demais para mostrar aqui (use Abrir pasta)"}
        with open(caminho, "rb") as f:
            return {"ok": True, "src": _data_uri(f.read(), _mime(caminho))}
    except OSError as e:
        return {"ok": False, "erro": f"não deu para ler a imagem: {e}"}


def cameras_prontas(estado):
    """Quantas câmeras já terminaram, no estado do nucleo.ProgressoRender (evento 'progresso')."""
    return sum(1 for e in (estado or {}).get("etapas", []) if str(e.get("id", "")).startswith("camera:")
               and e.get("estado") == "concluida")
