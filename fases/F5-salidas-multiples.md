# Fase F5: Salidas múltiples, pantalla completa sin bordes, logo y calibración

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior: Windows (ctypes/Win32, multi-monitor, DPI) y Tkinter. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** es una app de escritorio Python para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz.

Hoy hay **una sola ventana Luz**. Paquete `lighthouse/`:
- `engine.py`, con `sample(delay_s)`.
- `scene.py`, con `compose(snap, scene, cfg) -> Frame(left, right, logo_visible)` y los 15 looks del cliente.
- `win32.py` (ctypes).
- `ui.py`, `audio.py`, `config.py`, `selftest.py` y `__main__.py`.
- `build.ps1` genera el exe.

**Producción del cliente** (topología decidida):
- LightHouse corre en la **laptop DJ** junto a rekordbox y maneja las **dos pantallas chicas**: dos salidas de video, o una duplicada con splitter.
- La **TV de 43"** de cara al público la muestra otra laptop por red. Eso es F6 y reutilizará lo de esta fase: config por salida, logo y regla `unirse_a_looks`.
  - Si la laptop DJ tuviera una salida libre y la TV estuviera cerca, la TV también puede ser una **salida local** con logo.
- **Cada TV tiene distinto retraso**: hace falta un retardo por salida.

## Lee primero

1. `fases/README.md`: secciones *Topología decidida*, *Arquitectura → Latencia*, *Decisiones de diseño → Salidas* y *Estado*. **Respeta lo decidido.**
2. `lighthouse/ui.py` (ventana Luz actual y loop de render), `lighthouse/scene.py`, `lighthouse/engine.py` (`sample`), `lighthouse/win32.py`, `lighthouse/config.py` y `lighthouse/__main__.py`.

## Precondiciones

- `fases/README.md` marca **F4 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.
- Ejecuta `win32` o un script rápido para saber **cuántos monitores** hay en esta máquina. Si solo hay uno, las pruebas multi-monitor se documentan como pendientes.

## Objetivo

1. **N salidas** (hasta 4), cada una asignable a un monitor, en **pantalla completa sin bordes** que cubra exactamente el display, o en ventana para montaje.
2. Por salida: master, retardo, contenido (luz / luz + logo) y cuándo se une a los looks.
3. Detalles de show: DPI, cursor oculto, pantalla que no se duerme, identificar monitores.
4. Modo de calibración de retardo.

## Alcance

### Entra

**`win32.py`**
- `set_dpi_aware()`: `shcore.SetProcessDpiAwareness(2)`. Se llama en `__main__` **antes** de crear `Tk()`.
- `monitors() -> list[Monitor(device, x, y, w, h, primary)]`, con `EnumDisplayMonitors` + `GetMonitorInfoW` (`MONITORINFOEXW`, para el nombre `\\.\DISPLAYn`). Tk solo ve el primario.
- `keep_awake(on)`: `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)` = `0x80000003` al arrancar; `0x80000000` al salir.
- `window_rect(hwnd)` con `GetWindowRect`, para verificar.

**Nuevo `outputs.py`**: clase `Output`, un `Toplevel` por salida.
- **Pantalla completa**: `overrideredirect(True)` + `geometry(f"{w}x{h}{x:+d}{y:+d}")`.
  - Con coordenadas negativas el formato correcto es `+-2560+-360`. `-2560-360` lo coloca mal (medido).
  - **No usar** `-fullscreen`.
  - Opcional, si el rectángulo no queda exacto: `SetWindowPos(HWND_TOPMOST, …, SWP_NOACTIVATE)`.
- **Modo ventana**: ventana normal con título, para arrastrar y montar.
- `cursor="none"` sobre la salida.
- `Canvas` con dos mitades (lo que hoy hace la ventana Luz), más un `image` para el logo.
- `render(frame)`: solo actualiza lo que cambió.

**Config por salida**

| Campo | Valores |
|---|---|
| `nombre` | texto |
| `monitor` | `device` + rectángulo; si el monitor ya no existe → primario, con aviso |
| `pantalla_completa` | bool |
| `master` | 0–100 % |
| `retardo_extra_ms` | 0–200; se pasa a `engine.sample(delay_s)` |
| `contenido` | `Luz` / `Luz + logo` |
| `logo` | ruta a PNG |
| `unirse_a_looks` | `siempre` / `excepto en 1` / `nunca` |

