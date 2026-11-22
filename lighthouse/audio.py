"""Captura WASAPI loopback con PyAudioWPatch: enumerar salidas, abrir/cerrar stream, reconectar."""
import logging
import time

import numpy as np
import pyaudiowpatch as pa

from .engine import BLOCK

log = logging.getLogger(__name__)


class Audio:
    def __init__(self, on_block):
        """on_block(x): x = bloque mono float32; se llama desde el hilo de audio de PortAudio."""
        self.on_block = on_block
        self.p = pa.PyAudio()
        self.stream = None
        self.devs = []

    def refresh(self, prefer=None):
        """Lista las salidas loopback. Devuelve (nombres, índice a seleccionar o None)."""
        self.devs = list(self.p.get_loopback_device_info_generator())
        names = [d["name"] for d in self.devs]
        if prefer not in names:
            try:
                prefer = self.p.get_default_wasapi_loopback()["name"]
            except Exception:
                prefer = names[0] if names else None
        return names, (names.index(prefer) if prefer in names else None)

    def info(self, i):
        d = self.devs[i]
        return int(d["defaultSampleRate"]), d["maxInputChannels"]

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

        def cb(data, frames, info, status):
            if status:
                log.warning("estado del stream: %s", status)
            self.on_block(np.frombuffer(data, np.float32).reshape(-1, ch).mean(axis=1))
            return None, pa.paContinue

        try:
            self.stream = self.p.open(format=pa.paFloat32, channels=ch, rate=sr, input=True,
                                      input_device_index=dev["index"], frames_per_buffer=BLOCK,
                                      stream_callback=cb)
        except Exception:
            log.exception("error al abrir el stream de %r", dev["name"])
            raise
        log.info("stream abierto: %r %d Hz %d canales", dev["name"], sr, ch)

    def reconnect(self, name):
        """PyAudio cachea la lista: re-inicializar para ver salidas nuevas (HDMI, BT)."""
        log.info("reconectando audio (%r)", name)
        self.close()
        self.p.terminate()
        self.p = pa.PyAudio()
        return self.refresh(name)

    def terminate(self):
        self.close()
        self.p.terminate()