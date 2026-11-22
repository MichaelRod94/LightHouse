# LightHouse · Diseño de la interfaz (Etapa 2)

> Especificación de diseño del rework de la ventana **Control**. Es la fuente de verdad de las fases F7–F14 (`fases/F7-*.md` … `fases/F14-*.md`). Cada prompt de fase cita secciones de este documento por número (§).
>
> El sistema de tokens (§9) trae el tema por defecto, **"oscuro"**. Los otros tres temas (vaporwave, glass y blue ocean), el selector y las reglas de contraste están en §13 y los implementa F14.

Índice: 1 Principios · 2 Arquitectura de información · 3 Layouts responsive · 4 Componentes · 5 Tooltips · 6 Tutorial · 7 Intro · 8 Config · 9 Tokens y tema por defecto · 10 Accesibilidad · 11 Riesgos · 12 Qué se verifica por script · 13 Temas.

---

## 1. Principios

1. **El show manda.** Ningún elemento de la interfaz puede retrasar la luz: nada de timers nuevos, nada de animaciones que compitan con `App.fast()`. Todo lo "vivo" de Control se pinta en el loop lento existente (`slow()`, ~30 Hz) y solo si cambió (`put()`).
2. **Tres cosas siempre a la vista**, en cualquier tamaño: **qué look está activo**, **si llega señal** (golpe, nivel, BPM) y **cómo apagar todo** (Blackout). Lo demás puede colapsar.
3. **Ocupa lo que le den.** La ventana se adapta sola al tamaño (pantalla completa, media pantalla, franja, mini). Nunca se pierde un control: si no cabe, se pliega o el cuerpo se desplaza.
4. **Se entiende leyendo.** Etiquetas en español llano, sin jerga; cada control explica qué hace y cuándo usarlo al pasar el ratón. Lo fino va en "Avanzado", plegado.
5. **Una sola fuente para la apariencia.** Colores, tipografías, espaciados y radios viven en un módulo de tokens. Cero colores sueltos en el código de la interfaz.
6. **Nada sorprende en vivo.** Los cambios de vista no mueven los looks de sitio relativo (siempre en orden 1–7, Q–U, Z), no roban el teclado y no cambian valores. La rueda del ratón nunca cambia un valor por accidente.
7. **Todo es omisible.** Intro, tutorial y tooltips se pueden saltar y desactivar; ninguno bloquea las teclas de show.

Qué significa "dinámico" aquí: respuesta inmediata y barata. Estados hover/activo por eventos (sin timers), indicadores vivos a 30 Hz con `put()`, y una vista previa en miniatura de lo que sale por la Salida 1. No hay fundidos ni transiciones animadas dentro de Control (Tk no los hace baratos).

---

## 2. Arquitectura de información

### 2.1 Zonas

| Zona | Contenido | Visibilidad |
|---|---|---|
| **A. Barra de looks** | Los 15 looks (tecla + nombre + muestra de color) | Siempre, en todos los modos |
| **B. Franja En vivo** | Punto de golpe, medidor, BPM, look activo, estado, vista previa, avisos (chips), selector de Modo, **Bump**, **Blackout**, selector de Vista | Siempre (condensada en compacto y mini) |
| **C. Pestañas** | Show · Audio · Salidas · Ayuda | Completo, medio y compacto. En mini no existen |
| **D. Tarjetas** | Grupos de controles dentro de cada pestaña. Cada tarjeta tiene parte **básica** y, si aplica, **Avanzado** plegable | Según pestaña y modo |

Cambio respecto a hoy: "Fuente de audio" deja la columna fija y pasa a la pestaña Audio; sus alarmas (SIN SEÑAL, SATURA, errores) suben a la franja En vivo como chips, que es donde se miran durante el show. "Modo" y "Blackout" suben a la franja En vivo. La leyenda de atajos del pie pasa a la pestaña Ayuda.

Control nuevo: **Bump** (botón de mantener, junto a Blackout). Hoy el destello manual solo existe como tecla `F`: quien aprende leyendo los tooltips nunca lo encontraría, y con el ratón no se puede dar. El botón hace lo mismo que la tecla (enciende al presionar, apaga al soltar) y no agrega ninguna llave de config. En mini no se muestra (no cabe; ahí queda la tecla).

### 2.2 Tarjetas: básico y avanzado

`id` es el identificador estable de la tarjeta (lo usan `layout.plan`, la config y el tutorial).

| Pestaña | Tarjeta (`id`) | Básico (siempre visible) | Avanzado (plegado por defecto) |
|---|---|---|---|
| Show | Respuesta (`respuesta`) | Preset de respuesta · Sensibilidad · Limitar destellos | Máx. destellos/s · aviso de fotosensibilidad (visible al desactivar el límite) |
| Show | Luz (`luz`) | Brillo general · Duración del destello · Preset de sincronía · Adelantar / atrasar la luz (+ nota de anticipación) | Luz mínima entre golpes · Curva de brillo · Brillo en modo Manual |
| Show | Color del look 1 (`color`) | Tipo de color · Temperatura · Paleta (+ / −) | — |
| Show | Estrobos Q–Y (`estrobos`) | — (tarjeta entera plegada: solo título y "Avanzado") | Cuándo se apaga el estrobo · Duración mínima |
| Show | Teclado (`teclado`) | Teclas siempre activas (globales) + nota | Navegar con Tab (§10) |
| Audio | Fuente de audio (`fuente`) | Dispositivo · Canal · Reconectar · estado | Dar prioridad a rekordbox |
| Audio | Nivel de entrada (`ganancia`) | Automático / Fijo | Nivel de referencia |
| Audio | Qué escucha (`filtro`) | Preset de filtro | Hasta qué frecuencia |
| Audio | Golpe (`golpe`) | — | Pausa mínima entre golpes · Ignorar sonido por debajo de · Golpes fuertes brillan más |
| Audio | Ritmo (`tempo`) | En cada golpe / Al ritmo · BPM (Detectado / Manual) · Tap | BPM manual · Un destello cada |
| Audio | Calma (`tranquilo`) | Preset de calma | Esperar sin golpes · Suavidad · Brillo en calma · Cuánto respira |
| Salidas | Salidas (`salidas`) | Lista · Agregar · Quitar · Agregar TV remota · Identificar pantallas · Calibrar sincronía · estado de red | — |
| Salidas | Salida seleccionada (`salida_sel`) | Nombre · Monitor / Destino · Pantalla completa · Brillo de esta salida · Contenido · Logo · Seguir los looks | Retraso de esta pantalla · Puerto |
| Ayuda | Atajos (`atajos`) | Tabla de teclas (generada del mapa de teclas real) | — |
| Ayuda | Ayuda (`ayuda`) | Ver tutorial · Mostrar ayudas al pasar el ratón · Animación de entrada · Tema (§13) · versión y rutas de config/log | — |

Reglas:
- La **Sensibilidad** es un solo control (una variable): vive en Respuesta porque se toca en vivo (`+` / `−`).
- El estado abierto/cerrado de cada "Avanzado" se guarda (§8). Una tarjeta sin parte básica muestra solo su título y el botón "Avanzado ▸".
- Si un valor avanzado no está en su default, el botón "Avanzado" muestra un punto (`•`) para avisar que hay algo cambiado ahí dentro.
- **No se elimina ningún control ni se cambia ninguna llave de `config.json` existente.** Solo cambian etiquetas (texto visible) y ubicación. Los valores de las listas que se guardan en la config (`Kick (120 Hz)`, `Muy reactivo`, `excepto en 1`, `Luz + logo`…) **no se renombran**.

### 2.3 Etiquetas: jerga → llano

| Hoy | Propuesta |
|---|---|
| Lecturas | En vivo |
| Decay (ms) | Duración del destello (ms) |
| Master (%) (panel Luz) | Brillo general (%) |
| Piso pulso (%) | Luz mínima entre golpes (%) |
| Curva (gamma) | Curva de brillo |
| Manual (%) | Brillo en modo Manual (%) |
| Offset (ms) | Adelantar / atrasar la luz (ms) |
| Ganancia · Automática (AGC) · Fija (la perilla manda) | Nivel de entrada · Automático · Fijo (manda la perilla del mezclador) |
| Referencia (dBFS) | Nivel de referencia (dB) |
| Filtro (qué escucha el detector de golpe) · Corte (Hz) | Qué escucha · Hasta qué frecuencia (Hz) |
| Refractario (ms) | Pausa mínima entre golpes (ms) |
| Compuerta (dB) | Ignorar sonido por debajo de (dB) |
| Intensidad por golpe | Golpes fuertes brillan más |
| Tempo (panel) · Cada kick · Al tempo (sigue sin kick) | Ritmo · En cada golpe · Al ritmo (sigue aunque no haya golpe) |
| Flash cada | Un destello cada |
| Tap [0] | Marcar el ritmo [0] |
| Cierre del golpe · Mínimo (ms) | Cuándo se apaga el estrobo · Duración mínima (ms) |
| Tranquilo (panel) · Entrar tras (s) · Suavizado (s) · Nivel base (%) · Profundidad (%) | Calma · Esperar sin golpes (s) · Suavidad del cambio (s) · Brillo en calma (%) · Cuánto respira (%) |
| Color (opcional) | Color del look 1 |
| Master (%) (salida) · Retardo extra (ms) | Brillo de esta salida (%) · Retraso de esta pantalla (ms) |
| Unirse a looks | Seguir los looks |
| Identificar · Calibrar retardo | Identificar pantallas · Calibrar sincronía |
| Prioridad baja (laptop DJ) | Dar prioridad a rekordbox |
| Teclas globales | Teclas siempre activas (globales) |

Se conservan, con tooltip: Blackout, Bump, BPM, Look, Estrobo, y los nombres de modo Auto / Pulso / Tranquilo / Manual (aparecen así en `LEEME.txt`). La fase que renombra actualiza `LEEME.txt`.

---

## 3. Layouts responsive

### 3.1 Unidades

Todo umbral está en **px lógicos**: `px físicos / escala`, con `escala = root.winfo_fpixels("1i") / 96` (1.0 al 100 %, 1.5 al 150 %). El tamaño que cuenta es el del área cliente de Control (`winfo_width` / `winfo_height`).

### 3.2 Modos y breakpoints

| Modo | Condición (px lógicos) | Densidad | Para qué |
|---|---|---|---|
| **Mini** | Forzado por el usuario, **o** alto < 300, **o** ancho < 560 | densa | Junto a rekordbox: looks + señal + Blackout |
| **Compacto** | (no mini) alto < 600 **o** ancho < 760, o forzado "Compacta" | densa | Franja 1920×540, laptop al 125–150 %, ventana chica |
| **Medio** | ancho < 1200 | cómoda | Media pantalla (960×1080), ventana normal |
| **Completo** | ancho ≥ 1200 y alto ≥ 600 | cómoda | 1366×768 y 1920×1080 maximizada |

Parámetros derivados (no son modos):
- **Columnas de tarjetas**: `cols = clamp(ancho // 400, 1, 4)`. Mini: 0.
- **Filas de looks**: 1 si el ancho ≥ 900 (cómoda) o ≥ 760 (densa); si no, 2 filas (8 + 7: `1–7 Q` arriba, `W E R T Y U Z` abajo).
- **Filas de la franja En vivo**: 3 en cómoda. En densa (compacto), 1 si el ancho ≥ 1100; si no, 2 (arriba: punto, BPM, medidor, look activo, vista previa y **Blackout**; abajo: estado, chips, Modo, Bump y Vista). Una sola fila no cabe en una ventana de 560–1100 px. Blackout va siempre en la primera fila, pegado a la derecha.
- **Histéresis**: 24 px a favor del modo actual, para que no parpadee al arrastrar el borde.

Casos de referencia (los prueba el self-check):

| Caso | Área cliente lógica aprox. | Resultado |
|---|---|---|
| 1920×1080 al 100 %, maximizada | 1920×1010 | completo, 4 columnas, 1 fila de looks |
| 1366×768 al 100 %, maximizada | 1366×700 | completo, 3 columnas |
| 1920×1080 al 150 %, maximizada | 1280×670 | completo, 3 columnas |
| 1366×768 al 125 %, maximizada | 1093×560 | compacto, 2 columnas |
| Media pantalla vertical 960×1080 | 946×1010 | medio, 2 columnas, 1 fila de looks |
| Media pantalla horizontal 1920×540 | 1906×500 | compacto, 4 columnas |
| Ventana chica | 700×420 | compacto, 1 columna, 2 filas de looks |
| Mini tira | 820×90 | mini, 1 fila de looks |
| Mini bloque | 400×150 | mini, 2 filas de looks |

