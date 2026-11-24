"""Entrada do PathToMesh: abre a interface web (pywebview + WebView2, app_web.py).

Se o pywebview não estiver instalado, se o WebView2 faltar no Windows ou se a janela web não
abrir, grava um log de erro e abre a interface Tkinter (app_ui.py), que continua como reserva.
Com --tk, abre direto a interface Tkinter.

O launcher abre este arquivo.
"""
import sys
import traceback

import registro_erros

ORIGEM = "app"

# Chave do runtime do WebView2 (Evergreen) no registro do Windows
_CHAVE_WEBVIEW2 = r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_CHAVE_WEBVIEW2_32 = r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def webview2_instalado(winreg=None):
    """True se o runtime do WebView2 está instalado (no Windows). Fora do Windows, True (lá o
    pywebview usa outro motor). Sem o módulo winreg, True (quem decide é o pywebview)."""
    if winreg is None:
        if sys.platform != "win32":
            return True
        try:
            import winreg
        except ImportError:
            return True
    for raiz, chave in ((winreg.HKEY_LOCAL_MACHINE, _CHAVE_WEBVIEW2_32), (winreg.HKEY_LOCAL_MACHINE, _CHAVE_WEBVIEW2),
                        (winreg.HKEY_CURRENT_USER, _CHAVE_WEBVIEW2)):
        try:
            with winreg.OpenKey(raiz, chave) as k:
                versao, _ = winreg.QueryValueEx(k, "pv")
            if versao and str(versao) != "0.0.0.0":
                return True
        except OSError:
            continue
    return False


def abrir_web():
    """Abre a interface web (levanta exceção se não der)."""
    import app_web
    app_web.iniciar()


def abrir_reserva():
    """Abre a interface Tkinter (app_ui.py)."""
    import app_ui
    app_ui.executar()


def main(argv=None, abrir_web=abrir_web, abrir_reserva=abrir_reserva, webview2_instalado=webview2_instalado):
    """Devolve 'web' ou 'tk' (a interface que foi aberta)."""
    argv = sys.argv[1:] if argv is None else argv
    if "--tk" in argv:
        abrir_reserva()
        return "tk"

    motivo, detalhes = None, ""
    try:
        import webview  # noqa: F401
    except Exception as e:
        motivo, detalhes = f"o pywebview não está instalado ou não carregou ({type(e).__name__}: {e})", traceback.format_exc()
    if motivo is None and not webview2_instalado():
        motivo = "o WebView2 (motor do Edge usado pela janela) não está instalado neste Windows"
        detalhes = "Instale o 'Microsoft Edge WebView2 Runtime' (gratuito, da Microsoft) e abra o app de novo."
    if motivo is None:
        try:
            abrir_web()
            return "web"
        except Exception as e:
            motivo, detalhes = f"a interface web não abriu ({type(e).__name__}: {e})", traceback.format_exc()

    registro_erros.gravar_log(ORIGEM, "Interface web indisponível: " + motivo,
                              "O app abriu a interface Tkinter (reserva) no lugar da interface web.\n\n" + detalhes)
    abrir_reserva()
    return "tk"


if __name__ == "__main__":
    registro_erros.instalar_ganchos(ORIGEM)
    main()
