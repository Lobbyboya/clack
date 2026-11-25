"""Motor do app desktop (Windows/macOS): teclado + mixer + pacote + config, num processo só."""

import contextlib
import sys
import threading
from pathlib import Path

from . import config, listeners
from .packs import Pack, list_packs


class Engine:
    def __init__(self, cfg_path: Path | None = None, mixer=None, listener_factory=None):
        self.cfg_path = cfg_path
        self.cfg = config.load(cfg_path)
        self.audio_error = ""
        self._lock = threading.Lock()
        self._mixer = mixer
        self._listener_factory = listener_factory or listeners.create
        self.listener = None
        visible = [p for p in list_packs() if not p.startswith("_")]
        if self.cfg["pack"] not in visible:
            self.cfg["pack"] = config.DEFAULTS["pack"] if config.DEFAULTS["pack"] in visible else visible[0]
        self.pack = Pack(self.cfg["pack"])

    # --- ciclo de vida ----------------------------------------------------------
    def start(self):
        if self._mixer is None:
            try:
                from .audio import Mixer
                self._mixer = Mixer()
                self._mixer.start()
            except Exception as exc:  # sem placa de som, PortAudio ausente etc.
                self._mixer = None
                self.audio_error = str(exc) or exc.__class__.__name__
        if self._mixer is not None:
            self._mixer.volume = self.cfg["volume"] / 100
        self.listener = self._listener_factory(self.on_key)
        try:
            self.listener.start()
        except Exception as exc:
            self.listener.status = listeners.ERROR
            self.listener.detail = str(exc) or exc.__class__.__name__

    def stop(self):
        if self.listener is not None:
            with contextlib.suppress(Exception):
                self.listener.stop()
        if self._mixer is not None:
            with contextlib.suppress(Exception):
                self._mixer.stop()

    # --- teclas --------------------------------------------------------------------
    def on_key(self, code: int, down: bool):
        if not self.cfg["enabled"] or self._mixer is None:
            return
        with self._lock:
            pack = self.pack
        sound = pack.sound_for(code, "down" if down else "up")
        if sound:
            self._mixer.play(sound.pick())

    def preview(self):
        """Toca um aperto e uma soltura do pacote atual (mesmo com o som desligado)."""
        if self._mixer is None:
            return
        with self._lock:
            pack = self.pack
        for kind in ("down", "up"):
            sound = pack.sound_for(30, kind)  # tecla A
            if sound:
                self._mixer.play(sound.pick())

    # --- ajustes -------------------------------------------------------------------
    def set_enabled(self, on: bool):
        self.cfg["enabled"] = bool(on)
        self._save()

    def set_volume(self, vol: int):
        vol = max(0, min(100, int(vol)))
        self.cfg["volume"] = vol
        if self._mixer is not None:
            self._mixer.volume = vol / 100
        self._save()

    def set_pack(self, name: str):
        if name not in list_packs() or name.startswith("_"):
            raise ValueError(f"pacote desconhecido: {name}")
        pack = Pack(name)
        with self._lock:
            self.pack = pack
        self.cfg["pack"] = name
        self._save()

    def _save(self):
        try:
            config.save(self.cfg, self.cfg_path)
        except OSError as exc:
            print(f"clack: não consegui salvar a configuração: {exc}", file=sys.stderr)
