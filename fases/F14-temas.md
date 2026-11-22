# Fase F14: Temas (oscuro, vaporwave, glass y blue ocean) con selector

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior con oficio en Tkinter/ttk (estilos, ventanas en capas, DWM en Windows) y criterio de diseño visual y accesibilidad (contraste WCAG). Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes. Corre en la **laptop DJ junto a rekordbox**, de noche; el DJ la mira de reojo.

Paquete `lighthouse/`: `engine.py`, `audio.py`, `scene.py` (looks y sus colores), `outputs.py` (salidas de luz), `net.py`, `pantalla.py` (receptor `--pantalla`), `win32.py` (**todo** el ctypes), `config.py`, `theme.py` (tokens, tema "oscuro", `paint` y `apply`, F7), `layout.py` (F8), `selftest.py`, `ui.py` (ventana **Control**) y `__main__.py`. Según lo que ya esté hecho, también `tips.py` (F10), `tutorial.py` (F11) e `intro.py` (F13).

Desde F7 toda la apariencia de Control sale de `theme.py`: los widgets `ttk` por `ttk.Style` y los `tk` clásicos por `theme.paint`, que recuerda qué token pinta cada opción. `theme.apply(root, theme)` se puede llamar más de una vez y repinta todo.

**Lo que pidió el usuario**: cuatro temas — **oscuro, vaporwave, glass transparente y blue ocean**.

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos ni periódicos nuevos**. El pintado de las salidas vive en `App.fast()`; lo vivo de Control, en `App.slow()` (~30 Hz) con `App.put()`.
- Las salidas de luz nunca usan Canvas.
- Las teclas de show se leen con `GetAsyncKeyState` y se pausan al escribir en un campo de texto.
- ctypes solo en `win32.py`. Config JSON versionada.
- **Los temas nunca tocan las salidas de luz ni la pantalla remota**: los colores de los looks son del cliente.

## Lee primero

1. `fases/README.md`: sección *Etapa 2: interfaz* (decisiones de la etapa y notas de las fases hechas).
2. `fases/diseno-ui.md`: **§13 completo** (reglas, **paletas**, estados e indicadores, **glass**, selector y **pares de contraste**), §9 (tokens y tema "oscuro"), §4 (componentes y estados), §10 (accesibilidad). Es la especificación; respétala.
3. `lighthouse/theme.py`, `lighthouse/ui.py`, `lighthouse/win32.py`, `lighthouse/config.py`, `lighthouse/selftest.py`, `LEEME.txt`; y, si existen, `lighthouse/tips.py`, `lighthouse/tutorial.py` e `lighthouse/intro.py`.

## Precondiciones

- `fases/README.md` marca **F7 ✅** y **F8 ✅** (el selector vive en la pestaña Ayuda, que nace en F8). Si no, detente y avisa.
- Si F9, F10, F11 o F13 están **en curso** en otra sesión, espera: todas tocan `ui.py`. Anota cuáles están ✅: son las superficies que tienes que revisar en los cuatro temas.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.
- **Antes de tocar código**, mide la línea base de CPU con el arnés (ver *Verificación*).

## Objetivo

1. Tres temas nuevos — **vaporwave**, **glass** y **blue ocean** — junto al tema por defecto **oscuro**.
2. Un **selector de tema** en Ayuda que cambia toda la ventana al instante, sin reiniciar, y se recuerda.
3. **Glass**: ventana translúcida que sigue siendo legible con rekordbox detrás, con su fallback opaco.
4. Un self-check que **no deje pasar** un tema incompleto o con poco contraste.

## Alcance

### Entra

