# Fase F7: Sistema de tokens, tema por defecto y registro de controles

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior con oficio en Tkinter/ttk (estilos, temas, DPI en Windows). Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes. Corre en la **laptop DJ junto a rekordbox**; el DJ cambia los looks con el teclado.

Paquete `lighthouse/`: `engine.py` (DSP), `audio.py`, `scene.py` (15 looks, `compose`), `outputs.py` (salidas de video), `net.py`, `pantalla.py` (receptor `--pantalla`), `win32.py` (**todo** el ctypes), `config.py` (JSON versionado, hoy v4), `selftest.py`, `ui.py` (ventana **Control**: barra de looks, lecturas, pestañas Show / Audio / Salidas) y `__main__.py`. `build.ps1` genera el exe (57 MB).

Esta es la primera fase de la **Etapa 2: interfaz**. Hoy `ui.py` tiene colores sueltos (`"#666"`, `"#c33"`, `"#ffd966"`…), fuentes repetidas y usa el tema ttk nativo. Después de esta fase, **toda** la apariencia sale de un módulo de tokens, y la fase F14 podrá agregar temas enchufando paletas y cambiarlos sin reiniciar.

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**. Pillow no va en el exe. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos** (`after(1)` gira al 98 %). El pintado de las salidas vive en `App.fast()`; los indicadores de Control, en `App.slow()` (~30 Hz) con `App.put()` (solo si cambió).
- Las salidas de luz nunca usan Canvas.
- Las teclas de show se leen con `GetAsyncKeyState` y se pausan al escribir en un campo de texto.
- ctypes solo en `win32.py`. Config JSON versionada con migraciones.

## Lee primero

1. `fases/README.md`: *Estado* (notas de F2, F4 y F5), *Arquitectura decidida* y la sección *Etapa 2: interfaz*.
2. `fases/diseno-ui.md`: **§1 Principios, §4 Componentes, §5.3 Registro e identificadores, §8 Config, §9 Tokens y tema por defecto, §10 Accesibilidad (contraste), §12, §13.5 (qué se repinta al cambiar de tema) y §13.6 (pares de contraste)**. Es la especificación; respétala.
3. `lighthouse/ui.py` completo, `lighthouse/config.py`, `lighthouse/selftest.py`, `lighthouse/win32.py`, `lighthouse/__main__.py`, `lighthouse/outputs.py` (solo para saber qué queda exento).

## Precondiciones

