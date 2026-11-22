# Fase F6: Pantalla remota por red (laptop DJ → laptop de visuales → TV 43")

> **Prompt autocontenido.** Pégalo completo en una sesión **nueva** del asistente de código, abierta en `C:\Users\desarrollo 6\Desktop\CodeP\LightHouse`.

## Rol

Eres un desarrollador Python senior: Windows, sockets UDP y Tkinter. Implementas **solo esta fase**, con el cambio mínimo que cumpla los criterios.

## Proyecto

**LightHouse** es una app de escritorio Python para Windows. Escucha el audio de un set de DJ y convierte cada golpe en luz en varias salidas (ventanas sin bordes por monitor).
- Cada salida compone su imagen con `scene.compose(engine.sample(retardo), scene, cfg) -> Frame(left, right, logo_visible)`.
- Paquete `lighthouse/`: `engine.py`, `scene.py`, `outputs.py`, `win32.py`, `ui.py`, `audio.py`, `config.py`, `selftest.py` y `__main__.py`.
- `build.ps1` genera el exe.

**Topología del cliente** (decidida):
- La **laptop DJ** corre rekordbox + LightHouse (emisor):
  - capta el audio por loopback;
  - el DJ elige los looks con el teclado;
  - maneja las 2 pantallas chicas.
- La **laptop de visuales** corre LightHouse en modo **pantalla** (receptor, sin audio) y muestra por HDMI la **TV de 43"** de cara al público:
  - en el look 1 se ve su **logo** tranquilo;
  - al elegir otro look, se une en color con las chicas.
- **Objetivo del cliente**: menos cables y no usar el booth (queda para sus bocinas extra).

## Lee primero

1. `fases/README.md`: *Topología decidida*, *Arquitectura*, *Decisiones de diseño → Salidas* y *Estado*. **Respeta lo decidido.**
2. `lighthouse/outputs.py` (ventanas, logo, regla `unirse_a_looks`), `lighthouse/scene.py`, `lighthouse/ui.py`, `lighthouse/__main__.py` y `lighthouse/config.py`.

## Precondiciones

- `fases/README.md` marca **F5 ✅**. Si no, detente y avisa.
- `python -m lighthouse --test` pasa y `.\build.ps1` construye.
- `git status`.

## Diseño decidido

Validado por el arquitecto.

**Emisor → receptor**
- UDP con el **estado ya renderizado**: sin lógica duplicada en el receptor.
- Sin timestamps ni sincronía de reloj: el jitter en LAN o hotspot propio es menor a un frame.
- **Sin OSC.**

**Paquete** de 14 bytes:
```python
struct.pack("<2sBIBBBBBBB", b"LH", 1, seq, Lr, Lg, Lb, Rr, Rg, Rb, flags)
```
- `seq`: uint32 creciente.
- `flags`: bit0 = mostrar logo.

**Destino**
- **`Automático` (default, cero configuración)**: por cada IPv4 local que no sea `127.*` (obtenidas con `socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)`), un socket **ligado a esa IP** con `SO_BROADCAST` envía a `255.255.255.255:47800`.
  - En Windows, ligar a la IP local hace que el broadcast salga por esa interfaz. Funciona en cable Ethernet directo (direcciones `169.254.*` automáticas) y en hotspot.
  - Re-enumerar las IP cada 5 s: el cable o el hotspot pueden conectarse después.
- **`IP fija`** (opcional): unicast a la IP:puerto indicados.

**Envío**
- Al cambiar el frame, más un **keepalive a 50 Hz**.
- Sockets no bloqueantes, desde el loop rápido de la UI. **Nunca** desde el hilo de audio.
- Errores de `sendto` (red caída) → se ignoran con un log ocasional, sin spamear.

**Receptor**
- Escucha `0.0.0.0:47800` en un hilo daemon y guarda el último frame bajo lock.
- Descarta paquetes con `seq` menor que el último, considerando el desbordamiento de uint32.
- Si `seq` salta hacia atrás más de 1000 durante más de 1 s, acepta el nuevo emisor: el emisor se reinició.
- **Más de 1 s sin paquetes** → muestra **solo el logo sobre negro**, con un fundido de 0.5 s. **Nunca** texto en la TV del público. Si no hay logo, negro.

## Alcance

### Entra

**Nuevo `net.py`**: `Sender` (modos automático e IP fija) y `Receiver(port)`.

**Salida tipo `Remota`** en el panel Salidas (`outputs.py` / `ui.py`)
- Campos: destino (`Automático` / IP), puerto (default 47800) y los mismos campos por salida (master, retardo extra, `unirse_a_looks`, mostrar logo).
- Compone igual que una local; en vez de pintar, envía.
- Indicador en el panel: `Enviando por: 169.254.x.x, 192.168.x.x` / `sin red`.
- **Preset de salida "TV grande (remota)"**: `excepto en 1`, logo activado, master 30 %.

