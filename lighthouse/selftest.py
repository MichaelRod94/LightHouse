"""Self-check del motor con señal sintética: python -m lighthouse --test"""
import numpy as np

from .engine import BLOCK, Engine


def selftest():
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

    def run(**knobs):
        e = Engine(sr)
        for k, v in knobs.items():
            setattr(e, k, v)
        e.set_band(e.band)
        log = []
        for i in range(0, len(sig) - BLOCK + 1, BLOCK):
            e.process(sig[i:i + BLOCK])
            log.append((e.t, e.beat, e.calm, e.out, e.flashes))
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
    _, late = run(delay=0.1)
    assert np.allclose(late[10:, 3], log[:-10, 3])       # retardo = 10 bloques exactos
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
