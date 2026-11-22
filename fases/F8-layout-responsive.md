# Fase F8: Arquitectura de información y layout responsive (completo, medio y compacto)

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior con oficio en Tkinter/ttk (gestores de geometría, DPI, ventanas redimensionables) y criterio de interfaz para herramientas en vivo. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes. Corre en la **laptop DJ junto a rekordbox**; el DJ cambia los looks con el teclado.

Paquete `lighthouse/`: `engine.py`, `audio.py`, `scene.py`, `outputs.py`, `net.py`, `pantalla.py`, `win32.py` (**todo** el ctypes), `config.py` (JSON versionado, v5 desde F7), `theme.py` (tokens y tema "oscuro", F7), `selftest.py`, `ui.py` (ventana **Control**) y `__main__.py`. `build.ps1` genera el exe.

Hoy Control tiene tamaño fijo (lo que pide su contenido, ~1085×576 al 100 %): barra de looks arriba, una columna fija a la izquierda (Lecturas, Fuente de audio, Modo) y un `ttk.Notebook` con Show / Audio / Salidas a dos columnas. No se adapta a media pantalla ni a una franja.

**Usos reales que debe cubrir:**
- 1920×1080 completo (preparación en casa).
- Media pantalla con Windows Snap: 960×1080 y 1920×540.
- Laptop 1366×768, y escalados de Windows de 125–150 %.
- Junto a rekordbox, ocupando lo mínimo (el modo mini es F9; aquí se deja preparado).

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos** (`after(1)` gira al 98 %). El pintado de las salidas vive en `App.fast()`; los indicadores de Control, en `App.slow()` (~30 Hz) con `App.put()`.
- Las salidas de luz nunca usan Canvas. Un Canvas chico en Control es aceptable si se mide su costo.
- Las teclas de show se leen con `GetAsyncKeyState` y se pausan al escribir en un campo de texto.
- ctypes solo en `win32.py`. Config JSON versionada con migraciones.

## Lee primero

1. `fases/README.md`: *Estado*, sección *Etapa 2: interfaz* (notas de F7).
2. `fases/diseno-ui.md`: **§1, §2 (zonas, tarjetas básico/avanzado, etiquetas nuevas), §3 (modos, breakpoints, wireframes, tamaños), §4 (componentes y feedback en vivo), §8 (config), §10 (accesibilidad), §12**. Es la especificación; respétala.
3. `lighthouse/ui.py` completo, `lighthouse/theme.py`, `lighthouse/config.py`, `lighthouse/selftest.py`, `lighthouse/win32.py`, `LEEME.txt`.

## Precondiciones

- `fases/README.md` marca **F7 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.
- **Antes de tocar código**, mide la línea base de CPU con el arnés (ver *Verificación*).

## Objetivo

1. Reorganizar Control en las cuatro zonas de la especificación: **barra de looks**, **franja En vivo**, **pestañas** (Show · Audio · Salidas · Ayuda) y **tarjetas** con parte básica y "Avanzado" plegable.
2. Que la ventana sea **redimensionable** y elija sola entre los modos **completo**, **medio** y **compacto** según su tamaño, con una función pura.
3. Etiquetas en español llano (tabla de §2.3).
4. Persistir vista, pestaña, "Avanzado" abiertos y el tamaño de la ventana.

## Alcance

### Entra

**Nuevo `lighthouse/layout.py`** (puro: sin Tk)
- `Layout(mode, cols, look_rows, dense)`, `pick(w, h, forced="auto", prev=None)` y `plan(layout, tab)`, tal como los define §3.2.
- Umbrales en px lógicos: mini si alto < 300 o ancho < 560 (o `forced == "mini"`); compacto si alto < 600 o ancho < 760 (o `forced == "compacto"`); medio si ancho < 1200; si no, completo. `cols = clamp(w // 400, 1, 4)`. Filas de looks: 1 si ancho ≥ 900 (cómoda) o ≥ 760 (densa); si no, 2. Filas de la franja En vivo en densa: 1 si ancho ≥ 1100; si no, 2. Histéresis de 24 px a favor de `prev`.
- `pick` ya devuelve `"mini"` (así F9 no toca esta función), pero **en esta fase un resultado mini se dibuja como compacto**.
- La tabla de tarjetas por pestaña (ids de §2.2) y sus pesos de altura viven aquí.

