import pytest

from clack import config, listeners
from clack.engine import Engine
from clack.keymap import KEY


class FakeMixer:
    def __init__(self):
        self.volume = None
        self.played = 0
        self.stopped = False

    def play(self, _samples):
        self.played += 1

    def stop(self):
        self.stopped = True


class IdleListener(listeners.BaseListener):
    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@pytest.fixture
def engine(tmp_path):
    eng = Engine(cfg_path=tmp_path / "config.json", mixer=FakeMixer(), listener_factory=IdleListener)
    eng.start()
    return eng


def test_start_applies_volume_and_starts_listener(engine):
    assert engine._mixer.volume == config.DEFAULTS["volume"] / 100
    assert engine.listener.started


def test_keys_play_only_when_enabled(engine):
    engine.on_key(KEY["A"], True)
    engine.on_key(KEY["A"], False)
    played = engine._mixer.played
    assert played >= 1
    engine.set_enabled(False)
    engine.on_key(KEY["A"], True)
    assert engine._mixer.played == played


def test_preview_plays_even_when_disabled(engine):
    engine.set_enabled(False)
    engine.preview()
    assert engine._mixer.played >= 1


def test_volume_is_clamped_and_saved(engine):
    engine.set_volume(150)
    assert engine.cfg["volume"] == 100
    assert engine._mixer.volume == 1.0
    engine.set_volume(-5)
    assert config.load(engine.cfg_path)["volume"] == 0


def test_pack_switch(engine):
    engine.set_pack("topre")
    assert engine.pack.name == "topre"
    assert config.load(engine.cfg_path)["pack"] == "topre"


@pytest.mark.parametrize("bad", ["nao-existe", "_mouse", "../packs"])
def test_invalid_pack_is_rejected(engine, bad):
    with pytest.raises(ValueError):
        engine.set_pack(bad)


def test_unknown_pack_in_config_falls_back(tmp_path):
    path = tmp_path / "config.json"
    config.save({"enabled": True, "pack": "sumiu", "volume": 10}, path)
    eng = Engine(cfg_path=path, mixer=FakeMixer(), listener_factory=IdleListener)
    assert eng.cfg["pack"] == config.DEFAULTS["pack"]


def test_audio_failure_is_reported_not_raised(tmp_path, monkeypatch):
    import clack.audio

    class BrokenMixer:
        def __init__(self):
            raise OSError("sem placa de som")

    monkeypatch.setattr(clack.audio, "Mixer", BrokenMixer)
    eng = Engine(cfg_path=tmp_path / "c.json", listener_factory=IdleListener)
    eng.start()
    assert eng.audio_error == "sem placa de som"
    eng.on_key(KEY["A"], True)  # sem mixer: não pode quebrar
    eng.preview()


def test_listener_failure_is_reported(tmp_path):
    class BrokenListener(listeners.BaseListener):
        def start(self):
            raise RuntimeError("sem gancho")

        def stop(self):
            pass

    eng = Engine(cfg_path=tmp_path / "c.json", mixer=FakeMixer(), listener_factory=BrokenListener)
    eng.start()
    assert eng.listener.status == listeners.ERROR
    assert eng.listener.detail == "sem gancho"


def test_stop(engine):
    engine.stop()
    assert engine.listener.stopped
    assert engine._mixer.stopped
