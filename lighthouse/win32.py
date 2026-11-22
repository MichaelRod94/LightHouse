"""Todo el ctypes del proyecto (Windows): prioridad, teclado, DPI, monitores, keep-awake y rectángulos."""
import ctypes
import logging
import os
import re
from ctypes import wintypes
from typing import NamedTuple

log = logging.getLogger(__name__)
BELOW_NORMAL, NORMAL = 0x4000, 0x20
ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x1, 0x2

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
_k32.SetThreadExecutionState.argtypes = (wintypes.DWORD,)
_k32.SetThreadExecutionState.restype = wintypes.DWORD
_MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
_u32.EnumDisplayMonitors.argtypes = (wintypes.HDC, ctypes.c_void_p, _MONITORENUMPROC, wintypes.LPARAM)
_u32.EnumDisplayMonitors.restype = wintypes.BOOL
_u32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_u32.GetWindowRect.restype = wintypes.BOOL
_PID = os.getpid()


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


_u32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(_MONITORINFOEXW))
_u32.GetMonitorInfoW.restype = wintypes.BOOL


class Monitor(NamedTuple):
    device: str  # \\.\DISPLAYn
    x: int       # píxeles físicos (proceso DPI aware); el primario empieza en 0,0
    y: int
    w: int
    h: int
    primary: bool

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
    """La ventana al frente es de este proceso (cualquiera: Control o una salida, con o sin bordes)."""
    pid = wintypes.DWORD()
    _u32.GetWindowThreadProcessId(_u32.GetForegroundWindow(), ctypes.byref(pid))
    return pid.value == _PID


def set_dpi_aware() -> bool:
    """Per-monitor DPI aware (antes de crear Tk): geometrías y monitores en píxeles físicos, sin que
    Windows estire la ventana. Si falla (ya fijado, Windows viejo), cae al DPI aware del sistema."""
    try:
        hr = ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        if hr == 0:
            return True
        log.warning("SetProcessDpiAwareness(2) devolvió 0x%08x", hr & 0xFFFFFFFF)
    except (OSError, AttributeError):
        log.warning("shcore.SetProcessDpiAwareness no disponible")
    return bool(_u32.SetProcessDPIAware())


def monitors():
    """Monitores conectados (EnumDisplayMonitors + GetMonitorInfoW), ordenados por \\\\.\\DISPLAYn."""
    out = []

    def cb(hmon, hdc, rect, lparam):
        mi = _MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(mi)
        if _u32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            out.append(Monitor(mi.szDevice, r.left, r.top, r.right - r.left, r.bottom - r.top,
                               bool(mi.dwFlags & 1)))
        return True

    _u32.EnumDisplayMonitors(None, None, _MONITORENUMPROC(cb), 0)
    num = lambda m: int((re.findall(r"\d+", m.device) or [0])[-1])
    return sorted(out, key=lambda m: (num(m), m.device))


def keep_awake(on: bool) -> bool:
    """Pantalla y sistema sin dormirse mientras corre (powercfg /requests lo lista bajo DISPLAY).
    Es por hilo: llamar desde el hilo Tk, que vive todo el programa."""
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if on else ES_CONTINUOUS
    ok = bool(_k32.SetThreadExecutionState(flags))
    log.info("keep-awake %s%s", "activado" if on else "liberado", "" if ok else " (falló)")
    return ok


def window_rect(hwnd):
    """(x, y, w, h) de la ventana según GetWindowRect (para verificar la pantalla completa)."""
    r = wintypes.RECT()
    if not _u32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top