# Fase F9: Modo mini (junto a rekordbox), siempre encima y tecla F9

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior: Tkinter/ttk y Windows (ctypes/Win32: estilos de ventana, foco, siempre encima). Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes.

Paquete `lighthouse/`: `engine.py`, `audio.py`, `scene.py`, `outputs.py`, `net.py`, `pantalla.py`, `win32.py` (**todo** el ctypes), `config.py` (v6 desde F8), `theme.py` (tokens, F7), `layout.py` (`pick` / `plan`, F8), `selftest.py`, `ui.py` (ventana **Control**, responsive desde F8) y `__main__.py`.

**El caso de uso de esta fase**: la laptop del DJ tiene **rekordbox ocupando casi toda la pantalla**. LightHouse debe ocupar lo mínimo y seguir siendo útil: ver el look activo, cambiarlo, ver que llega señal y poder apagar todo.

Un detalle que manda sobre el diseño: **las teclas de show solo llegan con LightHouse al frente** (salvo "Teclas siempre activas"). Con rekordbox al frente, el DJ tiene que saber de un vistazo si sus teclas van a LightHouse o no, y poder cambiar de look con el ratón.

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos**. El pintado de las salidas vive en `App.fast()`; los indicadores de Control, en `App.slow()` (~30 Hz) con `App.put()`.
- Las teclas de show se leen con `GetAsyncKeyState` y se pausan al escribir en un campo de texto.
- ctypes solo en `win32.py`. Config JSON versionada.

## Lee primero

1. `fases/README.md`: *Estado*, *Decisiones de diseño → Teclas*, sección *Etapa 2: interfaz* (notas de F8).
2. `fases/diseno-ui.md`: **§3.2 (condición de mini), §3.3 (cómo se cambia), §3.5 (wireframes "Mini — tira" y "Mini — bloque" y tamaños), §4, §8, §11**.
3. `lighthouse/ui.py`, `lighthouse/layout.py`, `lighthouse/win32.py`, `lighthouse/config.py`, `lighthouse/selftest.py`, `LEEME.txt`.

## Precondiciones

- `fases/README.md` marca **F8 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.
- **Antes de tocar código**, mide la línea base de CPU con el arnés (ver *Verificación*).

## Objetivo

1. Una **vista Mini** con dos formas según el ancho: **tira** (una fila) y **bloque** (looks en dos filas).
2. Entrar y salir de Mini a mano (selector Vista, botón Ampliar, **tecla F9**) y sola al encoger la ventana.
3. **Siempre encima** opcional, con geometría propia recordada.
4. Experimental y opcional: que un clic en el mini **no le quite el teclado a rekordbox**.

## Alcance

### Entra

**`ui.py`: vista Mini**
- Cuando `layout.pick` devuelve `mode == "mini"`, Control muestra **solo**:
  - punto de golpe, medidor reducido y BPM;
  - los 15 looks (1 fila si el ancho ≥ 760 px lógicos; si no, 2 filas: `1–7 Q` y `W E R T Y U Z`), con el activo resaltado;
  - vista previa, **Blackout**, interruptor **Siempre encima** y botón **Ampliar**;
  - una línea de estado: `Look 2 · Rojo · AUTO·PULSO · Teclas: …`. SIN SEÑAL / SATURA sustituyen al estado del modo (las alarmas mandan); el look activo y `Teclas: …` no se quitan nunca.
- **Reparto** (wireframes de §3.5; el del prompt anterior no cabía):
  - **tira**: fila 1 = los 15 looks + Blackout (15 × 44 + 96 px ya llenan los 800); fila 2 = punto, BPM, medidor, línea de estado, vista previa, Siempre encima y Ampliar.
  - **bloque**: fila 1 = punto, BPM, medidor, vista previa, **Blackout**, Siempre encima y Ampliar; filas 2 y 3 = looks; fila 4 = línea de estado (el estado del modo solo si cabe).