Funciones puras (módulo `lighthouse/layout.py`, sin Tk):

```python
class Layout(NamedTuple):
    mode: str        # "completo" | "medio" | "compacto" | "mini"
    cols: int        # columnas de tarjetas (0 en mini)
    look_rows: int   # 1 o 2
    dense: bool

def pick(w, h, forced="auto", prev=None) -> Layout      # w, h en px lógicos; forced: "auto" | "compacto" | "mini"
def plan(layout, tab) -> list[tuple[str, int, int]]      # (id de tarjeta, columna, fila) de la pestaña visible
```

`plan` reparte las tarjetas de la pestaña en `cols` columnas en orden de lectura, equilibrando alturas con un peso por tarjeta (tabla de pesos en el propio módulo). Es determinista y testeable.

### 3.3 Cómo se cambia

- **Automático**: al cambiar el tamaño de la ventana (`<Configure>` de la raíz) se agenda **un solo** `after(120)` cancelable (el mismo patrón que `Output.later`); al dispararse se llama `pick` y, solo si el `Layout` cambió, se recolocan las tarjetas con `grid` / `grid_forget`. Los widgets se crean una vez; nunca se destruyen ni se recrean al cambiar de modo.
- **Manual**: selector **Vista** en la franja En vivo: `Automática` (por tamaño) · `Compacta` · `Mini`. Tecla **F9**: alterna Mini ↔ vista anterior (acción `mini` del mapa de teclas, editable como las demás).
- Al entrar a Mini a mano, la ventana toma la geometría mini guardada y, si "Siempre encima" está activo, se fija encima. Al salir, vuelve a la geometría normal y deja de estar encima.
- Si el usuario encoge la ventana a mano por debajo de los umbrales, entra a Mini sola, sin tocar "siempre encima".
- **Ampliar y F9 siempre sacan de Mini**, también cuando se entró sola por tamaño: en ese caso la ventana vuelve a la última geometría normal guardada (o al tamaño por defecto). Si solo se cambiara la vista, la ventana seguiría siendo chica y el botón parecería no hacer nada.

### 3.4 Qué se guarda (§8)

Vista elegida, pestaña activa, "Avanzado" abiertos, geometría normal **con tamaño**, geometría mini, "siempre encima" del mini. Hoy solo se restaura la posición de Control; con el layout responsive se restaura también el tamaño (validado contra los monitores con `outputs.geo_ok`).

### 3.5 Wireframes

**Completo** (≥ 1200 × 600; ejemplo 1366×700, 3 columnas):

```
┌ LightHouse · Control ──────────────────────────────────────────────────────────────── ─ □ ✕ ┐
│ ████ ████ ████ ████ ████ ████ ▓▒░█ █▓█▓ █▓█▓ ░░██ ░░██ ░░██ ░░██ ▁▃▅█ ░░░░   ← muestras     │
│ [ 1 ][ 2 ][ 3 ][ 4 ][ 5 ][ 6 ][ 7 ][ Q ][ W ][ E ][ R ][ T ][ Y ][ U ][ Z ]   ← tecla        │
│ Blanco Rojo Azul Morado Verde Amar. Arco B/Rojo B/Mor ½roja ½mor ½ver ½azul Resp. Negro       │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ ●  128 BPM  ▓▓▓▓▓▓▓░░░│░░░   Look 2 · Rojo   AUTO · PULSO   ▌▐ vista previa                  │
│ [Teclas: activas] [SIN SEÑAL] [SATURA] [TV: enviando]                                        │
│ Modo [Auto][Pulso][Tranquilo][Manual]         Vista [Automática ▾]  [ Bump ] [  BLACKOUT  ]  │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Show ] [ Audio ] [ Salidas ] [ Ayuda ]                                                     │
│ ┌ Respuesta ────────────┐ ┌ Luz ──────────────────┐ ┌ Color del look 1 ─────┐               │
│ │ [Normal            ▾] │ │ Brillo general   ──●─ │ │ [Blanco            ▾] │               │
│ │ Sensibilidad    ──●── │ │ Duración destello ●── │ │ Temperatura      ──●─ │               │
│ │ ☑ Limitar destellos   │ │ [Salida por cable  ▾] │ │ Paleta ████ [+] [−]   │               │
│ │ Avanzado ▸            │ │ Adelantar/atrasar ─●─ │ └───────────────────────┘               │
│ └───────────────────────┘ │ Avanzado ▸            │ ┌ Estrobos Q–Y ─────────┐               │
│ ┌ Teclado ──────────────┐ └───────────────────────┘ │ Avanzado ▸            │               │
│ │ ☐ Teclas siempre act. │                           └───────────────────────┘               │
│ └───────────────────────┘                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Medio** (ancho 760–1199; ejemplo media pantalla 960×1080, 2 columnas):

```
┌ LightHouse · Control ─────────────────────────── ─ □ ✕ ┐
│ ██ ██ ██ ██ ██ ██ ▓▒ █▓ █▓ ░█ ░█ ░█ ░█ ▁█ ░░          │
│ [1][2][3][4][5][6][7][Q][W][E][R][T][Y][U][Z]         │
├───────────────────────────────────────────────────────┤
│ ● 128 BPM ▓▓▓▓▓░░│░░  Look 2 · Rojo  AUTO·PULSO  ▌▐   │
│ [Teclas: activas] [SIN SEÑAL]                         │
│ [Auto][Pulso][Tranq.][Man.] Vista[▾] [Bump] [BLACKOUT]│
├───────────────────────────────────────────────────────┤
│ [ Show ] [ Audio ] [ Salidas ] [ Ayuda ]              │
│ ┌ Respuesta ───────────┐ ┌ Luz ─────────────────────┐ │
│ │ …                    │ │ …                        │ │
│ └──────────────────────┘ └──────────────────────────┘ │
│ ┌ Teclado ─────────────┐ ┌ Color del look 1 ────────┐ │
│ │ …                    │ │ …                        │ │
│ └──────────────────────┘ └──────────────────────────┘ │
│ ┌ Estrobos Q–Y ────────┐          (sobra alto: nada   │
│ │ Avanzado ▸           │           se estira)         │
│ └──────────────────────┘                              │
└───────────────────────────────────────────────────────┘
```

Con ancho < 900 la barra de looks pasa a 2 filas (8 + 7) y los botones conservan su ancho mínimo.

**Compacto** (alto < 600 o ancho < 760; ejemplo franja 1920×540, 4 columnas). La franja En vivo se condensa en **una** fila (dos si el ancho < 1100, §3.2), los botones de look son de una línea (`2 Rojo`) con la muestra como banda superior fina, y las tarjetas solo enseñan lo básico:

```
┌ LightHouse · Control ──────────────────────────────────────────────────────────────── ─ □ ✕ ┐
│ [1 Blanco][2 Rojo][3 Azul][4 Morado][5 Verde][6 Amar.][7 Arco][Q][W][E][R][T][Y][U][Z]       │
│ ● 128 ▓▓▓░│░ Look 2·Rojo AUTO·PULSO ▌▐ [Teclas: activas] [Auto▾] Vista[▾] [Bump] [ BLACKOUT ]│
│ [ Show ] [ Audio ] [ Salidas ] [ Ayuda ]                                                     │
│ ┌ Respuesta ───────┐ ┌ Luz ─────────────┐ ┌ Color look 1 ────┐ ┌ Teclado ─────────┐          │
│ │ [Normal       ▾] │ │ Brillo      ──●─ │ │ [Blanco       ▾] │ │ ☐ Teclas siempre │          │
│ │ Sensibilidad ─●─ │ │ Duración    ●─── │ │ Temperatura ──●─ │ └──────────────────┘          │
│ │ ☑ Limitar dest.  │ │ [Por cable    ▾] │ │ Paleta ███ [+][−]│ ┌ Estrobos Q–Y ────┐          │
│ │ Avanzado ▸       │ │ Adel./atrasar ●─ │ └──────────────────┘ │ Avanzado ▸       │          │
│ └──────────────────┘ │ Avanzado ▸       │                      └──────────────────┘          │
│                      └──────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

En compacto el selector de Modo es una lista desplegable (ahorra ancho) y el cuerpo de tarjetas se desplaza en vertical si algún "Avanzado" abierto no cabe.

**Mini — tira** (ancho ≥ 760; ~820×90). Sin pestañas ni tarjetas. Los 15 looks densos (15 × 44 = 660 px) y Blackout (96 px) llenan solos una fila de 800 px: la señal va en la línea de estado.

