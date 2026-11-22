"""Tokens de apariencia de la ventana Control, tema por defecto y su aplicación a Tk/ttk.

Puro al importarlo (sin crear Tk ni cargar ctypes). Todo color, fuente y medida de la interfaz sale de aquí:
  - los estilos ttk los define apply();
  - los widgets tk clásicos y los ítems de Canvas se colorean con paint(), que recuerda opción -> token
    para que apply() vuelva a pintarlos al cambiar de tema;
  - los colores que se deciden en cada tick se leen con tok() del tema vigente.
Quedan fuera (datos del show, no apariencia): scene.py, outputs.py, pantalla.py, PALETTE y KELVIN."""
import logging
import re

log = logging.getLogger(__name__)

DEFAULT = "oscuro"
FAMILY = "Segoe UI"
# Oscuro neutro con acento ámbar (la lámpara del faro). Valores y contrastes: fases/diseno-ui.md §9.3
OSCURO = {
    "label": "Oscuro",
    # superficies
    "bg": "#14161A", "surface": "#1D2026", "surface_alt": "#272B33", "hover": "#313743", "trough": "#0E1013",
    "border": "#3A404B", "border_strong": "#7A8496",
    # texto
    "fg": "#ECEFF4", "fg_muted": "#A7B0BD", "fg_disabled": "#808997",
    # acento y estado
    "accent": "#FFC53D", "accent_fg": "#14161A", "focus": "#5CC8FF", "danger": "#D7263D", "danger_fg": "#FFFFFF",
    "danger_text": "#FF6B6B", "warn": "#FF9F1C", "ok": "#4CD97B",
    # en vivo
    "live_fg": "#ECEFF4", "meter_level": "#7A8496", "meter_hit": "#ECEFF4", "meter_threshold": "#FF6B6B",
    "beat_on": "#FFFFFF", "beat_off": "#313743",
    # ayudas
    "tooltip_bg": "#F4F1E8", "tooltip_fg": "#14161A", "tooltip_border": "#7A8496", "tutorial_ring": "#FFC53D",
    "intro_bg": "#000000", "intro_fg": "#FFFFFF",
    # tipografía: (familia, puntos, peso)
    "font.family": FAMILY, "font.body": (FAMILY, 10, "normal"), "font.small": (FAMILY, 9, "normal"),
    "font.title": (FAMILY, 10, "bold"), "font.big": (FAMILY, 18, "bold"), "font.look": (FAMILY, 9, "bold"),
    "font.intro": (FAMILY, 28, "bold"),
    # espaciado, radio y tamaños (px lógicos: pasan por px())
    "space.xs": 2, "space.sm": 4, "space.md": 8, "space.lg": 12, "space.xl": 16,
    "radius.sm": 3, "radius.md": 6,
    "size.look_w": 60, "size.look_h": 44, "size.look_w_dense": 44, "size.look_h_dense": 32,
    "size.blackout_w": 96, "size.control_h": 28, "size.card_min_w": 340, "size.tip_max_w": 320,
    "size.tut_ring": 3, "size.tut_margin": 3, "size.tut_gap": 8, "size.tut_wrap": 300,  # anillo, hueco y globo
    # ventana
    "window.alpha": 1.0, "window.alpha_hover": 1.0, "window.dark_titlebar": True,
    "window.caption": "#14161A", "window.caption_fg": "#ECEFF4", "ttk.base": "clam",
    # tiempos (ms)
    "motion.tip_delay": 500, "motion.tip_delay_next": 100, "motion.layout_debounce": 120,
}
# los otros tres temas (fases/diseno-ui.md §13.2): solo lo que cambia; tipografía, medidas y tiempos, los de oscuro
VAPORWAVE = {
    "base": "oscuro", "label": "Vaporwave",
    "bg": "#1A1033", "surface": "#24174A", "surface_alt": "#31205F", "hover": "#40297A", "trough": "#100A22",
    "border": "#4A3580", "border_strong": "#A592E0",
    "fg": "#F6EEFF", "fg_muted": "#CDBFEE", "fg_disabled": "#A294CC",
    "accent": "#FF71CE", "accent_fg": "#1A1033", "focus": "#01CDFE", "danger": "#D6246E", "danger_fg": "#FFFFFF",
    "danger_text": "#FF9BB0", "warn": "#FFE66D", "ok": "#05FFA1",
    "live_fg": "#01CDFE", "meter_level": "#B967FF", "meter_hit": "#01CDFE", "meter_threshold": "#FF71CE",
    "beat_on": "#FF71CE", "beat_off": "#40297A",
    "tooltip_bg": "#FFF0FA", "tooltip_fg": "#1A1033", "tooltip_border": "#FF71CE", "tutorial_ring": "#01CDFE",
    "intro_bg": "#0D0221", "intro_fg": "#FFFFFF",
    "window.alpha": 1.0, "window.alpha_hover": 1.0, "window.dark_titlebar": True,
    "window.caption": "#1A1033", "window.caption_fg": "#F6EEFF",
}
GLASS = {  # ventana translúcida (-alpha de toda la ventana Control, §13.4); opaca con el puntero dentro
    "base": "oscuro", "label": "Glass (transparente)",
    "bg": "#0B1016", "surface": "#121922", "surface_alt": "#1A232E", "hover": "#25313F", "trough": "#06090D",
    "border": "#34414F", "border_strong": "#9AABBD",
    "fg": "#F4F8FB", "fg_muted": "#C3CEDA", "fg_disabled": "#9CAAB9",
    "accent": "#9FE8FF", "accent_fg": "#0B1016", "focus": "#FFD166", "danger": "#FF5C6C", "danger_fg": "#0B1016",
    "danger_text": "#FF9A9A", "warn": "#FFC670", "ok": "#6FE89B",
    "live_fg": "#F4F8FB", "meter_level": "#9AABBD", "meter_hit": "#F4F8FB", "meter_threshold": "#FF9A9A",
    "beat_on": "#FFFFFF", "beat_off": "#25313F",
    "tooltip_bg": "#F4F8FB", "tooltip_fg": "#0B1016", "tooltip_border": "#9AABBD", "tutorial_ring": "#FFD166",
    "intro_bg": "#000000", "intro_fg": "#FFFFFF",
    "window.alpha": 0.92, "window.alpha_hover": 1.0, "window.dark_titlebar": True,
    "window.caption": "#0B1016", "window.caption_fg": "#F4F8FB",
}
BLUE_OCEAN = {
    "base": "oscuro", "label": "Blue Ocean",
    "bg": "#071A2B", "surface": "#0C2438", "surface_alt": "#123049", "hover": "#1A405F", "trough": "#04111D",
    "border": "#23506F", "border_strong": "#6FA3C7",
    "fg": "#EAF6FF", "fg_muted": "#A5C4DA", "fg_disabled": "#7B9BB3",
    "accent": "#2EC4F1", "accent_fg": "#04111D", "focus": "#FFD166", "danger": "#D12F45", "danger_fg": "#FFFFFF",
    "danger_text": "#FF8A80", "warn": "#FFC857", "ok": "#3DDC97",
    "live_fg": "#7FE7FF", "meter_level": "#6FA3C7", "meter_hit": "#EAF6FF", "meter_threshold": "#FF8A80",
    "beat_on": "#7FE7FF", "beat_off": "#1A405F",
    "tooltip_bg": "#EAF6FF", "tooltip_fg": "#071A2B", "tooltip_border": "#6FA3C7", "tutorial_ring": "#FFC857",
    "intro_bg": "#020B14", "intro_fg": "#EAF6FF",
    "window.alpha": 1.0, "window.alpha_hover": 1.0, "window.dark_titlebar": True,
    "window.caption": "#071A2B", "window.caption_fg": "#EAF6FF",
}
THEMES = {DEFAULT: OSCURO, "vaporwave": VAPORWAVE, "glass": GLASS, "blue_ocean": BLUE_OCEAN}  # nombre -> tokens
NAMES = ("oscuro", "vaporwave", "glass", "blue_ocean")  # orden del selector (texto visible: su token label)
REQUIRED = frozenset(OSCURO)
BLACK, WHITE = "#000000", "#FFFFFF"  # lo que puede haber detrás de una ventana translúcida (peor caso, §13.6)

