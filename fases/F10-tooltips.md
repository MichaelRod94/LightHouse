# Fase F10: Tooltips (ayuda al pasar el ratón) en todos los controles

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior con oficio en Tkinter (ventanas sin bordes, eventos de puntero, multi-monitor) y buen criterio de redacción en español llano. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes. La usa un DJ, no un técnico.

Paquete `lighthouse/`: `engine.py`, `audio.py`, `scene.py`, `outputs.py`, `net.py`, `pantalla.py`, `win32.py` (**todo** el ctypes; `monitors()` da los rectángulos reales de cada monitor), `config.py`, `theme.py` (tokens, F7), `layout.py` (F8), `selftest.py`, `ui.py` (ventana **Control**: responsive desde F8, vista Mini desde F9) y `__main__.py`.

Desde F7 **cada control interactivo está registrado** en `App.ids` (`widget → id`, por ejemplo `luz.decay`, `look.Q`, `sal.unirse`).

**Lo que pidió el usuario**: *"Cualquier persona con leerlo debe entender qué hacer y qué hace cada cosa."*

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos ni periódicos nuevos**. Los indicadores de Control viven en `App.slow()` con `App.put()`.
- Las teclas de show se leen con `GetAsyncKeyState` y solo actúan con una ventana de LightHouse al frente; se pausan al escribir en un campo de texto. **Un tooltip no debe cambiar nada de eso.**
- ctypes solo en `win32.py`.

## Lee primero

1. `fases/README.md`: sección *Etapa 2: interfaz* (notas de F7–F9).
2. `fases/diseno-ui.md`: **§5 completo** (sistema, reglas de redacción, registro y **catálogo de textos**), §2.3 (etiquetas), §9.2 (tokens `tooltip_*`, `size.tip_max_w`, `motion.tip_*`), §10.
3. `lighthouse/ui.py`, `lighthouse/theme.py`, `lighthouse/win32.py`, `lighthouse/outputs.py` (`monitor_at`), `lighthouse/selftest.py`.

## Precondiciones

- `fases/README.md` marca **F9 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.

## Objetivo

1. Un tooltip en **cada** control interactivo y en cada indicador de Control, con el texto del catálogo.
2. Un self-check que **falle** si algún control interactivo se queda sin tooltip.
3. Que se puedan desactivar.

## Alcance

### Entra

**Nuevo `lighthouse/tips.py`**
- **`TIPS`**: diccionario `id → texto`, con **todos** los textos del catálogo de `fases/diseno-ui.md` §5.4. Los grupos del catálogo (`look.2`…`look.6`, `look.E/R/T/Y`, `avanzado.*`) pueden generarse con una plantilla, pero cada `id` registrado debe resolver a un texto.
  - Puedes pulir la redacción; respeta las reglas de §5.2: español llano, tuteo, 1–2 frases, **qué hace + cuándo usarlo**, ≤ 200 caracteres, sin siglas sin explicar.
  - Si un control existe en la app y no está en el catálogo, **escribe su texto** con esas reglas y avisa en la respuesta final.
  - Los `id` del catálogo cuyos controles nacen en una fase posterior (`ayuda.tutorial` y `tut.*` en F11, `ayuda.intro` en F13, `ayuda.tema` en F14) **no** se agregan aquí si el control todavía no existe: los agrega su fase, para que el check de huérfanos pase.
- **`title(id, app)`**: primera línea en negrita: la etiqueta visible del control y su tecla real si la tiene, tomada del mapa de teclas de la app (`Blackout · Espacio`, `Look 2 · Rojo · 2`). Si el usuario cambió las teclas en `config.json`, el tooltip muestra las suyas.
- **`place(px, py, w, h, monitor) -> (x, y)`**: función **pura** que decide dónde va el tooltip.
  - Normal: 14 px a la derecha y 20 px debajo del puntero.
  - Si se sale del rectángulo del monitor: voltea a la izquierda y/o arriba; último recurso, recorta con 8 px de margen.
  - **Nunca** deja el puntero dentro del rectángulo del tooltip.