```
┌ LightHouse ─────────────────────────────────────────────────────────────── ─ □ ✕ ┐
│ [1][2][3][4][5][6][7][Q][W][E][R][T][Y][U][Z]                     [  BLACKOUT  ] │
│ ● 128 ▓▓░│  Look 2 · Rojo · AUTO·PULSO · Teclas: en otra ventana      ▌▐  [▣][⤢] │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Mini — bloque** (ancho < 760; ~400×150). Blackout va arriba: junto a la segunda fila de looks (7 × 44 + 96 px) no cabe en 400 px.

```
┌ LightHouse ───────────────────────── ─ □ ✕ ┐
│ ● 128 ▓▓░│ ▌▐          [ BLACKOUT ] [▣][⤢] │
│ [1][2][3][4][5][6][7][Q]                   │
│ [W][E][R][T][Y][U][Z]                      │
│ Look 2 · Rojo · Teclas: en otra ventana    │
└────────────────────────────────────────────┘
```

`[▣]` = Siempre encima (interruptor). `[⤢]` = Ampliar (sale de Mini, §3.3). El look activo se distingue por el fondo de acento y por el texto "Look 2 · Rojo". El mini **conserva la barra de título** de Windows (se arrastra, se cierra y se trae al frente como cualquier ventana; una ventana sin bordes complica el foco del teclado).

Reglas del mini (el DJ lo mira de reojo, con rekordbox al frente):
- **La línea de estado es zona segura**: un clic en ella trae LightHouse al frente (las teclas pasan a "activas") y **no cambia nada**. Es la forma de recuperar el teclado sin tocar un look por accidente.
- **Prioridad de la línea de estado**: SIN SEÑAL / SATURA sustituyen al estado del modo; el look activo y "Teclas: …" no se quitan nunca. En bloque, el estado del modo (`AUTO·PULSO`) solo se muestra si cabe.
- "Teclas: en otra ventana" es lo normal en mini y va en `fg_muted`; "Teclas: siempre activas" y "en pausa" van en `warn`.
- Si la ventana es más chica que el contenido, lo último que se recorta es la línea de estado: los looks y Blackout quedan siempre enteros.

Tamaños objetivo de **contenido** (px lógicos, `winfo_reqwidth` × `winfo_reqheight`, con todos los "Avanzado" plegados):

| Modo | Tamaño pedido máximo |
|---|---|
| Completo, 3 columnas, pestaña más alta | ≤ 1280 × 660 |
| Medio, 2 columnas | ≤ 900 de ancho |
| Compacto, 4 columnas | ≤ 1880 × 480 |
| Compacto, 1 columna | ≤ 420 de ancho |
| Mini tira | ≤ 800 × 80 |
| Mini bloque | ≤ 400 × 140 |

Mínimo de ventana: `minsize` de 360 × 72 lógicos (con 120 de alto, la tira de 80 no se podría dejar en su tamaño).

### 3.6 Laptop de visuales (`--pantalla`)

Sin cambios de diseño: no tiene panel. Dos reglas: **nunca** muestra intro ni tutorial, y **no usa los tokens ni los temas** (§13.1): lo que sale por la TV es del show.

---

## 4. Componentes

Todos se crean con funciones de fábrica de un solo módulo (`lighthouse/widgets.py` o métodos de `App`), que reciben un **`id`** obligatorio (§5.3) y aplican tokens. Base ttk: tema **`clam`** (es el único tema ttk de Windows que respeta colores en todos sus elementos; `vista` ignora los fondos).

| Componente | Base Tk | Normal | Hover | Activo / seleccionado | Deshabilitado | Foco (solo con "Navegar con Tab") |
|---|---|---|---|---|---|---|
| **Botón de look** | `tk.Radiobutton` sin indicador + `Canvas` de muestra | `surface_alt`, texto `fg` | fondo `hover` | fondo `accent`, texto `accent_fg`, negrita | — | borde `focus` 2 px |
| **Blackout** | `tk.Checkbutton` sin indicador | borde `danger`, texto `danger_text` | fondo `hover` | fondo `danger`, texto `danger_fg`, texto "BLACKOUT ●" | — | borde `focus` |
| **Bump** | `tk.Button` de mantener (`<ButtonPress-1>` enciende, `<ButtonRelease-1>` apaga) | `surface_alt`, texto `fg` | fondo `hover` | fondo `accent`, texto `accent_fg` mientras se mantiene (con el ratón **o** con la tecla `F`) | — | borde `focus` |
| **Segmento** (Modo, pestañas) | `ttk.Radiobutton` estilo `Toolbutton` | `surface`, `fg_muted` | `hover` | `surface_alt` + subrayado `accent`, `fg` | `fg_disabled` | `focus` |
| **Botón** | `ttk.Button` | `surface_alt` | `hover` | `border_strong` al presionar | `fg_disabled` | `focus` |
| **Deslizador** | `tk.Scale` (se conserva: muestra el valor) | canal `trough`, perilla `fg_muted` | perilla `fg` | perilla `accent` al arrastrar | texto `fg_disabled` | `focus` |
| **Lista desplegable** | `ttk.Combobox` solo lectura | `surface_alt` | `hover` | lista: selección `accent` / `accent_fg` | `fg_disabled` | `focus` |
| **Casilla / opción** | `ttk.Checkbutton` / `ttk.Radiobutton` | marca `fg_muted` | `hover` | marca `accent` | `fg_disabled` | `focus` |
| **Campo de texto** | `ttk.Entry` | `surface_alt`, borde `border_strong` | — | borde `accent` al escribir | `fg_disabled` | (siempre toma foco) |
| **Tarjeta** | `tk.Frame` con título | fondo `surface`, borde `border` | — | — | — | — |
| **Avanzado ▸ / ▾** | `ttk.Button` estilo enlace | `fg_muted` | `fg` | `▾` abierto; `•` si hay valores no default | — | `focus` |
| **Chip de aviso** | `tk.Label` | oculto si no aplica | — | Texto de color sobre fondo `surface_alt`: `danger_text` (SIN SEÑAL), `warn` (SATURA, avisos), `ok` (red), `fg_muted` (info). El relleno `danger` queda solo para Blackout activo | — | — |

Los widgets `tk.*` clásicos no se enteran de `ttk.Style`: reciben sus colores con `theme.paint(widget, opción="token", …)`, que además **recuerda** el enlace opción → token. Así `theme.apply` puede volver a pintar toda la ventana al cambiar de tema, sin reiniciar (§9.1, §13.5).

Feedback en vivo (todo en `slow()` con `put()`; **cero timers nuevos**):

| Elemento | Qué muestra | Costo esperado |
|---|---|---|
| Punto de golpe | `beat_on` 100 ms tras cada golpe; si no `beat_off` | 1 `itemconfig` por cambio |
| Medidor | Nivel de banda, subida y línea de umbral (Canvas chico, 3 ítems) | 3 `coords` por tick como mucho |
| BPM, estado, look activo | Texto (BPM y look activo en `live_fg`) | solo si cambia |
| Vista previa `▌▐` | Dos `Frame` de ~28×20 con el último `Frame` compuesto para la Salida 1 (lo deja `fast()` en un atributo; lo pinta `slow()`) | ≤ 2 `configure(bg)` por tick |
| Chip "Teclas" | `activas` (ok) · `en otra ventana` (muted) · `siempre activas` (warn, globales) · `en pausa` (warn, escribiendo o navegando) | solo si cambia |
| Chips SIN SEÑAL / SATURA / red / avisos de salida | Como hoy, pero en la franja | solo si cambian |

Hover y presionado van por eventos `<Enter>` / `<Leave>` (tk) o `style.map` (ttk). No hay animaciones.

Seguridad en vivo:
- **Rueda del ratón**: se quita el binding de clase `<MouseWheel>` de `TCombobox` (hoy la rueda cambia el dispositivo de audio si el puntero está encima). La rueda solo desplaza el cuerpo de tarjetas.
- **Ctrl / Alt**: con Ctrl o Alt presionados las teclas de show no disparan (hoy `Alt+F4` cambia a modo Manual antes de cerrar, y un atajo `Ctrl+1` dispararía el look 1).

---

## 5. Tooltips

### 5.1 Sistema

- **Módulo** `lighthouse/tips.py`: catálogo `TIPS` (`id → texto`) + clase `Tooltip` (una sola ventana compartida).
- **Retardo**: 500 ms con el puntero quieto sobre el control. Si se mostró otro tooltip hace menos de 1 s, 100 ms. Un solo `after` cancelable por vez (no es un timer periódico).
- **Se oculta** al salir del control, al hacer clic, al presionar cualquier tecla, al cambiar de modo de layout o de pestaña, cuando Control pierde el foco (`<FocusOut>` de la raíz, por ejemplo con Alt+Tab) y al empezar la intro o un paso del tutorial.
- **Se muestra aunque LightHouse no esté al frente**: basta con pasar el ratón. En mini, con rekordbox al frente, es la única forma de leer la ayuda sin quitarle el teclado a rekordbox.
- **Controles deshabilitados**: también tienen tooltip; su texto dice cuándo se activan ("Solo con …").
- **Con "Navegar con Tab"** (§10): el tooltip del control enfocado aparece al recibir el foco, debajo del control, y se oculta con `Esc` o al mover el foco. Sin esto, quien no usa ratón no tendría ayuda.
- **Ventana**: `Toplevel` sin bordes (`overrideredirect`), siempre encima, que **no toma el foco** (no interfiere con "LightHouse al frente" ni con `typing`). Fondo `tooltip_bg`, texto `tooltip_fg`, borde 1 px `tooltip_border`, relleno `space.md`.
- **Posición**: 14 px a la derecha y 20 px debajo del puntero (nunca debajo del puntero mismo). Si se sale del monitor donde está el puntero (rectángulo real de `win32.monitors()`, no el primario de Tk), se voltea a la izquierda y/o arriba; como último recurso se recorta al borde con 8 px de margen.
- **Ancho máximo**: 320 px lógicos (`wraplength`). Texto de 1–2 frases, ≤ 200 caracteres.
- **Contenido**: primera línea opcional en negrita con la etiqueta y su tecla (`Blackout · Espacio`); luego el texto.
- **Desactivar**: Ayuda → "Mostrar ayudas al pasar el ratón" (activo por defecto).
- **Mini**: mismos tooltips; como la ventana es chica, siempre se colocan fuera de ella si hay sitio (debajo o arriba de la ventana).
- **Costo**: nada mientras no hay hover. No hay sondeo.

### 5.2 Reglas de redacción

Español llano, tuteo, 1–2 frases: **qué hace** + **cuándo usarlo o qué pasa si lo mueves**. Sin siglas sin explicar. Si hay tecla, se nombra. Los avisos de seguridad (rekordbox, fotosensibilidad) van dentro del tooltip además de su nota visible.

### 5.3 Registro e identificadores

Todo control interactivo se registra al crearse: `app.ids[widget] = "grupo.nombre"`. El self-check recorre el árbol de widgets de Control y **falla** si un widget interactivo (`Button`, `TButton`, `Checkbutton`, `TCheckbutton`, `Radiobutton`, `TRadiobutton`, `Scale`, `TCombobox`, `TEntry`, `Entry`, `Listbox`, o cualquier widget con binding de clic propio) no tiene `id`, si su `id` no está en `TIPS`, o si el texto está vacío o pasa de 200 caracteres. Los mismos `id` sirven de **objetivo del tutorial** (§6).

### 5.4 Catálogo

**Barra de looks**

| id | Texto |
|---|---|
| `look.1` | Luz blanca que sigue la música (o el color que elijas en "Color del look 1"). Es el look de inicio; en él la TV grande muestra su logo. |
| `look.2` … `look.6` | Todo en {rojo / azul / morado / verde / amarillo}, siguiendo cada golpe. Queda activo hasta que elijas otro look. |
| `look.7` | Arcoíris: cambia de color en cada golpe, en orden. Úsalo para subir la energía. |
| `look.Q` | Estrobo blanco y rojo: alterna en cada golpe y se apaga a negro cuando el golpe deja de sonar. Para los momentos fuertes. |
| `look.W` | Estrobo blanco y morado: alterna en cada golpe y se apaga a negro cuando el golpe deja de sonar. |
| `look.E` `look.R` `look.T` `look.Y` | Pantalla partida: una mitad en {rojo / morado / verde / azul} y la otra en negro. Se intercambian en cada golpe. |
| `look.U` | Morado que sube 4 segundos y baja 4 segundos, sin seguir la música. Para entradas, pausas o charla. |
| `look.Z` | Negro total: no responde a la música. Mantén F para dar un destello a mano. Si solo quieres apagar un momento y volver al mismo look, usa Blackout (Espacio). |

**Franja En vivo**

| id | Etiqueta | Texto |
|---|---|---|
| `vivo.punto` | ● | Se enciende con cada golpe que LightHouse detecta. Si no parpadea con la música, revisa la Fuente de audio o sube la Sensibilidad. |
| `vivo.medidor` | Medidor | Barra de arriba: cuánto grave entra. Barra de abajo: la subida de cada golpe. Línea vertical: lo que debe superar para contar como golpe. |
| `vivo.bpm` | BPM | La velocidad de la música en golpes por minuto (BPM), según la detecta LightHouse. "--" significa que todavía no la sabe. |
| `vivo.look` | Look activo | El look que se está mostrando. Cámbialo con su tecla o con un clic en la barra de arriba. |
| `vivo.estado` | Estado | Lo que hace la luz ahora: sigue los golpes (Pulso), está en calma (Tranquilo), Manual, Blackout o Bump. |
| `vivo.previa` | Vista previa | Lo que está mostrando la Salida 1 en este momento, en pequeño. |
| `vivo.teclas` | Teclas | Dice si tus teclas llegan a LightHouse. "En otra ventana": las recibe otro programa; haz clic aquí para recuperarlas. "En pausa": estás escribiendo; pulsa Enter para terminar. |
| `vivo.sin_senal` | SIN SEÑAL | No llega sonido desde hace más de 3 segundos. Revisa que suene música y que la Fuente de audio sea la correcta. |
| `vivo.satura` | SATURA | El sonido entra demasiado fuerte. Baja el volumen de entrada o la perilla del mezclador. |
| `vivo.red` | TV remota | Estado del envío a la TV remota. "Sin red" significa que la otra laptop no está conectada. |
| `vivo.avisos` | Avisos | Problemas de alguna salida: monitor desconectado o logo que no se pudo abrir. |
| `modo.auto` | F1 Auto | La luz sigue los golpes y, si la música se calma, pasa sola a una respiración suave. Úsalo casi siempre. |
| `modo.pulso` | F2 Pulso | Siempre sigue los golpes, aunque la música esté tranquila. |
| `modo.tranquilo` | F3 Tranquilo | Respiración suave que no marca los golpes. Para ambiente o mientras hablas. |
| `modo.manual` | F4 Manual | Brillo fijo, sin seguir la música. Lo ajustas con "Brillo en modo Manual". |
| `blackout` | Blackout · Espacio | Apaga todas las pantallas al instante. Otro clic (o Espacio) las vuelve a encender en el mismo look. |
| `bump` | Bump · F (mantener) | Mientras lo mantienes presionado, todas las pantallas se encienden a tope con el color del look. Al soltar, todo sigue como estaba. |
| `vista.selector` | Vista | Tamaño de esta ventana. Automática se adapta al espacio; Compacta ahorra sitio; Mini deja solo los looks, la señal y el Blackout. Tecla F9: mini. |
| `vista.fijar` | Siempre encima | Mantiene esta ventana por encima de rekordbox y de todo lo demás. |
| `vista.ampliar` | Ampliar · F9 | Vuelve a la ventana grande con todos los ajustes. |
| `vista.sin_foco` | No quitar el teclado | Al hacer clic aquí, el teclado se queda en el otro programa (por ejemplo rekordbox). Útil si cambias looks con el ratón. |

**Pestañas y tarjetas**

| id | Etiqueta | Texto |
|---|---|---|
| `tab.show` | Show | Lo que se toca durante la fiesta: respuesta, brillo, color y teclas. |
| `tab.audio` | Audio | De dónde escucha LightHouse y cómo detecta los golpes. Se ajusta una vez, antes de empezar. |
| `tab.salidas` | Salidas | Las pantallas que funcionan como luces: en qué monitor va cada una y qué muestra. |
| `tab.ayuda` | Ayuda | Lista de teclas, tutorial y opciones de ayuda. |
| `avanzado.*` | Avanzado | Muestra u oculta los ajustes finos de este grupo. Lo normal es no tocarlos. Un punto indica que alguno fue cambiado. |

**Respuesta**

| id | Etiqueta | Texto |
|---|---|---|
| `resp.preset` | Respuesta | Normal: equilibrado. Muy reactivo: destellos más cortos y seguidos, para música rápida. Mueve varios ajustes a la vez; luego puedes afinar. |
| `golpe.sens` | Sensibilidad · + / − | Qué tan fácil se enciende la luz. Súbela si se pierde golpes; bájala si destella con cualquier sonido. |
| `resp.limite` | Limitar destellos | Impide destellos demasiado seguidos, que pueden provocar crisis a personas con epilepsia fotosensible. Déjalo activo siempre que haya público. |
| `resp.limite_hz` | Máx. destellos/s | Cuántos destellos por segundo se permiten como mucho. 6 deja pasar ritmos rápidos sin llegar a ser peligroso. |

**Luz**

| id | Etiqueta | Texto |
|---|---|---|
| `luz.master` | Brillo general (%) | Brillo máximo de todas las pantallas. Bájalo si deslumbra. |
| `luz.decay` | Duración del destello (ms) | Cuánto tarda en apagarse la luz después de cada golpe. Corto = golpes secos; largo = luz más suave. |
| `luz.sinc_preset` | Sincronía | Compensa el retraso típico de tu salida de sonido para que luz y sonido coincidan. Elige cómo está conectado el sonido. |
| `luz.offset` | Adelantar / atrasar la luz (ms) | Positivo: la luz llega más tarde. Negativo: se adelanta (solo funciona "Al ritmo" y con un ritmo estable). Ajústalo hasta que luz y golpe coincidan. |
| `luz.piso` | Luz mínima entre golpes (%) | Brillo que queda entre un golpe y otro. En 0 la pantalla queda negra entre golpes. |
| `luz.gamma` | Curva de brillo | Cómo se reparte el brillo: valores altos dejan los golpes suaves más oscuros y dan más contraste. |
| `luz.manual` | Brillo en modo Manual (%) | El brillo fijo que se usa cuando el modo es Manual (F4). |

**Color del look 1**

| id | Etiqueta | Texto |
|---|---|---|
| `color.modo` | Tipo de color | Color del look 1: blanco puro, un blanco cálido o frío, o una paleta que cambia en cada destello. |
| `color.kelvin` | Temperatura (K) | Tono del blanco: valores bajos son cálidos (ámbar), valores altos son fríos (azulados). Solo con "Temperatura". |
| `color.paleta` | Paleta | Los colores que se van turnando, uno por destello. Solo con "Paleta". |
| `color.mas` | + | Agrega un color a la paleta. |
| `color.menos` | − | Quita el último color de la paleta. |

**Estrobos Q–Y**

| id | Etiqueta | Texto |
|---|---|---|
| `estrobo.cierre` | Cuándo se apaga el estrobo | Valores altos apagan el color en cuanto el golpe empieza a bajar (más seco); valores bajos lo dejan encendido más tiempo. |
| `estrobo.min` | Duración mínima (ms) | Lo mínimo que dura encendido cada destello de estrobo, para que se alcance a ver. |

**Teclado**

| id | Etiqueta | Texto |
|---|---|---|
| `teclas.globales` | Teclas siempre activas (globales) | Las teclas funcionan aunque otro programa esté al frente. Cuidado: esas mismas teclas también le llegan a rekordbox. |
| `teclas.tab` | Navegar con Tab | Permite moverte por los controles con Tab y las flechas. Mientras un control tiene el foco, las teclas de looks quedan en pausa; Esc las devuelve. |

**Fuente de audio**

| id | Etiqueta | Texto |
|---|---|---|
| `audio.dispositivo` | Dispositivo | De dónde escucha LightHouse. Con rekordbox en esta laptop elige "Salida (loopback) · …" con el mismo dispositivo que usa rekordbox. |
| `audio.canal` | Canal | Qué canal de la entrada se escucha. "Mezcla" usa todos; elige un canal si conectaste un solo cable. |
| `audio.reconectar` | Reconectar | Vuelve a buscar y abrir el dispositivo de audio. Úsalo si conectaste algo nuevo o el medidor dejó de moverse. |
| `audio.estado` | Estado | Datos del dispositivo abierto o el último error de audio. |
| `audio.prioridad` | Dar prioridad a rekordbox | LightHouse cede el procesador a los demás programas para que el sonido nunca se corte. Déjalo activo en la laptop del DJ. |

**Nivel de entrada**

| id | Etiqueta | Texto |
|---|---|---|
| `nivel.auto` | Automático | LightHouse ajusta solo el volumen de entrada. Es lo normal cuando escucha lo que suena en esta laptop. |
| `nivel.fijo` | Fijo (manda la perilla del mezclador) | El nivel no se corrige: la perilla de tu mezclador decide cuánta luz hay. Para entradas por cable. |
| `nivel.ref` | Nivel de referencia (dB) | Con nivel Fijo: el volumen de entrada que cuenta como "a tope". Bájalo si la luz se queda corta. |

**Qué escucha**

| id | Etiqueta | Texto |
|---|---|---|
| `filtro.preset` | Qué escucha | Qué parte del sonido cuenta como golpe. "Kick" sigue el bombo; "Completo" escucha todo, incluidas voces y aplausos. |
| `filtro.corte` | Hasta qué frecuencia (Hz) | Límite de graves que se escuchan. Bajo = solo el bombo más profundo; alto = también bajos y toms. |

**Golpe**

| id | Etiqueta | Texto |
|---|---|---|
| `golpe.pausa` | Pausa mínima entre golpes (ms) | Tiempo mínimo entre dos golpes seguidos. Súbelo si un solo golpe enciende la luz dos veces. |
| `golpe.compuerta` | Ignorar sonido por debajo de (dB) | El sonido más bajo que este nivel se trata como silencio. Súbelo si la luz reacciona al ruido de fondo. |
| `golpe.fuerza` | Golpes fuertes brillan más | Activo: un golpe suave da menos luz que uno fuerte. Apagado: todos los golpes encienden igual. |

**Ritmo**

| id | Etiqueta | Texto |
|---|---|---|
| `tempo.kick` | En cada golpe | La luz destella solo cuando suena un golpe. Si la música se queda sin bombo, la luz se detiene. |
| `tempo.ritmo` | Al ritmo (sigue aunque no haya golpe) | La luz sigue marcando el ritmo aunque el bombo desaparezca un momento. |
| `tempo.fuente` | BPM | De dónde sale la velocidad de la música. "Detectado": la calcula LightHouse. "Manual / Tap": la marcas tú. |
| `tempo.tap` | Marcar el ritmo · 0 | Toca al ritmo de la música 3 o más veces para fijar la velocidad a mano. |
| `tempo.bpm_manual` | BPM manual | La velocidad, en golpes por minuto, que se usa cuando eliges "Manual / Tap". |
| `tempo.divisor` | Un destello cada | 1/1: un destello por golpe. 1/2: uno cada dos golpes. 1/4: uno cada cuatro. |

**Calma**

| id | Etiqueta | Texto |
|---|---|---|
| `calma.preset` | Calma | Cómo se ve la luz cuando la música está tranquila: respiración suave, tenue fija o casi apagada. |
| `calma.espera` | Esperar sin golpes (s) | Segundos sin golpes antes de pasar a calma (en modo Auto). |
| `calma.suavidad` | Suavidad del cambio (s) | Qué tan lento sube y baja la luz en calma. |
| `calma.base` | Brillo en calma (%) | Brillo de fondo mientras la música está tranquila. |
| `calma.respira` | Cuánto respira (%) | Cuánto sube la luz con el volumen de la música en calma. En 0 queda fija. |

**Salidas**

| id | Etiqueta | Texto |
|---|---|---|
| `salidas.lista` | Lista de salidas | Cada salida es una pantalla que funciona como luz. Haz clic en una para ver y cambiar sus ajustes. |
| `salidas.agregar` | Agregar | Crea otra salida en esta laptop (hasta 4). Aparece como ventana para que la arrastres a su monitor. |
| `salidas.quitar` | Quitar | Elimina la salida seleccionada. Siempre queda al menos una. |
| `salidas.tv` | Agregar TV remota | Crea una salida que se envía por red a otra laptop con LightHouse en modo pantalla. Ya viene lista para la TV grande con logo. |
| `salidas.identificar` | Identificar pantallas | Durante 3 segundos cada salida muestra su número y su monitor, para saber cuál es cuál. |
| `salidas.calibrar` | Calibrar sincronía | Abre una guía para alinear la luz con el sonido usando la cámara lenta del celular. |
| `sal.nombre` | Nombre | El nombre de esta salida en la lista. Mientras escribes, las teclas de looks quedan en pausa; Enter termina. |
| `sal.monitor` | Monitor | En qué monitor se muestra esta salida cuando está en pantalla completa. |
| `sal.completa` | Pantalla completa / Ventana | Cambia entre cubrir todo el monitor, sin bordes, y una ventana normal para acomodarla. También con doble clic sobre la salida; Esc vuelve a ventana. |
| `sal.destino` | Destino | "Automático" encuentra sola a la otra laptop. Escribe una dirección IP solo si quieres enviar a una en concreto. |
| `sal.puerto` | Puerto | Número de puerto de red. Debe ser el mismo en las dos laptops; lo normal es no tocarlo. |
| `sal.master` | Brillo de esta salida (%) | Brillo solo de esta pantalla. Úsalo para que una TV grande brille menos que las demás. |
| `sal.retardo` | Retraso de esta pantalla (ms) | Retrasa solo esta salida. Sirve para igualar pantallas que responden más rápido que otras. |
| `sal.contenido` | Contenido | "Luz": solo color. "Luz + logo": además muestra tu logo cuando esta salida no está siguiendo un look. |
| `sal.logo` | Logo (PNG) | Ruta de la imagen del logo. Mejor un PNG ya del tamaño de la pantalla. |
| `sal.logo_buscar` | … | Abre una ventana para elegir el archivo del logo. |
| `sal.unirse` | Seguir los looks | Cuándo esta salida muestra el look activo: siempre, en todos menos el look 1 (ahí enseña su logo), o nunca. |
| `calib.salir` | Salir | Cierra la guía y devuelve el look y los ajustes que tenías antes de calibrar. |

**Ayuda**

| id | Etiqueta | Texto |
|---|---|---|
| `ayuda.tutorial` | Ver tutorial | Recorrido de 2 minutos por lo esencial. Puedes saltarlo en cualquier momento. |
| `ayuda.tips` | Mostrar ayudas al pasar el ratón | Muestra explicaciones como esta al dejar el ratón sobre un control. |
| `ayuda.intro` | Animación de entrada | Muestra la animación corta al abrir LightHouse. La luz y el sonido arrancan igual con o sin ella. |
| `ayuda.carpeta` | Abrir carpeta de registros | Abre la carpeta con el archivo que hay que enviar si algo falla. |
| `ayuda.tema` | Tema | Cambia los colores de esta ventana. No cambia la luz de tus pantallas ni los colores de los looks. |

**Tutorial**

| id | Etiqueta | Texto |
|---|---|---|
| `tut.ver` | Ver tutorial | Empieza el recorrido guiado. La luz sigue funcionando mientras lo ves. |
| `tut.ahora_no` | Ahora no | Cierra esta pregunta. Puedes ver el tutorial cuando quieras desde Ayuda. |
| `tut.no_preguntar` | No volver a preguntar | Marca esto para que la pregunta no aparezca al abrir LightHouse. |
| `tut.atras` | Atrás | Vuelve al paso anterior. |
| `tut.siguiente` | Siguiente | Pasa al paso siguiente aunque no hayas hecho lo que pide. |
| `tut.omitir` | Omitir tutorial · Esc | Cierra el recorrido ahora. Se puede repetir desde Ayuda. |

---

## 6. Tutorial interactivo (omisible)

### 6.1 Primer arranque

Al abrir por primera vez (config `ui.tutorial = "preguntar"`) aparece una **banda no modal** entre la franja En vivo y las pestañas. No es un diálogo: no bloquea nada y la luz ya está funcionando.

```
│ ¿Primera vez con LightHouse?  Recorrido de 2 minutos.   [ Ver tutorial ]  [ Ahora no ]  ☐ No volver a preguntar │
```

- **Ver tutorial** → empieza. Al terminar o al omitirlo a mitad queda `"visto"`: no vuelve a preguntar.
- **Ahora no** → oculta la banda. Si la casilla está marcada queda `"no_preguntar"`; si no, vuelve a preguntar en el próximo arranque.
- La banda no aparece en modo mini, ni mientras corre la intro (aparece al terminar), ni en `--pantalla`.
- Se repite cuando se quiera: **Ayuda → Ver tutorial**.

### 6.2 Mecánica

- **Datos, no código**: los pasos son una lista en `lighthouse/tutorial.py` (`STEPS`): `id` del control objetivo (los de §5.3), pestaña que debe estar abierta, título, texto, y condición opcional de avance (función que mira el estado de la app).
- **Resaltado**: un **anillo** de 4 `Frame` delgados (3 px, color `tutorial_ring`) colocados con `place()` alrededor del control objetivo, por encima de todo. Sin Canvas, sin capa oscura (Tk no tiene velos translúcidos baratos). El anillo se recoloca cuando cambia el layout.
- **Globo**: un `Frame` con `place()` junto al objetivo (debajo si cabe; si no, arriba o al lado; nunca encima del objetivo ni fuera de la ventana). Contiene: `Paso 3 de 9`, título, texto, y los botones `Atrás` · `Siguiente` · `Omitir tutorial`.
- **Interactivo**: cuando el paso pide una acción ("Presiona 2"), avanza solo al cumplirse la condición; `Siguiente` siempre está disponible. Las condiciones se evalúan en `slow()` (30 Hz existentes): **sin timers nuevos**.
- **Nunca se salta un paso sin que se lea**:
  - Si la condición **ya se cumple al mostrar el paso** (el audio ya funcionaba, ya había BPM), el paso **no avanza solo**: el globo muestra `✓ Ya está` y espera a `Siguiente`.
  - Si se cumple después, el globo muestra `✓ Hecho` y avanza unos 700 ms más tarde. Ese tiempo lo mide `tick()` con el reloj; no es un timer.
- **Sin ratón**: `Enter` hace de `Siguiente` y `Esc` omite, siempre que el foco no esté en un campo de texto ni en un control (con "Navegar con Tab", el primer `Esc` devuelve el foco y el segundo omite). El globo recuerda las dos teclas en su pie: `Enter: siguiente · Esc: omitir`.
- **Las teclas de show siguen vivas**: el globo no tiene campos de texto, sus botones no toman el foco y el tutorial nunca activa la pausa de teclas. Presionar una tecla de look durante el tutorial cambia el look de verdad (es lo que se quiere enseñar).
- **Omitir**: botón `Omitir tutorial` o `Esc` (binding de Tk en la raíz; `Esc` no es tecla de show). Deja todo como estaba, salvo lo que el usuario cambió a propósito.
- **Layout**: si la vista es Mini al empezar, se pasa a la vista automática y al terminar se restaura. Si el objetivo no está visible (pestaña equivocada, "Avanzado" cerrado), el tutorial abre la pestaña; si aun así no está, el globo sale centrado y sin anillo.
- Los tooltips se silencian mientras hay un paso activo.

### 6.3 Pasos

| # | Objetivo (`id`) | Pestaña | Título | Texto | Avanza solo cuando |
|---|---|---|---|---|---|
| 1 | — (centrado) | — | Bienvenido | LightHouse escucha tu música y convierte cada golpe en luz en tus pantallas. La luz ya está funcionando: este recorrido no detiene nada. | — |
| 2 | `audio.dispositivo` | Audio | 1. Dile de dónde escuchar | Pon música. Abre esta lista y elige "Salida (loopback) · …" con el mismo dispositivo por el que suena tu música (el que usa rekordbox). | llega señal (no hay SIN SEÑAL y hubo un golpe) |
| 3 | `vivo.medidor` | — | 2. Comprueba la señal | Con música, el punto parpadea en cada golpe y aparece la velocidad (BPM). Si no se mueve, pulsa Atrás y prueba otro dispositivo. | hay BPM detectado |
| 4 | `look.2` | — | 3. Cambia de look | Presiona la tecla 2 (o haz clic). Cada look se queda activo hasta que elijas otro. | look activo = 2 |
| 5 | `look.Q` | — | 4. Estrobos | Presiona Q: un estrobo que se apaga cuando el golpe deja de sonar. Con 1 vuelves al blanco. | look activo = Q |
| 6 | `blackout` | — | 5. Apagar todo | Espacio apaga todas las pantallas; Espacio otra vez las enciende. Al lado, Bump (mantén F) da un destello a mano. | blackout se activó y se desactivó |
| 7 | `resp.preset` | Show | 6. Qué tan reactivo | "Muy reactivo" da destellos más cortos y seguidos. Con + y − ajustas la sensibilidad en vivo. | — |
| 8 | `salidas.lista` | Salidas | 7. Tus pantallas | Cada salida es una pantalla-luz. Arrástrala a su monitor y haz doble clic para pantalla completa. "Identificar pantallas" te dice cuál es cuál. | — |
| 9 | `vista.selector` | — | 8. Junto a rekordbox | "Mini" (F9) deja solo los looks, la señal y el Blackout. Ojo: tus teclas solo llegan a LightHouse si su ventana está al frente; el aviso "Teclas" te lo dice. | — |
| 10 | `tab.ayuda` | Ayuda | Listo | Deja el ratón sobre cualquier control para ver qué hace. Este recorrido se repite desde Ayuda. | — |

---

## 7. Intro (animación de entrada)

### 7.1 Reglas

- Dura **≤ 3 s**. Se muestra **dentro de la ventana Control**, como una capa que la cubre (`place` a toda la ventana), no como una ventana aparte previa.
- **No retrasa nada**: se crea al final de `App.__init__`, cuando el audio ya está abierto y las salidas ya pintan. `App.fast()` sigue corriendo debajo: las salidas reaccionan a la música durante la intro.
- **Reloj**: la intro avanza desde `slow()` (los ~30 Hz que ya existen), eligiendo el cuadro por **tiempo transcurrido** (si un tick se atrasa, salta cuadros). **Ningún `after` nuevo.**
- **Costo**: como mucho una imagen decodificada por tick. Presupuesto: ≤ 4 ms por tick (p95) y ningún pintado de salida retrasado más de 5 ms por la intro; se mide en la fase de implementación. Si no se cumple, se baja resolución o cuadros (es un dato del manifiesto).
- **Se omite** con cualquier tecla, cualquier clic o al cerrar. Una tecla de show presionada durante la intro **además hace su acción** (el `2` salta la intro y pone el look 2).
- **Se desactiva** en Ayuda → "Animación de entrada" (`ui.intro`), o con `--sin-intro`. Nunca corre en `--pantalla`, en `--test`, ni si la app arranca en vista Mini o la ventana es más chica que el lienzo.
- Si falta un archivo o el manifiesto no es válido: no hay intro, se anota en el log y la app arranca normal.

### 7.2 Qué significa "sin hardcode"

1. **El reproductor es genérico**: `lighthouse/intro.py` interpreta un manifiesto `assets/intro/intro.json`. En el código Python no hay coordenadas, tiempos, textos ni colores de ninguna intro concreta.
2. **Los textos salen de la app**: el manifiesto usa variables (`{app}`, `{version}`, `{autor}`, `{dispositivo}`) que se rellenan con `lighthouse.VERSION`, `__author__` y el estado real. La versión nunca está pintada en un PNG.
3. **Los colores salen de los tokens o de los looks**: `"token:intro_fg"`, `"look:2"`. Las imágenes de Blender son **luz neutra** (blancos y grises sobre negro o transparente) para que cualquier tema futuro combine sin volver a renderizar.
4. **Los assets se regeneran con un comando**: la escena de Blender se construye con un script (`intro_src/<concepto>/build.py`) que lee `params.json` (tamaño, cuadros, nombre de la app). Nada se retoca a mano.
5. **Cambiar de intro = cambiar la carpeta** `assets/intro/`, sin tocar código.

Por qué así: es lo único que permite que el usuario elija entre tres propuestas, que el agente de temas ajuste colores, y que una versión nueva no obligue a re-renderizar.

### 7.3 Formato del manifiesto (resumen)

```json
{
  "formato": 1,
  "lienzo": [640, 360],
  "duracion_ms": 2400,
  "fondo": "token:intro_bg",
  "capas": [
    {"id": "escena", "tipo": "secuencia", "archivos": "faro_{:03d}.png", "cuadros": 48, "fps": 20, "pos": [0.5, 0.5]},
    {"id": "golpe", "tipo": "color", "color": "look:2", "rect": [0.5, 0, 1, 1],
     "pistas": {"visible": [[600, true], [680, false]]}},
    {"id": "lente", "tipo": "secuencia", "archivos": "lente_{:02d}.png", "cuadros": 16, "cuadro_por": "nivel"},
    {"id": "nombre", "tipo": "texto", "texto": "{app}", "fuente": "token:font.intro", "color": "token:intro_fg",
     "pistas": {"y": [[0, 0.82], [1800, 0.76, "out_cubic"]], "visible": [[1500, true]]}},
    {"id": "version", "tipo": "texto", "texto": "v{version}", "fuente": "token:font.small", "color": "token:fg_muted",
     "pos": [0.5, 0.9], "pistas": {"visible": [[1900, true]]}}
  ]
}
```

- Tipos de capa: `secuencia` (cuadros PNG, por tiempo o ligados a `"nivel"` = nivel de audio real del motor, 0..1), `imagen` (un PNG que se mueve), `texto` (dibujado por Tk), `color` (rectángulo relleno, para cortes duros).
- Pistas: lista de `[t_ms, valor, easing?]` por propiedad (`x`, `y`, `visible`, `cuadro`). Easings: `lineal`, `in_cubic`, `out_cubic`, `in_out`, `corte`.
- Posiciones relativas al lienzo (0..1). El lienzo se centra en la ventana sobre `fondo`; con escala ≥ 200 % las imágenes se amplían ×2 (`zoom` entero).
- Se dibuja en **un Canvas chico** (el lienzo) dentro de Control. Es el único lugar donde se usa Canvas con imágenes; se mide su costo.

### 7.4 Tres conceptos

**A · "Faro"** — figurativo, 3D, cálido. Duración 2,4 s.

| t (s) | Qué se ve |
|---|---|
| 0,0–0,4 | Negro. Abajo a la izquierda se insinúa la silueta de un faro contra un cielo apenas más claro. |
| 0,4–0,8 | La lámpara se enciende: un punto de luz que crece con halo. |
| 0,8–1,8 | El haz (volumétrico) barre de izquierda a derecha por todo el cuadro. A su paso deja encendido el nombre en 3D, letra por letra. |
| 1,8–2,4 | El haz sale por la derecha; el nombre queda iluminado; aparece debajo `v{version}` (texto de la app). Corte a Control. |

- Producción: Blender, cámara fija, luz volumétrica (spot + volumen), nombre como texto 3D leído de `params.json`. Secuencia completa de ~48 cuadros a 20 fps, 640×360.
- Peso estimado: 2–3 MB. Costo: el más alto de los tres (un PNG completo por tick).
- Carácter: explica el nombre, elegante, "marca".

**B · "Pulso"** — gráfico, el lenguaje del producto. Duración 1,8 s.

| t (s) | Qué se ve |
|---|---|
| 0,0–0,3 | Negro real. |
| 0,3 / 0,7 / 1,1 | Tres golpes ("tun–tun–TUN"): el cuadro se parte en dos mitades que destellan como las salidas reales — mitad derecha en rojo (look 2), mitad izquierda en morado (look 4), y el tercero todo blanco — con corte duro a negro entre golpes. |
| 1,1–1,5 | Sobre el blanco del tercer golpe, el nombre aparece recortado en negro; el blanco se apaga y el nombre queda en blanco sobre negro (sprite de 6 cuadros de brillo). |
| 1,5–1,8 | `v{version}` debajo. Corte a Control. |

- Producción: los destellos son capas `color` con colores `look:N` (salen de `scene.LOOKS`: si el usuario cambia los colores de sus looks, la intro cambia). Blender solo renderiza el nombre (6 cuadros con resplandor).
- Peso estimado: < 0,3 MB. Costo: casi nulo (cambios de color de rectángulos).
- Carácter: directo, enérgico, es literalmente lo que hace la app. Aviso: son 3 destellos en ~0,8 s (≈ 2,5 Hz, por debajo del límite de 3 Hz) y no a pantalla completa, sino dentro de la ventana Control.

**C · "Primer golpe"** — en vivo: reacciona al audio real. Duración 2,6 s.

| t (s) | Qué se ve |
|---|---|
| 0,0–0,4 | Negro; aparece en primer plano la lente de un faro (cristal facetado, 3D), apagada. |
| 0,4–2,2 | La lente **brilla con el nivel de audio real**: el cuadro mostrado depende del nivel que mide el motor en ese instante (16 cuadros de "apagada" a "a tope"). Si hay música, late con ella desde el primer segundo. Debajo: `Escuchando: {dispositivo}`. Sin audio, la lente respira sola (pista de respaldo del manifiesto). |
| 2,2–2,6 | El nombre y `v{version}` sobre la lente encendida. Corte a Control. |

- Producción: Blender, un solo encuadre de la lente; 16 cuadros variando la emisión de la lámpara (no es una animación temporal: es una escala de brillo).
- Peso estimado: ~1 MB. Costo: bajo (16 imágenes; la mayoría de los ticks repiten cuadro).
- Carácter: demuestra al abrir que "ya está escuchando"; es la más "dinámica" en sentido literal y sirve de comprobación de señal.

Comparación rápida:

| | A Faro | B Pulso | C Primer golpe |
|---|---|---|---|
| Duración | 2,4 s | 1,8 s | 2,6 s |
| Peso en el exe | 2–3 MB | < 0,3 MB | ~1 MB |
| Costo por tick | alto (medir) | mínimo | bajo |
| Depende de Blender | mucho | poco | medio |
| Reacciona al audio | no | no | sí |

### 7.5 Producción y presupuesto

- **Propuestas (F12)**: una sesión usa Blender por MCP (`mcp__Blender__execute_blender_code_for_cli`, Blender en segundo plano con un `.blend`), una escena por concepto, en paralelo si conviene. Deja en `fases/intro-propuestas/<A-faro|B-pulso|C-primer-golpe>/`: `preview.mp4`, `tira.png` (8 cuadros en una imagen), `storyboard.md`, `build.py`, `params.json` y los cuadros PNG. Se detiene para que el usuario elija.
- **Implementación (F13)**: reproductor + assets finales de la elegida en `assets/intro/`, incluidos en `lighthouse.spec`.
- **Presupuesto**: assets de la intro ≤ **3 MB** en el exe (tope duro 5 MB). El exe debe quedar ≤ 62 MB (límite del proyecto: 80 MB). PNG de 8 bits; sin audio.

---

## 8. Config

Todas las preferencias de interfaz van en **un diccionario `ui`** dentro de `config.json` (el cargador ya valida diccionarios anidados y rellena con defaults lo que falte):

| Llave | Tipo / valores | Default | Fase |
|---|---|---|---|
| `ui.theme` | `"oscuro"` · `"vaporwave"` · `"glass"` · `"blue_ocean"` | `"oscuro"` | F7 (los otros tres y el selector, F14) |
| `ui.vista` | `"auto"` · `"compacto"` · `"mini"` | `"auto"` | F8 (mini en F9) |
| `ui.tab` | `"show"` · `"audio"` · `"salidas"` · `"ayuda"` | `"show"` | F8 |
| `ui.avanzado` | `{id de tarjeta: bool}` | todo `false` | F8 |
| `ui.tab_nav` | bool (Navegar con Tab) | `false` | F8 |
| `ui.geo_mini` | geometría `WxH+X+Y` | `""` | F9 |
| `ui.mini_encima` | bool | `true` | F9 |
| `ui.mini_sin_foco` | bool (experimental) | `false` | F9 |
| `ui.tips` | bool | `true` | F10 |
| `ui.tutorial` | `"preguntar"` · `"no_preguntar"` · `"visto"` | `"preguntar"` | F11 |
| `ui.intro` | bool | `true` | F13 |

- `geo_control` (ya existe) pasa a restaurar **posición y tamaño** (F8).
- Versión de config: **v5** en F7 (aparece `ui`), **v6** en F8 (cambia el significado de `geo_control`). Las fases siguientes solo agregan llaves con default dentro de `ui`: no suben la versión.
- La acción `mini` se suma al mapa `keys` con default `["F9"]`.
- Un valor inválido cae a su default con aviso en el log, como el resto de la config. Para `ui.theme` eso incluye un tema que ya no exista (§13.5).

---

## 9. Sistema de tokens y tema por defecto

### 9.1 Módulo

`lighthouse/theme.py` (puro: sin Tk al importarlo):

```python
THEMES = {"oscuro": {...}}      # nombre -> dict plano de tokens
DEFAULT = "oscuro"
REQUIRED = frozenset({...})     # todas las llaves que un tema debe definir
def get(name) -> dict           # tema válido y completo; nombre desconocido -> DEFAULT con aviso
def validate(theme) -> list[str]  # llaves que faltan o valores mal formados
def px(n, scale) -> int         # px lógicos -> físicos
def contrast(a, b) -> float     # relación de contraste WCAG entre dos colores
def paint(widget, **tokens)     # colorea un widget tk clásico y recuerda opción -> token
def apply(root, theme)          # único punto que toca ttk.Style, option_add y la barra de título;
                                # vuelve a pintar todo lo registrado con paint()
