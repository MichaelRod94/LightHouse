"""Tutorial interactivo omisible de la ventana Control (fases/diseno-ui.md §6): pasos como datos (STEPS), un anillo
de 4 marcos y un globo con place() sobre la raíz. Sin Canvas, sin capa oscura y sin timers: avanza desde
App.slow() (tick) mientras está activo."""
import time
from collections import namedtuple

from . import theme

HOLD_S = 0.7  # cuánto se muestra "✓ Hecho" antes de pasar solo al paso siguiente
Step = namedtuple("Step", "id tab title text done")


# --- condiciones de avance: solo LEEN estado (done(app, mem); mem se vacía al mostrar cada paso)
def _signal(app, mem):
    from .ui import NO_SIGNAL_S
    e = app.eng
    return e.t - e.last_sound <= NO_SIGNAL_S and e.t - e.last_beat < 2


def _bpm(app, mem):
    e = app.eng
    return bool(e.bpm) and e.t - e.last_beat < 2


def _look(lid):
    return lambda app, mem: app.scene.look == lid


def _blackout(app, mem):
    """Activado y desactivado: así el paso nunca deja las pantallas apagadas."""
    if app.scene.blackout:
        mem["on"] = True
    return bool(mem.get("on")) and not app.scene.blackout


STEPS = (
    Step(None, None, "Bienvenido",
         "LightHouse escucha tu música y convierte cada golpe en luz en tus pantallas. La luz ya está "
         "funcionando: este recorrido no la detiene. Puedes salir cuando quieras.", None),
    Step("audio.dispositivo", "audio", "Dile de dónde escuchar",
         "Pon música. Abre esta lista y elige \"Salida (loopback) · …\" con el mismo dispositivo por el que "
         "suena tu música (el que usa rekordbox).", _signal),
    Step("vivo.medidor", None, "Comprueba la señal",
         "Con música, el punto parpadea en cada golpe y aparece la velocidad (BPM). Si no se mueve, pulsa Atrás "
         "y prueba otro dispositivo.", _bpm),
    Step("look.2", None, "Cambia de look",
         "Presiona la tecla 2 (o haz clic en este botón). Cada look se queda activo hasta que elijas otro.",
         _look("2")),
    Step("look.Q", None, "Estrobos",
         "Presiona Q: un estrobo que se apaga cuando el golpe deja de sonar. Con 1 vuelves al blanco.",
         _look("Q")),
    Step("blackout", None, "Apagar todo",
         "Espacio apaga todas las pantallas y Espacio otra vez las enciende: pruébalo. Al lado, Bump (mantén F) "
         "da un destello a mano.", _blackout),
    Step("resp.preset", "show", "Qué tan reactivo",
         "\"Muy reactivo\" da destellos más cortos y seguidos. Con + y − ajustas la sensibilidad en vivo.", None),
    Step("salidas.lista", "salidas", "Tus pantallas",
         "Cada salida es una pantalla-luz. Arrástrala a su monitor y haz doble clic para pantalla completa. "
         "\"Identificar pantallas\" te dice cuál es cuál.", None),
    Step("vista.selector", None, "Junto a rekordbox",
         "\"Mini\" (F9) deja solo los looks, la señal y el Blackout. Ojo: tus teclas solo llegan a LightHouse si "
         "su ventana está al frente; el aviso \"Teclas\" te lo dice.", None),
    Step("tab.ayuda", "ayuda", "Listo",
         "Deja el ratón sobre cualquier control para ver qué hace. Este recorrido se repite desde Ayuda → "
         "Ver tutorial.", None),
)


# --- geometría pura (rectángulos = (x, y, w, h))
def ring_rects(x, y, w, h, grosor, margen):
    """Los 4 lados (arriba, abajo, izquierda, derecha) de un anillo de ese grosor alrededor del objetivo, a
    `margen` de distancia. Ninguno toca el objetivo."""
    m, g = margen, grosor
    ow = w + 2 * (m + g)
    return ((x - m - g, y - m - g, ow, g), (x - m - g, y + h + m, ow, g),
            (x - m - g, y - m, g, h + 2 * m), (x + w + m, y - m, g, h + 2 * m))


