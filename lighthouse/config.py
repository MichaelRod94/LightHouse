"""Config persistente: %APPDATA%/LightHouse/config.json (JSON con "version", escritura atómica)."""
import json
import logging
import os
import re

log = logging.getLogger(__name__)
VERSION = 6
_SIZED = re.compile(r"^\d+x\d+(([+-]-?\d+)([+-]-?\d+))$")


def _migrate(raw):
    """Sube un dict guardado por versiones anteriores al formato actual (en sitio)."""
    v = raw.get("version", 1)
    if v < 2:  # F1 -> F2: retardo -> offset; la lista de audio lleva prefijo
        if "delay" in raw and "offset" not in raw:
            raw["offset"] = raw.pop("delay")
        if isinstance(raw.get("device"), str) and raw["device"]:
            raw["device"] = "Salida (loopback) · " + raw["device"]  # = audio.LOOP; F1 solo tenía loopback
    # v2 -> v3 (F4): solo llaves nuevas (teclas, colores de looks, estrobos, limitador); las ponen los defaults
    if v < 4 and "outputs" not in raw:  # F5: la ventana Luz pasa a ser la Salida 1, en ventana, con su geometría
        geo = raw.pop("geo_light", "")
        raw["outputs"] = [{"geo": geo if isinstance(geo, str) else ""}]  # el resto de campos: defaults
    # v4 -> v5 (F7): aparece "ui" (theme); no transforma nada, las llaves nuevas las ponen los defaults
    if v < 6 and isinstance(raw.get("geo_control"), str):
        # F8: geo_control pasa a restaurar también el tamaño; el guardado era el del contenido viejo,
        # así que solo se conserva la posición ("+X+Y") y el tamaño lo pone el default
        g = _SIZED.match(raw["geo_control"])
        raw["geo_control"] = g[1] if g else ""
    # F9 (sin subir la versión): ui.geo_mini, ui.mini_encima, ui.mini_sin_foco y keys.mini son llaves nuevas
    # que ponen los defaults; ui.vista ya aceptaba "mini"
    # F10 (sin subir la versión): ui.tips (ayudas al pasar el ratón, activo por defecto) es una llave nueva
    # que ponen los defaults
    # F11 (sin subir la versión): ui.tutorial ("preguntar" · "no_preguntar" · "visto") es una llave nueva
    # que ponen los defaults; un valor inválido vuelve a "preguntar" (App.apply_ui)
    # F13 (sin subir la versión): ui.intro (animación de entrada, activa por defecto) es una llave nueva
    # que ponen los defaults
    # F14 (sin subir la versión): ui.theme acepta los cuatro temas; uno que no sea texto o que no exista se
    # normaliza a "oscuro" en load(), sin tocar ninguna otra llave
    if v < VERSION:
        log.info("config migrada de v%s a v%d", v, VERSION)


def path():
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "LightHouse", "config.json")


def log_dir():
    """Carpeta de registros (lighthouse.log): %LOCALAPPDATA%/LightHouse/logs."""
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "LightHouse", "logs")


def _fit(v, d):
    """v con el tipo de d (bool/int/float/str/list de str/dict de esos/list de dict), o None si no encaja.
    dict: solo las llaves de d; cada una que no encaje conserva su default.
    list de dict (salidas): cada elemento contra el primero de d; los que no son dict se descartan."""
    if isinstance(d, dict):
        if not isinstance(v, dict):
            return None
        fits = {k: _fit(v[k], dv) if k in v else None for k, dv in d.items()}
        return {k: dv if fits[k] is None else fits[k] for k, dv in d.items()}
    if isinstance(d, bool):
        return v if isinstance(v, bool) else None
    if isinstance(d, (int, float)):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    if isinstance(d, str):
        return v if isinstance(v, str) else None
    if isinstance(d, list) and d and isinstance(d[0], dict):
        items = [_fit(i, d[0]) for i in v] if isinstance(v, list) else []
        return [i for i in items if i is not None] or None
    if isinstance(d, list):
        return v if isinstance(v, list) and v and all(isinstance(i, str) for i in v) else None
    return None


def load(defaults):
    """defaults = {llave: valor inicial} (los define la UI/Engine: única fuente de verdad).
    Devuelve el dict completo: lo guardado válido sobre los defaults."""
    out, p = dict(defaults), path()
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("la raíz no es un objeto")
    except FileNotFoundError:
        return out
    except Exception as ex:  # JSON corrupto: se aparta y se arranca con defaults
        log.warning("config ilegible (%s); se renombra a .bad y se usan defaults", ex)
        try:
            os.replace(p, p + ".bad")
        except OSError:
            log.exception("no se pudo renombrar a .bad")
        return out
    if isinstance(raw.get("version", 1), (int, float)):
        _migrate(raw)
    for k, d in defaults.items():
        if k in raw:
            v = _fit(raw[k], d)
            if v is None:
                log.warning("config: %r con tipo inválido (%r); se usa el default", k, raw[k])
            else:
                out[k] = v
    ui = raw.get("ui")
    if isinstance(ui, dict) and "theme" in ui and isinstance(out.get("ui"), dict) and "theme" in out["ui"]:
        from . import theme  # F14: ui.theme acepta los temas de theme.THEMES (sin subir la versión)
        if not isinstance(ui["theme"], str) or ui["theme"] not in theme.THEMES:
            log.warning("config: ui.theme=%r no es un tema conocido; se usa %r", ui["theme"], theme.DEFAULT)
            out["ui"] = dict(out["ui"], theme=theme.DEFAULT)  # solo esa llave
    return out  # llaves desconocidas: ignoradas


def _write(d):
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    os.replace(p + ".tmp", p)  # atómico


def _raw():
    try:
        with open(path(), encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def save(d):
    keep = {k: v for k, v in _raw().items() if k == "pantalla"}  # la app no pisa la config del modo pantalla
    _write({"version": VERSION, **keep, **d})


def save_key(key, value):
    """Modo --pantalla: guarda solo su llave y conserva el resto del archivo."""
    raw = _raw()
    raw.setdefault("version", VERSION)
    raw[key] = value
    _write(raw)
