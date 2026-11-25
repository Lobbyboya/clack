"""Escuta o teclado do sistema inteiro e avisa cada tecla como código do evdev.

Cada sistema tem um backend:
  - Linux: lê /dev/input pelo evdev (funciona no Wayland; exige o grupo 'input').
  - Windows: gancho WH_KEYBOARD_LL (via pynput), lendo o scancode físico.
  - macOS: event tap só de escuta do Quartz (exige "Monitoramento de Entrada").

Todos chamam callback(código_evdev, apertou: bool) numa thread própria, sem
repetição automática (segurar a tecla toca o som uma vez só).
"""

import sys
import threading
from collections.abc import Callable

from . import keymap

KeyCallback = Callable[[int, bool], None]

# Estados que a interface mostra.
OK = "ok"
NO_PERMISSION = "no-permission"
ERROR = "error"


class BaseListener:
    def __init__(self, callback: KeyCallback):
        self.callback = callback
        self.status = OK
        self.detail = ""
        self._pressed: set[int] = set()

    def emit(self, code: int, down: bool):
        """Filtra a repetição automática e repassa o evento."""
        if down:
            if code in self._pressed:
                return
            self._pressed.add(code)
        else:
            self._pressed.discard(code)
        try:
            self.callback(code, down)
        except Exception as exc:  # um erro no som nunca pode derrubar o gancho
            print(f"clack: erro no callback: {exc}", file=sys.stderr)

    def keyboards(self) -> list[str]:
        return []

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


# --- Windows -----------------------------------------------------------------------
class WindowsListener(BaseListener):
    WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105

    def start(self):
        from pynput import keyboard

        def event_filter(msg, data):
            # Retornar False faz o pynput descartar o evento antes de traduzi-lo
            # (nada de ToUnicodeEx, que atrapalha acentos como ´ e ~). O evento
            # continua normal para o resto do sistema: só suppress_event() o
            # bloquearia, e ele nunca é chamado.
            try:
                self.handle_event(msg, data.vkCode, data.scanCode, data.flags)
            except Exception as exc:
                print(f"clack: erro no gancho: {exc}", file=sys.stderr)
            return False

        self._listener = keyboard.Listener(win32_event_filter=event_filter)
        self._listener.start()
        self._listener.wait()

    def handle_event(self, msg: int, vk: int, scan: int, flags: int):
        """Lógica pura do gancho (testável em qualquer sistema)."""
        if msg in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN):
            down = True
        elif msg in (self.WM_KEYUP, self.WM_SYSKEYUP):
            down = False
        else:
            return
        if vk == 0xE7:  # VK_PACKET: caractere unicode injetado, não é tecla física
            return
        self.emit(keymap.win_to_evdev(scan, vk, flags), down)

    def stop(self):
        self._listener.stop()


# --- macOS -------------------------------------------------------------------------
def mac_input_monitoring_access() -> int:
    """IOHIDCheckAccess(kIOHIDRequestTypeListenEvent): 0 liberado, 1 negado, 2 não decidido."""
    import ctypes
    iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
    iokit.IOHIDCheckAccess.argtypes = [ctypes.c_uint32]
    iokit.IOHIDCheckAccess.restype = ctypes.c_uint32
    return iokit.IOHIDCheckAccess(1)


def mac_request_input_monitoring() -> bool:
    """Mostra o pedido de permissão do sistema (só na primeira vez) e diz se já está liberado."""
    import ctypes
    iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
    iokit.IOHIDRequestAccess.argtypes = [ctypes.c_uint32]
    iokit.IOHIDRequestAccess.restype = ctypes.c_bool
    return bool(iokit.IOHIDRequestAccess(1))