def _overlap(a, b):
    """Área en común de dos rectángulos."""
    return max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(
        0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def bubble_pos(target, bubble, window):
    """Esquina (x, y) de un globo (w, h) junto al objetivo (rectángulo; None = centrado) dentro de la ventana
    (rectángulo). Prueba debajo, arriba, a la derecha y a la izquierda; el primero que cabe sin tocar el objetivo.
    Si ninguno cabe (objetivo enorme), el que menos lo tapa."""
    wx, wy, ww, wh = window
    bw, bh = bubble
    cx = lambda v: max(wx, min(v, wx + ww - bw))
    cy = lambda v: max(wy, min(v, wy + wh - bh))
    if target is None:
        return cx(wx + (ww - bw) // 2), cy(wy + (wh - bh) // 2)
    tx, ty, tw, th = target
    cands = ((cx(tx), ty + th), (cx(tx), ty - bh), (tx + tw, cy(ty + (th - bh) // 2)),
             (tx - bw, cy(ty + (th - bh) // 2)))
    best = None
    for x, y in cands:
        inside = wx <= x and wy <= y and x + bw <= wx + ww and y + bh <= wy + wh
        cover = _overlap((x, y, bw, bh), target)
        if inside and not cover:
            return x, y
        score = cover + (0 if inside else 1 << 40)
        if best is None or score < best[0]:
            best = (score, cx(x), cy(y))
    return best[1], best[2]


class Tutorial:
    def __init__(self, app):
        self.app = app
        tk, ttk, P, S, root = app.tk, app.ttk, app.px, app.sp, app.root
        self.on = False
        self.i = 0
        self.mem = {}
        self.state = ""       # "" (sin condición) · "espera" · "hecho" (avanza en HOLD_S) · "ya" (ya se cumplía)
        self.t_done = 0.0
        self.key = None       # (rectángulo del objetivo, ancho, alto de la ventana) de la última colocación
        self.target = None
        self.opened = []      # tarjetas "Avanzado" que abrió el tutorial (se cierran al terminar)
        self.restore = {}
        self.ring = [tk.Frame(root, bd=0, highlightthickness=0) for _ in range(4)]
        for f in self.ring:
            theme.paint(f, bg="tutorial_ring")
        box = self.box = tk.Frame(root, bd=0, highlightthickness=P(2))
        theme.paint(box, bg="surface", highlightbackground="tutorial_ring", highlightcolor="tutorial_ring")
        wrap = P(theme.tok("size.tut_wrap"))

        def label(font, fg, **kw):
            lb = tk.Label(box, bd=0, anchor="w", justify="left", wraplength=wrap, padx=S("md"), **kw)
            theme.paint(lb, bg="surface", fg=fg, font=font)
            return lb
        self.num = label("font.small", "fg_muted")
        self.title = label("font.title", "fg")
        self.body = label("font.body", "fg")
        self.status = label("font.title", "ok")
        self.foot = label("font.small", "fg_muted", text="Enter: siguiente · Esc: omitir")
        row = ttk.Frame(box, padding=(S("md"), S("sm")))
        self.back_b = app.reg(ttk.Button(row, text="Atrás", takefocus=0, command=self.back), "tut.atras")
        self.next_b = app.reg(ttk.Button(row, text="Siguiente", takefocus=0, command=self.next), "tut.siguiente")
        self.skip_b = app.reg(ttk.Button(row, text="Omitir tutorial", takefocus=0, command=self.skip), "tut.omitir")
        for b in (self.back_b, self.next_b, self.skip_b):
            b.pack(side="left", padx=(0, S("sm")))
        self.num.pack(fill="x", pady=(S("md"), 0))
        self.title.pack(fill="x", pady=(S("xs"), 0))
        self.body.pack(fill="x", pady=(S("xs"), 0))
        self.status.pack(fill="x")
        row.pack(fill="x")
        self.foot.pack(fill="x", pady=(0, S("md")))
        # Enter y Esc: se enlazan una vez y solo actúan con el tutorial abierto y el foco en la ventana (no en un
        # campo de texto ni en un control: ahí conservan su función)
        for seq in ("<Return>", "<KP_Enter>"):
            root.bind(seq, self.on_enter, add="+")
        root.bind("<Escape>", self.on_esc, add="+")
        app.tip.attach_all()

    # --- ciclo de vida
    def owns(self, w):
        """¿w es del globo? (Navegar con Tab no les da foco: el tutorial nunca pausa las teclas.)"""
        return self.app.inside(w, self.box)

    def start(self):
        app = self.app
        if self.on:
            return
        self.on = True
        self.i = 0
        self.opened = []
        self.restore = dict(tab=app.tab_var.get(), mini=app.vista == "mini", geo=app.cur_geo(),
                            by_size=app.draw is not None and app.draw.mode == "mini" and app.vista != "mini",
                            blackout=app.scene.blackout, bo_step=False)
        app.tip.on = lambda: False  # tooltips en silencio mientras dura (no toca la preferencia del usuario)
        app.tip.hide()
        if app.draw is not None and app.draw.mode == "mini":
            app.leave_mini("auto" if app.vista == "mini" else None)
        app.update_band()
        self.show()

    def end(self):
        """Quita anillo y globo y deja la app como estaba (pestaña, "Avanzado" y vista); queda "visto"."""
        app, r = self.app, self.restore
        if not self.on:
            return
        self.on = False
        for f in self.ring:
            f.place_forget()
        self.box.place_forget()
        self.key = self.target = None
        app.tip.__dict__.pop("on", None)
        if r.get("bo_step") and not r["blackout"] and app.scene.blackout:  # nunca dejar las pantallas apagadas
            app.bo.set(False)
            app.scene.blackout = False
        for cid in self.opened:
            app.set_adv(cid, False)
        if app.tab_var.get() != r["tab"]:
            app.tab_var.set(r["tab"])
            app.show_tab()
        if r["mini"]:
            app.enter_mini()
        elif r["by_size"]:
            app.fit_geometry(r["geo"])
        app.set_tutorial("visto")

    def skip(self):
        self.end()

    def next(self):
        if not self.on:
            return
        if self.i >= len(STEPS) - 1:
            self.end()
        else:
            self.i += 1
            self.show()

    def back(self):
        if self.on and self.i > 0:
            self.i -= 1
            self.show()

    # --- teclado
    def key_ok(self, e):
        return self.on and str(e.widget) == str(self.app.root)  # el foco es de la ventana, no de un control

    def on_enter(self, e=None):
        if self.key_ok(e):
            self.next()

    def on_esc(self, e=None):
        if self.key_ok(e):
            self.skip()

    # --- un paso
    def by_id(self, wid):
        return next((w for w, i in self.app.ids.items() if i == wid), None)

    def show(self):
        app, st = self.app, STEPS[self.i]
        app.tip.hide()
        self.mem = {}
        if st.tab and app.tab_var.get() != st.tab:
            app.tab_var.set(st.tab)
            app.show_tab()
        w = self.target = self.by_id(st.id) if st.id else None
        if w is not None:
            for cid, (_, frame) in app.adv.items():  # el objetivo dentro de un "Avanzado" cerrado: se abre
                if app.inside(w, frame) and not app.adv_open[cid]:
                    app.set_adv(cid, True)
                    self.opened.append(cid)
        app.root.update_idletasks()
        if w is not None:
            self.reveal(w)
        if st.id == "blackout":
            self.restore["bo_step"] = True
        self.state = "" if st.done is None else "ya" if st.done(app, self.mem) else "espera"
        self.num.configure(text=f"Paso {self.i + 1} de {len(STEPS)}")
        self.title.configure(text=st.title)
        self.body.configure(text=st.text)
        self.status.configure(text="✓ Ya está" if self.state == "ya" else "")
        self.back_b.configure(state="normal" if self.i else "disabled")
        self.next_b.configure(text="Terminar" if self.i == len(STEPS) - 1 else "Siguiente")
        self.reposition(force=True)

    def reveal(self, w):
        """Si el objetivo está en el cuerpo de tarjetas y fuera de la vista, lo desplaza hasta verlo."""
        app = self.app
        if not (app.inside(w, app.body) and app.body_cv.winfo_viewable()):
            return
        y, h = w.winfo_rooty() - app.body.winfo_rooty(), w.winfo_height()
        top, view, total = app.body_cv.canvasy(0), app.body_cv.winfo_height(), max(app.body.winfo_height(), 1)
        if y < top or y + h > top + view:
            app.body_cv.yview_moveto(max(y - app.sp("md"), 0) / total)
            app.root.update_idletasks()

    def target_rect(self):
        """Rectángulo del objetivo en coordenadas de la raíz, o None si no se ve entero."""
        app, w, root = self.app, self.target, self.app.root
        if w is None or not w.winfo_viewable():
            return None
        x, y = w.winfo_rootx() - root.winfo_rootx(), w.winfo_rooty() - root.winfo_rooty()
        r = (x, y, w.winfo_width(), w.winfo_height())
        view = (0, 0, root.winfo_width(), root.winfo_height())
        if app.inside(w, app.body):  # y dentro de la parte visible del cuerpo de tarjetas
            cv = app.body_cv
            view = (cv.winfo_rootx() - root.winfo_rootx(), cv.winfo_rooty() - root.winfo_rooty(),
                    cv.winfo_width(), cv.winfo_height())
        if _overlap(r, view) < r[2] * r[3]:
            return None
        return r

    def reposition(self, force=False):
        """Anillo y globo según el objetivo y el tamaño de la ventana; solo si algo cambió."""
        app, root = self.app, self.app.root
        rect, ww, wh = self.target_rect(), root.winfo_width(), root.winfo_height()
        if (rect, ww, wh) == self.key and not force:
            return
        self.key = (rect, ww, wh)
        ring, margin = app.px(theme.tok("size.tut_ring")), app.px(theme.tok("size.tut_margin"))
        gap = app.px(theme.tok("size.tut_gap"))
        if rect:
            for f, (x, y, w, h) in zip(self.ring, ring_rects(*rect, ring, margin)):
                f.place(x=x, y=y, width=w, height=h)
                f.lift()
            near = margin + ring + gap
            obstacle = (rect[0] - near, rect[1] - near, rect[2] + 2 * near, rect[3] + 2 * near)
        else:
            for f in self.ring:
                f.place_forget()
            obstacle = None
        self.box.update_idletasks()
        x, y = bubble_pos(obstacle, (self.box.winfo_reqwidth(), self.box.winfo_reqheight()), (0, 0, ww, wh))
        self.box.place(x=x, y=y)
        self.box.lift()

    def tick(self, now=None):
        """Desde App.slow() (~30 Hz), solo mientras está activo: evalúa la condición del paso y recoloca."""
        if not self.on:
            return
        now = time.perf_counter() if now is None else now
        done = STEPS[self.i].done
        if self.state == "espera" and done(self.app, self.mem):
            self.state, self.t_done = "hecho", now
            self.status.configure(text="✓ Hecho")
        elif self.state == "hecho" and now - self.t_done >= HOLD_S:
            self.next()
            return
        self.reposition()
