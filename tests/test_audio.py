import threading
import time

import numpy as np
import pytest

sd = pytest.importorskip("sounddevice")

from clack import audio  # noqa: E402
from clack.packs import RATE  # noqa: E402


class FakeStream:
    """Imita o OutputStream: o teste chama o callback na mão, bloco a bloco.

    Como no PortAudio, stop() espera o callback em andamento terminar.
    """

    def __init__(self, callback, **_kw):
        self.callback = callback
        self.active = False
        self.starts = 0
        self.cb_lock = threading.Lock()

    def start(self):
        with self.cb_lock:
            self.active = True
            self.starts += 1

    def stop(self):
        with self.cb_lock:
            self.active = False

    def close(self):
        self.stop()

    def pull(self, frames=128) -> np.ndarray:
        out = np.zeros((frames, 1), dtype=np.float32)
        with self.cb_lock:
            try:
                self.callback(out, frames, None, None)
            except sd.CallbackStop:
                self.active = False
        return out[:, 0]


@pytest.fixture
def mixer():
    m = audio.Mixer(stream_factory=FakeStream)
    m.start()
    return m


def blocks_until_idle() -> int:
    return int(np.ceil(RATE * audio.IDLE_SECONDS / 128))


def test_mixes_and_drains(mixer):
    mixer.volume = 1.0
    mixer.play(np.full(200, 0.5, dtype=np.float32))
    first = mixer._stream.pull()
    assert 0.4 < first.max() <= 0.5
    second = mixer._stream.pull()
    assert second[:72].max() > 0 and second[72:].max() == 0
    assert mixer._voices == []


def test_output_is_clipped(mixer):
    mixer.volume = 1.0
    for _ in range(5):
        mixer.play(np.full(128, 0.9, dtype=np.float32))
    assert mixer._stream.pull().max() == pytest.approx(1.0)


def test_voice_limit(mixer):
    for _ in range(audio.MAX_VOICES + 10):
        mixer.play(np.zeros(10, dtype=np.float32))
    assert len(mixer._voices) == audio.MAX_VOICES


def test_sleeps_after_silence_and_wakes_on_next_key(mixer):
    stream = mixer._stream
    for _ in range(blocks_until_idle() - 1):
        stream.pull()
    assert stream.active
    stream.pull()
    assert not stream.active and mixer._idle          # dormiu
    mixer.play(np.ones(64, dtype=np.float32))
    assert stream.active and stream.starts == 2       # religou
    assert stream.pull().max() > 0                     # e o som da tecla saiu


def test_sound_keeps_stream_awake(mixer):
    stream = mixer._stream
    for _ in range(3 * blocks_until_idle()):
        mixer.play(np.zeros(8, dtype=np.float32))
        stream.pull()
    assert stream.active and stream.starts == 1


def test_no_restart_while_awake(mixer):
    for _ in range(50):
        mixer.play(np.zeros(8, dtype=np.float32))
    assert mixer._stream.starts == 1


def test_concurrent_keys_never_get_stuck(monkeypatch):
    """Áudio dormindo e acordando a cada 2 blocos enquanto teclas chegam de outra thread.

    Regra: nunca pode existir som pendente com o fluxo parado (seria uma tecla muda).
    """
    monkeypatch.setattr(audio, "IDLE_SECONDS", 2 * 128 / RATE)
    mixer = audio.Mixer(stream_factory=FakeStream)
    mixer.start()
    stream = mixer._stream
    stop = threading.Event()

    def audio_thread():
        while not stop.is_set():
            if stream.active:
                stream.pull()
            time.sleep(0.0002)

    t = threading.Thread(target=audio_thread)
    t.start()
    try:
        for i in range(400):
            mixer.play(np.ones(4, dtype=np.float32))
            time.sleep(0.0001 * (i % 7))
            with stream.cb_lock:
                assert stream.active or not mixer._voices, f"tecla presa na iteração {i}"
    finally:
        stop.set()
        t.join()
    assert stream.starts > 10, "o teste não exercitou o dormir/acordar"


def test_real_stream_sleeps_and_wakes(monkeypatch):
    """Com o PortAudio de verdade (pula se a máquina não tem saída de áudio)."""
    try:
        if not any(d["max_output_channels"] > 0 for d in sd.query_devices()):
            pytest.skip("sem saída de áudio")
        monkeypatch.setattr(audio, "IDLE_SECONDS", 0.2)
        m = audio.Mixer()
        m.start()
    except sd.PortAudioError as exc:
        pytest.skip(f"sem saída de áudio utilizável: {exc}")
    try:
        m.volume = 0.0  # silencioso
        time.sleep(0.6)
        assert not m._stream.active, "o fluxo não dormiu"
        m.play(np.zeros(4800, dtype=np.float32))
        assert m._stream.active, "o fluxo não acordou"
    finally:
        m.stop()
