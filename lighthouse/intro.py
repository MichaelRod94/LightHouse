"""Intro (animación de entrada): reproductor genérico de un manifiesto JSON (fases/diseno-ui.md §7).

Nada de una intro concreta vive aquí: ni coordenadas, ni tiempos, ni textos, ni colores, ni nombres de
archivo. Todo sale del manifiesto (assets/intro/intro.json), de los textos de la app, de los tokens del tema
y de los looks. Cambiar de intro es cambiar esa carpeta.

load / value / frame_index / resolve / color / fuente son puras (sin Tk). Intro dibuja en un Canvas del
tamaño del lienzo, dentro de Control, y avanza desde App.slow() (tick); no tiene ningún after propio."""
import json
import logging
import os
import re
import struct
import sys
import time

from . import theme

log = logging.getLogger(__name__)

FORMATO = 1
MAX_MS = 3000                     # la intro dura a lo más 3 s
TIPOS = ("secuencia", "imagen", "texto", "color")
EASINGS = ("lineal", "in_cubic", "out_cubic", "in_out", "corte")
NUMERICAS = ("x", "y", "nivel", "cuadro")  # pistas cuyos valores son números (el resto: visible = bool)
STEP_MS = 33                      # el paso de App.slow(); con él se planea qué cuadro decodificar antes
ARRANQUE_MS = 12                  # lo mismo, una sola vez al crear la intro (la ventana aún no se muestra)
PRE_MS = 1.5                     # en un tick libre se adelantan pasos mientras no se hayan gastado estos ms
VARS = re.compile(r"\{(\w+)\}")
_EASE = {"lineal": lambda u: u, "in_cubic": lambda u: u ** 3, "out_cubic": lambda u: 1 - (1 - u) ** 3,
         "in_out": lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2}


