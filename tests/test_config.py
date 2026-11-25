import json
import sys

from clack import config


def test_missing_file_gives_defaults(tmp_path):
    assert config.load(tmp_path / "nao-existe.json") == config.DEFAULTS


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ isso não é json", encoding="utf-8")
    assert config.load(path) == config.DEFAULTS
    path.write_text("[1, 2]", encoding="utf-8")
    assert config.load(path) == config.DEFAULTS


def test_bad_values_are_fixed(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"enabled": "sim", "pack": 3, "volume": 500}), encoding="utf-8")
    assert config.load(path) == {**config.DEFAULTS, "volume": 100}
    path.write_text(json.dumps({"volume": "alto"}), encoding="utf-8")
    assert config.load(path)["volume"] == config.DEFAULTS["volume"]


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "sub" / "config.json"
    cfg = {"enabled": False, "pack": "topre", "volume": 42}
    config.save(cfg, path)
    assert config.load(path) == cfg
    assert not path.with_suffix(".tmp").exists()


def test_platform_dir():
    d = config.config_dir()
    if sys.platform == "win32":
        assert d.name == "Clack"
    elif sys.platform == "darwin":
        assert d.parts[-2:] == ("Application Support", "Clack")
    else:
        assert d.name == "clack"