- `fases/README.md` marca **F6 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status` (para saber de qué estado partes).
- **Antes de tocar código**, mide la línea base con el arnés de CPU (ver *Verificación*) y captura la ventana Control actual. Guarda ambos datos para comparar.

## Objetivo

1. Un módulo de tokens (`lighthouse/theme.py`) con el tema por defecto **"oscuro"** y un único punto que aplica el tema a Tk/ttk.
2. `ui.py` sin un solo color, fuente o medida de apariencia suelta: todo sale de los tokens.
3. Un **registro de controles**: cada control interactivo tiene un `id` estable (lo usarán los tooltips de F10 y el tutorial de F11).
4. Un modo de construcción **sin ventana visible** (`headless`) para que el self-check revise la interfaz.

**La disposición de la ventana no cambia en esta fase** (mismas pestañas, mismos paneles, mismas etiquetas). Solo cambia de dónde sale la apariencia.

## Alcance

### Entra

**Nuevo `lighthouse/theme.py`** (puro al importarlo: sin crear Tk)
- `THEMES = {"oscuro": {...}}`, `DEFAULT = "oscuro"`, `REQUIRED` (todas las llaves obligatorias), `get(name)`, `validate(theme)`, `px(n, scale)`, `contrast(a, b)` (relación de contraste WCAG), `paint(widget, **tokens)` y `apply(root, theme)`.
- Tokens y valores: exactamente los de `fases/diseno-ui.md` §9.2 y §9.3 (colores, tipografía, espaciado, radio, tamaños, ventana, tiempos), incluidos `label`, `live_fg`, `window.alpha_hover`, `window.caption` y `window.caption_fg`.
- Un tema puede declarar `"base": "<otro>"` y definir solo lo que cambia; `get` devuelve el tema completo.
- `apply(root, theme)` es **el único lugar** que toca `ttk.Style` (tema base `clam`), `root.option_add` (lista del Combobox, fuentes por defecto), el fondo de la raíz, `-alpha` de Control (`window.alpha`) y la barra de título (oscura, con el color `window.caption` donde el sistema lo permita).
- **`apply` se puede llamar más de una vez** (la fase de temas, F14, cambia de tema sin reiniciar). Para eso:
  - `paint(widget, bg="surface_alt", fg="fg", …)` configura un widget `tk` clásico (o un ítem de Canvas) con los colores de los tokens **y recuerda** el enlace opción → token. `apply` vuelve a pintar todo lo registrado.
  - Ningún módulo de interfaz guarda un color en una variable ni lo pasa suelto a un widget. Los colores que se deciden en cada tick (punto de golpe, alarmas) se leen del tema vigente en ese momento.
  - `window.alpha_hover` solo se define aquí; su comportamiento lo implementa F14.
- Nombre de tema desconocido → `DEFAULT`, con aviso en el log.

**`win32.py`**
- `set_dark_titlebar(hwnd, on) -> bool`: `DwmSetWindowAttribute` con el atributo 20 (`DWMWA_USE_IMMERSIVE_DARK_MODE`); devuelve `False` sin lanzar si el sistema no lo soporta. Se aplica a Control y a la ventana de Calibrar.
- `set_caption_color(hwnd, bg, fg) -> bool`: atributos 35 (`DWMWA_CAPTION_COLOR`) y 36 (`DWMWA_TEXT_COLOR`), con el color como `0x00BBGGRR`. Solo existe en Windows 11: en Windows 10 devuelve `False` sin lanzar y queda la barra oscura estándar.

**`ui.py`**
- Reemplaza **todos** los literales de color, fuentes y rellenos por tokens. Las distancias pasan por `theme.px()` con la escala real (`root.winfo_fpixels("1i") / 96`).
- Los widgets `tk.*` clásicos que se conservan (`tk.Scale`, botones de look, Blackout, `Listbox`, los `Canvas` chicos de Control) reciben sus colores con `theme.paint` al crearse. Las muestras de color de los looks son datos del show: no pasan por `paint`.
- Estados de §4 de la especificación para lo que **ya existe**: hover (`<Enter>` / `<Leave>` en tk; `style.map` en ttk), seleccionado (look activo con `accent` / `accent_fg` y negrita; Blackout activo con `danger` y texto `BLACKOUT ●`), deshabilitado. **Sin timers.**
- **Registro**: `self.ids = {}` (`widget → id`). Cada control interactivo se registra al crearse con el `id` del catálogo de `fases/diseno-ui.md` §5.4 (`look.2`, `luz.decay`, `audio.dispositivo`, `sal.nombre`…). Los ayudantes `slider`, `check`, `presets`, `out_slider` y `field` reciben el `id` como parámetro obligatorio. Los indicadores con `id` en el catálogo (`vivo.*`) también se registran.
- **Rueda del ratón**: quita el binding de clase `<MouseWheel>` de `TCombobox` (hoy la rueda sobre la lista de dispositivos cambia el dispositivo de audio).
- **`App(headless=False, scaling=None)`**. Con `headless=True`:
  - la raíz y todas las ventanas quedan retiradas (`withdraw`), incluida la Salida 1;
  - no se abre audio ni se arranca el hilo `render`;
  - no se lee ni se escribe `config.json` (se usan los defaults);
  - no se llama a `keep_awake`;
  - `scaling` (si se da) se aplica con `tk scaling` **antes** de crear los widgets, para simular 150 %.
  - Debe existir una forma de cerrarla limpia (`quit()` sin guardar).
- El texto de la leyenda inferior sube de 8 a 9 pt (`font.small`).

**`config.py`**
- `VERSION = 5`. Nueva llave `ui` (diccionario) con `theme: "oscuro"`. La migración no transforma nada (las llaves nuevas las ponen los defaults); solo registra el salto de versión.
- `ui.theme` se guarda y se aplica al arrancar. **No hay selector de tema en la interfaz**: eso lo agrega F14.

**`selftest.py`** (se empaqueta en el exe; se ejecuta con `--test`)
1. **Tema completo**: `theme.validate(theme.get(n)) == []` para cada tema de `THEMES`.
2. **Contraste**: para cada tema de `THEMES`, **todos** los pares de `fases/diseno-ui.md` §13.6 cumplen su mínimo (texto normal ≥ 4,5; texto grande, indicadores y contornos ≥ 3,0). La lista de pares vive en `theme.py` (`CONTRAST_PAIRS`), para que la fase de temas la reutilice. El fallo nombra el tema y el par.
3. **`px`**: `px(8, 1.0) == 8`, `px(8, 1.5) == 12`.
4. **Sin colores sueltos**: en el código fuente de `ui.py` no hay literales `#rgb` / `#rrggbb` ni nombres de color de Tk como cadenas, salvo las constantes de datos del show `PALETTE` y `KELVIN`. Este check solo corre cuando hay código fuente (se omite en el exe congelado).
5. **Interfaz sin ventana**: construye `App(headless=True)`, recorre el árbol de widgets y falla si un widget interactivo (`Button`, `TButton`, `Checkbutton`, `TCheckbutton`, `Radiobutton`, `TRadiobutton`, `Scale`, `TCombobox`, `TEntry`, `Entry`, `Listbox`) no está en `app.ids`, o si dos widgets distintos comparten `id` (salvo los que el catálogo agrupa). Cierra en `finally`. Debe durar < 3 s.
6. **Config**: una config v4 guardada carga en v5 con `ui.theme == "oscuro"` y sin perder ninguna otra llave.
7. **Repintado**: con `App(headless=True)`, aplica un tema de prueba (copia de "oscuro" con `bg`, `surface_alt`, `fg` y `accent` distintos, creado en el propio check) y comprueba que **cada** widget registrado con `paint` y los estilos `ttk` tomaron los colores nuevos; vuelve a aplicar "oscuro" y comprueba que regresan. Así F14 solo tiene que agregar paletas.

