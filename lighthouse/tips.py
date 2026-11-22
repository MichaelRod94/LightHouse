"""Tooltips de la ventana Control: catálogo de textos (TIPS), títulos con la tecla real, colocación pura
(place) y una sola ventana compartida (Tooltip). Sin sondeo: solo un after de un disparo, cancelable,
mientras el puntero espera sobre un control (fases/diseno-ui.md §5)."""
import logging
import re
import time

from . import outputs, theme, win32
from .scene import LOOKS

log = logging.getLogger(__name__)

DX, DY, MARGIN, GAP = 14, 20, 8, 4  # px físicos: desplazamiento del puntero, margen al borde, hueco bajo la ventana
MAX_LEN = 200

# tarjetas con "Avanzado" (los mismos ids que ui.ADV_KEYS)
ADV_CARDS = ("respuesta", "luz", "estrobos", "teclado", "fuente", "ganancia", "filtro", "golpe", "tempo",
             "tranquilo", "salida_sel")
SOLID = {"2": "rojo", "3": "azul", "4": "morado", "5": "verde", "6": "amarillo"}
SPLIT = {"E": "rojo", "R": "morado", "T": "verde", "Y": "azul"}

# {accion} se cambia por la tecla real de esa acción (text()); así el texto sigue bien si cambian las teclas
TIPS = {
    # barra de looks
    "look.1": 'Luz blanca que sigue la música (o el color que elijas en "Color del look 1"). Es el look de '
              'inicio; en él la TV grande muestra su logo.',
    **{f"look.{k}": f"Todo en {c}, siguiendo cada golpe. Queda activo hasta que elijas otro look."
       for k, c in SOLID.items()},
    "look.7": "Arcoíris: cambia de color en cada golpe, en orden. Úsalo para subir la energía.",
    "look.Q": "Estrobo blanco y rojo: alterna en cada golpe y se apaga a negro cuando el golpe deja de sonar. "
              "Para los momentos fuertes.",
    "look.W": "Estrobo blanco y morado: alterna en cada golpe y se apaga a negro cuando el golpe deja de sonar.",
    **{f"look.{k}": f"Pantalla partida: una mitad en {c} y la otra en negro. Se intercambian en cada golpe."
       for k, c in SPLIT.items()},
    "look.U": "Morado que sube 4 segundos y baja 4 segundos, sin seguir la música. Para entradas, pausas o charla.",
    "look.Z": "Negro total: no responde a la música. Mantén {bump} para dar un destello a mano. Si solo quieres "
              "apagar un momento y volver al mismo look, usa Blackout ({blackout}).",
    # franja En vivo
    "vivo.punto": "Se enciende con cada golpe que LightHouse detecta. Si no parpadea con la música, revisa la "
                  "Fuente de audio o sube la Sensibilidad.",
    "vivo.medidor": "Barra de arriba: cuánto grave entra. Barra de abajo: la subida de cada golpe. Línea "
                    "vertical: lo que debe superar para contar como golpe.",
    "vivo.bpm": 'La velocidad de la música en golpes por minuto (BPM), según la detecta LightHouse. "--" '
                "significa que todavía no la sabe.",
    "vivo.look": "El look que se está mostrando. Cámbialo con su tecla o con un clic en la barra de arriba.",
    "vivo.estado": "Lo que hace la luz ahora: sigue los golpes (Pulso), está en calma (Tranquilo), Manual, "
                   "Blackout o Bump.",
    "vivo.previa": "Lo que está mostrando la Salida 1 en este momento, en pequeño.",
    "vivo.teclas": 'Dice si tus teclas llegan a LightHouse. "En otra ventana": las recibe otro programa; haz '
                   'clic aquí para recuperarlas. "En pausa": estás escribiendo; pulsa Enter para terminar.',
    "vivo.sin_senal": "No llega sonido desde hace más de 3 segundos. Revisa que suene música y que la Fuente "
                      "de audio sea la correcta.",
    "vivo.satura": "El sonido entra demasiado fuerte. Baja el volumen de entrada o la perilla del mezclador.",
    "vivo.audio": "Aviso del audio: LightHouse no está escuchando bien el dispositivo o se está reconectando. "
                  "Si no se arregla solo, abre la pestaña Audio y pulsa Reconectar.",
    "vivo.red": 'Estado del envío a la TV remota. "Sin red" significa que la otra laptop no está conectada.',
    "vivo.avisos": "Problemas de alguna salida: monitor desconectado o logo que no se pudo abrir.",
    "modo.selector": "Cómo reacciona la luz. Auto sigue los golpes y se calma sola; Pulso siempre sigue los "
                     "golpes; Tranquilo respira suave; Manual deja un brillo fijo.",
    "modo.auto": "La luz sigue los golpes y, si la música se calma, pasa sola a una respiración suave. Úsalo "
                 "casi siempre.",
    "modo.pulso": "Siempre sigue los golpes, aunque la música esté tranquila.",
    "modo.tranquilo": "Respiración suave que no marca los golpes. Para ambiente o mientras hablas.",
    "modo.manual": 'Brillo fijo, sin seguir la música. Lo ajustas con "Brillo en modo Manual".',
    "blackout": "Apaga todas las pantallas al instante. Otro clic (o {blackout}) las vuelve a encender en el "
                "mismo look.",
    "bump": "Mientras lo mantienes presionado, todas las pantallas se encienden a tope con el color del look. "
            "Al soltar, todo sigue como estaba.",
    "vista.selector": "Tamaño de esta ventana. Automática se adapta al espacio; Compacta ahorra sitio; Mini deja "
                      "solo los looks, la señal y el Blackout. Con {mini} entras y sales de Mini.",
    "vista.fijar": "Mantiene esta ventana por encima de rekordbox y de todo lo demás. Solo actúa en la vista Mini.",
    "vista.ampliar": "Vuelve a la ventana grande con todos los ajustes.",
    "vista.sin_foco": "En la vista Mini, un clic en un look o en Blackout no le quita el teclado al otro "
                      "programa (por ejemplo rekordbox). Es experimental: si falla, desactívalo.",
    # pestañas y tarjetas
    "tab.show": "Lo que se toca durante la fiesta: respuesta, brillo, color y teclas.",
    "tab.audio": "De dónde escucha LightHouse y cómo detecta los golpes. Se ajusta una vez, antes de empezar.",
    "tab.salidas": "Las pantallas que funcionan como luces: en qué monitor va cada una y qué muestra.",
    "tab.ayuda": "Lista de teclas, tutorial y opciones de ayuda.",
    **{f"avanzado.{c}": "Muestra u oculta los ajustes finos de este grupo. Lo normal es no tocarlos. Un punto "
                        "indica que alguno fue cambiado." for c in ADV_CARDS},
    # respuesta
    "resp.preset": "Normal: equilibrado. Muy reactivo: destellos más cortos y seguidos, para música rápida. "
                   "Mueve varios ajustes a la vez; luego puedes afinar.",
    "golpe.sens": "Qué tan fácil se enciende la luz. Súbela si se pierden golpes; bájala si destella con "
                  "cualquier sonido.",
    "resp.limite": "Impide destellos demasiado seguidos, que pueden provocar crisis a personas con epilepsia "
                   "fotosensible. Déjalo activo siempre que haya público.",
    "resp.limite_hz": "Cuántos destellos por segundo se permiten como mucho. 6 deja pasar ritmos rápidos sin "
                      "llegar a ser peligroso.",
    # luz
    "luz.master": "Brillo máximo de todas las pantallas. Bájalo si deslumbra.",
    "luz.decay": "Cuánto tarda en apagarse la luz después de cada golpe. Corto = golpes secos; largo = luz más "
                 "suave.",
    "luz.sinc_preset": "Compensa el retraso típico de tu salida de sonido para que luz y sonido coincidan. "
                       "Elige cómo está conectado el sonido.",
    "luz.offset": 'Positivo: la luz llega más tarde. Negativo: se adelanta (solo funciona "Al ritmo" y con un '
                  "ritmo estable). Ajústalo hasta que luz y golpe coincidan.",
    "luz.piso": "Brillo que queda entre un golpe y otro. En 0 la pantalla queda negra entre golpes.",
    "luz.gamma": "Cómo se reparte el brillo: valores altos dejan los golpes suaves más oscuros y dan más "
                 "contraste.",
    "luz.manual": "El brillo fijo que se usa cuando el modo es Manual ({manual}).",
    # color del look 1
    "color.modo": "Color del look 1: blanco puro, un blanco cálido o frío, o una paleta que cambia en cada "
                  "destello.",
    "color.kelvin": 'Tono del blanco: valores bajos son cálidos (ámbar), valores altos son fríos (azulados). '
                    'Solo con "Temperatura".',
    "color.paleta": 'Los colores que se van turnando, uno por destello. Solo con "Paleta".',
    "color.mas": "Agrega un color a la paleta.",
    "color.menos": "Quita el último color de la paleta.",
    # estrobos
    "estrobo.cierre": "Valores altos apagan el color en cuanto el golpe empieza a bajar (más seco); valores "
                      "bajos lo dejan encendido más tiempo.",
    "estrobo.min": "Lo mínimo que dura encendido cada destello de estrobo, para que se alcance a ver.",
    # teclado
    "teclas.globales": "Las teclas funcionan aunque otro programa esté al frente. Cuidado: esas mismas teclas "
                       "también le llegan a rekordbox.",
    "teclas.tab": "Permite moverte por los controles con Tab y las flechas. Mientras un control tiene el foco, "
                  "las teclas de looks quedan en pausa; Esc las devuelve.",
    # fuente de audio
    "audio.dispositivo": 'De dónde escucha LightHouse. Con rekordbox en esta laptop elige "Salida (loopback) · '
                         '…" con el mismo dispositivo que usa rekordbox.',
    "audio.canal": 'Qué canal de la entrada se escucha. "Mezcla" usa todos; elige un canal si conectaste un '
                   "solo cable.",
    "audio.reconectar": "Vuelve a buscar y abrir el dispositivo de audio. Úsalo si conectaste algo nuevo o el "
                        "medidor dejó de moverse.",
    "audio.estado": "Datos del dispositivo abierto o el último error de audio.",
    "audio.prioridad": "LightHouse cede el procesador a los demás programas para que el sonido nunca se corte. "
                       "Déjalo activo en la laptop del DJ.",
    # nivel de entrada
    "nivel.auto": "LightHouse ajusta solo el volumen de entrada. Es lo normal cuando escucha lo que suena en "
                  "esta laptop.",
    "nivel.fijo": "El nivel no se corrige: la perilla de tu mezclador decide cuánta luz hay. Para entradas por "
                  "cable.",
    "nivel.ref": 'Con nivel Fijo: el volumen de entrada que cuenta como "a tope". Bájalo si la luz se queda '
                 "corta.",
    # qué escucha
    "filtro.preset": 'Qué parte del sonido cuenta como golpe. "Kick" sigue el bombo; "Completo" escucha todo, '
                     "incluidas voces y aplausos.",
    "filtro.corte": "Límite de graves que se escuchan. Bajo = solo el bombo más profundo; alto = también bajos "
                    "y toms.",
    # golpe
    "golpe.pausa": "Tiempo mínimo entre dos golpes seguidos. Súbelo si un solo golpe enciende la luz dos veces.",
    "golpe.compuerta": "El sonido más bajo que este nivel se trata como silencio. Súbelo si la luz reacciona "
                       "al ruido de fondo.",
    "golpe.fuerza": "Activo: un golpe suave da menos luz que uno fuerte. Apagado: todos los golpes encienden "
                    "igual.",
    # ritmo
    "tempo.kick": "La luz destella solo cuando suena un golpe. Si la música se queda sin bombo, la luz se "
                  "detiene.",
    "tempo.ritmo": "La luz sigue marcando el ritmo aunque el bombo desaparezca un momento.",
    "tempo.fuente": 'De dónde sale la velocidad de la música. "Detectado": la calcula LightHouse. "Manual / '
                    'Tap": la marcas tú.',
    "tempo.tap": "Púlsalo al ritmo de la música, 3 o más veces, para fijar la velocidad a mano.",
    "tempo.bpm_manual": 'La velocidad, en golpes por minuto, que se usa cuando eliges "Manual / Tap".',
    "tempo.divisor": "1/1: un destello por golpe. 1/2: uno cada dos golpes. 1/4: uno cada cuatro.",
    # calma
    "calma.preset": "Cómo se ve la luz cuando la música está tranquila: respiración suave, tenue fija o casi "
                    "apagada.",
    "calma.espera": "Segundos sin golpes antes de pasar a calma (en modo Auto).",
    "calma.suavidad": "Qué tan lento sube y baja la luz en calma.",
    "calma.base": "Brillo de fondo mientras la música está tranquila.",
    "calma.respira": "Cuánto sube la luz con el volumen de la música en calma. En 0 queda fija.",
    # salidas
    "salidas.lista": "Cada salida es una pantalla que funciona como luz. Haz clic en una para ver y cambiar sus "
                     "ajustes.",
    "salidas.agregar": "Crea otra salida en esta laptop (hasta 4). Aparece como ventana para que la arrastres a "
                       "su monitor.",
    "salidas.quitar": "Elimina la salida seleccionada. Siempre queda al menos una.",
    "salidas.tv": "Crea una salida que se envía por red a otra laptop con LightHouse en modo pantalla. Ya viene "
                  "lista para la TV grande con logo.",
    "salidas.identificar": "Durante 3 segundos cada salida muestra su número y su monitor, para saber cuál es "
                           "cuál.",
    "salidas.calibrar": "Abre una guía para alinear la luz con el sonido usando la cámara lenta del celular.",
    "sal.nombre": "El nombre de esta salida en la lista. Mientras escribes, las teclas de looks quedan en "
                  "pausa; Enter termina.",
    "sal.monitor": "En qué monitor se muestra esta salida cuando está en pantalla completa.",
    "sal.completa": "Cambia entre cubrir todo el monitor, sin bordes, y una ventana normal para acomodarla. "
                    "También con doble clic sobre la salida; Esc vuelve a ventana.",
    "sal.destino": '"Automático" encuentra sola a la otra laptop. Escribe una dirección IP solo si quieres '
                   "enviar a una en concreto.",
    "sal.puerto": "Número de puerto de red. Debe ser el mismo en las dos laptops; lo normal es no tocarlo.",
    "sal.master": "Brillo solo de esta pantalla. Úsalo para que una TV grande brille menos que las demás.",
    "sal.retardo": "Retrasa solo esta salida. Sirve para igualar pantallas que responden más rápido que otras.",
    "sal.contenido": '"Luz": solo color. "Luz + logo": además muestra tu logo cuando esta salida no está '
                     "siguiendo un look.",
    "sal.logo": "Ruta de la imagen del logo. Mejor un PNG ya del tamaño de la pantalla.",
    "sal.logo_buscar": "Abre una ventana para elegir el archivo del logo.",
    "sal.unirse": "Cuándo esta salida muestra el look activo: siempre, en todos menos el look 1 (ahí enseña su "
                  "logo), o nunca.",
    "calib.salir": "Cierra la guía y devuelve el look y los ajustes que tenías antes de calibrar.",
    # ayuda
    "ayuda.tips": "Muestra explicaciones como esta al dejar el ratón sobre un control.",
    "ayuda.carpeta": "Abre la carpeta con el archivo que hay que enviar si algo falla.",
    "ayuda.intro": "Muestra la animación corta al abrir LightHouse. La luz y el sonido arrancan igual con o sin ella.",
    "ayuda.tutorial": "Abre un recorrido de 2 minutos que te enseña lo básico. Puedes repetirlo las veces que "
                      "quieras y salir con Esc.",
    # tutorial (banda de primer arranque y globo)
    "tut.ver": "Empieza el recorrido de 2 minutos. La luz sigue funcionando mientras tanto.",
    "tut.ahora_no": "Cierra este aviso por ahora. El recorrido siempre está en la pestaña Ayuda.",
    "tut.no_preguntar": 'Marca la casilla y pulsa "Ahora no" para que este aviso no vuelva a salir al abrir '
                        "LightHouse.",
    "tut.atras": "Vuelve al paso anterior.",
    "tut.siguiente": "Pasa al paso siguiente. También con Enter. En el último paso termina el recorrido.",
    "tut.omitir": "Cierra el recorrido ahora mismo. No cambia ningún ajuste. También con Esc.",
}

