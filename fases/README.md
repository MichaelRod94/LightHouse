# LightHouse: plan de implementación por fases

> Índice maestro y **fuente de verdad compartida entre sesiones**: arquitectura decidida, decisiones, estado y contexto del cliente.
>
> Cada fase se implementa en una **sesión nueva** con su prompt autocontenido (`fases/Fx-*.md`): se abre el asistente de código en la carpeta del proyecto y se pega el prompt completo.
>
> `PLAN.md` documenta el diseño de la maqueta v3 (motor DSP, modos, tempo y presets). Este plan es la evolución hacia producción.

## Estado

| Fase | Prompt | Depende de | Estado | Notas |
|---|---|---|---|---|
| F1 | [Base modular](F1-base-modular.md) | — | ✅ | 2026-11-21: paquete `lighthouse/` v0.4.0 con config persistente, log y `python -m lighthouse --test`. Notas F2: `audio.Audio(on_block)` (`refresh/info/open/close/reconnect`) y `ui.App.on_block`; config = `config.load(defaults)/save(d)` con defaults tomados de `App.snapshot()` (nueva perilla = widget registrado en `vars`/`checks` o llave nueva en snapshot+apply). |
| F2 | [Entrada, latencia y prioridad](F2-entrada-y-latencia.md) | F1 | ✅ | 2026-11-22: una lista con entradas WASAPI (`Entrada · `) y loopback (`Salida (loopback) · `), canal (`audio.to_mono`), ganancia AGC/Fija (`agc`, `ref_db`), SIN SEÑAL/SATURA, reconexión cada 3 s, `offset` −150…+300 ms con anticipación Al tempo, `win32.set_low_priority`, config v2 (migra `delay`→`offset` y el nombre del loopback). **CPU** (`Get-Process`, 10–15 s con audio): loopback 6,0–8,9 % (F1 con el mismo método: 8,2–11,4 %), micrófono 4,9 %, exe 6,7 % → ⚠️ el loopback no baja de 5 % (solo stream + Tk ociosos ya cuestan ~2,5 %). ⚠️ **Desviación**: `after(1)` gira al ~98 % de un núcleo en Tcl 8.6.15 (trunca la espera a 0 ms), así que el pintado lo dispara cada bloque de audio (hilo `render` → `tk.call` al hilo Tk): mediana 0,2 ms, p99 ~1 ms. `.\build.ps1` re-corrido OK (57,0 MB). Notas F4/F5: todo ctypes en `win32.py`; el pintado vive en `App.fast()` (lo llaman el hilo `render` por bloque y el loop lento a 30 Hz); el loop lento actualiza widgets con `App.put()` (solo si cambian). Pendiente manual: aplausos/voz al micrófono, desconexión USB real, Administrador de tareas, UR12 y rekordbox en sitio. |
| F3 | [Ejecutable](F3-ejecutable.md) | F2 | ✅ | 2026-11-21 (en paralelo con F2; `.\build.ps1` re-corrido OK con F2 terminada el 2026-11-22): filtro propio (decimado ×8 + 4 biquads RBJ, ~27 µs/bloque), sin scipy; `build.ps1` → `dist\LightHouse` 57,0 MB, ZIP 23,5 MB, ventana en ~0,6–1,2 s. PyInstaller 6.22.3 en `.venv-build`. Notas: el venv usa el Python 3.14 global; `run.py` hace `sys.exit(main())`; `--test` en el exe sale con 0/1 y escribe "self-check ok" al log; `LEEME.txt` se copia al ZIP. Pendiente manual: probar en una PC sin Python y la reacción de la luz con audio real. |
| F4 | [Looks por teclado (mapa del cliente)](F4-looks-teclado.md) | F3 | ✅ | 2026-11-22: `lighthouse/scene.py` (15 looks latch; `compose(snap, scene, cfg) -> Frame(left, right, logo_visible)`), compuerta de golpe y limitador (6 Hz, descarta el destello) en el motor, teclas por `GetAsyncKeyState` dentro de `App.fast()` (sin `bind_all`; F1–F4 modos, 0 tap, +/− sensibilidad; `Teclas globales` apagada por defecto), barra de looks, presets `Respuesta` (Normal / Muy reactivo), config v3 (`keys`, `look_colors`, `cierre`, `strobe_min_ms`, `flash_limit`, `flash_limit_hz`, `global_keys`, `response`; el look no se guarda). **CPU** con loopback (`Get-Process`, 10 s): app 6,7–9,4 % (F3 en la misma sesión: 6,6–7,5 %), exe 5,8–7,5 %. ⚠️ **Desviaciones**: (1) la ventana Luz usa dos `Frame` con `bg`, no `Canvas`: a 1920×1080 el Canvas cuesta 7,3 ms por pintado contra 0,3 ms; (2) un destello sin golpe (tick de tempo) solo abre la compuerta `strobe_min_ms`: con la regla literal, un pad estable la dejaba abierta siempre. Si llega un golpe con la compuerta abierta, aplica la regla `cierre`. `.\build.ps1` OK (57,0 MB). Pendiente manual: mirar los looks con música, estrobo real, Bloc de notas al frente y exe con teclas reales. |
| F5 | [Salidas múltiples y pantalla completa](F5-salidas-multiples.md) | F4 | ✅ | 2026-11-22: `lighthouse/outputs.py` (`Output` = un `Toplevel` por salida con dos `Frame`+`bg`, logo `Label`+`PhotoImage` con zoom/subsample entero, Identificar; `compose_output()` puro con la regla `unirse_a_looks` y el master de la salida), `win32` (`set_dpi_aware`, `monitors`, `keep_awake`, `window_rect`), Control en pestañas Show / Audio / Salidas (looks e indicadores siempre visibles), Calibrar retardo, config v4 (`outputs`; `geo_light` → Salida 1 en ventana). Probado con **3 monitores**, todos al 100 % (1366×768, 2560×1440 en −2560,−360 y 1920×1080 primario): `GetWindowRect` == monitor en los 3 (python y exe, también al reiniciar); monitor ausente → primario con aviso, y se conserva el guardado. **CPU** (audio sintético a 100 bloques/s, 3–4 s por corrida porque tapa las pantallas): 3 salidas a pantalla completa 9,6–11,7 % (media ~10,7 %) en el look 2; con el logo de una salida local visible (look 1) 12,6–15,1 %; 2 salidas 8,7 %; 3 en ventana 7,2–9,0 %; F4 con el mismo arnés 7,0–10,4 %; exe sin audio 3,8 %. ⚠️ Las atenuaciones (cola del decay) se pintan como mucho cada 16 ms: subir de brillo, cambiar de color o cortar a negro se pinta ya (bajó de 12,1 a 9,6 %). Keep-awake: estado del sistema 0x0 → 0x3 → 0x0. Control: 1085×576 al 100 % y ~1452×787 al 150 % (`tk scaling`). Las teclas se pausan mientras se escribe en un campo de texto. `.\build.ps1` OK (57,1 MB). Pendiente manual: DPI mixto, `powercfg /requests` como administrador, bordes, barra de tareas, cursor y logo a ojo, audio real con 3 salidas. |
| F6 | [Pantalla remota por red (TV grande)](F6-red.md) | F5 | ✅ | 2026-11-22: `lighthouse/net.py` (`Sender` automático por broadcast ligado a cada IPv4 local, re-enumera cada 5 s en un hilo, o IP fija; `Receiver`, `SeqFilter`; paquete de 14 bytes, keepalive 40 Hz desde `App.fast()`), `RemoteOutput` en `outputs.py` (preset "Agregar TV remota": excepto en 1, logo, master 30 %), `pantalla.py` (`--pantalla [--puerto] [--monitor] [--logo]`, config bajo `pantalla`; `config.save` ya no la pisa), `LEEME.txt` sección "Dos laptops". Probado en la **misma máquina** (IP fija 127.0.0.1 y broadcast Automático con receptor 0.0.0.0): look 1 logo, look 2 color, sin emisor → logo; **no se probó con dos PCs**. CPU emisor ~6,6 % (sin audio, 1 local + 1 remota); receptor exe 0,8 %. `.uild.ps1` OK (57,1 MB). Pendiente manual: dos PCs (cable/hotspot, desfase a 240 fps), firewall en el receptor, fundido y logo a ojo. |

