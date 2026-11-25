"""Carrega pacotes de som (formato pack.json, códigos de tecla do evdev)."""

import json
import random
import wave
from pathlib import Path

import numpy as np

RATE = 48000
PACKS_DIR = Path(__file__).resolve().parent.parent / "packs"
PITCH_VARIANTS = (0.97, 1.0, 1.03)


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path.name}: só WAV 16 bits")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
        samples = data.astype(np.float32) / 32768.0
        if w.getframerate() != RATE:
            samples = _resample(samples, RATE / w.getframerate())
        return samples


def _resample(samples: np.ndarray, factor: float) -> np.ndarray:
    n = max(1, int(len(samples) * factor))
    return np.interp(np.linspace(0, len(samples) - 1, n),
                     np.arange(len(samples)), samples).astype(np.float32)


class Sound:
    """Um som com cópias em tons levemente diferentes, para não soar repetitivo."""

    def __init__(self, samples: np.ndarray):
        self.variants = [samples if p == 1.0 else _resample(samples, 1 / p)
                         for p in PITCH_VARIANTS]

    def pick(self) -> np.ndarray:
        return random.choice(self.variants)


class Pack:
    def __init__(self, name: str):
        folder = PACKS_DIR / name
        meta = json.loads((folder / "pack.json").read_text())
        self.name = name
        self.title = meta.get("name", name)
        cache: dict[str, Sound] = {}

        def load(entry: dict) -> dict:
            out = {}
            for kind in ("down", "up"):
                if kind in entry:
                    fname = entry[kind]
                    if fname not in cache:
                        cache[fname] = Sound(_load_wav(folder / fname))
                    out[kind] = cache[fname]
            return out

        self.default = [load(e) for e in meta.get("default", [])]
        self.keys = {int(code): load(e) for code, e in meta.get("keys", {}).items()}
        if not self.default:
            raise ValueError(f"pacote {name} sem sons 'default'")

    def sound_for(self, code: int, kind: str):
        entry = self.keys.get(code)
        if entry and kind in entry:
            return entry[kind]
        # Mesma tecla sempre cai na mesma variação, como num teclado de verdade.
        entry = self.default[code % len(self.default)]
        return entry.get(kind)


def list_packs() -> list[str]:
    return sorted(p.parent.name for p in PACKS_DIR.glob("*/pack.json"))
