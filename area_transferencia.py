"""Levar as imagens da galeria para outros programas (WhatsApp Desktop, Explorer, e-mail), no Windows.

- copiar(caminhos, hwnd): põe na área de transferência do Windows (ctypes, sem dependência):
  * CF_HDROP com os arquivos reais (colar no Explorer copia o arquivo; no WhatsApp/e-mail vira anexo)
    e "Preferred DropEffect" = cópia (o Explorer nunca move o original);
  * com UMA imagem, também o bitmap (CF_DIB, pelo Pillow, ou CF_BITMAP, pelo GDI+ do Windows, sem o
    Pillow; o Windows converte um no outro) e o "PNG" (os bytes do arquivo, para quem aceita
    transparência): Ctrl+V no WhatsApp ou num editor cola a imagem.
  A transparência vira fundo branco no bitmap (sem fundo preto ao colar).
- arrastar(caminhos, janela): arrastar de arquivo nativo (OLE DoDragDrop com CF_HDROP), pelo WinForms
  da janela do pywebview (o pythonnet já vem com o pywebview no Windows): Control.DoDragDrop com um
  DataObject de FileDrop, na thread da janela. O arrasto sai da janela do WebView2 como arquivo.
- arrastar_disponivel(): se dá para arrastar neste PC (senão a tela orienta a usar Copiar imagem).

Fora do Windows (ou sem o que precisa), as funções devolvem {'ok': False, 'mensagem': ...} sem
levantar erro. A parte do Windows fica em AreaWindows (os testes trocam por uma falsa).
"""
import io
import os
import struct
import sys
import time

CF_BITMAP = 2
CF_DIB = 8
CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
DROPEFFECT_COPY = 1
FORMATO_PNG = "PNG"                          # formato registrado (Chrome, WhatsApp, Office, GIMP)
FORMATO_EFEITO = "Preferred DropEffect"
LIMITE_BITMAP = 60 * 1024 * 1024             # arquivo maior que isso vai só como arquivo (sem bitmap)

MSG_SO_WINDOWS = "Copiar e arrastar imagens só funcionam no Windows."


def eh_windows():
    return sys.platform == "win32"


# ------------------------------------------------------------------ dados dos formatos (testáveis)
def bytes_hdrop(caminhos):
    """DROPFILES (20 bytes: pFiles=20, pt=(0,0), fNC=0, fWide=1) + os caminhos em UTF-16,
    cada um terminado em \\0, e mais um \\0 no fim."""
    cabecalho = struct.pack("<IiiII", 20, 0, 0, 0, 1)
    lista = "".join(str(c) + "\0" for c in caminhos) + "\0"
    return cabecalho + lista.encode("utf-16-le")


def ler_hdrop(dados):
    """O contrário de bytes_hdrop (para os testes): a lista de caminhos."""
    p_files, _, _, _, wide = struct.unpack("<IiiII", dados[:20])
    texto = dados[p_files:].decode("utf-16-le" if wide else "mbcs")
    return [c for c in texto.split("\0") if c]


def bytes_efeito_copia():
    return struct.pack("<I", DROPEFFECT_COPY)


def bytes_dib(caminho, image=None):
    """CF_DIB (BITMAPINFOHEADER + pixels, 24 bits) da imagem, pelo Pillow; a transparência vira
    fundo branco. None sem o Pillow ou se ele não abrir a imagem."""
    if image is None:
        import galeria
        image = galeria.pillow()
    if image is None:
        return None
    try:
        with image.open(caminho) as img:
            img.load()
            if img.mode in ("RGBA", "LA", "P", "PA"):
                rgba = img.convert("RGBA")
                fundo = image.new("RGB", rgba.size, (255, 255, 255))
                fundo.paste(rgba, mask=rgba.split()[-1])
                rgb = fundo
            else:
                rgb = img.convert("RGB")
            saida = io.BytesIO()
            rgb.save(saida, "BMP")
        dados = saida.getvalue()
        return dados[14:] if dados[:2] == b"BM" else None      # sem o BITMAPFILEHEADER
    except Exception:
        return None


def bytes_png(caminho):
    """Os bytes do arquivo, se ele for PNG (para o formato "PNG"); senão None."""
    try:
        if os.path.getsize(caminho) > LIMITE_BITMAP:
            return None
        with open(caminho, "rb") as f:
            dados = f.read()
        return dados if dados[:8] == b"\x89PNG\r\n\x1a\n" else None
    except OSError:
        return None