Leyenda: ⬜ pendiente · 🔄 en curso · ✅ hecha.

**Notas de F4 para F5:**
- **`Engine.sample(delay_s=0.0) -> Snapshot(out, n, gate, t)`**: estado de hace `offset + delay_s`. Se llama sin lock desde el hilo Tk. El historial guarda 64 bloques (~640 ms): alcanza para offset 300 + retardo 200 ms; si se pide más, subir `maxlen`. `out` ya trae modo, master, piso y gamma; blackout y bump **no** (los decide `compose`).
- **`scene.compose(snap, scene, cfg) -> Frame(left, right, logo_visible)`**: pura, la única que decide colores.
  - `Cfg(master, gamma, base, colors)` es lo de cada salida: la TV con master ~30 % usa su propio `Cfg` y su propio `sample(delay)`.
  - `unirse_a_looks` se decide fuera de `compose`. Para una salida no unida, por ejemplo, compón con `Scene(look="1")`, copiando `bump`/`blackout`.
  - `logo_visible` es `True` solo en el look 1 sin bump **ni blackout**.
- `Scene.n0` y `Scene.t0` se toman de `sample()` sin retardo extra. `compose` usa `k = max(n - n0, 0)`, así que una salida retrasada no ve un `k` negativo.
- **Pintar con `Frame` + `bg`, nunca con `Canvas`**: a pantalla completa, el Canvas cuesta ~7 ms por pintado. Repintar solo si cambió (como `App.painted`).
- Las teclas ya miran `win32.app_in_foreground()` (cualquier ventana del proceso, incluidas las salidas sin bordes de F5). No hace falta foco de Tk.
- La ventana Control creció a 1079×763 (antes ~1048×661): revisar en pantallas de 768 px / DPI.

