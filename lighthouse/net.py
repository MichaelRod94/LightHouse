"""Red (F6): el emisor manda por UDP el Frame ya resuelto de una salida remota; el receptor (modo
--pantalla) guarda el último. Paquete de 14 bytes, sin timestamps ni OSC. Solo stdlib."""
import logging
import socket
import struct
import threading
import time

from .scene import BLACK, Frame

log = logging.getLogger(__name__)
PORT = 47800
AUTO = "Automático"
FMT = struct.Struct("<2sBIBBBBBBB")  # "LH", versión, seq, Lr Lg Lb, Rr Rg Rb, flags (bit0 = logo)
KEEPALIVE_S = 0.025       # al menos 40 Hz aunque nada cambie (un paquete perdido se repone en 25 ms)
REENUM_S = 5.0            # el cable o el hotspot pueden conectarse después
SIGNAL_S, FADE_S = 1.0, 0.5   # sin paquetes > 1 s: fundido de 0.5 s a solo el logo sobre negro
BACK_MAX, RESTART_S = 1000, 1.0
LOG_EVERY_S = 10.0


def pack(seq, f):
    return FMT.pack(b"LH", 1, seq & 0xFFFFFFFF, *f.left, *f.right, 1 if f.logo_visible else 0)


def unpack(data):
    """-> (seq, Frame) o None si no es un paquete nuestro."""
    if len(data) != FMT.size:
        return None
    magic, ver, seq, lr, lg, lb, rr, rg, rb, flags = FMT.unpack(data)
    if magic != b"LH" or ver != 1:
        return None
    return seq, Frame((lr, lg, lb), (rr, rg, rb), bool(flags & 1))


def valid_ip(s):
    try:
        socket.inet_aton(s)
        return s.count(".") == 3
    except OSError:
        return False


