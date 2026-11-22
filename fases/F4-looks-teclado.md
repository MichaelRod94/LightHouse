# Fase F4: Looks por teclado (mapa del cliente), estrobos con compuerta y reactividad

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior: Windows (ctypes/Win32), Tkinter y lógica de show en vivo. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** es una app de escritorio Python para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz: ventanas de color sólido que funcionan como luces.
- Corre en la **laptop DJ junto a rekordbox**, que tiene **sus propios atajos de teclado**. El DJ elige los looks con ese mismo teclado.
- Paquete `lighthouse/`: `engine.py`, `audio.py`, `ui.py`, `config.py`, `win32.py` (ctypes, creado en F2), `selftest.py` y `__main__.py`.
- `build.ps1` genera el exe.
- El motor ya produce:
  - `out` (intensidad 0..1 según modo Auto/Pulso/Tranquilo/Manual);
  - `flashes` (contador de destellos: golpes o ticks de tempo, respetando el divisor);
  - el nivel de banda `lb`;
  - historial para el offset.

**Mapa de teclas pedido literalmente por el cliente** (manda sobre cualquier otra propuesta):

| Tecla | Pedido del cliente |
|---|---|
| 1 | Blanco |
| 2 | Rojo |
| 3 | Azul |
| 4 | Morado |
| 5 | Verde |
| 6 | Amarillo |
| 7 | Un color por cada golpe, diferente, en el orden de los colores del arcoíris |
| Q | Los estrobos alternan cada golpe en blanco y rojo (1 y 1) |
| W | Los estrobos alternan cada golpe en blanco y morado (1 y 1) |
| E | Estrobos con la pantalla partida a la mitad, dos colores alternando de izquierda a derecha entre sí. Al principio la izquierda es negra y la derecha roja |
| R | Igual, con la derecha morada |
| T | Igual, con la derecha verde |
| Y | Igual, con la derecha azul |
| U | Morado que sube su intensidad en 4 s y la baja en 4 s, en bucle (8 s por repetición) |
| Z | Negro total, sin responder a ningún golpe ni sonido |

**Aclaraciones del cliente:**
- En los estrobos, el color "**se apaga cuando deja de recibir la señal**".
- El 7 cambia **por cada golpe**.
- Quiere que se vea **muy reactivo**.

Referencia visual: Skrillex en EDC México 2024, "Ratata". La pantalla entera en un color saturado con **cortes duros prendido/apagado contra negro** en los golpes.

## Lee primero

1. `fases/README.md`: *Mapa de teclas del cliente*, *Decisiones de diseño → Looks* (estrobo con compuerta, bump, blackout, reactividad, límite de destellos, teclas y atajos reasignados) y *Estado*. **Respeta lo decidido.**
2. `lighthouse/engine.py`, `lighthouse/ui.py`, `lighthouse/config.py`, `lighthouse/win32.py` y `lighthouse/selftest.py`.

## Precondiciones

- `fases/README.md` marca **F3 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.

## Objetivo

1. Implementar los **15 looks** como escenas **latch** (cada tecla deja el look activo hasta elegir otro).
2. **Estrobos con compuerta**.
3. **Reactividad configurable**.
4. **Sensibilidad en vivo** por teclado.
5. Lectura de teclas sin depender de las ventanas de Tk.
6. Reasignar los atajos que chocan.

## Alcance

### Entra

**`engine.py`**

- **Compuerta de golpe**, calculada por bloque:
  - Se **abre** en cada destello y registra el pico de `lb` desde que abrió.
  - Se **cierra** cuando `lb < cierre × pico` **y** ya pasaron `strobe_min_ms`.
  - Queda cerrada hasta el siguiente destello.
  - Perillas: `cierre` (0.2–0.9, default 0.5) y `strobe_min_ms` (20–120, default 40).
- **`sample(delay_s=0.0) -> Snapshot`**, con:
  - `out` (intensidad con offset);
  - `n` (contador de destellos en ese instante);
  - `gate` (compuerta abierta o no);
  - `t` (tiempo del motor).
- El historial guarda por bloque `(out, flashes, gate)`. `delay_s` es un retardo **extra** que F5 usará por salida.
- **Limitador configurable**: `flash_limit` (bool, default `True`) y `flash_limit_hz` (3–10, default **6**).
  - Con el limitador activo, un destello que llega antes de `1/flash_limit_hz` del anterior **se descarta**: no incrementa `flashes`, no dispara el pulso ni abre la compuerta.
  - Reemplaza la regla actual de "media profundidad a menos de 333 ms".

**Nuevo `lighthouse/scene.py`** (puro, sin Tk ni ctypes)