# (texto/forma, fondo, mínimo): fases/diseno-ui.md §13.6. Texto normal >= 4,5; grande, indicadores y contornos >= 3,0
CONTRAST_PAIRS = (
    *((f, b, 4.5) for f in ("fg", "fg_muted", "danger_text", "warn", "ok", "live_fg")
      for b in ("bg", "surface", "surface_alt")),
    ("fg", "hover", 4.5), ("accent_fg", "accent", 4.5), ("danger_fg", "danger", 4.5),
    ("tooltip_fg", "tooltip_bg", 4.5), ("intro_fg", "intro_bg", 4.5), ("window.caption_fg", "window.caption", 4.5),
    *(("fg_disabled", b, 3.0) for b in ("surface", "surface_alt")),
    *((f, b, 3.0) for f in ("border_strong", "focus", "accent", "tutorial_ring", "beat_on")
      for b in ("bg", "surface", "surface_alt")),
    ("accent", "hover", 3.0), ("danger", "bg", 3.0), ("danger", "surface", 3.0), ("beat_on", "beat_off", 3.0),
    *((f, "trough", 3.0) for f in ("meter_level", "meter_hit", "meter_threshold")),
)
# ventanas que nunca son translúcidas (el tooltip es otra ventana; la barra de título la pinta Windows)
OPAQUE_PAIRS = frozenset({("tooltip_fg", "tooltip_bg"), ("window.caption_fg", "window.caption")})

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")


