"""Autoteste do app empacotado: `Clack --selftest saida.json`.

Roda no executável final (PyInstaller) para provar que nada ficou de fora do
pacote: sons, PortAudio, backend de teclado da plataforma e a janela Qt. Grava
um JSON com o resultado de cada verificação e uma captura da janela ao lado
(saida.png). Sai com código 0 só se tudo passar.

A injeção de teclas reais no Windows só acontece com CLACK_SELFTEST_INJECT=1
(usado no CI), para nunca digitar nada na máquina de alguém.
"""

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

from . import keymap, listeners
from .packs import Pack, list_packs


def check_packs() -> str:
    names = list_packs()
    visible = [n for n in names if not n.startswith("_")]
    if len(visible) < 10:
        raise AssertionError(f"poucos pacotes no bundle: {names}")
    for name in names:
        pack = Pack(name)
        if pack.sound_for(keymap.KEY["A"], "down") is None:
            raise AssertionError(f"{name}: sem som para a tecla A")
    return f"{len(names)} pacotes carregados"


def check_audio() -> str:
    import sounddevice as sd  # falha aqui se a biblioteca PortAudio não foi empacotada
    version = sd.get_portaudio_version()[1]
    try:
        outputs = [d["name"] for d in sd.query_devices() if d["max_output_channels"] > 0]
    except Exception as exc:  # máquina sem placa de som (CI): não é defeito do app
        outputs = [f"(sem dispositivos: {exc})"]
    return f"{version}; saídas: {len(outputs)}"


def check_keymap() -> str:
    assert keymap.win_to_evdev(0x1E, 0x41, 0) == keymap.KEY["A"]
    assert keymap.win_to_evdev(0x48, 0x26, keymap.LLKHF_EXTENDED) == keymap.KEY["UP"]
    assert keymap.mac_to_evdev(0x00) == keymap.KEY["A"]
    assert keymap.mac_to_evdev(0x31) == keymap.KEY["SPACE"]
    return "ok"


# --- Windows: teclas de verdade pelo gancho do sistema ------------------------------------
# (scancode, extended, código evdev esperado)
WIN_KEYS = [
    (0x1E, False, keymap.KEY["A"]),
    (0x39, False, keymap.KEY["SPACE"]),
    (0x1C, False, keymap.KEY["ENTER"]),
    (0x2A, False, keymap.KEY["LEFTSHIFT"]),
    (0x48, True, keymap.KEY["UP"]),
    (0x1D, True, keymap.KEY["RIGHTCTRL"]),
]


