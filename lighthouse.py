"""LightHouse: maqueta de luz virtual que reacciona a la música (WASAPI loopback).

python lighthouse.py          -> app (ventana Control + ventana Luz)
python lighthouse.py --test   -> self-check del motor con señal sintética
"""
import collections
import math
import sys
import threading
import time

import numpy as np
from scipy.signal import butter, sosfilt

BLOCK = 480  # frames por bloque (~10 ms @ 48 kHz)
FILTERS = {"Sub (60 Hz)": 60, "Kick (120 Hz)": 120, "Bajo (200 Hz)": 200, "Completo": 0}
# presets = valores de los mismos sliders (unidades de la GUI); el usuario puede moverlos después
CALM = {
    "Respiración suave": dict(calm_after=5, calm_smooth=1.5, calm_base=10, calm_depth=40),
    "Tenue fijo": dict(calm_after=5, calm_smooth=1.5, calm_base=20, calm_depth=0),
    "Casi apagado": dict(calm_after=5, calm_smooth=3, calm_base=3, calm_depth=5),
    "Demo (entra en 2 s)": dict(calm_after=2, calm_smooth=1, calm_base=10, calm_depth=60),
}
DELAYS = {"Salida por cable / USB (0 ms)": dict(delay=0), "Salida HDMI / monitor (50 ms)": dict(delay=50),
          "Salida Bluetooth (200 ms)": dict(delay=200)}
# blanco por temperatura (aprox. de cuerpo negro), interpolado
KELVIN = np.array([[2000, 255, 137, 18], [3000, 255, 180, 107], [4000, 255, 209, 163],
                   [5000, 255, 228, 206], [6500, 255, 249, 253], [8000, 227, 233, 255], [10000, 204, 219, 255]])
PALETTE = ["#ff2a55", "#ff9f1c", "#2ec4ff", "#9b5cff"]


