"""Todo el ctypes del proyecto (Windows): prioridad del proceso; en fases siguientes teclas, monitores..."""
import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger(__name__)
BELOW_NORMAL, NORMAL = 0x4000, 0x20

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
_k32.SetPriorityClass.restype = wintypes.BOOL


def set_low_priority(on: bool) -> bool:
    """Prioridad del proceso BELOW_NORMAL (on) o NORMAL: rekordbox en la misma laptop siempre gana."""
    ok = bool(_k32.SetPriorityClass(_k32.GetCurrentProcess(), BELOW_NORMAL if on else NORMAL))
    if ok:
        log.info("prioridad del proceso: %s", "por debajo de lo normal" if on else "normal")
    else:
        log.warning("SetPriorityClass falló (error %d)", ctypes.get_last_error())
    return ok
