# Fase F13: Intro — implementación de la animación elegida

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`. Si la propuesta elegida necesita volver a renderizar, la sesión necesita **Blender 5.2+** instalado (lo invoca `tools/intro/generar.ps1` en segundo plano).

## Rol

Eres un desarrollador Python senior con oficio en Tkinter (Canvas, `PhotoImage`, rendimiento del hilo de interfaz) y en empaquetado con PyInstaller. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes.

Paquete `lighthouse/`: `engine.py`, `audio.py`, `scene.py`, `outputs.py`, `net.py`, `pantalla.py` (receptor `--pantalla`), `win32.py` (**todo** el ctypes), `config.py`, `theme.py` (tokens), `layout.py`, `tips.py`, `tutorial.py`, `selftest.py`, `ui.py` (ventana **Control**) y `__main__.py`. `build.ps1` + `lighthouse.spec` generan el exe (~57 MB; hoy el spec no empaqueta archivos de datos).

En F12 se produjeron tres propuestas de animación de entrada con Blender y **el usuario eligió C · "Primer golpe" sin audio** (`fases/intro-propuestas/ELEGIDA.md`; esa carpeta es local e ignorada por git). La lente parpadea con una **pista autoral fija** del manifiesto (pista `nivel`). La intro **no lee el audio ni el dispositivo**.

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**: Pillow no va en el exe; `PhotoImage` con PNG nativo sí. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos** (`after(1)` gira al 98 %). El pintado de las salidas vive en `App.fast()`; lo vivo de Control, en `App.slow()` (~30 Hz).
- Las salidas de luz nunca usan Canvas. **Un Canvas chico en Control es aceptable, midiendo su costo.**
- La intro debe ser barata, omitible y **nunca retrasar el show**: el audio y las salidas arrancan en paralelo; una tecla o un clic la salta.
- Las teclas de show se leen con `GetAsyncKeyState`. ctypes solo en `win32.py`. Config JSON versionada.

## Lee primero

1. `fases/intro-propuestas/ELEGIDA.md` (trae el manifiesto sugerido y la nota de rendimiento) y la carpeta `fases/intro-propuestas/C-primer-golpe/` (`storyboard.md`, `params.json`, `build.py`, `tira.png`).
2. `fases/diseno-ui.md`: **§7 completo** (reglas, **qué significa "sin hardcode"**, formato del manifiesto, presupuesto), §8 (`ui.intro`), §9 (tokens `intro_bg`, `intro_fg`, `font.intro`).
3. `fases/README.md`: sección *Etapa 2: interfaz* (notas de las fases anteriores) y *Arquitectura → Latencia*.
4. `lighthouse/ui.py` (`__init__`, `fast`, `slow`, `put`), `lighthouse/theme.py`, `lighthouse/__main__.py`, `lighthouse/selftest.py`, `lighthouse.spec`, `build.ps1`, `LEEME.txt`.

## Precondiciones

- `fases/README.md` marca **F12 ✅** y existe `fases/intro-propuestas/ELEGIDA.md` (en la carpeta local, no en git). Si no, **detente y pregunta al usuario cuál elige**.
- `fases/README.md` marca **F8 ✅** como mínimo (hace falta `ui` en la config y la pestaña Ayuda). Si F9, F10 o F11 están en curso en otra sesión, espera a que terminen: todas tocan `ui.py`.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.
- **Antes de tocar código**, mide: tiempo de arranque hasta que la ventana Control es visible, tiempo hasta el primer pintado de una salida, y CPU en show con el arnés (ver *Verificación*).

## Objetivo

1. Un **reproductor genérico** que interpreta un manifiesto JSON y muestra la intro dentro de Control.
2. Los **assets finales** de la propuesta elegida, dentro del presupuesto, empaquetados en el exe.
3. Omitir con cualquier tecla o clic; desactivar desde Ayuda y por línea de comandos.

## Alcance

### Entra

**Assets: `assets/intro/`**
- `intro.json` (el manifiesto; `ELEGIDA.md` trae uno sugerido) + los 16 PNG `lente_00…lente_15`, generados con el generador de C desde `tools/intro/`. Si hay que ajustar algo, se cambia `params.json` y se vuelve a renderizar; **no se retocan imágenes a mano**.
- PNG de 8 bits, luz neutra (blancos y grises). Presupuesto: **≤ 3 MB** en total. Si se pasa: menos cuadros, lienzo 480×270 o paleta reducida — decisiones que quedan en el manifiesto y en `params.json`.
- La versión, el nombre del dispositivo y cualquier texto variable **no** van en los PNG.
- `lighthouse.spec`: agrega `assets/intro` a `datas`. Una función `resource_path()` resuelve la carpeta tanto desde el código fuente como desde el exe congelado (`sys._MEIPASS`).

**Generador: `tools/intro/`** (va al repo y **no** entra al exe; `fases/intro-propuestas/` es local e ignorada por git)
- Copia desde `fases/intro-propuestas/`:
  - `generar.ps1`, `comun.py` y `app.json`;
  - `C-primer-golpe/` con `build.py`, `params.json`, `escena.blend` y `storyboard.md`;
  - `ELEGIDA.md`, que pasa a ser `tools/intro/LEEME.md`.
- Las rutas ya funcionan desde ahí. Comprueba con `.\tools\intro\generar.ps1 -Concepto C-primer-golpe` que se regeneran los mismos cuadros:
  - `generar.ps1` busca la raíz del repo hacia arriba y reescribe `app.json` a su lado;
  - `build.py` importa `comun.py` de su carpeta o de la de arriba.
- En `.gitignore`: `tools/intro/*/cuadros/`, `tools/intro/*/capas/` y `tools/intro/*/*.blend1`.
- Los PNG finales se copian de `tools/intro/C-primer-golpe/cuadros/` a `assets/intro/`. `lighthouse.spec` nunca empaqueta `tools/`.

**Nuevo `lighthouse/intro.py`**
- **`load(path) -> Manifest | None`**: lee y **valida** `intro.json` (formato de `fases/diseno-ui.md` §7.3). Cualquier error — archivo ausente, JSON inválido, capa de tipo desconocido, PNG que falta, duración > 3000 ms — devuelve `None` y deja un aviso en el log. **Nunca lanza.**
- **`value(track, t_ms)`**: función **pura** que interpola una pista `[[t_ms, valor, easing?], …]`. Easings: `lineal`, `in_cubic`, `out_cubic`, `in_out`, `corte`. Antes del primer punto vale el primero; después del último, el último.
- **`frame_index(layer, t_ms)`**: función **pura**: cuadro de una capa `secuencia` por tiempo (`fps`) o por `"cuadro_por": "nivel"`, con el nivel 0..1 tomado de la pista `nivel` de la propia capa (`round(nivel × (cuadros − 1))`; es el parpadeo autoral de C, no el nivel de audio).
- **`resolve(texto, datos)`** y **`color(ref, theme, looks)`**: funciones puras: rellenan `{app}`, `{version}` y `{autor}`, y resuelven `"token:…"` / `"look:N"`. Una referencia desconocida cae a `intro_fg` con aviso.
- **`Intro(app, manifest)`**:
  - Una capa que cubre Control: un `Frame` con `place(relwidth=1, relheight=1)` de color `fondo`, con **un Canvas del tamaño del lienzo** centrado.
  - Tipos de capa: `secuencia`, `imagen`, `texto` (ítem de texto del Canvas con la fuente del token) y `color` (rectángulo).
  - **`tick(now)`** se llama desde `App.slow()` mientras la intro está viva. Calcula el tiempo transcurrido, actualiza **solo lo que cambió** y, al pasar `duracion_ms`, termina. **Ningún `after` propio.** Si un tick llega tarde, salta cuadros (va por tiempo, no por contador).
  - **Carga perezosa**: como mucho **un** `PhotoImage` decodificado por tick; nada de precargar todos los cuadros en `__init__`. Al terminar se liberan todas las imágenes y se destruye la capa.
    - Medido en F12 (Tk 8.6.15, 640×360 en gris): `PhotoImage(file=…)` ≈ 4,3 ms (p95 4,9), por encima del presupuesto; `PhotoImage(data=…)` con los bytes leídos al empezar (0,5 MB) ≈ 3,1 ms (p95 3,5).
    - Usa esa vía: decodifica en el primer uso, reutiliza las imágenes ya decodificadas (la pista repite cuadros) y, en los ticks libres, adelanta el siguiente cuadro de la pista.
  - Con escala de pantalla ≥ 200 % las imágenes se amplían con `zoom(2)`; si no, tamaño natural.
- **El reproductor no contiene nada específico de la propuesta elegida**: ni coordenadas, ni tiempos, ni textos, ni colores, ni nombres de archivo. Probarlo con un segundo manifiesto mínimo debe funcionar sin tocar `intro.py`.

**`ui.py`**
- La intro se crea **al final de `App.__init__`**, después de abrir el audio y crear las salidas: cuando la ventana aparece, el show ya corre. `App.fast()` no se toca: las salidas pintan debajo durante la intro.
- **No hay intro** si: `ui.intro` es `false`; se pasó `--sin-intro`; `headless`; la vista inicial es Mini; la ventana es más chica que el lienzo; o `load()` devolvió `None`.
- **Omitir**: cualquier tecla (`<Key>` sobre la raíz) o clic (`<Button>`) la quita al instante. Además, si `poll_keys` detecta una tecla de show durante la intro, la intro se quita **y la acción se ejecuta** (el `2` salta la intro y pone el look 2).
- Durante la intro: los tooltips callan y la banda "¿Ver tutorial?" espera; aparece al terminar.
- Pestaña Ayuda → tarjeta `ayuda`: casilla **"Animación de entrada"** (`ayuda.intro`, `ui.intro`, activa por defecto), registrada en `App.ids` y con texto en `tips.TIPS`.
- La intro no lee el motor ni la lista de dispositivos: el parpadeo sale solo de la pista `nivel` del manifiesto.

**`__main__.py`**
- Opción `--sin-intro`. `--pantalla` y `--test` nunca muestran intro.

**`config.py`**
- En `ui`: `intro` (`true`). Llave nueva con default: **no subas la versión**.

**`LEEME.txt`**
- Una línea: la animación de entrada se salta con cualquier tecla o clic y se desactiva en Ayuda → Animación de entrada.

**`selftest.py`**
1. **Manifiesto real**: `intro.load()` sobre `assets/intro/intro.json` devuelve un manifiesto válido; todos sus archivos existen; `duracion_ms ≤ 3000`; el peso total de la carpeta es ≤ 3 MB.
2. **`value`**: puntos conocidos de cada easing (inicio, mitad y fin), antes del primer punto, después del último, y `corte` (cambia de golpe).
3. **`frame_index`**: por tiempo (t = 0, mitad, final y más allá del final → último cuadro) y por nivel (0 → primer cuadro, 1 → último, 0,5 → el de en medio).
4. **`resolve` y `color`**: `{version}` da `lighthouse.VERSION`; `token:intro_fg` da el color del tema; `look:2` da el rojo de `scene.LOOKS`; una referencia desconocida no lanza.
5. **Manifiesto roto**: sin archivo, con JSON inválido, con una capa de tipo desconocido y con un PNG que falta → `load()` devuelve `None` sin lanzar.
6. **Genérico**: un manifiesto mínimo de prueba (una capa `color` y una `texto`, creado en una carpeta temporal) carga y se reproduce con `Intro` en `App(headless=True)` llamando a `tick()` con tiempos simulados hasta el final; al terminar no queda la capa ni imágenes vivas.
7. **Sin hardcode**: en el código fuente de `intro.py` no aparece ningún nombre de archivo PNG ni literal de color (se omite en el exe congelado).
8. **Omitir**: llamar a `skip()` a mitad deja la app igual que si la intro hubiera terminado.

### No entra

- Las otras dos propuestas. Un selector de intros en la interfaz.
- Sonido en la intro. Intro en las salidas de luz o en `--pantalla`.
- Variantes de la intro por tema (los temas son de F14; la intro ya toma sus colores de los tokens).
- Cambios en `App.fast()` o en el motor.

## Diseño decidido

- **"Sin hardcode"** = reproductor genérico + manifiesto + textos de la app + colores de tokens/looks + assets regenerables por script. Cambiar de intro es cambiar la carpeta `assets/intro/`.
- La intro vive **dentro de Control** y empieza cuando el show ya está corriendo; no es una pantalla de carga.
- El reloj es `slow()`; la intro va por tiempo transcurrido.
- Si algo falla, **no hay intro**: nunca un error visible ni un arranque más lento.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 8 checks nuevos.
2. **A ojo, con capturas** en 3–4 instantes de la intro (script de desarrollo): corresponde al storyboard de la propuesta elegida; el nombre y `v1.0.0` se leen; los colores salen del tema.
3. **No retrasa el show** (mide y reporta, contra la línea base tomada al empezar):
   - tiempo hasta que Control es visible: no sube más de 100 ms;
   - tiempo hasta el primer pintado de una salida: no sube más de 20 ms;
   - durante la intro, con audio sintético, el costo de cada `tick()` es ≤ 4 ms (p95) y ningún pintado de salida se retrasa más de 5 ms por culpa de la intro. Instrumenta `fast()` y `tick()` **solo en el script de medición**, no en el código de la app.
   Si no se cumple, reduce cuadros o resolución **en el manifiesto y en `params.json`**, y vuelve a medir.
4. Cualquier tecla o clic la quita al instante; presionar `2` durante la intro la quita **y** pone el look 2.
5. Con la casilla apagada o con `--sin-intro` no aparece; `--pantalla` nunca la muestra. Al arrancar en vista Mini no aparece.
6. Renombrar temporalmente `assets/intro/intro.json`: la app arranca normal, sin intro, con un aviso en el log (restáuralo después).
7. Cambiar `VERSION` temporalmente a `9.9.9` cambia el texto de la intro sin tocar ningún asset (restáuralo después).
8. **CPU en show** una vez terminada la intro: igual que antes de la fase (± 0,5 puntos). Reporta el número.
9. `.\build.ps1` pasa; el exe muestra la intro (los assets viajan dentro) y pasa `--test`. El exe crece ≤ 5 MB y queda ≤ 62 MB. Reporta ambos tamaños.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
"{0:N2} MB" -f ((Get-ChildItem assets\intro -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
```
```powershell
python -m lighthouse --sin-intro
```

**Arnés de medición** (script de desarrollo en `$env:TEMP`): apunta `$env:APPDATA` a una carpeta temporal, crea `App()`, cierra el audio real y alimenta `app.on_block(x)` con un bombo sintético a 100 bloques/s durante 4 s. Mide: `time.process_time()` / tiempo real; tiempo de arranque hasta `winfo_viewable()`; duración de cada `tick()` de la intro; y el intervalo entre un bloque de audio y su pintado, con y sin intro. Cierra con `app.quit()` en un `finally`. Tres corridas.

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_intro.py"; Remove-Item Env:\APPDATA
```

**Capturas** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí): abre la app con config temporal y captura el rectángulo de Control a los ~0,3 s, ~1 s y ~2 s. La app vive ≤ 5 s y se cierra en `finally`. Lee las imágenes.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Pillow y Blender son herramientas de desarrollo: no entran en `requirements.txt` ni en el exe. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Apariencia**: todo desde `theme.py`; ningún color, fuente o medida suelta en `intro.py` ni en `ui.py`. Las referencias `token:…` se resuelven con el tema vigente al empezar la intro (F14 agrega más temas).
- **Rendimiento**: ningún timer nuevo. Nada nuevo en `App.fast()`. En `App.slow()`, solo la llamada a `tick()` mientras la intro vive.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): nada de pantalla completa, automatización de escritorio ni navegadores. Blender, si se usa, en segundo plano.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. Si la propuesta elegida no se puede reproducir dentro del presupuesto de costo, detente y propón al usuario la simplificación (menos cuadros, lienzo menor) antes de aplicarla.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F13 → ✅, fecha y nota de una línea (propuesta implementada, peso de los assets, costo por tick, tiempos de arranque antes/después, CPU, tamaño del exe, pendientes).
2. Responde al usuario con:
   - qué cambió;
   - cómo verla, saltarla y desactivarla;
   - las mediciones y qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): animación de entrada dirigida por manifiesto`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