# primera línea (negrita): la etiqueta visible del control. Los looks y los modos se arman en title()
LABELS = {
    "vivo.punto": "Golpe", "vivo.medidor": "Medidor", "vivo.bpm": "BPM", "vivo.look": "Look activo",
    "vivo.estado": "Estado", "vivo.previa": "Vista previa", "vivo.teclas": "Teclas", "vivo.sin_senal": "SIN SEÑAL",
    "vivo.satura": "SATURA", "vivo.audio": "Audio", "vivo.red": "TV remota", "vivo.avisos": "Avisos",
    "modo.selector": "Modo", "blackout": "Blackout", "bump": "Bump (mantener)", "vista.selector": "Vista",
    "vista.fijar": "Siempre encima", "vista.ampliar": "Ampliar", "vista.sin_foco": "No quitar el teclado",
    "tab.show": "Show", "tab.audio": "Audio", "tab.salidas": "Salidas", "tab.ayuda": "Ayuda",
    "resp.preset": "Respuesta", "golpe.sens": "Sensibilidad", "resp.limite": "Limitar destellos",
    "resp.limite_hz": "Máx. destellos/s", "luz.master": "Brillo general (%)",
    "luz.decay": "Duración del destello (ms)", "luz.sinc_preset": "Sincronía",
    "luz.offset": "Adelantar / atrasar la luz (ms)", "luz.piso": "Luz mínima entre golpes (%)",
    "luz.gamma": "Curva de brillo", "luz.manual": "Brillo en modo Manual (%)", "color.modo": "Tipo de color",
    "color.kelvin": "Temperatura (K)", "color.paleta": "Paleta", "color.mas": "Agregar color",
    "color.menos": "Quitar color", "estrobo.cierre": "Cuándo se apaga el estrobo",
    "estrobo.min": "Duración mínima (ms)", "teclas.globales": "Teclas siempre activas (globales)",
    "teclas.tab": "Navegar con Tab", "audio.dispositivo": "Dispositivo", "audio.canal": "Canal",
    "audio.reconectar": "Reconectar", "audio.estado": "Estado", "audio.prioridad": "Dar prioridad a rekordbox",
    "nivel.auto": "Automático", "nivel.fijo": "Fijo (manda la perilla del mezclador)",
    "nivel.ref": "Nivel de referencia (dB)", "filtro.preset": "Qué escucha",
    "filtro.corte": "Hasta qué frecuencia (Hz)", "golpe.pausa": "Pausa mínima entre golpes (ms)",
    "golpe.compuerta": "Ignorar sonido por debajo de (dB)", "golpe.fuerza": "Golpes fuertes brillan más",
    "tempo.kick": "En cada golpe", "tempo.ritmo": "Al ritmo", "tempo.fuente": "BPM",
    "tempo.tap": "Marcar el ritmo", "tempo.bpm_manual": "BPM manual", "tempo.divisor": "Un destello cada",
    "calma.preset": "Calma", "calma.espera": "Esperar sin golpes (s)", "calma.suavidad": "Suavidad del cambio (s)",
    "calma.base": "Brillo en calma (%)", "calma.respira": "Cuánto respira (%)",
    "salidas.lista": "Lista de salidas", "salidas.agregar": "Agregar", "salidas.quitar": "Quitar",
    "salidas.tv": "Agregar TV remota", "salidas.identificar": "Identificar pantallas",
    "salidas.calibrar": "Calibrar sincronía", "sal.nombre": "Nombre", "sal.monitor": "Monitor",
    "sal.completa": "Pantalla completa / Ventana", "sal.destino": "Destino", "sal.puerto": "Puerto",
    "sal.master": "Brillo de esta salida (%)", "sal.retardo": "Retraso de esta pantalla (ms)",
    "sal.contenido": "Contenido", "sal.logo": "Logo (PNG)", "sal.logo_buscar": "Buscar logo",
    "sal.unirse": "Seguir los looks", "calib.salir": "Salir", "ayuda.tips": "Mostrar ayudas",
    "ayuda.carpeta": "Abrir carpeta de registros", "ayuda.intro": "Animación de entrada", "ayuda.tutorial": "Ver tutorial", "tut.ver": "Ver tutorial",
    "tut.ahora_no": "Ahora no", "tut.no_preguntar": "No volver a preguntar", "tut.atras": "Atrás",
    "tut.siguiente": "Siguiente", "tut.omitir": "Omitir tutorial",
    **{f"avanzado.{c}": "Avanzado" for c in ADV_CARDS},
}
MODE_ACTIONS = {"modo.auto": ("Modo Auto", "auto"), "modo.pulso": ("Modo Pulso", "pulso"),
                "modo.tranquilo": ("Modo Tranquilo", "tranquilo"), "modo.manual": ("Modo Manual", "manual")}
