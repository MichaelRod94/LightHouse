# Fase F12: Intro — tres propuestas de animación de entrada (Blender)

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`. La sesión necesita las herramientas de **Blender por MCP**.

## Rol

Eres un diseñador de motion graphics y artista técnico de Blender (Python `bpy`, luz volumétrica, render por lotes), con criterio de marca. Produces **tres previsualizaciones** de una animación de entrada y **te detienes para que el usuario elija**. **No escribes código de la app** en esta fase.

## Proyecto

**LightHouse** (v1.0.0) es una app de escritorio Python/Tkinter para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en pantallas sin bordes: color sólido, cortes duros contra negro, estrobos y pantalla partida. Referencia visual del cliente: una pantalla LED entera en un color saturado que se prende y se apaga con cada golpe.

El usuario pidió una **introducción dinámica al abrir la app**, **"sin hardcode"**, y ver **tres propuestas** para elegir.

**Cómo se reproducirá después** (fase F13; condiciona lo que produces aquí):
- Dentro de la ventana Control, en un lienzo de **640×360**, con Tkinter puro: imágenes **PNG** (`PhotoImage` nativo, **sin Pillow**), rectángulos de color y texto dibujado por la app.
- Tk **no** tiene transparencia por capa ni escalado fraccionario: un fundido es una secuencia de cuadros ya renderizados; una imagen se muestra a su tamaño.
- La intro dura **≤ 3 s**, se salta con cualquier tecla o clic y **no retrasa el show**: el audio y las pantallas arrancan en paralelo.
- Presupuesto: assets finales ≤ **3 MB** dentro del ejecutable.
- **"Sin hardcode"** significa (ver `fases/diseno-ui.md` §7.2): reproductor genérico + **manifiesto JSON** de capas, tiempos y easing; textos y versión tomados de la app; colores tomados de los tokens del tema o de los looks; assets regenerables con un comando. Por eso las imágenes de Blender deben ser **luz neutra** (blancos y grises sobre negro o transparente) y **la versión nunca va pintada en un PNG**.

## Lee primero

1. `fases/diseno-ui.md`: **§7 completo** (reglas, "sin hardcode", formato del manifiesto, **los tres conceptos con su storyboard** y presupuesto) y §9.3 (tema por defecto: fondo negro, texto blanco, acento ámbar `#FFC53D`).
2. `fases/README.md`: *Referencia visual* y sección *Etapa 2: interfaz*.
3. `lighthouse/scene.py` (colores de los looks: la propuesta B los usa) y `lighthouse/__init__.py` (`VERSION`, `__author__`).
4. `assets/` (el icono actual, por si sirve de referencia de marca).

## Precondiciones

- Esta fase **no depende** de F7–F11 y no toca `lighthouse/`: puede correr en paralelo con ellas.
- **Blender disponible**: comprueba que `mcp__Blender__execute_blender_code_for_cli` responde (ejecuta un script mínimo que devuelva `bpy.app.version_string`) y anota la versión. Si no está disponible, prueba `blender --version` en PowerShell y usa `blender --background --python <script>`. **Si no hay Blender por ninguna vía, detente y avisa**: no simules los renders con otra herramienta.
- `git status`.

## Objetivo

Dejar en `fases/intro-propuestas/` tres carpetas — `A-faro`, `B-pulso`, `C-primer-golpe` — cada una con una previsualización que el usuario pueda abrir con doble clic, y **detenerse** con una comparación clara para que elija.

## Alcance

### Entra

**Preparación común**
- Crea `fases/intro-propuestas/` con una subcarpeta por concepto.
- Genera `fases/intro-propuestas/app.json` con datos **leídos de la app, no escritos a mano**: nombre (`LightHouse`), `VERSION`, `__author__` y los colores de los looks 2 (rojo), 3 (azul) y 4 (morado) de `scene.LOOKS`. Sale de un comando de una línea de Python que importa `lighthouse` y `lighthouse.scene`.
- Cada concepto tiene:
  - **`params.json`**: lienzo (`[640, 360]`), cuadros por segundo, duración, y los parámetros artísticos propios (ángulos, intensidades, textos). Es lo único que se edita para ajustar la animación.
  - **`build.py`**: script de Blender que **construye la escena desde cero** leyendo `params.json` y `../app.json`, y la guarda como `escena.blend`. Nada se modela a mano en la interfaz de Blender.
  - **`render.py`** (o una opción de `build.py`): renderiza los cuadros PNG a `cuadros/` y el video a `preview.mp4` (codificador FFmpeg que trae Blender, H.264).
