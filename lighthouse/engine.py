"""LightHouse: motor DSP puro (golpe / BPM / calma / tempo -> luz 0..1). Sin audio ni GUI."""
import collections
import math

import numpy as np
from scipy.signal import butter, sosfilt

BLOCK = 480  # frames por bloque (~10 ms @ 48 kHz)


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

