"""Traduz códigos de tecla do Windows e do macOS para os códigos do evdev (Linux).

Os pacotes de som (pack.json) usam os códigos do evdev para as teclas especiais,
então os três sistemas precisam falar a mesma língua. Este módulo não importa
nada específico de plataforma: dá para testá-lo em qualquer sistema.
"""

# Códigos do evdev usados abaixo (linux/input-event-codes.h). Os testes conferem
# cada valor com o módulo evdev de verdade.
KEY = {
    "ESC": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10,
    "0": 11, "MINUS": 12, "EQUAL": 13, "BACKSPACE": 14, "TAB": 15,
    "Q": 16, "W": 17, "E": 18, "R": 19, "T": 20, "Y": 21, "U": 22, "I": 23, "O": 24, "P": 25,
    "LEFTBRACE": 26, "RIGHTBRACE": 27, "ENTER": 28, "LEFTCTRL": 29,
    "A": 30, "S": 31, "D": 32, "F": 33, "G": 34, "H": 35, "J": 36, "K": 37, "L": 38,
    "SEMICOLON": 39, "APOSTROPHE": 40, "GRAVE": 41, "LEFTSHIFT": 42, "BACKSLASH": 43,
    "Z": 44, "X": 45, "C": 46, "V": 47, "B": 48, "N": 49, "M": 50,
    "COMMA": 51, "DOT": 52, "SLASH": 53, "RIGHTSHIFT": 54, "KPASTERISK": 55,
    "LEFTALT": 56, "SPACE": 57, "CAPSLOCK": 58,
    "F1": 59, "F2": 60, "F3": 61, "F4": 62, "F5": 63, "F6": 64, "F7": 65, "F8": 66,
    "F9": 67, "F10": 68, "NUMLOCK": 69, "SCROLLLOCK": 70,
    "KP7": 71, "KP8": 72, "KP9": 73, "KPMINUS": 74, "KP4": 75, "KP5": 76, "KP6": 77,
    "KPPLUS": 78, "KP1": 79, "KP2": 80, "KP3": 81, "KP0": 82, "KPDOT": 83,
    "102ND": 86, "F11": 87, "F12": 88, "RO": 89,
    "KPENTER": 96, "RIGHTCTRL": 97, "KPSLASH": 98, "SYSRQ": 99, "RIGHTALT": 100,
    "HOME": 102, "UP": 103, "PAGEUP": 104, "LEFT": 105, "RIGHT": 106, "END": 107,
    "DOWN": 108, "PAGEDOWN": 109, "INSERT": 110, "DELETE": 111,
    "KPEQUAL": 117, "PAUSE": 119, "KPCOMMA": 121, "YEN": 124,
    "LEFTMETA": 125, "RIGHTMETA": 126, "COMPOSE": 127,
    "F13": 183, "F14": 184, "F15": 185, "F16": 186, "F17": 187, "F18": 188,
    "F19": 189, "F20": 190,
}

# Teclas sem equivalente conhecido recebem um código fora da faixa do evdev. O
# pacote então usa um som "default", sempre o mesmo para a mesma tecla.
UNKNOWN_BASE = 1000


# --- Windows ----------------------------------------------------------------------
# O gancho de teclado do Windows entrega o scancode do "set 1" do PC. Nas teclas
# sem o prefixo E0 esse número é exatamente o código do evdev (o evdev nasceu
# dele). As teclas com prefixo E0 ("extended") precisam desta tabela.
WIN_EXTENDED = {
    0x1C: KEY["KPENTER"], 0x1D: KEY["RIGHTCTRL"], 0x35: KEY["KPSLASH"],
    0x37: KEY["SYSRQ"], 0x38: KEY["RIGHTALT"], 0x45: KEY["NUMLOCK"],
    0x46: KEY["PAUSE"], 0x47: KEY["HOME"], 0x48: KEY["UP"], 0x49: KEY["PAGEUP"],
    0x4B: KEY["LEFT"], 0x4D: KEY["RIGHT"], 0x4F: KEY["END"], 0x50: KEY["DOWN"],
    0x51: KEY["PAGEDOWN"], 0x52: KEY["INSERT"], 0x53: KEY["DELETE"],
    0x5B: KEY["LEFTMETA"], 0x5C: KEY["RIGHTMETA"], 0x5D: KEY["COMPOSE"],
    0x36: KEY["RIGHTSHIFT"], 0x2A: KEY["LEFTSHIFT"],
}
# Scancodes sem E0 acima de F12 que têm nome no evdev.
WIN_PLAIN_EXTRA = {
    0x64: KEY["F13"], 0x65: KEY["F14"], 0x66: KEY["F15"], 0x67: KEY["F16"],
    0x68: KEY["F17"], 0x69: KEY["F18"], 0x6A: KEY["F19"], 0x6B: KEY["F20"],
    0x73: KEY["RO"], 0x7D: KEY["YEN"], 0x7E: KEY["KPCOMMA"],
}
VK_PAUSE = 0x13
VK_NUMLOCK = 0x90