- Corre Blender **en segundo plano**. Los tres conceptos son independientes: si conviene, lánzalos **en paralelo** (un agente por concepto, cada uno con su carpeta y su `.blend`); si no, uno tras otro.
- Motor de render: el más rápido que dé el resultado (EEVEE para A y C; B casi no necesita 3D). Ningún render debería tardar más de unos minutos: son 640×360 y ≤ 3 s.

**Los tres conceptos** (storyboard y tiempos exactos en `fases/diseno-ui.md` §7.4; aquí lo esencial)

- **A · "Faro"** — 2,4 s, ~48 cuadros a 20 fps. Silueta de un faro abajo a la izquierda; la lámpara se enciende; un **haz volumétrico** barre de izquierda a derecha y va dejando iluminado el nombre en 3D. Cámara fija. Todo en luz neutra sobre negro.
- **B · "Pulso"** — 1,8 s. Tres golpes: el cuadro se parte en **dos mitades** que destellan como las salidas reales (rojo a la derecha, morado a la izquierda, y el tercero todo blanco), con **corte duro a negro** entre golpes; el nombre queda en blanco sobre negro. En la app final los destellos serán rectángulos de color dibujados por Tk con los colores de los looks; **en el preview simúlalos en Blender** con planos emisivos que usen los colores de `app.json`. Lo único que se renderiza como asset es el nombre con resplandor (~6 cuadros de brillo).
- **C · "Primer golpe"** — 2,6 s. Primer plano de la **lente de un faro** (cristal facetado), apagada, que **brilla con el nivel del audio real**. Asset: **16 cuadros** del mismo encuadre, de "apagada" a "a tope" (es una escala de brillo, no una animación temporal). Para el preview, anima esa escala con un patrón de bombo a 128 BPM (golpe y caída) y añade debajo el texto de ejemplo `Escuchando: Salida (loopback) · Altavoces`.

En los tres, el nombre de la app sale de `app.json`; la línea `v{version}` del preview se dibuja como texto aparte (en la app la pondrá Tk).

**Entregables por carpeta**
- `preview.mp4`: la animación a velocidad real, 640×360.
- `tira.png`: una sola imagen con 8 cuadros representativos en fila o en cuadrícula 4×2, para comparar de un vistazo. Puedes componerla con el compositor de Blender o con un script de desarrollo con Pillow (**Pillow solo como herramienta de desarrollo; no se agrega a `requirements.txt`**).
- `cuadros/`: los PNG renderizados.
- `storyboard.md`: qué pasa en cada tramo, duración, y una tabla con: número de imágenes que necesitaría la app, **peso total estimado de los assets finales** (suma real de los PNG que irían al exe) y costo esperado (una imagen por tick / casi nulo / bajo).
- `build.py`, `params.json`, `escena.blend`.

**Comparación**
- `fases/intro-propuestas/LEEME.md`: tabla comparativa de las tres (duración, peso, costo, carácter, riesgos), con enlaces a cada `preview.mp4` y `tira.png`, y **tu recomendación razonada** en 3–4 líneas.
- **Mira tus propios resultados**: lee cada `tira.png` (y cuadros sueltos si hace falta) y corrige lo que se vea mal — texto ilegible, haz quemado, encuadre cortado — antes de presentarlo.

**Higiene del repositorio**
- Agrega a `.gitignore`: `fases/intro-propuestas/*/cuadros/` y `fases/intro-propuestas/*/*.blend1`. Los `preview.mp4`, `tira.png`, scripts, `params.json` y `storyboard.md` sí se versionan. Si `escena.blend` pesa más de 5 MB, ignóralo también (se regenera con `build.py`).

### No entra

- **Nada en `lighthouse/`**: ni el reproductor, ni el manifiesto final, ni la casilla de Ayuda (eso es F13).
- Assets finales en `assets/intro/` (F13, solo de la propuesta elegida).
- Audio en la intro. Logotipo o tipografía nuevos para la marca (usa una fuente sobria que venga con Blender o con Windows).
- Más de tres propuestas, o variantes de color por tema (los temas son de F14; por eso la luz es neutra).

