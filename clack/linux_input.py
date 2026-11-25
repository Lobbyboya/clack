"""Teclados no Linux pelo evdev, sem acordar a CPU à toa.

O kernel avisa pelo inotify quando um dispositivo aparece, some ou muda de
permissão em /dev/input; só então o Clack olha os dispositivos. Parado, o laço
fica bloqueado no select() sem prazo: zero acordadas por segundo.
"""

import ctypes
import ctypes.util
import os
import selectors
import struct
import sys
import threading
from collections.abc import Callable

import evdev
from evdev import ecodes

from .listeners import NO_PERMISSION, OK, BaseListener, KeyCallback

IN_ATTRIB = 0x00000004     # permissão mudou (o udev ajusta logo depois de criar)
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_NONBLOCK = 0o4000
IN_CLOEXEC = 0o2000000
_EVENT = struct.Struct("iIII")  # wd, mask, cookie, len (struct inotify_event)


class DirWatch:
    """inotify mínimo: avisa quais arquivos de um diretório foram criados, apagados ou alterados."""

    def __init__(self, path: str, mask: int = IN_CREATE | IN_DELETE | IN_ATTRIB):
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        self.fd = libc.inotify_init1(IN_NONBLOCK | IN_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1 falhou")
        if libc.inotify_add_watch(self.fd, os.fsencode(path), mask) < 0:
            err = ctypes.get_errno()
            os.close(self.fd)
            raise OSError(err, f"inotify_add_watch falhou em {path}")

    def fileno(self) -> int:
        return self.fd

    def read(self) -> list[tuple[int, str]]:
        """[(máscara, nome do arquivo)] dos eventos pendentes."""
        try:
            data = os.read(self.fd, 64 * 1024)
        except BlockingIOError:
            return []
        events, i = [], 0
        while i < len(data):
            _wd, mask, _cookie, length = _EVENT.unpack_from(data, i)
            i += _EVENT.size
            name = data[i:i + length].rstrip(b"\0").decode(errors="replace")
            i += length
            events.append((mask, name))
        return events

    def close(self):
        os.close(self.fd)


def is_keyboard(dev: evdev.InputDevice) -> bool:
    keys = dev.capabilities().get(ecodes.EV_KEY, [])
    return ecodes.KEY_A in keys and ecodes.KEY_SPACE in keys


class LinuxListener(BaseListener):
    INPUT_DIR = "/dev/input"
    FALLBACK_RESCAN_SECONDS = 30.0  # só se o inotify não estiver disponível

    def __init__(self, callback: KeyCallback, on_change: Callable[[str], None] | None = None):
        super().__init__(callback)
        self.on_change = on_change or (lambda _msg: None)  # avisos "teclado entrou/saiu"
        self.ready = threading.Event()                      # primeira varredura feita
        self._devices: dict[str, evdev.InputDevice] = {}    # teclados abertos
        self._ignored: set[str] = set()                     # não são teclado: nunca reabrir
        self._lock = threading.Lock()
        self._wake_r, self._wake_w = os.pipe()
        self._running = False
        self._thread = None

    def keyboards(self) -> list[str]:
        with self._lock:
            return [d.name for d in self._devices.values()]

    # --- dispositivos ----------------------------------------------------------------
    def _consider(self, path: str, sel: selectors.BaseSelector):
        if path in self._devices or path in self._ignored:
            return
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            return  # sem permissão ainda: o IN_ATTRIB do udev traz de volta
        if is_keyboard(dev):
            with self._lock:
                self._devices[path] = dev
            sel.register(dev, selectors.EVENT_READ, "device")
            self.on_change(f"teclado: {dev.name} ({path})")
        else:
            self._ignored.add(path)
            dev.close()

    def _forget(self, path: str, sel: selectors.BaseSelector):
        self._ignored.discard(path)
        with self._lock:
            dev = self._devices.pop(path, None)
        if dev is not None:
            sel.unregister(dev)
            dev.close()
            self.on_change(f"teclado removido: {dev.name}")

    def _scan_all(self, sel: selectors.BaseSelector):
        for path in evdev.list_devices(self.INPUT_DIR):
            self._consider(path, sel)

    def _update_status(self):
        if self._devices:
            self.status, self.detail = OK, ""
        else:
            self.status = NO_PERMISSION
            self.detail = "nenhum teclado legível (grupo 'input'?)"

    # --- laço ------------------------------------------------------------------------
    def _run(self):
        sel = selectors.DefaultSelector()
        sel.register(self._wake_r, selectors.EVENT_READ, "wake")
        try:
            watch = DirWatch(self.INPUT_DIR)
            sel.register(watch, selectors.EVENT_READ, "watch")
            timeout = None
        except OSError as exc:
            print(f"clack: inotify indisponível ({exc}); procurando teclados a cada "
                  f"{self.FALLBACK_RESCAN_SECONDS:.0f} s", file=sys.stderr)
            watch, timeout = None, self.FALLBACK_RESCAN_SECONDS
        try:
            self._scan_all(sel)
            self._update_status()
            self.ready.set()
            while self._running:
                ready = sel.select(timeout)
                if not ready:  # só acontece sem inotify
                    self._scan_all(sel)
                for key, _ in ready:
                    if key.data == "wake":
                        return
                    if key.data == "watch":
                        self._on_dir_events(watch.read(), sel)
                    else:
                        self._on_device(key.fileobj, sel)
                self._update_status()
        finally:
            for dev in list(self._devices.values()):
                dev.close()
            if watch is not None:
                watch.close()
            sel.close()

    def _on_dir_events(self, events, sel):
        for mask, name in events:
            if not name.startswith("event"):
                continue
            path = os.path.join(self.INPUT_DIR, name)
            if mask & IN_DELETE:
                self._forget(path, sel)
            else:  # criado ou com permissão nova
                self._consider(path, sel)

    def _on_device(self, dev, sel):
        try:
            events = list(dev.read())
        except OSError:  # desconectado
            self._forget(dev.path, sel)
            return
        for ev in events:
            # value: 1 = apertou, 0 = soltou, 2 = repetição automática (ignorada)
            if ev.type == ecodes.EV_KEY and ev.value in (0, 1):
                self.emit(ev.code, ev.value == 1)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, name="clack-evdev", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        os.write(self._wake_w, b"x")
        if self._thread is not None:
            self._thread.join(2)
        os.close(self._wake_r)
        os.close(self._wake_w)
