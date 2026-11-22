# C · "Primer golpe" — storyboard (versión elegida)

La lente de un faro, en primer plano, parpadea con un ritmo de bombo y se llena de luz en cada golpe. **2,6 s** (preview a 30 fps, 78 cuadros), 640×360, luz neutra sobre negro. **No lee el audio**: el parpadeo es una pista fija escrita en `params.json` (`parpadeo`), con el mismo ritmo de la primera versión (128 BPM: golpes en 0,40 · 0,87 · 1,34 · 1,81 · 2,28 s).

| t (s) | Qué pasa |
|---|---|
| 0,0–0,2 | Negro. |
| 0,2–0,4 | Aparece la lente **apagada** (`lente_00`): vidrio de Fresnel con sus anillos tallados, aros de metal con pernos, barras del bastidor y el tambor de la carcasa a un lado. |
| 0,4–2,2 | Cuatro golpes. En cada uno la lente se **llena de luz** de golpe (`lente_15`: el cristal entero encendido, anillos marcados, halo y bruma) y cae en ~0,45 s a un brillo bajo (`lente_03`), donde ya se leen los anillos. |
| 2,2–2,6 | Quinto golpe (2,28 s). El nombre y `v{version}` aparecen bajo la lente (textos de Tk). Corte a Control. |

## Cómo la compondría la app (F13)

- Capa `secuencia`: `lente_{:02d}.png`, 16 cuadros, `"cuadro_por": "nivel"`, con la pista `nivel` del manifiesto = la lista `parpadeo` de `params.json` (`[t_ms, nivel, easing]`; `corte` al golpe y `out_cubic` en la caída). Cuadro = `round(nivel × 15)`. Visible desde 200 ms.
- Capas `texto` (Tk, **ninguna en PNG**): `{app}` (`token:font.intro`, `token:intro_fg`, y 0,80) y `v{version}` (`token:font.small`, `token:fg_muted`, y 0,895), desde 2200 ms.
- Ya no hay `Escuchando: {dispositivo}` ni dependencia del nivel de audio.

## Assets y costo

| Imágenes que necesita la app | Peso total medido (suma de los PNG) | Costo esperado |
|---|---|---|
| 16 PNG 640×360, gris de 8 bits (`lente_00` apagada … `lente_15` a tope; escala de brillo) | **506 651 B = 0,48 MB** (25–34 KB cada uno) | **Bajo.** Medido aquí (Tk 8.6.15, ventana oculta): `PhotoImage(file=…)` ≈ 4,3 ms (p95 4,9), por encima del presupuesto de 4 ms; con los bytes leídos al empezar (0,5 MB) y `PhotoImage(data=…)` ≈ 3,1 ms (p95 3,5). Una decodificación como mucho por tick, reutilizando las ya hechas (la pista usa unos 13 cuadros distintos y los repite); cambiar a una imagen ya decodificada ≈ 1,5 ms. |

## Cómo se renderiza (y por qué es más realista que la primera versión)

- **Lente de Fresnel enfocada**: la cara de cada anillo tiene la pendiente que manda un rayo hacia el foco (Snell con IOR 1,5, focal 1,3). La lámpara (núcleo + bulbo esmerilado) está justo donde la lente enfoca los rayos que vienen de la cámara: encendida, **todo el cristal** se ve lleno de luz, como cuando el haz de un faro te apunta.
- **Cycles en CPU, acotado**: la luz se suma linealmente, así que solo se renderizan **dos pases** EXR (`capas/ambiente.exr`: luces de estudio y reflejos con la lámpara apagada; `capas/lampara.exr`: solo lámpara, bruma interior y haz). Cada nivel es `ambiente + k·lampara` con `k = 0,55·(i/15)^2,2`, y el compositor le aplica Bloom + Fog Glow por nivel. 128 muestras adaptativas + denoise, 8 hilos: ≈ 55 s en total en esta máquina.
- **Bruma volumétrica** suave dentro del tambor y un halo delante de la lente (solo en el pase de la lámpara: el fondo queda negro real). **Carcasa** de metal con rugosidad irregular, pernos y barras, iluminada por una luz clave y una contraluz.

## Riesgos

- 16 imágenes decodificadas en memoria mientras dura la intro (se liberan al terminar).
- El golpe a tope es un destello blanco grande dentro del lienzo (5 golpes en 2,2 s ≈ 2,1 Hz, por debajo de 3 Hz).
- Re-render ≈ 1 min de CPU (8 de 12 hilos); `-ReusarCapas` recompone niveles y preview en segundos si solo cambian tiempos, resplandor o textos.

## Regenerar y ajustar

```powershell
.\fases\intro-propuestas\generar.ps1 -Concepto C-primer-golpe
.\fases\intro-propuestas\generar.ps1 -Concepto C-primer-golpe -ReusarCapas   # sin volver a renderizar los pases
```

En `params.json`: `parpadeo` (la pista autoral), `lente` (focal, anillos, giro), `encuadre`, `lampara`, `bruma`, `luces`, `nivel_max` y `asset.gamma` (curva de brillo), `resplandor`, `textos` y `tira_ms`. La primera versión (con "Escuchando…" y destello horizontal) quedó en `v1/` para comparar.
