"""GUI: ventana Control (pestañas Show / Audio / Salidas) + salidas de video, looks por teclado, presets,
watchdog de silencio, reconexión, calibración de retardo y config."""
import logging
import threading
import time

import numpy as np

from . import config, net, outputs, scene, theme, win32
from .audio import Audio
from .engine import BLOCK, Engine
from .outputs import JOIN, LOGO, CONTENT, MAX_OUTPUTS, compose_output, make_output, remote_output
from .scene import LOOKS, Cfg, Scene

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
RESPONSE = {"Normal": dict(min_gap=250, flash_limit_hz=6, decay=250, vmin=8, sens=1.5),
            "Muy reactivo": dict(min_gap=140, flash_limit_hz=6, decay=120, vmin=0, sens=1.8)}
# acción -> teclas (nombres de win32.vk_code). Editable en config.json ("keys"); sin editor en la UI
KEYS = {**{str(i): [str(i), f"NUMPAD{i}"] for i in range(1, 8)}, **{c: [c] for c in "QWERTYUZ"},
        "blackout": ["SPACE"], "bump": ["F"], "auto": ["F1"], "pulso": ["F2"], "tranquilo": ["F3"],
        "manual": ["F4"], "tap": ["0", "NUMPAD0"], "sens+": ["OEM_PLUS", "ADD"],
        "sens-": ["OEM_MINUS", "SUBTRACT"]}
GLOBAL_WARN = "Las teclas también llegarán a rekordbox si está al frente"
LOCAL_NOTE = "Solo con LightHouse al frente (cualquier ventana suya)"
PHOTO_WARN = "Rojo saturado a pantalla completa > 3 Hz puede provocar crisis en personas fotosensibles"
# blanco por temperatura (aprox. de cuerpo negro), interpolado
KELVIN = np.array([[2000, 255, 137, 18], [3000, 255, 180, 107], [4000, 255, 209, 163],
                   [5000, 255, 228, 206], [6500, 255, 249, 253], [8000, 227, 233, 255], [10000, 204, 219, 255]])
PALETTE = ["#ff2a55", "#ff9f1c", "#2ec4ff", "#9b5cff"]
MODES = ("auto", "pulso", "tranquilo", "manual")
COLOR_MODES = ["Blanco", "Temperatura", "Paleta (cambia en cada flash)"]
CALIB_TEXT = ("Pon un track con kick claro. Graba con el celular en cámara lenta (240 fps) bocina + pantallas. "
              "Cuenta cuadros entre el golpe audible y el destello: 1 cuadro ≈ 4 ms. "
              "Ajusta el offset global y el retardo de cada salida hasta alinear.")
CALIB_WHERE = ("Offset global: pestaña Show → Luz. Retardo de cada salida: pestaña Salidas. "
               "Mientras calibras: look 1 en blanco, piso 0, decay 50 ms y modo Pulso.")
MIC_HINT = ("Revisa Configuración → Privacidad → Micrófono → "
            "Permitir que las aplicaciones de escritorio accedan")
RETRY_S, NO_SIGNAL_S, CLIP_S = 3.0, 3.0, 0.5
METER_W, SWATCH_W, SLIDER_W = 320, 110, 200  # medidas en px lógicos (pasan por px())
LABEL_W = 17  # ancho (en caracteres) de las etiquetas de fila
LAST_ERROR = None  # último error no controlado; el loop lento lo muestra en el label de estado


def report(exc_type, exc, tb, where="excepción"):
    """Traceback al log y texto corto para el label de estado."""
    global LAST_ERROR
    log.error("%s no controlada", where, exc_info=(exc_type, exc, tb))
    LAST_ERROR = f"Error: {exc_type.__name__}: {exc}"[:80]