- **Regla de `unirse_a_looks`**:
  - Si la salida **no** está unida al look actual (`nunca`, o `excepto en 1` estando en el look 1), muestra su contenido propio: luz base (color del look 1) × `out` × master, más el logo si aplica.
  - Si está unida, muestra el `Frame` del look y **oculta el logo**.
  - Blackout y bump afectan a **todas** las salidas.
- Caso del cliente:
  - Pantallas chicas: `siempre`.
  - TV grande (remota en F6, o local si se conecta directo): `excepto en 1` + logo + master 30 %.

**Logo**
- PNG con `tk.PhotoImage`, centrado, escalado con el mayor factor entero de `zoom`/`subsample` que quepa (~70 % del lado menor).
- Sin Pillow: `# ponytail:` escala entera; si se ve mal, preparar el PNG al tamaño de la pantalla.

**UI: panel `Salidas`** en la ventana Control
- Lista de salidas con **Agregar** / **Quitar** (mínimo 1, máximo 4).
- Por salida, todos los campos de la tabla anterior + botón **Pantalla completa / Ventana**.
- **`Identificar`**: durante 3 s cada salida muestra en grande `Salida N · \\.\DISPLAYn · 1920×1080`.
- **`Calibrar retardo`**:
  - Cambia temporalmente a blanco, piso 0, decay 50 ms y modo Pulso.
  - Muestra el procedimiento: *"Pon un track con kick claro. Graba con el celular en cámara lenta (240 fps) bocina + pantallas. Cuenta cuadros entre el golpe audible y el destello: 1 cuadro ≈ 4 ms. Ajusta el offset global y el retardo de cada salida hasta alinear."*
  - **Salir** restaura los valores anteriores.

**Migración**
- La ventana Luz única pasa a ser la **Salida 1**, en modo ventana, con su geometría guardada.
- `version` de config +1.

**Rendimiento**
- El loop rápido (`after(1)`) compone y pinta **todas** las salidas.
- `compose` se llama una vez por salida con su propio `sample(delay)`.

**Self-check**
1. **Regla de unirse**: en look 2, una salida `excepto en 1` muestra rojo y `logo_visible=False`; en look 1 muestra luz base con `logo_visible=True`.
2. **Retardo extra por salida**: `sample(0.05)` va 5 bloques atrás.

### No entra

- Red / pantalla remota (F6).
- Overlay y gamepad (descartados por el cliente).
- Video dentro de LightHouse.
- Pillow u otras librerías de imagen.

## Criterios de aceptación

1. Self-check completo pasa.
2. **Con 2+ monitores**: cada salida en pantalla completa cubre **exactamente** su monitor (`GetWindowRect` == rectángulo del monitor; verifícalo con un script). Sin bordes ni barra de tareas visibles, y el cursor no se ve.
3. `powercfg /requests` (consola de administrador si hace falta) lista LightHouse bajo DISPLAY mientras corre. Al cerrar, desaparece.
4. `Identificar` etiqueta bien cada monitor.
5. Con el look 1, la salida "pantalla grande" muestra el logo con su master. Con 2 o Q se une y oculta el logo. Blackout apaga todo.
6. Al reiniciar, las salidas vuelven a sus monitores. Con un monitor desconectado, esa salida cae al primario con aviso.
7. CPU < 5 % de un núcleo con 3 salidas a pantalla completa y audio entrando. Reporta el número.
8. `.\build.ps1` pasa y el exe hace todo lo anterior.
9. **DPI mixto** (laptop al 125–150 % + monitor al 100 %): si no puedes probarlo, documéntalo como pendiente en la nota de estado.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
powercfg /requests
```
```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva. Win32 solo por `ctypes`, dentro de `win32.py`.
- **Alcance**: cambios mínimos. No adelantes F6. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`: F5 → ✅, fecha, nota con la CPU medida y los pendientes (DPI mixto, número de monitores probados).
2. Responde al usuario con:
   - qué cambió;
   - cómo montar las salidas del cliente;
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(salidas): multiventana por monitor, pantalla completa sin bordes, logo y calibración`) y la lista de archivos.

   **No hagas el commit.**