- **`Tooltip(app)`**: **una sola** ventana compartida.
  - `Toplevel` sin bordes (`overrideredirect`), siempre encima, creada una vez y retirada; **no toma el foco** ni activa la ventana.
  - Colores, fuente, relleno y ancho máximo desde los tokens (`tooltip_bg`, `tooltip_fg`, `tooltip_border`, `font.body`, `space.md`, `size.tip_max_w` con `wraplength`).
  - **Retardo**: `motion.tip_delay` (500 ms) con el puntero sobre el control; si se mostró otro tooltip hace menos de 1 s, `motion.tip_delay_next` (100 ms). **Un solo `after` cancelable a la vez** (no es periódico).
  - **Se oculta** en `<Leave>`, `<ButtonPress>`, cualquier tecla, cambio de layout o de pestaña, y en `<FocusOut>` de la raíz (por ejemplo con Alt+Tab).
  - **Se muestra aunque LightHouse no esté al frente**: el `<Enter>` llega igual. Es el caso del mini con rekordbox al frente; ahí el tooltip es la única ayuda que no le quita el teclado a rekordbox. No condiciones el tooltip a `win32.app_in_foreground()`.
  - **Controles deshabilitados**: también muestran su tooltip (el texto dice cuándo se activan).
  - **Con "Navegar con Tab"** (`ui.tab_nav`): el tooltip del control enfocado aparece en `<FocusIn>`, debajo del control, y se oculta con `Esc` o al mover el foco.
  - El monitor del puntero sale de `win32.monitors()` + `outputs.monitor_at` (Tk solo conoce el monitor principal).
- Enlace: una sola función recorre `app.ids` y pone los bindings `<Enter>` / `<Leave>` / `<ButtonPress>` (con `add="+"`, sin pisar los existentes). Para un `ttk.Combobox`, también sobre su parte interna si hace falta.

**`ui.py`**
- Crea el `Tooltip` al final de `__init__` y enlaza todos los controles registrados, incluidos los de la ventana **Calibrar** (`calib.salir`) cuando se abre.
- Pestaña Ayuda → tarjeta `ayuda`: casilla **"Mostrar ayudas al pasar el ratón"** (`ayuda.tips`, `ui.tips`, activa por defecto).
- En vista Mini los tooltips funcionan igual; como la ventana es chica, se colocan fuera de ella cuando hay sitio.
- Quita las notas largas que ahora duplican un tooltip **solo** si la especificación lo indica; las advertencias de seguridad (rekordbox con teclas globales, fotosensibilidad) **se quedan visibles** además de estar en el tooltip.

**`config.py`**
- En `ui`: `tips` (`true`). Llave nueva con default: **no subas la versión**.

**`selftest.py`**
1. **Cobertura** (el check clave): con `App(headless=True)`, recorre el árbol de widgets de Control y **falla** — listando los culpables — si un widget interactivo (`Button`, `TButton`, `Checkbutton`, `TCheckbutton`, `Radiobutton`, `TRadiobutton`, `Scale`, `TCombobox`, `TEntry`, `Entry`, `Listbox`, o cualquier widget con binding propio de `<Button-1>`) no tiene `id`, o su `id` no resuelve a un texto en `TIPS`.
2. **Calidad**: ningún texto vacío; todos ≤ 200 caracteres; todos terminan en punto; ninguno contiene las palabras de jerga de la columna "Hoy" de §2.3 (`decay`, `offset`, `gamma`, `refractario`, `AGC`, `dBFS`, `master`, `kick`, `tempo`…), buscadas como palabra completa. Excepción: un valor de lista citado tal como se ve en pantalla, entre comillas (`"Kick"`, `"Salida (loopback) · …"`).
3. **Sin huérfanos**: todo `id` de `TIPS` corresponde a un control registrado (o a un grupo de plantilla); así no quedan textos de controles que ya no existen.
4. **`place`**: con el puntero en el centro, cerca de cada borde y en cada esquina de un monitor de 1366×768, y en un monitor con origen negativo (`-2560, -360`, 2560×1440): el tooltip queda entero dentro del monitor y el puntero queda fuera de su rectángulo.
5. **`title`**: con el mapa de teclas por defecto, `title("blackout")` nombra Espacio; con un mapa cambiado, nombra la tecla nueva.

