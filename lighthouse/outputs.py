"""Salidas de video: un Toplevel por salida, en pantalla completa sin bordes sobre un monitor o en
ventana (para montar). compose_output() aplica la regla unirse_a_looks y el master de la salida:
es pura (sin Tk) y la prueba el self-check."""
import logging
import math
import re

from . import net, win32
from .scene import BLACK, Cfg, Scene, compose

log = logging.getLogger(__name__)
JOIN = ("siempre", "excepto en 1", "nunca")
LIGHT, LOGO = "Luz", "Luz + logo"
CONTENT = (LIGHT, LOGO)
MAX_OUTPUTS = 4
WIN_GEO = "640x400+60+60"
GEO_RE = re.compile(r"^(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)$")
LOGO_FIT = 0.7   # el logo cabe en ~70 % del lado menor de la salida
IDENT_MS = 3000
DIM_S = 0.016  # atenuaciones: como mucho un pintado cada ~16 ms (un cuadro a 60 Hz)


def joined(rule, look):
    """La salida muestra el look activo (y oculta su logo)."""
    return rule == "siempre" or (rule == "excepto en 1" and look != "1")


def compose_output(snap, sc, cfg, rule, master=1.0, logo=False):
    """Frame de una salida. Unida: el Frame del look, sin logo. No unida: su contenido propio,
    luz base (look 1) × out × master, con logo si lo lleva. Blackout y bump vienen en sc: afectan a
    todas. master (0..1) entra como el master del motor (antes de la gamma)."""
    j = joined(rule, sc.look)
    if not j:
        sc = Scene("1", sc.n0, sc.t0, sc.bump, sc.blackout)
    if master != 1.0:
        snap = snap._replace(out=snap.out * master ** cfg.gamma)
        cfg = Cfg(cfg.master * master, cfg.gamma, cfg.base, cfg.colors)
    f = compose(snap, sc, cfg)
    vis = logo and not j and f.logo_visible
    return f if vis == f.logo_visible else f._replace(logo_visible=vis)


def rect_str(m):
    return f"{m.w}x{m.h}+{m.x}+{m.y}"


def default_output(n, mons, used=()):
    """Config de una salida nueva: en ventana, asignada al primer monitor secundario libre (el primario
    suele ser la pantalla de la laptop, con la ventana Control); si no hay, al primario."""
    m = next((m for m in mons if m.device not in used and not m.primary), None) or \
        next((m for m in mons if m.primary), None)
    off = 60 + 40 * (n - 1)
    return dict(nombre=f"Salida {n}", monitor=m.device if m else "", monitor_rect=rect_str(m) if m else "",
                pantalla_completa=False, master=100.0, retardo_extra_ms=0.0, contenido=LIGHT, logo="",
                unirse_a_looks="siempre", geo=f"640x400+{off}+{off}",
                tipo="local", destino=net.AUTO, puerto=float(net.PORT))


def remote_output(n):
    """Preset "TV grande (remota)": se une excepto en 1, con logo y master 30 %, hacia la pantalla remota."""
    return dict(default_output(n, ()), nombre="TV grande (remota)", tipo="remota", contenido=LOGO,
                unirse_a_looks="excepto en 1", master=30.0)


def make_output(app, d, mons):
    return RemoteOutput(app, d) if d.get("tipo") == "remota" else Output(app, d, mons)


def resolve(device, rect, mons):
    """Monitor guardado -> (Monitor, aviso). Por device; si no está, por rectángulo; si no, el primario."""
    for m in mons:
        if m.device == device:
            return m, None
    for m in mons:
        if rect_str(m) == rect:
            return m, None
    prim = next((m for m in mons if m.primary), None) or (mons[0] if mons else win32.Monitor("", 0, 0, 640, 480, True))
    return prim, (f"{device} no está conectado: se usa el principal ({prim.device})" if device else None)


def monitor_at(x, y, mons):
    return next((m for m in mons if m.x <= x < m.x + m.w and m.y <= y < m.y + m.h), None)


