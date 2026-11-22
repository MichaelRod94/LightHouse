"""LightHouse: motor DSP puro (golpe / BPM / calma / tempo -> luz 0..1). Sin audio ni GUI."""
import collections
import math
from typing import NamedTuple

import numpy as np

BLOCK = 480  # frames por bloque (~10 ms @ 48 kHz)
DECIM = 8  # decimación antes del filtro de graves
QS = (0.5412, 1.3066)  # Q de las 2 secciones de un Butterworth de 4º orden


class Snapshot(NamedTuple):
    """Estado del motor en un instante (ya con offset): lo consume scene.compose()."""
    out: float   # intensidad 0..1 (modo, master, piso y gamma)
    n: int       # contador de destellos
    gate: bool   # compuerta de golpe abierta (estrobos Q–Y)
    t: float     # tiempo del motor (s)


def _rbj(kind, f0, fs, q):
    """Biquad RBJ (Audio EQ Cookbook) normalizado: (b0, b1, b2, a1, a2)."""
    w = 2 * math.pi * f0 / fs
    c, a = math.cos(w), math.sin(w) / (2 * q)
    if kind == "lp":
        b0, b1 = (1 - c) / 2, 1 - c
    else:
        b0, b1 = (1 + c) / 2, -(1 + c)
    a0 = 1 + a
    return (b0 / a0, b1 / a0, b0 / a0, -2 * c / a0, (1 - a) / a0)


class BandPass:
    """Pasa-banda 30 Hz..hz: 2 biquads pasa-altos + 2 pasa-bajos (Butterworth 4º por lado),
    forma directa II transpuesta con estado persistente. Trabaja a sr/DECIM."""

    def __init__(self, sr, hz):
        fs = sr / DECIM
        hz = min(hz, 0.45 * fs)
        self.c = [_rbj("hp", 30, fs, q) for q in QS] + [_rbj("lp", hz, fs, q) for q in QS]
        self.z = [[0.0, 0.0] for _ in self.c]

    def __call__(self, x):
        """x: bloque a sr -> lista filtrada a sr/DECIM."""
        n = len(x) // DECIM
        # ponytail: decimar x8 promediando grupos (filtro antialias tipo caja); basta para energía < 250 Hz
        y = x[:n * DECIM].reshape(n, DECIM).mean(axis=1).tolist()
        for (b0, b1, b2, a1, a2), z in zip(self.c, self.z):
            z1, z2 = z
            for i, v in enumerate(y):
                o = b0 * v + z1
                z1 = b1 * v - a1 * o + z2
                z2 = b2 * v - a2 * o
                y[i] = o
            z[0], z[1] = z1, z2
        return y