# controles que tienen tecla propia: id -> acciones del mapa de teclas de la app
KEYED = {"blackout": ("blackout",), "bump": ("bump",), "tempo.tap": ("tap",), "vista.ampliar": ("mini",),
         "vista.selector": ("mini",), "golpe.sens": ("sens+", "sens-"),
         **{k: (a,) for k, (_, a) in MODE_ACTIONS.items()}}


def key_text(app, action):
    """Tecla real de una acción en el mapa de la app ("Espacio", "F1"), o None si no tiene."""
    from .ui import key_label
    keys = app.keys.get(action)
    return key_label(keys[0]) if keys else None


def title(wid, app):
    """Primera línea del tooltip: etiqueta del control y su tecla real ("Blackout · Espacio",
    "Look 2 · Rojo · 2"). Si el usuario cambió las teclas en config.json, sale la suya."""
    if wid.startswith("look."):
        lid = wid[5:]
        name, key = LOOKS[lid][0], key_text(app, lid)
        head = f"Look {name}" if lid.isalpha() else f"Look {lid} · {name}"
        return f"{head} · {key}" if key else head
    head = MODE_ACTIONS[wid][0] if wid in MODE_ACTIONS else LABELS.get(wid, "")
    keys = [k for k in (key_text(app, a) for a in KEYED.get(wid, ())) if k]
    if wid == "vista.selector" and keys:  # la tecla de Mini no es la de la vista: se dice
        return f"{head} · {keys[0]} = Mini"
    return f"{head} · {' / '.join(keys)}" if head and keys else head


