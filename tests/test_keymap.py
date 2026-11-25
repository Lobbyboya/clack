import pytest

from clack import keymap
from clack.keymap import KEY, LLKHF_EXTENDED, mac_to_evdev, win_to_evdev


def test_key_codes_match_evdev():
    ecodes = pytest.importorskip("evdev.ecodes")
    for name, code in KEY.items():
        assert ecodes.ecodes[f"KEY_{name}"] == code, name


@pytest.mark.parametrize("scan", range(1, 89))
def test_windows_plain_scancodes_are_evdev_codes(scan):
    assert win_to_evdev(scan, 0x41, 0) == scan


@pytest.mark.parametrize(("scan", "vk", "name"), [
    (0x48, 0x26, "UP"), (0x50, 0x28, "DOWN"), (0x4B, 0x25, "LEFT"), (0x4D, 0x27, "RIGHT"),
    (0x1C, 0x0D, "KPENTER"), (0x1D, 0xA3, "RIGHTCTRL"), (0x38, 0xA5, "RIGHTALT"),
    (0x53, 0x2E, "DELETE"), (0x52, 0x2D, "INSERT"), (0x47, 0x24, "HOME"), (0x4F, 0x23, "END"),
    (0x5B, 0x5B, "LEFTMETA"), (0x35, 0x6F, "KPSLASH"),
])
def test_windows_extended_keys(scan, vk, name):
    assert win_to_evdev(scan, vk, LLKHF_EXTENDED) == KEY[name]


def test_windows_pause_and_numlock_share_scancode():
    assert win_to_evdev(0x45, keymap.VK_PAUSE, 0) == KEY["PAUSE"]
    assert win_to_evdev(0x45, keymap.VK_NUMLOCK, LLKHF_EXTENDED) == KEY["NUMLOCK"]


def test_windows_without_scancode_uses_virtual_key():
    assert win_to_evdev(0, 0x41, 0) == KEY["A"]
    assert win_to_evdev(0, 0x20, 0) == KEY["SPACE"]
    assert win_to_evdev(0, 0x0D, 0) == KEY["ENTER"]


def test_windows_unknown_keys_get_stable_codes_outside_evdev_range():
    first = win_to_evdev(0x5F, 0xAD, 0)
    assert first >= keymap.UNKNOWN_BASE
    assert win_to_evdev(0x5F, 0xAD, 0) == first


@pytest.mark.parametrize(("vk", "name"), [
    (0x00, "A"), (0x01, "S"), (0x0C, "Q"), (0x12, "1"), (0x1D, "0"), (0x24, "ENTER"),
    (0x30, "TAB"), (0x31, "SPACE"), (0x33, "BACKSPACE"), (0x35, "ESC"), (0x38, "LEFTSHIFT"),
    (0x3C, "RIGHTSHIFT"), (0x37, "LEFTMETA"), (0x7E, "UP"), (0x7B, "LEFT"), (0x75, "DELETE"),
    (0x7A, "F1"), (0x6F, "F12"),
])
def test_mac_keycodes(vk, name):
    assert mac_to_evdev(vk) == KEY[name]


def test_mac_table_has_no_duplicate_targets():
    values = list(keymap.MAC_TO_EVDEV.values())
    assert len(values) == len(set(values))


def test_mac_letters_and_digits_all_mapped():
    targets = set(keymap.MAC_TO_EVDEV.values())
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        assert KEY[ch] in targets, ch