**Notas de F5 para F6:**
- **`outputs.compose_output(snap, scene, cfg, rule, master, logo) -> Frame`**: pura; el emisor puede componer la TV remota con su propia config de salida (mismos campos que `outputs` en `config.json`: `master`, `retardo_extra_ms`, `contenido`, `logo`, `unirse_a_looks`) y mandar el `Frame` ya resuelto.
- El receptor puede reutilizar `Output` (`render(frame, now)`); sin red, `Frame(BLACK, BLACK, True)` muestra solo el logo.
- El logo con transparencias cuesta ~2 ms por cambio de fondo (Tk re-mezcla el alfa): en la laptop DJ suma ~3 % si una salida local lo muestra; en el receptor no importa.

**Descartadas tras las respuestas del cliente:**
- **Gamepad**: "solo estaba cruzado en el camino".
- **Overlay sobre otro software**: la TV no usa VLC, OBS ni Resolume.

## Contexto del cliente

Fuentes: `contextovideo.md` (transcripción de su video), capturas de WhatsApp, cuadros del video y sus respuestas al cuestionario.

### Hardware y setup (confirmado)

- **Laptop DJ**:
  - rekordbox + **Pioneer DDJ-FLX6** (salidas **master RCA** y **booth RCA**).
  - Hoy maneja las **dos pantallas chicas** con un **código HTML en el navegador**. Captura el audio de la ventana de rekordbox "como videollamada", reacciona a los graves y él cambia la respuesta con **teclas del teclado**.
- **Laptop de visuales**: 1 HDMI, 2 USB-C y 2 USB 3.0. Hoy **no** corre ningún programa de visuales.
- **Pantalla grande**: **TV de 43"**, detrás del DJ y de cara al público. Es de un depa rentado: no se mueve.
- **Steinberg UR12**: interfaz que pensaba usar para llevar el booth a la laptop de visuales.
- **Bocinas extra** (para sonido envolvente): todavía no las tiene conectadas; las piensa añadir por el **booth**. Las bocinas principales **no** tienen THRU/LINK.
- **Dispara los looks él mismo, con el teclado.** No hay asistente ni gamepad.
- **Lo que pide**:
  - Que la TV muestre su **logo** con un video "un poquito **menos** fuerte".
  - **Solo cuando él decide**, que se una en color con las pantallas chicas.
  - **No sacrificar el booth** para las bocinas.
  - **Menos cables.**
  - Que se vea **muy reactivo**.

### Referencia visual