```

Agregar un tema = agregar una entrada a `THEMES` con todas las llaves de `REQUIRED`. Un tema puede declarar `"base": "oscuro"` y definir solo lo que cambia.

**`apply` se puede llamar más de una vez** (cambio de tema en caliente, §13.5). Por eso ningún módulo de interfaz guarda un color en una variable ni lo pasa suelto a un widget: los `ttk` salen de `ttk.Style`, los `tk` clásicos y los ítems de Canvas pasan por `paint`, y los colores que se deciden en cada tick (punto de golpe, chips) se leen del tema vigente en ese momento.

Regla de oro, verificada por el self-check: **ningún literal de color** (`#rgb`, `#rrggbb` o nombre de color de Tk) en `ui.py`, `widgets.py`, `tips.py`, `tutorial.py`, `intro.py` ni `layout.py`. Quedan exentos por ser **datos del show**, no apariencia: `scene.py` (colores de los looks), `outputs.py` y `pantalla.py` (superficies de luz), y las constantes `PALETTE` / `KELVIN`.

### 9.2 Tokens

| Grupo | Tokens |
|---|---|
| **Color · superficies** | `bg` (fondo de ventana) · `surface` (tarjetas) · `surface_alt` (controles, botones) · `hover` · `trough` (canal de deslizadores y medidor) · `border` (separadores) · `border_strong` (contorno de controles) |
| **Color · texto** | `fg` · `fg_muted` · `fg_disabled` |
| **Color · acento y estado** | `accent` · `accent_fg` · `focus` · `danger` (relleno) · `danger_fg` · `danger_text` (texto de alarma sobre fondo oscuro) · `warn` · `ok` |
| **Color · En vivo** | `live_fg` (BPM y look activo) · `meter_level` · `meter_hit` · `meter_threshold` · `beat_on` · `beat_off` |
| **Color · ayudas** | `tooltip_bg` · `tooltip_fg` · `tooltip_border` · `tutorial_ring` · `intro_bg` · `intro_fg` |
| **Tipografía** | `font.family` · `font.body` · `font.small` · `font.title` · `font.big` (BPM, look activo) · `font.look` (botones de look) · `font.intro` — cada uno `(familia, puntos, peso)` |
| **Espaciado** (px lógicos) | `space.xs` 2 · `space.sm` 4 · `space.md` 8 · `space.lg` 12 · `space.xl` 16 |
| **Radio** (px lógicos) | `radius.sm` 3 · `radius.md` 6 — Tk solo redondea lo que se dibuja en Canvas (medidor, muestras, punto); los widgets nativos son rectos. El token existe para esos dibujos y para temas futuros |
| **Tamaños** (px lógicos) | `size.look_w` 60 · `size.look_h` 44 · `size.look_w_dense` 44 · `size.look_h_dense` 32 · `size.blackout_w` 96 · `size.control_h` 28 · `size.card_min_w` 340 · `size.tip_max_w` 320 |
| **Ventana** | `label` (nombre visible del tema) · `window.alpha` (1.0; opacidad de Control, para el tema "glass") · `window.alpha_hover` (1.0; opacidad con el puntero dentro de Control) · `window.dark_titlebar` (bool) · `window.caption` / `window.caption_fg` (color de la barra de título y de su texto; solo Windows 11) · `ttk.base` (`"clam"`) |
| **Tiempos** (ms) | `motion.tip_delay` 500 · `motion.tip_delay_next` 100 · `motion.layout_debounce` 120 |