# --- datos (puros)
def _resolve(name, seen=()):
    t = THEMES[name]
    base = t.get("base")
    out = {}
    if base in THEMES and base not in seen + (name,):
        out = _resolve(base, seen + (name,))
    elif base:
        log.warning("tema %r: base %r desconocida o circular", name, base)
    out.update({k: v for k, v in t.items() if k != "base"})
    return out


def get(name):
    """Tema completo (con su base resuelta). Nombre desconocido -> DEFAULT, con aviso en el log."""
    if not isinstance(name, str) or name not in THEMES:
        log.warning("tema %r desconocido; se usa %r", name, DEFAULT)
        name = DEFAULT
    return _resolve(name)


def _kind(v):
    return ("color" if isinstance(v, str) and _HEX.fullmatch(v) else "font" if isinstance(v, tuple) else
            "bool" if isinstance(v, bool) else "int" if isinstance(v, int) else
            "float" if isinstance(v, float) else "str")


def validate(theme):
    """Problemas de un tema ya resuelto: llaves que faltan, que sobran o con valor mal formado ([] = válido)."""
    bad = [f"falta {k}" for k in sorted(REQUIRED - set(theme))]
    bad += [f"sobra {k}" for k in sorted(set(theme) - REQUIRED)]
    for k in sorted(REQUIRED & set(theme)):
        v, want = theme[k], _kind(OSCURO[k])
        if want == "color":
            ok = isinstance(v, str) and bool(_HEX.fullmatch(v))
        elif want == "font":
            ok = (isinstance(v, tuple) and len(v) == 3 and isinstance(v[0], str) and isinstance(v[1], int)
                  and v[2] in ("normal", "bold"))
        elif want in ("int", "float"):
            ok = isinstance(v, (int, float)) and not isinstance(v, bool)
        else:
            ok = isinstance(v, type(OSCURO[k]))
        if not ok:
            bad.append(f"{k}={v!r} mal formado")
    return bad


