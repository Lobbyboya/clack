"""Daemon do Linux: lê os teclados pelo evdev (funciona no Wayland) e toca o som de cada tecla.

O comando `clack` e o painel GTK conversam com ele por um socket Unix.
"""

import json
import os
import selectors
import socket
from pathlib import Path

from . import config
from .audio import Mixer
from .linux_input import LinuxListener
from .packs import Pack, list_packs

RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SOCKET_PATH = RUNTIME / "clack.sock"


def log(msg: str):
    print(msg, flush=True)


class Daemon:
    def __init__(self):
        self.cfg = config.load()
        self.mixer = Mixer()
        self.mixer.volume = self.cfg["volume"] / 100
        self.pack = Pack(self.cfg["pack"])
        self.keyboard = LinuxListener(self.on_key, on_change=log)

    def on_key(self, code: int, down: bool):
        if not self.cfg["enabled"]:
            return
        sound = self.pack.sound_for(code, "down" if down else "up")
        if sound:
            self.mixer.play(sound.pick())

    # --- controle (comando clack) -----------------------------------------
    def on_control(self, server: socket.socket):
        conn, _ = server.accept()
        with conn:
            try:
                reply = self.handle(json.loads(conn.recv(4096)))
            except Exception as exc:  # resposta de erro para o cliente
                reply = {"ok": False, "error": str(exc)}
            conn.sendall(json.dumps(reply).encode())

    def handle(self, cmd: dict) -> dict:
        action = cmd.get("action")
        if action == "on":
            self.cfg["enabled"] = True
        elif action == "off":
            self.cfg["enabled"] = False
        elif action == "toggle":
            self.cfg["enabled"] = not self.cfg["enabled"]
        elif action == "pack":
            name = cmd["value"]
            if name not in list_packs():
                return {"ok": False, "error": f"pacote desconhecido: {name}"}
            self.pack = Pack(name)
            self.cfg["pack"] = name
        elif action == "volume":
            vol = max(0, min(100, int(cmd["value"])))
            self.cfg["volume"] = vol
            self.mixer.volume = vol / 100
        elif action != "status":
            return {"ok": False, "error": f"comando desconhecido: {action}"}
        if action != "status":
            config.save(self.cfg)
        return {"ok": True, **self.cfg, "teclados": self.keyboard.keyboards()}

    # --- laço principal ---------------------------------------------------
    def run(self):
        SOCKET_PATH.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(SOCKET_PATH))
        server.listen()
        sel = selectors.DefaultSelector()
        sel.register(server, selectors.EVENT_READ)

        self.keyboard.start()
        self.keyboard.ready.wait(5)
        if not self.keyboard.keyboards():
            log("nenhum teclado legível: você está no grupo 'input'? "
                "(depois do usermod é preciso sair e entrar na sessão)")
        self.mixer.start()
        log(f"clack rodando, pacote {self.pack.title}, volume {self.cfg['volume']}")
        try:
            while True:
                for _key, _ in sel.select():  # sem prazo: só acorda quando alguém fala com o daemon
                    self.on_control(server)
        except KeyboardInterrupt:
            pass
        finally:
            self.keyboard.stop()
            self.mixer.stop()
            server.close()
            SOCKET_PATH.unlink(missing_ok=True)