def win_send_scancodes(keys):
    """Injeta aperto e soltura de cada tecla com SendInput (só scancode, como um teclado)."""
    import ctypes
    from ctypes import wintypes

    ulong_ptr = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ulong_ptr)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]

    input_keyboard = 1
    extendedkey, keyup, scancode = 0x0001, 0x0002, 0x0008
    send_input = ctypes.windll.user32.SendInput
    send_input.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    send_input.restype = wintypes.UINT
    for scan, extended, _ in keys:
        for up in (False, True):
            flags = scancode | (extendedkey if extended else 0) | (keyup if up else 0)
            event = INPUT(type=input_keyboard, ki=KEYBDINPUT(0, scan, flags, 0, 0))
            if send_input(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
                raise OSError(f"SendInput falhou (erro {ctypes.GetLastError()})")
            time.sleep(0.03)


def check_windows_hook() -> str:
    got = []
    listener = listeners.WindowsListener(lambda code, down: got.append((code, down)))
    listener.start()
    try:
        time.sleep(0.5)  # o pynput instala o gancho logo depois de "pronto"
        if os.environ.get("CLACK_SELFTEST_INJECT") != "1":
            return "gancho instalado (injeção de teclas desligada)"
        win_send_scancodes(WIN_KEYS)
        deadline = time.time() + 3
        expected = [(code, down) for _, _, code in WIN_KEYS for down in (True, False)]
        while time.time() < deadline and len(got) < len(expected):
            time.sleep(0.05)
    finally:
        listener.stop()
    if got != expected:
        raise AssertionError(f"esperado {expected}, recebido {got}")
    return f"{len(got)} eventos corretos"


# --- macOS: o callback do tap com eventos Quartz de verdade --------------------------------
def check_mac_tap() -> str:
    import Quartz as Q

    got = []
    listener = listeners.MacListener(lambda code, down: got.append((code, down)))

    def key_event(keycode, down, event_type=None, flags=0):
        event = Q.CGEventCreateKeyboardEvent(None, keycode, down)
        if event_type is not None:
            Q.CGEventSetType(event, event_type)
        Q.CGEventSetFlags(event, flags)  # sempre: o evento novo herda os modificadores atuais
        listener._tap_callback(None, Q.CGEventGetType(event), event, None)

    key_event(0x00, True)                                   # A aperta
    key_event(0x00, False)                                  # A solta
    key_event(0x7E, True)                                   # seta para cima
    key_event(0x7E, False)
    shift_l = listener.MOD_BITS[0x38] | Q.kCGEventFlagMaskShift
    key_event(0x38, True, Q.kCGEventFlagsChanged, shift_l)  # Shift esquerdo aperta
    key_event(0x38, False, Q.kCGEventFlagsChanged, 0)       # e solta
    expected = [(30, True), (30, False), (103, True), (103, False), (42, True), (42, False)]
    if got != expected:
        raise AssertionError(f"esperado {expected}, recebido {got}")
    access = listeners.mac_input_monitoring_access()
    return f"tap ok; permissão de monitoramento = {access} (0 liberado, 1 negado, 2 não pedido)"


# --- janela ----------------------------------------------------------------------------
class _SilentMixer:
    volume = 0.6

    def __init__(self):
        self.played = 0

    def play(self, _samples):
        self.played += 1

    def stop(self):
        pass


class _IdleListener(listeners.BaseListener):
    def start(self):
        pass

    def stop(self):
        pass


def check_window(screenshot: Path) -> str:
    from PySide6.QtWidgets import QApplication

    from .engine import Engine
    from .qt_app import MainWindow, setup_app

    app = QApplication.instance() or setup_app([sys.argv[0]])
    with tempfile.TemporaryDirectory() as tmp:
        mixer = _SilentMixer()
        engine = Engine(cfg_path=Path(tmp) / "config.json", mixer=mixer,
                        listener_factory=_IdleListener)
        engine.start()
        win = MainWindow(engine)
        win.show()
        for _ in range(20):
            app.processEvents()
            time.sleep(0.02)

        win.power.click()                       # desliga
        assert engine.cfg["enabled"] is False, "botão de ligar não desligou"
        win.power.click()                       # liga de novo
        assert engine.cfg["enabled"] is True
        win.slider.setValue(35)
        win.save_volume()
        assert engine.cfg["volume"] == 35, "volume não foi salvo"
        target = next(n for n in win.tiles if n != engine.cfg["pack"])
        win.on_pack(target)
        assert engine.cfg["pack"] == target, "pacote não trocou"
        assert win.tiles[target].property("selected") is True
        assert mixer.played > 0, "a prévia do pacote não tocou"
        saved = json.loads((Path(tmp) / "config.json").read_text(encoding="utf-8"))
        assert saved == engine.cfg, "config.json diferente do estado"

        for _ in range(10):
            app.processEvents()
        win.grab().save(str(screenshot))
        win.quitting = True
        win.close()
    return f"janela ok; captura em {screenshot.name}"


def run(out: str) -> int:
    out_path = Path(out).resolve()
    checks = [("pacotes", check_packs), ("áudio", check_audio), ("mapa de teclas", check_keymap)]
    if sys.platform == "win32":
        checks.append(("gancho do Windows", check_windows_hook))
    elif sys.platform == "darwin":
        checks.append(("tap do macOS", check_mac_tap))
    checks.append(("janela", lambda: check_window(out_path.with_suffix(".png"))))

    results, ok = {}, True
    for name, fn in checks:
        try:
            results[name] = {"ok": True, "info": fn()}
        except Exception:
            ok = False
            results[name] = {"ok": False, "info": traceback.format_exc()}
    report = {"ok": ok, "platform": sys.platform, "frozen": bool(getattr(sys, "frozen", False)),
              "checks": results}
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if ok else 1
