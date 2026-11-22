# Fase F11: Tutorial interactivo omisible

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior con oficio en Tkinter y en diseño de primeras experiencias (onboarding) para herramientas en vivo. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes. La usa un DJ, no un técnico.

Paquete `lighthouse/`: `engine.py`, `audio.py`, `scene.py`, `outputs.py`, `net.py`, `pantalla.py`, `win32.py` (**todo** el ctypes), `config.py`, `theme.py` (tokens, F7), `layout.py` (F8), `tips.py` (tooltips, F10), `selftest.py`, `ui.py` (ventana **Control**: barra de looks, franja En vivo, pestañas Show / Audio / Salidas / Ayuda con tarjetas; vista Mini) y `__main__.py`.

Cada control está registrado en `App.ids` con un `id` estable (`look.2`, `audio.dispositivo`, `blackout`…): son los **objetivos** del tutorial.

**Lo que pidió el usuario**: un tutorial interactivo, **omisible**: *que sea decisión del usuario consultarlo*.

**Restricciones duras del proyecto** (medidas; no se discuten):
- Solo Tkinter/ttk. **Ninguna dependencia nueva**. Exe ≤ 80 MB.
- CPU < 10 % de un núcleo en show.
- **Nunca timers `after(n)` cortos ni periódicos nuevos**. Lo vivo de Control corre en `App.slow()` (~30 Hz) con `App.put()`.
- Las salidas de luz nunca usan Canvas.
- Las teclas de show se leen con `GetAsyncKeyState` y se pausan al escribir en un campo de texto. **El tutorial no debe romper ni pausar las teclas**: la luz sigue funcionando mientras se muestra.
- ctypes solo en `win32.py`. Config JSON versionada.

## Lee primero

1. `fases/README.md`: sección *Etapa 2: interfaz* (notas de F7–F10).
2. `fases/diseno-ui.md`: **§6 completo** (primer arranque, mecánica y **tabla de pasos**), §5.3 (identificadores), §8 (`ui.tutorial`), §9.2 (token `tutorial_ring`), §10.
3. `lighthouse/ui.py`, `lighthouse/tips.py`, `lighthouse/layout.py`, `lighthouse/theme.py`, `lighthouse/selftest.py`, `LEEME.txt`.

## Precondiciones

- `fases/README.md` marca **F10 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.

## Objetivo

1. Un recorrido guiado de ~2 minutos que resalta un control por paso y avanza solo cuando el usuario hace lo que se le pide.
2. En el primer arranque, una **pregunta no modal**: "¿Ver tutorial?", con "No volver a preguntar".
3. Se omite en cualquier momento y se repite desde Ayuda.

## Alcance

### Entra

**Nuevo `lighthouse/tutorial.py`**
- **`STEPS`**: lista de pasos como **datos**: `id` objetivo (o `None` para un paso centrado), pestaña que debe estar abierta, título, texto, y condición opcional de avance (`done(app) -> bool`). Contenido: la tabla de `fases/diseno-ui.md` §6.3 (10 pasos). Puedes pulir la redacción con las reglas de §5.2.
- **`ring_rects(x, y, w, h, grosor, margen) -> 4 rectángulos`**: función pura con los cuatro lados del anillo alrededor del objetivo.
- **`bubble_pos(target, bubble, window) -> (x, y)`**: función pura. Coloca el globo debajo del objetivo si cabe; si no, arriba, a la derecha o a la izquierda; **nunca encima del objetivo ni fuera de la ventana**; sin objetivo, centrado.
- **`Tutorial(app)`**:
  - **Anillo**: 4 `Frame` delgados (3 px lógicos, color `tutorial_ring`) con `place()` sobre la raíz, por encima de todo. **Sin Canvas y sin capa oscura.**
  - **Globo**: un `Frame` con `place()` sobre la raíz: `Paso N de M`, título (`font.title`), texto (ajustado a ~300 px lógicos) y botones **Atrás** · **Siguiente** · **Omitir tutorial**. En el último paso, "Siguiente" dice **Terminar**. Los botones **no toman el foco** y no hay ningún campo de texto.
  - **Avance**: `tick()` se llama desde `App.slow()` **solo mientras el tutorial está activo**; evalúa `done(app)` del paso actual. **Ningún timer nuevo.**
    - Si la condición **ya se cumple al mostrar el paso** (el audio ya funcionaba, ya había BPM), el paso **no avanza solo**: el globo muestra `✓ Ya está` y espera a Siguiente. Si avanzara, el paso pasaría sin que nadie lo lea.
    - Si se cumple después, el globo muestra `✓ Hecho` y avanza unos 700 ms más tarde, medidos por `tick()` con el reloj (`time.perf_counter()`), no con un `after`.
  - **Sin ratón**: `Enter` hace de Siguiente y `Esc` omite (bindings de Tk sobre la raíz, solo durante el tutorial). No actúan si el foco está en un campo de texto o en un control: ahí `Enter` y `Esc` conservan su función (terminar de escribir, devolver el foco). El pie del globo lo recuerda: `Enter: siguiente · Esc: omitir`.
  - Antes de mostrar un paso: abre su pestaña; si el objetivo está dentro de un "Avanzado" cerrado, lo abre; si la vista es Mini, pasa a la automática (y la restaura al terminar). Si el objetivo aun así no está visible, el globo sale centrado y sin anillo.
  - El anillo y el globo se recolocan cuando cambia el layout o el tamaño de la ventana.
  - **Omitir**: botón o `Esc` (binding de Tk sobre la raíz, activo solo durante el tutorial; `Esc` no es tecla de show). Quita anillo y globo y deja la app como esté.
  - Mientras hay un paso activo, los tooltips quedan en silencio; al terminar vuelven.