**Modo receptor**
```powershell
LightHouse.exe --pantalla [--puerto 47800] [--monitor N] [--logo ruta.png]
```
Equivalente: `python -m lighthouse --pantalla …`.
- Abre **una salida sin bordes** en el monitor indicado (default: el monitor externo si hay; si no, el primario), con cursor oculto y keep-awake (reusa `outputs.py` y `win32.py`).
- Pinta lo que llega. El logo es un archivo **local del receptor**.
- Recuerda su config (`monitor`, `logo`, `puerto`) en `config.json` bajo una llave `pantalla`, para que la próxima vez basten un doble clic y un acceso directo.
- Sin audio y sin panel de control.
- **Al arrancar** muestra 3 s en una esquina `LightHouse pantalla · IP …`. Después, nada de texto.
- `Esc` cierra, con confirmación.
- Crear un acceso directo de ejemplo es responsabilidad del `LEEME.txt` (explicar `--pantalla` en el campo *Destino* del acceso directo).

**Firewall**
- La primera vez Windows pregunta en el receptor: documentar en `LEEME.txt` que se debe permitir en **redes privadas**.
- Alternativa: `netsh advfirewall firewall add rule name="LightHouse" dir=in action=allow protocol=UDP localport=47800`.

**`LEEME.txt`** (sección "Dos laptops")

| Opción | Cómo |
|---|---|
| **A: cable** (recomendada) | Cable Ethernet entre las dos laptops (adaptador USB-C/USB 3.0 si no tienen puerto). Sin configurar IPs: Windows asigna `169.254.*` en ~30 s |
| **B: hotspot propio** | En la laptop de visuales, *Configuración → Red → Zona con cobertura inalámbrica móvil*, banda de 5 GHz si existe. La laptop DJ se conecta a esa red |

- **Nunca** usar el Wi-Fi del lugar.
- Orden de arranque: da igual. El receptor muestra el logo hasta que llega señal.

**Self-check**
1. Empaquetar/desempaquetar ida y vuelta.
2. Descarte de `seq` viejo, incluido el desbordamiento (`0xFFFFFFFF` → `0`), y aceptación de un emisor reiniciado.
3. Emisor (IP fija `127.0.0.1`) y receptor en un puerto efímero: el receptor obtiene el último frame enviado.
4. Timeout: sin paquetes > 1 s → el receptor reporta "sin señal" y su frame es logo sobre negro.

### No entra

- OSC, Ableton Link y MIDI.
- Cifrado o autenticación (red privada entre dos laptops).
- Audio por red.
- Más de un receptor configurado (el broadcast automático ya llega a varios si existieran).

## Criterios de aceptación

1. Self-check pasa.
2. **Misma máquina**: la app con una salida remota (`Automático`) y `python -m lighthouse --pantalla --monitor 2` en otra consola → el receptor muestra lo mismo que una salida local.
   - En el look 1 se ve el logo.
   - En el look 2 o Q se une en color.
   - Cerrar el emisor → en ~1 s queda solo el logo.
3. **Dos PCs** (si hay disponibles), por cable directo o hotspot: funciona **sin configurar IPs**, y sin desfase visible entre salida local y remota con el mismo retardo. Si hay celular con 240 fps, mídelo. Si no hay segunda PC, documéntalo como pendiente.
4. Con la red desconectada y reconectada, el envío se recupera solo en ≤ 5 s.
5. `.\build.ps1` pasa y `LightHouse.exe --pantalla` funciona desde el exe.

## Verificación

```powershell
python -m lighthouse --test; "exit=$LASTEXITCODE"
```
```powershell
python -m lighthouse --pantalla --monitor 2
```
```powershell
.\build.ps1
```

## Reglas

- **Shell**: solo PowerShell (5.1: sin `&&` ni `||`). Nada de bash.
- **Git**: no hagas `commit`, `push`, ramas, `stash` ni `reset`.
- **Dependencias**: ninguna nueva (stdlib `socket`, `struct` y `threading`).
- **Alcance**: cambios mínimos. Si algo del diseño es imposible, detente y explica alternativas.

## Al terminar

1. Actualiza `fases/README.md`: F6 → ✅, fecha y nota de una línea (indica si se probó con dos PCs).
2. Responde al usuario con:
   - qué cambió;
   - cómo montar las dos laptops (cable y hotspot);
   - qué no pudiste verificar;
   - **mensaje de commit sugerido** (p. ej. `feat(red): pantalla remota por UDP con descubrimiento automático`) y la lista de archivos.

   **No hagas el commit.**
