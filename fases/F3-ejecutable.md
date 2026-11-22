# Fase F3: Ejecutable para usuario final (sin scipy, PyInstaller, ZIP portable)

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior con experiencia en empaquetado para Windows (PyInstaller) y DSP básico. Implementas **solo esta fase**.

## Proyecto

**LightHouse** es una app de escritorio Python para Windows. Escucha el audio de un set de DJ (loopback o interfaz de audio) y convierte cada golpe en luz.
- Paquete `lighthouse/`: `engine.py`, `audio.py`, `ui.py`, `config.py`, `selftest.py`, `__main__.py`.
- `python -m lighthouse --test` corre los self-checks.
- El cliente es un usuario promedio: necesita **un ejecutable que abra con doble clic**, sin instalar Python.

## Lee primero

1. `fases/README.md`: arquitectura y decisiones (sección *Ejecutable*) y estado. **Respeta lo decidido.**
2. `lighthouse/engine.py` (sobre todo `set_band` y `process`), `lighthouse/__main__.py`, `lighthouse/selftest.py` y `requirements.txt`.

## Precondiciones

- `fases/README.md` marca **F2 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa.
- `git status`.

## Objetivo

1. **Quitar scipy** del runtime: ~116 MB en disco y 2 s de arranque, solo para `butter`/`sosfilt`.
2. **Ejecutable onedir** con PyInstaller, `build.ps1` reproducible, ZIP portable y guía para el usuario final.

## Alcance

### Entra

**Filtro propio en `engine.py`** (reemplaza `butter` + `sosfilt`)
- Pasa-banda = **2 biquads pasa-altos a 30 Hz + 2 biquads pasa-bajos al corte**: Butterworth de 4º orden por lado, Q = 0.5412 y 1.3066, fórmulas RBJ (Audio EQ Cookbook). Forma directa II transpuesta, con estado persistente entre bloques.
- `hz=0` → sin filtro, como hoy.
- Rehacer coeficientes en `set_band` y al cambiar `sr`, de forma segura entre hilos: reemplazar el objeto entero, como hoy.
- **Rendimiento**: un lazo Python sobre 480 muestras cuesta ~187 µs por bloque (medido), aceptable.
  - Preferible **decimar ×8 antes de filtrar**: promedio de grupos de 8 muestras → 60 muestras por bloque a `sr/8`, ~25 µs. La RMS de banda completa sigue usando la señal cruda.
  - Si decimas, documéntalo con un `# ponytail:` (filtro antialias tipo caja; suficiente para energía < 250 Hz).
- **Check opcional de desarrollo** en `selftest.py`: si `scipy` se puede importar, comparar la magnitud del filtro propio contra `butter(4, [30, hz], 'bandpass')` a 30, 60, 120, 250 y 1000 Hz, con tolerancia de ±2 dB en banda y atenuación ≥ 20 dB a 1 kHz. Si scipy no está, se salta con un aviso. El self-check principal debe pasar **sin scipy**.

**Dependencias**
- `requirements.txt` sin scipy.
- Nuevo `requirements-build.txt`: `pyinstaller>=6.15` fijado a la versión que instales.

**Punto de entrada**
- `run.py` en la raíz (PyInstaller necesita un script fuera del paquete): `from lighthouse.__main__ import main; main()`.
- **No lo llames `LightHouse.py`**: Windows no distingue mayúsculas, así que `import lighthouse` cargaría ese script en vez del paquete. El nombre del exe sale de `name=` en el spec.

**`lighthouse.spec`** (versionado)
- `name="LightHouse"`, `console=False` y `upx=False`.
- Ícono `assets/lighthouse.ico`.
- `excludes` de lo que el site global arrastraría: `scipy`, `cv2`, `PIL`, `matplotlib`, `pandas`.
- Si PyInstaller no recoge solo el `.pyd` y las DLL de `pyaudiowpatch`, agrega `collect_dynamic_libs("pyaudiowpatch")`.

**Ícono**
- `assets/lighthouse.ico`, generado **una vez** con un script temporal en `$env:TEMP` usando Pillow si está disponible (es solo herramienta de desarrollo, no dependencia).
- Diseño simple: círculo blanco con halo sobre negro. Tamaños 16–256.

