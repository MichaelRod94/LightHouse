"""GUI: ventana Control + ventana Luz, presets, watchdog de silencio, reconexión y config persistente."""
import logging
import re
import threading
import time

import numpy as np

from . import config, win32
from .audio import Audio
from .engine import BLOCK, Engine

log = logging.getLogger(__name__)

FILTERS = {"Sub (60 Hz)": 60, "Kick (120 Hz)": 120, "Bajo (200 Hz)": 200, "Completo": 0}
# presets = valores de los mismos sliders (unidades de la GUI); el usuario puede moverlos después
CALM = {
    "Respiración suave": dict(calm_after=5, calm_smooth=1.5, calm_base=10, calm_depth=40),
    "Tenue fijo": dict(calm_after=5, calm_smooth=1.5, calm_base=20, calm_depth=0),
    "Casi apagado": dict(calm_after=5, calm_smooth=3, calm_base=3, calm_depth=5),
    "Demo (entra en 2 s)": dict(calm_after=2, calm_smooth=1, calm_base=10, calm_depth=60),
}
OFFSETS = {"Salida por cable / USB (0 ms)": dict(offset=0), "Salida HDMI / monitor (50 ms)": dict(offset=50),
           "Salida Bluetooth (200 ms)": dict(offset=200)}
# blanco por temperatura (aprox. de cuerpo negro), interpolado
KELVIN = np.array([[2000, 255, 137, 18], [3000, 255, 180, 107], [4000, 255, 209, 163],
                   [5000, 255, 228, 206], [6500, 255, 249, 253], [8000, 227, 233, 255], [10000, 204, 219, 255]])
PALETTE = ["#ff2a55", "#ff9f1c", "#2ec4ff", "#9b5cff"]
MODES = ("auto", "pulso", "tranquilo", "manual")
COLOR_MODES = ["Blanco", "Temperatura", "Paleta (cambia en cada flash)"]
LIGHT_GEO = "640x400+60+60"
GEO_RE = re.compile(r"^\d+x\d+[+-]-?\d+[+-]-?\d+$")
MIC_HINT = ("Revisa Configuración → Privacidad → Micrófono → "
            "Permitir que las aplicaciones de escritorio accedan")
RETRY_S, NO_SIGNAL_S, CLIP_S = 3.0, 3.0, 0.5
LAST_ERROR = None  # último error no controlado; el loop lento lo muestra en el label de estado


def report(exc_type, exc, tb, where="excepción"):
    """Traceback al log y texto corto para el label de estado."""
    global LAST_ERROR
    log.error("%s no controlada", where, exc_info=(exc_type, exc, tb))
    LAST_ERROR = f"Error: {exc_type.__name__}: {exc}"[:80]