def local_ips():
    """IPv4 locales no loopback (getaddrinfo del nombre del equipo): incluye 169.254.* y las del hotspot."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({i[4][0] for i in infos if not i[4][0].startswith(("127.", "0."))})


class Sender:
    """Automático: un socket ligado a cada IPv4 local, con SO_BROADCAST, hacia 255.255.255.255:port
    (en Windows, ligar a la IP hace que el broadcast salga por esa interfaz). IP fija: unicast.
    send() solo desde el hilo Tk (App.fast), nunca bloquea; la enumeración corre en un hilo aparte."""

    def __init__(self, dest=AUTO, port=PORT):
        self.auto = dest == AUTO
        self.dest, self.port = dest, int(port)
        self.seq, self.last, self.t_sent, self.t_log = 0, None, -1e9, -1e9
        self.socks = {}  # ip -> socket (automático) | {"": socket} (IP fija); se reemplaza entero
        self.running, self.ev = True, threading.Event()
        if self.auto:
            threading.Thread(target=self.enum_loop, name="net-enum", daemon=True).start()
        else:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setblocking(False)
                self.socks = {"": s}
            except OSError as ex:
                log.warning("red: no se pudo crear el socket: %s", ex)

    def enum_loop(self):
        built = 0.0
        while self.running:
            ips = local_ips()
            socks = dict(self.socks)
            for ip in [i for i in socks if i not in ips]:
                socks.pop(ip).close()
            for ip in ips:
                if ip not in socks:
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                        s.bind((ip, 0))
                        s.setblocking(False)
                        socks[ip] = s
                    except OSError as ex:
                        log.warning("red: no se pudo usar %s: %s", ip, ex)
            if set(socks) != set(self.socks):
                log.info("red: enviando por %s", ", ".join(sorted(socks)) or "(sin red)")
            self.socks = socks
            built = time.monotonic()
            self.ev.wait(REENUM_S)  # un error de envío despierta antes, pero no más de 1 vez por segundo
            self.ev.clear()
            if self.running:
                time.sleep(max(0.0, 1.0 - (time.monotonic() - built)))

    def status(self):
        if not self.auto:
            return f"Enviando a {self.dest}:{self.port}" if self.socks else "sin red"
        return "Enviando por: " + ", ".join(sorted(self.socks)) if self.socks else "sin red"

    def send(self, f, now):
        """Manda f si cambió o si pasaron KEEPALIVE_S. Los errores de red se ignoran (log ocasional)."""
        if f == self.last and now - self.t_sent < KEEPALIVE_S:
            return
        self.last, self.t_sent = f, now
        data = pack(self.seq, f)
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        addr = ("255.255.255.255" if self.auto else self.dest, self.port)
        for ip, s in list(self.socks.items()):
            try:
                s.sendto(data, addr)
            except BlockingIOError:
                pass  # buffer lleno un instante: el siguiente keepalive lo repone
            except OSError as ex:
                if now - self.t_log >= LOG_EVERY_S:
                    self.t_log = now
                    log.warning("red: sendto por %s falló: %s", ip or addr[0], ex)
                if self.auto:  # red caída o IP que ya no existe: se re-enumera
                    self.socks = {k: v for k, v in self.socks.items() if k != ip}
                    s.close()
                    self.ev.set()

    def close(self):
        self.running = False
        self.ev.set()
        for s in list(self.socks.values()):
            s.close()
        self.socks = {}


class SeqFilter:
    """Acepta el paquete si es más nuevo (aritmética módulo 2^32). Un seq que retrocede > BACK_MAX
    durante > RESTART_S es un emisor reiniciado; tras > RESTART_S sin aceptar nada, se acepta cualquiera."""

    def __init__(self):
        self.last = None
        self.t_ok = self.t_back = None

    def accept(self, seq, now):
        if self.last is not None and now - self.t_ok <= RESTART_S:
            d = (seq - self.last) & 0xFFFFFFFF
            if d == 0:
                return False
            if d >= 0x80000000:  # viejo o reordenado
                if 0x100000000 - d <= BACK_MAX:
                    return False
                if self.t_back is None:
                    self.t_back = now
                if now - self.t_back <= RESTART_S:
                    return False
        self.last, self.t_ok, self.t_back = seq, now, None
        return True


class Receiver:
    """Escucha UDP en host:port (hilo daemon) y guarda el último frame bajo lock."""

    def __init__(self, port=PORT, host="0.0.0.0"):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((host, int(port)))
        except OSError:
            self.sock.close()
            raise
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.lock, self.filt = threading.Lock(), SeqFilter()
        self.fr, self.rx = Frame(BLACK, BLACK, True), None  # rx = perf_counter del último frame aceptado
        self.running = True
        threading.Thread(target=self.run, name="net-rx", daemon=True).start()

    def run(self):
        while self.running:
            try:
                data = self.sock.recv(64)
            except socket.timeout:
                continue
            except OSError:
                if self.running:
                    time.sleep(0.05)
                continue
            p = unpack(data)
            if p:
                now = time.perf_counter()
                with self.lock:
                    if self.filt.accept(p[0], now):
                        self.fr, self.rx = p[1], now

    def signal(self, now):
        with self.lock:
            return self.rx is not None and now - self.rx <= SIGNAL_S

    def frame(self, now):
        """Frame a pintar. Sin paquetes > SIGNAL_S: la luz se apaga en FADE_S y queda solo el logo sobre
        negro (Frame(BLACK, BLACK, True)); si no hay logo, el Output lo pinta como negro."""
        with self.lock:
            f, rx = self.fr, self.rx
        if rx is None:
            return Frame(BLACK, BLACK, True)
        late = now - rx - SIGNAL_S
        if late <= 0:
            return f
        k = max(1.0 - late / FADE_S, 0.0)
        sc = lambda c: tuple(round(x * k) for x in c)
        return Frame(sc(f.left), sc(f.right), True)

    def close(self):
        self.running = False
        self.sock.close()