**`theme.py`**
- Tres entradas nuevas en `THEMES`: `"vaporwave"`, `"glass"` y `"blue_ocean"`, cada una con `"base": "oscuro"` y **exactamente** los valores de la tabla de `fases/diseno-ui.md` §13.2. No cambies un color "a ojo": si uno no te convence, comprueba el contraste, propón el cambio en la respuesta final y actualiza la tabla de la especificación.
- `NAMES`: los nombres en el orden del selector (`oscuro`, `vaporwave`, `glass`, `blue_ocean`); el texto visible de cada uno es su token `label`.
- La tipografía, los tamaños, el espaciado y los tiempos **no cambian** entre temas (§13.1).
- Funciones puras:
  - `mix(color, behind, alpha)`: mezcla por canal.
  - `contrast_glass(fg, bg, alpha)`: el peor caso de §13.6 (blanco o negro detrás del texto y detrás del fondo, por separado).
  - `check_contrast(theme) -> list[str]`: recorre **todos** los pares de §13.6 (la lista `CONTRAST_PAIRS` de F7; complétala si le falta alguno) y devuelve los que no llegan a su mínimo. Si `window.alpha` < 1, cada par —salvo los del tooltip y la barra de título— debe cumplirlo también con `contrast_glass`.
  - `effective_alpha(theme, hover, transparency_ok) -> float`: `1.0` si `transparency_ok` es falso; `window.alpha_hover` si `hover`; si no, `window.alpha`.
- `apply(root, theme)` aplica además el color de la barra de título (`win32.set_caption_color`, si F7 no lo hizo ya) y la opacidad que devuelva `effective_alpha`.

**`win32.py`**
- `transparency_enabled() -> bool`: lee `EnableTransparency` de `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize` con `winreg` (biblioteca estándar). Si el valor no existe o no se puede leer, `True`.
- Si faltan de F7: `set_dark_titlebar` y `set_caption_color` (atributos 20, 35 y 36 de `DwmSetWindowAttribute`; devuelven `False` sin lanzar en Windows 10).

**`ui.py`**
- **Selector**: pestaña Ayuda → tarjeta `ayuda`, lista desplegable **Tema** (`ayuda.tema`), de solo lectura, con los `label` en el orden de `NAMES`. Regístrala en `App.ids`; si existe `tips.py`, dale su texto del catálogo (§5.4).
- **Vista previa inmediata**: al elegir, se llama a `theme.apply` y la ventana entera cambia en el acto. Sin botón de confirmar, sin reinicio, sin diálogo.
- **Todo se repinta**: estilos `ttk`, widgets registrados con `paint`, ítems de Canvas (medidor, punto de golpe), la ventana de Calibrar si está abierta, la ventana del tooltip, y el anillo y el globo del tutorial si están a la vista. Las muestras de la barra de looks y la vista previa `▌▐` **no** cambian: enseñan los colores reales del show.
  - Ojo con la lista de un `ttk.Combobox`: `option_add` solo afecta a las listas que se creen después. Las que ya se abrieron alguna vez hay que configurarlas directamente (o forzar que se vuelvan a crear).
  - Si encuentras un color guardado en un atributo o pasado suelto a un widget (un fallo de F7–F13), pásalo a `paint` o léelo del tema vigente; no lo parchees solo para tu tema.
- **Glass** (enfoque decidido en §13.4: opacidad de toda la ventana Control con `-alpha`; **no** uses Mica/Acrylic ni `-transparentcolor`):
  - En reposo, `window.alpha` (0,92). Con el puntero dentro de Control, `window.alpha_hover` (1,0): `<Enter>` y `<Leave>` sobre la raíz, comprobando con las coordenadas del puntero que salió de verdad de la ventana (un `<Leave>` hacia un widget hijo no cuenta). **Sin timers.**
  - También opaca mientras el tutorial está activo.
  - El tooltip es otra ventana y **nunca** es translúcido.
  - **Fallback opaco** cuando `win32.transparency_enabled()` es falso, o cuando `-alpha` no se aplica (la llamada lanza, o el valor leído después no es el pedido): glass se dibuja con su misma paleta y opacidad 1,0, se anota en el log y bajo el selector aparece la nota `En este equipo, Glass se muestra sin transparencia.`
  - En Windows 10 `-alpha` funciona igual; solo se pierde el color de la barra de título (queda la oscura estándar).
- **Persistencia**: el tema elegido se guarda en `ui.theme` con el resto de la config y se aplica al arrancar, **antes** de mostrar la ventana (sin destello del tema anterior).

**`config.py`**
- `ui.theme` acepta los cuatro nombres. **Normalización al cargar**: un valor que no sea texto o que no esté en `theme.THEMES` cae a `"oscuro"`, con aviso en el log y sin tocar ninguna otra llave. **No subas la versión** (la llave existe desde F7).

**`LEEME.txt`**
- Una línea: Ayuda → Tema cambia los colores de la ventana de control; no cambia la luz de las pantallas.