class Engine:
    """Bloque de audio mono -> golpe / BPM / calma / luz 0..1.
    Sin audio ni GUI: se prueba alimentándolo con arrays."""

    def __init__(self, sr=48000):
        self.sr = sr
        # perillas: las escribe la GUI, las lee el hilo de audio (floats simples, el GIL basta)
        self.mode = "auto"         # auto | pulso | tranquilo | manual
        self.blackout = self.bump = False
        self.sens = 1.5            # umbral de golpe = 0.3/sens + flujo medio (1 s)
        self.min_gap = 0.25        # s, refractario entre golpes (0.25 => máx 240 BPM)
        self.gate_db = -50.0       # compuerta, medida antes del AGC
        self.sync = "kick"         # kick: flash en cada golpe | tempo: reloj al BPM, sigue sin kick
        self.bpm_src = "auto"      # auto: BPM detectado | manual: slider / tap
        self.bpm_manual = 120.0
        self.divisor = 1           # flash cada N eventos
        self.by_strength = True    # flash proporcional a la fuerza del golpe (mín. 60 %)
        self.decay = 0.25          # s hasta ~5 % del flash
        self.vmax, self.vmin = 1.0, 0.08  # master; piso del pulso
        self.gamma = 1.0
        self.delay = 0.0           # s; el loopback capta antes de que suene (BT/HDMI van atrasados)
        self.manual = 0.5
        self.calm_after = 5.0      # s sin golpes -> tranquilo
        self.calm_smooth = 1.5     # s, suavizado de la respiración
        self.calm_base = 0.10      # nivel de tranquilo
        self.calm_depth = 0.40     # cuánto sube con la música (0 = nivel fijo)
        self.set_band(120)
        # estado
        self.t = 0.0
        self.win = collections.deque(maxlen=4)     # RMS deslizante de 40 ms
        self.lbs = collections.deque([0.0], maxlen=4)
        self.peak_b = self.peak_f = 1e-4
        self.onset = self.o_avg = self.o_disp = self.thresh = self.lb = 0.0
        self.last_beat = self.last_flash = self.last_tick = -1e9
        self.beats = collections.deque(maxlen=9)
        self.taps = collections.deque(maxlen=5)
        self.count = self.flashes = self.out_n = self.k_last = self.off = 0
        self.phase = 0.0
        self.beat = False
        self.bpm = self.bpm_lock = 0.0
        self.calm = True
        self.calm_w = 1.0
        self.pulse = self.smooth = 0.0
        self.hist = collections.deque([(0.0, 0)], maxlen=64)
        self.out = 0.0

    def set_band(self, hz):
        """Pasa-banda 30 Hz..hz (fuera DC y rumble); hz=0 -> banda completa."""
        self.band = hz
        if hz:
            sos = butter(4, [30, hz], "bandpass", fs=self.sr, output="sos")
            self.filt = [sos, np.zeros((sos.shape[0], 2))]  # se reemplaza entero: seguro entre hilos
        else:
            self.filt = None

    def tap(self):
        """Tap tempo: 3+ toques fijan BPM manual; cada toque fija la fase."""
        if self.taps and self.t - self.taps[-1] > 2.0:
            self.taps.clear()
        self.taps.append(self.t)
        if len(self.taps) >= 3:
            self.bpm_manual = min(max(60 / float(np.mean(np.diff(self.taps))), 40.0), 240.0)
            self.bpm_src = "manual"
        self.phase, self.off = self.t, 0

    def process(self, x):
        dt = len(x) / self.sr
        self.t += dt
        y, f = x, self.filt
        if f is not None:
            y, f[1] = sosfilt(f[0], x, zi=f[1])
        self.win.append((float(np.mean(x * x)), float(np.mean(y * y))))
        full = math.sqrt(sum(w[0] for w in self.win) / len(self.win))
        band = math.sqrt(sum(w[1] for w in self.win) / len(self.win))

        # compuerta antes del AGC; bajo ella el AGC se congela y no infla el silencio
        silent = full < 10 ** (self.gate_db / 20)
        if not silent:
            k = math.exp(-dt / 8.0)
            self.peak_b = max(band, self.peak_b * k)
            self.peak_f = max(full, self.peak_f * k)
        lb = 0.0 if silent else band / self.peak_b
        lf = 0.0 if silent else full / self.peak_f
        self.lb = lb

        # golpe = subida de la envolvente en 40 ms (flujo), no nivel: un bajo sostenido no dispara
        self.onset = max(0.0, lb - self.lbs[0])
        self.lbs.append(lb)
        self.thresh = 0.3 / self.sens + self.o_avg
        self.beat = self.onset > self.thresh and self.t - self.last_beat > self.min_gap
        self.o_avg += (self.onset - self.o_avg) * (1 - math.exp(-dt / 1.0))
        self.o_disp = max(self.onset, self.o_disp * math.exp(-dt / 0.15))  # para el medidor

        if self.beat:
            if self.calm and self.t - self.last_beat < 1.5:  # sale de calma al 2º golpe seguido
                self.calm = False
            self.last_beat = self.t
            self.beats.append(self.t)
            self._bpm()
        if not self.calm and self.t - self.last_beat > self.calm_after:
            self.calm = True

        flash = False
        if self._tick(silent) if self.sync == "tempo" else self.beat:
            self.count += 1
            flash = self.count % self.divisor == 0
        if flash:
            s = (min(1.0, max(0.6, 2 * self.onset)) if self.beat else 0.6) if self.by_strength else 1.0
            if self.t - self.last_flash < 1 / 3:  # fotosensibilidad: >3 flashes/s -> media profundidad
                s *= 0.5
            self.last_flash = self.t
            self.flashes += 1
            self.pulse = max(self.pulse, s)
        else:
            self.pulse *= math.exp(-dt * 3 / self.decay)
        self.smooth += (lf - self.smooth) * (1 - math.exp(-dt / self.calm_smooth))
        tau = 0.5 if self.calm else 0.03  # entra a calma en ~1.5 s, sale en <100 ms (no llegar tarde al drop)
        self.calm_w += ((1.0 if self.calm else 0.0) - self.calm_w) * (1 - math.exp(-dt / tau))

        pulse_v = self.vmin + (1 - self.vmin) * self.pulse
        calm_v = self.calm_base + self.calm_depth * self.smooth  # banda completa, no solo graves
        v = {"pulso": pulse_v, "tranquilo": calm_v, "manual": self.manual,
             "auto": self.calm_w * calm_v + (1 - self.calm_w) * pulse_v}[self.mode]
        self.hist.append((min(max(v * self.vmax, 0.0), 1.0) ** self.gamma, self.flashes))
        out, self.out_n = self.hist[-1 - min(round(self.delay / dt), len(self.hist) - 1)]
        self.out = 0.0 if self.blackout else 1.0 if self.bump else out  # manuales sin retardo

    def _tick(self, silent):
        """Reloj de tempo: pulsa al BPM aunque el kick desaparezca. Un kick cerca de la grilla
        re-sincroniza la fase; dos seguidos fuera de ella re-enganchan (cambió el tema)."""
        if silent:
            return False
        bpm = self.bpm_manual if self.bpm_src == "manual" else self.bpm_lock
        if not bpm:
            return self.beat  # aún sin tempo fiable: cada golpe
        period = 60 / bpm
        tick = False
        if self.beat:
            e = ((self.t - self.phase) / period) % 1
            if min(e, 1 - e) < 0.25 or self.off >= 1:
                self.phase, self.off, self.k_last = self.t, 0, 0
                tick = True  # kick en la grilla: flash ya (salvo que la grilla acabe de disparar)
            else:
                self.off += 1
        k = math.floor((self.t - self.phase) / period)
        if k != self.k_last:  # cruzó un tiempo sin kick: el reloj dispara solo
            self.k_last, tick = k, True
        tick = tick and self.t - self.last_tick > 0.5 * period
        if tick:
            self.last_tick = self.t
        return tick

    def _bpm(self):
        iv = np.diff(self.beats)
        iv = iv[iv < 2.0]
        if len(iv) < 4:
            return
        med = float(np.median(iv))
        mad = float(np.median(np.abs(iv - med)))
        self.bpm = 60 / med if mad < 0.1 * med else 0.0  # 0 = sin confianza -> "--"
        self.bpm_lock = self.bpm or self.bpm_lock         # el reloj de tempo usa el último fiable