Las distancias en Tk son píxeles físicos: todo relleno o tamaño pasa por `px()` para que la ventana escale al 125–150 %. Las fuentes en puntos ya escalan solas.

`window.alpha` solo se aplica a Control (nunca a las salidas ni al tooltip). Una ventana translúcida obliga al compositor de Windows a mezclar: el tema que la use debe medir CPU (§13.4).

### 9.3 Tema por defecto: "oscuro"

Oscuro neutro con acento ámbar (la lámpara del faro). Oscuro porque se usa de noche junto a rekordbox, que también es oscuro, y porque una ventana clara ilumina la cara del DJ y compite con las pantallas-luz.

| Token | Valor | Contraste medido |
|---|---|---|
| `bg` | `#14161A` | — |
| `surface` | `#1D2026` | — |
| `surface_alt` | `#272B33` | — |
| `hover` | `#313743` | `fg` 10,4:1 |
| `trough` | `#0E1013` | — |
| `border` | `#3A404B` | decorativo |
| `border_strong` | `#7A8496` | 4,3:1 sobre `surface`, 3,8:1 sobre `surface_alt` |
| `fg` | `#ECEFF4` | 15,7:1 sobre `bg`, 14,2:1 sobre `surface`, 12,3:1 sobre `surface_alt` |
| `fg_muted` | `#A7B0BD` | 7,5:1 sobre `surface`, 6,5:1 sobre `surface_alt` |
| `fg_disabled` | `#808997` | 4,6:1 sobre `surface`, 4,0:1 sobre `surface_alt` |
| `accent` | `#FFC53D` | 11,5:1 sobre `bg` |
| `accent_fg` | `#14161A` | 11,5:1 sobre `accent` |
| `focus` | `#5CC8FF` | 8,7:1 sobre `surface` |
| `danger` | `#D7263D` | relleno |
| `danger_fg` | `#FFFFFF` | 5,0:1 sobre `danger` |
| `danger_text` | `#FF6B6B` | 5,9:1 sobre `surface`, 5,1:1 sobre `surface_alt` |
| `warn` | `#FF9F1C` | 7,9:1 sobre `surface`, 6,9:1 sobre `surface_alt` |
| `ok` | `#4CD97B` | 9,0:1 sobre `surface`, 7,8:1 sobre `surface_alt` |
| `live_fg` | `#ECEFF4` | igual que `fg` |
| `meter_level` | `#7A8496` | — |
| `meter_hit` | `#ECEFF4` | — |
| `meter_threshold` | `#FF6B6B` | — |
| `beat_on` / `beat_off` | `#FFFFFF` / `#313743` | — |
| `tooltip_bg` / `tooltip_fg` / `tooltip_border` | `#F4F1E8` / `#14161A` / `#7A8496` | 16,0:1 |
| `tutorial_ring` | `#FFC53D` | — |
| `intro_bg` / `intro_fg` | `#000000` / `#FFFFFF` | — |
| `label` | `"Oscuro"` | — |
| `window.alpha` / `window.alpha_hover` | `1.0` / `1.0` | — |
| `window.dark_titlebar` | `true` | — |
| `window.caption` / `window.caption_fg` | `#14161A` / `#ECEFF4` | 15,7:1 |