Skrillex, EDC México 2024 ([YouTube EDPu0fxvrIc](https://www.youtube.com/watch?v=EDPu0fxvrIc&t=339s)), min ~5:39–5:55, "Ratata":
- La pantalla LED completa en **un solo color rojo saturado**.
- **Cortes duros prendido/apagado contra negro** en los golpes, con **negro real** entre golpes.
- Láseres del mismo color.

### Mapa de teclas del cliente (literal; manda sobre cualquier otra propuesta)

| Tecla | Look |
|---|---|
| 1 | Blanco |
| 2 | Rojo |
| 3 | Azul |
| 4 | Morado |
| 5 | Verde |
| 6 | Amarillo |
| 7 | Un color diferente por cada golpe, en el orden del arcoíris |
| Q | Estrobos alternando cada golpe entre blanco y rojo (1 y 1) |
| W | Estrobos alternando cada golpe entre blanco y morado (1 y 1) |
| E | Estrobos con la pantalla partida a la mitad, alternando izquierda/derecha entre sí; al inicio izquierda negra y derecha roja |
| R | Igual que E, con la derecha morada |
| T | Igual que E, con la derecha verde |
| Y | Igual que E, con la derecha azul |
| U | Morado que sube de intensidad en 4 s y baja en 4 s, en bucle (ciclo de 8 s) |
| Z | Negro total, sin responder a ningún golpe ni sonido |

**Aclaraciones del cliente:**
- **E–Y**: el lado de color "**se apaga cuando deja de recibir la señal**", es decir, sigue al golpe.
- **7**: cambia de color **por cada golpe**.
- **Límite de destellos**: no sabe cuál conviene, pero le importa que se vea **muy reactivo**.

## Topología decidida

```
LAPTOP DJ (rekordbox + LightHouse "emisor")
  ├─ audio: loopback WASAPI de la salida que usa rekordbox   ← sin cables, como hoy el HTML
  ├─ teclado del DJ → looks
  ├─ salidas de video → 2 pantallas chicas                     (como hoy)
  └─ red (Ethernet directo o hotspot Wi-Fi propio) ─────────┐
                                                             ▼
LAPTOP DE VISUALES (LightHouse "pantalla", sin audio) ─HDMI─► TV 43" (logo + se une a los looks)

DDJ-FLX6: master → bocinas principales · booth → bocinas extra (libre)
```

**Por qué esta topología:**
- Elimina el cable de audio hacia la laptop de visuales.
- **Libera el booth** para las bocinas extra.
- Usa **un solo análisis**: todas las pantallas en sincronía exacta.
- El DJ dispara todo desde **el mismo teclado** que ya usa.

**Riesgos y mitigación:**
- **Carga en la laptop DJ**:
  - LightHouse mide 0,4 % de un núcleo de motor y 6–9 % en total con loopback (medido en F2; meta < 10 %), con prioridad baja.
  - Corre con **prioridad de proceso baja** (F2): rekordbox siempre gana.
- **Atajos de rekordbox**: si se leen las teclas de forma global, 1–7, Q, W, Z… también llegarían a rekordbox si está al frente.
  - **Por defecto las teclas solo funcionan con LightHouse al frente**, igual que hoy con el HTML.
  - Modo global opcional, con advertencia.
- **Loopback y ASIO**: si rekordbox usara ASIO, el loopback no ve el audio. Como el HTML ya lo captura, la ruta WASAPI existe. **Verificar en sitio** que el medidor se mueve.
  - Respaldo: booth (Y) → UR12 → entrada de la laptop DJ.
- **Red**:
  - Preferible **cable Ethernet directo**: con adaptador USB-C/USB 3.0 si la laptop no tiene puerto.
  - Alternativa sin cables: **hotspot propio** en 5 GHz.
  - **Nunca el Wi-Fi del lugar.**
  - Si se cae la red, la TV muestra **solo el logo** (no negro).

**Alternativa sin segunda laptop**: si la laptop DJ tiene una salida de video libre y la TV está a ≤ 10–15 m, un cable HDMI directo elimina la red. Entonces F6 no hace falta.

**Respaldo de audio** (si falla el loopback):
- **Y RCA** en un canal del booth → **entrada 2 Hi-Z** de la UR12 → laptop DJ. La otra pata de la Y va a la bocina extra.
- **+48V apagado** y ganancia baja.
- AGC apagado: **la perilla de booth = sensibilidad**, como pidió el cliente. El modo "Fija" de F2.

## Arquitectura decidida

Validada por el agente arquitecto Python, con mediciones en esta máquina.

### Modelo

- **Un solo proceso**:
  - Hilo de audio de PortAudio (callback de 10 ms) → `Engine.process`, puro.
  - Hilo Tk → render.
- **Composición** con una función pura `compose(estado_motor, escena, cfg_salida) -> Frame` (color izquierdo, color derecho, visibilidad del logo).
- **Salidas**:
  - Ventanas Tk sin bordes, una por monitor (F5).
  - Salida **remota** por UDP hacia la laptop de visuales (F6).
- **Por qué no otras opciones** (medido):
  - `Engine.process` cuesta 42 µs por bloque y pintar a pantalla completa 0,18 ms. No hace falta multiproceso ni bus de eventos.
  - pygame/SDL es el plan B, solo si una medición con cámara a 240 fps muestra que domina el compositor.
  - Qt (+80–120 MB) y web kiosk (+1 frame) quedan descartados.

### Paquete

Cada módulo se crea en la fase indicada; no antes.

| Módulo | Fase | Responsabilidad |
|---|---|---|
| `lighthouse/__main__.py` | F1 | Arranque, logging, `--test` (en F6 también `--pantalla`) |
| `lighthouse/engine.py` | F1 | DSP puro: golpe, BPM, calma, tempo y luz |
| `lighthouse/audio.py` | F1 | Enumerar dispositivos, abrir y cerrar stream, mezcla de canales |
| `lighthouse/ui.py` | F1 | Ventana de control (y la ventana Luz hasta F5) |
| `lighthouse/config.py` | F1 | JSON con `version`, escritura atómica, cargador tolerante |
| `lighthouse/selftest.py` | F1 | Self-checks con `assert`; se empaquetan en el exe (`--test`) |
| `lighthouse/win32.py` | F2 | Todo el ctypes: prioridad, teclas, monitores, DPI, keep-awake |
| `lighthouse/scene.py` | F4 | Looks y `compose()`, puro y testeable |
| `lighthouse/outputs.py` | F5 | Ventanas de salida por monitor |
| `lighthouse/net.py` | F6 | Emisor y receptor UDP |

### Latencia

Presupuesto medido/estimado por el arquitecto:

| Etapa | Hoy | Cambio | Objetivo |
|---|---|---|---|
| Captura WASAPI compartido | 10–22 ms (medido) | Ninguno | 10–22 ms |
| Detección (RMS 40 ms + flujo) | ~19 ms mediana (medido) | El límite real es el filtro de graves | ~15–19 ms |
| Salto al render | `after(15)` = 15,6 ms de periodo, máx 28 (medido) | **Hilo `render` por bloque de audio → `App.fast()` en el hilo Tk**: mediana 0,2 ms, p99 ~1 ms (medido en F2). `after(1)` queda descartado: gira al ~98 % de un núcleo en Tcl 8.6 | ≤ 1 ms |
| Pintado Tk | 0,18 ms (medido) | — | — |
| DWM + scanout a 60 Hz | 16–25 ms (estimado) | Solo SDL/D3D con flip directo (plan B) | igual |
| TV / monitor | 5–15 ms; TV sin Modo Juego 30–120 ms | **Modo Juego en las TV** | 5–20 ms |
| Red (solo la TV remota) | — | Ethernet < 1 ms; Wi-Fi propio 2–10 ms | < 10 ms |
| **Total** | **~65–120 ms** | | **~50–70 ms** |

- **Offset unificado** de −150…+300 ms que reemplaza el retardo actual.
  - Valores negativos (anticipación) solo en modo *Al tempo* con BPM fiable.
  - Default 0. Calibrar en sitio: una luz adelantada se nota más que una atrasada.
- **Retardo extra por salida** (0–200 ms): cada TV tiene su propio retraso.
- Descartado:
  - Bloques de 256.
  - `timeBeginPeriod`.
  - WASAPI exclusivo/ASIO.
  - Ableton Link.

### Ejecutable

- PyInstaller ≥ 6.15 (soporta 3.14), en **onedir**, windowed y sin UPX.
- Venv de build limpio con versiones fijadas.
- **Sin scipy**: biquads RBJ propios. Ahorra 60–80 MB y 2 s de arranque.
- Exe estimado: ~50 MB.
- Rutas:
  - Config: `%APPDATA%\LightHouse\config.json`.
  - Logs: `%LOCALAPPDATA%\LightHouse\logs\`.
- **El mismo exe sirve para las dos laptops**: modo normal (emisor) y `--pantalla` (receptor, F6).

## Decisiones de diseño (para que las sesiones no las re-discutan)

### Looks

- Cada tecla **selecciona un look que se queda activo (latch)** hasta elegir otro.
- Todos siguen la música salvo **U** (temporizado) y **Z** (negro).
- Look inicial: **1 Blanco**.

| Look | Color | Comportamiento |
|---|---|---|
| 1 | Color base del panel Color (blanco, temperatura o paleta) | Intensidad = salida del motor |
| 2–6 | Rojo `#FF0000`, Azul `#0030FF`, Morado `#8000FF`, Verde `#00FF00`, Amarillo `#FFD000` | Intensidad = salida del motor |
| 7 | Arcoíris `#FF0000 #FF7F00 #FFFF00 #00FF00 #0000FF #4B0082 #8F00FF` | Avanza un color por **cada golpe** (destello) |
| Q / W | Alterna blanco ↔ rojo / blanco ↔ morado | **Estrobo con compuerta** |
| E / R / T / Y | Pantalla partida; la izquierda empieza negra y la derecha con color (rojo / morado / verde / azul) | Los lados se intercambian en cada golpe. **Estrobo con compuerta** |
| U | Morado, onda triangular 0 → master en 4 s y master → 0 en 4 s | Ignora el audio |
| Z | Negro | Ignora todo, salvo el bump |

**Estrobo con compuerta (Q–Y)**: "se apaga cuando deja de recibir la señal".
- El color se **enciende a tope** en cada golpe.
- Se mantiene **mientras el golpe suena**: nivel de banda ≥ `cierre` × el nivel máximo desde el golpe. `cierre` default 0.5, rango 0.2–0.9.
- Dura como mínimo `strobe_min_ms` (default 40 ms) y luego se corta a **negro real** (piso 0, sin decay).
- Un destello **sin golpe** (tick de tempo en un breakdown) dura solo `strobe_min_ms`. Si llega un golpe con la compuerta abierta, vuelve a aplicar la regla de `cierre` (F4).

**Bump** (mantener `F`):
- Sólido al 100 % del color del look, ignorando piso, gamma, decay y offset.
- Es el "Ratata" manual.

**Blackout** (`Espacio`): gana sobre todo.

**Reactividad** (el cliente la pide):
- Preset **"Muy reactivo"**: refractario 140 ms, límite 6 Hz, decay 120 ms, piso 0 y sensibilidad 1.8. Junto a "Normal" (los defaults actuales).
- **Sensibilidad en vivo**: `+` / `−` (también los del teclado numérico) suben o bajan la sensibilidad. Reemplaza a la perilla de booth cuando el audio es loopback.

**Límite de destellos** (seguridad):
- Activo por defecto a **6 Hz**: deja pasar redobles de kick a 1/8 hasta 180 BPM y frena los de 1/16. Configurable 3–10 Hz.
- Desactivable a conciencia, con advertencia: el rojo saturado a pantalla completa entre 3 y 30 Hz es lo más provocador para la epilepsia fotosensible.
- Avisar a los invitados.
- El bump manual no se limita.

**Teclas**:
- Se leen con `GetAsyncKeyState` en el tick, para que funcionen aunque el foco esté en una ventana de salida sin bordes.
- Por defecto **solo con LightHouse al frente** (la laptop DJ tiene rekordbox con sus propios atajos).
- "Teclas globales" opcional, con advertencia.

**Atajos reasignados** por choque con el mapa del cliente:

| Atajo | Antes | Ahora |
|---|---|---|
| Modos Auto/Pulso/Tranquilo/Manual | 1–4 | **F1–F4** |
| Tap tempo | T | **0** |
| Blackout | `Espacio` | `Espacio` (se mantiene) |
| Bump | `F` | `F` (se mantiene) |

- Teclado numérico equivalente.
- Mapa editable en `config.json`.

### Salidas

- **Regla `unirse_a_looks`** por salida: `siempre` / `excepto en 1` / `nunca`.
  - Unida → muestra el look y **oculta el logo**.
  - No unida → su contenido propio: luz base × master, con el logo si aplica.
  - Blackout y bump afectan a todas.
- **Caso del cliente**:
  - Pantallas chicas: `siempre`.
  - TV grande (remota): `excepto en 1`, con logo y master ~30 %. En el look 1 respira tranquila con su logo; al elegir cualquier otro look se une en color.

## Validación con agentes Fable

### Experto AV

**Corrigió:**
- El video que pide es "menos fuerte", no "más fuerte".
- Es un depa, no un venue.
- La FLX6 tiene master y booth RCA, sin XLR (confirmado por el cliente).

**Aportó:**
- Retardo por salida.
- Negro real y corte duro en los golpes.
- Problema del foco del teclado.
- Logo oculto durante el golpe.
- Seguridad fotosensible.
- Checklist de show.

### Arquitecto Python

**Midió:**
- `after()`.
- Costo del motor y del pintado.
- Latencia de captura y de detección.
- Rectángulos de monitor con `overrideredirect`.

**Recomendó:**
- Un proceso.
- Quitar scipy.
- PyInstaller onedir.
- Teclas por `GetAsyncKeyState`.
- Config con `version`.
- UDP con el estado ya renderizado.

### Tras las respuestas del cliente

- La red pasa de opcional a **topología principal**: el análisis se hace en la laptop DJ, igual que hoy con el HTML.
- La UR12 queda de respaldo.
- Gamepad y overlay se descartan.

## Preguntas pendientes (no bloquean F1–F5)

1. ¿A cuántos metros queda la TV de la laptop DJ y de la laptop de visuales? ¿Las laptops tienen puerto Ethernet? → define cable vs hotspot en F6.
2. ¿Cómo conecta hoy la laptop DJ las dos pantallas chicas: dos salidas de video o una duplicada? → define las salidas en F5.
3. ¿rekordbox tiene activos atajos de teclado (Preferencias → Teclado)? → confirma el default "teclas solo con LightHouse al frente".
4. **Verificación en sitio**: con LightHouse en la laptop DJ, elegir el loopback del dispositivo de salida de rekordbox y confirmar que el medidor se mueve.

## Checklist de show (para el cliente)

1. LightHouse en la laptop DJ: el medidor se mueve con rekordbox. Las teclas responden con LightHouse al frente.
2. Modo Juego en todas las TV y retardo calibrado por pantalla.
3. Laptops con corriente; sin suspensión, notificaciones ni actualizaciones.
4. Red entre laptops por cable o hotspot propio. La TV muestra el logo si se desconecta.
5. Probar cada look, el blackout, el bump y soltar la tecla.
6. Bajar la música: la luz cae a calma, no se congela.
7. Si falla el loopback: respaldo booth → Y → UR12 (+48V apagado). Si falla todo: tap tempo (`0`) + looks manuales.
8. Cables fijados con cinta y cable de repuesto a la mano. Mantener el HTML actual como respaldo.

## Reglas comunes a todas las sesiones de fase

Cada prompt las repite.

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**:
  - Sin `commit`, `push`, ramas, `stash` ni `reset`.
  - Al terminar, **solo sugerir** el mensaje de commit y la lista de archivos.
- **Dependencias**: solo las que lista la fase. Cualquier otra se **pregunta**.
- **Alcance**:
  - Solo lo de la fase. No adelantar fases siguientes ni reescribir lo que funciona.
  - Si el diseño decidido resulta imposible, detenerse y proponer alternativas.
- **Cierre**:
  - La app queda funcionando.
  - `python -m lighthouse --test` pasa; desde F3 **toda fase corre `.\build.ps1` al final** y el exe debe pasar `--test`.
  - Actualizar la tabla **Estado** (✅, fecha, nota de una línea) y añadir notas para la siguiente fase si algo cambió.