# Quando o scancode vem zerado (tecla injetada só com o código virtual), usamos o
# código virtual (VK) do Windows.
WIN_VK = {
    0x08: KEY["BACKSPACE"], 0x09: KEY["TAB"], 0x0D: KEY["ENTER"], 0x10: KEY["LEFTSHIFT"],
    0x11: KEY["LEFTCTRL"], 0x12: KEY["LEFTALT"], 0x13: KEY["PAUSE"], 0x14: KEY["CAPSLOCK"],
    0x1B: KEY["ESC"], 0x20: KEY["SPACE"], 0x21: KEY["PAGEUP"], 0x22: KEY["PAGEDOWN"],
    0x23: KEY["END"], 0x24: KEY["HOME"], 0x25: KEY["LEFT"], 0x26: KEY["UP"],
    0x27: KEY["RIGHT"], 0x28: KEY["DOWN"], 0x2C: KEY["SYSRQ"], 0x2D: KEY["INSERT"],
    0x2E: KEY["DELETE"], 0x5B: KEY["LEFTMETA"], 0x5C: KEY["RIGHTMETA"], 0x5D: KEY["COMPOSE"],
    0x90: KEY["NUMLOCK"], 0x91: KEY["SCROLLLOCK"],
    0xA0: KEY["LEFTSHIFT"], 0xA1: KEY["RIGHTSHIFT"], 0xA2: KEY["LEFTCTRL"],
    0xA3: KEY["RIGHTCTRL"], 0xA4: KEY["LEFTALT"], 0xA5: KEY["RIGHTALT"],
}
WIN_VK.update({0x30 + i: KEY[str(i)] for i in range(10)})                  # 0-9
WIN_VK.update({0x41 + i: KEY[chr(0x41 + i)] for i in range(26)})          # A-Z
WIN_VK.update({0x70 + i: KEY[f"F{i + 1}"] for i in range(12)})            # F1-F12
WIN_VK.update({0x60 + i: KEY[f"KP{i}"] for i in range(10)})               # teclado numérico

LLKHF_EXTENDED = 0x01


def win_to_evdev(scan: int, vk: int, flags: int) -> int:
    """Código do evdev para um evento do gancho WH_KEYBOARD_LL do Windows."""
    extended = bool(flags & LLKHF_EXTENDED)
    # Pause e NumLock compartilham o scancode 0x45; o Windows marca o NumLock como
    # "extended", mas o VK é a forma mais segura de separar os dois.
    if vk == VK_PAUSE:
        return KEY["PAUSE"]
    if vk == VK_NUMLOCK:
        return KEY["NUMLOCK"]
    if scan == 0:
        return WIN_VK.get(vk, UNKNOWN_BASE + vk)
    if extended:
        return WIN_EXTENDED.get(scan, UNKNOWN_BASE + 0x100 + scan)
    if 1 <= scan <= 88:
        return scan
    return WIN_PLAIN_EXTRA.get(scan, UNKNOWN_BASE + scan)