Tipografía: `Segoe UI` (viene con Windows; no se empaqueta ninguna fuente). `font.body` 10 · `font.small` 9 · `font.title` 10 negrita · `font.big` 18 negrita · `font.look` 9 negrita · `font.intro` 28 negrita.

**Por qué se llama "oscuro" y no "faro"**: el usuario pidió cuatro temas por su nombre (oscuro, vaporwave, glass transparente y blue ocean). Este tema —oscuro neutro con acento ámbar— **es** el "oscuro" de esa lista y es el default. No existe un tema "faro" aparte: dos temas oscuros casi iguales en el selector solo harían dudar. El guiño al faro se queda en el acento ámbar y en la intro.

---

## 10. Accesibilidad

- **Contraste**: texto normal ≥ 4,5:1; texto grande, iconos, indicadores y contornos de control ≥ 3:1 (tabla de §9.3, medida). El self-check calcula el contraste de **todos los pares de §13.6** en cada tema y falla si alguno no llega: así un tema nuevo no puede romperlo.
- **No solo color**: el look activo se marca con fondo de acento **y** negrita **y** el texto "Look N · Nombre". Las alarmas son texto (SIN SEÑAL, SATURA), no solo un color. Blackout activo cambia su texto a "BLACKOUT ●".
- **Tamaños mínimos**: texto ≥ 9 pt (hoy la leyenda usa 8). Botones de look ≥ 60×44 px lógicos (≥ 44×32 en densa). Blackout ≥ 96×32. Cualquier otro control ≥ 28 px de alto.
- **Escalado**: funciona al 100–150 % (los tamaños de §3.5 se verifican simulando 150 % con `tk scaling`).
- **Teclado**:
  - Todo lo del show ya tiene tecla (looks, Blackout, Bump, modos, tap, sensibilidad) y se suma F9 (mini).
  - **Navegar con Tab** (opcional, apagado por defecto): hoy ningún control toma el foco, a propósito, porque `Espacio` (Blackout) también activaría el botón enfocado. Con la opción activa, los controles toman el foco (Tab / Mayús+Tab, flechas en deslizadores y listas, Espacio o Enter para activar) y, **mientras el foco esté en un control, las teclas de show quedan en pausa** (el mismo mecanismo que al escribir en un campo; el chip dice "Teclas: en pausa"). `Esc` devuelve el foco a la ventana y reactiva las teclas.
  - El foco siempre se ve: contorno `focus` de 2 px.
  - Con Ctrl o Alt presionados las teclas de show no disparan.
