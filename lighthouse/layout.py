"""Layout responsive de la ventana Control: modo según el tamaño y reparto de tarjetas por pestaña.
Puro (sin Tk): lo prueba el self-check. Medidas en px lógicos (px físicos / escala). fases/diseno-ui.md §3.2."""
from typing import NamedTuple

MINI_H, MINI_W = 300, 560        # mini: alto < 300 o ancho < 560 (o forzado)
COMPACT_H, COMPACT_W = 600, 760  # compacto: alto < 600 o ancho < 760 (o forzado)
MEDIUM_W = 1200                  # medio: ancho < 1200; si no, completo
COL_W, MAX_COLS = 400, 4         # columnas de tarjetas = clamp(ancho // 400, 1, 4)
LOOKS_1ROW, LOOKS_1ROW_DENSE = 900, 760  # una fila de looks desde este ancho (cómoda / densa)
LIVE_1ROW = 1100                 # franja En vivo densa en una fila desde este ancho; si no, dos
HYST = 24                        # histéresis a favor del layout anterior (no parpadea al arrastrar el borde)
MODES = ("mini", "compacto", "medio", "completo")  # de menor a mayor
FORCED = ("auto", "compacto", "mini")
TABS = ("show", "audio", "salidas", "ayuda")

# pestaña -> tarjetas (id de fases/diseno-ui.md §2.2) en orden de lectura, con su peso de altura
# (su alto pedido con "Avanzado" plegado, en decenas de px lógicos): plan() equilibra las columnas con él
CARDS = {
    "show": (("respuesta", 17), ("luz", 25), ("color", 15), ("estrobos", 7), ("teclado", 12)),
    "audio": (("fuente", 16), ("ganancia", 12), ("filtro", 9), ("golpe", 7), ("tempo", 18), ("tranquilo", 10)),
    "salidas": (("salidas", 31), ("salida_sel", 30)),
    "ayuda": (("atajos", 31), ("ayuda", 22)),
}


class Layout(NamedTuple):
    mode: str        # "completo" | "medio" | "compacto" | "mini"
    cols: int        # columnas de tarjetas (0 en mini)
    look_rows: int   # 1 o 2 (en mini: 1 = tira, 2 = bloque)
    dense: bool


def _below(v, limit, prev_below):
    """v < limit, con histéresis: si antes estaba por debajo, hace falta pasarlo por HYST para salir."""
    if prev_below is None:
        return v < limit
    return v < limit + HYST if prev_below else v < limit - HYST


def cols_for(w, prev=None):
    """Columnas de tarjetas para un ancho (1–4), con histéresis respecto a prev."""
    c = int(w // COL_W)
    if prev:
        if c > prev and w < (prev + 1) * COL_W + HYST:
            c = prev
        elif c < prev and w >= prev * COL_W - HYST:
            c = prev
    return min(max(c, 1), MAX_COLS)


def pick(w, h, forced="auto", prev=None):
    """Layout para un área cliente de w × h px lógicos. forced: "auto" | "compacto" | "mini"."""
    rank = MODES.index(prev.mode) if prev else None

    def below(v, limit, boundary):  # boundary: índice del modo justo por debajo del umbral
        return _below(v, limit, None if rank is None else rank <= boundary)

    if forced == "mini" or below(h, MINI_H, 0) or below(w, MINI_W, 0):
        mode = "mini"
    elif forced == "compacto" or below(h, COMPACT_H, 1) or below(w, COMPACT_W, 1):
        mode = "compacto"
    elif below(w, MEDIUM_W, 2):
        mode = "medio"
    else:
        mode = "completo"
    dense = mode in ("mini", "compacto")
    same = prev is not None and prev.dense == dense
    two = (prev.look_rows == 2) if same else None
    if mode == "mini" and two is False:  # tira: los 15 looks + Blackout no caben bajo 760; pasa a bloque ahí
        two = None
    rows = 2 if _below(w, LOOKS_1ROW_DENSE if dense else LOOKS_1ROW, two) else 1
    cols = 0 if mode == "mini" else cols_for(w, prev.cols if prev else None)
    return Layout(mode, cols, rows, dense)


def live_rows(w, dense, prev=None):
    """Filas de la franja En vivo: 3 en cómoda; en densa, 1 si el ancho >= 1100 y 2 si no."""
    if not dense:
        return 3
    return 2 if _below(w, LIVE_1ROW, None if prev not in (1, 2) else prev == 2) else 1


def plan(layout, tab):
    """[(id de tarjeta, columna, fila)] de la pestaña: en orden de lectura, cada tarjeta a la columna
    menos alta hasta ahora (empate: la de la izquierda). Determinista. Mini (0 columnas): []."""
    n = layout.cols
    if n <= 0:
        return []
    heights, rows, out = [0] * n, [0] * n, []
    for cid, weight in CARDS[tab]:
        c = min(range(n), key=lambda i: (heights[i], i))
        out.append((cid, c, rows[c]))
        heights[c] += weight
        rows[c] += 1
    return out
