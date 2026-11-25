"""Mixer de baixa latência: soma os sons ativos dentro do callback do PortAudio.

Para não gastar CPU à toa, o fluxo de áudio se desliga depois de alguns segundos
de silêncio e religa na próxima tecla (religar leva poucos milissegundos).
"""

import random
import threading

import numpy as np
import sounddevice as sd

from .packs import RATE

MAX_VOICES = 32
IDLE_SECONDS = 3.0


class Mixer:
    def __init__(self, stream_factory=sd.OutputStream):
        self.volume = 0.6
        self._voices: list[list] = []  # [amostras, posição, ganho]
        self._lock = threading.Lock()          # protege _voices e _idle (usado no callback)
        self._restart_lock = threading.Lock()  # serializa stop/start do fluxo
        self._idle = True                      # fluxo parado ou parando
        self._silent_frames = 0
        self._stream = stream_factory(samplerate=RATE, channels=1, dtype="float32",
                                      blocksize=128, latency="low", callback=self._callback)

    def start(self):
        """Abre o áudio (valida o dispositivo); ele dorme sozinho se ficar em silêncio."""
        with self._lock:
            self._idle = False
            self._silent_frames = 0
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
            self._silent_frames = 0
            wake = self._idle
            self._idle = False
        if wake:
            with self._restart_lock:
                # stop() espera o callback que decidiu dormir terminar; depois religa.
                self._stream.stop()
                self._stream.start()

    def _callback(self, outdata, frames, _time, _status):
        out = outdata[:, 0]
        out.fill(0)
        go_idle = False
        with self._lock:
            if not self._voices:
                self._silent_frames += frames
                if self._silent_frames < RATE * IDLE_SECONDS:
                    return
                self._idle = go_idle = True
            else:
                alive = []
                for voice in self._voices:
                    samples, pos, gain = voice
                    chunk = samples[pos:pos + frames]
                    out[:len(chunk)] += chunk * gain
                    voice[1] = pos + frames
                    if voice[1] < len(samples):
                        alive.append(voice)
                self._voices = alive
        if go_idle:
            raise sd.CallbackStop  # encerra o fluxo; play() religa quando precisar
        np.clip(out, -1.0, 1.0, out=out)