**`ui.py`: estructura**
- **Sin `ttk.Notebook`**: barra de pestañas propia (segmentos) + un contenedor único de tarjetas. Todas las tarjetas son hijas de ese contenedor y se colocan con `grid` según `layout.plan`; las de otra pestaña se retiran con `grid_remove`. **Los widgets se crean una sola vez**; cambiar de modo o de pestaña nunca destruye ni recrea widgets.
- **Barra de looks** (zona A): 1 o 2 filas según `look_rows`; en densa, botones de una línea (`2 Rojo`) con la muestra como banda fina.
- **Franja En vivo** (zona B): punto de golpe, medidor, BPM, look activo, estado, **vista previa**, chips (Teclas, SIN SEÑAL, SATURA, TV remota, avisos de salida), selector de Modo, selector **Vista** (`Automática` · `Compacta`; "Mini" lo añade F9), **Bump** y **Blackout**. En compacto se condensa en una fila si el ancho ≥ 1100 px lógicos y en dos si es menor (§3.2), y el Modo pasa a lista desplegable. Blackout va siempre en la primera fila, a la derecha.
- **Bump** (`bump`, nuevo): botón de mantener junto a Blackout. `<ButtonPress-1>` enciende el bump y `<ButtonRelease-1>` lo apaga, igual que la tecla `F`; se ve activo mientras dura, venga del ratón o de la tecla. Si la ventana pierde el foco con el botón presionado, el bump se suelta. No agrega llaves de config.
- **Tarjetas** (zona D) con el contenido y el reparto básico/avanzado de §2.2. "Fuente de audio" pasa a la pestaña Audio; sus alarmas quedan en los chips. La Sensibilidad vive en Respuesta.
- **Avanzado ▸ / ▾** por tarjeta: muestra u oculta su parte avanzada; un punto `•` si algún valor avanzado no está en su default.
- **Pestaña Ayuda**: tarjeta `atajos` (tabla de teclas generada del mapa real `self.keys`, reemplaza la leyenda del pie) y tarjeta `ayuda` (versión, rutas de config y logs, botón "Abrir carpeta de registros"). Los botones del tutorial, los tooltips y la intro los agregan F10, F11 y F13; el selector de tema, F14.
- **Cuerpo desplazable**: si las tarjetas visibles no caben en el alto disponible, el cuerpo se desplaza en vertical con la rueda (contenedor con Canvas estático). La rueda **nunca** cambia el valor de un control.
- **Redimensionado**: la raíz es redimensionable, con `minsize` de 360×72 px lógicos. `<Configure>` de la raíz agenda **un solo** `after(120)` cancelable (el patrón de `Output.later`); al dispararse llama a `layout.pick` y recoloca **solo si el `Layout` cambió**.
- Todo control nuevo se registra en `App.ids` con su `id` del catálogo (§5.4): `tab.*`, `avanzado.<tarjeta>`, `vista.selector`, `vivo.previa`, `vivo.teclas`, `bump`, `ayuda.carpeta`…

**`ui.py`: feedback en vivo** (todo en `slow()` con `put()`; ningún timer nuevo)
- **Vista previa**: `fast()` deja en un atributo el último `Frame` compuesto para la Salida 1 (una asignación, nada más); `slow()` pinta dos `Frame` chicos con esos colores.
- **Chip Teclas**: `Teclas: activas` · `Teclas: en otra ventana` · `Teclas: siempre activas` (globales) · `Teclas: en pausa` (escribiendo o navegando), según `win32.app_in_foreground()`, `keys_global` y `typing`. Un clic en el chip trae LightHouse al frente y no cambia nada más.

**`ui.py`: teclas**
- Con **Ctrl o Alt** presionados, `poll_keys` no dispara acciones (hoy `Alt+F4` cambia a modo Manual antes de cerrar).
- **Navegar con Tab** (`ui.tab_nav`, apagado por defecto; casilla en la tarjeta Teclado → Avanzado): con la opción activa, los controles registrados toman el foco; mientras el foco está en un control las teclas de show quedan en pausa (mismo mecanismo que `typing`) y `Esc` devuelve el foco a la raíz. Contorno de foco con el token `focus`.

**Etiquetas**
- Aplica la tabla de §2.3. **No cambies llaves de `config.json` ni los valores de las listas que se guardan** (`Kick (120 Hz)`, `Muy reactivo`, `excepto en 1`, `Luz + logo`…).
- Actualiza `LEEME.txt` con los nombres nuevos y la nueva ubicación de los controles.

**`config.py`**
- `VERSION = 6`. En `ui`: `vista` (`"auto"` / `"compacto"`; acepta también `"mini"` para F9), `tab`, `avanzado` (`{id de tarjeta: bool}`), `tab_nav`.
- `geo_control` pasa a restaurar **posición y tamaño** (validado con `outputs.geo_ok`). Migración v5 → v6: se conserva solo la posición del `geo_control` guardado (su tamaño era el del contenido viejo) y se usa el tamaño por defecto.
- Tamaño por defecto al primer arranque: el pedido por el modo completo si cabe en el área de trabajo del monitor; si no, el área de trabajo.

**`selftest.py`**
1. **`layout.pick`** contra los 9 casos de la tabla de §3.2 (modo, columnas, filas de looks).
2. **Histéresis**: con `prev` en medio, un ancho de 1210 sigue en medio y 1230 pasa a completo; al revés, desde completo, 1190 sigue en completo y 1170 pasa a medio.
3. **`layout.plan`**: para cada pestaña y cada `cols` de 1 a 4, cada tarjeta de la pestaña aparece exactamente una vez, en una columna válida, sin dos tarjetas en la misma celda.
4. **Tamaños pedidos** con `App(headless=True)`, todos los "Avanzado" plegados, a escala 100 % y 150 % (`scaling`): los de la tabla de §3.5 para completo (3 columnas, cada pestaña), medio (2 columnas) y compacto (4 columnas y 1 columna).
5. **Registro**: sigue pasando el check de F7 (todo control interactivo tiene `id`), ahora con los controles nuevos.
6. **Teclas**: la decisión "¿disparan las teclas?" es una función pura probada — no con Ctrl, no con Alt, no escribiendo, no con foco en un control, no sin estar al frente salvo globales.
7. **Config**: una config v5 carga en v6 conservando la posición de `geo_control`; `ui.vista` inválida cae a `"auto"`.

