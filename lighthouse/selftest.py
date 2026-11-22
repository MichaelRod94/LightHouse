"""Self-check del motor con señal sintética: python -m lighthouse --test"""
import numpy as np

from .engine import BLOCK, BandPass, Engine


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
