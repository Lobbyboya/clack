import os
import sys

import pytest

from clack import listeners
from clack.keymap import KEY, LLKHF_EXTENDED


def collect(cls):
    got = []
    return cls(lambda code, down: got.append((code, down))), got


def test_autorepeat_is_ignored():
    lst, got = collect(listeners.LinuxListener)
    for down in (True, True, True, False, True, False):
        lst.emit(30, down)
    assert got == [(30, True), (30, False), (30, True), (30, False)]


def test_callback_error_does_not_propagate():
    def boom(code, down):
        raise RuntimeError("falhou")

    listeners.LinuxListener(boom).emit(30, True)  # não pode levantar


def test_windows_event_logic():
    lst, got = collect(listeners.WindowsListener)
    lst.handle_event(0x100, 0x41, 0x1E, 0)                   # WM_KEYDOWN A
    lst.handle_event(0x100, 0x41, 0x1E, 0)                   # repetição: ignorada
    lst.handle_event(0x101, 0x41, 0x1E, 0)                   # WM_KEYUP A
    lst.handle_event(0x104, 0xA5, 0x38, LLKHF_EXTENDED)      # WM_SYSKEYDOWN Alt direito
    lst.handle_event(0x105, 0xA5, 0x38, LLKHF_EXTENDED)
    lst.handle_event(0x100, 0xE7, 0x00E9, 0)                 # VK_PACKET (texto injetado)
    lst.handle_event(0x0200, 0x41, 0x1E, 0)                  # outra mensagem
    assert got == [(KEY["A"], True), (KEY["A"], False),
                   (KEY["RIGHTALT"], True), (KEY["RIGHTALT"], False)]


def test_mac_event_logic():
    m = listeners.MacListener
    lst, got = collect(m)
    lst.handle_event(m.KEY_DOWN, 0x00, 0, False)              # A
    lst.handle_event(m.KEY_DOWN, 0x00, 0, True)               # repetição do sistema
    lst.handle_event(m.KEY_UP, 0x00, 0, False)
    lst.handle_event(m.FLAGS_CHANGED, 0x38, m.MOD_BITS[0x38], False)   # Shift esq. aperta
    lst.handle_event(m.FLAGS_CHANGED, 0x3C, m.MOD_BITS[0x38] | m.MOD_BITS[0x3C], False)  # + dir.
    lst.handle_event(m.FLAGS_CHANGED, 0x38, m.MOD_BITS[0x3C], False)   # solta o esquerdo
    lst.handle_event(m.FLAGS_CHANGED, 0x3C, 0, False)                  # solta o direito
    lst.handle_event(m.FLAGS_CHANGED, 0x39, 0, False)                  # Caps Lock
    lst.handle_event(m.FLAGS_CHANGED, 0x3F, 0x800000, False)           # Fn: sem som
    assert got == [
        (KEY["A"], True), (KEY["A"], False),
        (KEY["LEFTSHIFT"], True), (KEY["RIGHTSHIFT"], True),
        (KEY["LEFTSHIFT"], False), (KEY["RIGHTSHIFT"], False),
        (KEY["CAPSLOCK"], True), (KEY["CAPSLOCK"], False),
    ]


@pytest.mark.skipif(sys.platform != "win32" or os.environ.get("CLACK_SELFTEST_INJECT") != "1",
                    reason="só no Windows do CI (injeta teclas de verdade)")
def test_windows_real_hook():
    from clack.selftest import check_windows_hook
    assert "eventos corretos" in check_windows_hook()


@pytest.mark.skipif(sys.platform != "darwin", reason="só no macOS")
def test_mac_real_quartz_events():
    from clack.selftest import check_mac_tap
    assert check_mac_tap().startswith("tap ok")


@pytest.mark.skipif(sys.platform != "darwin", reason="só no macOS")
def test_mac_start_without_permission_reports_status():
    lst, _ = collect(listeners.MacListener)
    lst.start()
    try:
        assert lst.status in (listeners.OK, listeners.NO_PERMISSION)
    finally:
        lst.stop()