- **La línea de estado es zona segura**: un clic en ella trae LightHouse al frente (las teclas pasan a "activas") y no cambia nada. Es la forma de recuperar el teclado sin tocar un look por accidente.
- Colores del aviso Teclas en mini: "en otra ventana" en `fg_muted` (es lo normal junto a rekordbox); "siempre activas" y "en pausa" en `warn`; "activas" en `ok`.
- Si la ventana es más chica que el contenido, lo último que se recorta es la línea de estado; los looks y Blackout quedan enteros. `minsize` sigue en 360×72 px lógicos.
- Pestañas, tarjetas, selector de Modo y cuerpo desplazable quedan ocultos (`grid_remove`); **no se destruyen**.
- Tamaños objetivo del contenido (px lógicos): tira ≤ 800 × 80; bloque ≤ 400 × 140. Botones de look en tamaño denso (`size.look_w_dense` × `size.look_h_dense`).
- El mini **conserva la barra de título de Windows**: no uses `overrideredirect`.
- Título de la ventana en mini: `LightHouse` (corto).

**Entrar y salir**
- Selector **Vista**: añade la opción `Mini`.
- Botón **Ampliar** (en el mini): vuelve a la vista anterior (`auto` o `compacto`).
- **Ampliar y F9 siempre sacan de Mini**, también cuando se entró sola por tamaño: en ese caso restauran la última geometría normal guardada (o el tamaño por defecto de F8). Nunca deben "no hacer nada".
- **Tecla F9**: nueva acción `mini` en el mapa de teclas (`KEYS`, default `["F9"]`, editable en `config.json` como las demás). Alterna Mini ↔ vista anterior. Como toda tecla de show, solo actúa con LightHouse al frente o con teclas globales.
- **Entrar a mano** (selector o F9): guarda la geometría normal, aplica `ui.geo_mini` (si está vacía o no es válida: tira de 800×80 px lógicos de contenido, arriba a la derecha del área de trabajo del monitor donde está Control) y activa siempre-encima si `ui.mini_encima`.
- **Salir**: guarda la geometría mini en `ui.geo_mini`, restaura la geometría normal y quita siempre-encima.
- **Entrar sola**: si el usuario encoge la ventana por debajo de los umbrales, se dibuja como mini **sin** mover la ventana ni cambiar siempre-encima. Al agrandarla vuelve sola.
- Las geometrías se validan con `outputs.geo_ok` contra los monitores actuales.

**Siempre encima**
- Interruptor `vista.fijar` → `root.attributes("-topmost", …)`. Solo se aplica mientras la vista es Mini. Se guarda en `ui.mini_encima` (default `true`).
- Las salidas a pantalla completa ya son siempre-encima: comprueba que el mini queda **por encima** de una salida a pantalla completa en el mismo monitor (si no, vuelve a subirlo al entrar a Mini) y documenta el resultado.

**Experimental: "No quitar el teclado"** (`vista.sin_foco`, `ui.mini_sin_foco`, default `false`)
- `win32.set_no_activate(hwnd, on)`: pone o quita el estilo extendido `WS_EX_NOACTIVATE` (`GetWindowLongPtrW` / `SetWindowLongPtrW`, índice `GWL_EXSTYLE`).
- Con la opción activa y la vista en Mini, un clic en un look o en Blackout hace su acción **sin** traer LightHouse al frente: el teclado sigue en rekordbox.
- **Verifícalo de verdad** (con el Bloc de notas al frente: tras un clic en el mini, lo que se teclea sigue cayendo en el Bloc de notas y el look cambió). Si con Tk no es fiable — clics que no llegan, la ventana no se puede arrastrar, o queda sin poder activarse al salir de Mini — **no lo incluyas**: quita la opción, deja documentado qué falló y sigue. Dedícale un intento acotado; no es criterio de aceptación.
- Al salir de Mini el estilo se quita siempre.

**`layout.py`**
- No debería cambiar `pick` (ya devuelve mini desde F8). Si hace falta, agrega solo lo necesario para la forma tira/bloque.

**`config.py`**
- En `ui`: `geo_mini` (`""`), `mini_encima` (`true`), `mini_sin_foco` (`false`); `ui.vista` acepta `"mini"`. Son llaves nuevas con default: **no subas la versión**.
- Si la app se cerró en Mini, arranca en Mini con su geometría.

**Registro y documentación**
- Registra en `App.ids`: `vista.fijar`, `vista.ampliar`, y `vista.sin_foco` si se incluye.
- `LEEME.txt`: sección corta "Junto a rekordbox (vista Mini)": cómo entrar (F9 o Vista → Mini), siempre encima, qué significa el aviso "Teclas", y la advertencia de "Teclas siempre activas".