- Las condiciones solo **leen** estado (`app.scene.look`, `app.scene.blackout`, señal, BPM). El tutorial **no cambia** looks ni ajustes por su cuenta.
- El paso de Blackout se cumple cuando se activó **y** se desactivó, para no dejar las pantallas apagadas.

**`ui.py`**
- **Banda de primer arranque** (no modal, entre la franja En vivo y las pestañas): `¿Primera vez con LightHouse? Recorrido de 2 minutos.` + **Ver tutorial** + **Ahora no** + casilla **No volver a preguntar**.
  - Solo aparece si `ui.tutorial == "preguntar"`, la vista no es Mini y no se está mostrando la intro (si existe; aparece cuando termina).
  - **Ver tutorial** → empieza; al terminar u omitir queda `ui.tutorial = "visto"`.
  - **Ahora no** → oculta la banda; con la casilla marcada queda `"no_preguntar"`, sin marcar vuelve a preguntar en el próximo arranque.
  - La banda no bloquea nada: looks, teclas y audio funcionan con ella a la vista.
- Pestaña Ayuda → tarjeta `ayuda`: botón **Ver tutorial** (`ayuda.tutorial`), siempre disponible.
- Registra los controles nuevos en `App.ids` y dales texto en `tips.TIPS` (el check de cobertura de F10 debe seguir pasando): `ayuda.tutorial`, `tut.ver`, `tut.ahora_no`, `tut.no_preguntar`, `tut.atras`, `tut.siguiente`, `tut.omitir`.

**`config.py`**
- En `ui`: `tutorial` (`"preguntar"` · `"no_preguntar"` · `"visto"`; default `"preguntar"`; valor inválido → default). Llave nueva con default: **no subas la versión**.

**`LEEME.txt`**
- Una línea en la guía rápida: el tutorial se ofrece al abrir por primera vez y se repite desde Ayuda → Ver tutorial.

**`selftest.py`**
1. **Objetivos válidos**: con `App(headless=True)`, cada `id` de `STEPS` existe en el registro de controles y cada pestaña nombrada existe.
2. **Textos**: cada paso tiene título y texto no vacíos; texto ≤ 240 caracteres.
3. **`ring_rects`**: los 4 rectángulos rodean el objetivo sin taparlo (ninguno intersecta el rectángulo del objetivo) y respetan grosor y margen.
4. **`bubble_pos`**: con el objetivo en el centro, en cada borde y en cada esquina de una ventana de 1366×700 y de una de 700×420, el globo queda dentro de la ventana y no intersecta el objetivo; sin objetivo queda centrado.
5. **Recorrido completo sin ventana**: iniciar, `Siguiente` hasta el final y terminar deja `ui.tutorial == "visto"`, sin anillo ni globo colocados y con la vista original restaurada. `Atrás` en el paso 1 no hace nada.
6. **Avance por acción**: en el paso del look 2, seleccionar el look 2 (`app.select_look("2")`) y llamar a `tick()` con un reloj simulado marca el paso como hecho y, pasados 700 ms, avanza. Si el look 2 **ya estaba** activo al mostrar el paso, `tick()` no avanza: espera a Siguiente.
7. **Estados de la pregunta**: `"preguntar"` + Ahora no sin casilla → sigue `"preguntar"`; con casilla → `"no_preguntar"`; omitir a mitad → `"visto"`.
8. **Las teclas no se pausan**: con el tutorial activo, la función que decide si las teclas disparan (la de F8) sigue devolviendo lo mismo que sin tutorial.

