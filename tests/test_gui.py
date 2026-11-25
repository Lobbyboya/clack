import json

import pytest

pytest.importorskip("PySide6")


def test_window_selftest(tmp_path):
    from clack.selftest import check_window
    shot = tmp_path / "janela.png"
    assert check_window(shot).startswith("janela ok")
    assert shot.stat().st_size > 10_000


def test_full_selftest_report(tmp_path, monkeypatch):
    from clack.selftest import run
    out = tmp_path / "selftest.json"
    code = run(str(out))
    report = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0, report
    assert report["ok"]