- **Fotosensibilidad**: la interfaz de Control nunca destella a pantalla completa; la vista previa mide ~28×20 px; la intro "Pulso" queda por debajo de 3 Hz y dentro de la ventana.
- **Lenguaje**: español llano en etiquetas y tooltips (§2.3, §5.2).

---

## 11. Riesgos

| Riesgo | Mitigación |
|---|---|
| El tema ttk `clam` cambia el aspecto de todos los controles y algún elemento (flecha de la lista, casilla) queda poco legible | F7 captura la ventana y revisa cada tipo de control; los colores de cada estado salen de tokens con contraste verificado |
| Recolocar tarjetas al redimensionar provoca parpadeo o cuesta CPU | Un solo `after(120)` cancelable; se recoloca solo si cambió el `Layout`; los widgets no se recrean. Se mide el tiempo de recolocación (objetivo ≤ 50 ms) |
| La UI nueva sube la CPU en show (más widgets vivos, vista previa) | Todo lo vivo va por `put()` a 30 Hz. Cada fase mide con el mismo arnés antes y después; límite: no subir más de 1 punto porcentual y seguir < 10 % |
| El cuerpo desplazable usa un Canvas contenedor | Es estático (solo se mueve al desplazar). Se mide; si cuesta, el desplazamiento se limita al modo compacto |
| "No quitar el teclado" en mini (`WS_EX_NOACTIVATE`) puede no llevarse bien con Tk | Es opcional y experimental: F9 lo verifica; si no es fiable, se documenta y no se incluye |
| Mini siempre encima tapa parte de rekordbox | El usuario lo coloca y redimensiona; se guarda su geometría; el interruptor está a un clic |
| La intro compite con el pintado al arrancar | Avanza desde `slow()`, un PNG por tick, presupuesto medido; el concepto B casi no cuesta; se desactiva con una casilla |
| Blender por MCP no disponible en la sesión de propuestas | F12 lo comprueba en precondiciones y se detiene; respaldo: `blender --background --python` si está en el PATH |
| Tooltips que tapan el control o salen de pantalla con varios monitores | Posición calculada contra el monitor real del puntero (`win32.monitors()`); función pura con self-check |
| El tutorial cambia looks de verdad con las pantallas puestas | Es lo que enseña; la banda de inicio lo dice ("la luz ya está funcionando"); se omite con Esc |
| Renombrar etiquetas desorienta a quien ya usa la app | `LEEME.txt` se actualiza en la misma fase; los tooltips explican cada control; los valores guardados no cambian |
| Glass: detrás de la ventana hay rekordbox, con formas de onda de mucho contraste | La opacidad mínima es 0,92 y el contraste se verifica en el **peor caso** (blanco o negro detrás de cada píxel, §13.6); con el puntero dentro, la ventana es opaca; el tooltip nunca es translúcido |
| Glass: la ventana translúcida sube la CPU | F14 mide con el arnés; si sube más de 1 punto, el tema queda opaco (`window.alpha` 1.0) y se documenta |
| Cambiar de tema en vivo deja algún widget con el color anterior | Todo color pasa por `ttk.Style` o por `theme.paint`; el self-check cambia de tema sin ventana y compara cada widget registrado |
| El self-check con ventanas falla en una máquina sin escritorio | La parte de interfaz del self-check crea la ventana retirada (`withdraw`), sin audio ni salidas ni escritura de config, y dura < 3 s |

---

## 12. Qué se verifica por script

| Qué | Cómo |
|---|---|
| Elección de modo | `layout.pick` contra la tabla de casos de §3.2 (incluida la histéresis) |
| Reparto de tarjetas | `layout.plan`: todas las tarjetas de la pestaña aparecen exactamente una vez, en columnas válidas |
| Tamaños pedidos | `winfo_reqwidth` / `winfo_reqheight` por modo contra §3.5, a escala 100 % y 150 % (`tk scaling`), con la ventana retirada |
| Tokens | Todo tema define `REQUIRED`; contrastes mínimos de §10 sobre los pares de §13.6; ningún literal de color fuera de los módulos exentos |
| Temas | Los cuatro temas definen los mismos tokens que "oscuro"; todos los pares de §13.6 pasan (en glass, en el peor caso); cambiar de tema sin ventana repinta todos los widgets registrados; `scene.LOOKS` y la composición de las salidas no cambian con el tema |
| Tooltips | Todo control interactivo tiene `id`, texto en `TIPS`, ≤ 200 caracteres; `tips.place()` (pura) nunca sale del monitor ni tapa el puntero |
| Tutorial | Todo `id` objetivo de `STEPS` existe en el registro; los valores de `ui.tutorial` migran bien |
| Intro | El manifiesto es válido, todos los archivos existen, peso total ≤ 3 MB, duración ≤ 3000 ms; el interpolador de pistas (puro) da los valores esperados |
| Teclas | Con Ctrl o Alt no hay acciones; con foco en un control (Navegar con Tab) quedan en pausa |
| CPU en show | Arnés de desarrollo en `$env:TEMP` (audio sintético a 100 bloques/s, 4 s, config temporal): `time.process_time()` / tiempo real, antes y después de cada fase |

---

## 13. Temas

Cuatro temas, los que pidió el usuario: **oscuro** (default), **vaporwave**, **glass** (transparente) y **blue ocean**. Los implementa F14.

### 13.1 Reglas

- **Qué cambia un tema**: la ventana Control en todas sus vistas (incluida Mini), la ventana de Calibrar, los tooltips, el tutorial y la intro (`intro_bg`, `intro_fg` y las fuentes; los colores `look:N` de la intro no).
- **Qué no cambia nunca**: las salidas de luz, la pantalla remota (`--pantalla`), los colores de los looks, `PALETTE` y `KELVIN`. Son del show y del cliente. `outputs.py` y `pantalla.py` **no importan `theme`**. La vista previa `▌▐` y las muestras de la barra de looks enseñan los colores reales de los looks: tampoco cambian.
- **Los cuatro son oscuros.** Un tema claro iluminaría la cara del DJ y competiría con las pantallas-luz (§9.3). Se distinguen por el matiz y por el acento, no por la luminosidad.
- **La tipografía no cambia** entre temas: `Segoe UI` con los tamaños de §9.3. Los tamaños pedidos de §3.5 (el mini cabe en 800 × 80) están verificados con esa fuente; otra familia cambiaría los anchos y obligaría a verificar cada vista por tema.
- **Los estados no cambian de mecánica**, solo de color: hover = fondo `hover`; activo = fondo `accent` con texto `accent_fg` y negrita; foco = contorno `focus` de 2 px. En los cuatro temas `focus` es de un matiz distinto al de `accent`, para que "enfocado" y "activo" no se confundan.
- **Las alarmas se leen igual en todos**: SIN SEÑAL en `danger_text` (rojo o coral), SATURA en `warn` (ámbar o arena), red bien en `ok` (verde). Ningún tema cambia el significado de un color de estado.
- Sin dependencias nuevas, sin timers, sin nada nuevo en `App.fast()`.

### 13.2 Paletas

| Token | oscuro (default) | vaporwave | glass | blue ocean |
|---|---|---|---|---|
| `label` | Oscuro | Vaporwave | Glass (transparente) | Blue Ocean |
| `bg` | `#14161A` | `#1A1033` | `#0B1016` | `#071A2B` |
| `surface` | `#1D2026` | `#24174A` | `#121922` | `#0C2438` |
| `surface_alt` | `#272B33` | `#31205F` | `#1A232E` | `#123049` |
| `hover` | `#313743` | `#40297A` | `#25313F` | `#1A405F` |
| `trough` | `#0E1013` | `#100A22` | `#06090D` | `#04111D` |
| `border` | `#3A404B` | `#4A3580` | `#34414F` | `#23506F` |
| `border_strong` | `#7A8496` | `#A592E0` | `#9AABBD` | `#6FA3C7` |
| `fg` | `#ECEFF4` | `#F6EEFF` | `#F4F8FB` | `#EAF6FF` |
| `fg_muted` | `#A7B0BD` | `#CDBFEE` | `#C3CEDA` | `#A5C4DA` |
| `fg_disabled` | `#808997` | `#A294CC` | `#9CAAB9` | `#7B9BB3` |
| `accent` | `#FFC53D` ámbar | `#FF71CE` rosa neón | `#9FE8FF` hielo | `#2EC4F1` aguamarina |
| `accent_fg` | `#14161A` | `#1A1033` | `#0B1016` | `#04111D` |
| `focus` | `#5CC8FF` | `#01CDFE` | `#FFD166` | `#FFD166` |
| `danger` | `#D7263D` | `#D6246E` | `#FF5C6C` | `#D12F45` |
| `danger_fg` | `#FFFFFF` | `#FFFFFF` | `#0B1016` | `#FFFFFF` |
| `danger_text` | `#FF6B6B` | `#FF9BB0` | `#FF9A9A` | `#FF8A80` |
| `warn` | `#FF9F1C` | `#FFE66D` | `#FFC670` | `#FFC857` |
| `ok` | `#4CD97B` | `#05FFA1` | `#6FE89B` | `#3DDC97` |
| `live_fg` | `#ECEFF4` | `#01CDFE` | `#F4F8FB` | `#7FE7FF` |
| `meter_level` | `#7A8496` | `#B967FF` | `#9AABBD` | `#6FA3C7` |
| `meter_hit` | `#ECEFF4` | `#01CDFE` | `#F4F8FB` | `#EAF6FF` |
| `meter_threshold` | `#FF6B6B` | `#FF71CE` | `#FF9A9A` | `#FF8A80` |
| `beat_on` | `#FFFFFF` | `#FF71CE` | `#FFFFFF` | `#7FE7FF` |
| `beat_off` | `#313743` | `#40297A` | `#25313F` | `#1A405F` |
| `tooltip_bg` | `#F4F1E8` | `#FFF0FA` | `#F4F8FB` | `#EAF6FF` |
| `tooltip_fg` | `#14161A` | `#1A1033` | `#0B1016` | `#071A2B` |
| `tooltip_border` | `#7A8496` | `#FF71CE` | `#9AABBD` | `#6FA3C7` |
| `tutorial_ring` | `#FFC53D` | `#01CDFE` | `#FFD166` | `#FFC857` |
| `intro_bg` | `#000000` | `#0D0221` | `#000000` | `#020B14` |
| `intro_fg` | `#FFFFFF` | `#FFFFFF` | `#FFFFFF` | `#EAF6FF` |
| `window.alpha` | `1.0` | `1.0` | **`0.92`** | `1.0` |
| `window.alpha_hover` | `1.0` | `1.0` | `1.0` | `1.0` |
| `window.dark_titlebar` | `true` | `true` | `true` | `true` |
| `window.caption` | `#14161A` | `#1A1033` | `#0B1016` | `#071A2B` |
| `window.caption_fg` | `#ECEFF4` | `#F6EEFF` | `#F4F8FB` | `#EAF6FF` |

Tipografía, espaciado, radios, tamaños y tiempos: los de "oscuro" (§9.2, §9.3). Los tres temas nuevos declaran `"base": "oscuro"` y definen solo las filas de esta tabla.