def px(n, scale):
    """px lógicos -> físicos (scale = winfo_fpixels('1i') / 96)."""
    return int(n * scale + 0.5)


def _lum(c):
    ch = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """Relación de contraste WCAG 2.1 entre dos colores '#RRGGBB'."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(color, behind, alpha):
    """Color que se ve de `color` con opacidad alpha sobre `behind`: alpha · color + (1 − alpha) · behind."""
    a, b = ([int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in (color, behind))
    return "#%02X%02X%02X" % tuple(round(alpha * x + (1 - alpha) * y) for x, y in zip(a, b))


def contrast_glass(fg, bg, alpha):
    """Peor caso de una ventana translúcida (§13.6): detrás de la letra y detrás del fondo puede haber blanco o
    negro, y no tiene por qué ser lo mismo."""
    return min(contrast(mix(fg, x, alpha), mix(bg, y, alpha)) for x in (BLACK, WHITE) for y in (BLACK, WHITE))


def check_contrast(theme, name=None):
    """Pares de CONTRAST_PAIRS (§13.6) bajo su mínimo, cada uno con tema, par, valor y mínimo ([] = todos cumplen).
    Con window.alpha < 1, cada par (salvo el tooltip y la barra de título) también en el peor caso."""
    name = name or theme.get("label", "?")
    alpha, bad = theme["window.alpha"], []
    for f, b, m in CONTRAST_PAIRS:
        c = contrast(theme[f], theme[b])
        if c < m:
            bad.append(f"{name}: {f} sobre {b} = {c:.2f} < {m}")
        elif alpha < 1 and (f, b) not in OPAQUE_PAIRS:
            c = contrast_glass(theme[f], theme[b], alpha)
            if c < m:
                bad.append(f"{name}: {f} sobre {b} = {c:.2f} < {m} (peor caso con opacidad {alpha:g})")
    return bad


def effective_alpha(theme, hover, transparency_ok):
    """Opacidad de Control: 1.0 sin transparencia en el equipo; con el puntero dentro (o el tutorial), la de
    hover; si no, la de reposo."""
    if not transparency_ok:
        return 1.0
    return float(theme["window.alpha_hover"] if hover else theme["window.alpha"])


# --- tema vigente y widgets pintados
_cur = get(DEFAULT)
_painted = {}    # (widget, ítem de Canvas | None) -> {opción: token}
_wins = {}       # Toplevel extra (Calibrar) -> True; apply() les pone fondo y barra de título
_listeners = []  # funciones sin argumentos que apply() llama al terminar (p. ej. vaciar cachés de put())
# opacidad de Control: puntero dentro (o tutorial) · efectos de transparencia de Windows · -alpha funciona aquí
_win = {"hover": False, "transparency": True, "alpha_ok": True}


def current():
    return _cur


def tok(token):
    """Valor del token en el tema vigente (para lo que se decide en cada tick)."""
    return _cur[token]


def on_apply(fn):
    _listeners.append(fn)


def paint(widget, item=None, **tokens):
    """Colorea un widget tk clásico (o el ítem de su Canvas) con tokens y recuerda opción -> token."""
    _painted.setdefault((widget, item), {}).update(tokens)
    _paint1(widget, item, tokens)


def _paint1(widget, item, tokens):
    vals = {opt: _cur[t] for opt, t in tokens.items()}
    if item is None:
        widget.configure(**vals)
    else:
        widget.itemconfigure(item, **vals)


def window(w):
    """Toplevel de la interfaz (Calibrar): fondo de ventana y barra de título según el tema vigente."""
    _wins[w] = True
    paint(w, bg="bg")
    _chrome(w, _cur)


def _chrome(w, t):
    """Barra de título oscura y color de título (Windows 11); nunca lanza."""
    try:
        from . import win32
        w.update_idletasks()
        hwnd = int(w.wm_frame(), 16)
        if hwnd:
            win32.set_dark_titlebar(hwnd, t["window.dark_titlebar"])
            win32.set_caption_color(hwnd, t["window.caption"], t["window.caption_fg"])
    except Exception:
        log.exception("no se pudo aplicar la barra de título")


def _styles(root, t):
    from tkinter import ttk
    s = ttk.Style(root)
    s.theme_use(t["ttk.base"])
    body, small, title, big, look = t["font.body"], t["font.small"], t["font.title"], t["font.big"], t["font.look"]
    b = dict(background=t["surface"], foreground=t["fg"], bordercolor=t["border"], darkcolor=t["surface"],
             lightcolor=t["surface"], troughcolor=t["trough"], focuscolor=t["focus"], insertcolor=t["fg"],
             fieldbackground=t["surface_alt"], selectbackground=t["accent"], selectforeground=t["accent_fg"],
             font=body)
    s.configure(".", **b)
    s.configure(".", focusthickness=2, focussolid=1)  # contorno de foco (solo con "Navegar con Tab")
    s.map(".", foreground=[("disabled", t["fg_disabled"])], background=[("disabled", t["surface"])])
    # marcos y etiquetas: por defecto sobre una tarjeta (surface); "Bg." = sobre el fondo de la ventana
    s.configure("TFrame", background=t["surface"])
    s.configure("Bg.TFrame", background=t["bg"])
    s.configure("TLabel", background=t["surface"], foreground=t["fg"])
    for name, bg, fg, font in (("Bg.TLabel", "bg", "fg", body), ("Muted.TLabel", "surface", "fg_muted", body),
                               ("Warn.TLabel", "surface", "warn", body), ("Ok.TLabel", "surface", "ok", body),
                               ("Big.TLabel", "surface", "live_fg", big), ("State.TLabel", "surface", "fg", title),
                               ("Live.TLabel", "surface", "live_fg", title),
                               ("Mini.TLabel", "surface", "live_fg", look),  # línea de estado del mini
                               ("Legend.TLabel", "bg", "fg_muted", small), ("BgWarn.TLabel", "bg", "warn", body),
                               ("BgMuted.TLabel", "bg", "fg_muted", body)):
        s.configure(name, background=t[bg], foreground=t[fg], font=font)
    s.configure("Mini.TLabel", padding=0, borderwidth=0)  # ancho = el del texto (ui.mini_state_fits, exacto)
    # tarjetas
    s.configure("TLabelframe", background=t["surface"], bordercolor=t["border"], lightcolor=t["border"],
                darkcolor=t["border"], relief="solid", borderwidth=1)
    s.configure("TLabelframe.Label", background=t["surface"], foreground=t["fg"], font=title)
    # botón
    s.configure("TButton", background=t["surface_alt"], foreground=t["fg"], bordercolor=t["border_strong"],
                lightcolor=t["surface_alt"], darkcolor=t["surface_alt"], relief="flat", anchor="center")
    s.map("TButton", background=[("disabled", t["surface"]), ("pressed", t["border_strong"]),
                                 ("active", t["hover"])],
          lightcolor=[("pressed", t["border_strong"]), ("active", t["hover"])],
          darkcolor=[("pressed", t["border_strong"]), ("active", t["hover"])],
          foreground=[("disabled", t["fg_disabled"])], bordercolor=[("disabled", t["border"])])
    # casilla y opción
    for w in ("TCheckbutton", "TRadiobutton"):
        s.configure(w, background=t["surface"], foreground=t["fg"], indicatorbackground=t["surface_alt"],
                    indicatorforeground=t["accent"], upperbordercolor=t["border_strong"],
                    lowerbordercolor=t["border_strong"], bordercolor=t["border_strong"])
        s.map(w, background=[("active", t["hover"])], foreground=[("disabled", t["fg_disabled"])],
              indicatorbackground=[("active", t["hover"]), ("disabled", t["surface"])],
              indicatorforeground=[("disabled", t["fg_disabled"])])
    # lista desplegable y campo de texto
    s.configure("TCombobox", background=t["surface_alt"], fieldbackground=t["surface_alt"], foreground=t["fg"],
                arrowcolor=t["fg"], bordercolor=t["border_strong"], lightcolor=t["surface_alt"],
                darkcolor=t["surface_alt"], insertcolor=t["fg"], selectbackground=t["surface_alt"],
                selectforeground=t["fg"])
    s.map("TCombobox", fieldbackground=[("disabled", t["surface"]), ("readonly", t["surface_alt"])],
          background=[("active", t["hover"]), ("readonly", t["surface_alt"])],
          foreground=[("disabled", t["fg_disabled"])], arrowcolor=[("disabled", t["fg_disabled"])],
          selectbackground=[("readonly", t["surface_alt"])], selectforeground=[("readonly", t["fg"])],
          bordercolor=[("focus", t["accent"])], lightcolor=[("focus", t["accent"])])
    s.configure("TEntry", fieldbackground=t["surface_alt"], foreground=t["fg"], insertcolor=t["fg"],
                bordercolor=t["border_strong"], lightcolor=t["surface_alt"], darkcolor=t["surface_alt"])
    s.map("TEntry", fieldbackground=[("disabled", t["surface"])], foreground=[("disabled", t["fg_disabled"])],
          bordercolor=[("focus", t["accent"])], lightcolor=[("focus", t["accent"])])
    # segmentos (pestañas y Modo): el subrayado de acento del seleccionado es un Frame aparte (ui.segment)
    s.configure("Seg.Toolbutton", background=t["surface"], foreground=t["fg_muted"], bordercolor=t["border"],
                lightcolor=t["surface"], darkcolor=t["surface"], padding=(10, 3), anchor="center")
    s.map("Seg.Toolbutton", background=[("selected", t["surface_alt"]), ("active", t["hover"])],
          foreground=[("selected", t["fg"]), ("active", t["fg"])],
          lightcolor=[("selected", t["surface_alt"]), ("active", t["hover"])],
          darkcolor=[("selected", t["surface_alt"]), ("active", t["hover"])])
    # "Avanzado ▸": botón con aspecto de enlace
    s.configure("Link.TButton", background=t["surface"], foreground=t["fg_muted"], bordercolor=t["surface"],
                lightcolor=t["surface"], darkcolor=t["surface"], relief="flat", padding=(0, 2), anchor="w")
    s.map("Link.TButton", background=[("active", t["surface"]), ("pressed", t["surface"])],
          foreground=[("active", t["fg"]), ("pressed", t["fg"])],
          lightcolor=[("active", t["surface"]), ("pressed", t["surface"])],
          darkcolor=[("active", t["surface"]), ("pressed", t["surface"])],
          bordercolor=[("focus", t["focus"])])
    # barra de desplazamiento del cuerpo de tarjetas
    s.configure("Vertical.TScrollbar", background=t["surface_alt"], troughcolor=t["bg"], bordercolor=t["bg"],
                lightcolor=t["surface_alt"], darkcolor=t["surface_alt"], arrowcolor=t["fg_muted"])
    s.map("Vertical.TScrollbar", background=[("active", t["hover"])], arrowcolor=[("active", t["fg"])])


def _popdowns(root, t):
    """El Toplevel de lista de cada Combobox se crea al abrirla la primera vez y ya no lee la base de opciones:
    se repinta a mano. Lo crea Tcl, no Python (winfo_children() de tkinter no lo ve): se recorre con Tcl."""
    call, split = root.tk.call, root.tk.splitlist
    opts = ("-background", t["surface_alt"], "-foreground", t["fg"], "-selectbackground", t["accent"],
            "-selectforeground", t["accent_fg"], "-font", t["font.body"])

    def walk(w):
        for c in split(call("winfo", "children", w)):
            if call("winfo", "class", c) == "TCombobox":
                lb = f"{c}.popdown.f.l"
                if call("winfo", "exists", lb):
                    call(lb, "configure", *opts)
            else:
                walk(c)
    walk(str(root))


def apply(root, theme=None):
    """ÚNICO punto que toca ttk.Style, la base de opciones, el fondo de la raíz, -alpha (effective_alpha; el
    puntero lo cambia set_hover) y la barra de título. Se puede llamar más de una vez (cambio de tema en
    caliente): vuelve a pintar todo lo registrado.
    theme = nombre, dict (puede declarar "base") o None (el vigente)."""
    global _cur
    if theme is not None:
        if isinstance(theme, str):
            t = get(theme)
        else:
            t = dict(theme)
            base = t.pop("base", None)
            t = {**(get(base) if base else {}), **t}
        bad = validate(t)
        if bad:
            log.warning("tema con problemas: %s", "; ".join(bad))
        _cur = t
    t = _cur
    root.configure(bg=t["bg"])
    _styles(root, t)
    from tkinter import font as tkfont
    body = t["font.body"]
    want = dict(family=body[0], size=body[1], weight="normal")
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        f = tkfont.nametofont(name, root=root)
        if any(f.cget(k) != v for k, v in want.items()):  # solo si cambia: reconfigurar una fuente con nombre
            f.configure(**want)                            # rehace todos los widgets y Tk no libera esa memoria
    for opt, key in (("background", "surface_alt"), ("foreground", "fg"), ("selectBackground", "accent"),
                     ("selectForeground", "accent_fg")):
        root.option_add(f"*TCombobox*Listbox.{opt}", t[key])
    root.option_add("*TCombobox*Listbox.font", body)
    _popdowns(root, t)
    for key in [k for k in _painted if not _alive(k[0])]:
        del _painted[key]
    for (w, item), tokens in list(_painted.items()):
        try:
            _paint1(w, item, tokens)
        except Exception:  # destruido entre medias
            _painted.pop((w, item), None)
    for w in [w for w in _wins if not _alive(w)]:
        del _wins[w]
    for w in (root, *_wins):
        _chrome(w, t)
    if t["window.alpha"] < 1:  # el equipo puede tener los efectos de transparencia apagados (se relee en cada cambio)
        from . import win32
        _win["transparency"] = win32.transparency_enabled()
        if not _win["transparency"]:
            log.info("efectos de transparencia de Windows desactivados: %s se muestra opaco", t["label"])
    _alpha(root)
    for fn in _listeners:
        fn()


def _alpha(root):
    """-alpha de Control según el tema vigente, el puntero y la transparencia del equipo (solo Control: nunca
    las salidas ni el tooltip). Si no se aplica (lanza o al leerlo no es el pedido), queda opaca para siempre."""
    a = effective_alpha(_cur, _win["hover"], _win["transparency"] and _win["alpha_ok"])
    try:
        root.attributes("-alpha", a)
        got = float(root.attributes("-alpha"))
    except Exception:
        got = None
    if got is None or abs(got - a) > 0.005:
        log.warning("-alpha %.2f no se aplicó (leído: %s); la ventana queda opaca", a, got)
        _win["alpha_ok"] = False
        try:
            root.attributes("-alpha", 1.0)
        except Exception:
            pass


def set_hover(root, on):
    """Puntero dentro de Control o tutorial activo (on): opacidad de hover; si no, la de reposo. Por eventos."""
    if _win["hover"] != bool(on):
        _win["hover"] = bool(on)
        if _cur["window.alpha"] != _cur["window.alpha_hover"]:
            _alpha(root)


def opaque_fallback():
    """¿El tema vigente pide transparencia y este equipo la muestra opaca? (nota bajo el selector)."""
    return _cur["window.alpha"] < 1 and not (_win["transparency"] and _win["alpha_ok"])


def _alive(w):
    try:
        return bool(w.winfo_exists())
    except Exception:
        return False
