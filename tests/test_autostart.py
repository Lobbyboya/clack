import sys

import pytest

from clack import autostart


def test_desktop_exec_quoting():
    assert autostart.desktop_exec(["/usr/bin/python3", "/opt/app/main.py", "--hidden"]) == \
        "/usr/bin/python3 /opt/app/main.py --hidden"
    assert autostart.desktop_exec(["/home/a b/x", 'q"$`\\', "100%"]) == \
        '"/home/a b/x" "q\\"\\$\\`\\\\" "100%%"'


def test_launch_command_hidden():
    cmd = autostart.launch_command()
    assert cmd[-1] == "--hidden"
    assert cmd[0] == sys.executable


@pytest.mark.skipif(sys.platform in ("win32", "darwin"), reason="Linux")
def test_linux_toggle(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    text = (tmp_path / "autostart" / "dev.renan.clack.desktop").read_text()
    assert "--hidden" in text
    assert autostart.is_enabled()
    autostart.set_enabled(False)
    assert not autostart.is_enabled()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS")
def test_mac_toggle(tmp_path, monkeypatch):
    import plistlib
    monkeypatch.setattr(autostart.Path, "home", lambda: tmp_path)
    autostart.set_enabled(True)
    data = plistlib.loads((tmp_path / "Library/LaunchAgents/dev.renan.clack.plist").read_bytes())
    assert data["RunAtLoad"] is True and data["ProgramArguments"][-1] == "--hidden"
    assert autostart.is_enabled()
    autostart.set_enabled(False)
    assert not autostart.is_enabled()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows")
def test_windows_toggle(monkeypatch):
    import winreg
    monkeypatch.setattr(autostart, "NAME", "ClackTesteAutomatico")
    try:
        autostart.set_enabled(True)
        assert autostart.is_enabled()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, autostart.RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, "ClackTesteAutomatico")
        assert value.endswith("--hidden")
    finally:
        autostart.set_enabled(False)
    assert not autostart.is_enabled()