def geo_ok(geo, mons):
    """'WxH+X+Y' válido y con la barra de título (esquina superior izquierda) sobre algún monitor."""
    g = GEO_RE.match(geo or "")
    if not g:
        return False
    if g[3][0] == "-" or g[4][0] == "-":  # relativo al borde derecho/inferior: Tk lo resuelve, no se valida
        return True
    x, y = int(g[3][1:]), int(g[4][1:])
    return monitor_at(x + 40, y + 10, mons) is not None


class RemoteOutput:
    """Salida remota: compone como una local (master, retardo extra, regla de unirse, logo sí/no) pero en
    vez de pintar manda el Frame por UDP (net.Sender). El logo es un archivo del receptor."""
    remote = True
    full, logo, logo_err = False, "", None

    def __init__(self, app, d):
        self.name = d["nombre"].strip() or "Salida"
        self.master = min(max(d["master"], 0.0), 100.0)
        self.delay_ms = min(max(d["retardo_extra_ms"], 0.0), 200.0)
        self.content = d["contenido"] if d["contenido"] in CONTENT else LIGHT
        self.join = d["unirse_a_looks"] if d["unirse_a_looks"] in JOIN else JOIN[0]
        self.sender, self.warn = None, None
        self.dest, self.port = d["destino"], int(d["puerto"])
        self.connect(self.dest, self.port)

    def connect(self, dest, port):
        """(Re)crea el emisor; un destino o puerto no válido cae a Automático / 47800 con aviso."""
        dest = dest.strip()
        self.warn = None
        if dest.lower() in ("", net.AUTO.lower(), "automatico"):
            dest = net.AUTO
        elif not net.valid_ip(dest):
            self.warn = f"destino {dest!r} no es una IP válida: se usa {net.AUTO}"
            dest = net.AUTO
        if not 1 <= port <= 65535:
            self.warn = (self.warn or "") + f" puerto {port} no válido: se usa {net.PORT}"
            port = net.PORT
        if self.sender:
            self.sender.close()
        self.dest, self.port = dest, port
        self.sender = net.Sender(dest, port)

    def snapshot(self):
        d = default_output(1, ())
        d.update(nombre=self.name, master=self.master, retardo_extra_ms=self.delay_ms, contenido=self.content,
                 unirse_a_looks=self.join, tipo="remota", destino=self.dest, puerto=float(self.port))
        return d

    def render(self, f, now):
        self.sender.send(f, now)

    def status(self):
        return self.sender.status()

    def identify(self, n, mons):
        pass

    def destroy(self):
        self.sender.close()