class App:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk

        self.eng = Engine()
        self.lock = threading.Lock()
        self.audio = Audio(self.on_block)
        self.last_audio = self.last_feed = time.perf_counter()
        self.zeros = np.zeros(BLOCK)
        self.color, self.key, self.rgbs = "", None, [(255, 255, 255)]
        self.vars = {}    # llave -> (var, k, fn, lo, hi)
        self.scales = {}  # llave -> tk.Scale
        self.checks = {}  # atributo del motor -> BooleanVar
        self.palette = list(PALETTE)
        self.geo = {"geo_control": "", "geo_light": LIGHT_GEO}  # última geometría válida vista
        self.chan_idx = 0           # 0 = Mezcla, n = Canal n
        self.want = None            # dispositivo que debe estar abierto (para reintentar)
        self.retry_t = 0.0
        self.was_alive = False
        self.shown = {}             # lo último que put() mandó a cada widget

        root = self.root = tk.Tk()
        root.title("LightHouse · Control")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.report_callback_exception = lambda *a: report(*a, where="callback de Tk")
        self.light = tk.Toplevel(root, bg="black")
        self.light.title("LightHouse · Luz")
        self.light.geometry(LIGHT_GEO)
        self.light.protocol("WM_DELETE_WINDOW", self.light.iconify)
        self.light.bind("<F11>", lambda e: self.fullscreen(None))
        self.light.bind("<Double-Button-1>", lambda e: self.fullscreen(None))
        self.light.bind("<Escape>", lambda e: self.fullscreen(False))

        cols = [ttk.Frame(root, padding=6) for _ in range(3)]
        for i, c in enumerate(cols):
            c.grid(row=0, column=i, sticky="n")

        def box(title, col):
            fr = ttk.LabelFrame(cols[col], text=title, padding=6)
            fr.pack(fill="x", pady=3)
            return fr

        # --- columna 0: entrada y detección
        fr = box("Fuente de audio", 0)
        self.dev = ttk.Combobox(fr, state="readonly", width=44, takefocus=0)
        self.dev.pack(fill="x")
        self.dev.bind("<<ComboboxSelected>>", lambda e: self.pick_device())
        row = ttk.Frame(fr); row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Canal").pack(side="left")
        self.chan = ttk.Combobox(row, state="readonly", values=["Mezcla"], width=9, takefocus=0)
        self.chan.current(0)
        self.chan.pack(side="left", padx=6)
        self.chan.bind("<<ComboboxSelected>>", lambda e: self.pick_channel())
        self.no_sig = tk.Label(row, text="", fg="#d00", font=("Segoe UI", 9, "bold"))
        self.no_sig.pack(side="left", padx=4)
        self.clip = tk.Label(row, text="", fg="#e60", font=("Segoe UI", 9, "bold"))
        self.clip.pack(side="left", padx=4)
        row = ttk.Frame(fr); row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Reconectar", command=self.reconnect, takefocus=0).pack(side="left")
        self.status = ttk.Label(row, text="", wraplength=250)
        self.status.pack(side="left", padx=6)
        self.low_prio = tk.BooleanVar(value=True)
        self.low_prio.trace_add("write", lambda *_: win32.set_low_priority(self.low_prio.get()))
        ttk.Checkbutton(fr, text="Prioridad baja (laptop DJ)", variable=self.low_prio,
                        takefocus=0).pack(anchor="w", pady=(4, 0))

        fr = box("Ganancia", 0)
        self.agc = tk.BooleanVar(value=self.eng.agc)
        self.checks["agc"] = self.agc
        row = ttk.Frame(fr); row.pack(fill="x")
        ttk.Radiobutton(row, text="Automática (AGC)", value=True, variable=self.agc,
                        takefocus=0).pack(side="left")
        ttk.Radiobutton(row, text="Fija (la perilla manda)", value=False, variable=self.agc,
                        takefocus=0).pack(side="left", padx=8)
        self.slider(fr, "Referencia (dBFS)", "ref_db", -40, 0)
        self.agc.trace_add("write", lambda *_: self.set_agc())
        self.set_agc()

        fr = box("Modo", 0)
        self.mode = tk.StringVar(value=self.eng.mode)
        self.mode.trace_add("write", lambda *_: setattr(self.eng, "mode", self.mode.get()))
        for i, m in enumerate(MODES, 1):
            ttk.Radiobutton(fr, text=f"{i} {m.capitalize()}", value=m, variable=self.mode,
                            takefocus=0).pack(side="left")
        self.bo = tk.BooleanVar(value=False)
        tk.Checkbutton(fr, text="Blackout", variable=self.bo, indicatoron=False, selectcolor="#c33",
                       takefocus=0, padx=8, command=lambda: setattr(self.eng, "blackout", self.bo.get())
                       ).pack(side="right")

        fr = box("Filtro (qué escucha el detector de golpe)", 0)
        self.preset = ttk.Combobox(fr, state="readonly", values=list(FILTERS), takefocus=0)
        self.preset.set("Kick (120 Hz)")
        self.preset.pack(fill="x")
        self.preset.bind("<<ComboboxSelected>>", lambda e: self.pick_filter())
        self.band = self.slider(fr, "Corte (Hz)", "band", 40, 250, fn=self.band_from_slider)

        fr = box("Golpe", 0)
        self.slider(fr, "Sensibilidad (×)", "sens", 1.0, 3.0, res=0.1)
        self.slider(fr, "Refractario (ms)", "min_gap", 120, 500, k=0.001)
        self.slider(fr, "Compuerta (dB)", "gate_db", -60, -30)
        self.check(fr, "Intensidad por golpe", "by_strength")

        # --- columna 1: lecturas, tempo, luz
        fr = box("Lecturas", 1)
        self.meter = tk.Canvas(fr, width=320, height=56, bg="#111", highlightthickness=0)
        self.meter.pack()
        self.bar_l = self.meter.create_rectangle(0, 4, 0, 24, fill="#666", width=0)
        self.bar_o = self.meter.create_rectangle(0, 32, 0, 52, fill="#eee", width=0)
        self.line = self.meter.create_line(0, 28, 0, 56, fill="#e33", width=2)
        ttk.Label(fr, text="gris: nivel de banda · blanco: subida (golpe) · rojo: umbral",
                  foreground="#666").pack()
        row = ttk.Frame(fr); row.pack(fill="x")
        self.dot = tk.Canvas(row, width=26, height=26, highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(3, 3, 23, 23, fill="#333", width=0)
        self.bpm = ttk.Label(row, text="-- BPM", font=("Segoe UI", 18, "bold"))
        self.bpm.pack(side="left", padx=8)
        self.state = ttk.Label(row, text="", font=("Segoe UI", 11, "bold"))
        self.state.pack(side="right")

        fr = box("Tempo", 1)
        row = ttk.Frame(fr); row.pack(fill="x")
        self.sync = tk.StringVar(value=self.eng.sync)
        self.sync.trace_add("write", lambda *_: setattr(self.eng, "sync", self.sync.get()))
        ttk.Radiobutton(row, text="Cada kick", value="kick", variable=self.sync, takefocus=0).pack(side="left")
        ttk.Radiobutton(row, text="Al tempo (sigue sin kick)", value="tempo", variable=self.sync,
                        takefocus=0).pack(side="left", padx=8)
        row = ttk.Frame(fr); row.pack(fill="x", pady=4)
        ttk.Label(row, text="BPM", width=15).pack(side="left")
        self.src = ttk.Combobox(row, state="readonly", values=["Detectado", "Manual / Tap"], width=13,
                                takefocus=0)
        self.src.set("Detectado")
        self.src.pack(side="left")
        self.src.bind("<<ComboboxSelected>>", lambda e: setattr(
            self.eng, "bpm_src", "manual" if self.src.get().startswith("Manual") else "auto"))
        ttk.Button(row, text="Tap [T]", command=self.tap, takefocus=0, width=8).pack(side="left", padx=6)
        self.slider(fr, "BPM manual", "bpm_manual", 60, 200)
        row = ttk.Frame(fr); row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Flash cada", width=15).pack(side="left")
        div = self.div = ttk.Combobox(row, state="readonly", values=["1/1", "1/2", "1/4"], width=5, takefocus=0)
        div.set("1/1")
        div.pack(side="left")
        div.bind("<<ComboboxSelected>>", lambda e: setattr(self.eng, "divisor", int(div.get()[2:])))

        fr = box("Luz", 1)
        self.slider(fr, "Decay (ms)", "decay", 50, 1000, k=0.001)
        self.slider(fr, "Master (%)", "vmax", 0, 100, k=0.01)
        self.slider(fr, "Piso pulso (%)", "vmin", 0, 50, k=0.01)
        self.slider(fr, "Curva (gamma)", "gamma", 0.5, 3.0, res=0.1)
        self.slider(fr, "Manual (%)", "manual", 0, 100, k=0.01)
        self.presets(fr, OFFSETS)
        self.slider(fr, "Offset (ms)", "offset", -150, 300, k=0.001, res=5)
        self.lead = ttk.Label(fr, text="", foreground="#666")
        self.lead.pack(anchor="w")

        # --- columna 2: tranquilo y color
        fr = box("Tranquilo", 2)
        self.presets(fr, CALM)
        self.slider(fr, "Entrar tras (s)", "calm_after", 2, 15)
        self.slider(fr, "Suavizado (s)", "calm_smooth", 1, 3, res=0.1)
        self.slider(fr, "Nivel base (%)", "calm_base", 0, 60, k=0.01)
        self.slider(fr, "Profundidad (%)", "calm_depth", 0, 60, k=0.01)

        fr = box("Color (opcional)", 2)
        self.color_mode = ttk.Combobox(fr, state="readonly", takefocus=0, values=COLOR_MODES)
        self.color_mode.set("Blanco")
        self.color_mode.pack(fill="x")
        self.kelvin = self.slider(fr, "Temperatura (K)", None, 2000, 10000, res=100, init=4000, key="kelvin")
        row = ttk.Frame(fr); row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Paleta", width=15).pack(side="left")
        self.swatch = tk.Canvas(row, width=110, height=22, highlightthickness=0)
        self.swatch.pack(side="left")
        ttk.Button(row, text="+", width=3, command=self.add_color, takefocus=0).pack(side="left", padx=2)
        ttk.Button(row, text="−", width=3, command=self.pop_color, takefocus=0).pack(side="left")
        self.draw_palette()

        ttk.Label(root, foreground="#666", padding=(8, 0, 8, 8), text=(
            "Espacio: Blackout · 1-4: modos · F (mantener): flash 100 % · T: tap tempo · "
            "Ventana Luz: F11 / doble clic = pantalla completa, Esc sale")).grid(row=1, column=0, columnspan=3)

        root.bind_all("<space>", lambda e: (self.bo.set(not self.bo.get()),
                                            setattr(self.eng, "blackout", self.bo.get())))
        for i, m in enumerate(MODES, 1):
            root.bind_all(str(i), lambda e, m=m: self.mode.set(m))
        root.bind_all("<KeyPress-f>", lambda e: setattr(self.eng, "bump", True))
        root.bind_all("<KeyRelease-f>", lambda e: setattr(self.eng, "bump", False))
        root.bind_all("<KeyPress-t>", lambda e: self.tap())

        # config: los defaults son los valores iniciales de arriba (Engine + UI); lo guardado válido los pisa
        defaults = self.snapshot()
        cfg = config.load(defaults)
        self.apply(cfg)  # aplica también la prioridad (trace de low_prio)
        self.snap = self.saved = self.snapshot()
        self.dirty_t = None
        self.fast_cmd = root.register(self.fast)
        self.wake, self.running = threading.Event(), True
        threading.Thread(target=self.waker, name="render", daemon=True).start()
        self.refresh(cfg["device"] or None)
        self.open()
        self.slow()
        self.autosave()

    # --- widgets
    def slider(self, fr, label, attr, lo, hi, k=1.0, res=1, fn=None, init=None, key=None):
        tk = self.tk
        fn = fn or (lambda val: attr and setattr(self.eng, attr, val))
        var = tk.DoubleVar(value=round(getattr(self.eng, attr) / k, 3) if init is None else init)
        row = self.ttk.Frame(fr); row.pack(fill="x")
        self.ttk.Label(row, text=label, width=15).pack(side="left", anchor="s", pady=(0, 4))
        sc = tk.Scale(row, from_=lo, to=hi, resolution=res, orient="horizontal", variable=var, length=200,
                      takefocus=0, command=lambda v: fn(float(v) * k))
        sc.pack(side="left", fill="x", expand=True)
        self.vars[key or attr or label] = (var, k, fn, lo, hi)
        self.scales[key or attr or label] = sc
        return var

    def check(self, fr, label, attr):
        var = self.tk.BooleanVar(value=getattr(self.eng, attr))
        self.ttk.Checkbutton(fr, text=label, variable=var, takefocus=0,
                             command=lambda: setattr(self.eng, attr, var.get())).pack(anchor="w", pady=(4, 0))
        self.checks[attr] = var

    def presets(self, fr, table):
        """Combo que mueve varios sliders a la vez; luego el usuario ajusta a mano."""
        cb = self.ttk.Combobox(fr, state="readonly", values=list(table), takefocus=0)
        cb.set(next(iter(table)))
        cb.pack(fill="x", pady=(4, 2))

        def apply(_):
            for attr, val in table[cb.get()].items():
                var, k = self.vars[attr][:2]
                var.set(val)
                setattr(self.eng, attr, val * k)
        cb.bind("<<ComboboxSelected>>", apply)

    def set_agc(self):
        """AGC o ganancia fija; la referencia solo se mueve en Fija."""
        on = self.agc.get()
        self.eng.agc = on
        self.scales["ref_db"].config(state="disabled" if on else "normal", fg="#999" if on else "black")

    def band_from_slider(self, hz):
        hz = int(hz)
        self.eng.set_band(hz)
        self.preset.set(next((n for n, v in FILTERS.items() if v == hz), f"Personalizado ({hz} Hz)"))

    def pick_filter(self):
        hz = FILTERS[self.preset.get()]
        if hz:
            self.band.set(hz)
        self.eng.set_band(hz)

    def tap(self):
        with self.lock:
            self.eng.tap()
        if self.eng.bpm_src == "manual":
            self.src.set("Manual / Tap")
            self.vars["bpm_manual"][0].set(round(self.eng.bpm_manual))

    def add_color(self):
        from tkinter import colorchooser
        c = colorchooser.askcolor(parent=self.root, title="Color para la paleta")[1]
        if c:
            self.palette.append(c)
            self.draw_palette()

    def pop_color(self):
        if len(self.palette) > 1:
            self.palette.pop()
            self.draw_palette()

    def draw_palette(self):
        self.swatch.delete("all")
        w = 110 / len(self.palette)
        for i, c in enumerate(self.palette):
            self.swatch.create_rectangle(i * w, 0, (i + 1) * w, 22, fill=c, width=0)

    def fullscreen(self, on):
        on = not self.light.attributes("-fullscreen") if on is None else on
        self.light.attributes("-fullscreen", on)

    # --- config
    def snapshot(self):
        """Todo lo persistente, en unidades de la GUI. Llave = nombre en config.json."""
        s = {k: v[0].get() for k, v in self.vars.items()}
        s.update({a: v.get() for a, v in self.checks.items()})
        s.update(mode=self.mode.get(), sync=self.sync.get(), bpm_src=self.eng.bpm_src,
                 divisor=self.eng.divisor, preset=self.preset.get(), color_mode=self.color_mode.get(),
                 palette=list(self.palette), device=self.dev.get(), channel=self.chan_idx,
                 low_priority=self.low_prio.get())
        for key, w in (("geo_control", self.root), ("geo_light", self.light)):
            if w.winfo_viewable() and not (w is self.light and w.attributes("-fullscreen")):
                self.geo[key] = w.geometry()
        s.update(self.geo)
        return s

    def apply(self, c):
        """Aplica un dict de config (ya con tipos válidos) a widgets y motor."""
        def pick(key, allowed):
            if c[key] in allowed:
                return True
            log.warning("config: %r=%r no es válido; se usa el default", key, c[key])
            return False

        for key, (var, k, fn, lo, hi) in self.vars.items():
            v = min(max(c[key], lo), hi)
            var.set(v)
            fn(v * k)
        for attr, var in self.checks.items():
            var.set(c[attr])
            setattr(self.eng, attr, c[attr])
        if pick("mode", MODES):
            self.mode.set(c["mode"])
        if pick("sync", ("kick", "tempo")):
            self.sync.set(c["sync"])
        if pick("bpm_src", ("auto", "manual")):
            self.eng.bpm_src = c["bpm_src"]
            self.src.set("Manual / Tap" if c["bpm_src"] == "manual" else "Detectado")
        if pick("divisor", (1, 2, 4)):
            self.eng.divisor = int(c["divisor"])
            self.div.set(f"1/{self.eng.divisor}")
        if c["preset"] == "Completo":  # el slider de corte no llega a 0: "Completo" se guarda aparte
            self.preset.set("Completo")
            self.eng.set_band(0)
        if pick("color_mode", COLOR_MODES):
            self.color_mode.set(c["color_mode"])
        if pick("channel", range(65)):
            self.chan_idx = int(c["channel"])  # se ajusta al dispositivo al abrirlo
        self.low_prio.set(c["low_priority"])
        try:
            for col in c["palette"]:
                self.root.winfo_rgb(col)
            self.palette = list(c["palette"])
            self.draw_palette()
        except self.tk.TclError:
            log.warning("config: paleta inválida %r; se usa el default", c["palette"])
        for key, w in (("geo_control", self.root), ("geo_light", self.light)):
            if GEO_RE.match(c[key]):  # ponytail: no valida que caiga en un monitor existente; F5 lo revisa
                w.geometry(c[key])
                self.geo[key] = c[key]
            elif c[key]:
                log.warning("config: %r=%r no es válido", key, c[key])

    def save(self):
        try:
            config.save(self.snapshot())
        except Exception:
            log.exception("no se pudo guardar la config")

    def autosave(self):
        # ponytail: debounce por sondeo a 2 Hz (compara snapshots); si hiciera falta, engancharlo a cada widget
        now = time.perf_counter()
        s = self.snapshot()
        if s != self.snap:
            self.snap, self.dirty_t = s, now
        elif self.dirty_t and now - self.dirty_t >= 1.0 and s != self.saved:
            self.save()
            self.saved, self.dirty_t = s, None
        self.root.after(500, self.autosave)

    # --- audio
    def on_block(self, x):  # hilo de audio
        with self.lock:
            self.eng.process(x)
        self.last_audio = self.last_feed = time.perf_counter()
        self.wake.set()  # pintar ya (no bloquea al hilo de audio)

    def waker(self):
        """Hilo "render": por cada bloque pide al hilo Tk que pinte (tkinter serializa la llamada).
        Reemplaza al after(1) del diseño: en Tcl 8.6/Windows after(1) gira al ~100 % de un núcleo."""
        while self.running:
            self.wake.wait()
            self.wake.clear()
            try:
                self.root.tk.call(self.fast_cmd)
            except Exception:  # aún sin mainloop (RuntimeError) o cerrando (TclError)
                time.sleep(0.05)

    def refresh(self, prefer=None):
        names, i = self.audio.refresh(prefer)
        self.dev["values"] = names
        if i is not None:
            self.dev.current(i)

    def reconnect(self):
        names, i = self.audio.reconnect(self.dev.get())
        self.dev["values"] = names
        if i is not None:
            self.dev.current(i)
        self.open()

    def pick_device(self):
        self.chan_idx = 0  # otro dispositivo: empieza en Mezcla
        self.open()

    def pick_channel(self):
        self.chan_idx = self.chan.current()
        self.audio.sel = self.chan_idx - 1 if self.chan_idx > 0 else None

    def open(self):
        self.audio.close()
        self.retry_t, self.was_alive = time.perf_counter(), False  # un fallo al abrir no pisa su mensaje
        i = self.dev.current()
        if not self.audio.devs or i < 0:
            self.want = None
            self.status.config(text="Sin dispositivos de audio")
            log.warning("sin dispositivos de audio")
            return
        self.want = self.dev.get()
        sr, ch = self.audio.info(i)
        self.chan["values"] = ["Mezcla"] + [f"Canal {n}" for n in range(1, ch + 1)]
        self.chan.current(self.chan_idx if self.chan_idx <= ch else 0)
        self.audio.sel = self.chan.current() - 1 if self.chan.current() > 0 else None
        with self.lock:
            self.eng.sr = sr
            self.eng.set_band(self.eng.band)  # rehacer el filtro con la frecuencia nativa
            self.eng.last_sound = self.eng.t  # SIN SEÑAL cuenta sus 3 s desde que se abre
        try:
            self.audio.open(i)
            self.status.config(text=f"{sr} Hz · {ch} canales")
        except Exception as ex:
            self.status.config(text=f"Error: {ex}" + (f". {MIC_HINT}" if self.audio.is_input(i) else ""))

    def retry(self):
        """Stream caído: re-enumera y reabre el MISMO dispositivo; si no está, espera al próximo intento."""
        name = self.want
        log.info("reintentando abrir %r", name)
        names, i = self.audio.reconnect(name)
        self.dev["values"] = names
        if i is not None and names[i] == name:
            self.dev.current(i)
            self.open()
        else:
            self.dev.set(name)  # se conserva (y se guarda) aunque no esté en la lista
            self.retry_t = time.perf_counter()
            self.status.config(text=f"Reconectando… (no está: {name})")

    # --- render
    def base_rgbs(self):
        """Colores base (0..255) a escalar por la salida; varios = paleta, uno por flash."""
        m = self.color_mode.get()
        if m == "Temperatura":
            return [tuple(float(np.interp(self.kelvin.get(), KELVIN[:, 0], KELVIN[:, i])) for i in (1, 2, 3))]
        if m.startswith("Paleta"):
            return [tuple(c / 257 for c in self.root.winfo_rgb(p)) for p in self.palette]
        return [(255, 255, 255)]

    def fast(self):
        """Render rápido (por bloque de audio, vía waker; y en cada tick lento): solo lee la salida
        del motor y pinta si cambió."""
        e = self.eng
        out, n = e.out, e.out_n
        if (out, n) != self.key:
            self.key = out, n
            rgb = self.rgbs[n % len(self.rgbs)]
            color = "#%02x%02x%02x" % (round(rgb[0] * out), round(rgb[1] * out), round(rgb[2] * out))
            if color != self.color:
                self.color = color
                self.light.configure(bg=color)

    def slow(self):
        """Loop lento (~30 Hz): watchdog de silencio, reconexión, medidores, labels e indicadores."""
        global LAST_ERROR
        self.root.after(33, self.slow)  # primero: una excepción (p. ej. al reconectar) no detiene el loop
        now = time.perf_counter()
        if now - self.last_audio > 0.2:  # el loopback deja de entregar bloques en silencio
            n = min(int((now - self.last_feed) * self.eng.sr) // BLOCK, 100)
            if n:
                with self.lock:
                    for _ in range(n):
                        self.eng.process(self.zeros)
                self.last_feed = now
        alive = self.audio.alive()
        if self.want and not alive:
            if self.was_alive:
                log.warning("el stream de %r dejó de entregar audio; reintento cada %g s", self.want, RETRY_S)
                self.status.config(text="Sin audio: reconectando…")
            if now - self.retry_t >= RETRY_S:
                self.retry()
                alive = self.audio.alive()
        self.was_alive = alive
        if LAST_ERROR:
            self.status.config(text=LAST_ERROR)
            LAST_ERROR = None
        rgbs = self.base_rgbs()
        if rgbs != self.rgbs:
            self.rgbs, self.key = rgbs, None  # repinta aunque la salida no cambie
        self.fast()  # sin bloques (loopback en silencio, sin stream) también se pinta
        e, put = self.eng, self.put
        w = 320
        put(self.meter.coords, self.bar_l, 0, 4, round(w * min(e.lb, 1)), 24)
        put(self.meter.coords, self.bar_o, 0, 32, round(w * min(e.o_disp, 1)), 52)
        x = round(w * min(e.thresh, 1))
        put(self.meter.coords, self.line, x, 28, x, 56)
        put(self.dot.itemconfig, self.dot_id, fill="white" if e.t - e.last_beat < 0.1 else "#333")
        if e.sync == "tempo" and e.bpm_src == "manual":
            put(self.bpm.config, text=f"{e.bpm_manual:.0f} BPM (manual)")
        else:
            put(self.bpm.config, text=f"{e.bpm:.0f} BPM" if e.bpm and e.t - e.last_beat < 2 else "-- BPM")
        put(self.state.config, text="BLACKOUT" if e.blackout else "FLASH" if e.bump else
            e.mode.upper() if e.mode != "auto" else "AUTO · TRANQUILO" if e.calm else "AUTO · PULSO")
        put(self.lead.config, text="" if e.offset >= 0 else "anticipación activa" if e.lead() else
            "anticipación inactiva (requiere Al tempo)" if e.sync != "tempo" else
            "anticipación inactiva (esperando BPM fiable)")
        put(self.no_sig.config, text="SIN SEÑAL" if alive and e.t - e.last_sound > NO_SIGNAL_S else "")
        put(self.clip.config, text="SATURA" if now - self.audio.clip_t < CLIP_S else "")

    def put(self, fn, *args, **kw):
        """fn(*args, **kw) solo si cambió desde la última vez: cada config/coords hace redibujar a Tk."""
        key = (fn.__self__, fn.__name__, args[:1])
        if self.shown.get(key) != (args, kw):
            self.shown[key] = (args, kw)
            fn(*args, **kw)

    def quit(self):
        self.save()
        self.running = False
        self.audio.terminate()
        self.wake.set()
        self.root.destroy()