### No entra

- **Modo mini** como vista propia, siempre encima y tecla F9 (F9).
- Tooltips (F10), tutorial (F11), intro (F12–F13), temas.
- Quitar, agregar o cambiar el comportamiento de controles del motor. Editor de teclas.
- Cambios en `outputs.py`, `scene.py`, `engine.py` o en el modo `--pantalla`.

## Diseño decidido

- **Tres cosas siempre visibles** en cualquier tamaño: look activo, señal (golpe, nivel, BPM) y Blackout.
- El orden de los looks nunca cambia (1–7, Q–U, Z); con 2 filas: `1–7 Q` arriba y `W E R T Y U Z` abajo.
- El cambio de modo es por **tamaño de la ventana**, no por tamaño del monitor.
- Nada se anima: los cambios de layout son inmediatos.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 7 checks nuevos, y termina en < 10 s.
2. **Ningún control desaparece**: todos los controles de antes existen, con su etiqueta nueva, y siguen moviendo lo mismo. Compara la lista de `id` registrados con el catálogo de §5.4.
3. **A ojo, con capturas** (script de desarrollo; mira cada imagen): la ventana a 1920×1010, 1366×700, 946×1010, 1906×500 y 700×420 px lógicos corresponde al wireframe de su modo en §3.5. No hay texto cortado ni controles montados.
4. Arrastrar el borde de la ventana cambia de modo sin parpadeo apreciable. Mide el tiempo de una recolocación (objetivo ≤ 50 ms) y repórtalo.
5. El selector Vista funciona (`Automática` / `Compacta`) y, junto con la pestaña, los "Avanzado" abiertos y el tamaño de la ventana, se conserva al reiniciar.
6. "SIN SEÑAL", "SATURA", los errores de audio y los avisos de salida se ven en la franja En vivo en los tres modos. En una ventana de 700×420 la franja ocupa dos filas, sin nada cortado, y Blackout sigue a la vista.
7. La vista previa muestra lo mismo que la Salida 1 (color, mitades partidas en E–Y, negro en blackout).
8. Mantener el botón Bump enciende las salidas a tope y soltarlo las devuelve, igual que la tecla `F`. `Alt+F4` cierra sin cambiar de modo. Con "Navegar con Tab" activo, Tab recorre los controles, el chip dice "en pausa" y `Esc` reactiva las teclas; apagado, todo se comporta como antes.
9. Cabe en **1366×768 al 100 %** y en **1920×1080 al 150 %** sin desplazamiento con los "Avanzado" plegados (check 4).
10. **CPU en show**: no sube más de 1 punto porcentual sobre la línea base y sigue < 10 %. Reporta ambos números.
11. `.\build.ps1` pasa y el exe hace todo lo anterior. `LEEME.txt` está al día.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```

**Arnés de CPU** (script de desarrollo en `$env:TEMP`): apunta `$env:APPDATA` a una carpeta temporal, crea `App()`, cierra el audio real, alimenta `app.on_block(x)` con un bombo sintético a 100 bloques/s durante 4 s, mide `time.process_time()` / tiempo real y cierra con `app.quit()` en un `finally`. Tres corridas; reporta el rango. Úsalo **antes** de empezar y al final.

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_cpu.py"; Remove-Item Env:\APPDATA
```

**Capturas** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí): por cada tamaño, abre la app con config temporal, fija la geometría, espera ~1,5 s, captura el rectángulo de Control (`win32.window_rect`) y cierra en `finally`. Cada ventana vive ≤ 5 s. Lee las imágenes.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Apariencia**: ningún color, fuente o medida suelta; todo desde `theme.py`. Los widgets `tk` clásicos y los ítems de Canvas se colorean con `theme.paint`, para que un cambio de tema los repinte (los checks de F7 —sin colores sueltos y repintado— deben seguir pasando).
- **Rendimiento**: ningún timer periódico nuevo; el único `after` nuevo permitido es el de un disparo (120 ms, cancelable) del redimensionado. Nada nuevo en `App.fast()` salvo guardar el último `Frame`.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): no uses pantalla completa, automatización de escritorio ni navegadores.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. No adelantes F9–F13. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F8 → ✅, fecha y nota de una línea (tamaños pedidos por modo al 100 % y 150 %, tiempo de recolocación, CPU antes/después, tamaño del exe, pendientes). Agrega notas para F9: cómo se dibuja un `Layout`, qué falta para el modo mini y dónde vive el selector Vista.
2. Responde al usuario con:
   - qué cambió y dónde quedó cada control;
   - cómo probar cada modo;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): layout responsive con tarjetas, franja En vivo y etiquetas llanas`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