def text(wid, app=None):
    """Texto del tooltip con las {acciones} cambiadas por su tecla real (la de fábrica si no hay app)."""
    from .ui import KEYS, key_label

    def key(m):
        keys = (app.keys if app else KEYS).get(m[1])
        return key_label(keys[0]) if keys else m[0]
    return re.sub(r"\{([a-z]+)\}", key, TIPS[wid])


def overlap(a, b):
    """¿Se tocan los rectángulos (x, y, w, h)?"""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def place(px, py, w, h, mon, avoid=None):
    """Esquina (x, y) de un tooltip de w × h para un puntero en (px, py), dentro del monitor mon (x, y, w, h).
    Normal: DX a la derecha y DY debajo; si no cabe, voltea a la izquierda y/o arriba; último recurso, recorta
    con MARGIN px. Nunca deja el puntero dentro del tooltip. avoid = (x, y, w, h) de la ventana (Mini) o del
    control (Tab): el tooltip va debajo (o arriba) de ese rectángulo, alineado con px."""
    mx, my, mw, mh = mon.x, mon.y, mon.w, mon.h
    r, b = mx + mw, my + mh
    fit = lambda x, y: mx <= x and x + w <= r and my <= y and y + h <= b
    clamp = lambda v, lo, hi: max(min(v, hi), lo)
    cx = clamp(px, mx + MARGIN, r - w - MARGIN)
    if avoid:
        ax, ay, aw, ah = avoid
        for y in (ay + ah + GAP, ay - GAP - h):
            if fit(cx, y):
                return cx, y
    for y in (py + DY, py - DY - h):
        for x in (px + DX, px - DX - w):
            if fit(x, y):
                return x, y
    # último recurso: recortado con margen, pero por un solo eje para que el puntero quede fuera
    for y in (py + DY, py - DY - h):
        if my <= y and y + h <= b:
            return clamp(px + DX, mx + MARGIN, r - w - MARGIN), clamp(y, my + MARGIN, b - h - MARGIN)
    for x in (px + DX, px - DX - w):
        if mx <= x and x + w <= r:
            return clamp(x, mx + MARGIN, r - w - MARGIN), clamp(py + DY, my + MARGIN, b - h - MARGIN)
    return clamp(px + DX, mx + MARGIN, r - w - MARGIN), clamp(py + DY, my + MARGIN, b - h - MARGIN)


