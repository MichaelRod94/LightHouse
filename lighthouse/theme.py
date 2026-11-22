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
    # ventana
    "window.alpha": 1.0, "window.alpha_hover": 1.0, "window.dark_titlebar": True,
    "window.caption": "#14161A", "window.caption_fg": "#ECEFF4", "ttk.base": "clam",
    # tiempos (ms)
    "motion.tip_delay": 500, "motion.tip_delay_next": 100, "motion.layout_debounce": 120,
}
THEMES = {DEFAULT: OSCURO}  # agregar un tema = agregar una entrada (puede declarar "base": "<otro>")
REQUIRED = frozenset(OSCURO)

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


def contrast_failures(theme, name="?"):
    """Pares de CONTRAST_PAIRS que no llegan a su mínimo, con el nombre del tema ([] = todos cumplen)."""
    return [f"{name}: {f} sobre {b} = {contrast(theme[f], theme[b]):.2f} < {m}"
            for f, b, m in CONTRAST_PAIRS if contrast(theme[f], theme[b]) < m]


# --- tema vigente y widgets pintados
_cur = get(DEFAULT)
_painted = {}    # (widget, ítem de Canvas | None) -> {opción: token}
_wins = {}       # Toplevel extra (Calibrar) -> True; apply() les pone fondo y barra de título
_listeners = []  # funciones sin argumentos que apply() llama al terminar (p. ej. vaciar cachés de put())


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
    body, small, title, big = t["font.body"], t["font.small"], t["font.title"], t["font.big"]
    b = dict(background=t["surface"], foreground=t["fg"], bordercolor=t["border"], darkcolor=t["surface"],
             lightcolor=t["surface"], troughcolor=t["trough"], focuscolor=t["focus"], insertcolor=t["fg"],
             fieldbackground=t["surface_alt"], selectbackground=t["accent"], selectforeground=t["accent_fg"],
             font=body)
    s.configure(".", **b)
    s.map(".", foreground=[("disabled", t["fg_disabled"])], background=[("disabled", t["surface"])])
    # marcos y etiquetas: por defecto sobre una tarjeta (surface); "Bg." = sobre el fondo de la ventana
    s.configure("TFrame", background=t["surface"])
    s.configure("Bg.TFrame", background=t["bg"])
    s.configure("TLabel", background=t["surface"], foreground=t["fg"])
    for name, bg, fg, font in (("Bg.TLabel", "bg", "fg", body), ("Muted.TLabel", "surface", "fg_muted", body),
                               ("Warn.TLabel", "surface", "warn", body), ("Ok.TLabel", "surface", "ok", body),
                               ("Big.TLabel", "surface", "live_fg", big), ("State.TLabel", "surface", "fg", title),
                               ("Legend.TLabel", "bg", "fg_muted", small), ("BgWarn.TLabel", "bg", "warn", body),
                               ("BgMuted.TLabel", "bg", "fg_muted", body)):
        s.configure(name, background=t[bg], foreground=t[fg], font=font)
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
    # pestañas
    s.configure("TNotebook", background=t["bg"], bordercolor=t["border"], lightcolor=t["border"],
                darkcolor=t["border"], tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=t["surface"], foreground=t["fg_muted"], bordercolor=t["border"],
                lightcolor=t["border"], darkcolor=t["surface"], padding=(10, 3))
    s.map("TNotebook.Tab", background=[("selected", t["surface_alt"]), ("active", t["hover"])],
          foreground=[("selected", t["fg"]), ("active", t["fg"])],
          lightcolor=[("selected", t["accent"])], darkcolor=[("selected", t["surface_alt"])],
          expand=[("selected", (0, 0, 0, 0))])


def _popdowns(w, t):
    """El Toplevel de lista de cada Combobox se crea al usarlo y ya no lee la base de opciones: se repinta a mano."""
    for c in w.winfo_children():
        if c.winfo_class() == "Listbox" and str(c).endswith(".popdown.f.l"):
            c.configure(background=t["surface_alt"], foreground=t["fg"], selectbackground=t["accent"],
                        selectforeground=t["accent_fg"], font=t["font.body"])
        else:
            _popdowns(c, t)


def apply(root, theme=None):
    """ÚNICO punto que toca ttk.Style, la base de opciones, el fondo de la raíz, -alpha y la barra de título.
    Se puede llamar más de una vez (cambio de tema en caliente): vuelve a pintar todo lo registrado.
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
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"):
        tkfont.nametofont(name, root=root).configure(family=body[0], size=body[1], weight="normal")
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
    try:
        root.attributes("-alpha", t["window.alpha"])
    except Exception:
        log.warning("no se pudo aplicar -alpha")
    for fn in _listeners:
        fn()


def _alive(w):
    try:
        return bool(w.winfo_exists())
    except Exception:
        return False
