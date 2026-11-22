"""Todo el ctypes del proyecto (Windows): prioridad del proceso y teclado; en fases siguientes monitores..."""
import ctypes
import logging
import os
from ctypes import wintypes

log = logging.getLogger(__name__)
BELOW_NORMAL, NORMAL = 0x4000, 0x20

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
_k32.SetPriorityClass.restype = wintypes.BOOL

_u32 = ctypes.WinDLL("user32", use_last_error=True)
_u32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
_u32.GetAsyncKeyState.restype = ctypes.c_short
_u32.GetForegroundWindow.restype = wintypes.HWND
_u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_u32.GetWindowThreadProcessId.restype = wintypes.DWORD
_PID = os.getpid()

# nombres de teclas para config.json (además de "A".."Z" y "0".."9")
VK = {"SPACE": 0x20, "ADD": 0x6B, "SUBTRACT": 0x6D, "OEM_PLUS": 0xBB, "OEM_MINUS": 0xBD,
      **{f"NUMPAD{i}": 0x60 + i for i in range(10)}, **{f"F{i}": 0x6F + i for i in range(1, 25)}}


def set_low_priority(on: bool) -> bool:
    """Prioridad del proceso BELOW_NORMAL (on) o NORMAL: rekordbox en la misma laptop siempre gana."""
    ok = bool(_k32.SetPriorityClass(_k32.GetCurrentProcess(), BELOW_NORMAL if on else NORMAL))
    if ok:
        log.info("prioridad del proceso: %s", "por debajo de lo normal" if on else "normal")
    else:
        log.warning("SetPriorityClass falló (error %d)", ctypes.get_last_error())
    return ok


def vk_code(name):
    """'Q', '1', 'F1', 'NUMPAD1', 'SPACE', 'OEM_PLUS'... -> código virtual-key, o None si no se conoce."""
    n = str(name).upper()
    if len(n) == 1 and ("A" <= n <= "Z" or "0" <= n <= "9"):
        return ord(n)
    return VK.get(n)


def key_down(vk) -> bool:
    """Tecla presionada ahora mismo, tenga o no el foco esta app."""
    return bool(_u32.GetAsyncKeyState(vk) & 0x8000)


def app_in_foreground() -> bool:
    """La ventana al frente es de este proceso (cualquiera: Control, Luz o las de F5)."""
    pid = wintypes.DWORD()
    _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value == _PID