def montar_formatos(caminhos, com_imagem=True, image=None, win=None):
    """[(formato, valor)] para a área de transferência. valor: bytes (vai num HGLOBAL) ou
    ('hbitmap', handle) (CF_BITMAP do GDI+)."""
    itens = [(CF_HDROP, bytes_hdrop(caminhos)), (FORMATO_EFEITO, bytes_efeito_copia())]
    if com_imagem and len(caminhos) == 1:
        caminho = caminhos[0]
        try:
            grande = os.path.getsize(caminho) > LIMITE_BITMAP
        except OSError:
            grande = True
        if not grande:
            dib = bytes_dib(caminho, image)
            if dib is not None:
                itens.append((CF_DIB, dib))
            elif win is not None:
                hbm = win.hbitmap(caminho)            # sem o Pillow: o GDI+ do Windows lê a imagem
                if hbm:
                    itens.append((CF_BITMAP, ("hbitmap", hbm)))
            png = bytes_png(caminho)
            if png is not None:
                itens.append((FORMATO_PNG, png))
    return itens


# ------------------------------------------------------------------ Windows (ctypes)
class AreaWindows:
    """Área de transferência do Windows por ctypes (user32, kernel32, gdi32 e gdiplus)."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self._c = ctypes
        u = self._u = ctypes.WinDLL("user32", use_last_error=True)
        k = self._k = ctypes.WinDLL("kernel32", use_last_error=True)
        self._g = ctypes.WinDLL("gdi32")
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.OpenClipboard.restype = wintypes.BOOL
        u.EmptyClipboard.restype = wintypes.BOOL
        u.CloseClipboard.restype = wintypes.BOOL
        u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u.SetClipboardData.restype = wintypes.HANDLE
        u.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        u.RegisterClipboardFormatW.restype = wintypes.UINT
        k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k.GlobalAlloc.restype = wintypes.HGLOBAL
        k.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k.GlobalFree.argtypes = [wintypes.HGLOBAL]
        k.GlobalFree.restype = wintypes.HGLOBAL
        self._g.DeleteObject.argtypes = [wintypes.HGDIOBJ]

    def _formato(self, formato):
        return formato if isinstance(formato, int) else self._u.RegisterClipboardFormatW(formato)

    def _hglobal(self, dados):
        k = self._k
        h = k.GlobalAlloc(GMEM_MOVEABLE, len(dados))
        if not h:
            return None
        p = k.GlobalLock(h)
        if not p:
            k.GlobalFree(h)
            return None
        self._c.memmove(p, dados, len(dados))
        k.GlobalUnlock(h)
        return h

    def hbitmap(self, caminho):
        """HBITMAP da imagem pelo GDI+ (transparência sobre branco), ou None."""
        c = self._c
        try:
            gdip = c.WinDLL("gdiplus")

            class Entrada(c.Structure):
                _fields_ = [("GdiplusVersion", c.c_uint32), ("DebugEventCallback", c.c_void_p),
                            ("SuppressBackgroundThread", c.c_int), ("SuppressExternalCodecs", c.c_int)]
            token = c.c_size_t(0)
            entrada = Entrada(1, None, 0, 0)
            if gdip.GdiplusStartup(c.byref(token), c.byref(entrada), None) != 0:
                return None
            try:
                bitmap = c.c_void_p()
                if gdip.GdipCreateBitmapFromFile(c.c_wchar_p(caminho), c.byref(bitmap)) != 0:
                    return None
                try:
                    hbm = c.c_void_p()
                    if gdip.GdipCreateHBITMAPFromBitmap(bitmap, c.byref(hbm), c.c_uint32(0xFFFFFFFF)) != 0:
                        return None
                    return hbm.value
                finally:
                    gdip.GdipDisposeImage(bitmap)
            finally:
                gdip.GdiplusShutdown(token)
        except Exception:
            return None

    def colocar(self, hwnd, itens, tentativas=10):
        """Esvazia a área de transferência e põe os itens. Devolve a lista dos formatos postos."""
        u = self._u
        for _ in range(tentativas):                 # outro programa pode estar com ela aberta
            if u.OpenClipboard(hwnd or None):
                break
            time.sleep(0.03)
        else:
            raise OSError("a área de transferência está ocupada por outro programa")
        postos = []
        try:
            if not u.EmptyClipboard():
                raise OSError("não deu para limpar a área de transferência")
            for formato, valor in itens:
                f = self._formato(formato)
                if isinstance(valor, tuple) and valor[0] == "hbitmap":
                    if u.SetClipboardData(f, valor[1]):
                        postos.append(formato)
                    else:
                        self._g.DeleteObject(valor[1])
                    continue
                h = self._hglobal(valor)
                if h is None:
                    continue
                if u.SetClipboardData(f, h):
                    postos.append(formato)          # agora o Windows é o dono da memória
                else:
                    self._k.GlobalFree(h)
        finally:
            u.CloseClipboard()
        return postos

    def botao_apertado(self):
        """Algum botão do mouse está apertado agora (o arrasto ainda está acontecendo)?"""
        u = self._u
        return bool((u.GetAsyncKeyState(0x01) | u.GetAsyncKeyState(0x02)) & 0x8000)


def _win_padrao():
    return AreaWindows() if eh_windows() else None


def copiar(caminhos, hwnd=0, com_imagem=True, win=None, image=None):
    """Copia os arquivos (e, com uma imagem só, o bitmap e o PNG) para a área de transferência."""
    caminhos = [c for c in caminhos if c and os.path.isfile(c)]
    if not caminhos:
        return {"ok": False, "mensagem": "Nenhuma imagem para copiar."}
    try:
        win = win if win is not None else _win_padrao()
    except Exception as e:
        return {"ok": False, "mensagem": f"A área de transferência do Windows não está disponível: {e}"}
    if win is None:
        return {"ok": False, "mensagem": MSG_SO_WINDOWS}
    itens = montar_formatos(caminhos, com_imagem, image, win)
    try:
        postos = win.colocar(hwnd, itens)
    except Exception as e:
        return {"ok": False, "mensagem": f"Não deu para copiar: {e}"}
    if CF_HDROP not in postos:
        return {"ok": False, "mensagem": "Não deu para copiar os arquivos para a área de transferência."}
    com_bitmap = CF_DIB in postos or CF_BITMAP in postos
    n = len(caminhos)
    if n == 1:
        mensagem = "Imagem copiada: cole com Ctrl+V (WhatsApp, e-mail, Explorer)." if com_bitmap else \
            "Arquivo copiado: cole com Ctrl+V (WhatsApp, e-mail, Explorer)."
    else:
        mensagem = f"{n} imagens copiadas como arquivos: cole com Ctrl+V (WhatsApp, e-mail, Explorer)."
    return {"ok": True, "mensagem": mensagem, "formatos": [str(f) for f in postos], "quantas": n}


# ------------------------------------------------------------------ arrastar (WinForms do pywebview)
def _form_da_janela(janela):
    """O Form do WinForms da janela do pywebview (janela.native), ou None."""
    form = getattr(janela, "native", None) if janela is not None else None
    return form if form is not None and hasattr(form, "DoDragDrop") and hasattr(form, "BeginInvoke") else None


def _dotnet():
    """(Action, Array, String, DataObject, DataFormats, DragDropEffects) do .NET, ou None."""
    try:
        import clr  # noqa: F401  (pythonnet: já carregado pelo pywebview no Windows)
        from System import Action, Array, String
        from System.Windows.Forms import DataFormats, DataObject, DragDropEffects
        return Action, Array, String, DataObject, DataFormats, DragDropEffects
    except Exception:
        return None


def arrastar_disponivel(janela=None, dotnet=None):
    if not eh_windows() and dotnet is None:
        return False
    if janela is not None and _form_da_janela(janela) is None:
        return False
    return (dotnet or _dotnet()) is not None


def arrastar(caminhos, janela, win=None, dotnet=None, ao_erro=None):
    """Começa o arrastar de arquivo nativo (DoDragDrop OLE com CF_HDROP) na thread da janela.
    Volta logo (o arrasto continua enquanto o botão do mouse estiver apertado)."""
    caminhos = [c for c in caminhos if c and os.path.isfile(c)]
    if not caminhos:
        return {"ok": False, "mensagem": "Nenhuma imagem para arrastar."}
    if not eh_windows() and dotnet is None:
        return {"ok": False, "mensagem": MSG_SO_WINDOWS}
    form = _form_da_janela(janela)
    net = dotnet or _dotnet()
    if form is None or net is None:
        return {"ok": False, "mensagem": "Arrastar para fora não está disponível neste PC: use Copiar imagem."}
    Action, Array, String, DataObject, DataFormats, DragDropEffects = net
    try:
        win = win if win is not None else _win_padrao()
    except Exception:
        win = None

    def fazer():
        try:
            if win is not None and not win.botao_apertado():
                return                              # o botão já foi solto: não há o que arrastar
            dados = DataObject()
            dados.SetData(DataFormats.FileDrop, Array[String](list(caminhos)))
            form.DoDragDrop(dados, DragDropEffects.Copy)
        except Exception as e:
            if ao_erro:
                ao_erro(e)

    try:
        form.BeginInvoke(Action(fazer))
    except Exception as e:
        return {"ok": False, "mensagem": f"Não deu para começar o arrasto: {e}"}
    return {"ok": True}
