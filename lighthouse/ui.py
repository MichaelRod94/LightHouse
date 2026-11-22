"""GUI: ventana Control (barra de looks, franja En vivo, pestañas Show / Audio / Salidas / Ayuda con tarjetas
y layout responsive completo / medio / compacto / Mini junto a rekordbox) + salidas de video, looks por
teclado, presets, watchdog de silencio, reconexión, calibración de sincronía y config."""
import logging
import math
import os
import re
import threading
import time

import numpy as np

from . import VERSION, __author__, config, intro, layout, net, outputs, scene, theme, tips, tutorial, win32
from .audio import Audio
from .engine import BLOCK, Engine
from .outputs import JOIN, LOGO, CONTENT, MAX_OUTPUTS, compose_output, make_output, remote_output
from .scene import BLACK, LOOKS, Cfg, Scene

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
        "sens-": ["OEM_MINUS", "SUBTRACT"], "mini": ["F9"]}
ACTION_NAMES = {"blackout": "Blackout", "bump": "Bump (mantener)", "auto": "Modo Auto", "pulso": "Modo Pulso",
                "tranquilo": "Modo Tranquilo", "manual": "Modo Manual", "tap": "Marcar el ritmo",
                "sens+": "Más sensibilidad", "sens-": "Menos sensibilidad", "mini": "Vista Mini / volver"}
KEY_NAMES = {"SPACE": "Espacio", "OEM_PLUS": "+", "OEM_MINUS": "−", "ADD": "Num +", "SUBTRACT": "Num −"}
# nombre corto de cada look para su botón (el largo, de scene.LOOKS, va en "Look 2 · Rojo")
LOOK_SHORT = {"1": "Blanco", "2": "Rojo", "3": "Azul", "4": "Morado", "5": "Verde", "6": "Amar.", "7": "Arco",
              "Q": "B/Rojo", "W": "B/Mor.", "E": "½ roja", "R": "½ mor.", "T": "½ verde", "Y": "½ azul",
              "U": "Resp.", "Z": "Negro"}
LOOK_NAMED_DENSE = "1234567"  # en densa solo estos llevan nombre junto a la tecla ("2 Rojo"); Q–Z, solo la tecla
GLOBAL_WARN = "Las teclas también llegarán a rekordbox si está al frente"
LOCAL_NOTE = "Solo con LightHouse al frente (cualquier ventana suya)"
KEYS_NOTE = ("Con LightHouse al frente (o con \"Teclas siempre activas\"); nunca con Ctrl o Alt presionados "
             "ni mientras escribes.")
PHOTO_WARN = "Rojo saturado a pantalla completa > 3 Hz puede provocar crisis en personas fotosensibles"
# blanco por temperatura (aprox. de cuerpo negro), interpolado
KELVIN = np.array([[2000, 255, 137, 18], [3000, 255, 180, 107], [4000, 255, 209, 163],
                   [5000, 255, 228, 206], [6500, 255, 249, 253], [8000, 227, 233, 255], [10000, 204, 219, 255]])
PALETTE = ["#ff2a55", "#ff9f1c", "#2ec4ff", "#9b5cff"]
MODES = ("auto", "pulso", "tranquilo", "manual")
MODE_LABELS = [f"F{i} {m.capitalize()}" for i, m in enumerate(MODES, 1)]  # segmentos (cómoda)
MODE_SHORT = [m.capitalize() for m in MODES]  # lista desplegable (densa, ahorra ancho)
COLOR_MODES = ["Blanco", "Temperatura", "Paleta (cambia en cada flash)"]
TABS = {"show": "Show", "audio": "Audio", "salidas": "Salidas", "ayuda": "Ayuda"}  # id -> etiqueta
VISTAS = {"auto": "Automática", "compacto": "Compacta", "mini": "Mini"}
APP_NAME = "LightHouse"  # {app} de la intro
TUTORIAL = ("preguntar", "no_preguntar", "visto")  # ui.tutorial
STATES = ("BLACKOUT", "BUMP", "AUTO · TRANQUILO", "AUTO · PULSO", "PULSO", "TRANQUILO", "MANUAL")
AUTO_PREFIX = "AUTO · "  # en densa no se muestra: el modo ya está en la lista desplegable
BPM_MANUAL = {False: " (manual)", True: " (man.)"}  # sufijo del BPM manual (cómoda / densa)
CALIB_TEXT = ("Pon un track con kick claro. Graba con el celular en cámara lenta (240 fps) bocina + pantallas. "
              "Cuenta cuadros entre el golpe audible y el destello: 1 cuadro ≈ 4 ms. Ajusta \"Adelantar / "
              "atrasar la luz\" y el \"Retraso de esta pantalla\" de cada salida hasta alinear.")
CALIB_WHERE = ("Adelantar / atrasar la luz: pestaña Show → Luz. Retraso de cada pantalla: pestaña Salidas → "
               "Salida seleccionada → Avanzado. Mientras calibras: look 1 en blanco, luz mínima 0, duración del "
               "destello 50 ms y modo Pulso.")
MIC_HINT = ("Revisa Configuración → Privacidad → Micrófono → "
            "Permitir que las aplicaciones de escritorio accedan")
NOFOCUS_NOTE = ("En la vista Mini, un clic en un look o en Blackout no le quita el teclado al programa que "
                "está al frente (rekordbox). Un clic en la línea de estado sí trae LightHouse al frente.")
KEYS_TEXTS = ("Teclas: activas", "Teclas: en otra ventana", "Teclas: siempre activas", "Teclas: en pausa")
GLASS_NOTE = "En este equipo, Glass se muestra sin transparencia."  # bajo el selector Tema (fases/diseno-ui.md §13.4)
RETRY_S, NO_SIGNAL_S, CLIP_S = 3.0, 3.0, 0.5
# medidas en px lógicos (pasan por px())
METER_W, METER_W_NARROW, METER_W_DENSE = 240, 120, 70  # cómoda (1 fila de looks / 2 filas) y densa
METER_W_MINI = 56
MINI_SIZE = (800, 80)                      # geometría mini por defecto (contenido de la tira)
SWATCH_W, SLIDER_W = 110, 190
METER_Y = (4, 24, 32, 52, 28, 56)          # medidor: barra de nivel, barra de golpe y línea de umbral (y0, y1)
METER_Y_DENSE = (2, 12, 15, 25, 14, 27)
SWATCH_H, SWATCH_H_DENSE = 8, 4            # muestra de color sobre cada botón de look
PREVIEW = (14, 20)                         # cada mitad de la vista previa
TEXT_W = 330                               # ancho de los textos que se parten en varias líneas
FRAME_EXTRA = (16, 40)                     # bordes + barra de título de Windows (aprox.)
LABEL_W = 17  # ancho (en caracteres) de las etiquetas de fila; las más largas se parten en dos líneas
POS_RE = re.compile(r"^([+-]-?\d+)([+-]-?\d+)$")  # geo_control migrado de v5: solo la posición
FOCUSABLE = {"Button", "TButton", "Checkbutton", "TCheckbutton", "Radiobutton", "TRadiobutton", "Scale",
             "TCombobox", "Listbox"}  # con "Navegar con Tab" toman el foco (los campos de texto, siempre)
# tarjeta -> llaves de config de su parte avanzada (punto • en "Avanzado" si alguna no está en su default)
ADV_KEYS = {"respuesta": ("flash_limit_hz",), "luz": ("vmin", "gamma", "manual"),
            "estrobos": ("cierre", "strobe_min_ms"), "teclado": (), "fuente": ("low_priority",),
            "ganancia": ("ref_db",), "filtro": ("band",), "golpe": ("min_gap", "gate_db", "by_strength"),
            "tempo": ("bpm_manual", "divisor"), "tranquilo": ("calm_after", "calm_smooth", "calm_base", "calm_depth"),
            "salida_sel": ()}
LAST_ERROR = None  # último error no controlado; el loop lento lo muestra en el label de estado


def report(exc_type, exc, tb, where="excepción"):
    """Traceback al log y texto corto para el label de estado."""
    global LAST_ERROR
    log.error("%s no controlada", where, exc_info=(exc_type, exc, tb))
    LAST_ERROR = f"Error: {exc_type.__name__}: {exc}"[:80]


def keys_live(fg, global_keys, typing, focused, ctrl, alt):
    """¿Disparan las teclas de show? Nunca con Ctrl o Alt presionados (Alt+F4 no cambia de modo), ni
    escribiendo en un campo, ni con el foco en un control ("Navegar con Tab"); y solo con LightHouse al
    frente, salvo "Teclas siempre activas" (globales). Pura: la prueba el self-check."""
    return not (ctrl or alt or typing or focused) and (fg or global_keys)


def keys_chip(fg, global_keys, paused):
    """Texto y token de color del aviso "Teclas" de la franja En vivo."""
    if paused:
        return "Teclas: en pausa", "warn"
    if global_keys:
        return "Teclas: siempre activas", "warn"
    return ("Teclas: activas", "ok") if fg else ("Teclas: en otra ventana", "fg_muted")


def state_text(st, dense, mini):
    """Estado del modo en la franja: en densa sin "AUTO · " (el modo ya está en su lista); en Mini no hay
    lista de Modo: va entero y en corto, tras el look ("· AUTO·PULSO")."""
    if mini:
        return "· " + st.replace(" · ", "·")
    return st.replace(AUTO_PREFIX, "") if dense else st


def key_label(name):
    """Nombre de config de una tecla -> texto para la tabla de atajos ("NUMPAD1" -> "Num 1")."""
    n = str(name).upper()
    return KEY_NAMES.get(n) or (f"Num {n[6:]}" if n.startswith("NUMPAD") else n)


def hexrgb(c):
    return "#%02x%02x%02x" % c  # colores del show (vista previa): no son tokens del tema