class App:
    def __init__(self, headless=False, scaling=None):
        """headless: raíz y ventanas retiradas, sin audio, sin hilo render, sin leer ni escribir config.json y
        sin keep_awake (self-check de la interfaz). scaling: `tk scaling` previo a los widgets (2.0 = 150 %)."""
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.headless = headless

        self.eng = Engine()
        self.lock = threading.Lock()
        self.audio = Audio(self.on_block)
        self.last_audio = self.last_feed = time.perf_counter()
        self.zeros = np.zeros(BLOCK)
        self.scene, self.cfg = Scene(), Cfg()  # el look activo no se persiste: siempre arranca en 1
        self.outputs = []                      # Output (la Salida 1 hereda la ventana Luz de F1–F4)
        self.mons = win32.monitors()
        self.calib = None                      # valores a restaurar al salir de Calibrar retardo
        self.keys = {a: list(v) for a, v in KEYS.items()}
        self.look_hex = {k: list(v[2]) for k, v in LOOKS.items() if v[2]}
        self.vk_actions, self.bump_vks, self.held = {}, (), None
        self.keys_global = False
        self.vars = {}    # llave -> (var, k, fn, lo, hi)
        self.scales = {}  # llave -> tk.Scale
        self.checks = {}  # atributo del motor -> BooleanVar
        self.ids = {}     # widget -> id estable (fases/diseno-ui.md §5.3): tooltips (F10) y tutorial (F11)
        self.palette = list(PALETTE)
        self.geo = {"geo_control": ""}  # última geometría válida vista
        self.theme_name = theme.DEFAULT
        self.chan_idx = 0           # 0 = Mezcla, n = Canal n
        self.want = None            # dispositivo que debe estar abierto (para reintentar)
        self.retry_t = 0.0
        self.was_alive = False
        self.shown = {}             # lo último que put() mandó a cada widget

        root = self.root = tk.Tk()
        root.withdraw()  # sin parpadeo mientras se construye; se muestra al final (salvo headless)
        if scaling:
            root.tk.call("tk", "scaling", scaling)
        self.scale = root.winfo_fpixels("1i") / 96  # 1.0 al 100 %, 1.5 al 150 %
        theme.apply(root, theme.DEFAULT)  # antes de crear widgets: paint() lee el tema vigente
        theme.on_apply(self.shown.clear)  # tras cambiar de tema, put() vuelve a mandar lo que cambió de color
        root.unbind_class("TCombobox", "<MouseWheel>")  # la rueda sobre una lista no cambia su valor
        root.title("LightHouse · Control")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.report_callback_exception = lambda *a: report(*a, where="callback de Tk")
        if not headless:
            win32.keep_awake(True)  # pantalla sin dormirse; quit() y __main__ (finally) lo liberan
        P, S = self.px, self.sp

        # fila 0: barra de looks · fila 1: indicadores (siempre visibles) + pestañas · fila 2: ayuda.
        # Pestañas para que la ventana quepa en 1366×768 al 100 % y en 1920×1080 al 150 % (DPI aware)
        left = ttk.Frame(root, padding=S("md"), style="Bg.TFrame")
        left.grid(row=1, column=0, sticky="n")
        self.nb = ttk.Notebook(root, takefocus=0)
        self.nb.grid(row=1, column=1, sticky="n", padx=(0, S("md")), pady=(S("md"), S("md")))
        tab = {}
        for name in ("Show", "Audio", "Salidas"):
            t = ttk.Frame(self.nb, padding=S("sm"), style="Bg.TFrame")
            self.nb.add(t, text=f"  {name}  ")
            tab[name] = [ttk.Frame(t, padding=(S("sm"), 0), style="Bg.TFrame") for _ in range(2)]
            for i, c in enumerate(tab[name]):
                c.grid(row=0, column=i, sticky="n")
        show, aud, outs = tab["Show"], tab["Audio"], tab["Salidas"]

        def box(title, parent):
            fr = ttk.LabelFrame(parent, text=title, padding=S("md"))
            fr.pack(fill="x", pady=S("sm"))
            return fr

        # --- siempre visibles: lecturas, fuente de audio (estado, SIN SEÑAL, SATURA), modo y blackout
        fr = box("Lecturas", left)
        self.mw = P(METER_W)                                          # ancho del medidor; ys = alturas de sus barras
        self.my = tuple(P(v) for v in (4, 24, 32, 52, 28, 56))
        self.meter = tk.Canvas(fr, width=self.mw, height=self.my[5], highlightthickness=0)
        self.meter.pack()
        theme.paint(self.meter, bg="trough")
        self.bar_l = self.meter.create_rectangle(0, self.my[0], 0, self.my[1], width=0)
        self.bar_o = self.meter.create_rectangle(0, self.my[2], 0, self.my[3], width=0)
        self.line = self.meter.create_line(0, self.my[4], 0, self.my[5], width=2)
        for item, token in ((self.bar_l, "meter_level"), (self.bar_o, "meter_hit"), (self.line, "meter_threshold")):
            theme.paint(self.meter, item, fill=token)
        self.reg(self.meter, "vivo.medidor")
        ttk.Label(fr, text="gris: nivel de banda · blanco: subida (golpe) · rojo: umbral",
                  style="Muted.TLabel").pack()
        row = ttk.Frame(fr); row.pack(fill="x")
        self.dot = tk.Canvas(row, width=P(26), height=P(26), highlightthickness=0)
        self.dot.pack(side="left")
        theme.paint(self.dot, bg="surface")
        self.dot_id = self.dot.create_oval(P(3), P(3), P(23), P(23), width=0)
        theme.paint(self.dot, self.dot_id, fill="beat_off")  # slow() lo pone en beat_on con cada golpe
        self.reg(self.dot, "vivo.punto")
        self.bpm = self.reg(ttk.Label(row, text="-- BPM", style="Big.TLabel"), "vivo.bpm")
        self.bpm.pack(side="left", padx=S("md"))
        self.state = self.reg(ttk.Label(row, text="", style="State.TLabel"), "vivo.estado")
        self.state.pack(side="right")
        self.look_lbl = self.reg(ttk.Label(fr, text="", style="Big.TLabel"), "vivo.look")
        self.look_lbl.pack(anchor="w")

        fr = box("Fuente de audio", left)
        self.dev = self.reg(ttk.Combobox(fr, state="readonly", width=44, takefocus=0), "audio.dispositivo")
        self.dev.pack(fill="x")
        self.dev.bind("<<ComboboxSelected>>", lambda e: self.pick_device())
        row = ttk.Frame(fr); row.pack(fill="x", pady=(S("sm"), 0))
        ttk.Label(row, text="Canal").pack(side="left")
        self.chan = self.reg(ttk.Combobox(row, state="readonly", values=["Mezcla"], width=9, takefocus=0),
                             "audio.canal")
        self.chan.current(0)
        self.chan.pack(side="left", padx=S("md"))
        self.chan.bind("<<ComboboxSelected>>", lambda e: self.pick_channel())
        self.no_sig = self.chip(row, "vivo.sin_senal", "danger_text")
        self.clip = self.chip(row, "vivo.satura", "warn")
        row = ttk.Frame(fr); row.pack(fill="x", pady=(S("sm"), 0))
        self.reg(ttk.Button(row, text="Reconectar", command=self.reconnect, takefocus=0),
                 "audio.reconectar").pack(side="left")
        self.status = self.reg(ttk.Label(row, text="", wraplength=P(250)), "audio.estado")
        self.status.pack(side="left", padx=S("md"))
        self.low_prio = tk.BooleanVar(value=True)
        self.low_prio.trace_add("write", lambda *_: win32.set_low_priority(self.low_prio.get()))
        self.reg(ttk.Checkbutton(fr, text="Prioridad baja (laptop DJ)", variable=self.low_prio, takefocus=0),
                 "audio.prioridad").pack(anchor="w", pady=(S("sm"), 0))

        fr = box("Ganancia", aud[0])
        self.agc = tk.BooleanVar(value=self.eng.agc)
        self.checks["agc"] = self.agc
        row = ttk.Frame(fr); row.pack(fill="x")
        self.reg(ttk.Radiobutton(row, text="Automática (AGC)", value=True, variable=self.agc, takefocus=0),
                 "nivel.auto").pack(side="left")
        self.reg(ttk.Radiobutton(row, text="Fija (la perilla manda)", value=False, variable=self.agc,
                                 takefocus=0), "nivel.fijo").pack(side="left", padx=S("md"))
        self.slider(fr, "nivel.ref", "Referencia (dBFS)", "ref_db", -40, 0)
        self.agc.trace_add("write", lambda *_: self.set_agc())
        self.set_agc()

        fr = box("Modo", left)
        self.mode = tk.StringVar(value=self.eng.mode)
        self.mode.trace_add("write", lambda *_: setattr(self.eng, "mode", self.mode.get()))
        for i, m in enumerate(MODES, 1):
            self.reg(ttk.Radiobutton(fr, text=f"F{i} {m.capitalize()}", value=m, variable=self.mode,
                                     takefocus=0), f"modo.{m}").pack(side="left")
        self.bo = tk.BooleanVar(value=False)
        self.bo_btn = self.reg(tk.Checkbutton(
            fr, text="Blackout", variable=self.bo, indicatoron=False, takefocus=0, padx=S("md"), bd=1,
            highlightthickness=S("xs"), width=10, command=lambda: setattr(self.scene, "blackout", self.bo.get())),
            "blackout")
        self.bo_btn.pack(side="right")
        self.bo.trace_add("write", lambda *_: self.style_blackout())
        self.style_blackout()

        fr = box("Teclado", show[0])
        self.global_keys = tk.BooleanVar(value=False)
        self.reg(ttk.Checkbutton(fr, text="Teclas globales", variable=self.global_keys, takefocus=0),
                 "teclas.globales").pack(anchor="w")
        self.keys_note = ttk.Label(fr, text=LOCAL_NOTE, style="Muted.TLabel", wraplength=P(330))
        self.keys_note.pack(anchor="w")
        self.global_keys.trace_add("write", lambda *_: self.set_global_keys())

        fr = box("Filtro (qué escucha el detector de golpe)", aud[0])
        self.preset = self.reg(ttk.Combobox(fr, state="readonly", values=list(FILTERS), takefocus=0),
                               "filtro.preset")
        self.preset.set("Kick (120 Hz)")
        self.preset.pack(fill="x")
        self.preset.bind("<<ComboboxSelected>>", lambda e: self.pick_filter())
        self.band = self.slider(fr, "filtro.corte", "Corte (Hz)", "band", 40, 250, fn=self.band_from_slider)

        fr = box("Golpe", aud[0])
        self.slider(fr, "golpe.sens", "Sensibilidad (×)", "sens", 1.0, 3.0, res=0.1)
        self.slider(fr, "golpe.pausa", "Refractario (ms)", "min_gap", 120, 500, k=0.001)
        self.slider(fr, "golpe.compuerta", "Compuerta (dB)", "gate_db", -60, -30)
        self.check(fr, "golpe.fuerza", "Intensidad por golpe", "by_strength")

        fr = box("Tempo", aud[1])
        row = ttk.Frame(fr); row.pack(fill="x")
        self.sync = tk.StringVar(value=self.eng.sync)
        self.sync.trace_add("write", lambda *_: setattr(self.eng, "sync", self.sync.get()))
        self.reg(ttk.Radiobutton(row, text="Cada kick", value="kick", variable=self.sync, takefocus=0),
                 "tempo.kick").pack(side="left")
        self.reg(ttk.Radiobutton(row, text="Al tempo (sigue sin kick)", value="tempo", variable=self.sync,
                                 takefocus=0), "tempo.ritmo").pack(side="left", padx=S("md"))
        row = ttk.Frame(fr); row.pack(fill="x", pady=S("sm"))
        ttk.Label(row, text="BPM", width=LABEL_W).pack(side="left")
        self.src = self.reg(ttk.Combobox(row, state="readonly", values=["Detectado", "Manual / Tap"], width=13,
                                         takefocus=0), "tempo.fuente")
        self.src.set("Detectado")
        self.src.pack(side="left")
        self.src.bind("<<ComboboxSelected>>", lambda e: setattr(
            self.eng, "bpm_src", "manual" if self.src.get().startswith("Manual") else "auto"))
        self.reg(ttk.Button(row, text="Tap [0]", command=self.tap, takefocus=0, width=8),
                 "tempo.tap").pack(side="left", padx=S("md"))
        self.slider(fr, "tempo.bpm_manual", "BPM manual", "bpm_manual", 60, 200)
        row = ttk.Frame(fr); row.pack(fill="x", pady=(S("sm"), 0))
        ttk.Label(row, text="Flash cada", width=LABEL_W).pack(side="left")
        div = self.div = self.reg(ttk.Combobox(row, state="readonly", values=["1/1", "1/2", "1/4"], width=5,
                                               takefocus=0), "tempo.divisor")
        div.set("1/1")
        div.pack(side="left")
        div.bind("<<ComboboxSelected>>", lambda e: setattr(self.eng, "divisor", int(div.get()[2:])))

        fr = box("Luz", show[0])
        self.slider(fr, "luz.decay", "Decay (ms)", "decay", 50, 1000, k=0.001)
        self.slider(fr, "luz.master", "Master (%)", "vmax", 0, 100, k=0.01)
        self.slider(fr, "luz.piso", "Piso pulso (%)", "vmin", 0, 50, k=0.01)
        self.slider(fr, "luz.gamma", "Curva (gamma)", "gamma", 0.5, 3.0, res=0.1)
        self.slider(fr, "luz.manual", "Manual (%)", "manual", 0, 100, k=0.01)
        self.presets(fr, "luz.sinc_preset", OFFSETS)
        self.slider(fr, "luz.offset", "Offset (ms)", "offset", -150, 300, k=0.001, res=5)
        self.lead = ttk.Label(fr, text="", style="Muted.TLabel")
        self.lead.pack(anchor="w")

        fr = box("Respuesta", show[1])
        self.resp = self.presets(fr, "resp.preset", RESPONSE)
        self.check(fr, "resp.limite", "Limitar destellos", "flash_limit")
        self.slider(fr, "resp.limite_hz", "Máx. destellos/s", "flash_limit_hz", 3, 10)
        ttk.Label(fr, text=PHOTO_WARN, style="Warn.TLabel", wraplength=P(330)).pack(anchor="w")

        fr = box("Estrobos (Q–Y)", show[1])
        self.slider(fr, "estrobo.cierre", "Cierre del golpe", "cierre", 0.2, 0.9, res=0.05)
        self.slider(fr, "estrobo.min", "Mínimo (ms)", "strobe_min_ms", 20, 120)

        fr = box("Tranquilo", aud[1])
        self.presets(fr, "calma.preset", CALM)
        self.slider(fr, "calma.espera", "Entrar tras (s)", "calm_after", 2, 15)
        self.slider(fr, "calma.suavidad", "Suavizado (s)", "calm_smooth", 1, 3, res=0.1)
        self.slider(fr, "calma.base", "Nivel base (%)", "calm_base", 0, 60, k=0.01)
        self.slider(fr, "calma.respira", "Profundidad (%)", "calm_depth", 0, 60, k=0.01)

        fr = box("Color (opcional)", show[1])
        self.color_mode = self.reg(ttk.Combobox(fr, state="readonly", takefocus=0, values=COLOR_MODES),
                                   "color.modo")
        self.color_mode.set("Blanco")
        self.color_mode.pack(fill="x")
        self.kelvin = self.slider(fr, "color.kelvin", "Temperatura (K)", None, 2000, 10000, res=100, init=4000,
                                  key="kelvin")
        row = ttk.Frame(fr); row.pack(fill="x", pady=(S("sm"), 0))
        ttk.Label(row, text="Paleta", width=LABEL_W).pack(side="left")
        self.swatch = tk.Canvas(row, width=P(SWATCH_W), height=P(22), highlightthickness=0)
        self.swatch.pack(side="left")
        theme.paint(self.swatch, bg="surface")
        self.reg(self.swatch, "color.paleta")
        self.reg(ttk.Button(row, text="+", width=3, command=self.add_color, takefocus=0),
                 "color.mas").pack(side="left", padx=S("xs"))
        self.reg(ttk.Button(row, text="−", width=3, command=self.pop_color, takefocus=0),
                 "color.menos").pack(side="left")
        self.draw_palette()

        # --- pestaña Salidas: lista + campos de la seleccionada (se editan en vivo)
        fr = box("Salidas", outs[0])
        self.out_list = self.reg(tk.Listbox(fr, height=MAX_OUTPUTS, width=36, exportselection=False,
                                            activestyle="none", takefocus=0, bd=0, highlightthickness=1),
                                 "salidas.lista")
        theme.paint(self.out_list, bg="surface_alt", fg="fg", selectbackground="accent",
                    selectforeground="accent_fg", highlightbackground="border_strong", highlightcolor="accent",
                    font="font.body")
        self.out_list.pack(fill="x")
        self.out_list.bind("<<ListboxSelect>>", lambda e: self.show_output())
        row = ttk.Frame(fr); row.pack(fill="x", pady=(S("sm"), 0))
        self.out_add = self.reg(ttk.Button(row, text="Agregar", command=self.add_output, takefocus=0),
                                "salidas.agregar")
        self.out_add.pack(side="left")
        self.out_del = self.reg(ttk.Button(row, text="Quitar", command=self.del_output, takefocus=0),
                                "salidas.quitar")
        self.out_del.pack(side="left", padx=S("md"))
        self.out_tv = self.reg(ttk.Button(row, text="Agregar TV remota", command=lambda: self.add_output(True),
                                          takefocus=0), "salidas.tv")
        self.out_tv.pack(side="left")
        row = ttk.Frame(fr); row.pack(fill="x", pady=(S("sm"), 0))
        self.reg(ttk.Button(row, text="Identificar", command=self.identify, takefocus=0),
                 "salidas.identificar").pack(side="left")
        self.reg(ttk.Button(row, text="Calibrar retardo", command=self.calibrate, takefocus=0),
                 "salidas.calibrar").pack(side="left", padx=S("md"))
        ttk.Label(fr, style="Muted.TLabel", wraplength=P(300), text=(
            "En la salida: doble clic = pantalla completa (en el monitor donde está) / ventana; Esc = ventana. "
            "Fuera del look 1 (o en \"siempre\") la salida se une al look y oculta el logo.")).pack(
            anchor="w", pady=(S("md"), 0))
        self.net_lbl = self.reg(ttk.Label(fr, text="", style="Ok.TLabel", wraplength=P(300)),
                                "vivo.red")  # estado de las salidas remotas
        self.net_lbl.pack(anchor="w", pady=(S("md"), 0))

        fr = box("Salida seleccionada", outs[1])
        self.loading = False  # True mientras show_output() carga los campos: no escribir de vuelta

        def field(wid, label, make, parent=None, **pack):
            """Fila 'etiqueta + widget'; registra el widget con su id y lo devuelve."""
            r = ttk.Frame(parent or fr); r.pack(fill="x", pady=S("xs"))
            ttk.Label(r, text=label, width=LABEL_W).pack(side="left")
            w = self.reg(make(r), wid)
            w.pack(side="left", **pack)
            return w

        self.typing = False  # foco en un campo de texto: las teclas (GetAsyncKeyState) no disparan looks
        self.o_name = tk.StringVar()
        ent = field("sal.nombre", "Nombre", lambda r: ttk.Entry(r, textvariable=self.o_name, width=26),
                    fill="x", expand=True)
        self.text_entry(ent)
        self.o_name.trace_add("write", lambda *_: self.edit_output("name", self.o_name.get()))
        slot = ttk.Frame(fr)  # monitor y pantalla completa (local) | destino y puerto (remota)
        slot.pack(fill="x")
        self.loc_fr, self.rem_fr = ttk.Frame(slot), ttk.Frame(slot)
        self.o_dest = field("sal.destino", "Destino", lambda r: ttk.Combobox(r, values=[net.AUTO], width=26),
                            self.rem_fr, fill="x", expand=True)
        self.text_entry(self.o_dest, self.edit_remote)
        self.o_dest.bind("<<ComboboxSelected>>", lambda e: self.edit_remote())
        self.o_port = tk.StringVar()
        ent = field("sal.puerto", "Puerto", lambda r: ttk.Entry(r, textvariable=self.o_port, width=8), self.rem_fr)
        self.text_entry(ent, self.edit_remote)
        self.o_mon = field("sal.monitor", "Monitor", lambda r: ttk.Combobox(
            r, state="readonly", width=30, takefocus=0, postcommand=self.list_monitors), self.loc_fr,
            fill="x", expand=True)
        self.o_mon.bind("<<ComboboxSelected>>", lambda e: self.pick_monitor())
        self.o_full = field("sal.completa", "", lambda r: ttk.Button(
            r, text="Pantalla completa", takefocus=0, command=lambda: self.sel().set_full(not self.sel().full)),
            self.loc_fr, fill="x", expand=True)
        self.o_master = self.out_slider(fr, "sal.master", "Master (%)", "master", 0, 100)
        self.o_delay = self.out_slider(fr, "sal.retardo", "Retardo extra (ms)", "delay_ms", 0, 200)
        self.o_content = field("sal.contenido", "Contenido", lambda r: ttk.Combobox(
            r, state="readonly", values=CONTENT, width=12, takefocus=0))
        self.o_content.bind("<<ComboboxSelected>>", lambda e: self.edit_output("content", self.o_content.get()))
        logo_slot = ttk.Frame(fr)
        logo_slot.pack(fill="x")
        self.o_logo = tk.StringVar()
        ent = field("sal.logo", "Logo (PNG)", lambda r: ttk.Entry(r, textvariable=self.o_logo, width=22),
                    logo_slot, fill="x", expand=True)
        r = self.logo_row = ent.master
        self.text_entry(ent, lambda: self.set_logo(self.o_logo.get()))
        self.reg(ttk.Button(r, text="…", width=3, command=self.browse_logo, takefocus=0),
                 "sal.logo_buscar").pack(side="left", padx=(S("sm"), 0))
        self.o_join = field("sal.unirse", "Unirse a looks", lambda r: ttk.Combobox(
            r, state="readonly", values=JOIN, width=12, takefocus=0))
        self.o_join.bind("<<ComboboxSelected>>", lambda e: self.edit_output("join", self.o_join.get()))
        self.out_warn = self.reg(ttk.Label(left, text="", style="BgWarn.TLabel", wraplength=P(330)),
                                 "vivo.avisos")  # monitor ausente, logo
        self.out_warn.pack(anchor="w", padx=S("sm"))

        # --- looks (latch): también con el mouse; las teclas se leen en fast() (poll_keys)
        bar = ttk.Frame(root, padding=(S("lg"), S("md"), S("lg"), 0), style="Bg.TFrame")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.look_var = tk.StringVar(value=self.scene.look)
        self.look_btns, self.look_sw = {}, {}
        for i, lid in enumerate(LOOKS):
            bar.columnconfigure(i, weight=1)
            sw = self.look_sw[lid] = tk.Canvas(bar, height=P(8), width=P(40), highlightthickness=0)
            theme.paint(sw, bg="surface_alt")
            sw.grid(row=0, column=i, sticky="ew", padx=1)
            self.look_btns[lid] = self.reg(tk.Radiobutton(
                bar, value=lid, variable=self.look_var, indicatoron=False, takefocus=0, bd=1,
                highlightthickness=0, command=lambda lid=lid: self.select_look(lid)), f"look.{lid}")
            self.look_btns[lid].grid(row=1, column=i, sticky="ew", padx=1)
        self.look_var.trace_add("write", lambda *_: self.style_looks())
        self.style_looks()

        ttk.Label(root, style="Legend.TLabel", padding=(S("md"), 0, S("md"), S("md")), text=(
            "1–7 · Q W E R T Y U · Z: looks (quedan hasta elegir otro) · Espacio: blackout · F (mantener): bump · "
            "F1–F4: modos · 0: tap · + / −: sensibilidad · Salidas: doble clic = pantalla completa, Esc = ventana")
                  ).grid(row=2, column=0, columnspan=2)

        # config: los defaults son los valores iniciales de arriba (Engine + UI); lo guardado válido los pisa
        defaults = self.snapshot()
        defaults["outputs"] = [outputs.default_output(1, self.mons)]  # plantilla de cada salida guardada
        cfg = defaults if headless else config.load(defaults)  # headless: nunca lee config.json
        self.apply(cfg)  # aplica también la prioridad (trace de low_prio) y crea las salidas
        self.snap = self.saved = self.snapshot()
        self.dirty_t = None
        self.fast_cmd = root.register(self.fast)
        self.wake, self.running = threading.Event(), not headless
        if headless:
            for o in self.outputs:
                o.win.withdraw()
            return
        threading.Thread(target=self.waker, name="render", daemon=True).start()
        self.refresh(cfg["device"] or None)
        self.open()
        root.deiconify()
        root.update()  # mapea las ventanas ya; luego Control queda por encima de la Salida 1 en ventana
        root.lift()
        self.slow()
        self.autosave()

    # --- widgets
    # --- apariencia y registro
    def px(self, n):
        """px lógicos -> físicos con la escala real de la pantalla."""
        return theme.px(n, self.scale)

    def sp(self, name):
        """Espaciado del tema (space.<name>) en px físicos."""
        return self.px(theme.tok(f"space.{name}"))

    def reg(self, widget, wid):
        """Registra un control con su id estable (fases/diseno-ui.md §5.4) y lo devuelve."""
        self.ids[widget] = wid
        return widget

    def chip(self, parent, wid, color):
        """Aviso de texto de color sobre una tarjeta (SIN SEÑAL, SATURA): lo vacío no ocupa lugar visible."""
        lb = self.reg(self.tk.Label(parent, text="", bd=0), wid)
        theme.paint(lb, bg="surface", fg=color, font="font.title")
        lb.pack(side="left", padx=self.sp("sm"))
        return lb

    def style_scale(self, sc):
        theme.paint(sc, bg="surface", fg="fg", troughcolor="trough", activebackground="accent",
                    highlightbackground="surface", highlightcolor="focus", font="font.small")
        sc.configure(bd=1, highlightthickness=0, sliderrelief="raised", relief="flat")

    def style_looks(self):
        """Botones de look: el activo en acento con negrita (el hover es el estado active nativo de Tk)."""
        cur = self.look_var.get()
        for lid, b in self.look_btns.items():
            on = lid == cur
            theme.paint(b, bg="accent" if on else "surface_alt", fg="accent_fg" if on else "fg",
                        activebackground="accent" if on else "hover",
                        activeforeground="accent_fg" if on else "fg", selectcolor="accent", font="font.look")

    def style_blackout(self):
        """Blackout: borde danger y texto de alarma; activo = relleno danger, texto BLACKOUT ●."""
        on = self.bo.get()
        self.bo_btn.configure(text="BLACKOUT ●" if on else "Blackout")
        theme.paint(self.bo_btn, bg="danger" if on else "surface_alt", fg="danger_fg" if on else "danger_text",
                    activebackground="danger" if on else "hover",
                    activeforeground="danger_fg" if on else "danger_text", selectcolor="danger",
                    highlightbackground="danger", highlightcolor="focus", font="font.title")

    # --- widgets
    def slider(self, fr, wid, label, attr, lo, hi, k=1.0, res=1, fn=None, init=None, key=None):
        tk = self.tk
        fn = fn or (lambda val: attr and setattr(self.eng, attr, val))
        var = tk.DoubleVar(value=round(getattr(self.eng, attr) / k, 3) if init is None else init)
        row = self.ttk.Frame(fr); row.pack(fill="x")
        self.ttk.Label(row, text=label, width=LABEL_W).pack(side="left", anchor="s", pady=(0, self.sp("sm")))
        sc = self.reg(tk.Scale(row, from_=lo, to=hi, resolution=res, orient="horizontal", variable=var,
                               length=self.px(SLIDER_W), takefocus=0, command=lambda v: fn(float(v) * k)), wid)
        self.style_scale(sc)
        sc.pack(side="left", fill="x", expand=True)
        self.vars[key or attr or label] = (var, k, fn, lo, hi)
        self.scales[key or attr or label] = sc
        return var

    def check(self, fr, wid, label, attr):
        var = self.tk.BooleanVar(value=getattr(self.eng, attr))
        self.reg(self.ttk.Checkbutton(fr, text=label, variable=var, takefocus=0,
                                      command=lambda: setattr(self.eng, attr, var.get())),
                 wid).pack(anchor="w", pady=(self.sp("sm"), 0))
        self.checks[attr] = var

    def presets(self, fr, wid, table):
        """Combo que mueve varios sliders a la vez; luego el usuario ajusta a mano."""
        cb = self.reg(self.ttk.Combobox(fr, state="readonly", values=list(table), takefocus=0), wid)
        cb.set(next(iter(table)))
        cb.pack(fill="x", pady=(self.sp("sm"), self.sp("xs")))

        def apply(_):
            for attr, val in table[cb.get()].items():
                var, k = self.vars[attr][:2]
                var.set(val)
                setattr(self.eng, attr, val * k)
        cb.bind("<<ComboboxSelected>>", apply)
        return cb

    def nudge(self, key, d):
        """Mueve un slider (y su perilla) d unidades de la GUI, dentro de su rango."""
        var, k, fn, lo, hi = self.vars[key]
        v = round(min(max(var.get() + d, lo), hi), 3)
        var.set(v)
        fn(v * k)

    def set_global_keys(self):
        self.keys_global = self.global_keys.get()
        self.keys_note.config(text=GLOBAL_WARN if self.keys_global else LOCAL_NOTE,
                              style="Warn.TLabel" if self.keys_global else "Muted.TLabel")

    def set_keys(self, m):
        """m = {acción: [nombres de tecla]} (de config.json); lo inválido vuelve al default."""
        self.vk_actions = {}
        for act, names in m.items():
            vks = [win32.vk_code(n) for n in names]
            if not vks or None in vks:
                log.warning("config: teclas %r=%r no válidas; se usa el default", act, names)
                names, vks = KEYS[act], [win32.vk_code(n) for n in KEYS[act]]
            self.keys[act] = list(names)
            for vk in vks:
                self.vk_actions.setdefault(vk, []).append(act)
        self.bump_vks = tuple(vk for vk, acts in self.vk_actions.items() if "bump" in acts)
        for lid, b in self.look_btns.items():
            b.config(text=f"{self.keys[lid][0]}\n{LOOKS[lid][0]}")

    def set_colors(self, m):
        """m = {look: ['#RRGGBB', ...]} (de config.json); un look inválido vuelve a sus colores default."""
        colors = scene.default_colors()
        for lid, hexes in m.items():
            try:
                rgbs = [scene.rgb(h) for h in hexes]
                if LOOKS[lid][1] != "rainbow" and len(rgbs) != len(LOOKS[lid][2]):
                    raise ValueError(hexes)
            except ValueError:
                log.warning("config: colores de %r=%r no válidos; se usa el default", lid, hexes)
                hexes, rgbs = list(LOOKS[lid][2]), colors[lid]
            self.look_hex[lid], colors[lid] = list(hexes), rgbs
        self.cfg.colors = colors
        for lid, sw in self.look_sw.items():  # muestra: cómo se ve cada look
            kind, cols = LOOKS[lid][1], self.look_hex.get(lid, [])
            white, black = ("#%02x%02x%02x" % c for c in (scene.WHITE, scene.BLACK))
            segs = ([white] if kind == "base" else [black] if kind == "black" else
                    [black, cols[0]] if kind == "split" else cols)
            sw.bind("<Configure>", lambda e, sw=sw, segs=segs: self.draw_swatch(sw, segs))
            self.draw_swatch(sw, segs)

    def draw_swatch(self, sw, segs):
        sw.delete("all")  # los colores de la muestra son datos del show: no pasan por theme.paint
        w, h = sw.winfo_width(), self.px(9)
        for i, c in enumerate(segs):
            sw.create_rectangle(w * i / len(segs), 0, w * (i + 1) / len(segs) + 1, h, fill=c, width=0)

    def select_look(self, lid):
        self.scene.select(lid, self.eng.sample())
        self.look_var.set(lid)

    def key_action(self, act):
        if act in LOOKS:
            self.select_look(act)
        elif act in MODES:
            self.mode.set(act)
        elif act == "blackout":
            self.bo.set(not self.bo.get())
            self.scene.blackout = self.bo.get()
        elif act == "tap":
            self.tap()
        elif act in ("sens+", "sens-"):
            self.nudge("sens", 0.1 if act == "sens+" else -0.1)

    def poll_keys(self):
        """Teclas por GetAsyncKeyState: llegan aunque el foco de Tk esté en otra ventana de la app.
        Acción al presionar (flanco); el bump, mientras está presionada. Sin "Teclas globales",
        solo con un proceso LightHouse al frente; nunca mientras se escribe en un campo de texto."""
        if self.typing or not (self.keys_global or win32.app_in_foreground()):
            self.held, self.scene.bump = None, False
            return
        down = {vk for vk in self.vk_actions if win32.key_down(vk)}
        if self.held is not None:  # None: recién recuperado el permiso, solo se toma referencia
            for vk in down - self.held:
                for act in self.vk_actions[vk]:
                    self.key_action(act)
        self.held = down
        self.scene.bump = any(vk in down for vk in self.bump_vks)

    def set_agc(self):
        """AGC o ganancia fija; la referencia solo se mueve en Fija."""
        on = self.agc.get()
        self.eng.agc = on
        sc = self.scales["ref_db"]
        sc.config(state="disabled" if on else "normal")
        theme.paint(sc, fg="fg_disabled" if on else "fg")

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
        w, h = self.px(SWATCH_W) / len(self.palette), self.px(22)
        for i, c in enumerate(self.palette):
            self.swatch.create_rectangle(i * w, 0, (i + 1) * w, h, fill=c, width=0)

    # --- salidas
    def out_slider(self, fr, wid, label, attr, lo, hi):
        """Slider de la salida seleccionada (no va a self.vars: se guarda dentro de "outputs")."""
        var = self.tk.DoubleVar(value=lo)
        row = self.ttk.Frame(fr); row.pack(fill="x")
        self.ttk.Label(row, text=label, width=LABEL_W).pack(side="left", anchor="s", pady=(0, self.sp("sm")))
        sc = self.reg(self.tk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=var,
                                    length=self.px(SLIDER_W), takefocus=0,
                                    command=lambda v: self.edit_output(attr, float(v))), wid)
        self.style_scale(sc)
        sc.pack(side="left", fill="x", expand=True)
        return var

    def text_entry(self, ent, done=None):
        """Campo de texto: mientras tiene el foco las teclas no disparan looks; Enter o salir lo aplica."""
        def leave(_=None):
            self.typing = False
            if done:
                done()
        ent.bind("<FocusIn>", lambda e: setattr(self, "typing", True))
        ent.bind("<FocusOut>", leave)
        ent.bind("<Return>", lambda e: self.root.focus_set())  # suelta el foco -> FocusOut

    def sel(self):
        s = self.out_list.curselection()
        return self.outputs[min(s[0] if s else 0, len(self.outputs) - 1)]

    @staticmethod
    def out_label(n, o):
        return f"{n} · {o.name} · " + ("remota" if o.remote else f"pantalla completa · {o.mon.device}" if o.full else "ventana")

    def set_outputs(self, ds):
        """Crea las salidas desde la config (1..4); cada campo inválido cae a su default."""
        for o in self.outputs:
            o.destroy()
        self.mons = win32.monitors()
        self.outputs = [make_output(self, d, self.mons) for d in ds[:MAX_OUTPUTS]]
        self.outputs_changed(0)

    def outputs_changed(self, select=None):
        """Refresca la lista y los campos (tras agregar, quitar o cambiar de modo desde la salida)."""
        i = self.outputs.index(self.sel()) if select is None and self.out_list.size() else select or 0
        self.out_list.delete(0, "end")
        for n, o in enumerate(self.outputs, 1):
            self.out_list.insert("end", self.out_label(n, o))
        self.out_list.selection_set(i)
        full = "normal" if len(self.outputs) < MAX_OUTPUTS else "disabled"
        self.out_add.config(state=full)
        self.out_tv.config(state=full)
        self.out_del.config(state="normal" if len(self.outputs) > 1 else "disabled")
        self.show_output()

    def mon_label(self, m):
        return f"{m.device} · {m.w}×{m.h}" + (" · principal" if m.primary else "")

    def list_monitors(self):
        self.mons = win32.monitors()
        self.o_mon["values"] = [self.mon_label(m) for m in self.mons]

    def show_output(self):
        """Carga en los campos la salida seleccionada."""
        o, self.loading = self.sel(), True
        try:
            self.o_name.set(o.name)
            for w, on in ((self.loc_fr, not o.remote), (self.rem_fr, o.remote), (self.logo_row, not o.remote)):
                w.pack(fill="x", pady=self.sp("xs") if w is self.logo_row else 0) if on else w.pack_forget()
            if o.remote:
                self.o_dest.set(o.dest)
                self.o_port.set(str(o.port))
            else:
                self.list_monitors()
                self.o_mon.set(self.mon_label(o.mon))
                self.o_full.config(text="Ventana" if o.full else "Pantalla completa")
            self.o_master.set(o.master)
            self.o_delay.set(o.delay_ms)
            self.o_content.set(o.content)
            self.o_logo.set(o.logo)
            self.o_join.set(o.join)
        finally:
            self.loading = False

    def edit_output(self, attr, v):
        if self.loading:
            return
        o = self.sel()
        setattr(o, attr, v)
        if attr == "name":
            if not o.remote:
                o.win.title(f"LightHouse · {v}")
            i = self.outputs.index(o)
            self.out_list.delete(i)
            self.out_list.insert(i, self.out_label(i + 1, o))
            self.out_list.selection_set(i)

    def edit_remote(self):
        """Destino y puerto de la salida remota seleccionada (al salir del campo o elegir de la lista)."""
        o = self.sel()
        if self.loading or not o.remote:
            return
        try:
            port = int(self.o_port.get())
        except ValueError:
            port = 0
        o.connect(self.o_dest.get(), port)
        self.show_output()

    def pick_monitor(self):
        i = self.o_mon.current()
        if 0 <= i < len(self.mons) and not self.sel().remote:
            self.sel().set_monitor(self.mons[i])
            self.outputs_changed()

    def set_logo(self, path):
        o = self.sel()
        if not o.remote and path.strip() != o.logo:
            o.set_logo(path)

    def browse_logo(self):
        from tkinter import filedialog
        self.typing = True  # el diálogo nativo también es "LightHouse al frente": no disparar looks al escribir
        try:
            p = filedialog.askopenfilename(parent=self.root, title="Logo (PNG)",
                                           filetypes=[("PNG", "*.png"), ("Todos", "*.*")])
        finally:
            self.typing = False
        if p:
            self.o_logo.set(p)
            self.set_logo(p)

    def add_output(self, remote=False):
        if len(self.outputs) < MAX_OUTPUTS:
            self.mons = win32.monitors()
            used = {o.device for o in self.outputs if not o.remote}
            n = len(self.outputs) + 1
            self.outputs.append(make_output(self, remote_output(n) if remote else
                                            outputs.default_output(n, self.mons, used), self.mons))
            self.outputs_changed(len(self.outputs) - 1)

    def del_output(self):
        if len(self.outputs) > 1:
            o = self.sel()
            i = self.outputs.index(o)
            self.outputs.remove(o)
            o.destroy()
            self.outputs_changed(max(i - 1, 0))

    def identify(self):
        """Durante 3 s cada salida muestra en grande su número, monitor y resolución."""
        self.mons = win32.monitors()
        for n, o in enumerate(self.outputs, 1):
            o.identify(n, self.mons)

    def set_var(self, key, v):
        var, k, fn = self.vars[key][:3]
        var.set(v)
        fn(v * k)

    def calibrate(self):
        """Blanco, piso 0, decay 50 ms y modo Pulso mientras se calibra; Salir restaura lo anterior."""
        if self.calib:
            self.calib["win"].lift()
            return
        tk, ttk = self.tk, self.ttk
        self.calib = dict(look=self.scene.look, color_mode=self.color_mode.get(), mode=self.mode.get(),
                          vmin=self.vars["vmin"][0].get(), decay=self.vars["decay"][0].get())
        self.select_look("1")
        self.color_mode.set("Blanco")
        self.set_var("vmin", 0)
        self.set_var("decay", 50)
        self.mode.set("pulso")
        w = self.calib["win"] = tk.Toplevel(self.root)
        w.title("LightHouse · Calibrar retardo")
        w.protocol("WM_DELETE_WINDOW", self.calib_exit)
        theme.window(w)  # fondo y barra de título del tema
        fr = ttk.Frame(w, padding=self.sp("lg"), style="Bg.TFrame")
        fr.pack(fill="both", expand=True)
        ttk.Label(fr, text=CALIB_TEXT, wraplength=self.px(440), style="Bg.TLabel").pack(anchor="w")
        ttk.Label(fr, text=CALIB_WHERE, wraplength=self.px(440), style="BgMuted.TLabel").pack(
            anchor="w", pady=(self.sp("md"), 0))
        self.reg(ttk.Button(fr, text="Salir", command=self.calib_exit, takefocus=0),
                 "calib.salir").pack(anchor="e", pady=(self.sp("md"), 0))
        log.info("calibración de retardo: inicio")

    def calib_exit(self):
        c, self.calib = self.calib, None
        if not c:
            return
        self.select_look(c["look"])
        self.color_mode.set(c["color_mode"])
        self.set_var("vmin", c["vmin"])
        self.set_var("decay", c["decay"])
        self.mode.set(c["mode"])
        c["win"].destroy()
        log.info("calibración de retardo: fin (offset %.0f ms; retardos %s)", self.eng.offset * 1000,
                 [o.delay_ms for o in self.outputs])

    # --- config
    def snapshot(self):
        """Todo lo persistente, en unidades de la GUI. Llave = nombre en config.json."""
        s = {k: v[0].get() for k, v in self.vars.items()}
        s.update({a: v.get() for a, v in self.checks.items()})
        s.update(mode=self.mode.get(), sync=self.sync.get(), bpm_src=self.eng.bpm_src,
                 divisor=self.eng.divisor, preset=self.preset.get(), color_mode=self.color_mode.get(),
                 palette=list(self.palette), device=self.dev.get(), channel=self.chan_idx,
                 low_priority=self.low_prio.get(), response=self.resp.get(),
                 global_keys=self.global_keys.get(), keys={a: list(v) for a, v in self.keys.items()},
                 look_colors={k: list(v) for k, v in self.look_hex.items()},
                 outputs=[o.snapshot() for o in self.outputs], ui={"theme": self.theme_name})
        if self.root.winfo_viewable():
            self.geo["geo_control"] = self.root.geometry()
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
        if pick("response", RESPONSE):
            self.resp.set(c["response"])  # solo el nombre: los sliders ya traen sus valores
        self.set_theme(c["ui"]["theme"])
        self.global_keys.set(c["global_keys"])
        self.set_keys(c["keys"])
        self.set_colors(c["look_colors"])
        try:
            for col in c["palette"]:
                self.root.winfo_rgb(col)
            self.palette = list(c["palette"])
            self.draw_palette()
        except self.tk.TclError:
            log.warning("config: paleta inválida %r; se usa el default", c["palette"])
        g = outputs.GEO_RE.match(c["geo_control"])
        if g and outputs.geo_ok(c["geo_control"], self.mons):
            # solo la posición: el tamaño lo pide el contenido (cambió con las pestañas y con DPI aware)
            self.root.geometry(g[3] + g[4])
            self.geo["geo_control"] = c["geo_control"]
        elif c["geo_control"]:
            log.warning("config: geo_control=%r no es válido o cae fuera de los monitores", c["geo_control"])
        self.set_outputs(c["outputs"])

    def set_theme(self, name):
        """Aplica el tema guardado (ui.theme); uno desconocido cae al por defecto con aviso. Sin selector hasta F14."""
        if name not in theme.THEMES:
            log.warning("config: ui.theme=%r no es un tema conocido; se usa %r", name, theme.DEFAULT)
            name = theme.DEFAULT
        if name != self.theme_name:
            theme.apply(self.root, name)
        self.theme_name = name

    def save(self):
        try:
            config.save(self.snapshot())
        except Exception:
            log.exception("no se pudo guardar la config")

    def autosave(self):
        # ponytail: debounce por sondeo a 2 Hz (compara snapshots); si hiciera falta, engancharlo a cada widget
        if self.calib:  # los valores de calibración son temporales: no se guardan
            self.root.after(500, self.autosave)
            return
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
        """Render rápido (por bloque de audio, vía waker; y en cada tick lento): sondea las teclas y,
        por salida, compone su Frame (su retardo, su master, su regla de unirse) y pinta lo que cambió."""
        self.poll_keys()
        e, sc, cfg, now = self.eng, self.scene, self.cfg, time.perf_counter()
        for o in self.outputs:
            o.render(compose_output(e.sample(o.delay_ms * 0.001), sc, cfg, o.join, o.master * 0.01,
                                    o.content == LOGO), now)

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
                # el resto fraccionario se arrastra: el tiempo del motor (U respira en 8 s) no se atrasa
                self.last_feed = now if n == 100 else self.last_feed + n * BLOCK / self.eng.sr
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
        e, put, sc = self.eng, self.put, self.scene
        self.cfg = Cfg(master=e.vmax, gamma=e.gamma, base=tuple(self.base_rgbs()), colors=self.cfg.colors)
        self.fast()  # sin bloques (loopback en silencio, sin stream) también se pinta
        w, y = self.mw, self.my
        put(self.meter.coords, self.bar_l, 0, y[0], round(w * min(e.lb, 1)), y[1])
        put(self.meter.coords, self.bar_o, 0, y[2], round(w * min(e.o_disp, 1)), y[3])
        x = round(w * min(e.thresh, 1))
        put(self.meter.coords, self.line, x, y[4], x, y[5])
        put(self.dot.itemconfig, self.dot_id, fill=theme.tok("beat_on" if e.t - e.last_beat < 0.1 else "beat_off"))
        if e.sync == "tempo" and e.bpm_src == "manual":
            put(self.bpm.config, text=f"{e.bpm_manual:.0f} BPM (manual)")
        else:
            put(self.bpm.config, text=f"{e.bpm:.0f} BPM" if e.bpm and e.t - e.last_beat < 2 else "-- BPM")
        put(self.state.config, text="TECLAS EN PAUSA" if self.typing else
            "BLACKOUT" if sc.blackout else "BUMP" if sc.bump else
            e.mode.upper() if e.mode != "auto" else "AUTO · TRANQUILO" if e.calm else "AUTO · PULSO")
        put(self.look_lbl.config, text=f"Look {self.keys[sc.look][0]} · {LOOKS[sc.look][0]}")
        put(self.lead.config, text="" if e.offset >= 0 else "anticipación activa" if e.lead() else
            "anticipación inactiva (requiere Al tempo)" if e.sync != "tempo" else
            "anticipación inactiva (esperando BPM fiable)")
        put(self.no_sig.config, text="SIN SEÑAL" if alive and e.t - e.last_sound > NO_SIGNAL_S else "")
        put(self.clip.config, text="SATURA" if now - self.audio.clip_t < CLIP_S else "")
        put(self.net_lbl.config, text="\n".join(f"{o.name}: {o.status()}" for o in self.outputs if o.remote))
        put(self.out_warn.config, text="\n".join(
            w for o in self.outputs for w in (f"{o.name}: {o.warn}" if o.warn else "", o.logo_err) if w))

    def put(self, fn, *args, **kw):
        """fn(*args, **kw) solo si cambió desde la última vez: cada config/coords hace redibujar a Tk."""
        key = (fn.__self__, fn.__name__, args[:1])
        if self.shown.get(key) != (args, kw):
            self.shown[key] = (args, kw)
            fn(*args, **kw)

    def quit(self):
        if self.headless:  # sin guardar config, sin audio abierto y sin keep_awake
            self.running = False
            self.audio.terminate()
            self.root.destroy()
            return
        self.calib_exit()  # se guardan los valores de antes de calibrar
        self.save()
        self.running = False
        self.audio.terminate()
        self.wake.set()
        win32.keep_awake(False)
        self.root.destroy()
