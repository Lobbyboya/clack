"""Mixer de baixa latência: soma os sons ativos dentro do callback do PortAudio."""

import random
import threading

import numpy as np
import sounddevice as sd

from .packs import RATE

MAX_VOICES = 32


class Mixer:
    def __init__(self):
        self.volume = 0.6
        self._voices: list[list] = []  # [amostras, posição, ganho]
        self._lock = threading.Lock()
        self._stream = sd.OutputStream(samplerate=RATE, channels=1, dtype="float32",
                                       blocksize=128, latency="low",
                                       callback=self._callback)

    def start(self):
        self._stream.start()

    def stop(self):
        self._stream.stop()
        self._stream.close()

    def play(self, samples: np.ndarray):
        gain = self.volume * random.uniform(0.85, 1.0)
        with self._lock:
            if len(self._voices) >= MAX_VOICES:
                self._voices.pop(0)
            self._voices.append([samples, 0, gain])

    def _callback(self, outdata, frames, _time, _status):
        out = outdata[:, 0]
        out.fill(0)
        with self._lock:
            alive = []
            for voice in self._voices:
                samples, pos, gain = voice
                chunk = samples[pos:pos + frames]
                out[:len(chunk)] += chunk * gain
                voice[1] = pos + frames
                if voice[1] < len(samples):
                    alive.append(voice)
            self._voices = alive
        np.clip(out, -1.0, 1.0, out=out)