class MacListener(BaseListener):
    # Tipos de evento do Quartz (CGEventTypes.h), em número para a lógica poder ser
    # testada em qualquer sistema.
    KEY_DOWN, KEY_UP, FLAGS_CHANGED = 10, 11, 12
    TAP_DISABLED = (0xFFFFFFFE, 0xFFFFFFFF)  # por timeout / pelo usuário
    # Bits "device dependent" de CGEventFlags (NX_DEVICE*KEYMASK, IOLLEvent.h):
    # dizem se cada modificador, esquerdo ou direito, está pressionado agora.
    MOD_BITS = {
        0x3B: 0x00000001,  # Control esquerdo
        0x38: 0x00000002,  # Shift esquerdo
        0x3C: 0x00000004,  # Shift direito
        0x37: 0x00000008,  # Command esquerdo
        0x36: 0x00000010,  # Command direito
        0x3A: 0x00000020,  # Option esquerdo
        0x3D: 0x00000040,  # Option direito
        0x3E: 0x00002000,  # Control direito
    }

    def __init__(self, callback: KeyCallback):
        super().__init__(callback)
        self._loop = None
        self._tap = None
        self._thread = None

    def handle_event(self, event_type: int, keycode: int, flags: int, autorepeat: bool):
        """Lógica pura do tap (testável sem permissão): decide aperto e soltura."""
        if event_type == self.KEY_DOWN:
            if not autorepeat:
                self.emit(keymap.mac_to_evdev(keycode), True)
        elif event_type == self.KEY_UP:
            self.emit(keymap.mac_to_evdev(keycode), False)
        elif event_type == self.FLAGS_CHANGED:
            code = keymap.mac_to_evdev(keycode)
            if keycode == keymap.MAC_CAPSLOCK:
                # Caps Lock só avisa quando muda de estado: toca aperto e soltura.
                self.emit(code, True)
                self.emit(code, False)
            elif keycode in self.MOD_BITS:
                self.emit(code, bool(flags & self.MOD_BITS[keycode]))
            # Fn (0x3F) e outros: sem som.

    def _tap_callback(self, _proxy, event_type, event, _refcon):
        import Quartz as Q
        if event_type in self.TAP_DISABLED:
            # O sistema desliga o tap se ele demorar; religa na hora.
            if self._tap is not None:
                Q.CGEventTapEnable(self._tap, True)
            return event
        try:
            keycode = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventKeycode)
            autorepeat = Q.CGEventGetIntegerValueField(event, Q.kCGKeyboardEventAutorepeat)
            self.handle_event(event_type, keycode, Q.CGEventGetFlags(event), bool(autorepeat))
        except Exception as exc:  # nunca deixar uma exceção escapar para o Quartz
            print(f"clack: erro no tap: {exc}", file=sys.stderr)
        return event

    def start(self):
        import Quartz as Q
        if mac_input_monitoring_access() != 0:
            mac_request_input_monitoring()
        mask = (Q.CGEventMaskBit(Q.kCGEventKeyDown) | Q.CGEventMaskBit(Q.kCGEventKeyUp)
                | Q.CGEventMaskBit(Q.kCGEventFlagsChanged))
        self._tap = Q.CGEventTapCreate(Q.kCGSessionEventTap, Q.kCGHeadInsertEventTap,
                                       Q.kCGEventTapOptionListenOnly, mask,
                                       self._tap_callback, None)
        if self._tap is None:
            self.status = NO_PERMISSION
            return
        ready = threading.Event()

        def run():
            self._loop = Q.CFRunLoopGetCurrent()
            source = Q.CFMachPortCreateRunLoopSource(None, self._tap, 0)
            Q.CFRunLoopAddSource(self._loop, source, Q.kCFRunLoopCommonModes)
            Q.CGEventTapEnable(self._tap, True)
            ready.set()
            Q.CFRunLoopRun()

        self._thread = threading.Thread(target=run, name="clack-mac-tap", daemon=True)
        self._thread.start()
        ready.wait(5)

    def stop(self):
        if self._loop is not None:
            import Quartz as Q
            Q.CGEventTapEnable(self._tap, False)
            Q.CFRunLoopStop(self._loop)
            self._loop = None


# --- Linux -------------------------------------------------------------------------
class LinuxListener(BaseListener):
    RESCAN_SECONDS = 2.0

    def __init__(self, callback: KeyCallback):
        super().__init__(callback)
        self._devices = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def keyboards(self) -> list[str]:
        with self._lock:
            return [d.name for d in self._devices.values()]

    def _rescan(self, sel):
        import selectors

        import evdev
        from evdev import ecodes
        for path in evdev.list_devices():
            if path in self._devices:
                continue
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            keys = dev.capabilities().get(ecodes.EV_KEY, [])
            if ecodes.KEY_A in keys and ecodes.KEY_SPACE in keys:
                with self._lock:
                    self._devices[path] = dev
                sel.register(dev, selectors.EVENT_READ)
            else:
                dev.close()

    def _run(self):
        import selectors
        import time

        from evdev import ecodes
        sel = selectors.DefaultSelector()
        last = 0.0
        while not self._stop.is_set():
            if time.monotonic() - last >= self.RESCAN_SECONDS:
                self._rescan(sel)
                last = time.monotonic()
                if not self._devices:
                    self.status = NO_PERMISSION
                    self.detail = "nenhum teclado legível (grupo 'input'?)"
                else:
                    self.status, self.detail = OK, ""
            if not self._devices:
                time.sleep(0.5)
                continue
            for key, _ in sel.select(timeout=0.5):
                dev = key.fileobj
                try:
                    events = list(dev.read())
                except OSError:
                    sel.unregister(dev)
                    with self._lock:
                        self._devices.pop(dev.path, None)
                    continue
                for ev in events:
                    if ev.type == ecodes.EV_KEY and ev.value in (0, 1):
                        self.emit(ev.code, ev.value == 1)

    def start(self):
        self._thread = threading.Thread(target=self._run, name="clack-evdev", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()


def create(callback: KeyCallback) -> BaseListener:
    if sys.platform == "win32":
        return WindowsListener(callback)
    if sys.platform == "darwin":
        return MacListener(callback)
    return LinuxListener(callback)
