import pytest

pytest.importorskip("evdev")


@pytest.fixture
def daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clack import daemon as mod

    class FakeMixer:
        volume = 0.6

    monkeypatch.setattr(mod, "Mixer", FakeMixer)
    return mod.Daemon()


def test_commands(daemon, tmp_path):
    from clack import config
    assert daemon.handle({"action": "status"})["ok"]
    assert daemon.handle({"action": "off"})["enabled"] is False
    assert daemon.handle({"action": "toggle"})["enabled"] is True
    assert daemon.handle({"action": "volume", "value": "250"})["volume"] == 100
    assert daemon.mixer.volume == 1.0
    assert daemon.handle({"action": "pack", "value": "topre"})["pack"] == "topre"
    assert daemon.handle({"action": "pack", "value": "nada"})["ok"] is False
    assert daemon.handle({"action": "xyz"})["ok"] is False
    saved = config.load(tmp_path / "clack" / "config.json")
    assert saved == {"enabled": True, "pack": "topre", "volume": 100}
