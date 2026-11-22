# LightHouse: plan de desarrollo (v3: revisión AV + decisiones del usuario)

> **Siguiente etapa (producción con el cliente):** ver [fases/README.md](fases/README.md), con el plan por fases F1–F8 y sus prompts autocontenidos. Este documento queda como referencia del diseño de la maqueta.

Maqueta en Python de una luz virtual **blanca** que reacciona a la música que suena en la PC.

- Ejecutar: `python lighthouse.py`
- Self-check del motor: `python lighthouse.py --test`

## 1. Stack (todo ya instalado, cero dependencias nuevas)

| Pieza | Herramienta | Por qué |
|---|---|---|
| Captura de audio | `PyAudioWPatch` (WASAPI loopback) | Graba lo que sale por una salida concreta (Altavoces, HDMI, Auriculares) sin cables virtuales |
| DSP | `numpy` + `scipy.signal` | Butterworth pasa-banda con estado entre bloques (`sosfilt` + `zi`) |
| GUI | `tkinter` (stdlib) | Dos ventanas: **Control** y **Luz** |

## 2. Arquitectura (un solo archivo `lighthouse.py`)

```
Salida de audio elegida ──loopback──► callback PyAudio (bloques ~10 ms)
                                          │
                                          ▼
              Engine: mono → pasa-banda → RMS 40 ms → compuerta → AGC → flujo → golpe / BPM / calma → luz
                                          │  (estado compartido + lock)
                                          ▼
                     tk.after(15 ms) ──► Ventana Luz (gris 0..255)
                                    └──► Ventana Control (medidores)
              Watchdog: si el loopback deja de entregar audio > 200 ms, se alimenta silencio.
```

El motor corre a reloj de bloques (100 Hz), no a reloj de frames: un golpe no se pierde por el jitter de `tk.after`.

## 3. Pipeline DSP

1. **Mono**: promedio de canales.
2. **Pasa-banda** Butterworth 30 Hz..corte (el pasa-altos fijo de 30 Hz quita DC y rumble). Menú: Sub 60 / **Kick 120** / Bajo 200 / Completo, más un slider de ajuste fino de 40 a 250 Hz.
3. **Envolvente**: RMS deslizante de 40 ms con salto de 10 ms (10 ms rizaba con graves de 50 Hz).
4. **Compuerta** a −50 dBFS (rango −60 a −30), medida **antes** del AGC. Por debajo de ella el AGC se congela y no infla el silencio.
5. **AGC**: pico con release de 8 s, para que funcione a cualquier volumen.
6. **Golpe = flujo**, no nivel: se mide la subida de la envolvente en 40 ms. Un bajo sostenido (808) no dispara. Umbral = 0.3/sensibilidad + flujo medio de 1 s. Refractario ajustable de 120 a 500 ms.
7. **BPM**: mediana de los últimos 8 intervalos. Muestra "--" si la dispersión (MAD) supera el 10 % o si no hay golpes en 2 s. Sin plegado ×2/÷2.
8. **Calma con histéresis asimétrica**:
   - Entra tras 5 s sin golpes (rango 2–15), con fundido de ~1.5 s.
   - Sale al **2º golpe en menos de 1.5 s**, con fundido de <100 ms, para no llegar tarde al drop.

## 4. Modos de luz

| Modo | Comportamiento |
|---|---|
| **Pulso** | Flash por evento (kick o tiempo). Decay de 50–1000 ms (default 250). Intensidad proporcional a la fuerza del golpe (mín. 60 %), desactivable |
| **Tranquilo** | Nivel base + profundidad × música (**banda completa**, porque con el paso bajo la música suave dejaría la luz muerta) |
| **Auto** | Alterna entre Pulso y Tranquilo según el detector de calma |
| **Manual** | Fader fijo |
| **Blackout** | Botón de pánico. Gana sobre todo lo demás |

Comunes a todos los modos:
- **Master** (escala todo), **piso del pulso** 8 % (0–50) y **curva gamma** (0.5–3).
- **Fotosensibilidad**: los flashes a menos de 333 ms del anterior salen a media profundidad (límite de 3 flashes/s).
- **Retardo de luz** de 0–300 ms, porque el loopback capta antes de que suenen las bocinas Bluetooth o HDMI. Hay presets por tipo de salida: cable/USB 0, HDMI 50 y Bluetooth 200. Blackout y Flash manual no tienen retardo.

### Tempo (configurable)

- **Sincronía**:
  - *Cada kick*: un flash por cada golpe detectado.
  - *Al tempo*: un reloj al BPM que **sigue pulsando aunque el kick desaparezca**. Los kicks cercanos a la grilla re-sincronizan la fase; dos kicks seguidos fuera de la grilla la re-enganchan. Sin audio (bajo la compuerta), el reloj se detiene.
- **Fuente del BPM**: detectado, o manual (slider de 60–200 o **Tap**, tecla T, con 3 o más toques).
- **Flash cada** 1/1, 1/2 o 1/4 eventos.

