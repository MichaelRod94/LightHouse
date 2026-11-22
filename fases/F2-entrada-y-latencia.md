# Fase F2: Entrada de línea (interfaz/micrófono) y latencia

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior: Windows, audio en tiempo real (WASAPI/PortAudio) y Tkinter. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** es una app de escritorio Python para Windows. Escucha el audio de un set de DJ y convierte cada golpe (kick) en luz: ventanas de color sólido.
- Paquete `lighthouse/` (creado en F1): `engine.py`, `audio.py`, `ui.py`, `config.py`, `selftest.py`, `__main__.py`.
- Hoy **solo captura loopback** de salidas de Windows.
- **Uso principal del cliente**: LightHouse corre en la **laptop DJ junto a rekordbox** y capta por loopback la salida que usa rekordbox, como hoy lo hace su página HTML.
  - La app debe ser **ligera y de prioridad baja**: rekordbox nunca debe sufrir cortes.
- **Respaldo**: si el loopback no ve el audio (p. ej. rekordbox en ASIO), el *booth* de la controladora entra por un cable Y a la **entrada 2 Hi-Z de una Steinberg UR12**, que Windows ve como "micrófono".
  - En ese caso el cliente quiere que **la perilla de booth sea la sensibilidad** → ganancia fija (AGC apagado).

## Lee primero

1. `fases/README.md`: *Topología decidida* (uso principal por loopback y respaldo de audio), *Arquitectura* y *Estado*. **Respeta lo decidido.**
2. `lighthouse/engine.py`, `lighthouse/audio.py`, `lighthouse/ui.py` y `lighthouse/config.py`.

## Precondiciones

- `fases/README.md` marca **F1 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa.
- `git status` para saber qué hay sin commitear.

## Objetivo

1. Capturar desde **dispositivos de entrada** (interfaz o micrófono) además del loopback, eligiendo **canal**.
2. **AGC conmutable.** Con el AGC apagado, la perilla física de la mezcladora controla la intensidad.
3. **Indicadores de señal**: sin señal y saturación, más **reconexión automática**.
4. **Bajar la latencia del render** y unificar el retardo en un **offset** con anticipación en modo tempo.
5. **Prioridad baja del proceso**, para convivir con rekordbox.

## Alcance

### Entra

**Dispositivos (`audio.py`)**
- Una sola lista con:
  - entradas WASAPI (host API WASAPI, `maxInputChannels > 0`, que no sean loopback), con prefijo `Entrada · `;
  - dispositivos loopback, con prefijo `Salida (loopback) · `.
- Se persiste por nombre en la config. Si el guardado no existe → loopback por defecto.

**Canal**
- Combobox `Mezcla` / `Canal 1` … `Canal N` (según `maxInputChannels`).
- La función pura `to_mono(raw: np.ndarray, channels: int, sel: int | None) -> np.ndarray` vive en `audio.py` y se prueba en el self-check.
- Para la UR12 con la Y en la entrada 2, el usuario elige `Canal 2`.

**Ganancia (`engine.py`)**
- `agc: bool` (default `True`) y `ref_db` (−40…0 dBFS, default −12).
- Con `agc=False`, los picos de normalización quedan fijos en `10**(ref_db/20)`:
  - el nivel normalizado vale 1.0 a `ref_db`;
  - la perilla de la mezcladora cambia la intensidad de la luz;
  - la perilla a cero → la compuerta → calma.
- UI: radio `Automática (AGC)` / `Fija (la perilla manda)` + slider `Referencia (dBFS)`, activo solo en Fija.

**Indicadores (UI)**
- **`SIN SEÑAL`** en rojo: el stream está abierto pero la señal está bajo la compuerta por más de 3 s.
- **`SATURA`**: algún sample crudo |x| ≥ 0.98 en los últimos 0.5 s. Se calcula en el callback, sobre los datos crudos antes de mezclar.

**Errores de apertura**
- Si abrir una entrada falla, el estado muestra la pista: *"Revisa Configuración → Privacidad → Micrófono → Permitir que las aplicaciones de escritorio accedan"*.

**Reconexión automática**
- Si el stream deja de estar activo (`not stream.is_active()`) o el callback reporta error, reintenta abrir el mismo dispositivo cada 3 s.
- Estado visible y log. No reintenta en bucle apretado.

**Latencia del render (`ui.py`)**
- **Loop rápido** con `after(1)`: solo lee la salida y aplica color si cambió.
- **Loop lento** (~30 Hz): medidores, labels, BPM e indicadores.
- `sys.setswitchinterval(0.001)` al arrancar.