class Tooltip:
    """Una sola ventana compartida (Toplevel sin bordes, siempre encima, sin tomar el foco). Cero costo sin hover:
    no hay sondeo, solo el after del retardo, que se cancela al salir, hacer clic, teclear o cambiar el layout."""

    def __init__(self, app):
        self.app = app
        tk, root, P, S = app.tk, app.root, app.px, app.sp
        self.cur = None          # id del tooltip visible (None = oculto)
        self.t_hide = -1e9       # cuándo se ocultó el último tooltip visible (retardo corto si fue hace poco)
        self.bound = set()
        self.pointer = root.winfo_pointerxy  # los tests lo reemplazan; en uso, la posición real al mostrarlo
        win = self.win = tk.Toplevel(root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        theme.paint(win, bg="tooltip_border")
        box = tk.Frame(win, bd=0, highlightthickness=0)
        theme.paint(box, bg="tooltip_bg")
        box.pack(padx=P(1), pady=P(1))
        wrap = P(theme.tok("size.tip_max_w"))
        self.head = tk.Label(box, bd=0, justify="left", anchor="w", wraplength=wrap, padx=S("md"), pady=0)
        self.body = tk.Label(box, bd=0, justify="left", anchor="w", wraplength=wrap, padx=S("md"), pady=0)
        theme.paint(self.head, bg="tooltip_bg", fg="tooltip_fg", font="font.title")
        theme.paint(self.body, bg="tooltip_bg", fg="tooltip_fg", font="font.body")
        self.pad = S("md")
        win.update_idletasks()
        hwnd = int(win.wm_frame(), 16)
        if hwnd:
            win32.set_no_activate(hwnd, True)  # aparece sin quitarle el foco a nadie (ni a rekordbox)
        self.watch(root)
        self.attach_all()

    # --- enlaces
    def watch(self, win):
        """Ventana de la app (Control, Calibrar): cualquier tecla o perder el foco oculta el tooltip."""
        win.bind("<KeyPress>", self.hide, add="+")
        win.bind("<FocusOut>", self.hide, add="+")

    def attach_all(self):
        """Enlaza todo control registrado que aún no lo esté (también los de la ventana Calibrar)."""
        for w, wid in list(self.app.ids.items()):
            if w not in self.bound:
                self.bound.add(w)
                w.bind("<Enter>", lambda e, w=w, wid=wid: self.enter(w, wid), add="+")
                w.bind("<Leave>", lambda e, w=w: self.leave(w, e), add="+")
                w.bind("<ButtonPress>", self.hide, add="+")

    def leave(self, w, e):
        try:  # al pasar a un hijo del mismo control (la vista previa) sigue sobre él
            under = w.winfo_containing(e.x_root, e.y_root)
        except (self.app.tk.TclError, KeyError):
            under = None
        if under is None or not self.app.inside(under, w):
            self.hide()

    # --- mostrar y ocultar
    def on(self):
        return bool(self.app.tips_on.get()) and not self.app.intro_on  # durante la intro callan

    def enter(self, w, wid):
        """El puntero entró en el control: tras el retardo (corto si hace poco hubo otro tooltip), se muestra."""
        self.hide()
        if self.on():
            self.schedule(w, wid, False)

    def focus(self, w):
        """Con Navegar con Tab: el control que recibe el foco muestra su tooltip, debajo de él."""
        self.hide()
        wid = self.app.ids.get(w)
        if wid and self.on():
            self.schedule(w, wid, True)

    def schedule(self, w, wid, below):
        key = "motion.tip_delay_next" if time.monotonic() - self.t_hide < 1.0 or below else "motion.tip_delay"
        self.app.later("tip", theme.tok(key), lambda: self.show(w, wid, below))

    def show(self, w, wid, below=False):
        app = self.app
        try:
            if not (self.on() and w.winfo_exists()):
                return
            head = title(wid, app)
            self.head.configure(text=head)
            self.head.pack_forget()
            self.body.pack_forget()
            if head:
                self.head.pack(anchor="w", fill="x", pady=(self.pad, 0))
            self.body.configure(text=text(wid, app))
            self.body.pack(anchor="w", fill="x", pady=(self.pad // 2 if head else self.pad, self.pad))
            self.win.update_idletasks()
            tw, th = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
            px, py = self.pointer()
            avoid = None
            if app.draw is not None and app.draw.mode == "mini":  # ventana chica: el tooltip sale de ella
                avoid = win32.window_rect(int(app.root.wm_frame(), 16))
            elif below:
                px, py, aw, ah = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
                avoid = (px, py, aw, ah)
            mons = win32.monitors()
            mon = outputs.monitor_at(px, py, mons) or min(
                mons, key=lambda m: abs(px - m.x - m.w / 2) + abs(py - m.y - m.h / 2), default=None)
            if mon is None:
                return
            x, y = place(px, py, tw, th, mon, avoid)
            if avoid is None:  # un control alto (botón de look, lista): si lo tapa, va debajo (o arriba) de él
                box = (w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height())
                if overlap((x, y, tw, th), box):
                    x2, y2 = place(px + DX, py, tw, th, mon, box)
                    if not overlap((x2, y2, tw, th), box):
                        x, y = x2, y2
            self.win.geometry(f"+{x}+{y}")
            self.win.deiconify()
            self.cur = wid
        except app.tk.TclError:  # el control o la ventana se cerraron mientras tanto
            self.hide()

    def hide(self, _=None):
        job = self.app.jobs.pop("tip", None)
        if job:
            self.app.root.after_cancel(job)
        if self.cur is not None:
            self.win.withdraw()
            self.cur = None
            self.t_hide = time.monotonic()