### No entra

- Videos, imágenes o animaciones dentro del tutorial. Capa oscura sobre la ventana.
- Tutorial para la laptop de visuales (`--pantalla`) o para las salidas.
- Un asistente de configuración que cambie ajustes por el usuario.
- Intro (F12–F13), temas.

## Diseño decidido

- La pregunta inicial es una **banda dentro de Control**, no un diálogo: nunca bloquea el show.
- El tutorial **enseña haciendo**: presionar `2` durante el paso de looks cambia el look de verdad.
- Los pasos son **datos** en un módulo; agregar o reordenar pasos no toca el mecanismo.
- El resaltado es un anillo de 4 marcos: barato, sin Canvas y compatible con cualquier tema.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa, incluidos los 8 checks nuevos.
2. Con una config nueva, al abrir aparece la banda; la luz y las teclas funcionan con ella a la vista. "Ahora no" la quita; con la casilla marcada no vuelve a salir.
3. **A ojo, con capturas** de al menos los pasos 1, 2, 4, 6 y 8 (script de desarrollo): el anillo rodea el control correcto, el globo se lee completo, no tapa el objetivo y no sale de la ventana. Repite el paso 4 en una ventana de 946×1010 y en una de 700×420 px lógicos.
4. En el paso 4, presionar `2` (tecla real o `app.key_action("2")` en el script) avanza solo; en el paso 6, activar y desactivar Blackout avanza solo. `Siguiente` y `Enter` siempre funcionan. Con música ya sonando al empezar, los pasos 2 y 3 **no se saltan solos**: muestran `✓ Ya está`.
5. `Esc` y "Omitir tutorial" lo cierran en cualquier paso, sin dejar el anillo ni el globo, y sin dejar las pantallas en blackout.
6. Ayuda → Ver tutorial lo repite cuantas veces se quiera.
7. Si se inicia desde la vista Mini, pasa a la vista normal y al terminar vuelve a Mini.
8. Redimensionar la ventana durante un paso recoloca anillo y globo.
9. **CPU en show** con el tutorial cerrado: igual que antes de la fase (± 0,5 puntos). Con un paso activo: < 10 %. Reporta ambos.
10. `.\build.ps1` pasa y el exe hace todo lo anterior.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```

**Arnés de CPU** (script de desarrollo en `$env:TEMP`): apunta `$env:APPDATA` a una carpeta temporal, crea `App()`, cierra el audio real, alimenta `app.on_block(x)` con un bombo sintético a 100 bloques/s durante 4 s, mide `time.process_time()` / tiempo real y cierra con `app.quit()` en un `finally`. Con el tutorial cerrado y con un paso activo; tres corridas.

```powershell
$env:APPDATA = Join-Path $env:TEMP "lh_cfg"; python "$env:TEMP\lh_cpu.py"; Remove-Item Env:\APPDATA
```

**Capturas** (script de desarrollo en `$env:TEMP`; Pillow `ImageGrab` solo aquí): abre la app con config temporal, inicia el tutorial, salta al paso indicado, captura el rectángulo de Control y cierra en `finally`. Cada ventana vive ≤ 5 s (una ejecución por paso si hace falta). Lee las imágenes.

```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Apariencia**: todo desde `theme.py`; ningún color, fuente o medida suelta. Widgets `tk` clásicos e ítems de Canvas, con `theme.paint` (un cambio de tema debe repintarlos).
- **Rendimiento**: ningún timer nuevo. Nada nuevo en `App.fast()`. En `App.slow()`, solo la llamada a `tick()` cuando el tutorial está activo.
- **Ventanas de prueba**: viven ≤ 5 s y se cierran en un `finally`. El usuario está usando la máquina (3 monitores): nada de pantalla completa, automatización de escritorio ni navegadores.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: cambios mínimos. No adelantes F12–F13. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F11 → ✅, fecha y nota de una línea (número de pasos, CPU, pendientes: probarlo con una persona que no conozca la app). Agrega una nota para F13: la banda de primer arranque espera a que termine la intro.
2. Responde al usuario con:
   - qué cambió;
   - los textos de los pasos, para que los revise;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(ui): tutorial interactivo omisible con pregunta de primer arranque`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
