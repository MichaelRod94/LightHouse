"""python -m lighthouse          -> app (ventana Control + ventana Luz)
python -m lighthouse --test   -> self-check del motor con señal sintética (exit 0/1)
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
        return 0
    log.info("arranque LightHouse %s · Python %s · %s", VERSION, platform.python_version(), platform.platform())
    install_hooks()
    from .ui import App
    App().root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())