- `LOOKS`: los 15 looks con estos colores:

  | Look | Hex |
  |---|---|
  | Rojo | `#FF0000` |
  | Azul | `#0030FF` |
  | Morado | `#8000FF` |
  | Verde | `#00FF00` |
  | Amarillo | `#FFD000` |
  | Arcoíris | `#FF0000 #FF7F00 #FFFF00 #00FF00 #0000FF #4B0082 #8F00FF` |

  Colores y mapa de teclas son editables en `config.json`; sin editor en la UI.

- `Scene`: estado mínimo.
  - Look activo.
  - `n0`: valor de `n` al seleccionar el look.
  - `t0`: tiempo al seleccionar, para U.
  - Bump mantenido.
  - Blackout.
- `compose(snap, scene, cfg) -> Frame(left: RGB, right: RGB, logo_visible: bool)`: pura y determinista.
  - Con `k = snap.n - scene.n0` (destellos desde que se eligió el look):
    - **1**: color base del panel Color actual (blanco, temperatura o paleta) × `snap.out`.
    - **2–6**: color fijo × `snap.out`.
    - **7**: `ARCOIRIS[k % 7] × snap.out`. Empieza en rojo y avanza un color por golpe.
    - **Q / W**: con `snap.gate` abierta: `k` impar → blanco; `k` par → rojo o morado, a **master**. Con la compuerta cerrada o `k == 0` → **negro real** (sin piso ni gamma).
    - **E / R / T / Y**: con `snap.gate` abierta: `k` impar → izquierda negra, derecha color; `k` par → izquierda color, derecha negra. Con la compuerta cerrada o `k == 0` → ambas mitades negras.
    - **U**: morado × triángulo `((snap.t - t0) mod 8)`: sube 0→1 en 4 s y baja 1→0 en 4 s. Escala por master, aplica gamma e ignora el audio.
    - **Z**: negro; ignora el audio.
  - **Bump** (tecla mantenida): sólido al 100 % del color principal del look. Ignora piso, gamma, decay y offset. Funciona incluso en Z.
    - Para Q/W el color es blanco; para E–Y, el color de su lado de color; para 7, el color actual; para U, morado; para Z, blanco.
  - **Blackout**: negro sobre todo, incluido el bump.
  - `logo_visible`: `True` solo en el look 1 sin bump. Lo usarán F5 y F6.

**`win32.py`** (ya existe; agrega)

- `key_down(vk) -> bool` con `GetAsyncKeyState(vk) & 0x8000`.
- `app_in_foreground() -> bool`: compara `GetWindowThreadProcessId(GetForegroundWindow())` con `os.getpid()`.

**Teclas (`ui.py`)**

- **Sondeo en `App.fast()`**, con detección de flanco: acción al presionar. Para F: mientras está presionada.
  - `App.fast()` lo llama el hilo `render` en cada bloque de audio (~10 ms) y el loop lento a 30 Hz cuando no hay audio.
  - **No agregues timers `after(n)` cortos**: en Tcl 8.6 `after(1)` gira al ~98 % de un núcleo (medido en F2).
- **Quitar los `bind_all`** de teclas de show, para no disparar dos veces.
- **`Teclas globales`** (default **`False`**). Apagada, solo responde con `app_in_foreground()`.
  - Así se comporta como hoy la página HTML del cliente, y no compite con los atajos de rekordbox.
  - Al activarla, mostrar la advertencia: *"Las teclas también llegarán a rekordbox si está al frente"*.
- **Mapa final** (los VK salen del mapa en la config, con estos defaults):

  | Tecla | Acción |
  |---|---|
  | `1`–`7` y numérico `1`–`7` | Looks 1–7 |
  | `Q` `W` `E` `R` `T` `Y` `U` `Z` | Looks del cliente |
  | `Espacio` | Blackout (alterna) |
  | `F` mantenida | Bump |
  | `F1`–`F4` | Modos Auto / Pulso / Tranquilo / Manual (antes 1–4) |
  | `0` y numérico `0` | Tap tempo (antes T) |
  | `+` / `−` (`VK_OEM_PLUS`, `VK_OEM_MINUS`, `VK_ADD`, `VK_SUBTRACT`) | Sensibilidad ±0.1, en el rango 1.0–3.0, reflejada en su slider |

**UI**

