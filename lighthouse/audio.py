"""Captura WASAPI con PyAudioWPatch: entradas (interfaz/micrófono) y loopback de salidas.
Enumerar, abrir/cerrar stream, elegir canal, saturación y estado para la reconexión."""
import logging
import time

import numpy as np
import pyaudiowpatch as pa

from .engine import BLOCK

log = logging.getLogger(__name__)
IN, LOOP = "Entrada · ", "Salida (loopback) · "  # prefijos de la lista (y del nombre guardado)
CLIP = 0.98


def to_mono(raw, channels, sel):
    """raw = samples intercalados; sel = índice 0-based del canal, None = mezcla (promedio)."""
    x = raw.reshape(-1, channels)
    return x.mean(axis=1) if sel is None or sel >= channels else x[:, sel]


class Audio:
    def __init__(self, on_block):
        """on_block(x): x = bloque mono float32; se llama desde el hilo de audio de PortAudio."""
        self.on_block = on_block
        self.p = pa.PyAudio()
        self.stream = None
        self.devs, self.names = [], []
        self.sel = None              # canal (0-based) o None = mezcla; se puede cambiar en vivo
        self.loopback = True         # el abierto es loopback (en silencio no entrega bloques)
        self.failed = False          # el callback lanzó
        self.last_cb = self.clip_t = -1e9  # perf_counter del último bloque / último sample saturado

    def refresh(self, prefer=None):
        """Lista entradas WASAPI + loopback. Devuelve (nombres, índice a seleccionar o None)."""
        ins = [d for d in self.p.get_device_info_generator_by_host_api(host_api_type=pa.paWASAPI)
               if d["maxInputChannels"] > 0 and not d["isLoopbackDevice"]]
        loops = list(self.p.get_loopback_device_info_generator())
        self.devs = ins + loops
        self.names = [IN + d["name"] for d in ins] + [LOOP + d["name"] for d in loops]
        if prefer not in self.names:
            try:
                prefer = LOOP + self.p.get_default_wasapi_loopback()["name"]
            except Exception:
                prefer = None
            if prefer not in self.names:
                prefer = self.names[0] if self.names else None
        return list(self.names), (self.names.index(prefer) if prefer in self.names else None)

    def info(self, i):
        d = self.devs[i]
        return int(d["defaultSampleRate"]), d["maxInputChannels"]

    def is_input(self, i):
        return not self.devs[i]["isLoopbackDevice"]

    def alive(self):
        """Stream abierto y entregando. Una entrada entrega siempre; un loopback calla en silencio."""
        s = self.stream
        if s is None or self.failed:
            return False
        try:
            if not s.is_active():
                return False
        except Exception:
            return False
        return self.loopback or time.perf_counter() - self.last_cb < 2.0

    def close(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                log.exception("error al cerrar el stream")
            self.stream = None

    def open(self, i):
        """Abre el stream del dispositivo i. Lanza si falla (el llamador lo muestra)."""
        self.close()
        dev = self.devs[i]
        sr, ch = self.info(i)
        self.loopback, self.failed = not self.is_input(i), False
        self.last_cb = time.perf_counter()

        def cb(data, frames, info, status):
            try:
                if status:
                    log.warning("estado del stream: %s", status)
                raw = np.frombuffer(data, np.float32)
                now = time.perf_counter()
                if raw.max() >= CLIP or raw.min() <= -CLIP:  # crudo, antes de mezclar
                    self.clip_t = now
                self.last_cb = now
                self.on_block(to_mono(raw, ch, self.sel))
                return None, pa.paContinue
            except Exception:
                log.exception("error en el callback de audio")
                self.failed = True
                return None, pa.paAbort

        try:
            self.stream = self.p.open(format=pa.paFloat32, channels=ch, rate=sr, input=True,
                                      input_device_index=dev["index"], frames_per_buffer=BLOCK,
                                      stream_callback=cb)
        except Exception:
            log.exception("error al abrir el stream de %r", dev["name"])
            raise
        log.info("stream abierto: %r %d Hz %d canales", dev["name"], sr, ch)

    def reconnect(self, name):
        """PyAudio cachea la lista: re-inicializar para ver dispositivos nuevos (USB, HDMI, BT)."""
        log.info("reconectando audio (%r)", name)
        self.close()
        self.p.terminate()
        self.p = pa.PyAudio()
        return self.refresh(name)

    def terminate(self):
        self.close()
        self.p.terminate()
