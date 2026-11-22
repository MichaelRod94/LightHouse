# Fase F1: Base modular (paquete, config persistente, log, self-check)

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior: Windows, audio en tiempo real y Tkinter. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** es una app de escritorio Python para Windows. Escucha el audio de un set de DJ y convierte cada golpe (kick) en luz: ventanas de color sólido en pantallas que funcionan como luces.
- Hoy es una maqueta funcional **en un solo archivo**, `lighthouse.py` (~580 líneas):
  - `Engine`: DSP puro; detecta golpes, BPM, calma y tempo, y calcula la luz 0..1.
  - `App`: GUI Tk con ventana Control y ventana Luz; captura con PyAudioWPatch (WASAPI loopback).
  - `selftest()`: asserts con señal sintética.
- Dependencias instaladas: numpy, scipy, PyAudioWPatch y tkinter (stdlib). Python 3.14.

## Lee primero

1. `fases/README.md`: arquitectura decidida, decisiones y estado. **Respeta lo decidido.**
2. `lighthouse.py` completo.
3. `PLAN.md` (diseño de la maqueta), solo si necesitas contexto de una función.

## Precondiciones (verifícalas antes de tocar código)

- `python lighthouse.py --test` imprime `ok: ...`. Si falla, detente y avisa.
- `git status`. Anota qué hay sin commitear; no lo toques fuera de esta fase.

## Objetivo

Convertir el archivo único en el paquete `lighthouse/` **sin cambiar el comportamiento**, y agregar:
- config persistente;
- log a archivo;
- self-check ejecutable con `python -m lighthouse --test`.

Esta base la usan todas las fases siguientes.

## Alcance

### Entra

- **Paquete** `lighthouse/`. Crea solo estos módulos, en esta fase:

  | Archivo | Contenido |
  |---|---|
  | `__init__.py` | `VERSION = "0.4.0"` |
  | `__main__.py` | `main()`: configura el logging; `--test` corre el self-check y sale con código 0/1; sin argumentos abre la app |
  | `engine.py` | `Engine` y `BLOCK`, **sin cambios de lógica** |
  | `audio.py` | Lo que hoy hace `App` con PyAudioWPatch (enumerar loopback, default, abrir/cerrar stream, reconectar), en funciones o en una clase `Audio` pequeña. El callback convierte bytes → mono float y llama a una función que recibe |
  | `ui.py` | `App` (ventana Control + ventana Luz), presets (`FILTERS`, `CALM`, `DELAYS`, `KELVIN`, `PALETTE`) y el watchdog de silencio |
  | `config.py` | Carga y guardado de configuración (abajo) |
  | `selftest.py` | El `selftest()` actual, adaptado a imports del paquete |

- **Borra `lighthouse.py`** de la raíz con `git mv` o moviendo el contenido. Un archivo `lighthouse.py` junto a un paquete `lighthouse/` rompe los imports.
- **Config** en `%APPDATA%\LightHouse\config.json`:
  - Contiene `"version": 1` y todos los valores que el usuario puede cambiar:
    - todos los sliders;
    - modo, sincronía, fuente de BPM y divisor;
    - preset de filtro y corte;
    - intensidad por golpe;
    - modo de color, temperatura y paleta;
    - nombre del dispositivo de audio;
    - geometría (posición y tamaño) de ambas ventanas.
  - **Escritura atómica**: escribir a `config.json.tmp` y luego `os.replace`.
  - **Guardado**: con debounce de ~1 s tras el último cambio, y al cerrar.
  - **Cargador tolerante**:
    - Llaves desconocidas → se ignoran.
    - Llaves faltantes → default.
    - Tipo inválido → default + warning en el log.
    - JSON corrupto → renombrarlo a `config.json.bad` y arrancar con defaults.
  - Los **defaults** salen de los valores iniciales actuales de `Engine` y de la UI: una sola fuente de verdad, sin duplicar números.
- **Log** con `logging`:
  - `RotatingFileHandler` (1 MB × 3) en `%LOCALAPPDATA%\LightHouse\logs\lighthouse.log`.
  - Hooks: `sys.excepthook`, `threading.excepthook` y `root.report_callback_exception`. Escriben el traceback al log y muestran un texto corto en el label de estado.
  - Registrar: arranque (versión, Python, dispositivo elegido), errores de stream y reconexiones.
- **`requirements.txt`** con las versiones instaladas fijadas: `numpy`, `scipy` y `PyAudioWPatch`. Consulta las versiones con `python -m pip show`.
- **`.gitignore`**: `__pycache__/`, `*.pyc`, `build/`, `dist/`, `.venv*/`.

### No entra

- Cambios de lógica del motor, nuevos controles o cambios visuales.
- Entrada de micrófono/interfaz (F2), quitar scipy (F3), looks (F4) y multiventana (F5).
- Tests con frameworks: se mantiene el estilo `assert` del self-check.

## Diseño decidido

- Un solo proceso: hilo de audio (callback PortAudio) + hilo Tk, igual que hoy. Se mantiene el lock alrededor de `Engine.process`.
- `--test` debe funcionar también dentro del futuro exe (F3), por eso vive en `lighthouse/selftest.py` y no en `tests/`.
- `config.py` expone algo como `load() -> dict` y `save(d)`, más un registro simple de qué perillas persistir. Sin clases de esquema ni librerías.
- Un `# ponytail:` donde simplifiques a propósito, con el techo y la mejora futura.

## Criterios de aceptación

1. `python -m lighthouse --test` imprime la misma línea `ok: ...` que el `lighthouse.py --test` original y sale con código 0.
2. `python -m lighthouse` abre la app y **se ve y se comporta igual** (los mismos paneles y atajos).
3. **Persistencia**: cambia 3 sliders, el modo y el modo de color, cierra y vuelve a abrir → se conservan. Mueve la ventana Luz → al reabrir aparece donde estaba.
4. Borra `config.json` → la app arranca con defaults. Corrompe `config.json` (escribe `{{{`) → arranca con defaults, existe `config.json.bad` y hay un warning en el log.
5. Existe `%LOCALAPPDATA%\LightHouse\logs\lighthouse.log` con la línea de arranque.
6. Ya no existe `lighthouse.py` en la raíz.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
Get-Content "$env:LOCALAPPDATA\LightHouse\logs\lighthouse.log" -Tail 5
```
```powershell
Get-Content "$env:APPDATA\LightHouse\config.json"
```

Para la UI, escribe un script temporal **fuera del proyecto** (en `$env:TEMP`) que:
1. Instancie la app.
2. Mueva valores por las variables Tk.
3. Llame al guardado y cierre.
4. Re-instancie la app y compare.

Sin audio sonando, la app debe seguir viva gracias al watchdog.

## Reglas

- **Shell**: solo PowerShell (Windows PowerShell 5.1: sin `&&` ni `||`; usa `;` o `if ($?) {}`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`. `git mv` está permitido.
- **Dependencias**: ninguna nueva en esta fase.
- **Alcance**: cambios mínimos. No adelantes fases siguientes. Si algo del diseño es imposible, detente y explica alternativas antes de desviarte.

## Al terminar

1. Actualiza `fases/README.md`: fila F1 → ✅, fecha y nota de una línea. Agrega notas para F2 si cambió algo relevante (nombres de módulos o funciones).
2. Responde al usuario con:
   - qué cambió;
   - cómo probarlo (comandos);
   - qué no pudiste verificar;
   - **un mensaje de commit sugerido** (en español, p. ej. `refactor: paquete lighthouse con config persistente y log`) y la lista de archivos.

   **No hagas el commit.**