**`selftest.py`** (se empaqueta en el exe; se ejecuta con `--test`)
1. **Completitud**: para cada tema, `set(theme.get(n)) == set(theme.get("oscuro"))` y `theme.validate(theme.get(n)) == []`. Ningún tema deja un token sin definir ni inventa uno.
2. **Contraste**: `theme.check_contrast(theme.get(n)) == []` para **cada** tema; si falla, el mensaje nombra tema, par, valor y mínimo. Texto normal ≥ 4,5; texto grande, indicadores y contornos ≥ 3,0; glass, en el peor caso.
3. **La fórmula**: `contrast("#000000", "#FFFFFF") == 21` (± 0,01); `contrast(x, x) == 1`; `contrast("#767676", "#FFFFFF")` ≥ 4,5 y `contrast("#777777", "#FFFFFF")` < 4,5; `contrast(a, b) == contrast(b, a)`; `mix(c, x, 1.0) == c` y `mix("#000000", "#FFFFFF", 0.5)` da gris medio; `contrast_glass(fg, bg, 1.0) == contrast(fg, bg)`.
4. **Repintado**: con `App(headless=True)`, aplica cada tema por turno y comprueba que **cada** widget registrado con `paint` tiene el color de su token en ese tema y que los estilos `ttk` cambiaron; al volver a "oscuro" todo regresa. Mide lo que tarda cada cambio.
5. **El show no se entera**: con cada tema aplicado, `scene.LOOKS` es idéntico y `outputs.compose_output(…)` sobre una instantánea fija devuelve el mismo `Frame`. Con código fuente disponible, `outputs.py` y `pantalla.py` no importan `theme` (se omite en el exe congelado).
6. **Tamaños**: los tamaños pedidos de Control (y de la vista Mini, si F9 está hecha) son los mismos en los cuatro temas.
7. **Opacidad**: `effective_alpha` — glass en reposo 0,92; con `hover` 1,0; con `transparency_ok=False` 1,0; los otros tres temas, siempre 1,0.
8. **Config**: `ui.theme = "no_existe"` y `ui.theme = 7` cargan como `"oscuro"` sin perder otras llaves; cada nombre válido sobrevive a guardar y cargar.

### No entra

- Temas claros, temas definidos por el usuario, editor de colores o un deslizador de opacidad.
- Cambiar la tipografía, los tamaños o la disposición por tema.
- Mica, Acrylic, desenfoque o `-transparentcolor` (probados y descartados, §13.4).
- Tocar `outputs.py`, `pantalla.py`, `scene.py`, los colores de los looks, `PALETTE` o `KELVIN`.
- Variantes de la intro por tema: la intro ya toma `intro_bg`, `intro_fg` y las fuentes de los tokens.
- Nada nuevo en `App.fast()`.

## Diseño decidido

