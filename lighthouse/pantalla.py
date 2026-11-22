"""Modo receptor (F6): python -m lighthouse --pantalla [--puerto N] [--monitor N] [--logo ruta.png]
Una salida sin bordes que pinta lo que llega por UDP; sin red muestra solo el logo sobre negro."""
import logging
import re
import time

from . import config, net, outputs, win32

log = logging.getLogger(__name__)
CONFIRM_S, HINT_S = 3.0, 3.0
DEFAULTS = {"monitor": "", "logo": "", "puerto": float(net.PORT)}


def parse(argv):
    """-> dict(puerto, monitor, logo) con None en lo que no se pidió; ValueError si el argumento es inválido."""
    out, it = dict(puerto=None, monitor=None, logo=None), iter(argv)
    for a in it:
        k = {"--puerto": "puerto", "--monitor": "monitor", "--logo": "logo"}.get(a)
        v = next(it, None)
        if k is None or v is None:
            raise ValueError(f"argumento no válido: {a}")
        out[k] = v
    for k in ("puerto", "monitor"):
        if out[k] is not None and not out[k].isdigit():
            raise ValueError(f"--{k} debe ser un número")
    return out


def pick_monitor(device, mons):
    """Monitor pedido/guardado si existe; si no, el externo (primer no principal) y, si no hay, el principal."""
    m = next((m for m in mons if m.device == device), None)
    return m or next((m for m in mons if not m.primary), None) or next((m for m in mons if m.primary), mons[0])


class Pantalla:
    def __init__(self, port, monitor, logo, host="0.0.0.0"):
        import tkinter as tk
        self.tk = tk
        self.root = root = tk.Tk()
        root.withdraw()
        self.on_change = lambda *a: None  # Output.on_change
        self.outputs_changed = self.on_change
        self.rx = net.Receiver(port, host)
        mons = win32.monitors()
        m = pick_monitor(monitor, mons)
        d = dict(outputs.default_output(1, mons), nombre="Pantalla", monitor=m.device,
                 monitor_rect=outputs.rect_str(m), pantalla_completa=True, contenido=outputs.LOGO, logo=logo)
        self.out = o = outputs.Output(self, d, mons)
        w = o.win
        w.bind("<Double-Button-1>", lambda e: "break")
        w.bind("<Escape>", lambda e: self.on_escape(time.perf_counter()))
        w.protocol("WM_DELETE_WINDOW", lambda: None)
        self.lbl = tk.Label(w, fg="#aaaaaa", bg="black", font=("Segoe UI", 12), padx=8, pady=4, cursor="none")
        self.hint = None
        self.esc_t = -1e9
        self.show(f"LightHouse pantalla · {', '.join(net.local_ips()) or 'sin red'} · puerto {self.rx.port}",
                  HINT_S)
        w.focus_force()
        config.save_key("pantalla", dict(monitor=m.device, logo=o.logo, puerto=float(self.rx.port)))
        log.info("pantalla: monitor %s, puerto %d, logo %r", m.device, self.rx.port, o.logo)
        self.tick()

    def show(self, text, secs):
        """Texto en la esquina inferior izquierda (solo al arrancar y al pedir cerrar)."""
        if self.hint:
            self.root.after_cancel(self.hint)
        self.lbl.configure(text=text)
        self.lbl.place(x=0, rely=1.0, anchor="sw")
        self.lbl.lift()
        self.hint = self.root.after(int(secs * 1000), lambda: (self.lbl.place_forget(), setattr(self, "hint", None)))

    def on_escape(self, now):
        """Esc pide confirmación (un texto de 3 s en la esquina); un segundo Esc dentro de ese tiempo cierra."""
        if now - self.esc_t <= CONFIRM_S:
            self.close()
        else:
            self.esc_t = now
            self.show("Esc otra vez para cerrar", CONFIRM_S)

    def tick(self):
        now = time.perf_counter()
        self.out.render(self.rx.frame(now), now)
        self.root.after(15, self.tick)

    def close(self):
        self.rx.close()
        self.root.destroy()


def main(argv, host="0.0.0.0"):
    """Devuelve el código de salida. La config (monitor, logo, puerto) se recuerda en config.json."""
    try:
        a = parse(argv)
    except ValueError as ex:
        print(f"LightHouse --pantalla: {ex}")
        return 2
    saved = config.load({"pantalla": dict(DEFAULTS)})["pantalla"]
    port = int(a["puerto"] if a["puerto"] is not None else saved["puerto"])
    monitor = rf"\.\DISPLAY{a['monitor']}" if a["monitor"] is not None else saved["monitor"]
    logo = a["logo"] if a["logo"] is not None else saved["logo"]
    win32.set_dpi_aware()
    win32.keep_awake(True)
    try:
        p = Pantalla(port, monitor, logo, host)
        p.root.mainloop()
    except OSError as ex:  # puerto ocupado
        log.error("pantalla: no se pudo escuchar en el puerto %d: %s", port, ex)
        print(f"LightHouse --pantalla: no se pudo escuchar en el puerto {port}: {ex}")
        return 1
    finally:
        win32.keep_awake(False)
    return 0