**Offset unificado** (reemplaza `delay`)
- `offset` en segundos, de −0.150 a +0.300, default 0.
- **Positivo**: igual que hoy (historial de bloques).
- **Negativo** (anticipación): solo tiene efecto con `sync == "tempo"` y BPM fiable (`bpm_lock` o manual). El reloj de tempo dispara `|offset|` antes de la grilla.
- En modo kick, o sin BPM fiable, el negativo se trata como 0.
- La UI muestra *"anticipación activa"* o *"anticipación inactiva (requiere Al tempo)"*.
- Los presets de salida (cable 0 / HDMI 50 / Bluetooth 200 ms) siguen funcionando sobre `offset`.

**Prioridad (nuevo `lighthouse/win32.py`)**
- Ahí vivirá todo el ctypes del proyecto en fases siguientes.
- `set_low_priority(on: bool)`: `SetPriorityClass(GetCurrentProcess(), 0x4000)` (BELOW_NORMAL) o `0x20` (NORMAL).
- Checkbox `Prioridad baja (laptop DJ)`, default `True`, persistido. Se aplica al arrancar y al cambiar.

**Config**
- `version` 1 → 2, migrando `delay` → `offset`.
- Persistir dispositivo, canal, `agc`, `ref_db` y prioridad baja.

**Self-check** (agregar a `selftest.py`)
1. **`to_mono`**: con un array estéreo sintético (canal 1 = seno, canal 2 = ceros), `Canal 1` ≈ seno, `Canal 2` ≈ 0 y `Mezcla` ≈ seno/2.
2. **Ganancia fija**: el mismo groove a amplitud 1.0 y 0.25 con `agc=False` (`ref_db=-6`) → el pico de `out` del fuerte es claramente mayor (> 1.5×). Con `agc=True` los picos difieren < 15 %.
3. **Anticipación**: modo tempo, groove a 120 BPM. Tras el enganche (t > 4 s), los destellos con `offset=-0.1` ocurren 0.1 s ± 0.02 **antes** que con `offset=0`, comparando los tiempos de incremento de `flashes`.
4. **Modo kick con `offset=-0.1`** → salida idéntica a `offset=0`.

### No entra

- WASAPI exclusivo o ASIO (descartado).
- Bloques de 256 o `timeBeginPeriod` (descartados).
- Quitar scipy (F3), looks (F4), multiventana y retardo por salida (F5).

## Diseño decidido

- Seguir con PyAudioWPatch: maneja entradas WASAPI normales y loopback con la misma API.
- El callback sigue llamando `Engine.process` bajo el lock. `to_mono` se aplica antes.
- La anticipación se implementa en `Engine._tick` desplazando la grilla. No se toca la detección.

## Criterios de aceptación

1. Self-check completo pasa, incluidas las 4 pruebas nuevas.
2. **Prueba manual con el micrófono de la laptop** (no hay UR12 en desarrollo):
   - eliges `Entrada · Micrófono…`;
   - aplaudes o golpeas la mesa cerca → se detectan golpes y la luz reacciona;
   - con `Fija`, hablar suave apenas mueve la luz y un golpe fuerte sí.
3. Un sonido muy fuerte cerca del micrófono → `SATURA`. Silencio > 3 s → `SIN SEÑAL`.
4. Si hay un dispositivo USB de audio disponible: desconectarlo → estado de reconexión; conectarlo → vuelve solo en ≤ 6 s. Si no hay, documenta que no se pudo probar.
5. **CPU** del proceso < 5 % de un núcleo, en promedio de 10 s con audio entrando. Mídelo con el delta de `(Get-Process -Id <pid>).CPU` y repórtalo.
6. Las configs de F1 se migran solas (`delay` → `offset`) sin perder valores.
7. Con `Prioridad baja`, el Administrador de tareas (pestaña Detalles → Prioridad) muestra *Por debajo de lo normal*, y la luz sigue sin retraso perceptible.
8. **Pendiente de sitio** (documentar, no se puede probar aquí): con rekordbox corriendo, elegir el loopback de su dispositivo de salida, confirmar que el medidor se mueve y que no hay cortes de audio.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```

CPU, con la app corriendo: reemplaza `<pid>`.

```powershell
$p = Get-Process -Id <pid>; $a = $p.CPU; Start-Sleep 10; $p.Refresh(); "{0:N1} % de un núcleo" -f (($p.CPU - $a) / 10 * 100)
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva.
- **Alcance**: cambios mínimos. No adelantes fases siguientes. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`: F2 → ✅, fecha y nota de una línea, con la CPU medida. Agrega notas para F3 si cambió algo relevante.
2. Responde al usuario con:
   - qué cambió;
   - cómo probarlo;
   - qué no pudiste verificar (UR12 real, desconexión USB);
   - **mensaje de commit sugerido** (p. ej. `feat(audio): entrada de interfaz, canal, AGC conmutable y offset con anticipación`) y la lista de archivos.

   **No hagas el commit.**