class Engine:
    """Bloque de audio mono -> golpe / BPM / calma / luz 0..1.
    Sin audio ni GUI: se prueba alimentándolo con arrays."""

    def __init__(self, sr=48000):
        self.sr = sr
        # perillas: las escribe la GUI, las lee el hilo de audio (floats simples, el GIL basta)
        self.mode = "auto"         # auto | pulso | tranquilo | manual
        self.sens = 1.5            # umbral de golpe = 0.3/sens + flujo medio (1 s)
        self.min_gap = 0.25        # s, refractario entre golpes (0.25 => máx 240 BPM)
        self.gate_db = -50.0       # compuerta, medida antes del AGC
        self.agc = True            # False: ganancia fija, la perilla de la mezcladora manda
        self.ref_db = -12.0        # dBFS que valen nivel 1.0 con ganancia fija
        self.sync = "kick"         # kick: flash en cada golpe | tempo: reloj al BPM, sigue sin kick
        self.bpm_src = "auto"      # auto: BPM detectado | manual: slider / tap
        self.bpm_manual = 120.0
        self.divisor = 1           # flash cada N eventos
        self.by_strength = True    # flash proporcional a la fuerza del golpe (mín. 60 %)
        self.decay = 0.25          # s hasta ~5 % del flash
        self.vmax, self.vmin = 1.0, 0.08  # master; piso del pulso
        self.gamma = 1.0
        self.offset = 0.0          # s; >0 retrasa (BT/HDMI van atrasados); <0 anticipa (solo Al tempo)
        self.manual = 0.5
        self.calm_after = 5.0      # s sin golpes -> tranquilo
        self.calm_smooth = 1.5     # s, suavizado de la respiración
        self.calm_base = 0.10      # nivel de tranquilo
        self.calm_depth = 0.40     # cuánto sube con la música (0 = nivel fijo)
        self.cierre = 0.5          # la compuerta cierra cuando lb < cierre × pico desde el destello
        self.strobe_min_ms = 40.0  # ... y ya pasó este mínimo
        self.flash_limit = True    # fotosensibilidad: descarta destellos a más de flash_limit_hz
        self.flash_limit_hz = 6.0
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
        self.count = self.flashes = self.k_last = self.off = 0
        self.phase = 0.0
        self.beat = False
        self.bpm = self.bpm_lock = 0.0
        self.calm = True
        self.calm_w = 1.0
        self.pulse = self.smooth = 0.0
        self.gate = self.gate_hit = False  # compuerta; gate_hit: hubo golpe con ella abierta
        self.gate_t = -1e9
        self.gate_pk = 0.0
        self.dt = BLOCK / sr
        self.hist = collections.deque([(0.0, 0, False)], maxlen=64)  # por bloque: (out, flashes, gate)
        self.out = 0.0
        self.last_sound = -1e9  # último t sobre la compuerta (indicador SIN SEÑAL)

    def set_band(self, hz):
        """Pasa-banda 30 Hz..hz (fuera DC y rumble); hz=0 -> banda completa."""
        self.band = hz
        if hz:
            self.filt = BandPass(self.sr, hz)  # se reemplaza entero: seguro entre hilos
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

    def lead(self):
        """Anticipación efectiva (s): offset < 0 solo actúa Al tempo con BPM fiable; si no, 0."""
        bpm = self.bpm_manual if self.bpm_src == "manual" else self.bpm_lock
        return max(-self.offset, 0.0) if self.sync == "tempo" and bpm else 0.0

    def sample(self, delay_s=0.0):
        """Snapshot de hace offset + delay_s (delay_s: retardo extra por salida). Seguro desde otro hilo."""
        h, dt = self.hist, self.dt
        i = min(round((max(self.offset, 0.0) + delay_s) / dt), len(h) - 1)
        out, n, gate = h[-1 - i]
        return Snapshot(out, n, gate, self.t - i * dt)

    def process(self, x):
        dt = self.dt = len(x) / self.sr
        self.t += dt
        f = self.filt
        y = np.asarray(f(x)) if f is not None else x
        self.win.append((float(np.mean(x * x)), float(np.mean(y * y))))
        full = math.sqrt(sum(w[0] for w in self.win) / len(self.win))
        band = math.sqrt(sum(w[1] for w in self.win) / len(self.win))

        # compuerta antes del AGC; bajo ella el AGC se congela y no infla el silencio
        silent = full < 10 ** (self.gate_db / 20)
        if not silent:
            self.last_sound = self.t
        if not self.agc:  # ganancia fija: nivel 1.0 a ref_db; al volver al AGC parte de aquí
            self.peak_b = self.peak_f = 10 ** (self.ref_db / 20)
        elif not silent:
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
        if flash and self.flash_limit and self.t - self.last_flash < 1 / self.flash_limit_hz:
            flash = False  # limitador (fotosensibilidad): el destello se descarta entero
        if flash:
            s = (min(1.0, max(0.6, 2 * self.onset)) if self.beat else 0.6) if self.by_strength else 1.0
            self.last_flash = self.t
            self.flashes += 1
            self.pulse = max(self.pulse, s)
            # compuerta: abre en cada destello; un tick de tempo sin golpe solo dura el mínimo
            self.gate, self.gate_t, self.gate_pk, self.gate_hit = True, self.t, lb, self.beat
        else:
            self.pulse *= math.exp(-dt * 3 / self.decay)
            if self.gate:  # cierra cuando el golpe deja de sonar (lb < cierre × pico) y pasó el mínimo
                self.gate_pk = max(self.gate_pk, lb)
                self.gate_hit = self.gate_hit or self.beat
                if (self.t - self.gate_t) * 1000 >= self.strobe_min_ms - 1e-6 and (
                        not self.gate_hit or lb < self.cierre * self.gate_pk):
                    self.gate = False
        self.smooth += (lf - self.smooth) * (1 - math.exp(-dt / self.calm_smooth))
        tau = 0.5 if self.calm else 0.03  # entra a calma en ~1.5 s, sale en <100 ms (no llegar tarde al drop)
        self.calm_w += ((1.0 if self.calm else 0.0) - self.calm_w) * (1 - math.exp(-dt / tau))

        pulse_v = self.vmin + (1 - self.vmin) * self.pulse
        calm_v = self.calm_base + self.calm_depth * self.smooth  # banda completa, no solo graves
        v = {"pulso": pulse_v, "tranquilo": calm_v, "manual": self.manual,
             "auto": self.calm_w * calm_v + (1 - self.calm_w) * pulse_v}[self.mode]
        self.hist.append((min(max(v * self.vmax, 0.0), 1.0) ** self.gamma, self.flashes, self.gate))
        self.out = self.sample().out  # blackout y bump los decide scene.compose (sin retardo)

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
        # offset < 0: la grilla se adelanta |offset|; el kick que llega después cae en el refractario
        k = math.floor((self.t - self.phase + max(-self.offset, 0.0)) / period)
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

