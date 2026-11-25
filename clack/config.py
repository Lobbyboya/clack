"""Configuração do clack (ligado, pacote, volume), num JSON por usuário."""

import json
import os
import sys
from pathlib import Path

DEFAULTS = {"enabled": True, "pack": "tactile-brown", "volume": 60}


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "Clack"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Clack"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "clack"


def config_path() -> Path:
    return config_dir() / "config.json"


def load(path: Path | None = None) -> dict:
    path = path or config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except (OSError, ValueError):
        return dict(DEFAULTS)
    cfg = {**DEFAULTS, **data}
    # Valores estragados à mão voltam ao padrão em vez de derrubar o app.
    if not isinstance(cfg["enabled"], bool):
        cfg["enabled"] = DEFAULTS["enabled"]
    if not isinstance(cfg["pack"], str):
        cfg["pack"] = DEFAULTS["pack"]
    try:
        cfg["volume"] = max(0, min(100, int(cfg["volume"])))
    except (TypeError, ValueError):
        cfg["volume"] = DEFAULTS["volume"]
    return cfg


def save(cfg: dict, path: Path | None = None):
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    os.replace(tmp, path)  # troca atômica: nunca deixa um JSON pela metade