class App:
    def __init__(self, headless=False, scaling=None, con_intro=True):
        """headless: raíz y ventanas retiradas, sin audio, sin hilo render, sin leer ni escribir config.json y
        sin keep_awake (self-check de la interfaz). scaling: `tk scaling` previo a los widgets (2.0 = 150 %).
        con_intro=False (--sin-intro): nunca muestra la animación de entrada."""
        import tkinter as tk
        from tkinter import font as tkfont
        from tkinter import ttk
        self.tk, self.ttk, self.tkfont = tk, ttk, tkfont
        self.headless = headless

        self.eng = Engine()
        self.lock = threading.Lock()
        self.audio = Audio(self.on_block)
        self.last_audio = self.last_feed = time.perf_counter()
        self.zeros = np.zeros(BLOCK)
        self.scene, self.cfg = Scene(), Cfg()  # el look activo no se persiste: siempre arranca en 1
        self.outputs = []                      # Output (la Salida 1 hereda la ventana Luz de F1–F4)
        self.mons = win32.monitors()
        self.calib = None                      # valores a restaurar al salir de Calibrar sincronía
        self.keys = {a: list(v) for a, v in KEYS.items()}
        self.look_hex = {k: list(v[2]) for k, v in LOOKS.items() if v[2]}
        self.vk_actions, self.bump_vks, self.held = {}, (), None
        self.keys_global = False
        self.key_bump = self.bump_mouse = False  # bump por la tecla F / por el botón (se suman)
        self.vars = {}    # llave -> (var, k, fn, lo, hi)
        self.scales = {}  # llave -> tk.Scale
        self.checks = {}  # atributo del motor -> BooleanVar
        self.ids = {}     # widget -> id estable (fases/diseno-ui.md §5.3): tooltips (F10) y tutorial (F11)
        self.palette = list(PALETTE)
        self.geo = {"geo_control": ""}  # última geometría válida vista
        self.theme_name = theme.DEFAULT
        self.t_theme = 0.0          # ms del último cambio de tema (selector)
        self.ptr_in = False         # puntero dentro de Control (glass: opaca)
        self.chan_idx = 0           # 0 = Mezcla, n = Canal n
        self.want = None            # dispositivo que debe estar abierto (para reintentar)
        self.retry_t = 0.0
        self.was_alive = False
        self.shown = {}             # lo último que put() mandó a cada widget
        self.typing = False         # foco en un campo de texto: las teclas (GetAsyncKeyState) no disparan looks
        self.nav_focus = False      # "Navegar con Tab": foco en un control -> teclas en pausa
        self.loading = False        # True mientras show_output() carga los campos: no escribir de vuelta
        self.alarm = ""             # aviso de audio para la franja En vivo (error, reconectando…)
        self.preview = None         # último Frame compuesto para la Salida 1 (lo deja fast(), lo pinta slow())
        self.cards, self.adv, self.adv_open, self.adv_dirty = {}, {}, {}, {}
        self.seg_lines = {}         # variable -> [(valor, Frame del subrayado, token de fondo)]
        self.chip_vis = {}
        self.layout = self.draw = self.live_n = None  # Layout elegido, Layout dibujado y filas de la franja
        self.live_drawn = None
        self.vista = "auto"
        self.vista_prev = "auto"    # vista a la que vuelven Ampliar y F9 al salir de Mini
        self.geo_normal = None      # (geometría, maximizada) de la última ventana no mini
        self.geo_mini = ""          # ui.geo_mini
        self.topmost = self.noact = False  # siempre encima y "No quitar el teclado" aplicados ahora
        self.geo_req = ""           # última geometría pedida por fit_geometry (ver cur_geo)
        self.state_fits = True      # Mini bloque: el estado del modo solo si cabe
        self.jobs = {}
        self.sb_on = False
        self.t_layout = 0.0         # ms de la última recolocación
        self.tut_state = "preguntar"  # ui.tutorial: preguntar · no_preguntar · visto
        self.band_off = False       # "Ahora no": sin banda hasta el próximo arranque
        self.band_on = False        # la banda de primer arranque está a la vista
        self.intro = None           # F13: la animación de entrada viva (intro.Intro); mientras corre no hay banda
        self.intro_on = False

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
        P = self.px
        root.minsize(P(360), P(72))
        body_font = tkfont.Font(root=root, font=theme.tok("font.body"))
        self.label_px = body_font.measure("0") * LABEL_W  # las etiquetas de fila se parten a este ancho
        # zonas (fases/diseno-ui.md §2.1): 0 barra de looks · 1 franja En vivo · 2 pestañas · 3 tarjetas
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)
        self.build_looks()
        self.build_live()
        self.bar.lift(self.live)  # en Mini la barra de looks se empaca dentro de la franja: debe quedar encima
        self.build_band()
        self.build_tabs()
        self.build_body()
        self.build_show()
        self.build_audio()
        self.build_outputs()
        self.build_help()
        root.bind("<FocusIn>", self.on_focus_in)
        root.bind("<FocusOut>", lambda e: self.set_bump_mouse(False) if self.bump_mouse else None)
        root.bind("<Escape>", lambda e: root.focus_set())  # devuelve el foco a la ventana (teclas activas)
        root.bind("<MouseWheel>", self.on_wheel)
        root.bind("<Key>", self.skip_intro, add="+")  # cualquier tecla o clic quita la intro
        root.bind("<Button>", self.skip_intro, add="+")
        self.tip = tips.Tooltip(self)  # después de los binds de la raíz: los suyos van con add="+"
        self.tut = tutorial.Tutorial(self)
        root.bind("<Enter>", self.update_alpha, add="+")  # glass: opaca con el puntero dentro (por eventos)
        root.bind("<Leave>", self.update_alpha, add="+")

        # config: los defaults son los valores iniciales de arriba (Engine + UI); lo guardado válido los pisa
        defaults = self.defaults = self.snapshot()
        defaults["outputs"] = [outputs.default_output(1, self.mons)]  # plantilla de cada salida guardada
        cfg = defaults if headless else config.load(defaults)  # headless: nunca lee config.json
        self.apply(cfg)  # aplica también la prioridad (trace de low_prio) y crea las salidas
        self.snap = self.saved = self.snapshot()
        self.update_dots(self.snap)
        self.dirty_t = None
        self.fast_cmd = root.register(self.fast)
        self.wake, self.running = threading.Event(), not headless
        if headless:
            self.relayout(1366, 700, force=True)  # completo, 3 columnas (el self-check mide los demás)
            for o in self.outputs:
                o.win.withdraw()
            return
        geo, zoom = self.initial_geometry(cfg["geo_control"])
        self.geo["geo_control"] = geo
        if self.vista == "mini":  # se cerró en Mini: arranca en Mini, con su geometría
            self.geo_normal = (geo, zoom)
            geo, zoom = self.mini_geometry(geo), False
        root.geometry(geo)
        g = re.match(r"^(\d+)x(\d+)", geo)
        self.relayout(int(g[1]) / self.scale, int(g[2]) / self.scale, force=True)
        root.bind_class("Tk", "<Configure>", self.on_root_configure)  # solo la raíz, no sus hijos
        threading.Thread(target=self.waker, name="render", daemon=True).start()
        self.refresh(cfg["device"] or None)
        self.open()
        if con_intro and self.intro_var.get() and self.vista != "mini":  # con el show ya corriendo
            self.start_intro(int(g[1]), int(g[2]))
        root.deiconify()
        if zoom:
            root.state("zoomed")
        root.update()  # mapea las ventanas ya; luego Control queda por encima de la Salida 1 en ventana
        root.lift()
        if self.vista == "mini":
            self.mini_window(True)
        self.slow()
        self.autosave()

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

    def chip(self, parent, wid, color, font="font.title"):
        """Aviso de la franja En vivo: texto de color sobre surface_alt; vacío = oculto (chip_set)."""
        lb = self.reg(self.tk.Label(parent, text="", bd=0, padx=self.px(6), pady=self.px(1)), wid)
        theme.paint(lb, bg="surface_alt", fg=color, font=font)
        self.chip_vis[lb] = False
        return lb

    def segment(self, parent, var, value, text, wid, under, style="TFrame", command=None):
        """Segmento (pestañas, Modo): ttk.Radiobutton estilo Toolbutton con subrayado de acento al elegirlo."""
        fr = self.ttk.Frame(parent, style=style)
        rb = self.reg(self.ttk.Radiobutton(fr, text=text, value=value, variable=var, style="Seg.Toolbutton",
                                           takefocus=0, command=command), wid)
        rb.pack(fill="x")
        line = self.tk.Frame(fr, height=self.sp("xs"), bd=0, highlightthickness=0)
        line.pack(fill="x")
        fr.pack(side="left", padx=(0, 1))
        lines = self.seg_lines.setdefault(str(var), [])
        if not lines:
            var.trace_add("write", lambda *_: self.style_segments(var))
        lines.append((value, line, under))
        theme.paint(line, bg=under)
        return rb

    def style_segments(self, var):
        cur = var.get()
        for value, line, under in self.seg_lines[str(var)]:
            theme.paint(line, bg="accent" if value == cur else under)

    def style_scale(self, sc):
        theme.paint(sc, bg="surface", fg="fg", troughcolor="trough", activebackground="accent",
                    highlightbackground="surface", highlightcolor="focus", font="font.small")
        sc.configure(bd=1, highlightthickness=self.sp("xs"), sliderrelief="raised", relief="flat")

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

    def style_bump(self, on, btn=None):
        """Bump: activo (acento) mientras se mantiene, con el ratón o con la tecla F (btn: Ampliar del mini,
        mismo aspecto, nunca activo)."""
        theme.paint(btn or self.bump_btn, bg="accent" if on else "surface_alt", fg="accent_fg" if on else "fg",
                    activebackground="accent" if on else "hover", activeforeground="accent_fg" if on else "fg",
                    highlightbackground="surface", highlightcolor="focus", font="font.title")

    def style_top(self):
        """Siempre encima (interruptor del mini): encendido = fondo de acento, como el look activo."""
        on = self.mini_top.get()
        theme.paint(self.top_btn, bg="accent" if on else "surface_alt", fg="accent_fg" if on else "fg",
                    activebackground="accent" if on else "hover", activeforeground="accent_fg" if on else "fg",
                    selectcolor="accent", highlightbackground="surface", highlightcolor="focus", font="font.title")

    # --- zona A: barra de looks
    def build_looks(self):
        tk, P = self.tk, self.px
        bar = self.bar = self.ttk.Frame(self.root, style="Bg.TFrame", padding=(0, 0, 0, self.sp("xs")))
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.look_var = tk.StringVar(value=self.scene.look)
        self.look_btns, self.look_sw = {}, {}
        for lid in LOOKS:  # latch: también con el ratón; las teclas se leen en fast() (poll_keys)
            sw = self.look_sw[lid] = tk.Canvas(bar, height=P(SWATCH_H), width=P(10), highlightthickness=0, bd=0)
            theme.paint(sw, bg="surface_alt")
            b = self.look_btns[lid] = self.reg(tk.Radiobutton(
                bar, value=lid, variable=self.look_var, indicatoron=False, takefocus=0, bd=1,
                highlightthickness=self.sp("xs"), command=lambda lid=lid: self.select_look(lid)), f"look.{lid}")
            theme.paint(b, highlightbackground="bg", highlightcolor="focus")
        self.look_var.trace_add("write", lambda *_: self.style_looks())
        self.style_looks()

    def look_text(self, lid, dense, mini=False):
        k = self.keys[lid][0]
        if mini:  # 15 × 44 px: solo la tecla (el nombre del activo va en la línea de estado)
            return k
        if dense:
            return f"{k} {LOOK_SHORT[lid]}" if lid in LOOK_NAMED_DENSE else k
        return f"{k}\n{LOOK_SHORT[lid]}"

    def layout_looks(self, lay):
        """1 fila (15) o 2 (8 + 7: 1–7 Q arriba, W–Z abajo); el orden nunca cambia. Densa: botones de una
        línea con la muestra como banda fina."""
        dense, per = lay.dense, len(LOOKS) if lay.look_rows == 1 else 8
        bw = self.px(theme.tok("size.look_w_dense" if dense else "size.look_w"))
        bh = self.px(theme.tok("size.look_h_dense" if dense else "size.look_h"))
        for i, lid in enumerate(LOOKS):
            r, c = divmod(i, per)
            sw = self.look_sw[lid]
            sw.configure(height=self.px(SWATCH_H_DENSE if dense else SWATCH_H))
            sw.grid(row=2 * r, column=c, sticky="ew", padx=self.sp("xs"))
            self.look_btns[lid].configure(text=self.look_text(lid, dense, lay.mode == "mini"))
            self.look_btns[lid].grid(row=2 * r + 1, column=c, sticky="nsew")
        for c in range(len(LOOKS)):
            on = c < per
            self.bar.columnconfigure(c, weight=1 if on else 0, minsize=bw if on else 0,
                                     uniform="look" if on and not dense else "")
        self.bar.rowconfigure(1, minsize=bh)
        self.bar.rowconfigure(3, minsize=bh if lay.look_rows == 2 else 0)

    # --- zona B: franja En vivo
    def build_live(self):
        tk, ttk, P, S = self.tk, self.ttk, self.px, self.sp
        lv = self.live = ttk.Frame(self.root, padding=(S("md"), S("sm")))
        lv.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.live_fr = [ttk.Frame(lv) for _ in range(3)]  # filas; antes que los items: quedan debajo de ellos
        self.dot = tk.Canvas(lv, width=P(26), height=P(26), highlightthickness=0)
        theme.paint(self.dot, bg="surface")
        self.dot_id = self.dot.create_oval(P(3), P(3), P(23), P(23), width=0)
        theme.paint(self.dot, self.dot_id, fill="beat_off")  # slow() lo pone en beat_on con cada golpe
        self.reg(self.dot, "vivo.punto")
        self.bpm = self.reg(ttk.Label(lv, text="-- BPM", style="Big.TLabel"), "vivo.bpm")
        self.mw, self.my = P(METER_W), tuple(P(v) for v in METER_Y)  # ancho y alturas de las barras
        self.meter = tk.Canvas(lv, width=self.mw, height=self.my[5], highlightthickness=0)
        theme.paint(self.meter, bg="trough")
        self.bar_l = self.meter.create_rectangle(0, 0, 0, 0, width=0)
        self.bar_o = self.meter.create_rectangle(0, 0, 0, 0, width=0)
        self.line = self.meter.create_line(0, 0, 0, 0, width=2)
        for item, token in ((self.bar_l, "meter_level"), (self.bar_o, "meter_hit"), (self.line, "meter_threshold")):
            theme.paint(self.meter, item, fill=token)
        self.reg(self.meter, "vivo.medidor")
        self.look_lbl = self.reg(ttk.Label(lv, text="", style="Big.TLabel"), "vivo.look")
        self.state = self.reg(ttk.Label(lv, text="", style="State.TLabel"), "vivo.estado")
        prev = self.prev = self.reg(tk.Frame(lv, bd=0, highlightthickness=1), "vivo.previa")
        theme.paint(prev, bg="trough", highlightbackground="border_strong", highlightcolor="border_strong")
        self.prev_lr = [tk.Frame(prev, width=P(PREVIEW[0]), height=P(PREVIEW[1]), bd=0, highlightthickness=0,
                                 bg=hexrgb(BLACK)) for _ in range(2)]
        for f in self.prev_lr:
            f.pack(side="left")
        # avisos (chips): Teclas siempre; SIN SEÑAL, SATURA, audio, TV remota y salidas, solo si aplican
        self.chips = ttk.Frame(lv)
        self.keys_chip = self.chip(self.chips, "vivo.teclas", "ok", font="font.small")
        self.keys_chip.configure(cursor="hand2")
        self.keys_chip.bind("<Button-1>", self.to_front)  # trae LightHouse al frente y no cambia nada más
        self.no_sig = self.chip(self.chips, "vivo.sin_senal", "danger_text")
        self.clip = self.chip(self.chips, "vivo.satura", "warn")
        self.audio_chip = self.chip(self.chips, "vivo.audio", "danger_text")
        self.net_chip = self.chip(self.chips, "vivo.red", "ok", font="font.small")
        self.warn_chip = self.chip(self.chips, "vivo.avisos", "warn", font="font.small")
        self.chip_list = [self.keys_chip, self.no_sig, self.clip, self.audio_chip, self.net_chip, self.warn_chip]
        # Modo: segmentos (cómoda) o lista desplegable (densa, ahorra ancho); los dos mueven self.mode
        self.mode = tk.StringVar(value=self.eng.mode)
        self.mode_seg = ttk.Frame(lv)
        ttk.Label(self.mode_seg, text="Modo", style="Muted.TLabel").pack(side="left", padx=(0, S("sm")))
        for m, text in zip(MODES, MODE_LABELS):
            self.segment(self.mode_seg, self.mode, m, text, f"modo.{m}", under="surface")
        self.mode_cb = self.reg(ttk.Combobox(lv, state="readonly", values=MODE_SHORT, takefocus=0,
                                             width=max(map(len, MODE_SHORT))), "modo.selector")
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self.mode.set(MODES[self.mode_cb.current()]))
        self.mode.trace_add("write", lambda *_: self.set_mode())
        self.vista_fr = ttk.Frame(lv)
        self.vista_lbl = ttk.Label(self.vista_fr, text="Vista", style="Muted.TLabel")  # solo en cómoda
        self.vista_cb = self.reg(ttk.Combobox(self.vista_fr, state="readonly", values=list(VISTAS.values()),
                                              takefocus=0, width=max(map(len, VISTAS.values()))), "vista.selector")
        self.vista_cb.pack(side="right")
        self.vista_cb.bind("<<ComboboxSelected>>",
                           lambda e: self.choose_vista(list(VISTAS)[self.vista_cb.current()]))
        self.bump_btn = self.reg(tk.Button(lv, text="Bump", takefocus=0, bd=1, padx=S("lg"), pady=S("xs"),
                                           highlightthickness=S("xs")), "bump")
        self.bump_btn.bind("<ButtonPress-1>", lambda e: self.set_bump_mouse(True))
        self.bump_btn.bind("<ButtonRelease-1>", lambda e: self.set_bump_mouse(False))
        self.style_bump(False)
        self.bo = tk.BooleanVar(value=False)
        self.bo_btn = self.reg(tk.Checkbutton(
            lv, text="Blackout", variable=self.bo, indicatoron=False, takefocus=0, padx=S("md"), pady=S("xs"),
            bd=1, highlightthickness=S("xs"), width=10,
            command=lambda: setattr(self.scene, "blackout", self.bo.get())), "blackout")
        self.bo.trace_add("write", lambda *_: self.style_blackout())
        self.style_blackout()
        # vista Mini: Siempre encima (interruptor) y Ampliar (sale de Mini); solo se empacan en Mini
        self.mini_top = tk.BooleanVar(value=True)
        self.top_btn = self.reg(tk.Checkbutton(
            lv, text="Encima", variable=self.mini_top, indicatoron=False, takefocus=0, padx=S("sm"),
            pady=S("xs"), bd=1, highlightthickness=S("xs"), command=self.set_mini_top), "vista.fijar")
        self.mini_top.trace_add("write", lambda *_: self.style_top())
        self.style_top()
        self.ampliar_btn = self.reg(tk.Button(lv, text="Ampliar", takefocus=0, bd=1, padx=S("sm"), pady=0,
                                              highlightthickness=S("xs"), command=self.ampliar), "vista.ampliar")
        self.style_bump(False, self.ampliar_btn)
        # línea de estado (zona segura): un clic trae LightHouse al frente y no cambia nada
        for w in (self.look_lbl, self.state, self.no_sig, self.clip, self.audio_chip):
            w.bind("<Button-1>", self.to_front)
        self.live_items = [self.dot, self.bpm, self.meter, self.look_lbl, self.state, self.prev, self.chips,
                           self.mode_seg, self.mode_cb, self.vista_fr, self.bump_btn, self.bo_btn, self.top_btn,
                           self.ampliar_btn, self.bar]
        self.pack_chips()
        self.style_segments(self.mode)

    def fit_chars(self, font_token, texts):
        """Ancho (en caracteres, como mide ttk) para que quepa el texto más largo: la franja no salta."""
        f = self.tkfont.Font(root=self.root, font=theme.tok(font_token))
        return math.ceil(max(f.measure(t) for t in texts) / f.measure("0"))

    def layout_live(self, lay, rows):
        """Cómoda: 3 filas (señal y look · estado y avisos · Modo, Vista, Bump y Blackout). Densa: 1 fila
        (ancho >= 1100) o 2 (arriba punto, BPM, medidor, look, vista previa y Blackout; abajo estado, avisos,
        Modo, Bump y Vista). Blackout va a la derecha y se empaca primero: si falta ancho, nunca se recorta.
        Mini (fases/diseno-ui.md §3.5): la barra de looks entra en la franja. Tira: looks + Blackout; abajo
        punto, BPM, medidor, línea de estado, vista previa, Encima y Ampliar. Bloque: punto, BPM, medidor,
        vista previa, Blackout, Encima y Ampliar; looks en 2 filas; línea de estado. La línea de estado se
        empaca la última: es lo que se recorta si falta sitio."""
        S, d, dense, mini = self.sp, self, lay.dense, lay.mode == "mini"
        for w in self.live_items:
            w.pack_forget()
        for r in self.live_fr:
            r.pack_forget()
        big = "Live.TLabel" if dense else "Big.TLabel"
        font = "font.title" if dense else "font.big"
        if mini:  # BPM solo con el número; look y estado a su ancho natural (nada a su derecha que salte)
            self.bpm.configure(style=big, width=self.fit_chars(font, ("--", "200")))
            self.look_lbl.configure(style="Mini.TLabel", width=0)
            self.state.configure(style="Mini.TLabel", width=0)
        else:
            self.bpm.configure(style=big, width=self.fit_chars(font, ("-- BPM", "200 BPM" + BPM_MANUAL[dense])))
            looks = [f"Look {self.keys[lid][0]} · {name}" for lid, (name, *_) in LOOKS.items()]
            self.look_lbl.configure(style=big, width=self.fit_chars(font, looks))
            self.state.configure(style="State.TLabel", width=self.fit_chars(
                "font.title", [state_text(s, dense, False) for s in STATES]))
        for c in (self.no_sig, self.clip, self.audio_chip):  # alarmas: más chicas en la línea del mini
            theme.paint(c, font="font.small" if mini else "font.title")
        self.mw = self.px(METER_W_MINI if mini else METER_W_DENSE if dense else
                          METER_W if lay.look_rows == 1 else METER_W_NARROW)
        self.my = tuple(self.px(v) for v in (METER_Y_DENSE if dense else METER_Y))
        self.meter.configure(width=self.mw, height=self.my[5])
        self.live.configure(padding=(S("xs"), S("xs")) if mini else (S("md"), S("sm")))
        # Blackout: en Mini 96 px de ancho (15 × 44 + 96 = la tira de 760) y >= 32 de alto
        self.bo_btn.configure(padx=S("sm" if mini else "md"), pady=S("sm" if mini else "xs"))
        if dense:
            self.vista_lbl.pack_forget()
        else:
            self.vista_lbl.pack(side="left", padx=(0, S("sm")))
        if mini and lay.look_rows == 1:  # tira
            spec = [([d.bar], [d.bo_btn]),
                    ([d.dot, d.bpm, d.meter, d.look_lbl, d.state, d.chips], [d.ampliar_btn, d.top_btn, d.prev])]
        elif mini:  # bloque
            spec = [([d.dot, d.bpm, d.meter, d.prev], [d.ampliar_btn, d.top_btn, d.bo_btn]), ([d.bar], []),
                    ([d.look_lbl, d.state, d.chips], [])]
        elif not dense:
            spec = [([d.dot, d.bpm, d.meter, d.look_lbl, d.prev], []), ([d.state, d.chips], []),
                    ([d.mode_seg], [d.bo_btn, d.bump_btn, d.vista_fr])]
        elif rows == 1:
            spec = [([d.dot, d.bpm, d.meter, d.look_lbl, d.state, d.prev, d.chips, d.mode_cb, d.vista_fr],
                     [d.bo_btn, d.bump_btn])]
        else:
            spec = [([d.dot, d.bpm, d.meter, d.look_lbl, d.prev], [d.bo_btn]),
                    ([d.state, d.chips, d.mode_cb, d.bump_btn, d.vista_fr], [])]
        gap = S("sm") if dense else S("md")
        for i, (left, right) in enumerate(spec):
            row = self.live_fr[i]
            row.pack(fill="x", pady=(S("xs" if mini else "sm") if i else 0, 0))
            for w in right:  # primero: pack recorta a los últimos empacados
                tira_bo = mini and d.bar in left  # pegado a los looks y de su alto
                w.pack(in_=row, side="right", padx=(0 if tira_bo else gap, 0), fill="y" if tira_bo else "none")
            for w in left:
                if w is d.bar:  # la barra de looks ocupa lo que queda de su fila
                    w.pack(in_=row, side="left", fill="x", expand=True)
                else:  # en Mini el último de la línea de estado no deja hueco a su derecha
                    w.pack(in_=row, side="left", padx=(0, 0 if mini and w is d.chips else gap))
        if not mini:
            self.bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        i, left = next((i, left) for i, (left, _) in enumerate(spec) if d.state in left)
        self.state_at = (self.live_fr[i], left[left.index(d.state) + 1])  # fila y vecino (para volver a ponerlo)
        self.pack_chips()

    def mini_state_fits(self, w):
        """Mini bloque: ¿cabe el estado del modo junto al look y el aviso Teclas, en el peor caso? (w en px
        lógicos). La tira siempre tiene sitio."""
        fl, fs = (self.tkfont.Font(root=self.root, font=theme.tok(t)) for t in ("font.look", "font.small"))
        look = max(fl.measure(f"Look {self.keys[lid][0]} · {name}") for lid, (name, *_) in LOOKS.items())
        state = max(fl.measure(state_text(s, True, True)) for s in STATES)
        keys = max(fs.measure(t) for t in KEYS_TEXTS) + 2 * self.px(6)  # padx del chip
        return look + state + keys + 3 * self.sp("sm") <= self.px(w) - 2 * self.sp("xs")  # 3 separaciones

    def pack_chips(self):
        """Los avisos vacíos no ocupan lugar: se empacan solo los visibles, siempre en el mismo orden.
        En densa, una alarma (SIN SEÑAL, SATURA, audio) ocupa el lugar del estado del modo. En Mini solo van
        las alarmas (en el lugar del estado) y Teclas; el estado del bloque, solo si cabe."""
        alarms = (self.no_sig, self.clip, self.audio_chip)
        mini = self.draw is not None and self.draw.mode == "mini"
        for c in self.chip_list:
            c.pack_forget()
        for c in ([*alarms, self.keys_chip] if mini else self.chip_list):
            if self.chip_vis[c] or c is self.keys_chip:
                c.pack(side="left", padx=(0, self.sp("sm")))
        if self.draw is None:
            return
        alarm = any(self.chip_vis[c] for c in alarms)
        if (self.draw.dense and alarm) or (mini and not self.state_fits):
            self.state.pack_forget()
        elif not self.state.winfo_manager():
            row, nxt = self.state_at
            self.state.pack(in_=row, side="left", before=nxt, padx=(0, self.sp("sm" if self.draw.dense else "md")))

    def chip_set(self, lb, text, token=None):
        """Texto (y color) de un aviso, solo si cambió; vacío = oculto."""
        key = ("chip", str(lb))
        if self.shown.get(key) == (text, token):
            return
        self.shown[key] = (text, token)
        lb.configure(text=text)
        if token:
            theme.paint(lb, fg=token)
        if bool(text) != self.chip_vis[lb]:
            self.chip_vis[lb] = bool(text)
            self.pack_chips()

    # --- banda de primer arranque (fases/diseno-ui.md §6.1): no modal, entre la franja En vivo y las pestañas
    def build_band(self):
        tk, ttk, S = self.tk, self.ttk, self.sp
        fr = self.band_fr = ttk.Frame(self.root, padding=(S("md"), S("sm")))
        self.no_ask = tk.BooleanVar(value=False)
        right = [self.reg(ttk.Checkbutton(fr, text="No volver a preguntar", variable=self.no_ask, takefocus=0),
                          "tut.no_preguntar"),
                 self.reg(ttk.Button(fr, text="Ahora no", takefocus=0, command=self.band_no), "tut.ahora_no"),
                 self.reg(ttk.Button(fr, text="Ver tutorial", takefocus=0, command=self.tut_start), "tut.ver")]
        for w in right:
            w.pack(side="right", padx=(S("md"), 0))
        lb = ttk.Label(fr, text="¿Primera vez con LightHouse? Recorrido de 2 minutos.", wraplength=self.px(TEXT_W))
        lb.pack(side="left", fill="x", expand=True)

        def wrap(e):  # el texto se parte en el ancho que dejan los botones (solo si cambia: sin bucles)
            w = max(e.width - sum(b.winfo_reqwidth() + S("md") for b in right) - 2 * S("md"), self.px(140))
            if str(lb.cget("wraplength")) != str(w):
                lb.configure(wraplength=w)
        fr.bind("<Configure>", wrap)

    def band_wanted(self):
        return (self.tut_state == "preguntar" and not self.band_off and self.draw is not None
                and self.draw.mode != "mini" and not self.tut.on and not self.intro_on)

    def update_band(self):
        """Muestra u oculta la banda (nunca en Mini, con el tutorial abierto ni durante la intro)."""
        self.band_on = want = self.band_wanted()
        if self.headless:  # sin ventana: solo el estado, para el self-check
            return
        if want:
            self.band_fr.grid(row=2, column=0, columnspan=2, sticky="ew")
        else:
            self.band_fr.grid_remove()

    def band_no(self):
        """Ahora no: oculta la banda; con la casilla marcada no vuelve a preguntar nunca."""
        self.band_off = True
        if self.no_ask.get():
            self.tut_state = "no_preguntar"
        self.update_band()

    def tut_start(self):
        self.tut.start()

    def set_tutorial(self, state):
        self.tut_state = state
        self.update_band()

    # --- zona C: pestañas
    def build_tabs(self):
        S = self.sp
        tb = self.tabbar = self.ttk.Frame(self.root, style="Bg.TFrame", padding=(S("md"), S("md"), S("md"), 0))
        tb.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.tab_var = self.tk.StringVar(value="show")
        for tid, name in TABS.items():
            self.segment(tb, self.tab_var, tid, f"  {name}  ", f"tab.{tid}", under="bg", style="Bg.TFrame",
                         command=self.show_tab)
        self.style_segments(self.tab_var)

    # --- zona D: cuerpo de tarjetas (Canvas estático: solo se mueve al desplazar)
    def build_body(self):
        tk, ttk, S = self.tk, self.ttk, self.sp
        cv = self.body_cv = tk.Canvas(self.root, highlightthickness=0, bd=0, width=1, height=1,
                                      yscrollincrement=self.px(24))
        theme.paint(cv, bg="bg")
        cv.grid(row=4, column=0, sticky="nsew")
        self.body_sb = ttk.Scrollbar(self.root, orient="vertical", command=cv.yview, takefocus=0)
        cv.configure(yscrollcommand=self.body_sb.set)
        body = self.body = ttk.Frame(cv, style="Bg.TFrame", padding=(S("sm"), S("sm"), S("sm"), S("sm")))
        self.body_win = cv.create_window(0, 0, window=body, anchor="nw")
        # columnas: se crean antes que las tarjetas (quedan debajo) y cada tarjeta se coloca en una con grid(in_=)
        self.colfr = [ttk.Frame(body, style="Bg.TFrame") for _ in range(layout.MAX_COLS)]
        for cf in self.colfr:
            cf.columnconfigure(0, weight=1)
        cv.bind("<Configure>", self.on_body_view)
        body.bind("<Configure>", self.on_body_view)

    def card(self, cid, title, basic=True):
        """Tarjeta (hija del contenedor único): devuelve el marco de su parte básica (None si no tiene)."""
        fr = self.cards[cid] = self.ttk.LabelFrame(self.body, text=title, padding=self.sp("md"))
        if not basic:
            return None
        b = self.ttk.Frame(fr)
        b.pack(fill="x")
        return b

    def advanced(self, cid):
        """Botón "Avanzado ▸" de la tarjeta y el marco (plegado) de su parte avanzada."""
        fr = self.cards[cid]
        btn = self.reg(self.ttk.Button(fr, text="Avanzado ▸", style="Link.TButton", takefocus=0,
                                       command=lambda: self.toggle_adv(cid)), f"avanzado.{cid}")
        btn.pack(anchor="w", fill="x", pady=(self.sp("xs"), 0))
        a = self.ttk.Frame(fr)
        self.adv[cid], self.adv_open[cid], self.adv_dirty[cid] = (btn, a), False, False
        return a

    def set_adv(self, cid, on):
        self.adv_open[cid] = bool(on)
        btn, a = self.adv[cid]
        if on:
            a.pack(fill="x", after=btn)
        else:
            a.pack_forget()
        btn.configure(text=("Avanzado ▾" if on else "Avanzado ▸") + (" •" if self.adv_dirty[cid] else ""))

    def toggle_adv(self, cid):
        self.set_adv(cid, not self.adv_open[cid])  # el alto nuevo llega por <Configure> (on_body_view)

    def update_dots(self, s):
        """Punto • en "Avanzado" si algún valor de esa parte no está en su default."""
        d, o = self.defaults, (self.sel() if self.outputs else None)
        for cid, keys in ADV_KEYS.items():
            dirty = any(s[k] != d[k] for k in keys)
            if cid == "teclado":
                dirty = any(s["ui"][k] != d["ui"][k] for k in ("tab_nav", "mini_sin_foco"))
            elif cid == "salida_sel":
                dirty = bool(o) and (o.delay_ms != 0 or (o.remote and o.port != net.PORT))
            if dirty != self.adv_dirty[cid]:
                self.adv_dirty[cid] = dirty
                self.set_adv(cid, self.adv_open[cid])

    def row(self, parent, label):
        """Fila 'etiqueta + widgets' (la etiqueta se parte en dos líneas si no cabe)."""
        r = self.ttk.Frame(parent)
        r.pack(fill="x", pady=self.sp("xs"))
        self.ttk.Label(r, text=label, width=LABEL_W, wraplength=self.label_px).pack(side="left")
        return r

    def field(self, parent, wid, label, make, **pack):
        """Fila 'etiqueta + widget'; registra el widget con su id y lo devuelve."""
        w = self.reg(make(self.row(parent, label)), wid)
        w.pack(side="left", **pack)
        return w

    def note(self, parent, text="", style="Muted.TLabel"):
        lb = self.ttk.Label(parent, text=text, style=style, wraplength=self.px(TEXT_W))
        if text:
            lb.pack(anchor="w", pady=(self.sp("xs"), 0))
        return lb

    def note_set(self, lb, text):
        """Texto de una nota que cambia en vivo (solo si cambió); vacía no ocupa una línea en la tarjeta.
        Las notas vivas van al final de su marco: al volver a mostrarse quedan en el mismo lugar."""
        key = ("note", str(lb))
        if self.shown.get(key) == text:
            return
        self.shown[key] = text
        lb.config(text=text)
        if not text:
            lb.pack_forget()
        elif not lb.winfo_manager():
            lb.pack(anchor="w", pady=(self.sp("xs"), 0))

    # --- pestaña Show
    def build_show(self):
        tk, ttk, S = self.tk, self.ttk, self.sp
        f = self.card("respuesta", "Respuesta")
        self.resp = self.presets(f, "resp.preset", RESPONSE)
        self.slider(f, "golpe.sens", "Sensibilidad (×)", "sens", 1.0, 3.0, res=0.1)
        self.limit_cb = self.check(f, "resp.limite", "Limitar destellos", "flash_limit")
        self.photo = ttk.Label(f, text=PHOTO_WARN, style="Warn.TLabel", wraplength=self.px(TEXT_W))
        self.checks["flash_limit"].trace_add("write", lambda *_: self.show_photo())  # visible sin el límite
        a = self.advanced("respuesta")
        self.slider(a, "resp.limite_hz", "Máx. destellos/s", "flash_limit_hz", 3, 10)

        f = self.card("luz", "Luz")
        self.slider(f, "luz.master", "Brillo general (%)", "vmax", 0, 100, k=0.01)
        self.slider(f, "luz.decay", "Duración del destello (ms)", "decay", 50, 1000, k=0.001)
        self.presets(f, "luz.sinc_preset", OFFSETS)
        self.slider(f, "luz.offset", "Adelantar / atrasar la luz (ms)", "offset", -150, 300, k=0.001, res=5)
        self.lead = self.note(f)
        a = self.advanced("luz")
        self.slider(a, "luz.piso", "Luz mínima entre golpes (%)", "vmin", 0, 50, k=0.01)
        self.slider(a, "luz.gamma", "Curva de brillo", "gamma", 0.5, 3.0, res=0.1)
        self.slider(a, "luz.manual", "Brillo en modo Manual (%)", "manual", 0, 100, k=0.01)

        f = self.card("color", "Color del look 1")
        self.color_mode = self.field(f, "color.modo", "Tipo de color", lambda r: ttk.Combobox(
            r, state="readonly", takefocus=0, values=COLOR_MODES), fill="x", expand=True)
        self.color_mode.set("Blanco")
        self.kelvin = self.slider(f, "color.kelvin", "Temperatura (K)", None, 2000, 10000, res=100, init=4000,
                                  key="kelvin")
        r = self.row(f, "Paleta")
        self.swatch = tk.Canvas(r, width=self.px(SWATCH_W), height=self.px(22), highlightthickness=0)
        self.swatch.pack(side="left")
        theme.paint(self.swatch, bg="surface")
        self.reg(self.swatch, "color.paleta")
        self.reg(ttk.Button(r, text="+", width=3, command=self.add_color, takefocus=0),
                 "color.mas").pack(side="left", padx=S("xs"))
        self.reg(ttk.Button(r, text="−", width=3, command=self.pop_color, takefocus=0),
                 "color.menos").pack(side="left")
        self.draw_palette()

        self.card("estrobos", "Estrobos Q–Y", basic=False)
        a = self.advanced("estrobos")
        self.slider(a, "estrobo.cierre", "Cuándo se apaga el estrobo", "cierre", 0.2, 0.9, res=0.05)
        self.slider(a, "estrobo.min", "Duración mínima (ms)", "strobe_min_ms", 20, 120)

        f = self.card("teclado", "Teclado")
        self.global_keys = tk.BooleanVar(value=False)
        self.reg(ttk.Checkbutton(f, text="Teclas siempre activas (globales)", variable=self.global_keys,
                                 takefocus=0), "teclas.globales").pack(anchor="w")
        self.keys_note = self.note(f, LOCAL_NOTE)
        self.global_keys.trace_add("write", lambda *_: self.set_global_keys())
        a = self.advanced("teclado")
        self.tab_nav = tk.BooleanVar(value=False)
        self.reg(ttk.Checkbutton(a, text="Navegar con Tab", variable=self.tab_nav, takefocus=0),
                 "teclas.tab").pack(anchor="w")
        self.note(a, "Tab recorre los controles; mientras uno tiene el foco, las teclas de show quedan en "
                     "pausa. Esc las devuelve.")
        self.tab_nav.trace_add("write", lambda *_: self.set_tab_nav())
        self.mini_nofocus = tk.BooleanVar(value=False)  # ui.mini_sin_foco (se aplica al entrar a Mini)
        self.reg(ttk.Checkbutton(a, text="No quitar el teclado en Mini (experimental)", variable=self.mini_nofocus,
                                 takefocus=0), "vista.sin_foco").pack(anchor="w", pady=(S("sm"), 0))
        self.note(a, NOFOCUS_NOTE)

    # --- pestaña Audio
    def build_audio(self):
        tk, ttk, S = self.tk, self.ttk, self.sp
        f = self.card("fuente", "Fuente de audio")
        self.dev = self.reg(ttk.Combobox(f, state="readonly", width=44, takefocus=0), "audio.dispositivo")
        self.dev.pack(fill="x")
        self.dev.bind("<<ComboboxSelected>>", lambda e: self.pick_device())
        self.chan = self.field(f, "audio.canal", "Canal", lambda r: ttk.Combobox(
            r, state="readonly", values=["Mezcla"], width=9, takefocus=0))
        self.chan.current(0)
        self.chan.bind("<<ComboboxSelected>>", lambda e: self.pick_channel())
        r = ttk.Frame(f)
        r.pack(fill="x", pady=(S("xs"), 0))
        self.reg(ttk.Button(r, text="Reconectar", command=self.reconnect, takefocus=0),
                 "audio.reconectar").pack(side="left", anchor="n")
        self.status = self.reg(ttk.Label(r, text="", wraplength=self.px(240)), "audio.estado")
        self.status.pack(side="left", padx=S("md"))
        a = self.advanced("fuente")
        self.low_prio = tk.BooleanVar(value=True)
        self.low_prio.trace_add("write", lambda *_: win32.set_low_priority(self.low_prio.get()))
        self.reg(ttk.Checkbutton(a, text="Dar prioridad a rekordbox", variable=self.low_prio, takefocus=0),
                 "audio.prioridad").pack(anchor="w")

        f = self.card("ganancia", "Nivel de entrada")
        self.agc = tk.BooleanVar(value=self.eng.agc)
        self.checks["agc"] = self.agc
        self.reg(ttk.Radiobutton(f, text="Automático", value=True, variable=self.agc, takefocus=0),
                 "nivel.auto").pack(anchor="w")
        self.reg(ttk.Radiobutton(f, text="Fijo (manda la perilla del mezclador)", value=False, variable=self.agc,
                                 takefocus=0), "nivel.fijo").pack(anchor="w")
        a = self.advanced("ganancia")
        self.slider(a, "nivel.ref", "Nivel de referencia (dB)", "ref_db", -40, 0)
        self.agc.trace_add("write", lambda *_: self.set_agc())
        self.set_agc()

        f = self.card("filtro", "Qué escucha")
        self.preset = self.reg(ttk.Combobox(f, state="readonly", values=list(FILTERS), takefocus=0),
                               "filtro.preset")
        self.preset.set("Kick (120 Hz)")
        self.preset.pack(fill="x")
        self.preset.bind("<<ComboboxSelected>>", lambda e: self.pick_filter())
        a = self.advanced("filtro")
        self.band = self.slider(a, "filtro.corte", "Hasta qué frecuencia (Hz)", "band", 40, 250,
                                fn=self.band_from_slider)

        self.card("golpe", "Golpe", basic=False)
        a = self.advanced("golpe")
        self.slider(a, "golpe.pausa", "Pausa mínima entre golpes (ms)", "min_gap", 120, 500, k=0.001)
        self.slider(a, "golpe.compuerta", "Ignorar sonido por debajo de (dB)", "gate_db", -60, -30)
        self.check(a, "golpe.fuerza", "Golpes fuertes brillan más", "by_strength")

        f = self.card("tempo", "Ritmo")
        self.sync = tk.StringVar(value=self.eng.sync)
        self.sync.trace_add("write", lambda *_: setattr(self.eng, "sync", self.sync.get()))
        self.reg(ttk.Radiobutton(f, text="En cada golpe", value="kick", variable=self.sync, takefocus=0),
                 "tempo.kick").pack(anchor="w")
        self.reg(ttk.Radiobutton(f, text="Al ritmo (sigue aunque no haya golpe)", value="tempo",
                                 variable=self.sync, takefocus=0), "tempo.ritmo").pack(anchor="w")
        r = self.row(f, "BPM")
        self.src = self.reg(ttk.Combobox(r, state="readonly", values=["Detectado", "Manual / Tap"], width=13,
                                         takefocus=0), "tempo.fuente")
        self.src.set("Detectado")
        self.src.pack(side="left")
        self.src.bind("<<ComboboxSelected>>", lambda e: setattr(
            self.eng, "bpm_src", "manual" if self.src.get().startswith("Manual") else "auto"))
        self.reg(ttk.Button(f, text="Marcar el ritmo [0]", command=self.tap, takefocus=0),
                 "tempo.tap").pack(anchor="w", pady=(S("xs"), 0))
        a = self.advanced("tempo")
        self.slider(a, "tempo.bpm_manual", "BPM manual", "bpm_manual", 60, 200)
        div = self.div = self.field(a, "tempo.divisor", "Un destello cada", lambda r: ttk.Combobox(
            r, state="readonly", values=["1/1", "1/2", "1/4"], width=5, takefocus=0))
        div.set("1/1")
        div.bind("<<ComboboxSelected>>", lambda e: setattr(self.eng, "divisor", int(div.get()[2:])))

        f = self.card("tranquilo", "Calma")
        self.presets(f, "calma.preset", CALM)
        a = self.advanced("tranquilo")
        self.slider(a, "calma.espera", "Esperar sin golpes (s)", "calm_after", 2, 15)
        self.slider(a, "calma.suavidad", "Suavidad del cambio (s)", "calm_smooth", 1, 3, res=0.1)
        self.slider(a, "calma.base", "Brillo en calma (%)", "calm_base", 0, 60, k=0.01)
        self.slider(a, "calma.respira", "Cuánto respira (%)", "calm_depth", 0, 60, k=0.01)

    # --- pestaña Salidas: lista + campos de la seleccionada (se editan en vivo)
    def build_outputs(self):
        tk, ttk, S = self.tk, self.ttk, self.sp
        f = self.card("salidas", "Salidas")
        self.out_list = self.reg(tk.Listbox(f, height=MAX_OUTPUTS, width=36, exportselection=False,
                                            activestyle="none", takefocus=0, bd=0, highlightthickness=1),
                                 "salidas.lista")
        theme.paint(self.out_list, bg="surface_alt", fg="fg", selectbackground="accent",
                    selectforeground="accent_fg", highlightbackground="border_strong", highlightcolor="accent",
                    font="font.body")
        self.out_list.pack(fill="x")
        self.out_list.bind("<<ListboxSelect>>", lambda e: self.show_output())
        r = ttk.Frame(f)
        r.pack(fill="x", pady=(S("sm"), 0))
        self.out_add = self.reg(ttk.Button(r, text="Agregar", command=self.add_output, takefocus=0),
                                "salidas.agregar")
        self.out_add.pack(side="left")
        self.out_del = self.reg(ttk.Button(r, text="Quitar", command=self.del_output, takefocus=0),
                                "salidas.quitar")
        self.out_del.pack(side="left", padx=S("md"))
        self.out_tv = self.reg(ttk.Button(r, text="Agregar TV remota", command=lambda: self.add_output(True),
                                          takefocus=0), "salidas.tv")
        self.out_tv.pack(side="left")
        r = ttk.Frame(f)
        r.pack(fill="x", pady=(S("sm"), 0))
        self.reg(ttk.Button(r, text="Identificar pantallas", command=self.identify, takefocus=0),
                 "salidas.identificar").pack(side="left")
        self.reg(ttk.Button(r, text="Calibrar sincronía", command=self.calibrate, takefocus=0),
                 "salidas.calibrar").pack(side="left", padx=S("md"))
        self.note(f, "En la salida: doble clic = pantalla completa (en el monitor donde está) / ventana; "
                     "Esc = ventana. Fuera del look 1 (o en \"siempre\") la salida sigue el look y oculta el logo.")
        self.net_lbl = self.note(f, style="Ok.TLabel")   # estado de las salidas remotas (completo)
        self.out_warn = self.note(f, style="Warn.TLabel")  # avisos de las salidas (completos)

        f = self.card("salida_sel", "Salida seleccionada")
        self.o_name = tk.StringVar()
        ent = self.field(f, "sal.nombre", "Nombre", lambda r: ttk.Entry(r, textvariable=self.o_name, width=26),
                         fill="x", expand=True)
        self.text_entry(ent)
        self.o_name.trace_add("write", lambda *_: self.edit_output("name", self.o_name.get()))
        slot = ttk.Frame(f)  # monitor y pantalla completa (local) | destino (remota)
        slot.pack(fill="x")
        self.loc_fr, self.rem_fr = ttk.Frame(slot), ttk.Frame(slot)
        self.o_dest = self.field(self.rem_fr, "sal.destino", "Destino", lambda r: ttk.Combobox(
            r, values=[net.AUTO], width=26), fill="x", expand=True)
        self.text_entry(self.o_dest, self.edit_remote)
        self.o_dest.bind("<<ComboboxSelected>>", lambda e: self.edit_remote())
        self.o_mon = self.field(self.loc_fr, "sal.monitor", "Monitor", lambda r: ttk.Combobox(
            r, state="readonly", width=30, takefocus=0, postcommand=self.list_monitors), fill="x", expand=True)
        self.o_mon.bind("<<ComboboxSelected>>", lambda e: self.pick_monitor())
        self.o_full = self.field(self.loc_fr, "sal.completa", "", lambda r: ttk.Button(
            r, text="Pantalla completa", takefocus=0, command=lambda: self.sel().set_full(not self.sel().full)),
            fill="x", expand=True)
        self.o_master = self.out_slider(f, "sal.master", "Brillo de esta salida (%)", "master", 0, 100)
        self.o_content = self.field(f, "sal.contenido", "Contenido", lambda r: ttk.Combobox(
            r, state="readonly", values=CONTENT, width=12, takefocus=0))
        self.o_content.bind("<<ComboboxSelected>>", lambda e: self.edit_output("content", self.o_content.get()))
        logo_slot = ttk.Frame(f)
        logo_slot.pack(fill="x")
        self.o_logo = tk.StringVar()
        ent = self.field(logo_slot, "sal.logo", "Logo (PNG)", lambda r: ttk.Entry(
            r, textvariable=self.o_logo, width=22), fill="x", expand=True)
        r = self.logo_row = ent.master
        self.text_entry(ent, lambda: self.set_logo(self.o_logo.get()))
        self.reg(ttk.Button(r, text="…", width=3, command=self.browse_logo, takefocus=0),
                 "sal.logo_buscar").pack(side="left", padx=(S("sm"), 0))
        self.o_join = self.field(f, "sal.unirse", "Seguir los looks", lambda r: ttk.Combobox(
            r, state="readonly", values=JOIN, width=12, takefocus=0))
        self.o_join.bind("<<ComboboxSelected>>", lambda e: self.edit_output("join", self.o_join.get()))
        a = self.advanced("salida_sel")
        self.o_delay = self.out_slider(a, "sal.retardo", "Retraso de esta pantalla (ms)", "delay_ms", 0, 200)
        port_slot = ttk.Frame(a)  # solo en una salida remota
        port_slot.pack(fill="x")
        self.o_port = tk.StringVar()
        ent = self.field(port_slot, "sal.puerto", "Puerto", lambda r: ttk.Entry(
            r, textvariable=self.o_port, width=8))
        self.port_row = ent.master
        self.text_entry(ent, self.edit_remote)

    # --- pestaña Ayuda
    def build_help(self):
        ttk, S = self.ttk, self.sp
        f = self.card("atajos", "Atajos")
        grid = ttk.Frame(f)
        grid.pack(fill="x")
        # dos columnas de "teclas | acción" (una etiqueta de varias líneas por columna: sin alto extra por
        # fila); set_keys escribe las teclas del mapa real
        acts = list(KEYS)
        half = (len(acts) + 1) // 2
        self.key_cols = []
        for col, part in enumerate((acts[:half], acts[half:])):
            k = ttk.Label(grid, text="", style="State.TLabel", justify="left")
            k.grid(row=0, column=2 * col, sticky="nw", padx=(S("lg") if col else 0, S("md")))
            ttk.Label(grid, style="Muted.TLabel", justify="left", text="\n".join(
                LOOKS[a][0] if a in LOOKS else ACTION_NAMES[a] for a in part)).grid(row=0, column=2 * col + 1,
                                                                                     sticky="nw")
            self.key_cols.append((k, part))
        self.note(f, KEYS_NOTE).pack_configure(pady=(S("sm"), 0))  # sm: con F9 (fila 13) cabe en compacto

        f = self.card("ayuda", "Ayuda")
        ttk.Label(f, text=f"LightHouse {VERSION}", style="State.TLabel").pack(anchor="w")
        for title, path in (("Configuración", config.path()), ("Registros (lighthouse.log)", config.log_dir())):
            ttk.Label(f, text=title, style="Muted.TLabel").pack(anchor="w", pady=(S("md"), 0))
            ttk.Label(f, text=config.shown(path), wraplength=self.px(TEXT_W)).pack(anchor="w")
        r = ttk.Frame(f)  # los dos botones en una fila: con Tema, la tarjeta sigue cabiendo en compacto (480)
        r.pack(fill="x", pady=(S("md"), 0))
        self.reg(ttk.Button(r, text="Ver tutorial", command=self.tut_start, takefocus=0),
                 "ayuda.tutorial").pack(side="left")
        self.reg(ttk.Button(r, text="Abrir carpeta de registros", command=self.open_logs, takefocus=0),
                 "ayuda.carpeta").pack(side="left", padx=(S("md"), 0))
        self.tips_on = self.tk.BooleanVar(value=True)  # ui.tips
        self.reg(ttk.Checkbutton(f, text="Mostrar ayudas al pasar el ratón", variable=self.tips_on, takefocus=0),
                 "ayuda.tips").pack(anchor="w", pady=(S("md"), 0))
        self.tips_on.trace_add("write", lambda *_: self.tip.hide())
        self.intro_var = self.tk.BooleanVar(value=True)  # ui.intro
        self.reg(ttk.Checkbutton(f, text="Animación de entrada", variable=self.intro_var, takefocus=0),
                 "ayuda.intro").pack(anchor="w", pady=(S("md"), 0))
        labels = [theme.get(n)["label"] for n in theme.NAMES]  # ui.theme: se aplica en el acto, sin confirmar
        self.theme_cb = self.field(f, "ayuda.tema", "Tema", lambda r: ttk.Combobox(
            r, state="readonly", values=labels, width=max(map(len, labels)), takefocus=0))
        self.theme_cb.master.pack_configure(pady=(S("md"), 0))
        self.theme_cb.set(labels[0])
        self.theme_cb.bind("<<ComboboxSelected>>", lambda e: self.choose_theme(theme.NAMES[self.theme_cb.current()]))
        self.theme_note = self.note(f)  # solo si glass se ve opaco en este equipo (va al final de la tarjeta)

    def open_logs(self):
        d = config.log_dir()
        os.makedirs(d, exist_ok=True)
        os.startfile(d)

    # --- layout responsive (fases/diseno-ui.md §3)
    def on_root_configure(self, e):
        """Al arrastrar el borde llegan decenas de Configure: un solo after cancelable (como Output.later)."""
        self.later("layout", theme.tok("motion.layout_debounce"), self.relayout)

    def later(self, key, ms, fn):
        if key in self.jobs:
            self.root.after_cancel(self.jobs[key])
        self.jobs[key] = self.root.after(ms, lambda: (self.jobs.pop(key, None), fn()))

    def relayout(self, w=None, h=None, force=False):
        """Elige el layout para el tamaño (px lógicos; sin argumentos, el de la ventana) y recoloca solo si
        cambió. Los widgets nunca se destruyen ni se recrean."""
        win = w is None
        if win:
            w, h = self.root.winfo_width() / self.scale, self.root.winfo_height() / self.scale
            if w < 50 or h < 20:  # minimizada o aún sin mapear
                return
        lay = layout.pick(w, h, self.vista, self.layout)
        rows = layout.live_rows(w, lay.dense, self.live_n)
        if win and lay.mode != "mini":  # la ventana normal a la que vuelven Ampliar y F9
            self.geo_normal = (self.root.geometry(), self.root.state() == "zoomed")
        fits = self.mini_state_fits(w) if lay.mode == "mini" and lay.look_rows == 2 else True
        if force or (lay, rows, fits) != (self.layout, self.live_n, self.state_fits):
            t0 = time.perf_counter()
            self.apply_layout(lay, rows, w)
            self.t_layout = (time.perf_counter() - t0) * 1000
            log.info("layout: %s, %d col, looks en %d fila(s), franja en %d (%.0f × %.0f px lógicos, %.1f ms)",
                     lay.mode, self.draw.cols, lay.look_rows, rows, w, h, self.t_layout)

    def apply_layout(self, lay, rows, w):
        """Recoloca solo las zonas cuyos parámetros cambiaron (looks, franja, tarjetas). Mini: sin pestañas ni
        tarjetas (grid_remove: no se destruyen)."""
        self.layout, self.live_n = lay, rows
        old, new = self.draw, lay
        self.draw = new
        self.tip.hide()
        mini, was = new.mode == "mini", old is not None and old.mode == "mini"
        fits = self.mini_state_fits(w) if mini and new.look_rows == 2 else True
        if old is None or mini != was:
            self.show_full(not mini)
            if was:
                self.mini_window(False)  # al salir de Mini (también agrandándola a mano) deja de estar encima
        if old is None or (old.look_rows, old.dense, was) != (new.look_rows, new.dense, mini):
            self.layout_looks(new)
        if old is None or (old.look_rows, old.dense, was, self.live_drawn, self.state_fits) != (
                new.look_rows, new.dense, mini, rows, fits):
            self.state_fits = fits
            self.layout_live(new, rows)
            self.live_drawn = rows
        if old is None or old.cols != new.cols:
            self.place_cards()

    def show_full(self, on):
        """Pestañas y cuerpo de tarjetas; en Mini se quitan con grid_remove y el título es corto."""
        if on:
            self.tabbar.grid()
            self.body_cv.grid()  # la barra de desplazamiento la decide on_body_view
        else:
            for w in (self.tabbar, self.body_cv, self.body_sb):
                w.grid_remove()
            self.sb_on = False
        self.root.title("LightHouse · Control" if on else "LightHouse")
        self.update_band()

    def place_cards(self):
        """Tarjetas de la pestaña activa en sus columnas (layout.plan); las de otras pestañas, grid_remove."""
        S = self.sp
        want = {cid: (c, r) for cid, c, r in layout.plan(self.draw, self.tab_var.get())}
        for cid, fr in self.cards.items():
            if cid not in want:
                fr.grid_remove()
        for i, cf in enumerate(self.colfr):
            if i < self.draw.cols:
                cf.grid(row=0, column=i, sticky="new", padx=S("xs"))
                self.body.columnconfigure(i, weight=1, uniform="cols")
            else:
                cf.grid_remove()
                self.body.columnconfigure(i, weight=0, uniform="")
        for cid, (c, r) in want.items():
            self.cards[cid].grid(in_=self.colfr[c], row=r, column=0, sticky="new", pady=(0, S("sm")))

    def show_tab(self):
        self.tip.hide()
        self.place_cards()
        self.body_cv.yview_moveto(0)

    def fit_body(self):
        """El Canvas del cuerpo pide el tamaño de sus tarjetas: así la ventana pide su contenido entero (solo
        para medir; en pantalla el cuerpo toma el alto que sobra y se desplaza con on_body_view)."""
        self.root.update_idletasks()
        self.body_cv.configure(width=self.body.winfo_reqwidth(), height=self.body.winfo_reqheight())
        self.on_body_view()

    def on_body_view(self, e=None):
        """Región de desplazamiento y barra: solo si las tarjetas no caben en el alto disponible."""
        cv = self.body_cv
        if e is not None and e.widget is cv:
            cv.itemconfigure(self.body_win, width=e.width)
        bh, h = self.body.winfo_reqheight(), cv.winfo_height()
        cv.configure(scrollregion=(0, 0, cv.winfo_width(), bh))
        mini = self.draw is not None and self.draw.mode == "mini"
        need = not mini and bool(self.root.winfo_viewable()) and bh > h + 1
        if need != self.sb_on:
            self.sb_on = need
            if need:
                self.body_sb.grid(row=4, column=1, sticky="ns")
            else:
                self.body_sb.grid_remove()
        if not need:
            cv.yview_moveto(0)

    @staticmethod
    def inside(w, parent):
        """w es parent o un descendiente suyo (por ruta de Tk; w puede ser un nombre)."""
        s, p = str(w), str(parent)
        return s == p or s.startswith(p + ".")

    def on_wheel(self, e):
        """La rueda solo desplaza el cuerpo de tarjetas (nunca cambia el valor de un control)."""
        if self.sb_on and self.inside(e.widget, self.body_cv):
            self.body_cv.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def measure(self, w, h, tab, forced="auto"):
        """Tamaño pedido (px lógicos) de Control con el layout de una ventana de w × h y esa pestaña:
        (ancho, alto, ancho del cuerpo de tarjetas). Para el self-check y el tamaño por defecto."""
        self.tab_var.set(tab)
        lay = layout.pick(w, h, forced)
        self.apply_layout(lay, layout.live_rows(w, lay.dense), w)
        self.place_cards()
        self.fit_body()
        self.root.update_idletasks()  # la raíz recalcula su tamaño pedido con el Canvas ya ajustado
        s = self.scale
        return self.root.winfo_reqwidth() / s, self.root.winfo_reqheight() / s, self.body.winfo_reqwidth() / s

    def initial_geometry(self, saved):
        """geo_control guardado -> (geometría, maximizar). WxH+X+Y válido: tal cual. Solo posición (migrada
        de v5) o nada: el tamaño que pide el modo completo (al menos el mínimo de completo) si cabe en el área
        de trabajo del monitor; si no, el área de trabajo (maximizada)."""
        if outputs.GEO_RE.match(saved) and outputs.geo_ok(saved, self.mons):
            return saved, False
        p = POS_RE.match(saved)
        pos = saved if p and outputs.geo_ok("1x1" + saved, self.mons) else ""
        if saved and not pos:
            log.warning("config: geo_control=%r no es válido o cae fuera de los monitores", saved)
        tab, w, h = self.tab_var.get(), 0, 0
        for t in TABS:
            rw, rh, _ = self.measure(1366, 700, t)
            w, h = max(w, rw), max(h, rh)
        self.tab_var.set(tab)
        self.place_cards()  # las de la pestaña activa (measure dejó las de la última medida)
        w, h = self.px(max(w, layout.MEDIUM_W)), self.px(max(h, layout.COMPACT_H))
        x, y = (int(p[1].lstrip("+")), int(p[2].lstrip("+"))) if pos else (0, 0)  # "+-8" -> -8
        wa = win32.work_area(x + 40, y + 10)
        fw, fh = (self.px(v) for v in FRAME_EXTRA)
        if wa and (w + fw > wa[2] or h + fh > wa[3]):
            return f"{wa[2] - fw}x{wa[3] - fh}" + (pos or f"+{wa[0]}+{wa[1]}"), True
        return f"{w}x{h}{pos}", False

    def set_vista(self, v):
        """Vista guardada (ui.vista): auto (por tamaño) | compacto | mini. Inválida -> auto. Solo fija la vista
        y recoloca; entrar y salir de Mini con su geometría es enter_mini / leave_mini."""
        if v not in layout.FORCED:
            log.warning("config: ui.vista=%r no es válida; se usa 'auto'", v)
            v = "auto"
        self.vista = v
        if v != "mini":
            self.vista_prev = v
        self.vista_cb.set(VISTAS[v])
        if self.layout is not None and self.root.winfo_viewable():
            self.relayout(force=True)

    def choose_vista(self, v):
        """Selector Vista: Mini entra a Mini a mano; Automática o Compacta salen de Mini si hace falta."""
        if v == "mini":
            self.enter_mini()
        elif self.vista == "mini":
            self.leave_mini(v)
        else:
            self.set_vista(v)

    # --- vista Mini (fases/diseno-ui.md §3.3 y §3.5)
    def win_center(self, geo=None):
        """Centro (px físicos) de una geometría 'WxH+X+Y' o, sin ella, de la ventana."""
        g = outputs.GEO_RE.match(geo or "")
        if g:
            return int(g[3][1:]) + int(g[1]) // 2, int(g[4][1:]) + int(g[2]) // 2
        r = self.root
        return r.winfo_rootx() + r.winfo_width() // 2, r.winfo_rooty() + r.winfo_height() // 2

    def mini_geometry(self, ref=None):
        """ui.geo_mini si es válida en los monitores actuales; si no, la tira (800 × 80 lógicos de contenido)
        arriba a la derecha del área de trabajo del monitor donde está Control (ref: su geometría)."""
        g = self.geo_mini
        if outputs.GEO_RE.match(g) and outputs.geo_ok(g, win32.monitors()):
            return g
        if g:
            log.warning("config: ui.geo_mini=%r no es válida o cae fuera de los monitores", g)
        w, h = (self.px(v) for v in MINI_SIZE)
        wa = win32.work_area(*self.win_center(ref)) or (0, 0, w, h)
        return f"{w}x{h}+{wa[0] + wa[2] - w - self.px(FRAME_EXTRA[0])}+{wa[1]}"

    def cur_geo(self):
        """Geometría actual. Sin ventana (headless) Tk no aplica el tamaño a una ventana que nunca se mapeó:
        vale la última pedida."""
        return self.geo_req if self.headless and self.geo_req else self.root.geometry()

    def fit_geometry(self, geo):
        """Pone la geometría y recoloca ya con su tamaño (sin esperar al Configure; también sin ventana), sin
        histéresis: al volver de Mini el layout es el mismo que antes de entrar."""
        self.geo_req = geo
        self.root.geometry(geo)
        g = re.match(r"^(\d+)x(\d+)", geo)
        self.layout = self.live_n = None
        self.relayout(int(g[1]) / self.scale, int(g[2]) / self.scale, force=True)
        if not self.headless:  # aplicada ya: -topmost (SetWindowPos) antes del idle conservaría la posición vieja
            self.root.update_idletasks()

    def default_geometry(self):
        """Tamaño por defecto de F8 (el que pide completo) en el monitor de la ventana, lo más cerca posible de
        donde estaba sin salirse de su área de trabajo."""
        wa = win32.work_area(*self.win_center())
        geo, zoom = self.initial_geometry(f"+{wa[0]}+{wa[1]}" if wa else "")
        g = outputs.GEO_RE.match(geo)
        if g and not zoom:
            w, h = int(g[1]), int(g[2])
            fw, fh = (self.px(v) for v in FRAME_EXTRA)
            x = min(max(self.root.winfo_rootx(), wa[0]), wa[0] + wa[2] - w - fw)
            y = min(max(self.root.winfo_rooty(), wa[1]), wa[1] + wa[3] - h - fh)
            geo = f"{w}x{h}+{x}+{y}"
        return geo, zoom

    def mini_size(self, geo):
        """¿Una ventana de esa geometría se dibujaría como mini (con la vista actual)?"""
        g = re.match(r"^(\d+)x(\d+)", geo)
        return layout.pick(int(g[1]) / self.scale, int(g[2]) / self.scale, self.vista).mode == "mini"

    def enter_mini(self):
        """Mini a mano (Vista → Mini o F9): guarda la geometría normal, toma ui.geo_mini (o la tira por
        defecto) y, con "Siempre encima" activo, se fija encima."""
        if self.vista == "mini":
            return
        root, ref = self.root, self.cur_geo()
        if self.draw is None or self.draw.mode != "mini":  # ventana normal: a esta geometría se vuelve
            self.geo_normal = (ref, root.state() == "zoomed")
        if self.geo_normal:
            self.geo["geo_control"] = self.geo_normal[0]
        if root.state() == "zoomed":
            root.state("normal")
        self.vista_prev, self.vista = self.vista, "mini"
        self.vista_cb.set(VISTAS["mini"])
        self.fit_geometry(self.mini_geometry(ref))
        self.mini_window(True)
        log.info("vista Mini: %s (siempre encima: %s)", self.geo_req, self.topmost)

    def leave_mini(self, vista=None):
        """Sale de Mini (Ampliar, F9 o Vista), también si entró sola por tamaño: guarda ui.geo_mini, vuelve a
        la última geometría normal (o al tamaño por defecto) y deja de estar encima. Nunca "no hace nada"."""
        root = self.root
        if self.vista == "mini":
            if root.state() != "zoomed":
                self.geo_mini = self.cur_geo()
            self.vista = vista or self.vista_prev
        elif vista:
            self.vista = vista
        self.vista_cb.set(VISTAS[self.vista])
        self.mini_window(False)
        geo, zoom = self.geo_normal or ("", False)
        if not (outputs.GEO_RE.match(geo) and outputs.geo_ok(geo, win32.monitors()) and not self.mini_size(geo)):
            geo, zoom = self.default_geometry()
        if root.state() == "zoomed":
            root.state("normal")
        self.fit_geometry(geo)
        if zoom and not self.headless:
            root.state("zoomed")
        self.geo["geo_control"] = geo
        log.info("sale de Mini: vista %s, %s", self.vista, geo)

    def ampliar(self):
        """Botón Ampliar: sale de Mini; con "No quitar el teclado" además trae LightHouse al frente."""
        noact = self.noact
        self.leave_mini()
        if noact and not self.headless:
            self.to_front()

    def toggle_mini(self):
        """Tecla F9: alterna Mini ↔ vista anterior. Si se ve como mini (aunque haya entrado sola), sale."""
        if self.draw is not None and self.draw.mode == "mini":
            self.ampliar()
        else:
            self.enter_mini()

    def set_mini_top(self):
        """Interruptor Siempre encima (ui.mini_encima): si la ventana está en Mini, se aplica ya."""
        if self.draw is not None and self.draw.mode == "mini":
            self.mini_window(True)

    def mini_window(self, on):
        """on (en Mini): siempre encima y "No quitar el teclado" según sus opciones. off: se quitan siempre."""
        top = on and self.mini_top.get()
        if top != self.topmost:  # -topmost la pone arriba de todo, también de una salida a pantalla completa
            self.topmost = top
            self.root.attributes("-topmost", top)
        no = on and self.mini_nofocus.get()
        if no != self.noact:
            self.noact = no
            if not self.headless:
                win32.set_no_activate(int(self.root.wm_frame(), 16), no)

    # --- teclado y foco
    def set_tab_nav(self):
        """Navegar con Tab: los controles registrados toman el foco (contorno focus); apagado, ninguno
        (Espacio = Blackout no debe activar el botón enfocado)."""
        on = self.tab_nav.get()
        for w in self.ids:
            try:
                if w.winfo_class() in FOCUSABLE and not self.tut.owns(w):  # el globo del tutorial nunca toma foco
                    w.configure(takefocus=1 if on else 0)
            except self.tk.TclError:  # p. ej. el botón de Calibrar, ya cerrado
                pass
        if not on:
            self.nav_focus = False
            self.root.focus_set()

    def on_focus_in(self, e):
        w = e.widget
        self.nav_focus = bool(self.tab_nav.get()) and w is not self.root and w in self.ids
        if self.nav_focus:  # el tooltip del control enfocado (se oculta con Esc o al mover el foco)
            self.tip.focus(w)
        if self.nav_focus and self.inside(w, self.body):  # que el control enfocado quede a la vista
            y, h, top = w.winfo_rooty() - self.body.winfo_rooty(), w.winfo_height(), self.body_cv.canvasy(0)
            view, total = self.body_cv.winfo_height(), max(self.body.winfo_height(), 1)
            if y < top or y + h > top + view:
                self.body_cv.yview_moveto(max(y - self.sp("md"), 0) / total)

    def to_front(self, _=None):
        """Clic en el aviso Teclas: trae LightHouse al frente (las teclas pasan a activas); no cambia nada más."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def set_bump_mouse(self, on):
        """Botón Bump: mantener = bump (como la tecla F); se suelta también si la ventana pierde el foco."""
        self.bump_mouse = on
        self.scene.bump = on or self.key_bump

    def set_mode(self):
        m = self.mode.get()
        self.eng.mode = m
        if m in MODES:
            self.mode_cb.current(MODES.index(m))

    # --- widgets
    def slider(self, fr, wid, label, attr, lo, hi, k=1.0, res=1, fn=None, init=None, key=None):
        tk = self.tk
        fn = fn or (lambda val: attr and setattr(self.eng, attr, val))
        var = tk.DoubleVar(value=round(getattr(self.eng, attr) / k, 3) if init is None else init)
        row = self.ttk.Frame(fr)
        row.pack(fill="x")
        self.ttk.Label(row, text=label, width=LABEL_W, wraplength=self.label_px).pack(
            side="left", anchor="s", pady=(0, self.sp("sm")))
        sc = self.reg(tk.Scale(row, from_=lo, to=hi, resolution=res, orient="horizontal", variable=var,
                               length=self.px(SLIDER_W), takefocus=0, command=lambda v: fn(float(v) * k)), wid)
        self.style_scale(sc)
        sc.pack(side="left", fill="x", expand=True)
        self.vars[key or attr or label] = (var, k, fn, lo, hi)
        self.scales[key or attr or label] = sc
        return var

    def check(self, fr, wid, label, attr):
        var = self.tk.BooleanVar(value=getattr(self.eng, attr))
        cb = self.reg(self.ttk.Checkbutton(fr, text=label, variable=var, takefocus=0,
                                           command=lambda: setattr(self.eng, attr, var.get())), wid)
        cb.pack(anchor="w", pady=(self.sp("sm"), 0))
        self.checks[attr] = var
        return cb

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

    def show_photo(self):
        """Aviso de fotosensibilidad: visible mientras "Limitar destellos" está apagado."""
        if self.checks["flash_limit"].get():
            self.photo.pack_forget()
        else:
            self.photo.pack(anchor="w", after=self.limit_cb, pady=(self.sp("xs"), 0))

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
        dense, mini = bool(self.draw and self.draw.dense), bool(self.draw and self.draw.mode == "mini")
        for lid, b in self.look_btns.items():
            b.config(text=self.look_text(lid, dense, mini))
        for lb, part in self.key_cols:  # tabla de atajos (pestaña Ayuda), del mapa real
            lb.config(text="\n".join(" · ".join(key_label(n) for n in self.keys[a]) for a in part))

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
            white, black = (hexrgb(c) for c in (scene.WHITE, scene.BLACK))
            segs = ([white] if kind == "base" else [black] if kind == "black" else
                    [black, cols[0]] if kind == "split" else cols)
            sw.bind("<Configure>", lambda e, sw=sw, segs=segs: self.draw_swatch(sw, segs))
            self.draw_swatch(sw, segs)

    def draw_swatch(self, sw, segs):
        sw.delete("all")  # los colores de la muestra son datos del show: no pasan por theme.paint
        w, h = sw.winfo_width(), self.px(SWATCH_H + 1)
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
        elif act == "mini":
            self.toggle_mini()

    def poll_keys(self):
        """Teclas por GetAsyncKeyState: llegan aunque el foco de Tk esté en otra ventana de la app.
        Acción al presionar (flanco); el bump, mientras está presionada. Decide keys_live(): nada con Ctrl
        o Alt, escribiendo o con foco en un control; sin "Teclas globales", solo con LightHouse al frente."""
        if not keys_live(win32.app_in_foreground(), self.keys_global, self.typing, self.nav_focus,
                         win32.key_down(win32.VK_CONTROL), win32.key_down(win32.VK_MENU)):
            self.held, self.key_bump = None, False
            self.scene.bump = self.bump_mouse
            return
        down = {vk for vk in self.vk_actions if win32.key_down(vk)}
        if self.held is not None:  # None: recién recuperado el permiso, solo se toma referencia
            for vk in down - self.held:
                self.skip_intro()  # una tecla de show quita la intro y además hace su acción
                for act in self.vk_actions[vk]:
                    self.key_action(act)
        self.held = down
        self.key_bump = any(vk in down for vk in self.bump_vks)
        self.scene.bump = self.key_bump or self.bump_mouse

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
        row = self.ttk.Frame(fr)
        row.pack(fill="x")
        self.ttk.Label(row, text=label, width=LABEL_W, wraplength=self.label_px).pack(
            side="left", anchor="s", pady=(0, self.sp("sm")))
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
            for w, on in ((self.loc_fr, not o.remote), (self.rem_fr, o.remote), (self.logo_row, not o.remote),
                          (self.port_row, o.remote)):
                w.pack(fill="x", pady=self.sp("xs") if w in (self.logo_row, self.port_row) else 0) if on \
                    else w.pack_forget()
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
        if self.adv_dirty:
            self.update_dots(self.snap if hasattr(self, "snap") else self.defaults)

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
        w.title("LightHouse · Calibrar sincronía")
        w.protocol("WM_DELETE_WINDOW", self.calib_exit)
        theme.window(w)  # fondo y barra de título del tema
        fr = ttk.Frame(w, padding=self.sp("lg"), style="Bg.TFrame")
        fr.pack(fill="both", expand=True)
        ttk.Label(fr, text=CALIB_TEXT, wraplength=self.px(440), style="Bg.TLabel").pack(anchor="w")
        ttk.Label(fr, text=CALIB_WHERE, wraplength=self.px(440), style="BgMuted.TLabel").pack(
            anchor="w", pady=(self.sp("md"), 0))
        self.reg(ttk.Button(fr, text="Salir", command=self.calib_exit, takefocus=1 if self.tab_nav.get() else 0),
                 "calib.salir").pack(anchor="e", pady=(self.sp("md"), 0))
        self.tip.watch(w)
        self.tip.attach_all()
        log.info("calibración de sincronía: inicio")

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
        log.info("calibración de sincronía: fin (offset %.0f ms; retardos %s)", self.eng.offset * 1000,
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
                 outputs=[o.snapshot() for o in self.outputs],
                 ui={"theme": self.theme_name, "vista": self.vista, "tab": self.tab_var.get(),
                     "avanzado": dict(self.adv_open), "tab_nav": self.tab_nav.get(), "tips": self.tips_on.get(),
                     "tutorial": self.tut_state, "intro": self.intro_var.get()})
        if self.root.winfo_viewable():  # en Mini (a mano) la ventana es la mini; geo_control, la normal
            if self.vista != "mini":
                self.geo["geo_control"] = self.root.geometry()
            elif self.root.state() != "zoomed":
                self.geo_mini = self.root.geometry()
        s["ui"].update(geo_mini=self.geo_mini, mini_encima=self.mini_top.get(),
                       mini_sin_foco=self.mini_nofocus.get())
        s.update(self.geo)
        return s

    def apply(self, c):
        """Aplica un dict de config (ya con tipos válidos) a widgets y motor. La geometría la decide
        initial_geometry() al arrancar."""
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
        self.apply_ui(c["ui"])
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
        self.show_photo()
        self.set_outputs(c["outputs"])

    def apply_ui(self, u):
        """Preferencias de interfaz (ui): vista, pestaña, "Avanzado" abiertos, Navegar con Tab y las del mini
        (geometría, siempre encima, no quitar el teclado; se aplican al entrar a Mini)."""
        self.geo_mini = u["geo_mini"]
        self.mini_top.set(u["mini_encima"])
        self.mini_nofocus.set(u["mini_sin_foco"])
        self.set_vista(u["vista"])
        if u["tab"] not in TABS:
            log.warning("config: ui.tab=%r no es válida; se usa 'show'", u["tab"])
        self.tab_var.set(u["tab"] if u["tab"] in TABS else "show")
        for cid in self.adv:
            self.set_adv(cid, u["avanzado"].get(cid, False))
        self.tab_nav.set(u["tab_nav"])
        self.tips_on.set(u["tips"])
        self.intro_var.set(u["intro"])
        if u["tutorial"] not in TUTORIAL:
            log.warning("config: ui.tutorial=%r no es válida; se usa 'preguntar'", u["tutorial"])
        self.set_tutorial(u["tutorial"] if u["tutorial"] in TUTORIAL else "preguntar")
        if self.draw:
            self.show_tab()

    def set_theme(self, name):
        """Aplica un tema (ui.theme o el selector) a toda la ventana; uno desconocido cae al por defecto con
        aviso. Al arrancar corre antes de mostrar la ventana: sin destello del tema anterior."""
        if not isinstance(name, str) or name not in theme.THEMES:
            log.warning("config: ui.theme=%r no es un tema conocido; se usa %r", name, theme.DEFAULT)
            name = theme.DEFAULT
        if theme.current() != theme.get(name):
            theme.apply(self.root, name)
        self.theme_name = name
        self.theme_cb.set(theme.get(name)["label"])
        self.note_set(self.theme_note, GLASS_NOTE if theme.opaque_fallback() else "")

    def choose_theme(self, name):
        """Selector Ayuda → Tema: vista previa inmediata (sin confirmar ni reiniciar); se guarda con la config."""
        t0 = time.perf_counter()
        self.set_theme(name)
        self.t_theme = (time.perf_counter() - t0) * 1000
        log.info("tema: %s (%.0f ms)", self.theme_name, self.t_theme)

    def update_alpha(self, _=None):
        """Glass: opaca con el puntero dentro de Control o con el tutorial activo; translúcida al salir. Por
        eventos (<Enter>/<Leave> de la raíz): un <Leave> hacia un hijo no cuenta, se mira dónde está el puntero."""
        self.ptr_in = self.pointer_inside()
        theme.set_hover(self.root, self.ptr_in or self.tut.on)

    def pointer_inside(self):
        """¿El puntero está sobre Control (o sobre la lista abierta de una de sus listas desplegables)?"""
        call = self.root.tk.call
        try:
            x, y = self.root.winfo_pointerxy()
            w = call("winfo", "containing", x, y)
            if not w:
                return False
            top = str(call("winfo", "toplevel", w))
            return top == str(self.root) or call("winfo", "class", top) == "ComboboxPopdown"
        except self.tk.TclError:
            return False

    def save(self):
        try:
            config.save(self.snapshot())
        except Exception:
            log.exception("no se pudo guardar la config")

    def autosave(self):
        # ponytail: debounce por sondeo a 2 Hz (compara snapshots); si hiciera falta, engancharlo a cada widget
        if self.calib:  # los valores de calibración son temporales: no se guardan
            self.jobs["autosave"] = self.root.after(500, self.autosave)
            return
        now = time.perf_counter()
        s = self.snapshot()
        if s != self.snap:
            self.snap, self.dirty_t = s, now
            self.update_dots(s)
        elif self.dirty_t and now - self.dirty_t >= 1.0 and s != self.saved:
            self.save()
            self.saved, self.dirty_t = s, None
        self.jobs["autosave"] = self.root.after(500, self.autosave)

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

    def set_status(self, text, alarm=""):
        """Estado del audio (tarjeta Fuente de audio) y su aviso corto en la franja En vivo."""
        self.status.config(text=text)
        self.alarm = alarm

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
            self.set_status("Sin dispositivos de audio", "SIN AUDIO")
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
            self.set_status(f"{sr} Hz · {ch} canales")
        except Exception as ex:
            self.set_status(f"Error: {ex}" + (f". {MIC_HINT}" if self.audio.is_input(i) else ""), "ERROR DE AUDIO")

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
            self.set_status(f"Reconectando… (no está: {name})", "SIN AUDIO")

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
        for i, o in enumerate(self.outputs):
            f = compose_output(e.sample(o.delay_ms * 0.001), sc, cfg, o.join, o.master * 0.01, o.content == LOGO)
            o.render(f, now)
            if i == 0:
                self.preview = f  # vista previa de la Salida 1: la pinta slow()

    def slow(self):
        """Loop lento (~30 Hz): watchdog de silencio, reconexión, medidores, labels e indicadores."""
        global LAST_ERROR
        self.jobs["slow"] = self.root.after(33, self.slow)  # primero: una excepción no detiene el loop
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
                self.set_status("Sin audio: reconectando…", "SIN AUDIO")
            if now - self.retry_t >= RETRY_S:
                self.retry()
                alive = self.audio.alive()
        self.was_alive = alive
        if LAST_ERROR:
            self.set_status(LAST_ERROR, "ERROR")
            LAST_ERROR = None
        e, put, sc, chip = self.eng, self.put, self.scene, self.chip_set
        self.cfg = Cfg(master=e.vmax, gamma=e.gamma, base=tuple(self.base_rgbs()), colors=self.cfg.colors)
        self.fast()  # sin bloques (loopback en silencio, sin stream) también se pinta
        if self.intro is not None:
            self.tick_intro(now)
        w, y = self.mw, self.my
        put(self.meter.coords, self.bar_l, 0, y[0], round(w * min(e.lb, 1)), y[1])
        put(self.meter.coords, self.bar_o, 0, y[2], round(w * min(e.o_disp, 1)), y[3])
        x = round(w * min(e.thresh, 1))
        put(self.meter.coords, self.line, x, y[4], x, y[5])
        put(self.dot.itemconfig, self.dot_id, fill=theme.tok("beat_on" if e.t - e.last_beat < 0.1 else "beat_off"))
        dense, mini = self.draw.dense, self.draw.mode == "mini"
        unit = "" if mini else " BPM"  # en Mini, solo el número
        if e.sync == "tempo" and e.bpm_src == "manual":
            put(self.bpm.config, text=f"{e.bpm_manual:.0f}" + ("" if mini else " BPM" + BPM_MANUAL[dense]))
        else:
            put(self.bpm.config, text=(f"{e.bpm:.0f}" if e.bpm and e.t - e.last_beat < 2 else "--") + unit)
        st = ("BLACKOUT" if sc.blackout else "BUMP" if sc.bump else e.mode.upper() if e.mode != "auto" else
              AUTO_PREFIX + ("TRANQUILO" if e.calm else "PULSO"))
        put(self.state.config, text=state_text(st, dense, mini))
        put(self.look_lbl.config, text=f"Look {self.keys[sc.look][0]} · {LOOKS[sc.look][0]}")
        self.note_set(self.lead, "" if e.offset >= 0 else "anticipación activa" if e.lead() else
                      "anticipación inactiva (requiere Al ritmo)" if e.sync != "tempo" else
                      "anticipación inactiva (esperando BPM fiable)")  # al final de la parte básica
        f = self.preview
        if f:  # vista previa: lo mismo que la Salida 1 (≤ 2 configure por tick, solo si cambió)
            for half, rgb in zip(self.prev_lr, f[:2]):
                put(half.configure, bg=hexrgb(rgb))
        if self.shown.get("bump") != sc.bump:
            self.shown["bump"] = sc.bump
            self.style_bump(sc.bump)
        chip(self.keys_chip, *keys_chip(win32.app_in_foreground(), self.keys_global, self.typing or self.nav_focus))
        chip(self.no_sig, "SIN SEÑAL" if alive and e.t - e.last_sound > NO_SIGNAL_S else "")
        chip(self.clip, "SATURA" if now - self.audio.clip_t < CLIP_S else "")
        chip(self.audio_chip, self.alarm)
        rem = [o.status() for o in self.outputs if o.remote]
        off = any(s == "sin red" for s in rem)
        chip(self.net_chip, ("TV: sin red" if off else "TV: enviando") if rem else "", "warn" if off else "ok")
        warned = [str(n) for n, o in enumerate(self.outputs, 1) if o.warn or o.logo_err]
        chip(self.warn_chip, f"Aviso: salida {', '.join(warned)}" if warned else "")  # el detalle, en Salidas
        self.note_set(self.net_lbl, "\n".join(f"{o.name}: {o.status()}" for o in self.outputs if o.remote))
        self.note_set(self.out_warn, "\n".join(
            w for o in self.outputs for w in (f"{o.name}: {o.warn}" if o.warn else "", o.logo_err) if w))
        if self.tut.on:
            self.tut.tick()

    def tick_intro(self, now):
        """La intro avanza desde aquí (sin timer propio); si algo falla, se quita y la app sigue sin ella."""
        try:
            self.intro.tick(now)
        except Exception:
            log.warning("intro: falló; se quita", exc_info=True)
            self.intro.close()

    def start_intro(self, w, h):
        """Crea la intro sobre Control (ventana de w×h px). Sin intro si falta algo, no cabe o no se puede crear."""
        m = intro.load(intro.resource_path("assets", "intro", "intro.json"))
        if m is None:
            return
        z = intro.zoom_for(self.scale)
        if w < m.lienzo[0] * z or h < m.lienzo[1] * z:
            log.info("intro: la ventana es más chica que el lienzo; sin intro")
            return
        try:
            intro.Intro(self, m, {"app": APP_NAME, "version": VERSION, "autor": __author__})
        except Exception:
            log.warning("intro: no se pudo crear; sin intro", exc_info=True)

    def skip_intro(self, _=None):
        if self.intro is not None:
            self.intro.skip()

    def put(self, fn, *args, **kw):
        """fn(*args, **kw) solo si cambió desde la última vez: cada config/coords hace redibujar a Tk."""
        key = (fn.__self__, fn.__name__, args[:1])
        if self.shown.get(key) != (args, kw):
            self.shown[key] = (args, kw)
            fn(*args, **kw)

    def quit(self):
        for job in self.jobs.values():
            self.root.after_cancel(job)
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