## Diseño decidido

- Lienzo **640×360**, ≤ 3 s, fondo negro, luz neutra; el acento de color lo pone la app.
- Todo se genera con script a partir de `params.json` + `app.json`: repetir un render es un comando.
- Tres conceptos **distintos entre sí** a propósito: figurativo (A), gráfico con el lenguaje del producto (B) y reactivo al audio (C).

## Criterios de aceptación

1. Existen las tres carpetas con todos sus entregables, y cada `preview.mp4` se abre y dura lo que dice su storyboard (≤ 3 s).
2. Cada `tira.png` se ve bien al leerla: el nombre es legible, no hay cuadros en negro por error ni artefactos.
3. Borrar `cuadros/` y volver a correr `build.py` + render reproduce el mismo resultado (comprueba al menos uno).
4. El nombre y los colores vienen de `app.json`: cambia el nombre en una copia de `app.json`, renderiza **un** cuadro y comprueba que cambia (luego restáuralo).
5. Ningún PNG lleva la versión pintada.
6. El peso estimado de los assets finales de cada propuesta está medido (no supuesto) y es ≤ 3 MB. Si la A se pasa, propone en su `storyboard.md` cómo bajarlo (menos cuadros, 480×270, 16 colores).
7. `python -m lighthouse --test` sigue pasando (no tocaste la app).
8. `git status` muestra cambios solo en `fases/intro-propuestas/`, `.gitignore` y `fases/README.md`.

## Verificación

```powershell
python -c "import json, lighthouse, lighthouse.scene as s; print(json.dumps({'app': 'LightHouse', 'version': lighthouse.VERSION, 'autor': lighthouse.__author__, 'looks': {k: list(s.LOOKS[k][2]) for k in ('2', '3', '4')}}, ensure_ascii=False))"
```
```powershell
Get-ChildItem fases\intro-propuestas -Recurse -File | Where-Object { $_.FullName -notmatch '\\cuadros\\' } | Select-Object FullName, Length
```
```powershell
Get-ChildItem fases\intro-propuestas -Directory | ForEach-Object { "{0}: {1:N2} MB en cuadros" -f $_.Name, ((Get-ChildItem (Join-Path $_.FullName "cuadros") -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB) }
```
```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva en la app. Blender y Pillow son **herramientas de desarrollo** de esta fase; no entran en `requirements.txt` ni en el exe.
- **Blender**: siempre en segundo plano. No modifiques escenas ajenas ni archivos fuera de `fases/intro-propuestas/`. No descargues modelos, texturas ni fuentes de internet: todo se modela por script.
- **La máquina está en uso** (3 monitores): no abras ventanas a pantalla completa, no uses automatización de escritorio ni navegadores. No hace falta abrir la app.
- **Archivos**: en español, UTF-8. No menciones marcas de asistentes de IA en ningún archivo.
- **Alcance**: solo las propuestas. Si un concepto resulta imposible con las limitaciones de Tk descritas arriba, dilo y propón la variante más cercana que sí se pueda reproducir.

## Al terminar

1. Actualiza `fases/README.md`, sección *Etapa 2: interfaz*: F12 → 🔄 con la nota "propuestas listas en `fases/intro-propuestas/`; falta la elección del usuario". **No la marques ✅.**
2. Responde al usuario con:
   - las tres propuestas: ruta de cada `preview.mp4` y `tira.png`, duración, peso y costo;
   - tu recomendación, en 3–4 líneas;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `docs(intro): tres propuestas de animación de entrada`), sin atribuciones ni coautores, y la lista de archivos.

   **No hagas el commit.**
3. **Detente y pregunta: "¿Cuál eliges: A, B o C? ¿Algún ajuste?"**
4. Cuando el usuario responda, en la misma sesión:
   - aplica los ajustes que pida a esa propuesta (editando `params.json` y volviendo a renderizar);
   - escribe `fases/intro-propuestas/ELEGIDA.md` con la letra elegida, los ajustes pedidos y la fecha;
   - marca F12 → ✅ en `fases/README.md` con la elección en la nota.

   La fase F13 no puede empezar sin ese archivo.