### No entra

- Tutorial (F11), intro (F12–F13), temas.
- Tooltips en las salidas de luz o en `--pantalla`.
- Ayuda contextual con imágenes, enlaces o un manual dentro de la app.
- Cambiar etiquetas o mover controles (F8 ya lo hizo).

## Diseño decidido

- **Una** ventana de tooltip, reutilizada. Cero costo mientras no hay hover: no hay sondeo.
- El tooltip **nunca** tapa el puntero ni sale del monitor donde está el puntero.
- El catálogo es datos (`TIPS`), separado del mecanismo; el tutorial de F11 reutiliza los mismos `id`.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 5 checks nuevos. **Prueba que el check de cobertura muerde**: quita temporalmente un texto de `TIPS`, confirma que `--test` falla nombrando el control, y restáuralo.
2. Al dejar el ratón ~0,5 s sobre cualquier control aparece su tooltip; al salir, hacer clic o teclear, desaparece. **También con otra ventana al frente** (prueba en vista Mini con el Bloc de notas al frente): el tooltip aparece y el Bloc de notas sigue siendo la ventana activa.
3. **A ojo, con capturas** (script de desarrollo que mueve el puntero sobre 4–5 controles representativos — un look, un deslizador, Blackout, la lista de dispositivos, un control pegado al borde derecho de la pantalla — y captura): el tooltip se lee, no tapa el control ni el puntero y no sale de la pantalla.
4. Con un tooltip visible, **las teclas de show siguen funcionando** y `win32.app_in_foreground()` sigue en `True`; el chip Teclas no cambia. El tooltip no aparece en la barra de tareas ni roba el foco de un campo de texto.
5. La casilla "Mostrar ayudas al pasar el ratón" los apaga y enciende, y se conserva al reiniciar.
6. Funciona con Control en un monitor secundario (si hay más de uno; si no, se documenta como pendiente).
7. **CPU en show**: igual que antes de la fase (± 0,5 puntos) con el puntero quieto fuera de la ventana. Reporta el número.
8. `.\build.ps1` pasa y el exe muestra los tooltips.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```

**Arnés de CPU** (script de desarrollo en `$env:TEMP`): apunta `$env:APPDATA` a una carpeta temporal, crea `App()`, cierra el audio real, alimenta `app.on_block(x)` con un bombo sintético a 100 bloques/s durante 4 s, mide `time.process_time()` / tiempo real y cierra con `app.quit()` en un `finally`. Antes y después; tres corridas.

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_cpu.py"; Remove-Item Env:\APPDATA
```

**Capturas** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí): para provocar un tooltip sin mover el ratón real del usuario, genera el evento con `widget.event_generate("<Enter>", …)` y espera el retardo; si hace falta el puntero real, muévelo con `event_generate("<Motion>", warp=True)` y **devuélvelo a su sitio** en el `finally`. Cada ventana vive ≤ 5 s.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Apariencia**: todo desde `theme.py`; ningún color, fuente o medida suelta. Widgets `tk` clásicos e ítems de Canvas, con `theme.paint` (un cambio de tema debe repintarlos).
- **Rendimiento**: ningún timer periódico; solo el `after` de un disparo del retardo, cancelable. Nada nuevo en `App.fast()` ni en `App.slow()`.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): nada de pantalla completa, automatización de escritorio ni navegadores.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. No adelantes F11–F13. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F10 → ✅, fecha y nota de una línea (número de tooltips, CPU, pendientes). Agrega notas para F11: cómo silenciar los tooltips durante el tutorial y cómo obtener el widget de un `id`.
2. Responde al usuario con:
   - qué cambió;
   - los textos que escribiste o cambiaste respecto al catálogo, para que los revise;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): tooltips en todos los controles con self-check de cobertura`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