**`build.ps1`** (PowerShell 5.1)
1. Parámetro `-Python` (default `python`). Muestra la versión.
2. Crea o reusa `.venv-build` e instala `requirements.txt` + `requirements-build.txt`: **venv limpio**, para no arrastrar opencv o Pillow del site global.
3. Corre `python -m lighthouse --test` dentro del venv. Si falla, aborta.
4. Corre `pyinstaller lighthouse.spec --noconfirm --clean`.
5. Corre `dist\LightHouse\LightHouse.exe --test` con `Start-Process -Wait -PassThru` y revisa `ExitCode` (exe windowed: el resultado va por código de salida y log). Si no es 0, aborta.
6. Reporta tamaño de `dist\LightHouse` y crea `dist\LightHouse-<VERSION>-win64.zip` con `Compress-Archive`. `VERSION` sale de `lighthouse/__init__.py`.

**`--test` en el exe**
- Escribe el resultado al log y sale con 0/1.
- Si hay consola, también imprime.

**Python 3.14**
- Si PyInstaller falla con 3.14, prueba con `py -0p` si hay 3.13 o 3.12 y usa `-Python`.
- Si no hay alternativa, **detente y reporta**: no instales otro Python sin preguntar.

**`LEEME.txt`** (para el cliente, español sencillo; se incluye en el ZIP)
- Descomprimir, y antes: clic derecho al ZIP → Propiedades → **Desbloquear**.
- SmartScreen: *Más información → Ejecutar de todas formas* (el exe no está firmado).
- Permiso de micrófono para apps de escritorio, necesario para la UR12.
- **En la laptop DJ con rekordbox**: elegir `Salida (loopback) · <dispositivo que usa rekordbox>` y confirmar que el medidor se mueve. Dejar `Prioridad baja` activada.
- Respaldo con la UR12: entrada y canal; AGC automático vs fijo (perilla de booth = sensibilidad).
- Atajos actuales.
- Dónde están la config y los logs (`%APPDATA%\LightHouse`, `%LOCALAPPDATA%\LightHouse\logs`).
- El **checklist de show** de `fases/README.md`.

**`.gitignore`**: `.venv-build/`, `build/` y `dist/` (verifica que ya estén).

### No entra

- Instalador (Inno Setup/MSI), firma de código y autoactualización.
- Nuevas funciones de la app.

## Criterios de aceptación

1. `python -m lighthouse --test` pasa **sin scipy** dentro de `.venv-build`.
2. Fuera del venv, con scipy instalado, también pasa el check de comparación del filtro.
3. `.\build.ps1` termina sin errores y el exe pasa `--test` (código 0).
4. `dist\LightHouse\LightHouse.exe` abre con doble clic, lista dispositivos (entradas y loopback) y la luz reacciona al audio.
5. **Sin Python en el PATH**: lanzar el exe desde una consola con el PATH filtrado de rutas de Python funciona. Ideal: probar en otra PC sin Python; si no hay, documéntalo.
6. **Reportar**:
   - tamaño de `dist\LightHouse` (objetivo ≤ 80 MB);
   - tamaño del ZIP;
   - tiempo de arranque en frío hasta que aparece la ventana (objetivo < 3 s).
7. La reacción de la luz con el filtro nuevo se siente igual: los golpes coinciden con el self-check original (16/16 a 120 BPM y los hats sin filtro disparan).

## Verificación

```powershell
.\build.ps1
```
```powershell
$env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notmatch 'Python' }) -join ';'; Start-Process .\dist\LightHouse\LightHouse.exe
```
```powershell
"{0:N1} MB" -f ((Get-ChildItem .\dist\LightHouse -Recurse | Measure-Object Length -Sum).Sum / 1MB)
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`. No subas `dist/` ni `build/`.
- **Dependencias**: solo PyInstaller, y solo dentro de `.venv-build`. Nada global.
- **Alcance**: cambios mínimos. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`: F3 → ✅, fecha, tamaños y tiempo de arranque en la nota. Desde ahora, **toda fase debe correr `.\build.ps1` al final**: verifica que la sección de reglas lo diga.
2. Responde al usuario con:
   - qué cambió;
   - cómo construir y probar;
   - ruta del ZIP;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `build: ejecutable PyInstaller onedir y filtro sin scipy`) y la lista de archivos.

   **No hagas el commit.**
