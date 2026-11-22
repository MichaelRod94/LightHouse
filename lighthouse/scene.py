"""Looks del cliente y compose(): la ÚNICA función que decide colores. Puro (sin Tk ni ctypes)."""
from dataclasses import dataclass, field
from typing import NamedTuple

BLACK, WHITE = (0, 0, 0), (255, 255, 255)
BREATH_S = 8.0  # U: sube en 4 s y baja en 4 s

# id (= tecla por defecto) -> (nombre, tipo, colores). Los colores se pueden pisar en config.json.
LOOKS = {
    "1": ("Blanco", "base", ()),  # color base del panel Color (blanco, temperatura o paleta)
    "2": ("Rojo", "solid", ("#FF0000",)),
    "3": ("Azul", "solid", ("#0030FF",)),
    "4": ("Morado", "solid", ("#8000FF",)),
    "5": ("Verde", "solid", ("#00FF00",)),
    "6": ("Amarillo", "solid", ("#FFD000",)),
    "7": ("Arcoíris", "rainbow", ("#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0000FF", "#4B0082", "#8F00FF")),
    "Q": ("Blanco/Rojo", "strobe", ("#FFFFFF", "#FF0000")),
    "W": ("Blanco/Morado", "strobe", ("#FFFFFF", "#8000FF")),
    "E": ("Mitad roja", "split", ("#FF0000",)),
    "R": ("Mitad morada", "split", ("#8000FF",)),
    "T": ("Mitad verde", "split", ("#00FF00",)),
    "Y": ("Mitad azul", "split", ("#0030FF",)),
    "U": ("Respira morado", "breath", ("#8000FF",)),
    "Z": ("Negro", "black", ()),
}


def rgb(h):
    """'#RRGGBB' -> (r, g, b); ValueError si no tiene ese formato."""
    if not (isinstance(h, str) and len(h) == 7 and h[0] == "#"):
        raise ValueError(h)
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def default_colors():
    return {k: [rgb(c) for c in v[2]] for k, v in LOOKS.items()}


class Frame(NamedTuple):
    left: tuple   # RGB 0..255
    right: tuple
    logo_visible: bool  # F5/F6


@dataclass
class Scene:
    """Estado mínimo del show. El look activo no se persiste: siempre arranca en 1."""
    look: str = "1"
    n0: int = 0         # snap.n al elegir el look
    t0: float = 0.0     # snap.t al elegir el look (U)
    bump: bool = False  # tecla mantenida
    blackout: bool = False

    def select(self, look, snap):
        self.look, self.n0, self.t0 = look, snap.n, snap.t


@dataclass
class Cfg:
    """Lo que compose necesita de la configuración (por salida en F5)."""
    master: float = 1.0
    gamma: float = 1.0
    base: tuple = (WHITE,)  # look 1: uno o varios (paleta: uno por destello)
    colors: dict = field(default_factory=default_colors)


def _scale(c, v):
    return tuple(round(x * v) for x in c)


def compose(snap, scene, cfg):
    """Snapshot del motor + escena + cfg -> Frame. Pura y determinista."""
    kind = LOOKS[scene.look][1]
    cols = cfg.colors.get(scene.look) or (WHITE,)
    k = max(snap.n - scene.n0, 0)  # destellos desde que se eligió el look
    main = (cfg.base[snap.n % len(cfg.base)] if kind == "base" else cols[k % len(cols)] if kind == "rainbow"
            else WHITE if kind == "black" else cols[0])
    if scene.blackout:
        return Frame(BLACK, BLACK, False)
    if scene.bump:  # sólido al 100 %: ignora piso, gamma, decay, offset y master
        c = _scale(main, 1.0)
        return Frame(c, c, False)
    on = snap.gate and k > 0  # estrobos: color solo con la compuerta abierta; si no, negro real
    if kind == "strobe":
        c = _scale(cols[0] if k % 2 else cols[1], cfg.master) if on else BLACK
        return Frame(c, c, False)
    if kind == "split":
        c = _scale(main, cfg.master) if on else BLACK
        return Frame(BLACK, c, False) if k % 2 else Frame(c, BLACK, False)
    if kind == "breath":
        tri = 1 - abs((snap.t - scene.t0) % BREATH_S / (BREATH_S / 2) - 1)
        c = _scale(main, min(max(tri * cfg.master, 0.0), 1.0) ** cfg.gamma)
        return Frame(c, c, False)
    if kind == "black":
        return Frame(BLACK, BLACK, False)
    c = _scale(main, snap.out)  # base / solid / rainbow: siguen la intensidad del motor
    return Frame(c, c, kind == "base")