def resource_path(*parts):
    """Carpeta de recursos: la del repositorio en código fuente, sys._MEIPASS en el exe congelado."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def zoom_for(scale):
    """Factor entero de ampliación de las imágenes: ×2 con escala de pantalla >= 200 %."""
    return 2 if scale >= 1.99 else 1


# --- manifiesto
class Manifest:
    def __init__(self, folder, data):
        self.folder, self.data = folder, data
        self.lienzo = (int(data["lienzo"][0]), int(data["lienzo"][1]))
        self.duracion_ms = data["duracion_ms"]
        self.fondo = data["fondo"]
        self.capas = data["capas"]

    def frames(self, capa):
        """Una tupla de rutas por cuadro de una capa de imágenes. Con "franjas": N, cada cuadro son N archivos
        (franjas horizontales, de arriba abajo; el patrón recibe cuadro y franja): se decodifican de una en una."""
        if capa["tipo"] == "imagen":
            return [(os.path.join(self.folder, capa["archivo"]),)]
        n = capa.get("franjas", 1)
        return [tuple(os.path.join(self.folder, capa["archivos"].format(i, k)) for k in range(n))
                for i in range(capa["cuadros"])]

    def files(self):
        return [p for c in self.capas if c["tipo"] in ("secuencia", "imagen") for fr in self.frames(c) for p in fr]


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_track(name, pts):
    if not isinstance(pts, list) or not pts:
        raise ValueError(f"pista {name!r} vacía o mal formada")
    last = None
    for p in pts:
        if not isinstance(p, list) or not 2 <= len(p) <= 3 or not _num(p[0]):
            raise ValueError(f"pista {name!r}: punto mal formado {p!r}")
        if last is not None and p[0] < last:
            raise ValueError(f"pista {name!r}: tiempos desordenados")
        if len(p) == 3 and p[2] not in EASINGS:
            raise ValueError(f"pista {name!r}: easing desconocido {p[2]!r}")
        if name in NUMERICAS and not _num(p[1]):
            raise ValueError(f"pista {name!r}: valor no numérico {p[1]!r}")
        last = p[0]


def _check_layer(c, folder):
    if not isinstance(c, dict) or c.get("tipo") not in TIPOS:
        raise ValueError(f"capa de tipo desconocido: {c.get('tipo') if isinstance(c, dict) else c!r}")
    pistas = c.get("pistas", {})
    if not isinstance(pistas, dict):
        raise ValueError(f"capa {c.get('id')!r}: pistas mal formadas")
    for name, pts in pistas.items():
        _check_track(name, pts)
    t = c["tipo"]
    if t == "color":
        r = c.get("rect")
        if not (isinstance(r, list) and len(r) == 4 and all(_num(v) for v in r) and isinstance(c.get("color"), str)):
            raise ValueError(f"capa {c.get('id')!r}: falta rect o color")
    elif t == "texto":
        if not all(isinstance(c.get(k), str) for k in ("texto", "fuente", "color")):
            raise ValueError(f"capa {c.get('id')!r}: falta texto, fuente o color")
    elif t == "secuencia":
        n = c.get("cuadros")
        if not (isinstance(c.get("archivos"), str) and isinstance(n, int) and not isinstance(n, bool) and n >= 1):
            raise ValueError(f"capa {c.get('id')!r}: falta archivos o cuadros")
        nf = c.get("franjas", 1)
        if not (isinstance(nf, int) and not isinstance(nf, bool) and nf >= 1):
            raise ValueError(f"capa {c.get('id')!r}: franjas mal formadas")
        if c.get("cuadro_por") == "nivel":
            if "nivel" not in pistas:
                raise ValueError(f"capa {c.get('id')!r}: cuadro_por nivel sin pista nivel")
        elif not (_num(c.get("fps")) and c["fps"] > 0) and "cuadro" not in pistas:
            raise ValueError(f"capa {c.get('id')!r}: sin fps, cuadro ni nivel")
    elif not isinstance(c.get("archivo"), str):
        raise ValueError(f"capa {c.get('id')!r}: falta archivo")
    pos = c.get("pos", [0.5, 0.5])
    if not (isinstance(pos, list) and len(pos) == 2 and all(_num(v) for v in pos)):
        raise ValueError(f"capa {c.get('id')!r}: pos mal formada")


def load(path):
    """Lee y valida un manifiesto. Cualquier error (archivo, JSON, capa desconocida, archivo que falta,
    duración > 3000 ms) devuelve None con un aviso en el log. Nunca lanza."""
    try:
        folder = os.path.dirname(os.path.abspath(path))
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("formato") != FORMATO:
            raise ValueError("formato no soportado")
        lz = data.get("lienzo")
        if not (isinstance(lz, list) and len(lz) == 2 and all(isinstance(v, int) and v > 0 for v in lz)):
            raise ValueError("lienzo mal formado")
        d = data.get("duracion_ms")
        if not _num(d) or not 0 < d <= MAX_MS:
            raise ValueError(f"duracion_ms fuera de 1..{MAX_MS}: {d!r}")
        if not isinstance(data.get("fondo"), str) or not isinstance(data.get("capas"), list) or not data["capas"]:
            raise ValueError("faltan fondo o capas")
        for c in data["capas"]:
            _check_layer(c, folder)
        m = Manifest(folder, data)
        missing = [os.path.basename(p) for p in m.files() if not os.path.isfile(p)]
        if missing:
            raise ValueError(f"faltan archivos: {missing[:3]}")
        return m
    except Exception as ex:
        log.warning("intro: manifiesto no válido (%s): %s", path, ex)
        return None


# --- funciones puras
def value(track, t_ms):
    """Valor de una pista [[t_ms, valor, easing?], ...] en t_ms. El easing de un punto rige el tramo que llega
    a él; "corte" (y los valores que no son números, p. ej. visible) saltan al llegar. Antes del primer punto
    vale el primero; después del último, el último."""
    if t_ms <= track[0][0]:
        return track[0][1]
    for a, b in zip(track, track[1:]):
        if t_ms < b[0]:
            ease = b[2] if len(b) > 2 else "lineal"
            if ease == "corte" or not _num(a[1]) or not _num(b[1]):
                return a[1]
            return a[1] + (b[1] - a[1]) * _EASE[ease]((t_ms - a[0]) / (b[0] - a[0]))
    return track[-1][1]


def frame_index(layer, t_ms):
    """Cuadro (0..cuadros-1) de una capa secuencia en t_ms: por pista cuadro, por nivel (pista nivel de la
    propia capa: round(nivel × (cuadros − 1))) o por tiempo (fps)."""
    n, pistas = layer["cuadros"], layer.get("pistas", {})
    if "cuadro" in pistas:
        i = int(value(pistas["cuadro"], t_ms))
    elif layer.get("cuadro_por") == "nivel":
        i = int(min(max(value(pistas["nivel"], t_ms), 0.0), 1.0) * (n - 1) + 0.5)
    else:
        i = int(t_ms * layer["fps"] / 1000)
    return min(max(i, 0), n - 1)


def resolve(texto, datos):
    """Rellena {app}, {version}, {autor}... con datos; una variable desconocida se deja tal cual."""
    return VARS.sub(lambda m: str(datos.get(m[1], m[0])), texto)


def color(ref, tema, looks):
    """"token:nombre" -> color del tema; "look:N" -> primer color del look N (looks: id -> lista de "#rrggbb", como scene.LOOKS); "#rrggbb" tal
    cual (el escenario de la intro puede ser un color fijo, igual al de sus imágenes, con cualquier tema).
    Una referencia desconocida cae a intro_fg con aviso."""
    kind, _, name = str(ref).partition(":")
    if isinstance(ref, str) and ref.startswith("#") and len(ref) == 7:  # color fijo del manifiesto ("#rrggbb")
        try:
            int(ref[1:], 16)
            return ref
        except ValueError:
            pass
    if kind == "token" and isinstance(tema.get(name), str):
        return tema[name]
    if kind == "look" and looks.get(name):  # looks: id -> lista de colores del look; vale el primero
        return looks[name][0]
    log.warning("intro: color desconocido %r; se usa intro_fg", ref)
    return tema["intro_fg"]


def fuente(ref, tema):
    """"token:font.x" -> (familia, puntos, peso) del tema; desconocida cae a font.body con aviso."""
    name = str(ref).partition(":")[2]
    if isinstance(tema.get(name), tuple):
        return tema[name]
    log.warning("intro: fuente desconocida %r; se usa font.body", ref)
    return tema["font.body"]


# --- reproductor
class Intro:
    """Capa que cubre Control (Frame con un Canvas del tamaño del lienzo, centrado). Se registra en app.intro y
    marca app.intro_on; al terminar o al omitirla se destruye y avisa a la banda del tutorial (close)."""

    def __init__(self, app, manifest, datos=None):
        self.app, self.m, self.fr = app, manifest, None
        self.t0 = None
        self.did = False                   # este tick ya decodificó una imagen o cambió una imagen del Canvas
        self.photo, self.pending, self.raw = {}, {}, {}
        try:
            self._build(dict(datos or {}))
        except Exception:
            self.close()
            raise
        app.intro, app.intro_on = self, True
        app.update_band()

    def _build(self, datos):
        app, m = self.app, self.m
        th, looks = theme.current(), app.look_hex
        self.zoom = z = zoom_for(app.scale)
        self.W, self.H = m.lienzo[0] * z, m.lienzo[1] * z
        bg = color(m.fondo, th, looks)
        self.fr = app.tk.Frame(app.root, bg=bg, bd=0, highlightthickness=0)
        self.cv = cv = app.tk.Canvas(self.fr, width=self.W, height=self.H, bg=bg, bd=0, highlightthickness=0)
        cv.place(relx=0.5, rely=0.5, anchor="center")
        self.fr.place(x=0, y=0, relwidth=1, relheight=1)
        self.fr.lift()
        self.capas, self.plan = [], []
        for c in m.capas:
            pos = c.get("pos", [0.5, 0.5])
            xy = (pos[0] * self.W, pos[1] * self.H)
            half, offs = (0, 0), [(0, 0)]
            if c["tipo"] == "color":
                x0, y0, x1, y1 = c["rect"]
                items = [cv.create_rectangle(x0 * self.W, y0 * self.H, x1 * self.W, y1 * self.H, width=0,
                                             fill=color(c["color"], th, looks), state="hidden")]
            elif c["tipo"] == "texto":
                items = [cv.create_text(*xy, anchor="center", state="hidden", text=resolve(c["texto"], datos),
                                        font=fuente(c["fuente"], th), fill=color(c["color"], th, looks))]
            else:
                frames = m.frames(c)
                for fr in frames:
                    for p in fr:
                        with open(p, "rb") as f:
                            self.raw[p] = f.read()
                # la imagen (o la pila de franjas) se centra en pos; el tamaño sale de la cabecera de cada archivo
                dims = [struct.unpack(">II", self.raw[p][16:24]) for p in frames[0]]
                y, offs = 0, []
                for w, h in dims:
                    offs.append((0, y))
                    y += h * z
                half = (dims[0][0] * z / 2, y / 2)
                items = [cv.create_image(xy[0] - half[0] + ox, xy[1] - half[1] + oy, anchor="nw", state="hidden")
                         for ox, oy in offs]
                # los cuadros distintos, en el orden en que los pide la capa (se adelantan en ticks libres)
                seen = []
                for t in range(0, int(m.duracion_ms) + STEP_MS, STEP_MS):
                    fr = frames[frame_index(c, t)] if c["tipo"] == "secuencia" else frames[0]
                    if fr not in seen:
                        seen.append(fr)
                self.plan += [p for fr in seen for p in fr]
            self.capas.append({"c": c, "items": items, "half": half, "offs": offs, "vis": False, "xy": xy,
                               "idx": None})
        self.tick(None, ARRANQUE_MS)  # t = 0 y un primer adelanto de decodificación, antes de que Control aparezca

    # --- imágenes: un paso = decodificar un archivo (o ampliarlo, con zoom)
    def _step(self, p):
        self.did = True
        if p in self.pending:
            self.photo[p] = self.pending.pop(p).zoom(self.zoom)
        else:
            img = self.app.tk.PhotoImage(master=self.cv, data=self.raw[p])
            if self.zoom == 1:
                self.photo[p] = img
            else:
                self.pending[p] = img

    def _show(self, L, fr):
        """Pone las imágenes del cuadro fr (decodifica ahora las que falten) en los ítems de la capa."""
        for p in fr:
            while p not in self.photo:
                self._step(p)
        for item, p in zip(L["items"], fr):
            self.cv.itemconfigure(item, image=self.photo[p])
        self.did = True

    def tick(self, now, pre=PRE_MS):
        """Un paso: tiempo transcurrido (el primer tick es t = 0), actualiza solo lo que cambió y, al pasar
        duracion_ms, termina. Si llega tarde salta cuadros (va por tiempo). En un tick sin cambios de imagen
        adelanta la decodificación de los próximos archivos del plan (una o dos, sin pasar de PRE_MS)."""
        if self.fr is None:
            return
        if now is not None and self.t0 is None:
            self.t0 = now
        t = 0.0 if self.t0 is None else (now - self.t0) * 1000
        if t >= self.m.duracion_ms:
            self.close()
            return
        self.did = False
        for L in self.capas:
            self._update(L, t)
        if not self.did:
            t1 = time.perf_counter()
            for p in self.plan:
                if p not in self.photo:
                    self._step(p)
                    if (time.perf_counter() - t1) * 1000 >= pre:
                        break

    def _update(self, L, t):
        c, cv = L["c"], self.cv
        pistas = c.get("pistas", {})
        vis = bool(value(pistas["visible"], t)) if "visible" in pistas else True
        if vis != L["vis"]:
            L["vis"] = vis
            for item in L["items"]:
                cv.itemconfigure(item, state="normal" if vis else "hidden")
        if not vis:
            return
        if c["tipo"] != "color" and ("x" in pistas or "y" in pistas):
            xy = (value(pistas["x"], t) * self.W if "x" in pistas else L["xy"][0],
                  value(pistas["y"], t) * self.H if "y" in pistas else L["xy"][1])
            if xy != L["xy"]:
                L["xy"] = xy
                for item, (ox, oy) in zip(L["items"], L["offs"]):
                    cv.coords(item, xy[0] - L["half"][0] + ox, xy[1] - L["half"][1] + oy)
        if c["tipo"] == "secuencia":
            i = frame_index(c, t)
            if i != L["idx"]:
                L["idx"] = i
                self._show(L, self.m.frames(c)[i])
        elif c["tipo"] == "imagen" and L["idx"] is None:
            L["idx"] = 0
            self._show(L, self.m.frames(c)[0])

    def skip(self):
        self.close()

    def close(self):
        """Destruye la capa y libera las imágenes (idempotente); la app queda como sin intro."""
        fr, self.fr = self.fr, None
        if fr is not None:
            fr.destroy()
        self.photo.clear(), self.pending.clear(), self.raw.clear()
        self.capas = []
        app = self.app
        if app.intro is self:
            app.intro, app.intro_on = None, False
            app.update_band()
