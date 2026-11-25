"""Lê os teclados pelo evdev (funciona no Wayland) e toca o som de cada tecla."""

import json
import os
import selectors
import socket
import time
from pathlib import Path

import evdev
from evdev import ecodes

from . import config
from .audio import Mixer
from .packs import Pack, list_packs

RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SOCKET_PATH = RUNTIME / "clack.sock"
RESCAN_SECONDS = 2.0


def load_config() -> dict:
    return config.load()


def save_config(cfg: dict):
    config.save(cfg)


def is_keyboard(dev: evdev.InputDevice) -> bool:
    keys = dev.capabilities().get(ecodes.EV_KEY, [])
    return ecodes.KEY_A in keys and ecodes.KEY_SPACE in keys


class Daemon:
    def __init__(self):
        self.cfg = load_config()
        self.mixer = Mixer()
        self.mixer.volume = self.cfg["volume"] / 100
        self.pack = Pack(self.cfg["pack"])
        self.sel = selectors.DefaultSelector()
        self.devices: dict[str, evdev.InputDevice] = {}

    # --- teclados ---------------------------------------------------------
    def rescan(self):
        for path in evdev.list_devices():
            if path in self.devices:
                continue
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            if is_keyboard(dev):
                self.devices[path] = dev
                self.sel.register(dev, selectors.EVENT_READ, self.on_key)
                print(f"teclado: {dev.name} ({path})", flush=True)
            else:
                dev.close()

    def drop(self, dev):
        self.sel.unregister(dev)
        self.devices.pop(dev.path, None)
        print(f"teclado removido: {dev.name}", flush=True)

    def on_key(self, dev):
        try:
            events = list(dev.read())
        except OSError:
            self.drop(dev)
            return
        if not self.cfg["enabled"]:
            return
        for ev in events:
            # value: 1 = apertou, 0 = soltou, 2 = repetição automática (ignorada)
            if ev.type == ecodes.EV_KEY and ev.value in (0, 1):
                sound = self.pack.sound_for(ev.code, "down" if ev.value else "up")
                if sound:
                    self.mixer.play(sound.pick())

    # --- controle (comando clack) -----------------------------------------
    def on_control(self, server):
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
            save_config(self.cfg)
        return {"ok": True, **self.cfg, "teclados": [d.name for d in self.devices.values()]}

    # --- laço principal ---------------------------------------------------
    def run(self):
        SOCKET_PATH.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(SOCKET_PATH))
        server.listen()
        self.sel.register(server, selectors.EVENT_READ, self.on_control)

        self.rescan()
        if not self.devices:
            print("nenhum teclado legível: você está no grupo 'input'? "
                  "(depois do usermod é preciso sair e entrar na sessão)", flush=True)
        self.mixer.start()
        print(f"clack rodando, pacote {self.pack.title}, volume {self.cfg['volume']}", flush=True)

        last_scan = time.monotonic()
        try:
            while True:
                for key, _ in self.sel.select(timeout=RESCAN_SECONDS):
                    key.data(key.fileobj)
                if time.monotonic() - last_scan >= RESCAN_SECONDS:
                    self.rescan()
                    last_scan = time.monotonic()
        except KeyboardInterrupt:
            pass
        finally:
            self.mixer.stop()
            server.close()
            SOCKET_PATH.unlink(missing_ok=True)