# --- macOS ------------------------------------------------------------------------
# Códigos virtuais de tecla do macOS (kVK_* em HIToolbox/Events.h). São posições
# físicas do teclado, independentes do layout (igual ao evdev).
MAC_TO_EVDEV = {
    0x00: KEY["A"], 0x01: KEY["S"], 0x02: KEY["D"], 0x03: KEY["F"], 0x04: KEY["H"],
    0x05: KEY["G"], 0x06: KEY["Z"], 0x07: KEY["X"], 0x08: KEY["C"], 0x09: KEY["V"],
    0x0A: KEY["102ND"],  # kVK_ISO_Section (tecla extra dos teclados ISO)
    0x0B: KEY["B"], 0x0C: KEY["Q"], 0x0D: KEY["W"], 0x0E: KEY["E"], 0x0F: KEY["R"],
    0x10: KEY["Y"], 0x11: KEY["T"], 0x12: KEY["1"], 0x13: KEY["2"], 0x14: KEY["3"],
    0x15: KEY["4"], 0x16: KEY["6"], 0x17: KEY["5"], 0x18: KEY["EQUAL"], 0x19: KEY["9"],
    0x1A: KEY["7"], 0x1B: KEY["MINUS"], 0x1C: KEY["8"], 0x1D: KEY["0"],
    0x1E: KEY["RIGHTBRACE"], 0x1F: KEY["O"], 0x20: KEY["U"], 0x21: KEY["LEFTBRACE"],
    0x22: KEY["I"], 0x23: KEY["P"], 0x24: KEY["ENTER"], 0x25: KEY["L"], 0x26: KEY["J"],
    0x27: KEY["APOSTROPHE"], 0x28: KEY["K"], 0x29: KEY["SEMICOLON"],
    0x2A: KEY["BACKSLASH"], 0x2B: KEY["COMMA"], 0x2C: KEY["SLASH"], 0x2D: KEY["N"],
    0x2E: KEY["M"], 0x2F: KEY["DOT"], 0x30: KEY["TAB"], 0x31: KEY["SPACE"],
    0x32: KEY["GRAVE"], 0x33: KEY["BACKSPACE"], 0x35: KEY["ESC"],
    0x36: KEY["RIGHTMETA"], 0x37: KEY["LEFTMETA"], 0x38: KEY["LEFTSHIFT"],
    0x39: KEY["CAPSLOCK"], 0x3A: KEY["LEFTALT"], 0x3B: KEY["LEFTCTRL"],
    0x3C: KEY["RIGHTSHIFT"], 0x3D: KEY["RIGHTALT"], 0x3E: KEY["RIGHTCTRL"],
    0x40: KEY["F17"], 0x41: KEY["KPDOT"], 0x43: KEY["KPASTERISK"], 0x45: KEY["KPPLUS"],
    0x47: KEY["NUMLOCK"],  # kVK_ANSI_KeypadClear fica onde o NumLock fica no PC
    0x4B: KEY["KPSLASH"], 0x4C: KEY["KPENTER"], 0x4E: KEY["KPMINUS"],
    0x4F: KEY["F18"], 0x50: KEY["F19"], 0x51: KEY["KPEQUAL"],
    0x52: KEY["KP0"], 0x53: KEY["KP1"], 0x54: KEY["KP2"], 0x55: KEY["KP3"],
    0x56: KEY["KP4"], 0x57: KEY["KP5"], 0x58: KEY["KP6"], 0x59: KEY["KP7"],
    0x5A: KEY["F20"], 0x5B: KEY["KP8"], 0x5C: KEY["KP9"],
    0x5D: KEY["YEN"], 0x5E: KEY["RO"], 0x5F: KEY["KPCOMMA"],
    0x60: KEY["F5"], 0x61: KEY["F6"], 0x62: KEY["F7"], 0x63: KEY["F3"], 0x64: KEY["F8"],
    0x65: KEY["F9"], 0x67: KEY["F11"], 0x69: KEY["F13"], 0x6A: KEY["F16"],
    0x6B: KEY["F14"], 0x6D: KEY["F10"], 0x6F: KEY["F12"], 0x71: KEY["F15"],
    0x72: KEY["INSERT"],  # kVK_Help fica onde o Insert fica no PC
    0x73: KEY["HOME"], 0x74: KEY["PAGEUP"], 0x75: KEY["DELETE"], 0x76: KEY["F4"],
    0x77: KEY["END"], 0x78: KEY["F2"], 0x79: KEY["PAGEDOWN"], 0x7A: KEY["F1"],
    0x7B: KEY["LEFT"], 0x7C: KEY["RIGHT"], 0x7D: KEY["DOWN"], 0x7E: KEY["UP"],
}

# Teclas modificadoras do Mac: chegam como "flags changed", sem dizer se foi
# aperto ou soltura. kVK_Function (0x3F) também chega assim, mas não toca som.
MAC_MODIFIERS = {0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F}
MAC_CAPSLOCK = 0x39
MAC_FN = 0x3F


def mac_to_evdev(keycode: int) -> int:
    return MAC_TO_EVDEV.get(keycode, UNKNOWN_BASE + keycode)