class App:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        import pyaudiowpatch as pa
        self.tk, self.ttk, self.pa = tk, ttk, pa

        self.eng = Engine()
        self.lock = threading.Lock()
        self.p = pa.PyAudio()
        self.stream = None
        self.last_audio = self.last_feed = time.perf_counter()
        self.zeros = np.zeros(BLOCK)
        self.color = ""
        self.vars = {}
        self.palette = list(PALETTE)

        root = self.root = tk.Tk()
        root.title("LightHouse · Control")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.light = tk.Toplevel(root, bg="black")
        self.light.title("LightHouse · Luz")
        self.light.geometry("640x400+60+60")
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
        fr = box("Salida de audio", 0)
        self.dev = ttk.Combobox(fr, state="readonly", width=44, takefocus=0)
        self.dev.pack(fill="x")
        self.dev.bind("<<ComboboxSelected>>", lambda e: self.open())
        row = ttk.Frame(fr); row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Reconectar", command=self.reconnect, takefocus=0).pack(side="left")
        self.status = ttk.Label(row, text="")
        self.status.pack(side="left", padx=6)

        fr = box("Modo", 0)
        self.mode = tk.StringVar(value=self.eng.mode)
        self.mode.trace_add("write", lambda *_: setattr(self.eng, "mode", self.mode.get()))
        for i, m in enumerate(("auto", "pulso", "tranquilo", "manual"), 1):
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
        div = ttk.Combobox(row, state="readonly", values=["1/1", "1/2", "1/4"], width=5, takefocus=0)
        div.set("1/1")
        div.pack(side="left")
        div.bind("<<ComboboxSelected>>", lambda e: setattr(self.eng, "divisor", int(div.get()[2:])))

        fr = box("Luz", 1)
        self.slider(fr, "Decay (ms)", "decay", 50, 1000, k=0.001)
        self.slider(fr, "Master (%)", "vmax", 0, 100, k=0.01)
        self.slider(fr, "Piso pulso (%)", "vmin", 0, 50, k=0.01)
        self.slider(fr, "Curva (gamma)", "gamma", 0.5, 3.0, res=0.1)
        self.slider(fr, "Manual (%)", "manual", 0, 100, k=0.01)
        self.presets(fr, DELAYS)
        self.slider(fr, "Retardo luz (ms)", "delay", 0, 300, k=0.001, res=5)

        # --- columna 2: tranquilo y color
        fr = box("Tranquilo", 2)
        self.presets(fr, CALM)
        self.slider(fr, "Entrar tras (s)", "calm_after", 2, 15)
        self.slider(fr, "Suavizado (s)", "calm_smooth", 1, 3, res=0.1)
        self.slider(fr, "Nivel base (%)", "calm_base", 0, 60, k=0.01)
        self.slider(fr, "Profundidad (%)", "calm_depth", 0, 60, k=0.01)

        fr = box("Color (opcional)", 2)
        self.color_mode = ttk.Combobox(fr, state="readonly", takefocus=0,
                                       values=["Blanco", "Temperatura", "Paleta (cambia en cada flash)"])
        self.color_mode.set("Blanco")
        self.color_mode.pack(fill="x")
        self.kelvin = self.slider(fr, "Temperatura (K)", None, 2000, 10000, res=100, init=4000)
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
        for i, m in enumerate(("auto", "pulso", "tranquilo", "manual"), 1):
            root.bind_all(str(i), lambda e, m=m: self.mode.set(m))
        root.bind_all("<KeyPress-f>", lambda e: setattr(self.eng, "bump", True))
        root.bind_all("<KeyRelease-f>", lambda e: setattr(self.eng, "bump", False))
        root.bind_all("<KeyPress-t>", lambda e: self.tap())

        self.refresh()
        self.open()
        self.tick()

    # --- widgets
    def slider(self, fr, label, attr, lo, hi, k=1.0, res=1, fn=None, init=None):
        tk = self.tk
        fn = fn or (lambda val: attr and setattr(self.eng, attr, val))
        var = tk.DoubleVar(value=round(getattr(self.eng, attr) / k, 3) if init is None else init)
        row = self.ttk.Frame(fr); row.pack(fill="x")
        self.ttk.Label(row, text=label, width=15).pack(side="left", anchor="s", pady=(0, 4))
        tk.Scale(row, from_=lo, to=hi, resolution=res, orient="horizontal", variable=var, length=200,
                 takefocus=0, command=lambda v: fn(float(v) * k)).pack(side="left", fill="x", expand=True)
        self.vars[attr or label] = (var, k)
        return var

    def check(self, fr, label, attr):
        var = self.tk.BooleanVar(value=getattr(self.eng, attr))
        self.ttk.Checkbutton(fr, text=label, variable=var, takefocus=0,
                             command=lambda: setattr(self.eng, attr, var.get())).pack(anchor="w", pady=(4, 0))

    def presets(self, fr, table):
        """Combo que mueve varios sliders a la vez; luego el usuario ajusta a mano."""
        cb = self.ttk.Combobox(fr, state="readonly", values=list(table), takefocus=0)
        cb.set(next(iter(table)))
        cb.pack(fill="x", pady=(4, 2))

        def apply(_):
            for attr, val in table[cb.get()].items():
                var, k = self.vars[attr]
                var.set(val)
                setattr(self.eng, attr, val * k)
        cb.bind("<<ComboboxSelected>>", apply)

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

    # --- audio
    def refresh(self, prefer=None):
        self.devs = list(self.p.get_loopback_device_info_generator())
        names = [d["name"] for d in self.devs]
        self.dev["values"] = names
        if prefer not in names:
            try:
                prefer = self.p.get_default_wasapi_loopback()["name"]
            except Exception:
                prefer = names[0] if names else None
        if prefer in names:
            self.dev.current(names.index(prefer))

    def close_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def reconnect(self):  # PyAudio cachea la lista: re-inicializar para ver salidas nuevas (HDMI, BT)
        self.close_stream()
        name = self.dev.get()
        self.p.terminate()
        self.p = self.pa.PyAudio()
        self.refresh(name)
        self.open()

    def open(self):
        self.close_stream()
        if not self.devs:
            self.status.config(text="Sin salidas loopback")
            return
        dev = self.devs[self.dev.current()]
        sr, ch = int(dev["defaultSampleRate"]), dev["maxInputChannels"]
        with self.lock:
            self.eng.sr = sr
            self.eng.set_band(self.eng.band)  # rehacer el filtro con la frecuencia nativa

        def cb(data, frames, info, status):
            x = np.frombuffer(data, np.float32).reshape(-1, ch).mean(axis=1)
            with self.lock:
                self.eng.process(x)
            self.last_audio = self.last_feed = time.perf_counter()
            return None, self.pa.paContinue

        try:
            self.stream = self.p.open(format=self.pa.paFloat32, channels=ch, rate=sr, input=True,
                                      input_device_index=dev["index"], frames_per_buffer=BLOCK,
                                      stream_callback=cb)
            self.status.config(text=f"{sr} Hz · {ch} canales")
        except Exception as ex:
            self.status.config(text=f"Error: {ex}")

    # --- render
    def base_rgb(self, e):
        m = self.color_mode.get()
        if m == "Temperatura":
            return [float(np.interp(self.kelvin.get(), KELVIN[:, 0], KELVIN[:, i])) for i in (1, 2, 3)]
        if m.startswith("Paleta"):
            return [c / 257 for c in self.root.winfo_rgb(self.palette[e.out_n % len(self.palette)])]
        return [255, 255, 255]

    def tick(self):
        now = time.perf_counter()
        if now - self.last_audio > 0.2:  # el loopback deja de entregar bloques en silencio
            n = min(int((now - self.last_feed) * self.eng.sr) // BLOCK, 100)
            if n:
                with self.lock:
                    for _ in range(n):
                        self.eng.process(self.zeros)
                self.last_feed = now
        e = self.eng
        color = "#%02x%02x%02x" % tuple(round(c * e.out) for c in self.base_rgb(e))
        if color != self.color:
            self.color = color
            self.light.configure(bg=color)
        w = 320
        self.meter.coords(self.bar_l, 0, 4, w * min(e.lb, 1), 24)
        self.meter.coords(self.bar_o, 0, 32, w * min(e.o_disp, 1), 52)
        x = w * min(e.thresh, 1)
        self.meter.coords(self.line, x, 28, x, 56)
        self.dot.itemconfig(self.dot_id, fill="white" if e.t - e.last_beat < 0.1 else "#333")
        if e.sync == "tempo" and e.bpm_src == "manual":
            self.bpm.config(text=f"{e.bpm_manual:.0f} BPM (manual)")
        else:
            self.bpm.config(text=f"{e.bpm:.0f} BPM" if e.bpm and e.t - e.last_beat < 2 else "-- BPM")
        self.state.config(text="BLACKOUT" if e.blackout else "FLASH" if e.bump else
                          e.mode.upper() if e.mode != "auto" else
                          "AUTO · TRANQUILO" if e.calm else "AUTO · PULSO")
        self.root.after(15, self.tick)

    def quit(self):
        self.close_stream()
        self.p.terminate()
        self.root.destroy()


def selftest():
    sr, spb = 48000, 0.5  # 120 BPM
    rng = np.random.default_rng(0)

    def groove(secs):
        t = np.arange(int(sr * secs)) / sr
        s = np.zeros_like(t)
        for k in np.arange(0, secs, spb):  # kick 55 Hz con caída
            m = t >= k
            s[m] += 0.8 * np.sin(2 * np.pi * 55 * (t[m] - k)) * np.exp(-(t[m] - k) / 0.12)
        for h in np.arange(spb / 2, secs, spb):  # hi-hat a contratiempo
            i = int(h * sr)
            s[i:i + 1500] += 0.4 * rng.standard_normal(len(s[i:i + 1500]))
        f = np.where((t // 2) % 2 == 0, 45.0, 52.0)  # bajo sostenido, cambia de nota sin re-ataque
        return s + 0.35 * np.sin(2 * np.pi * np.cumsum(f) / sr)

    pad = 0.05 * np.sin(2 * np.pi * 440 * np.arange(sr * 6) / sr)  # breakdown: pad suave sin graves
    sig = np.concatenate([groove(8), pad, groove(6), np.zeros(sr * 3)])

    def run(**knobs):
        e = Engine(sr)
        for k, v in knobs.items():
            setattr(e, k, v)
        e.set_band(e.band)
        log = []
        for i in range(0, len(sig) - BLOCK + 1, BLOCK):
            e.process(sig[i:i + BLOCK])
            log.append((e.t, e.beat, e.calm, e.out, e.flashes))
        return e, np.array(log)

    def flashes(log, a, b):  # flashes en [a, b) s
        i, j = np.searchsorted(log[:, 0], [a, b])
        return int(log[j, 4] - log[i, 4])

    e, log = run()
    at = lambda s: log[np.searchsorted(log[:, 0], s)]
    beats1 = int(log[log[:, 0] < 8, 1].sum())
    assert 15 <= beats1 <= 16, beats1                    # 16 kicks: ni hats ni bajo sostenido disparan
    assert abs(e.bpm - 120) < 2, e.bpm
    assert not at(7.9)[2] and at(13.9)[2]                # entra a tranquilo en el breakdown
    assert not at(14.6)[2]                               # sale al 2º kick (14.5 s)
    assert abs(e.out - e.vmin) < 0.01, e.out             # silencio final: cae al piso
    assert flashes(log, 8.2, 9.9) == 0                   # modo kick: sin kick no hay flash
    _, full = run(band=0)
    beats_full = int(full[full[:, 0] < 8, 1].sum())
    assert beats_full > beats1, beats_full               # sin filtro los hats sí disparan
    _, late = run(delay=0.1)
    assert np.allclose(late[10:, 3], log[:-10, 3])       # retardo = 10 bloques exactos
    _, tempo = run(sync="tempo")
    assert 15 <= flashes(tempo, 0, 7.9) <= 17            # al tempo: igual que los kicks mientras hay kick
    assert flashes(tempo, 8.2, 9.9) == 3                 # sin kick sigue pulsando (8.5, 9.0, 9.5)
    assert flashes(tempo, 20.2, 22.9) == 0               # silencio real: se detiene
    t = Engine()
    for s in (1.0, 1.5, 2.0, 2.5):
        t.t = s
        t.tap()
    assert t.bpm_src == "manual" and abs(t.bpm_manual - 120) < 0.1, t.bpm_manual
    print(f"ok: bpm={e.bpm:.1f} golpes={beats1}/16 (sin filtro: {beats_full}) "
          f"tempo sin kick: {flashes(tempo, 8.2, 9.9)} flashes")


if __name__ == "__main__":
    selftest() if "--test" in sys.argv else App().root.mainloop()
