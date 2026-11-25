"""Liga/desliga a abertura do app desktop junto com o login do usuário.

- Windows: valor "Clack" em HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
- macOS: LaunchAgent em ~/Library/LaunchAgents/dev.renan.clack.plist
- Linux: ~/.config/autostart/dev.renan.clack.desktop (só para o app Qt; no Linux o
  normal é o daemon pelo systemd)
"""

import contextlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path

NAME = "Clack"
LABEL = "dev.renan.clack"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> list[str]:
    """Como reabrir este app, já escondido na bandeja."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--hidden"]
    main = Path(sys.modules["__main__"].__file__).resolve()
    return [sys.executable, str(main), "--hidden"]


def desktop_exec(cmd: list[str]) -> str:
    """Linha Exec= de um .desktop (a especificação só aceita aspas duplas)."""
    out = []
    for arg in cmd:
        if arg and all(c.isalnum() or c in "-_./=:+," for c in arg):
            out.append(arg)
        else:
            esc = "".join("\\" + c if c in '"`$\\' else c for c in arg)
            out.append(f'"{esc}"'.replace("%", "%%"))
    return " ".join(out)


def _mac_plist_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _linux_desktop_path(home: Path | None = None) -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (home or Path.home()) / ".config")
    return base / "autostart" / f"{LABEL}.desktop"


def is_enabled() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, NAME)
            return True
        except FileNotFoundError:
            return False
    if sys.platform == "darwin":
        return _mac_plist_path().exists()
    return _linux_desktop_path().exists()


def set_enabled(on: bool):
    cmd = launch_command()
    if sys.platform == "win32":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if on:
                winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
            else:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, NAME)
    elif sys.platform == "darwin":
        path = _mac_plist_path()
        if on:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                plistlib.dump({"Label": LABEL, "ProgramArguments": cmd, "RunAtLoad": True,
                               "ProcessType": "Interactive"}, f)
        else:
            path.unlink(missing_ok=True)
    else:
        path = _linux_desktop_path()
        if on:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[Desktop Entry]\nType=Application\nName=Clack\n"
                            f"Exec={desktop_exec(cmd)}\nX-GNOME-Autostart-enabled=true\n")
        else:
            path.unlink(missing_ok=True)
