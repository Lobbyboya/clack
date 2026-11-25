import json
import wave
from pathlib import Path

import pytest

from clack.packs import PACKS_DIR, RATE, Pack, list_packs

ROOT = Path(__file__).resolve().parent.parent
ALL = list_packs()


def test_expected_packs_present():
    assert len([p for p in ALL if not p.startswith("_")]) == 11


@pytest.mark.parametrize("name", ALL)
def test_pack_files(name):
    folder = PACKS_DIR / name
    meta = json.loads((folder / "pack.json").read_text(encoding="utf-8"))
    files = {e[k] for e in meta.get("default", []) for k in ("down", "up") if k in e}
    files |= {e[k] for e in meta.get("keys", {}).values() for k in ("down", "up") if k in e}
    assert files, "pacote sem arquivos"
    for fname in files:
        with wave.open(str(folder / fname)) as w:
            assert w.getsampwidth() == 2
            assert w.getframerate() == RATE
            assert w.getnframes() > 0


@pytest.mark.parametrize("name", ALL)
def test_pack_loads_and_answers_every_key(name):
    pack = Pack(name)
    for code in list(range(1, 130)) + [1500]:
        assert pack.sound_for(code, "down") is not None


@pytest.mark.parametrize("name", ALL)
def test_every_pack_is_credited(name):
    assert f"packs/{name}" in (ROOT / "SOUNDS-LICENSES.md").read_text(encoding="utf-8")
