# Intro elegida: C · "Primer golpe" (sin audio, lente llena de luz)

- **Fecha:** 2026-11-22.
- **Elección del usuario** (literal): "C, pero no necesita detectar nada de inicio, el parpadeo se ve bien, solo asegúrate que se vea mejor, más realista, foco lleno de luz."
- **Ver:** `C-primer-golpe/preview.mp4` (2,6 s, 640×360) y `C-primer-golpe/tira.png`. La primera versión quedó en `C-primer-golpe/v1/` para comparar.

## Ajustes aplicados

1. **Sin audio.** Se quitó `Escuchando: {dispositivo}` y toda dependencia del nivel real del motor. El parpadeo es una **pista autoral fija**, `parpadeo` en `C-primer-golpe/params.json`, en el formato de pistas del manifiesto (`[t_ms, nivel, easing]`). Conserva el ritmo de la primera versión: 5 golpes a 128 BPM (0,40 · 0,87 · 1,34 · 1,81 · 2,28 s). Cada golpe hace `corte` a 1,0, se sostiene 40 ms (para que ningún tick de ~30 Hz se pierda el pico) y cae con `out_cubic` a 0,44 en 160 ms y a 0,18 hacia el golpe siguiente.
2. **Más realista, "foco lleno de luz".**
   - La lente de Fresnel tiene los anillos tallados para enfocar la lámpara. Como la lámpara está en el foco de los rayos que vienen de la cámara, en cada golpe se enciende **todo el cristal**, no una franja.
   - Lámpara con núcleo y bulbo esmerilado, bruma volumétrica suave dentro de la carcasa y halo delante, carcasa metálica con pernos, barras y rugosidad irregular, y Bloom + Fog Glow creíbles. Se quitó el destello horizontal.
   - Render en Cycles (CPU, 8 hilos) con solo dos pases EXR combinados linealmente: ≈ 55 s en total.
3. **Final:** el título `LightHouse` (de `app.json`) y `v{version}` aparecen desde 2,2 s bajo la lente. Son textos de Tk y no están en ningún PNG.
4. **Peso:** 16 PNG 640×360 en gris de 8 bits (`lente_00` apagada … `lente_15` a tope) = **506 646 B (0,48 MB)**, dentro de los 3 MB. La pista usa 10 de los 16 cuadros: si hiciera falta bajar peso, se pueden empaquetar solo esos (≈ 0,3 MB), a costa de no poder cambiar la pista sin regenerar.

## Para F13

**Manifiesto sugerido** (`assets/intro/intro.json`). La pista `nivel` es la lista `parpadeo` de `params.json`, copiada tal cual:

```json
{
  "formato": 1,
  "lienzo": [640, 360],
  "duracion_ms": 2600,
  "fondo": "token:intro_bg",
  "capas": [
    {"id": "lente", "tipo": "secuencia", "archivos": "lente_{:02d}.png", "cuadros": 16, "cuadro_por": "nivel", "pos": [0.5, 0.5],
     "pistas": {"visible": [[0, false], [200, true, "corte"]], "nivel": "<parpadeo de params.json>"}},
    {"id": "nombre", "tipo": "texto", "texto": "{app}", "fuente": "token:font.intro", "color": "token:intro_fg", "pos": [0.5, 0.80],
     "pistas": {"visible": [[0, false], [2200, true, "corte"]]}},
    {"id": "version", "tipo": "texto", "texto": "v{version}", "fuente": "token:font.small", "color": "token:fg_muted", "pos": [0.5, 0.895],
     "pistas": {"visible": [[0, false], [2200, true, "corte"]]}}
  ]
}
```

- Cuadro mostrado = `round(nivel × 15)`. El easing de un punto rige el tramo que llega a él; `corte` salta al llegar (así lo evalúa `comun.pista()`, que hace el preview).
- **Rendimiento, medido aquí** con Tk 8.6.15 y la ventana oculta:
  - `PhotoImage(file=…)` de un cuadro 640×360 tarda ≈ 4,3 ms (p95 4,9), por encima del presupuesto de 4 ms por tick.
  - Leyendo los bytes al empezar (0,5 MB) y usando `PhotoImage(data=…)` tarda ≈ 3,1 ms (p95 3,5).
  - Cambiar a una imagen ya decodificada cuesta ≈ 1,5 ms.
  - Regla: como mucho una decodificación por tick, reutilizar las ya hechas y, en los ticks libres, adelantar el siguiente cuadro de la pista.
- **Generador:** F13 lo copia a `tools/intro/` (va al repo, no entra al exe): `generar.ps1`, `comun.py`, `app.json` y `C-primer-golpe/` (`build.py`, `params.json`, `escena.blend`, `storyboard.md`). Este archivo se copia como `tools/intro/LEEME.md`. Las rutas funcionan desde ahí: `generar.ps1` busca la raíz del repo hacia arriba y reescribe `app.json` a su lado; `build.py` importa `comun.py` de su carpeta o de la de arriba.

## Regenerar

```powershell
.\fases\intro-propuestas\generar.ps1 -Concepto C-primer-golpe                 # ≈ 1 min de CPU
.\fases\intro-propuestas\generar.ps1 -Concepto C-primer-golpe -ReusarCapas    # solo tiempos/resplandor/textos: segundos
```

Desde `tools/intro/`, lo mismo con `.\tools\intro\generar.ps1`. Requiere Blender 5.2 o superior (`$env:BLENDER_PATH`, el PATH o `C:\Program Files\Blender Foundation`). Se ajusta solo editando `C-primer-golpe/params.json`.


## Ajustes de F13 (luz difuminada, sin cortes)

- Pedido del usuario: la lente y el brillo de la v2 estaban bien; el resplandor terminaba en un corte recto (como un PNG mal recortado). Debía verse difuminado, como captado por una lente empañada.
- Causa del corte: el halo de la v2 era más grande que el cuadro de 640×360 (con la lente a 216 px de alto sobraban unos 29 px arriba), así que el resplandor se recortaba contra el borde; el degradado, además, salía sin dither y con bandas.
- Lienzo de 800×450 (antes 640×360) con la lente del mismo tamaño en pantalla (216 px de alto): `lienzo` y `encuadre.alto_rel` 0,48. El halo tiene sitio y cae a negro antes de los bordes (<= 1/255).
- `velo` (nuevo, en `build.py`): lente empañada tipo Pro-Mist. Las altas luces (sobre `umbral`) se desenfocan con tres gaussianas (`sigma` en px, `fuerza`) y se suman de vuelta; el Bloom queda como único Glare. Se quitó el Fog Glow.
- `dither` (nuevo): dither de Blender, sin bandas.
- `asset.niveles` 8 y `asset.franjas` 3: el costo de decodificar un PNG crece con sus píxeles (≈ 11,8 ms por megapíxel en Tk) y no cabe en un tick de 4 ms. Cada cuadro se parte en 3 franjas horizontales (`lente_NN_K.png`, `comun.partir_png`), que la app decodifica de una en una; con 8 niveles hay menos cuadros distintos que decodificar. Los cuadros completos quedan en `cuadros/` (preview y tira) y las franjas en `cuadros/franjas/`.
- El fondo del escenario en `assets/intro/intro.json` es `#000000` fijo (igual al negro de los cuadros), independiente del tema.
- Los PNG de `assets/intro/` son las franjas: `.\tools\intro\generar.ps1 -Concepto C-primer-golpe` y copiar `cuadros\franjas\lente_*.png` (borrando antes los de `assets\intro\`). `intro.json` se actualiza a mano si cambian `lienzo`, `cuadros` o `franjas`.