**`selftest.py`**
1. `layout.pick(820, 90)` → mini con 1 fila de looks; `pick(400, 150)` → mini con 2 filas; `pick(1366, 700, forced="mini")` → mini.
2. **Tamaños pedidos** de la vista Mini con `App(headless=True)` a escala 100 % y 150 %: tira ≤ 800 × 80 y bloque ≤ 400 × 140 px lógicos.
3. En Mini siguen registrados y visibles: los 15 looks, Blackout, punto, BPM, vista previa, `vista.fijar` y `vista.ampliar`.
4. **Ida y vuelta**: entrar a Mini y salir devuelve la geometría normal exacta y deja siempre-encima apagado. Con la ventana encogida a mano hasta ser mini (vista `auto`), Ampliar deja una ventana que ya no es mini.
5. El mapa de teclas por defecto incluye `mini` → `F9`, y una config guardada sin esa acción la recibe por default.

### No entra

- Ventana mini sin barra de título, acoplada a un borde o transparente.
- Un botón de Bump para el ratón, ni controles nuevos del motor.
- Tooltips (F10), tutorial (F11), intro (F12–F13), temas.
- Cambios en las salidas o en `--pantalla`.

## Diseño decidido

- Mini es una **vista de la misma ventana Control**, no una ventana aparte: mismos widgets, mismo estado.
- Siempre visibles en Mini: look activo, señal y Blackout.
- El aviso **Teclas** es parte esencial del mini: `activas` / `en otra ventana` / `siempre activas` / `en pausa`.
- El orden de los looks no cambia.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 5 checks nuevos.
2. **A ojo, con capturas**: la tira (~820×90) y el bloque (~400×150) corresponden a los wireframes de §3.5; nada cortado; el look activo se distingue.
3. F9 entra y sale de Mini con LightHouse al frente; también Vista → Mini y el botón Ampliar. Al salir, la ventana vuelve exactamente a donde estaba.
4. Con siempre-encima activo, el mini queda sobre otra ventana maximizada (prueba con el Bloc de notas maximizado). Al salir de Mini deja de estar encima.
5. Con otra ventana al frente, el aviso dice "Teclas: en otra ventana"; al hacer clic en la línea de estado del mini, "Teclas: activas" **y el look no cambió**; con teclas globales, "Teclas: siempre activas".
6. Un clic en un look del mini cambia el look; Blackout funciona; SIN SEÑAL se ve en la línea de estado.
7. Cerrar en Mini y volver a abrir: arranca en Mini, en el mismo sitio.
8. **CPU en show en Mini**: no supera la de la vista completa y sigue < 10 %. Reporta ambos números.
9. "No quitar el teclado": incluido y verificado, **o** descartado con la razón documentada.
10. `.\build.ps1` pasa y el exe hace todo lo anterior.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```

**Arnés de CPU** (script de desarrollo en `$env:TEMP`): apunta `$env:APPDATA` a una carpeta temporal, crea `App()`, cierra el audio real, alimenta `app.on_block(x)` con un bombo sintético a 100 bloques/s durante 4 s, mide `time.process_time()` / tiempo real y cierra con `app.quit()` en un `finally`. Mide en vista completa y en Mini; tres corridas cada una.

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_cpu.py"; Remove-Item Env:\APPDATA
```

**Capturas** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí): abre la app con config temporal, fuerza la vista Mini en cada forma, captura el rectángulo de Control y cierra en `finally`. Cada ventana vive ≤ 5 s. Lee las imágenes.

**Foco** (para "No quitar el teclado"): `win32.app_in_foreground()` antes y después de un clic sintetizado sobre el mini, con otra ventana al frente. Si necesitas abrir el Bloc de notas, ciérralo en el `finally`.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Apariencia**: todo desde `theme.py`; ningún color, fuente o medida suelta. Widgets `tk` clásicos e ítems de Canvas, con `theme.paint`.
- **Rendimiento**: ningún timer nuevo. Nada nuevo en `App.fast()`.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): no uses pantalla completa salvo para el criterio de siempre-encima, y entonces ≤ 5 s. Nada de automatización de escritorio ni navegadores.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. No adelantes F10–F13. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F9 → ✅, fecha y nota de una línea (tamaños del mini, CPU en Mini y en completo, resultado de "No quitar el teclado", pendientes: probar junto a rekordbox real).
2. Responde al usuario con:
   - qué cambió;
   - cómo usar el mini junto a rekordbox;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): vista mini siempre encima con tecla F9`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