### No entra

- Cambiar la disposición, las pestañas, las etiquetas o agrupar controles (F8).
- Modo mini (F9), tooltips (F10), tutorial (F11), intro (F12–F13).
- Temas adicionales, selector de tema y transparencia (F14).
- Tocar la apariencia de las salidas de luz (`outputs.py`, `pantalla.py`): son superficies de show, no interfaz.

## Diseño decidido

- Tema ttk base **`clam`**: es el único de Windows que respeta colores en todos sus elementos.
- Tema por defecto **"oscuro"**: oscuro neutro con acento ámbar (valores y contrastes en §9.3).
- Los tokens son un diccionario plano por tema; agregar un tema es agregar una entrada.
- Los colores de los looks (`scene.py`), `PALETTE` y `KELVIN` son **datos del show**, no tokens.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 7 checks nuevos, y termina en < 10 s.
2. `Select-String` no encuentra literales de color en `lighthouse\ui.py` fuera de `PALETTE` / `KELVIN`.
3. La app abre con el tema "oscuro": captura la ventana Control con un script de desarrollo y **mírala**. Revisa cada tipo de control (botón, lista desplegable abierta, casilla, opción, deslizador, campo de texto, lista de salidas, botones de look, Blackout activo e inactivo) en cada pestaña. Todo el texto se lee; no queda ningún parche del tema claro.
4. Los estados hover y seleccionado funcionan en los botones de look y en Blackout.
5. La barra de título de Control es oscura en Windows 10/11 (si el sistema no lo soporta, no falla).
6. Todo lo que funcionaba sigue igual: looks por teclado, Blackout, Bump, modos, tap, sensibilidad, salidas, calibración, guardado de config. La ventana Control sigue cabiendo en 1366×768 al 100 % y en 1920×1080 al 150 % (mide `winfo_reqwidth` / `winfo_reqheight` con `App(headless=True)` y con `scaling=2.0`; reporta los números).
7. **CPU en show**: con el arnés, no sube más de 1 punto porcentual sobre la línea base medida al empezar y sigue < 10 %. Reporta ambos números.
8. La rueda del ratón sobre una lista desplegable ya no cambia su valor.
9. `.\build.ps1` pasa; el exe abre con el tema y pasa `--test`. Reporta el tamaño.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
Select-String -Path lighthouse\ui.py -Pattern '"#[0-9a-fA-F]{3,6}"' | Where-Object { $_.Line -notmatch 'PALETTE|KELVIN' }
```

**Arnés de CPU** (script de desarrollo en `$env:TEMP`, no se agrega al repo). Debe:
- apuntar `$env:APPDATA` a una carpeta temporal antes de lanzar Python, para no leer ni pisar la config real del usuario (así arranca con una sola salida en ventana);
- crear `App()`, cerrar el audio real, y alimentar `app.on_block(x)` desde un hilo con un bombo sintético a 100 bloques/s durante 4 s;
- medir `time.process_time()` / tiempo real y imprimirlo;
- cerrar con `app.quit()` dentro de un `finally`. Repite 3 veces y reporta el rango.

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_cpu.py"; Remove-Item Env:\APPDATA
```

**Captura** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí, nunca en `requirements.txt`): abre la app, espera ~1,5 s, captura el rectángulo de la ventana Control (`win32.window_rect`) y cierra en `finally`. La app vive ≤ 5 s. Lee la imagen resultante.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Rendimiento**: ningún timer `after(n)` nuevo. Nada nuevo dentro de `App.fast()`.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): no pongas nada en pantalla completa ni uses automatización de escritorio o navegadores.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. No adelantes F8. Si algo del diseño es imposible (por ejemplo, un elemento de `clam` que no acepta color), detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F7 → ✅, fecha y nota de una línea (CPU antes/después, tamaño de Control al 100 % y 150 %, tamaño del exe, pendientes). Agrega notas para F8 sobre `theme.apply`, `App.ids` y `App(headless=True)`.
2. Responde al usuario con:
   - qué cambió;
   - cómo probarlo;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): sistema de tokens, tema oscuro y registro de controles`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
