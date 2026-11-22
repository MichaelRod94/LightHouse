"""Config persistente: %APPDATA%/LightHouse/config.json (JSON con "version", escritura atómica)."""
import json
import logging
import os

log = logging.getLogger(__name__)
VERSION = 3


def _migrate(raw):
    """Sube un dict guardado por versiones anteriores al formato actual (en sitio)."""
    v = raw.get("version", 1)
    if v < 2:  # F1 -> F2: retardo -> offset; la lista de audio lleva prefijo
        if "delay" in raw and "offset" not in raw:
            raw["offset"] = raw.pop("delay")
        if isinstance(raw.get("device"), str) and raw["device"]:
            raw["device"] = "Salida (loopback) · " + raw["device"]  # = audio.LOOP; F1 solo tenía loopback
    # v2 -> v3 (F4): solo llaves nuevas (teclas, colores de looks, estrobos, limitador); las ponen los defaults
    if v < VERSION:
        log.info("config migrada de v%s a v%d", v, VERSION)


def path():
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "LightHouse", "config.json")


def _fit(v, d):
    """v con el tipo de d (bool/int/float/str/list de str/dict de esos), o None si no encaja.
    dict: solo las llaves de d; cada una que no encaje conserva su default."""
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
    return out  # llaves desconocidas: ignoradas


def save(d):
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"version": VERSION, **d}, f, indent=1, ensure_ascii=False)
    os.replace(p + ".tmp", p)  # atómico