class Output:
    """Una salida: Toplevel con dos mitades (Frame + bg, nunca Canvas: a 1080p el Canvas cuesta
    ~7 ms por pintado), el logo centrado (Label + PhotoImage) y el rótulo de Identificar."""

    remote = False

    def __init__(self, app, d, mons):
        tk = self.tk = app.tk
        self.on_change = app.outputs_changed
        w = self.win = tk.Toplevel(app.root, bg="black", cursor="none")
        w.protocol("WM_DELETE_WINDOW", w.iconify)
        self.halves = [tk.Frame(w, bg="#000000", bd=0, highlightthickness=0, cursor="none") for _ in range(2)]
        # se solapan 1 px para que un look sólido no muestre costura
        self.halves[0].place(x=0, y=0, relwidth=0.5, width=1, relheight=1)
        self.halves[1].place(relx=0.5, y=0, relwidth=0.5, width=1, relheight=1)
        self.logo_lbl = tk.Label(w, bd=0, highlightthickness=0, padx=0, pady=0, bg="#000000", cursor="none")
        self.ident = tk.Label(w, fg="white", bg="black", cursor="none", justify="center", padx=20, pady=10)
        self.painted = [None, None]
        self.t_paint = -1e9
        self.logo_on, self.logo_bg = False, None
        self.img_raw = self.img = None
        self.size = self.img_size = None
        self.jobs = {}
        # en las bindtags de cada hijo está su Toplevel: estos binds valen para toda la salida
        w.bind("<Double-Button-1>", lambda e: self.toggle())
        w.bind("<Escape>", lambda e: self.set_full(False))
        w.bind("<Configure>", self.on_configure)

        self.name = d["nombre"].strip() or "Salida"
        self.device, self.rect = d["monitor"], d["monitor_rect"]
        self.full = d["pantalla_completa"]
        self.master = min(max(d["master"], 0.0), 100.0)
        self.delay_ms = min(max(d["retardo_extra_ms"], 0.0), 200.0)
        self.content = self.pick("contenido", d["contenido"], CONTENT)
        self.join = self.pick("unirse_a_looks", d["unirse_a_looks"], JOIN)
        self.geo = d["geo"] if geo_ok(d["geo"], mons) else WIN_GEO
        if d["geo"] and self.geo != d["geo"]:
            log.warning("salida %r: geometría %r no válida o fuera de los monitores", self.name, d["geo"])
        self.logo, self.logo_err = "", None
        self.set_logo(d["logo"])
        self.mon, self.warn = resolve(self.device, self.rect, mons)
        self.place()

    def pick(self, key, v, allowed):
        if v in allowed:
            return v
        log.warning("config: salida %r: %r=%r no es válido; se usa %r", self.name, key, v, allowed[0])
        return allowed[0]

    def snapshot(self):
        if not self.full and self.win.winfo_viewable():
            self.geo = self.win.geometry()
        return dict(nombre=self.name, monitor=self.device, monitor_rect=self.rect, pantalla_completa=self.full,
                    master=self.master, retardo_extra_ms=self.delay_ms, contenido=self.content, logo=self.logo,
                    unirse_a_looks=self.join, geo=self.geo, tipo="local", destino=net.AUTO,
                    puerto=float(net.PORT))

    def hwnd(self):
        return int(self.win.wm_frame(), 16)

    # --- lugar en pantalla
    def place(self):
        """Pantalla completa: sin bordes, cubriendo exactamente el monitor; si no, ventana normal."""
        w = self.win
        w.title(f"LightHouse · {self.name}")
        if self.full:
            self.mon, self.warn = resolve(self.device, self.rect, win32.monitors())
            if self.warn:
                log.warning("salida %r: %s", self.name, self.warn)
            m = self.mon
            w.withdraw()  # sin esto, quitar los bordes a una ventana ya visible la deja en su posición vieja
            w.overrideredirect(True)
            w.geometry(f"{m.w}x{m.h}+{m.x}+{m.y}")  # +-2560+-360: con -2560-360 Tk la coloca mal (medido)
            w.attributes("-topmost", True)  # encima de la barra de tareas
        else:
            w.attributes("-topmost", False)
            w.overrideredirect(False)
            w.geometry(self.geo)
        w.deiconify()

    def set_monitor(self, m):
        self.device, self.rect, self.mon, self.warn = m.device, rect_str(m), m, None
        if self.full:
            self.place()

    def set_full(self, on):
        if on == self.full:
            return
        if on and self.win.winfo_viewable():
            self.geo = self.win.geometry()
        self.full = on
        self.place()
        self.on_change()

    def toggle(self):
        """Doble clic: en ventana pasa a pantalla completa en el monitor donde está; si no, a ventana."""
        if not self.full:
            m = monitor_at(*self.center(), win32.monitors())
            if m:
                self.device, self.rect = m.device, rect_str(m)
        self.set_full(not self.full)

    def center(self):
        w = self.win
        return w.winfo_rootx() + w.winfo_width() // 2, w.winfo_rooty() + w.winfo_height() // 2

    def later(self, key, ms, fn):
        """Un solo after pendiente por llave (debounce / temporizador de un disparo)."""
        if key in self.jobs:
            self.win.after_cancel(self.jobs[key])
        self.jobs[key] = self.win.after(ms, lambda: (self.jobs.pop(key, None), fn()))

    def on_configure(self, e):
        if e.widget is self.win and (e.width, e.height) != self.size:
            self.size = (e.width, e.height)
            self.later("logo", 250, self.rescale)  # al arrastrar el borde llegan decenas de Configure

    # --- logo
    def set_logo(self, path):
        self.logo, self.logo_err, self.img_raw = path.strip(), None, None
        if self.logo:
            try:
                self.img_raw = self.tk.PhotoImage(master=self.win, file=self.logo)
            except self.tk.TclError as ex:
                self.logo_err = f"{self.name}: logo no válido ({ex})"
                log.warning("salida %r: no se pudo cargar el logo %r: %s", self.name, self.logo, ex)
        self.img_size = None
        self.rescale()

    def rescale(self):
        """Logo al mayor factor entero de zoom/subsample que quepa en ~70 % del lado menor."""
        raw = self.img_raw
        if raw is None or not self.size:
            self.img = None
            self.logo_lbl.configure(image="")
            return
        if self.size == self.img_size:
            return
        self.img_size = self.size
        fit, side = LOGO_FIT * min(self.size), max(raw.width(), raw.height())
        # ponytail: escala entera (sin Pillow); si se ve mal, preparar el PNG al tamaño de la pantalla
        self.img = raw.zoom(int(fit // side)) if fit >= 2 * side else raw if fit >= side else \
            raw.subsample(math.ceil(side / max(fit, 1)))
        self.logo_lbl.configure(image=self.img)

    # --- pintado
    def render(self, f, now):
        """Solo toca lo que cambió: cada configure hace redibujar a Tk (pantalla completa ~0,3 ms por
        mitad, el logo ~2 ms). Subir de brillo, cambiar de color o cortar a negro se pinta ya; una
        atenuación (la cola del decay) espera hasta DIM_S desde el último pintado: la pantalla
        refresca a 60 Hz y los bloques llegan a 100 Hz. El loop lento (30 Hz) pinta lo pendiente."""
        new = (f.left, f.right)
        if new != tuple(self.painted) and (now - self.t_paint >= DIM_S or not all(
                c != BLACK and all(a <= b for a, b in zip(c, p)) for c, p in zip(new, self.painted) if p)):
            self.t_paint = now
            for i, rgb in enumerate(new):
                if rgb != self.painted[i]:
                    self.painted[i] = rgb
                    self.halves[i].configure(bg="#%02x%02x%02x" % rgb)
        on = f.logo_visible and self.img is not None
        if on and self.painted[0] != self.logo_bg:  # el fondo del PNG (transparencias) sigue a la luz
            self.logo_bg = f.left
            self.logo_lbl.configure(bg="#%02x%02x%02x" % f.left)
        if on != self.logo_on:
            self.logo_on = on
            if on:
                self.logo_lbl.place(relx=0.5, rely=0.5, anchor="center")
            else:
                self.logo_lbl.place_forget()

    def identify(self, n, mons):
        """Durante 3 s: 'Salida N · \\\\.\\DISPLAYn · 1920×1080' en grande (el monitor donde está)."""
        m = monitor_at(*self.center(), mons) or self.mon
        W, H = self.size or (m.w, m.h)
        text = f"Salida {n} · {m.device} · {m.w}×{m.h}" + ("" if self.name == f"Salida {n}" else f"\n{self.name}")
        self.ident.configure(text=text, font=("Segoe UI", -max(12, int(min(H / 12, W / 24))), "bold"),
                             wraplength=int(W * 0.9))
        self.ident.place(relx=0.5, rely=0.5, anchor="center")
        self.ident.lift()
        self.later("ident", IDENT_MS, self.ident.place_forget)

    def destroy(self):
        for job in self.jobs.values():
            self.win.after_cancel(job)
        self.win.destroy()
