"""python -m lighthouse          -> app (ventana Control + salidas de video)
python -m lighthouse --test   -> self-check del motor con señal sintética (exit 0/1)
python -m lighthouse --pantalla [--puerto N] [--monitor N] [--logo ruta.png]  -> receptor de la TV remota
"""
import logging
import logging.handlers
import os
import platform
import sys
import threading
import traceback

from . import VERSION

log = logging.getLogger("lighthouse")


def setup_logging():
    d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "LightHouse", "logs")
    os.makedirs(d, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(os.path.join(d, "lighthouse.log"), maxBytes=1_000_000,
                                             backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(h)


def install_hooks():
    from .ui import report
    sys.excepthook = report
    threading.excepthook = lambda a: report(a.exc_type, a.exc_value, a.exc_traceback, "hilo " + str(a.thread))

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    setup_logging()
    if "--test" in argv:
        from .selftest import selftest
        try:
            selftest()
        except Exception:
            traceback.print_exc()
            log.exception("self-check falló")
            return 1
        log.info("self-check ok")
        return 0
    if "--pantalla" in argv:
        from . import pantalla
        install_hooks()
        return pantalla.main([a for a in argv if a != "--pantalla"])
    log.info("arranque LightHouse %s · Python %s · %s", VERSION, platform.python_version(), platform.platform())
    install_hooks()
    sys.setswitchinterval(0.001)  # el hilo de audio suelta el GIL al render en ≤ 1 ms (default 5 ms)
    from . import win32
    win32.set_dpi_aware()  # antes de crear Tk(): monitores y geometrías en píxeles físicos
    from .ui import App
    try:
        App().root.mainloop()
    finally:
        win32.keep_awake(False)  # también si App() o el mainloop lanzan
    return 0


if __name__ == "__main__":
    sys.exit(main())