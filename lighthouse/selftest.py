"""Self-check del motor con señal sintética: python -m lighthouse --test"""
import os

import numpy as np

from .engine import BLOCK, BandPass, Engine, Snapshot
from .scene import BLACK, WHITE, Cfg, Scene, compose


def check_filtro_scipy():
    """Opcional (solo desarrollo): compara el pasa-banda propio con scipy.butter. Sin scipy se salta."""
    try:
        from scipy.signal import butter, sosfreqz
    except ImportError:
        print("aviso: scipy no disponible, se salta la comparación del filtro")
        return
    sr, hz = 48000, 250
    sos = butter(4, [30, hz], "bandpass", fs=sr, output="sos")
    for f in (30, 60, 120, 250, 1000):
        filt = BandPass(sr, hz)
        x = np.sin(2 * np.pi * f * np.arange(sr * 2) / sr)
        y = np.concatenate([filt(x[i:i + BLOCK]) for i in range(0, len(x), BLOCK)])
        mine = 20 * np.log10(np.sqrt(np.mean(y[len(y) // 2:] ** 2)) / np.sqrt(0.5))
        ref = 20 * np.log10(abs(sosfreqz(sos, [f], fs=sr)[1][0]))
        if f == 1000:
            assert mine <= -20, (f, mine)
        else:
            assert abs(mine - ref) <= 2, (f, mine, ref)
    print("ok: filtro propio coincide con scipy (±2 dB en banda, ≥20 dB de atenuación a 1 kHz)")


COLOR_NAMES = {"black", "white", "red", "green", "blue", "yellow", "orange", "purple", "pink", "brown", "cyan",
               "magenta", "gray", "grey", "gold", "navy", "teal", "maroon", "lime", "silver"}
INTERACTIVE = {"Button", "TButton", "Checkbutton", "TCheckbutton", "Radiobutton", "TRadiobutton", "Scale",
               "TCombobox", "TEntry", "Entry", "Listbox"}


def check_sin_colores_sueltos():
    """ui.py y layout.py no tienen literales de color ni nombres de color de Tk, salvo PALETTE y KELVIN (datos
    del show). Solo con código fuente: en el exe congelado se omite."""
    import ast
    import re
    import sys
    from . import layout, tips, tutorial, ui
    for mod in (ui, layout, tips, tutorial):
        path = getattr(mod, "__file__", None)
        if getattr(sys, "frozen", False) or not path or not path.endswith(".py"):
            print("aviso: sin código fuente (exe), se salta el check de colores sueltos")
            return
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        exempt = {id(n) for a in ast.walk(tree) if isinstance(a, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id in ("PALETTE", "KELVIN") for t in a.targets)
                  for n in ast.walk(a)}
        exempt |= {id(n) for c in ast.walk(tree) if isinstance(c, ast.Compare) for n in ast.walk(c)}  # == "black"
        bad = [(n.lineno, n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant)
               and isinstance(n.value, str) and id(n) not in exempt
               and (re.fullmatch(r"#[0-9a-fA-F]{3,12}", n.value) or n.value.lower() in COLOR_NAMES
                    or n.value.startswith("System"))]
        assert not bad, f"colores sueltos en {os.path.basename(path)}: {bad}"
    print("ok: ui.py, layout.py, tips.py y tutorial.py sin literales de color (salvo PALETTE y KELVIN)")


# ids del catálogo (fases/diseno-ui.md §5.4) que existen desde F13. Falta a propósito el de F14
# (ayuda.tema) y calib.salir (se crea al abrir Calibrar sincronía).
CATALOG = {
    *(f"look.{k}" for k in "1234567QWERTYUZ"),
    "vivo.punto", "vivo.medidor", "vivo.bpm", "vivo.look", "vivo.estado", "vivo.previa", "vivo.teclas",
    "vivo.sin_senal", "vivo.satura", "vivo.red", "vivo.avisos", "modo.auto", "modo.pulso", "modo.tranquilo",
    "modo.manual", "blackout", "bump", "vista.selector", "tab.show", "tab.audio", "tab.salidas", "tab.ayuda",
    *(f"avanzado.{c}" for c in ("respuesta", "luz", "estrobos", "teclado", "fuente", "ganancia", "filtro",
                                "golpe", "tempo", "tranquilo", "salida_sel")),
    "resp.preset", "golpe.sens", "resp.limite", "resp.limite_hz", "luz.master", "luz.decay", "luz.sinc_preset",
    "luz.offset", "luz.piso", "luz.gamma", "luz.manual", "color.modo", "color.kelvin", "color.paleta",
    "color.mas", "color.menos", "estrobo.cierre", "estrobo.min", "teclas.globales", "teclas.tab",
    "audio.dispositivo", "audio.canal", "audio.reconectar", "audio.estado", "audio.prioridad", "nivel.auto",
    "nivel.fijo", "nivel.ref", "filtro.preset", "filtro.corte", "golpe.pausa", "golpe.compuerta", "golpe.fuerza",
    "tempo.kick", "tempo.ritmo", "tempo.fuente", "tempo.tap", "tempo.bpm_manual", "tempo.divisor",
    "calma.preset", "calma.espera", "calma.suavidad", "calma.base", "calma.respira", "salidas.lista",
    "salidas.agregar", "salidas.quitar", "salidas.tv", "salidas.identificar", "salidas.calibrar", "sal.nombre",
    "sal.monitor", "sal.completa", "sal.destino", "sal.puerto", "sal.master", "sal.retardo", "sal.contenido",
    "sal.logo", "sal.logo_buscar", "sal.unirse", "ayuda.carpeta", "vista.fijar", "vista.ampliar", "vista.sin_foco",
    "ayuda.tips", "ayuda.intro", "ayuda.tutorial", "tut.ver", "tut.ahora_no", "tut.no_preguntar", "tut.atras", "tut.siguiente",
    "tut.omitir"}


def check_layout():
    """F8 1–3: layout.pick contra los casos de §3.2, histéresis de 24 px y layout.plan."""
    from .layout import CARDS, TABS, Layout, pick, plan
    cases = (((1920, 1010), "completo", 4, 1), ((1366, 700), "completo", 3, 1), ((1280, 670), "completo", 3, 1),
             ((1093, 560), "compacto", 2, 1), ((946, 1010), "medio", 2, 1), ((1906, 500), "compacto", 4, 1),
             ((700, 420), "compacto", 1, 2), ((820, 90), "mini", 0, 1), ((400, 150), "mini", 0, 2))
    for (w, h), mode, cols, rows in cases:
        lay = pick(w, h)
        assert (lay.mode, lay.cols, lay.look_rows) == (mode, cols, rows), ((w, h), lay)
        assert lay.dense == (mode in ("compacto", "mini")), lay
    assert pick(1366, 700, "compacto").mode == "compacto" and pick(1366, 700, "mini").mode == "mini"
    assert pick(500, 700, "compacto").mode == "mini"  # forzar compacta no impide el mini por tamaño
    medio, full = pick(1100, 700), pick(1300, 700)
    assert medio.mode == "medio" and full.mode == "completo"
    assert pick(1210, 700, prev=medio).mode == "medio" and pick(1230, 700, prev=medio).mode == "completo"
    assert pick(1190, 700, prev=full).mode == "completo" and pick(1170, 700, prev=full).mode == "medio"
    n = 0
    for tab in TABS:
        ids = sorted(c for c, _ in CARDS[tab])
        for cols in range(1, 5):
            p = plan(Layout("completo", cols, 1, False), tab)
            cells = [(c, r) for _, c, r in p]
            assert sorted(cid for cid, _, _ in p) == ids, (tab, cols, p)
            assert all(0 <= c < cols and r >= 0 for c, r in cells), (tab, cols, p)
            assert len(set(cells)) == len(cells), (tab, cols, p)
            n += 1
    assert plan(pick(820, 90), "show") == []
    # F9 1: mini tira (1 fila) / bloque (2 filas); forzado; la tira pasa a bloque justo bajo 760 (los looks y
    # Blackout no caben) y el bloque espera a 760 + 24 para volver a tira
    tira, bloque, forced = pick(820, 90), pick(400, 150), pick(1366, 700, forced="mini")
    assert (tira.mode, tira.look_rows, bloque.mode, bloque.look_rows) == ("mini", 1, "mini", 2), (tira, bloque)
    assert (forced.mode, forced.cols, forced.look_rows) == ("mini", 0, 1), forced
    assert pick(759, 90, prev=tira).look_rows == 2 and pick(760, 90, prev=tira).look_rows == 1
    assert pick(780, 90, prev=bloque).look_rows == 2 and pick(790, 90, prev=bloque).look_rows == 1
    print(f"ok: layout.pick (9 casos de §3.2, forzado; mini tira/bloque), histéresis 24 px, layout.plan "
          f"({n} pestaña × columnas)")


def check_teclas():
    """F8 6: ¿disparan las teclas? (función pura) y el aviso Teclas."""
    from .ui import keys_chip, keys_live
    # keys_live(al frente, globales, escribiendo, foco en un control, Ctrl, Alt)
    assert keys_live(True, False, False, False, False, False)
    assert not keys_live(True, False, False, False, True, False), "con Ctrl"
    assert not keys_live(True, False, False, False, False, True), "con Alt (Alt+F4)"
    assert not keys_live(True, False, True, False, False, False), "escribiendo"
    assert not keys_live(True, False, False, True, False, False), "foco en un control (Navegar con Tab)"
    assert not keys_live(False, False, False, False, False, False), "otra ventana al frente"
    assert keys_live(False, True, False, False, False, False), "globales"
    assert not keys_live(False, True, False, False, False, True) and not keys_live(False, True, True, False, False,
                                                                                   False)
    assert keys_chip(True, False, False) == ("Teclas: activas", "ok")
    assert keys_chip(False, False, False) == ("Teclas: en otra ventana", "fg_muted")
    assert keys_chip(False, True, False) == ("Teclas: siempre activas", "warn")
    assert keys_chip(True, True, True) == ("Teclas: en pausa", "warn")
    print("ok: teclas: nada con Ctrl/Alt, escribiendo, con foco en un control ni sin estar al frente (salvo "
          "globales); aviso Teclas")


SIZES = (  # caso, ventana de referencia (px lógicos), máximos pedidos de §3.5 (None = sin límite)
    ("completo, 3 col", 1366, 700, 3, (1280, 660)), ("medio, 2 col", 946, 1010, 2, (900, None)),
    ("compacto, 4 col", 1906, 500, 4, (1880, 480)), ("compacto, 1 col", 700, 420, 1, (420, None)))


def check_tamanos():
    """F8 4: tamaño pedido de Control (px lógicos, "Avanzado" plegados) por modo y pestaña, al 100 % y al 150 %.
    Con los avisos de la franja en su caso más ancho habitual (Teclas: en otra ventana · TV: enviando).
    Compacto de 1 columna: el límite de 420 es el del cuerpo de tarjetas; la ventana entera debe caber en la
    de referencia (700). Tolerancia de 1 px por el redondeo de px() a escala no entera."""
    from tkinter import font as tkfont
    from . import layout, theme
    from .scene import LOOKS
    from .ui import STATES, App, state_text
    out = []
    for scaling, pct in ((96 / 72, 100), (2.0, 150)):
        app = App(headless=True, scaling=scaling)
        try:
            assert abs(app.scale - pct / 100) < 0.01, app.scale
            app.chip_set(app.keys_chip, "Teclas: en otra ventana", "fg_muted")
            app.chip_set(app.net_chip, "TV: enviando", "ok")
            for name, w, h, cols, (mw, mh) in SIZES:
                big = [0, 0, 0]
                for tab in layout.TABS:
                    rw, rh, bw = app.measure(w, h, tab)
                    assert app.draw.cols == cols, (name, app.draw)
                    if cols == 1:
                        assert bw <= mw + 1 and rw <= w, f"{name} {pct} % {tab}: cuerpo {bw:.0f}, ventana {rw:.0f}"
                    else:
                        assert rw <= mw + 1, f"{name} {pct} % {tab}: ancho {rw:.0f} > {mw}"
                    assert mh is None or rh <= mh + 1, f"{name} {pct} % {tab}: alto {rh:.0f} > {mh}"
                    big = [max(a, b) for a, b in zip(big, (rw, rh, bw))]
                out.append(f"{name} {pct} %: {big[0]:.0f}×{big[1]:.0f}" + (f" (cuerpo {big[2]:.0f})" if cols == 1
                                                                            else ""))
            # F9 2: vista Mini, con los textos más anchos de su línea de estado, sin alarma y con la más larga
            fl = tkfont.Font(root=app.root, font=theme.tok("font.look"))
            app.look_lbl.config(text=max((f"Look {app.keys[k][0]} · {v[0]}" for k, v in LOOKS.items()),
                                         key=fl.measure))
            app.state.config(text=max((state_text(s, True, True) for s in STATES), key=fl.measure))
            for name, w, h, rows, (mw, mh) in MINI_SIZES:
                big = [0, 0]
                for alarm in ("", "ERROR DE AUDIO"):
                    app.chip_set(app.audio_chip, alarm)
                    rw, rh, _ = app.measure(w, h, "show", forced="mini")
                    assert (app.draw.mode, app.draw.look_rows) == ("mini", rows), (name, app.draw)
                    assert rw <= mw + 1 and rh <= mh + 1, f"{name} {pct} % {alarm}: {rw:.0f}×{rh:.0f} > {mw}×{mh}"
                    big = [max(a, b) for a, b in zip(big, (rw, rh))]
                out.append(f"{name} {pct} %: {big[0]:.0f}×{big[1]:.0f}")
            app.chip_set(app.audio_chip, "")
        finally:
            app.quit()
    print("ok: tamaños pedidos (máx. de las 4 pestañas; mini con y sin alarma): " + " · ".join(out))


MINI_SIZES = (("mini tira", 820, 90, 1, (800, 80)), ("mini bloque", 400, 150, 2, (400, 140)))  # F9, §3.5


def check_mini():
    """F9 3–5: en Mini siguen visibles los looks, Blackout, señal y sus botones (y nada más); ida y vuelta de
    la geometría y de siempre encima (a mano, con F9 y sola por tamaño); acción mini -> F9 en el mapa de teclas."""
    from . import win32
    from .ui import KEYS, App
    app = App(headless=True, scaling=96 / 72)  # 100 %: `tk scaling` sigue en el proceso tras check_tamanos
    try:
        by_id = {i: w for w, i in app.ids.items()}

        def shown(w):  # gestionado por pack/grid hasta la raíz (sin ventana no hay winfo_ismapped)
            while w is not app.root:
                m = w.winfo_manager()
                if m not in ("pack", "grid"):
                    return bool(m)  # "" = quitado; "canvas" = dentro del cuerpo de tarjetas
                w = (w.pack_info() if m == "pack" else w.grid_info())["in"]
            return True
        app.chip_set(app.net_chip, "TV: enviando", "ok")  # en Mini no se muestra
        want = [f"look.{k}" for k in "1234567QWERTYUZ"] + ["blackout", "vivo.punto", "vivo.bpm", "vivo.medidor",
                                                           "vivo.previa", "vivo.look", "vivo.teclas",
                                                           "vista.fijar", "vista.ampliar"]
        gone = ["tab.show", "modo.auto", "modo.selector", "bump", "vista.selector", "resp.preset", "vivo.red"]
        for w, h, rows in ((820, 90, 1), (400, 150, 2)):
            app.measure(w, h, "show", forced="mini")
            assert app.draw.look_rows == rows and app.root.title() == "LightHouse", (app.draw, app.root.title())
            hidden = [i for i in want if not shown(by_id[i])]
            visible = [i for i in gone if shown(by_id[i])]
            assert not hidden and not visible, (rows, hidden, visible)
            assert not app.tabbar.winfo_manager() and not app.body_cv.winfo_manager()
            assert all(app.look_btns[k].cget("text") == app.keys[k][0] for k in app.look_btns)  # solo la tecla
        app.measure(1366, 700, "show")
        assert shown(app.tabbar) and shown(by_id["tab.show"]) and not shown(by_id["vista.ampliar"])
        assert app.root.title() == "LightHouse · Control"
        print(f"ok: Mini (tira y bloque): {len(want)} controles visibles (15 looks, Blackout, señal, Encima, "
              "Ampliar); pestañas, tarjetas, Modo, Bump y Vista ocultos (no destruidos)")

        # ida y vuelta: a mano (F9 simulada con win32.key_down / app_in_foreground) y con Ampliar
        top = lambda: bool(int(app.root.attributes("-topmost")))
        app.fit_geometry("1100x650+120+80")
        g0 = app.cur_geo()
        f9, down, front = win32.vk_code("F9"), set(), [True]
        saved = win32.key_down, win32.app_in_foreground
        win32.key_down, win32.app_in_foreground = (lambda vk: vk in down), (lambda: front[0])

        def press(vk):
            app.poll_keys()
            down.add(vk)
            app.poll_keys()
            down.discard(vk)
            app.poll_keys()
        try:
            press(f9)
            gm = app.cur_geo()
            assert app.vista == "mini" and app.draw.mode == "mini" and top() and app.topmost, (app.vista, gm)
            assert gm != g0 and app.draw.look_rows == 1, gm  # tira por defecto (sin ui.geo_mini)
            press(f9)
            got = (app.cur_geo(), app.vista, app.draw.mode, top())
            assert got == (g0, "auto", "medio", False), got
            assert app.snapshot()["ui"]["geo_mini"] == gm  # se recuerda la geometría mini
            front[0] = False  # con otra ventana al frente F9 no hace nada
            press(f9)
            assert app.vista == "auto" and app.cur_geo() == g0
        finally:
            win32.key_down, win32.app_in_foreground = saved
        app.set_vista("compacto")
        app.mini_top.set(False)
        app.choose_vista("mini")  # selector Vista -> Mini, sin siempre encima
        assert app.cur_geo() == gm and app.draw.mode == "mini" and not top()
        app.mini_top.set(True)
        app.set_mini_top()  # el interruptor se aplica ya en Mini
        assert top()
        app.ampliar()
        assert (app.cur_geo(), app.vista, top()) == (g0, "compacto", False), (app.cur_geo(), app.vista)
        # sola por tamaño (vista auto): no cambia siempre encima; Ampliar deja una ventana que ya no es mini
        app.set_vista("auto")
        app.fit_geometry("400x150+120+80")
        assert app.draw.mode == "mini" and app.vista == "auto" and not top()
        app.ampliar()
        assert app.draw.mode != "mini" and app.cur_geo() == g0, (app.draw, app.cur_geo())
        app.fit_geometry("500x200+120+80")
        app.geo_normal = None  # sin geometría normal conocida: el tamaño por defecto
        app.toggle_mini()
        assert app.draw.mode != "mini" and app.vista == "auto" and not top(), (app.draw, app.cur_geo())
        print(f"ok: Mini ida y vuelta: F9, selector y Ampliar vuelven a {g0} exacta y sin siempre encima; "
              f"sola por tamaño, Ampliar -> {app.draw.mode} ({app.cur_geo()})")

        # mapa de teclas: mini -> F9 por defecto; una config guardada sin esa acción la recibe por default
        assert KEYS["mini"] == ["F9"] and app.vk_actions[win32.vk_code("F9")] == ["mini"]
        defaults = app.snapshot()
        raw = dict(defaults, keys={a: v for a, v in defaults["keys"].items() if a != "mini"})
        assert load_cfg(raw, defaults)["keys"]["mini"] == ["F9"]
        print("ok: tecla F9 = acción mini (default; config sin ella -> F9)")
    finally:
        app.quit()


def load_cfg(raw, defaults):
    """config.load(defaults) de un config.json con raw, en un %APPDATA% temporal (no toca el real)."""
    import json
    import tempfile
    from . import config
    old = os.environ.get("APPDATA")
    with tempfile.TemporaryDirectory() as d:
        os.environ["APPDATA"] = d
        try:
            os.makedirs(os.path.dirname(config.path()))
            with open(config.path(), "w", encoding="utf-8") as f:
                json.dump(raw, f)
            return config.load(defaults)
        finally:
            os.environ.pop("APPDATA") if old is None else os.environ.update(APPDATA=old)


def check_interfaz():
    """App(headless=True): ids de todos los controles (y del catálogo de F9), config v4/v5 -> v6, preferencias
    de interfaz y repintado al cambiar de tema."""
    import time
    from . import config, theme
    from .ui import App
    t0 = time.perf_counter()
    app = App(headless=True)
    try:
        ids, dup, missing = {}, [], []
        lights = {str(o.win) for o in app.outputs if not o.remote}  # salidas: superficies de luz, no Control

        def walk(w):
            for c in w.winfo_children():
                if str(c) in lights:
                    continue
                clickable = any(b in ("<Button-1>", "<ButtonPress-1>", "<1>") for b in c.bind())  # clic propio
                if c.winfo_class() in INTERACTIVE or clickable:
                    i = app.ids.get(c)
                    if not i:
                        missing.append(str(c))
                    elif i in ids:
                        dup.append(i)
                    ids[i] = c
                walk(c)
        walk(app.root)
        dt = time.perf_counter() - t0
        assert not missing, f"controles sin id: {missing}"
        assert not dup, f"ids repetidos: {dup}"
        assert not app.root.winfo_viewable() and all(not o.win.winfo_viewable() for o in app.outputs)
        assert dt < 3, f"la interfaz sin ventana tardó {dt:.1f} s"
        reg = set(app.ids.values())
        lost = CATALOG - reg
        assert not lost, f"ids del catálogo sin control: {sorted(lost)}"
        extra = sorted(reg - CATALOG)
        print(f"ok: interfaz sin ventana: {len(ids)} controles con id, sin repetidos; catálogo de F9 completo "
              f"({len(CATALOG)} ids; fuera del catálogo: {', '.join(extra)}) ({dt:.2f} s)")

        # config v4 y v5 guardadas -> v6, sin perder ninguna otra llave; v5: geo_control conserva la posición
        defaults = app.snapshot()
        load = lambda raw: load_cfg(raw, defaults)
        v4 = {k: v for k, v in defaults.items() if k != "ui"}
        v4.update(version=4, decay=321.0, global_keys=True)
        out = load(v4)
        assert config.VERSION == 6 and out["ui"] == defaults["ui"], out["ui"]
        lost = [k for k, v in v4.items() if k != "version" and out[k] != v]
        assert not lost and set(out) == set(defaults), (lost, set(defaults) ^ set(out))
        v5 = dict(v4, version=5, geo_control="1203x581+100+50", ui={"theme": "oscuro"})
        out = load(v5)
        assert out["geo_control"] == "+100+50" and out["ui"] == defaults["ui"], (out["geo_control"], out["ui"])
        geo, _ = app.initial_geometry(out["geo_control"])
        assert geo.endswith("+100+50") and not geo.startswith("1203x581"), geo  # posición sí, tamaño viejo no
        assert load(dict(v5, geo_control="basura"))["geo_control"] == ""
        app.set_vista("xyz")
        assert app.vista == "auto" and app.vista_cb.get() == "Automática"
        app.set_vista("mini")  # se acepta (entrar a Mini con su geometría es enter_mini: check_mini)
        assert app.vista == "mini" and app.vista_cb.get() == "Mini"
        # preferencias de interfaz: vista, pestaña, "Avanzado" abiertos y Navegar con Tab van y vuelven
        app.set_vista("compacto")
        app.tab_var.set("audio")
        app.set_adv("luz", True)
        app.tab_nav.set(True)
        u = app.snapshot()["ui"]
        assert (u["vista"], u["tab"], u["avanzado"]["luz"], u["tab_nav"]) == ("compacto", "audio", True, True), u
        app.apply_ui(defaults["ui"])
        assert app.snapshot()["ui"] == defaults["ui"]
        app.apply_ui(u)
        assert app.snapshot()["ui"] == u and app.adv["luz"][1].winfo_manager() == "pack"
        app.apply_ui(defaults["ui"])
        print("ok: config v4/v5 -> v6 (geo_control: posición sí, tamaño por defecto; ui.vista inválida -> auto); "
              "vista, pestaña, Avanzado y Navegar con Tab se guardan y se restauran")

        # repintado: un tema de prueba y de vuelta a "oscuro"
        from tkinter import ttk

        def verify(t, tag):
            n = 0
            for (w, item), tokens in theme._painted.items():
                for opt, token in tokens.items():
                    if token.startswith("font."):
                        continue
                    got = str(w.itemcget(item, opt) if item is not None else w.cget(opt)).lower()
                    assert got == t[token].lower(), f"{tag}: {w} {opt}: {got} != {token} {t[token]}"
                    n += 1
            st = ttk.Style(app.root)
            for style, opt, token, state in (
                    ("TFrame", "background", "surface", None), ("Bg.TFrame", "background", "bg", None),
                    ("TLabel", "foreground", "fg", None), ("Muted.TLabel", "foreground", "fg_muted", None),
                    ("TButton", "background", "surface_alt", None), ("TCombobox", "fieldbackground", "surface_alt", None),
                    ("TEntry", "fieldbackground", "surface_alt", None),
                    ("Seg.Toolbutton", "background", "surface_alt", ["selected"]),
                    ("Link.TButton", "foreground", "fg_muted", None),
                    ("TCheckbutton", "indicatorforeground", "accent", None)):
                got = str(st.lookup(style, opt, state)).lower()
                assert got == t[token].lower(), f"{tag}: ttk {style} {opt}: {got} != {token} {t[token]}"
                n += 1
            assert str(app.root.cget("bg")).lower() == t["bg"].lower(), tag
            return n
        assert len(theme._painted) >= 60, len(theme._painted)
        test = dict(theme.get("oscuro"), bg="#102030", surface="#203040", surface_alt="#304050", fg="#FAFAF0",
                    accent="#00AA55", fg_muted="#C0C0D0")
        theme.apply(app.root, test)
        n = verify(test, "prueba")
        theme.apply(app.root, "oscuro")
        n += verify(theme.get("oscuro"), "oscuro")
        print(f"ok: repintado al cambiar de tema y volver: {n} colores comprobados en widgets tk y estilos ttk")
    finally:
        app.quit()


JERGA = {"decay", "offset", "gamma", "refractario", "agc", "dbfs", "master", "kick", "tempo", "tap", "flash",
         "lecturas", "piso", "ganancia", "compuerta", "loopback"}  # columna "Hoy" de §2.3


def check_tips():
    """F10: cada control interactivo tiene tooltip (con su enlace), textos de calidad, sin huérfanos, colocación
    dentro del monitor sin tapar el puntero y títulos con la tecla real."""
    import re
    from . import tips
    from .tips import TIPS, place, text, title
    from .ui import App
    from .win32 import Monitor
    app = App(headless=True)
    try:
        lights = {str(o.win) for o in app.outputs if not o.remote}
        tipwin = str(app.tip.win)
        seen, bad = {}, []

        def walk(w):
            for c in w.winfo_children():
                if str(c) in lights or str(c) == tipwin:
                    continue
                clickable = any(b in ("<Button-1>", "<ButtonPress-1>", "<1>") for b in c.bind())
                if c.winfo_class() in INTERACTIVE or clickable:
                    wid = app.ids.get(c)
                    if not wid:
                        bad.append(f"{c} (sin id)")
                    elif wid not in TIPS:
                        bad.append(f"{c} (id {wid} sin texto en TIPS)")
                    elif "<Enter>" not in c.bind():
                        bad.append(f"{c} (id {wid} sin enlace de hover)")
                    seen[wid] = c
                walk(c)
        walk(app.root)
        assert not bad, f"controles sin tooltip: {bad}"
        # 1 · cobertura: lo registrado también resuelve (p. ej. un widget que no es de los de la lista)
        miss = sorted(set(app.ids.values()) - set(TIPS))
        assert not miss, f"ids registrados sin texto en TIPS: {miss}"
        # 3 · sin huérfanos: cada texto es de un control registrado (calib.salir nace al abrir Calibrar)
        orphan = sorted(set(TIPS) - set(app.ids.values()) - {"calib.salir"})
        assert not orphan, f"textos de controles que ya no existen: {orphan}"
        # 2 · calidad (también con las teclas ya sustituidas)
        weak = []
        for wid in TIPS:
            t = text(wid, app)
            plain = re.sub(r'"[^"]*"', "", t)  # un valor citado tal como se ve en pantalla no cuenta
            words = {w.lower() for w in re.findall(r"\w+", plain)} & JERGA
            if not t.strip() or len(t) > tips.MAX_LEN or not t.endswith(".") or words or "{" in t:
                weak.append((wid, len(t), sorted(words)))
        assert not weak, f"textos que no cumplen las reglas de §5.2: {weak}"
        # 4 · place: puntero en el centro, cerca de cada borde y en cada esquina
        n = 0
        for mon in (Monitor("a", 0, 0, 1366, 768, True), Monitor("b", -2560, -360, 2560, 1440, False)):
            xs = (mon.x, mon.x + 5, mon.x + mon.w // 2, mon.x + mon.w - 6, mon.x + mon.w - 1)
            ys = (mon.y, mon.y + 5, mon.y + mon.h // 2, mon.y + mon.h - 6, mon.y + mon.h - 1)
            for w, h in ((340, 60), (340, 140), (230, 200)):
                for px in xs:
                    for py in ys:
                        x, y = place(px, py, w, h, mon)
                        assert mon.x <= x and x + w <= mon.x + mon.w and mon.y <= y and y + h <= mon.y + mon.h, \
                            ((px, py, w, h), (x, y), mon)
                        assert not (x <= px < x + w and y <= py < y + h), ((px, py, w, h), (x, y))
                        n += 1
        mon = Monitor("a", 0, 0, 1366, 768, True)
        assert place(100, 100, 300, 80, mon) == (114, 120)           # normal: 14 a la derecha y 20 debajo
        assert place(1300, 100, 300, 80, mon)[0] == 1300 - 14 - 300  # voltea a la izquierda
        assert place(100, 740, 300, 80, mon)[1] == 740 - 20 - 80     # voltea hacia arriba
        win = (100, 700, 800, 80)  # Mini al fondo del monitor: el tooltip sale arriba de la ventana
        x, y = place(300, 720, 300, 80, mon, avoid=win)
        assert y + 80 <= win[1] and x >= 0, (x, y)
        x, y = place(300, 100, 300, 80, mon, avoid=(100, 50, 800, 80))  # y con sitio, debajo
        assert y >= 130, (x, y)
        # 5 · título con la tecla real (y con la que cambió el usuario)
        assert title("blackout", app) == "Blackout · Espacio", title("blackout", app)
        assert title("look.2", app) == "Look 2 · Rojo · 2" and "Ampliar · F9" == title("vista.ampliar", app)
        assert "Espacio" in text("blackout", app) and "F" in text("look.Z", app)
        app.keys["blackout"], app.keys["1"] = ["B"], ["X"]
        assert title("blackout", app) == "Blackout · B" and "Espacio" not in title("blackout", app)
        assert "(o B)" in text("blackout", app) and title("look.1", app).endswith("· X")
        print(f"ok: tooltips: {len(seen)} controles interactivos con tooltip y enlace, {len(TIPS)} textos (≤ 200, con "
              f"punto, sin jerga), sin huérfanos; place en {n} puntos (monitor 1366×768 y con origen negativo); "
              f"título con la tecla real")
    finally:
        app.quit()


def check_tutorial():
    """F11: pasos válidos, textos, ring_rects y bubble_pos puros, recorrido sin ventana, avance por acción,
    estados de la pregunta de primer arranque y teclas de show intactas con el tutorial abierto."""
    from . import tutorial
    from .tutorial import STEPS, bubble_pos, ring_rects
    from .ui import TABS, App, keys_live
    app = App(headless=True)
    tut = app.tut
    try:
        # 1 · objetivos válidos
        ids = set(app.ids.values())
        for st in STEPS:
            assert st.id is None or st.id in ids, f"paso {st.title!r}: el control {st.id!r} no existe"
            assert st.tab is None or st.tab in TABS, f"paso {st.title!r}: la pestaña {st.tab!r} no existe"
        assert len(STEPS) == 10 and STEPS[0].id is None
        # 2 · textos
        for st in STEPS:
            assert st.title.strip() and st.text.strip() and len(st.text) <= 240, (st.title, len(st.text))
        # 3 · ring_rects: rodea sin tapar, con su grosor y su margen
        n = 0
        for x, y, w, h in ((0, 0, 50, 20), (100, 80, 200, 30), (7, 3, 1, 1)):
            for g, m in ((3, 3), (3, 0), (6, 2)):
                rs = ring_rects(x, y, w, h, g, m)
                assert len(rs) == 4 and all(tutorial._overlap(r, (x, y, w, h)) == 0 for r in rs), (rs, g, m)
                assert min(r[0] for r in rs) == x - m - g and min(r[1] for r in rs) == y - m - g
                assert max(r[0] + r[2] for r in rs) == x + w + m + g and max(r[1] + r[3] for r in rs) == y + h + m + g
                assert rs[0][3] == rs[1][3] == rs[2][2] == rs[3][2] == g  # grosor
                assert rs[2][0] + rs[2][2] + m == x and rs[3][0] - m == x + w  # margen a los lados
                n += 1
        # 4 · bubble_pos: centro, bordes y esquinas de dos ventanas; sin objetivo, centrado
        tw, th, bub = 140, 30, (340, 170)
        for win in ((0, 0, 1366, 700), (0, 0, 700, 420)):
            xs, ys = (0, (win[2] - tw) // 2, win[2] - tw), (0, (win[3] - th) // 2, win[3] - th)
            for x in xs:
                for y in ys:
                    t = (x, y, tw, th)
                    bx, by = bubble_pos(t, bub, win)
                    assert 0 <= bx and bx + bub[0] <= win[2] and 0 <= by and by + bub[1] <= win[3], (t, win, bx, by)
                    assert tutorial._overlap((bx, by, *bub), t) == 0, (t, win, bx, by)
            assert bubble_pos(None, bub, win) == ((win[2] - bub[0]) // 2, (win[3] - bub[1]) // 2)
        # 5 · recorrido completo sin ventana (también desde Mini); Atrás en el paso 1 no hace nada
        def placed():
            return [f.place_info() for f in tut.ring] + [tut.box.place_info()]
        app.set_tutorial("preguntar")
        tab0, vista0 = app.tab_var.get(), app.vista
        tut.start()
        assert tut.on and tut.i == 0 and tut.box.place_info()
        tut.back()
        assert tut.i == 0
        for i in range(len(STEPS)):
            assert tut.i == i and tut.on
            tut.next()
        assert not tut.on and app.tut_state == "visto" and not any(placed()), placed()
        assert app.tab_var.get() == tab0 and app.vista == vista0 and "on" not in app.tip.__dict__
        app.enter_mini()  # desde Mini: pasa a la vista normal y al terminar vuelve a Mini
        tut.start()
        assert app.vista == "auto" and app.draw.mode != "mini", (app.vista, app.draw.mode)
        tut.skip()
        assert app.vista == "mini" and app.draw.mode == "mini" and not any(placed())
        app.leave_mini()
        # 6 · avance por acción (reloj simulado) y "Ya está" cuando ya se cumplía
        app.select_look("1")
        tut.start()
        for _ in range(3):
            tut.next()
        assert STEPS[tut.i].id == "look.2" and tut.state == "espera"
        tut.tick(100.0)
        assert tut.i == 3 and tut.state == "espera"
        app.select_look("2")
        tut.tick(100.0)
        assert tut.state == "hecho" and tut.i == 3
        tut.tick(100.5)
        assert tut.i == 3
        tut.tick(100.71)
        assert tut.i == 4, tut.i
        tut.back()  # el look 2 ya está activo: se muestra "✓ Ya está" y espera
        assert tut.i == 3 and tut.state == "ya" and tut.status.cget("text") == "✓ Ya está"
        tut.tick(200.0)
        tut.tick(300.0)
        assert tut.i == 3 and tut.state == "ya"
        tut.next()
        tut.next()  # Blackout: se cumple al activarlo y desactivarlo
        assert STEPS[tut.i].id == "blackout" and tut.state == "espera"
        app.key_action("blackout")
        tut.tick(400.0)
        tut.tick(401.0)
        assert tut.state == "espera" and tut.i == 5
        app.key_action("blackout")
        tut.tick(402.0)
        assert tut.state == "hecho"
        app.key_action("blackout")  # omitir con las pantallas apagadas: no quedan en blackout
        tut.skip()
        assert not app.scene.blackout and not app.bo.get() and not tut.on
        app.select_look("1")
        # 7 · estados de la pregunta de primer arranque
        app.set_tutorial("preguntar")
        app.band_off = False
        app.no_ask.set(False)
        app.update_band()
        assert app.band_on
        app.band_no()
        assert app.tut_state == "preguntar" and not app.band_on and app.band_off
        app.band_off = False
        app.no_ask.set(True)
        app.band_no()
        assert app.tut_state == "no_preguntar" and not app.band_on
        app.no_ask.set(False)
        app.set_tutorial("preguntar")
        app.band_off = False
        app.intro_on = True
        assert not app.band_wanted()  # la banda espera a que termine la intro
        app.intro_on = False
        assert app.band_wanted()
        tut.start()
        assert not app.band_on  # con el tutorial abierto no hay banda
        tut.next()
        tut.skip()
        assert app.tut_state == "visto" and not tut.on
        bad = dict(app.snapshot()["ui"], tutorial="quizás")
        app.apply_ui(bad)
        assert app.tut_state == "preguntar" and app.snapshot()["ui"]["tutorial"] == "preguntar"
        # 8 · las teclas de show no se pausan con el tutorial abierto (ni con Navegar con Tab)
        base = keys_live(True, False, app.typing, app.nav_focus, False, False)
        app.tab_nav.set(True)
        tut.start()
        assert base and keys_live(True, False, app.typing, app.nav_focus, False, False) == base
        assert not app.typing and not app.nav_focus
        for b in (tut.back_b, tut.next_b, tut.skip_b):
            assert str(b.cget("takefocus")) == "0", b
        tk_classes = {w.winfo_class() for w in _descendants(tut.box)}
        assert not tk_classes & {"Entry", "TEntry", "Text", "TCombobox", "Listbox"}, tk_classes
        tut.skip()
        app.tab_nav.set(False)
        app.set_tutorial("preguntar")
        print(f"ok: tutorial: {len(STEPS)} pasos con objetivo, pestaña y texto (≤ 240) válidos; ring_rects ({n} casos) "
              f"y bubble_pos (1366×700 y 700×420, centro/bordes/esquinas); recorrido completo (también desde "
              f"Mini); avance por acción y '✓ Ya está'; estados de la pregunta; teclas de show sin pausa")
    finally:
        app.quit()


def check_intro():
    """F13: manifiesto real, value, frame_index, resolve y color (puras), manifiestos rotos, reproductor genérico
    con un manifiesto mínimo, sin hardcode en intro.py y omitir a mitad."""
    import ast
    import json
    import re
    import sys
    import tempfile
    from . import VERSION, intro, scene, theme
    from .ui import App

    # 1 · manifiesto real
    folder = intro.resource_path("assets", "intro")
    m = intro.load(os.path.join(folder, "intro.json"))
    assert m is not None, "intro.json no es válido"
    assert all(os.path.isfile(p) for p in m.files()) and m.duracion_ms <= 3000, m.duracion_ms
    total = sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder))
    assert total <= 3 * 1024 * 1024, total

    # 2 · value
    for e, mid in (("lineal", 0.5), ("in_cubic", 0.125), ("out_cubic", 0.875), ("in_out", 0.5)):
        tr = [[100, 2.0], [300, 6.0, e]]
        assert intro.value(tr, 100) == 2.0 and intro.value(tr, 300) == 6.0, e
        assert abs(intro.value(tr, 200) - (2 + 4 * mid)) < 1e-9, (e, intro.value(tr, 200))
    tr = [[100, 2.0], [300, 6.0, "corte"]]
    assert intro.value(tr, 299.9) == 2.0 and intro.value(tr, 300) == 6.0
    assert intro.value(tr, 0) == 2.0 and intro.value(tr, 9999) == 6.0
    tr = [[0, False], [50, True, "corte"], [80, False]]
    assert (intro.value(tr, 10), intro.value(tr, 60), intro.value(tr, 80)) == (False, True, False)

    # 3 · frame_index
    por_tiempo = {"cuadros": 11, "fps": 10}
    assert [intro.frame_index(por_tiempo, t) for t in (0, 500, 1000, 5000)] == [0, 5, 10, 10]
    por_nivel = {"cuadros": 11, "cuadro_por": "nivel", "pistas": {"nivel": [[0, 0.0], [1000, 1.0]]}}
    assert [intro.frame_index(por_nivel, t) for t in (0, 500, 1000)] == [0, 5, 10]

    # 4 · resolve y color
    assert intro.resolve("v{version} {x}", {"version": VERSION}) == f"v{VERSION} {{x}}"
    th = theme.get(theme.DEFAULT)
    looks = {k: v[2] for k, v in scene.LOOKS.items() if v[2]}
    assert intro.color("token:intro_fg", th, looks) == th["intro_fg"]
    assert intro.color("look:2", th, looks) == scene.LOOKS["2"][2][0] == "#FF0000"
    assert intro.color("nada:raro", th, looks) == th["intro_fg"] and intro.color("look:99", th, looks) == th["intro_fg"]
    assert intro.fuente("token:font.intro", th) == th["font.intro"] and intro.fuente("x", th) == th["font.body"]

    app = App(headless=True)
    try:
        with tempfile.TemporaryDirectory() as d:
            def write(data, name="intro.json"):
                p = os.path.join(d, name)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(data if isinstance(data, str) else json.dumps(data))
                return p
            # una secuencia de 2 cuadros (PNG escritos por Tk) + una capa color + un texto
            for i in range(2):
                img = app.tk.PhotoImage(master=app.root, width=8, height=8)
                img.put("gray%d" % (30 + 40 * i), to=(0, 0, 8, 8))
                img.write(os.path.join(d, f"q_{i}.png"), format="png")
                for k in range(2):  # y los mismos cuadros partidos en 2 franjas
                    img.write(os.path.join(d, f"s_{i}_{k}.png"), format="png")
                del img
            base = {"formato": 1, "lienzo": [64, 36], "duracion_ms": 300, "fondo": "token:intro_bg", "capas": [
                {"id": "c", "tipo": "color", "color": "look:2", "rect": [0, 0, 0.5, 1],
                 "pistas": {"visible": [[0, False], [100, True, "corte"], [200, False]]}},
                {"id": "q", "tipo": "secuencia", "archivos": "q_{}.png", "cuadros": 2, "fps": 10, "pos": [0.5, 0.5]},
                {"id": "s", "tipo": "secuencia", "archivos": "s_{}_{}.png", "cuadros": 2, "franjas": 2, "fps": 10},
                {"id": "t", "tipo": "texto", "texto": "{app} v{version}", "fuente": "token:font.small",
                 "color": "token:intro_fg", "pistas": {"y": [[0, 0.9], [300, 0.5, "out_cubic"]]}}]}
            # 5 · manifiestos rotos: None sin lanzar
            rotos = {"sin archivo": os.path.join(d, "no_existe.json"), "JSON inválido": write("{no es json", "mal.json"),
                     "capa desconocida": write(dict(base, capas=[{"id": "x", "tipo": "holograma"}]), "tipo.json"),
                     "PNG que falta": write(dict(base, capas=[dict(base["capas"][1], archivos="no_{}.png")]), "png.json"),
                     "dura de más": write(dict(base, duracion_ms=3001), "dura.json")}
            for nombre, p in rotos.items():
                assert intro.load(p) is None, nombre
            # 6 · genérico: un manifiesto mínimo se reproduce con tiempos simulados y no deja nada vivo
            mm = intro.load(write(base))
            assert mm is not None and len(mm.files()) == 6

            def estado():
                return (app.intro, app.intro_on, app.band_on, len(app.root.winfo_children()),
                        len(app.root.tk.call("image", "names")))
            antes = estado()
            it = intro.Intro(app, mm, {"app": "Prueba", "version": VERSION})
            assert app.intro is it and app.intro_on and len(it.cv.find_all()) == 5
            assert estado()[1:3] == (True, False) and app.band_on is False
            texto = [it.cv.itemcget(i, "text") for i in it.cv.find_all() if it.cv.type(i) == "text"]
            assert texto == [f"Prueba v{VERSION}"], texto
            fr, n, now = it.fr, 0, 1000.0
            while app.intro is not None:
                it.tick(now + n * 0.033)  # tiempo simulado: 30 Hz
                n += 1
                assert n < 100
            assert not fr.winfo_exists() and not it.photo and not it.raw and estado() == antes, (estado(), antes)
            # 8 · omitir a mitad deja la app igual que si hubiera terminado
            it = intro.Intro(app, mm, {"app": "Prueba"})
            for k in range(4):
                it.tick(now + k * 0.033)
            assert app.intro is it
            it.skip()
            assert estado() == antes and it.fr is None
            it.skip()  # idempotente
            # tick con la capa ya cerrada no hace nada
            it.tick(now)
    finally:
        app.quit()

    # 7 · sin hardcode: intro.py sin nombres de archivo PNG ni literales de color (en el exe no hay código fuente)
    path = getattr(intro, "__file__", None)
    if getattr(sys, "frozen", False) or not path or not path.endswith(".py"):
        print("aviso: sin código fuente (exe), se salta el check de intro sin hardcode")
    else:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        bad = [(n.lineno, n.value) for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and (re.search(r"\.png", n.value, re.I) or re.fullmatch(r"#[0-9a-fA-F]{3,12}", n.value)
                    or n.value.lower() in COLOR_NAMES or n.value.startswith("System"))]
        assert not bad, f"hardcode en intro.py: {bad}"
    print(f"ok: intro: manifiesto real ({len(m.files())} archivos, {m.duracion_ms} ms, {total / 1048576:.2f} MB), value "
          f"(4 easings + corte + bordes), frame_index, resolve y color; 5 manifiestos rotos -> None; manifiesto mínimo "
          f"genérico reproducido sin dejar capa ni imágenes; omitir = terminar; intro.py sin hardcode")


def _descendants(w):
    for c in w.winfo_children():
        yield c
        yield from _descendants(c)


def check_tema():
    from . import theme
    for n in theme.THEMES:
        t = theme.get(n)
        assert not theme.validate(t), (n, theme.validate(t))
        assert not theme.contrast_failures(t, n), theme.contrast_failures(t, n)
    assert theme.px(8, 1.0) == 8 and theme.px(8, 1.5) == 12
    assert abs(theme.contrast("#000000", "#FFFFFF") - 21) < 0.01
    assert theme.validate({"bg": "#12"}) and "falta fg" in theme.validate({})
    theme.THEMES["_hijo"] = {"base": "oscuro", "bg": "#000000", "label": "Hijo"}  # un tema solo define lo que cambia
    try:
        assert theme.get("_hijo")["bg"] == "#000000" and not theme.validate(theme.get("_hijo"))
        assert theme.get("no existe") == theme.get(theme.DEFAULT)
    finally:
        del theme.THEMES["_hijo"]
    print(f"ok: {len(theme.THEMES)} tema(s) completos, {len(theme.CONTRAST_PAIRS)} pares de contraste, px()")


def selftest():
    check_filtro_scipy()
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

    def run(x=None, **knobs):
        x = sig if x is None else x
        e = Engine(sr)
        for k, v in knobs.items():
            setattr(e, k, v)
        e.set_band(e.band)
        log = []
        for i in range(0, len(x) - BLOCK + 1, BLOCK):
            e.process(x[i:i + BLOCK])
            log.append((e.t, e.beat, e.calm, e.out, e.flashes, e.gate))
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
    _, late = run(offset=0.1)
    assert np.allclose(late[10:, 3], log[:-10, 3])       # offset +100 ms = 10 bloques exactos
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

    # --- F2: canal, ganancia fija, anticipación
    from .audio import to_mono
    s = np.sin(2 * np.pi * 440 * np.arange(BLOCK) / sr).astype(np.float32)
    st = np.stack([s, np.zeros_like(s)], axis=1).ravel()  # estéreo intercalado: L = seno, R = 0
    assert np.allclose(to_mono(st, 2, 0), s) and np.allclose(to_mono(st, 2, 1), 0)
    assert np.allclose(to_mono(st, 2, None), s / 2)       # Mezcla = promedio
    g = groove(8)
    peak = lambda x, **k: run(x, ref_db=-6, **k)[1][:, 3].max()
    fixed = peak(g, agc=False) / peak(0.25 * g, agc=False)
    auto = peak(g, agc=True) / peak(0.25 * g, agc=True)
    assert fixed > 1.5, fixed                            # ganancia fija: la perilla manda
    assert abs(auto - 1) < 0.15, auto                    # AGC: el nivel casi no importa
    ftimes = lambda lg: lg[1:, 0][np.diff(lg[:, 4]) > 0]  # instantes en que sube flashes
    t0 = ftimes(tempo)
    t1 = ftimes(run(sync="tempo", offset=-0.1)[1])
    t0 = t0[(t0 > 4) & (t0 < 8)]
    lead = np.array([t - t1[np.argmin(np.abs(t1 - (t - 0.1)))] for t in t0])
    assert len(t0) >= 7 and np.all(np.abs(lead - 0.1) <= 0.02 + 1e-9), lead  # Al tempo: se adelanta
    _, neg = run(offset=-0.1)
    assert np.array_equal(neg, log)                      # modo kick: offset < 0 = 0
    print(f"ok: to_mono · fija {fixed:.1f}× vs AGC {auto:.2f}× · anticipación "
          f"{lead.mean() * 1000:.0f} ms (±{np.abs(lead - 0.1).max() * 1000:.0f})")

    # --- F4: compuerta, limitador, sample() y compose()
    def gates(lg, a, b):  # duración (s) de la compuerta tras cada destello en [a, b)
        out = []
        for s in np.nonzero(np.diff(lg[:, 4]) > 0)[0] + 1:
            if a <= lg[s, 0] < b:
                j = s
                while j < len(lg) and lg[j, 5]:
                    j += 1
                out.append((j - s) * BLOCK / sr)
        return np.array(out)
    g_kick = np.concatenate([gates(log, 0, 8), gates(log, 14, 20)])  # 1: groove, modo kick
    assert len(g_kick) >= 27 and g_kick.min() >= 0.04 - 1e-9 and g_kick.max() < 0.45, g_kick
    g_tick = gates(tempo, 8.2, 13.9)
    assert len(g_tick) >= 10 and g_tick.max() <= 0.06 + 1e-9, g_tick  # breakdown: solo el mínimo
    burst = 0.8 * np.sin(2 * np.pi * 55 * np.arange(sr * 3) / sr) * ((np.arange(sr * 3) / sr) % 0.1 < 0.04)
    free = run(burst, min_gap=0.05, flash_limit=False)[1]
    lim = run(burst, min_gap=0.05)[1]  # 7: golpes cada 0.1 s, limitador a 6 Hz
    ft = ftimes(lim)
    assert flashes(free, 0.5, 2.9) >= 20, flashes(free, 0.5, 2.9)  # sin limitador sí llegan a 10/s
    assert len(ft) >= 10 and np.diff(ft).min() >= 1 / 6 - 1e-9, np.diff(ft)
    e = Engine(sr)  # 8: sample(delay_s) = estado de hace delay_s (10 bloques)
    s0, s1 = [], []
    for i in range(0, len(sig) // 3 - BLOCK + 1, BLOCK):
        e.process(sig[i:i + BLOCK])
        s0.append(e.sample())
        s1.append(e.sample(0.1))
    assert any(s.gate for s in s1), "sample: la compuerta nunca abrió"
    assert all(a[:3] == b[:3] and abs(a.t - b.t) < 1e-6 for a, b in zip(s1[10:], s0[:-10])), "sample(delay_s)"
    print(f"ok: compuerta {g_kick.min() * 1000:.0f}–{g_kick.max() * 1000:.0f} ms (tick sin kick "
          f"≤{g_tick.max() * 1000:.0f} ms) · limitador {1 / np.diff(ft).min():.1f} destellos/s · sample(0.1)")

    cfg, RED, PURPLE = Cfg(), (255, 0, 0), (128, 0, 255)
    snap = lambda n=0, gate=True, out=0.7, t=0.0: Snapshot(out, n, gate, t)
    sc = Scene()
    sc.select("Q", snap(10))  # n0 = 10
    q = lambda n, gate=True: compose(snap(n, gate), sc, cfg)
    assert [q(10 + k).left for k in (1, 2, 3)] == [WHITE, RED, WHITE]  # 2
    assert q(11, False) == (BLACK, BLACK, False) and q(10) == (BLACK, BLACK, False)
    sc.select("E", snap(10))
    assert q(11)[:2] == (BLACK, RED) and q(12)[:2] == (RED, BLACK) and q(11, False)[:2] == (BLACK, BLACK)  # 3
    sc.select("7", snap(10))
    rainbow = [(255, 0, 0), (255, 127, 0), (255, 255, 0), (0, 255, 0), (0, 0, 255), (75, 0, 130), (143, 0, 255)]
    assert [compose(snap(10 + k, out=1.0), sc, cfg).left for k in range(8)] == rainbow + rainbow[:1]  # 4
    sc.select("U", snap(0, t=100.0))  # 5: ignora out; triángulo de 8 s
    u = lambda dt, out=0.3, c=cfg: compose(snap(out=out, t=100.0 + dt), sc, c).left
    half = Cfg(master=0.5)
    assert u(0) == BLACK and u(4) == PURPLE and u(8) == BLACK and u(4, out=0.0) == PURPLE
    assert u(4, c=half) == (64, 0, 128) and u(2) == (64, 0, 128), (u(4, c=half), u(2))
    sc.select("Z", snap(0))  # 6
    assert compose(snap(out=1.0), sc, cfg) == (BLACK, BLACK, False)
    sc.bump = True
    assert compose(snap(out=0.0), sc, cfg) == (WHITE, WHITE, False)
    sc.blackout = True
    assert compose(snap(out=1.0), sc, cfg) == (BLACK, BLACK, False)
    sc = Scene()  # look 1 = base × out, con logo
    assert compose(snap(out=0.5), sc, cfg) == ((128, 128, 128), (128, 128, 128), True)
    print("ok: compose Q/E/7/U/Z, bump y blackout")

    # --- F5: regla unirse_a_looks por salida y retardo extra por salida
    from .config import _fit
    from .outputs import compose_output, default_output, resolve
    out = lambda sc, rule, master=1.0, logo=True, o=0.7: compose_output(snap(out=o), sc, cfg, rule, master, logo)
    sc = Scene()
    sc.select("2", snap(0))
    f = out(sc, "excepto en 1")                          # 1: look 2 -> se une: rojo, sin logo
    assert f.left == f.right == (178, 0, 0) and not f.logo_visible, f
    sc.select("1", snap(0))
    f = out(sc, "excepto en 1", master=0.3, o=0.5)       # look 1 -> luz base × out × master, con logo
    assert f == ((38, 38, 38), (38, 38, 38), True), f
    assert out(sc, "siempre") == ((178,) * 3, (178,) * 3, False)  # unida en el look 1: sin logo
    assert not out(sc, "excepto en 1", logo=False).logo_visible   # contenido "Luz": nunca logo
    sc.select("Q", snap(0))
    assert out(sc, "nunca", o=0.5) == ((128,) * 3, (128,) * 3, True)  # nunca: base del look 1
    sc.bump = True
    assert out(sc, "nunca", master=0.3) == (WHITE, WHITE, False)  # bump: a todas, sin logo
    sc.blackout = True
    assert all(out(sc, r) == (BLACK, BLACK, False) for r in ("siempre", "excepto en 1", "nunca"))
    e = Engine(sr)  # 2: sample(0.05) = 5 bloques atrás; con offset se suman
    e.offset = 0.1
    s0, s5 = [], []
    for i in range(0, len(sig) // 3 - BLOCK + 1, BLOCK):
        e.process(sig[i:i + BLOCK])
        s0.append(e.sample())
        s5.append(e.sample(0.05))
    assert all(a[:3] == b[:3] and abs(a.t - b.t) < 1e-6 for a, b in zip(s5[5:], s0[:-5])), "sample(0.05)"
    assert e.sample(0.05).t == e.t - 15 * e.dt
    assert e.hist.maxlen - 1 >= round((0.3 + 0.2) / e.dt), e.hist.maxlen  # offset 300 + retardo 200 ms
    from .win32 import Monitor
    mons = [Monitor("\\\\.\\DISPLAY1", 0, 0, 1920, 1080, True), Monitor("\\\\.\\DISPLAY2", 1920, 0, 1280, 720, False)]
    assert resolve("\\\\.\\DISPLAY2", "", mons) == (mons[1], None)
    m, warn = resolve("\\\\.\\DISPLAY9", "800x600+5000+0", mons)  # desconectado -> primario, con aviso
    assert m == mons[0] and warn, (m, warn)
    d = default_output(1, mons)  # config: lista de salidas; los campos inválidos caen al default
    fit = _fit([{"nombre": "TV", "master": 30, "logo": 5}, "x"], [d])
    assert len(fit) == 1 and fit[0]["nombre"] == "TV" and fit[0]["master"] == 30.0 and fit[0]["logo"] == "", fit
    print("ok: unirse_a_looks (excepto en 1 / siempre / nunca), bump y blackout en todas · sample(0.05) "
          "= 5 bloques · monitor ausente -> primario")

    # --- F6: red
    import time
    from . import net
    from .scene import Frame
    f = Frame((1, 2, 3), (250, 251, 252), True)
    pk = net.pack(7, f)
    assert len(pk) == 14 and net.unpack(pk) == (7, f), pk
    assert net.unpack(net.pack(0xFFFFFFFF, f._replace(logo_visible=False)))[1].logo_visible is False
    assert net.unpack(b"XX" + pk[2:]) is None and net.unpack(pk[:-1]) is None
    flt, t = net.SeqFilter(), 100.0
    assert flt.accept(10, t) and not flt.accept(10, t) and not flt.accept(9, t) and flt.accept(11, t)
    assert flt.accept(0xFFFFFFFE, t - 0.1) is False  # 11 -> 0xFFFFFFFE sería un retroceso de 13
    flt = net.SeqFilter()
    assert flt.accept(0xFFFFFFFE, t) and flt.accept(0xFFFFFFFF, t) and flt.accept(0, t) and flt.accept(1, t)
    assert not flt.accept(0xFFFFFFFF, t)  # desbordamiento: 0xFFFFFFFF ya es viejo
    assert flt.accept(3000, t) and not flt.accept(2900, t) and flt.accept(3001, t)  # reordenado: se descarta
    flt = net.SeqFilter()
    assert flt.accept(50000, t)
    assert not flt.accept(2, t + 0.1) and not flt.accept(3, t + 0.9)  # retrocede > 1000 pero aún no pasa 1 s
    assert flt.accept(4, t + 1.2) and flt.accept(5, t + 1.3)           # emisor reiniciado
    flt = net.SeqFilter()
    assert flt.accept(500, t) and flt.accept(1, t + 5)                 # tras > 1 s sin paquetes, cualquiera
    print("ok: paquete de 14 bytes · descarte de seq viejo, desbordamiento y emisor reiniciado")

    rx = net.Receiver(0, "127.0.0.1")  # puerto efímero
    tx = net.Sender("127.0.0.1", rx.port)
    frames = [Frame((i, 0, 0), (0, i, 0), i % 2 == 0) for i in range(1, 6)]
    for fr in frames:
        tx.send(fr, time.perf_counter())
        time.sleep(0.005)
    t1 = time.perf_counter() + 1
    while rx.rx is None or rx.fr != frames[-1]:
        assert time.perf_counter() < t1, "el receptor no obtuvo el último frame"
        time.sleep(0.005)
    n = tx.seq
    tx.send(frames[-1], tx.t_sent + 0.001)  # sin cambio y antes del keepalive: no manda
    assert tx.seq == n
    tx.send(frames[-1], tx.t_sent + net.KEEPALIVE_S + 0.001)  # keepalive
    assert tx.seq == n + 1
    assert rx.signal(rx.rx + 0.5) and rx.frame(rx.rx + 0.5) == frames[-1]
    assert not rx.signal(rx.rx + 1.2)  # timeout: sin señal
    mid = rx.frame(rx.rx + 1.25)  # a mitad del fundido: la luz a ~la mitad y el logo ya visible
    assert mid.logo_visible and 0 < mid.left[0] < frames[-1].left[0] + 1, mid
    assert rx.frame(rx.rx + 1.6) == Frame(BLACK, BLACK, True), rx.frame(rx.rx + 1.6)
    assert net.Receiver(0, "127.0.0.1").frame(0.0) == Frame(BLACK, BLACK, True)  # nunca llegó nada
    tx.close()
    rx.close()
    print("ok: emisor (127.0.0.1) -> receptor: último frame, keepalive, timeout 1 s -> solo logo sobre negro")

    # --- F7: tokens, tema, contraste, ui.py sin colores sueltos, interfaz sin ventana
    check_tema()
    check_sin_colores_sueltos()
    check_interfaz()
    # --- F8: layout responsive, teclas y tamaños pedidos por modo
    check_layout()
    check_teclas()
    check_tamanos()
    # --- F9: vista Mini (tamaños en check_tamanos; F9 1 en check_layout)
    check_mini()
    # --- F10: tooltips (cobertura de todos los controles, textos, colocación y títulos)
    check_tips()
    # --- F11: tutorial interactivo (pasos, geometría pura, recorrido, avance por acción, pregunta, teclas)
    check_tutorial()
    # --- F13: intro (manifiesto, funciones puras, reproductor genérico, omitir)
    check_intro()