- **"oscuro" es el tema por defecto** y es el mismo que definió F7 (oscuro neutro con acento ámbar). No existe un tema "faro" aparte.
- **Los cuatro temas son oscuros**: la app se usa de noche junto a rekordbox y una ventana clara compite con las pantallas-luz.
- **Glass = `-alpha` de toda la ventana**, con opacidad alta (0,92), opaca al pasar el ratón, y contraste verificado en el peor caso. Es lo único que Tk hace de forma fiable; el color final de Mica/Acrylic no lo controla el tema.
- **Los colores de estado significan lo mismo en todos los temas**: rojo o coral = sin señal y Blackout; ámbar o arena = saturación y avisos; verde = bien.
- **Ningún tema puede entrar sin pasar el contraste**: el self-check es la puerta.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 8 checks nuevos, y termina en < 12 s. **Prueba que el check de contraste muerde**: cambia temporalmente `fg_muted` de un tema por un gris oscuro, confirma que `--test` falla nombrando el tema y el par, y restáuralo. Haz lo mismo quitando un token de un tema (check de completitud).
2. Ayuda → Tema cambia toda la ventana al instante. Al cerrar y abrir, arranca con el tema elegido, sin destello del anterior.
3. **A ojo, con capturas, en los cuatro temas** (script de desarrollo; mira cada imagen): la pestaña Show completa, la pestaña Salidas con una salida seleccionada, una lista desplegable abierta, Blackout activo, un look activo y el chip SIN SEÑAL. Todo el texto se lee, los estados se distinguen y **no queda ningún parche del tema anterior**. Añade, según lo que esté hecho: la vista Mini (tira y bloque), un tooltip, un paso del tutorial con su anillo, y un instante de la intro.
4. **Cambiar de tema 10 veces seguidas** deja la ventana igual que al aplicar ese tema desde el arranque (compara dos capturas), y no crece la memoria ni el número de widgets.
5. **Glass sobre un fondo difícil**: el script de capturas pone **su propia** ventana de prueba detrás de Control, con franjas blancas y negras (vive ≤ 5 s), y captura Control en glass encima. El look activo, el BPM, los chips y las etiquetas de las tarjetas se leen sin esfuerzo. Con el puntero dentro, la ventana es opaca.
6. **Fallback de glass**: simulando en el script `transparency_enabled() == False`, glass se dibuja opaco y aparece la nota bajo el selector. Reporta qué pasa con la barra de título en esta máquina (color aplicado o no).
7. **Las salidas no cambian**: con un look fijo, el color de la Salida 1 es idéntico en los cuatro temas (captura o lectura del `bg` de sus marcos). `--pantalla` no cambia.
8. **Tiempo de cambio de tema** ≤ 100 ms (repórtalo). Durante el cambio, como mucho un pintado de salida se retrasa.
9. **CPU en show**, con el arnés, en cada tema: los cuatro siguen < 10 % y ninguno sube más de 1 punto sobre "oscuro". Si glass no lo cumple, déjalo opaco (`window.alpha` 1,0), documenta la medición y avisa: no bajes otras cosas para compensar.
10. La barra de título acompaña al tema (oscura; con el color del tema en Windows 11).
11. `.\build.ps1` pasa; el exe cambia de tema y pasa `--test`. Reporta el tamaño.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
python -c "from lighthouse import theme; [print(n, theme.check_contrast(theme.get(n)) or 'ok') for n in theme.NAMES]"
```
```powershell
Select-String -Path lighthouse\outputs.py, lighthouse\pantalla.py -Pattern 'theme'
```

**Arnés de CPU** (script de desarrollo en `$env:TEMP`): apunta `$env:APPDATA` a una carpeta temporal, crea `App()`, aplica el tema, cierra el audio real, alimenta `app.on_block(x)` con un bombo sintético a 100 bloques/s durante 4 s, mide `time.process_time()` / tiempo real y cierra con `app.quit()` en un `finally`. Tres corridas por tema; reporta el rango. Úsalo **antes** de empezar (solo "oscuro") y al final (los cuatro).

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_cpu.py"; Remove-Item Env:\APPDATA
```

**Capturas** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí): por cada tema, abre la app con config temporal, aplica el tema, espera ~1,5 s, captura el rectángulo de Control (`win32.window_rect`) y cierra en `finally`. Cada ventana vive ≤ 5 s (una ejecución por tema y por vista si hace falta). Para glass, la ventana de franjas de prueba se crea y se destruye en el mismo script. Lee las imágenes.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py` (`winreg` es biblioteca estándar y también va ahí).
- **Apariencia**: ningún color suelto; todo desde `theme.py`. Los colores de los temas viven **solo** en `THEMES`.
- **Rendimiento**: ningún timer nuevo. Nada nuevo en `App.fast()` ni en `App.slow()`. La opacidad de glass cambia por eventos.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): nada de pantalla completa, automatización de escritorio ni navegadores.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. Si una fase posterior aún no existe (mini, tooltips, tutorial, intro), no la adelantes: deja en el README la nota de que debe revisarse en los cuatro temas. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F14 → ✅, fecha y nota de una línea (tiempo de cambio de tema, CPU por tema, si glass quedó translúcido u opaco, resultado de la barra de título, tamaño del exe, pendientes: verlo junto a rekordbox real y en un Windows 10). Si quedan fases de la etapa sin hacer, agrega una nota para ellas: sus capturas se revisan en los cuatro temas y sus widgets `tk` usan `theme.paint`.
2. Responde al usuario con:
   - qué cambió y cómo cambiar de tema;
   - una captura por tema (rutas) y las mediciones;
   - los colores que hayas propuesto cambiar respecto a la especificación, con su contraste;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): temas oscuro, vaporwave, glass y blue ocean con selector`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