### Tranquilo por rangos + presets

Los sliders son *entrar tras* (2–15 s), *suavizado* (1–3 s), *nivel base* (0–60 %) y *profundidad* (0–60 %; 0 = nivel fijo). Los presets solo mueven esos sliders y después se ajustan a mano:

| Preset | Entrar tras | Suavizado | Base | Profundidad |
|---|---|---|---|---|
| Respiración suave (default) | 5 s | 1.5 s | 10 % | 40 % |
| Tenue fijo | 5 s | 1.5 s | 20 % | 0 % |
| Casi apagado | 5 s | 3 s | 3 % | 5 % |
| Demo (entra en 2 s) | 2 s | 1 s | 10 % | 60 % |

### Color (opcional; default blanco = solo intensidad)

- **Blanco**: solo intensidad.
- **Temperatura**: 2000–10000 K, de cálido a frío.
- **Paleta**: colores elegidos por el usuario con `+` (selector de color) y `−`. Avanza un color en cada flash; con un solo color queda como color fijo.

## 5. Pantallas

**Control**
- **Salida de audio**: lista loopback con la salida predeterminada preseleccionada, y *Reconectar*, que re-enumera para ver HDMI/BT recién conectados.
- **Modo**: 4 modos + Blackout.
- **Filtro**: menú de presets + corte.
- **Golpe**: sensibilidad, refractario, compuerta e intensidad por golpe.
- **Tempo**: sincronía, fuente del BPM, Tap, BPM manual y divisor.
- **Luz**: decay, master, piso, gamma, manual y retardo (con presets por salida).
- **Tranquilo**: presets + 4 rangos.
- **Color**: blanco, temperatura o paleta.
- **Lecturas**:
  - Medidor con nivel de banda, subida (golpe) y **línea roja de umbral**, para calibrar la sensibilidad a ojo.
  - Indicador de golpe, BPM y estado.
- **Atajos**:
  - Espacio: Blackout.
  - 1–4: modos.
  - **F mantenida**: flash al 100 %.
  - **T**: tap tempo.

**Luz**
- Color sólido = nivel × color (blanco por defecto). Se arrastra al 2º monitor o proyector; F11 o doble clic pone pantalla completa y Esc la quita.

## 6. Fases y estado

| Fase | Entregable | Verificación | Estado |
|---|---|---|---|
| F1 | Captura loopback + selector + medidor | Loopback real (salida virtual Oculus): 16/16 golpes, 120 BPM | ✅ |
| F2 | DSP: pasa-banda, flujo, BPM, calma, reloj de tempo, tap | `--test` cubre: kick + hats + bajo sostenido + breakdown + silencio, retardo, tempo sin kick (3 flashes) y tap a 120 | ✅ |
| F3 | Ventanas Control y Luz + modos + atajos + color + presets | Arranque, presets, tap, temperatura y paleta ejercitados sin errores | ✅ |
| F4 | Calibración con música real, ajustar defaults | Escucha con varios géneros (pendiente: usuario) | ⏳ |
| F5 | Salida a luces reales (DMX USB / Art-Net / WLED / Hue) | Fuera de la maqueta | ⬜ |

## 7. Revisión del especialista AV (Fable): qué se integró

**Integrado (imprescindible):**
- Onset por flujo.
- RMS de 40 ms.
- Pasa-banda con HP de 30 Hz.
- Menú de presets de filtro.
- Compuerta antes del AGC.
- Watchdog de silencio.
- Motor a reloj de bloques.
- Retardo de luz.
- Histéresis asimétrica.
- Tranquilo con banda completa.
- Piso del 8 %.
- Línea de umbral.
- Atajos con Flash/Bump.

**Integrado (recomendado):**
- Divisor de golpe.
- Refractario ajustable.
- Límite de 3 flashes/s.
- Intensidad por golpe.
- Gamma.
- Confianza de BPM.
- Filtro rehecho con la frecuencia nativa del dispositivo.
- Self-check ampliado.

**Integrado después (respuestas del usuario):**
- Tap tempo y "volante" de BPM.
- Temperatura de color.

**Futuro (fuera de la maqueta):**
- Beat tracking real (fase/downbeat).
- Presets guardados entre sesiones, MIDI, DMX/Art-Net, multizona y strobe.

## 8. Decisiones del usuario

| # | Pregunta | Decisión → implementación |
|---|---|---|
| 1 | ¿"Blanco en tonos"? | Solo intensidad por defecto; color opcional → temperatura o paleta |
| 2 | ¿Cada kick o mantener tempo? | Configurable → sincronía *Cada kick* / *Al tempo*, BPM detectado / manual / tap |
| 3 | ¿Qué hace la luz en tranquilo? | Configurable por rangos, con presets de comodidad y uno de demo |
| 4 | ¿Por qué salida suena? | Cualquiera (bocinas, audífonos, BT, HDMI) → selector + Reconectar + presets de retardo por tipo de salida |