- **Panel `Looks`**: cuadrícula de 15 botones ("1 Blanco", "Q Blanco/Rojo"…) con muestra de color. El activo va resaltado; también se seleccionan con el mouse. El look activo se muestra en grande en las lecturas.
- **Estrobos**: `Cierre del golpe` (0.2–0.9) y `Mínimo (ms)`.
- **`Respuesta`**: combo de presets con el mecanismo de presets existente.
  - **Normal**: defaults actuales.
  - **Muy reactivo**: refractario 140 ms, límite 6 Hz, decay 120 ms, piso 0, sensibilidad 1.8.
- **`Limitar destellos`** (checkbox) + `Máx. destellos/s` (3–10), con la advertencia: *"Rojo saturado a pantalla completa > 3 Hz puede provocar crisis en personas fotosensibles"*.
- **`Teclas globales`** con su advertencia.
- Actualizar la leyenda de atajos.

**Ventana Luz**

- Pasa a `Canvas` con **dos rectángulos** (mitades izquierda y derecha).
- Solo se actualiza lo que cambia.
- Sigue siendo una sola ventana; la multiventana es F5.

**Config**

- `version` +1.
- Persistir mapa de teclas, colores, `cierre`, `strobe_min_ms`, limitador, teclas globales y preset de respuesta.
- **No** persistir el look activo: siempre arranca en 1 Blanco.

**Self-check** (agregar a `selftest.py`)

1. **Compuerta** con el groove sintético existente (kick 55 Hz a 120 BPM): en cada destello se abre, dura ≥ 40 ms y se cierra **antes** del siguiente kick (< 450 ms). En modo tempo, un tick sin kick (breakdown) la abre solo ~`strobe_min_ms` (≤ 60 ms).
2. **Q** (`compose` con snapshots sintéticos): `gate=True` con `k` = 1, 2, 3 → blanco, rojo, blanco; `gate=False` → negro; `k=0` → negro.
3. **E**: `k=1` y `gate` → (negro, rojo); `k=2` → (rojo, negro); `gate=False` → (negro, negro).
4. **7**: `k` = 0…7 → rojo, naranja, amarillo, verde, azul, índigo, violeta, rojo.
5. **U**: `t − t0` = 0 → 0; 4 → master; 8 → 0; 2 → ~0.5 × master (antes de gamma). Ignora `out`.
6. **Z** → negro con cualquier `out`. Z + bump → blanco. Blackout gana sobre el bump.
7. **Limitador** a 6 Hz con golpes cada 0.1 s → `flashes` aumenta como máximo 1 cada 1/6 s.
8. **`sample(delay_s)`** devuelve el estado de hace `delay_s` (mismo patrón que la prueba de retardo existente).

### No entra

- Varias ventanas, monitores, pantalla completa sin bordes y logo (F5). Red (F6).
- Editor de mapa de teclas en la UI.
- Looks nuevos no pedidos.

## Diseño decidido

- Looks **latch** (pedido del cliente). Todos siguen la música salvo U y Z.
- `compose` es la **única** función que decide colores. La ventana solo pinta un `Frame`.
- Las teclas se leen con `GetAsyncKeyState`: las ventanas sin bordes de F5 no reciben foco de Tk. "Solo con LightHouse al frente" se decide con el proceso en primer plano, no con el foco de Tk.

## Criterios de aceptación

1. Self-check completo pasa, incluidas las 8 pruebas nuevas.
2. **Manual, con música**:
   - cada una de las 15 teclas cambia el look según la tabla;
   - en Q–Y el color dura lo que suena el golpe, con **negro real** entre golpes;
   - E–Y alternan de lado;
   - el 7 avanza por golpe;
   - U respira en 8 s;
   - Z queda en negro aunque suene música;
   - F mantenida da sólido;
   - Espacio apaga todo.
3. Con `Teclas globales` **apagada** y el Bloc de notas al frente, las teclas **no** hacen nada. Con LightHouse al frente (incluida una ventana Luz) **sí**. Encendida, funcionan con el Bloc de notas al frente.
4. `F1`–`F4` cambian de modo, `0` hace tap y `+`/`−` mueven la sensibilidad. Las teclas viejas (`1`–`4` para modos, `T` para tap) ya no lo hacen.
5. El preset **Muy reactivo** se siente claramente más reactivo en un drop (redobles a 1/8 visibles).
6. `.\build.ps1` pasa y el exe responde a las teclas.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Alcance**: cambios mínimos. No adelantes F5 o F6. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`: F4 → ✅, fecha y nota de una línea. Agrega notas para F5 sobre `sample`, `compose`, `Frame` y `Snapshot`.
2. Responde al usuario con:
   - qué cambió;
   - cómo probar cada look;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(looks): mapa de teclas del cliente, estrobos con compuerta y preset reactivo`) y la lista de archivos.

   **No hagas el commit.**