Carácter de cada uno:
- **oscuro**: gris neutro con acento ámbar. El más sobrio; no compite con rekordbox.
- **vaporwave**: índigo profundo con rosa neón de acento y cian en lo vivo (BPM, golpe del medidor, foco). El punto de golpe late en rosa. Menta para "bien", amarillo pastel para avisos.
- **glass**: pizarra azulada casi negra, acento hielo, ventana translúcida (§13.4). Textos más claros y fondos más oscuros que en los demás, para aguantar lo que haya detrás. `danger` es coral claro con texto oscuro: un rojo oscuro se pierde cuando detrás hay algo claro.
- **blue ocean**: azul marino con acento aguamarina; el BPM y el punto de golpe en espuma (`#7FE7FF`); avisos en arena y coral. El foco es arena para no confundirse con el acento azul.

### 13.3 Estados e indicadores por tema

| | oscuro | vaporwave | glass | blue ocean |
|---|---|---|---|---|
| Hover (fondo) | `#313743` | `#40297A` | `#25313F` | `#1A405F` |
| Activo / look seleccionado | ámbar `#FFC53D`, texto `#14161A` | rosa `#FF71CE`, texto `#1A1033` | hielo `#9FE8FF`, texto `#0B1016` | aguamarina `#2EC4F1`, texto `#04111D` |
| Foco (contorno 2 px) | azul claro `#5CC8FF` | cian `#01CDFE` | arena `#FFD166` | arena `#FFD166` |
| Blackout activo | `#D7263D`, texto blanco | `#D6246E`, texto blanco | `#FF5C6C`, texto `#0B1016` | `#D12F45`, texto blanco |
| **Señal**: punto de golpe encendido / apagado | `#FFFFFF` / `#313743` | `#FF71CE` / `#40297A` | `#FFFFFF` / `#25313F` | `#7FE7FF` / `#1A405F` |
| **Señal**: medidor (nivel · golpe · umbral) | `#7A8496` · `#ECEFF4` · `#FF6B6B` | `#B967FF` · `#01CDFE` · `#FF71CE` | `#9AABBD` · `#F4F8FB` · `#FF9A9A` | `#6FA3C7` · `#EAF6FF` · `#FF8A80` |
| **Sin señal** (chip) | `#FF6B6B` | `#FF9BB0` | `#FF9A9A` | `#FF8A80` |
| **Saturación** (chip SATURA y avisos) | `#FF9F1C` | `#FFE66D` | `#FFC670` | `#FFC857` |
| **BPM** y look activo (texto grande) | `#ECEFF4` | `#01CDFE` | `#F4F8FB` | `#7FE7FF` |
| Red / "Teclas: activas" | `#4CD97B` | `#05FFA1` | `#6FE89B` | `#3DDC97` |

Contraste **mínimo** de cada token sobre todos los fondos donde se usa (pares de §13.6), calculado con la fórmula WCAG 2.1. En glass, cada valor es el del **peor caso** con la ventana al 92 % (§13.6):

| Token | Mínimo exigido | oscuro | vaporwave | glass (peor caso) | blue ocean |
|---|---|---|---|---|---|
| `fg` | 4,5 | 10,4 | 10,2 | 8,1 | 9,8 |
| `fg_muted` | 4,5 | 6,5 | 8,2 | 6,6 | 7,5 |
| `danger_text` | 4,5 | 5,1 | 7,0 | 5,2 | 6,0 |
| `warn` | 4,5 | 6,9 | 11,2 | 6,8 | 8,8 |
| `ok` | 4,5 | 7,8 | 10,5 | 6,8 | 7,7 |
| `live_fg` | 4,5 | 12,3 | 7,4 | 9,7 | 9,6 |
| `accent_fg` sobre `accent` | 4,5 | 11,5 | 7,3 | 9,7 | 9,3 |
| `danger_fg` sobre `danger` | 4,5 | 5,0 | 4,8 | 4,5 | 5,0 |
| `tooltip_fg` sobre `tooltip_bg` | 4,5 | 16,0 | 16,4 | 17,9 | 16,0 |
| `intro_fg` sobre `intro_bg` | 4,5 | 21,0 | 20,0 | 15,5 | 18,0 |
| `fg_disabled` | 3,0 | 4,0 | 5,1 | 4,5 | 4,6 |
| `border_strong` | 3,0 | 3,8 | 5,2 | 4,5 | 5,0 |
| `focus` | 3,0 | 7,5 | 7,4 | 7,2 | 9,4 |
| `accent` (indicador) | 3,0 | 7,6 | 4,7 | 6,4 | 5,3 |
| `tutorial_ring` | 3,0 | 9,0 | 7,4 | 7,2 | 8,8 |
| `beat_on` | 3,0 | 11,9 | 4,7 | 8,7 | 7,6 |
| `danger` (contorno de Blackout) | 3,0 | 3,3 | 3,3 | 4,1 | 3,2 |
| `meter_level` sobre `trough` | 3,0 | 5,1 | 5,9 | 6,1 | 7,0 |
| `meter_hit` sobre `trough` | 3,0 | 16,5 | 10,3 | 13,2 | 17,3 |
| `meter_threshold` sobre `trough` | 3,0 | 6,9 | 7,8 | 7,1 | 8,3 |

Todos pasan. El más justo es `danger_fg` sobre `danger` en glass (4,5 en el peor caso): si se toca ese par, hay que volver a calcular.

### 13.4 Glass en Tk y Windows

**Enfoque elegido: opacidad de toda la ventana Control** con `root.attributes("-alpha", 0.92)`, sobre una paleta pensada para verse bien también opaca.

Se probó un prototipo en esta máquina (Windows 11 compilación 26300, Tk 8.6.15), con una ventana de 360 × 160 y texto claro sobre `#101820`:

| Opción | Resultado medido | Veredicto |
|---|---|---|
| `-alpha` 0.90 | Funciona. Fondo y texto se mezclan con lo de detrás: el blanco del texto bajó de 240 a ~219 sobre un fondo oscuro, y las letras de la ventana de atrás se adivinan | **Viable**, con opacidad alta y contraste verificado en el peor caso |
| Mica / Acrylic (`DwmSetWindowAttribute` 38 + `DwmExtendFrameIntoClientArea`) | Las tres llamadas devuelven éxito, pero Tk pinta con GDI y sus píxeles se **suman** al fondo del sistema: `#101820` se vio como `(100, 108, 116)` y `#000000` como `(84, 84, 84)`; el texto `#F0F4F8` salió como blanco puro | **Descartado**: el color final no lo decide el tema, así que el contraste no se puede garantizar ni verificar. Además el efecto solo existe en Windows 11 22H2 o posterior, y Windows lo vuelve sólido cuando la ventana no está activa, que es justo el estado normal del mini junto a rekordbox |
| `-transparentcolor` | Abre agujeros totalmente transparentes por los que **pasan los clics**; el borde suavizado del texto deja un halo del color clave (93 tonos distintos alrededor de las letras) | **Descartado**: no es vidrio, es un hueco, y deja el texto flotando sobre rekordbox sin fondo |

Reglas del tema glass:
- **Opacidad 0,92** en reposo. Es el mínimo: por debajo, lo de atrás estorba la lectura aunque el contraste numérico pase.
- **Opaca al interactuar**: con el puntero dentro de Control la ventana pasa a `window.alpha_hover` (1,0); al salir, vuelve a 0,92. Va por eventos `<Enter>` / `<Leave>` de la raíz (comprobando que el puntero salió de verdad de la ventana, no hacia un hijo); sin timers. Mientras el tutorial está activo también es opaca.
- **El tooltip nunca es translúcido** (es otra ventana, con su propio fondo claro).
- **Nunca** se aplica a las salidas ni a `--pantalla`.
- **Barra de título**: oscura, del color `window.caption` en Windows 11.
- **Se mide la CPU** con el arnés: la ventana translúcida obliga a mezclar cada repintado. Si glass sube más de 1 punto sobre "oscuro", el tema se queda opaco y se documenta.

**Fallback** (glass se dibuja **opaco**, con su misma paleta, que ya cumple el contraste sin transparencia):
- **Windows 10**: `-alpha` funciona igual que en Windows 11 (ventanas en capas), así que glass se ve translúcido también ahí. Lo único que se pierde es el color de la barra de título (`window.caption` necesita Windows 11): queda la barra oscura estándar, o la clara si el sistema tampoco soporta el modo oscuro. Ninguna de esas llamadas lanza.
- **Efectos de transparencia desactivados en Windows** (Configuración → Personalización → Colores; valor `EnableTransparency` = 0 en `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize`, leído con `winreg`): glass opaco. Quien apagó la transparencia en su sistema no la quiere aquí.
- **`-alpha` no se aplica** (la llamada lanza o el valor leído después no es el pedido): glass opaco, con aviso en el log.
- En los tres casos el selector muestra una nota bajo la lista: `En este equipo, Glass se muestra sin transparencia.`

### 13.5 Selector, vista previa y config

- **Dónde**: pestaña Ayuda → tarjeta `ayuda`, lista desplegable **Tema** (`ayuda.tema`) con los `label` de los temas, en este orden: Oscuro · Vaporwave · Glass (transparente) · Blue Ocean.
- **Vista previa inmediata**: al elegir un tema se aplica en el acto a toda la ventana (`theme.apply`), sin botón de confirmar ni reinicio. No hace falta un cuadro de muestra: la propia ventana es la muestra. La rueda del ratón no cambia la lista (§4), así que no hay cambios por accidente.
- **No toca el show**: el cambio corre en el hilo de interfaz y puede retrasar un pintado de las salidas una sola vez. Se mide (objetivo ≤ 100 ms) y se reporta.
- **Lo que se repinta**: todos los estilos `ttk`, todos los widgets registrados con `theme.paint` (incluidos los ítems de Canvas del medidor y las muestras), el tooltip, el anillo y el globo del tutorial si están a la vista, la barra de título y la opacidad. Los colores que se deciden en cada tick se leen del tema vigente.
- **Config**: `ui.theme` (ya existe desde F7, con `"oscuro"`). Se guarda con el resto de la config. **No se sube la versión**: la llave ya existe y solo crece la lista de valores válidos. La migración es una **normalización al cargar**: un valor que no sea texto o que no nombre un tema de `THEMES` (config editada a mano, o guardada por una versión futura con un tema que esta no tiene) cae a `"oscuro"` con aviso en el log, sin tocar ninguna otra llave.
- **Mini**: no tiene selector (no hay sitio); usa el tema elegido.

### 13.6 Pares de contraste que verifica el self-check

Función pura `theme.contrast(a, b)` (luminancia relativa WCAG 2.1). El self-check recorre **todos los temas** y falla, nombrando tema y par, si alguno queda bajo su mínimo.

**Texto normal, ≥ 4,5:1**
- `fg`, `fg_muted`, `danger_text`, `warn`, `ok` y `live_fg`, cada uno sobre `bg`, `surface` y `surface_alt`.
- `fg` sobre `hover`.
- `accent_fg` sobre `accent` · `danger_fg` sobre `danger` · `tooltip_fg` sobre `tooltip_bg` · `intro_fg` sobre `intro_bg` · `window.caption_fg` sobre `window.caption`.

**Texto grande, indicadores y contornos, ≥ 3:1**
- `fg_disabled` sobre `surface` y `surface_alt`.
- `border_strong`, `focus`, `accent`, `tutorial_ring` y `beat_on`, cada uno sobre `bg`, `surface` y `surface_alt`.
- `accent` sobre `hover` · `danger` sobre `bg` y `surface` · `beat_on` contra `beat_off`.
- `meter_level`, `meter_hit` y `meter_threshold` sobre `trough`.

**Temas translúcidos** (`window.alpha` < 1): además, cada par anterior —menos los del tooltip y la barra de título, que no son translúcidos— debe cumplir su mínimo en el **peor caso**:

```python
def mix(color, behind, alpha)        # alpha * color + (1 - alpha) * behind, por canal
def contrast_glass(fg, bg, alpha):   # detrás de cada píxel puede haber blanco o negro,
    return min(contrast(mix(fg, x, alpha), mix(bg, y, alpha))   # y no tiene por qué ser lo mismo
               for x in ("#000000", "#FFFFFF")                  # detrás de la letra que detrás del fondo
               for y in ("#000000", "#FFFFFF"))
```

Es deliberadamente pesimista: una forma de onda blanca sobre negro, detrás de la ventana, puede dejar blanco detrás del fondo y negro detrás de la letra de al lado.

**Completitud**: `set(theme.get(n)) == set(theme.get("oscuro"))` para cada tema; ninguno puede dejar un token sin definir ni inventar uno que el tema base no tenga.
