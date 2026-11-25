import os
import sys
import time
from collections import namedtuple

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("só no Linux", allow_module_level=True)
pytest.importorskip("evdev")

from evdev import ecodes  # noqa: E402

from clack import linux_input  # noqa: E402
from clack.linux_input import IN_ATTRIB, IN_CREATE, IN_DELETE, DirWatch, LinuxListener  # noqa: E402

Ev = namedtuple("Ev", "type code value")


def wait_until(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def wakeups(thread) -> int:
    """Quantas vezes a thread já foi acordada pelo kernel (trocas de contexto)."""
    with open(f"/proc/self/task/{thread.native_id}/status") as f:
        return sum(int(line.split()[1]) for line in f if "ctxt_switches" in line)


class FakeDevice:
    """Dispositivo de entrada falso: um pipe faz o papel do /dev/input/eventN."""

    def __init__(self, path, name, keyboard):
        self.path, self.name, self.keyboard = path, name, keyboard
        self.r, self.w = os.pipe()
        self.queue = []
        self.dead = False

    def fileno(self):
        return self.r

    def capabilities(self):
        keys = [ecodes.KEY_A, ecodes.KEY_SPACE] if self.keyboard else [ecodes.BTN_LEFT]
        return {ecodes.EV_KEY: keys}

    def push(self, code, value):
        self.queue.append(Ev(ecodes.EV_KEY, code, value))
        os.write(self.w, b"x")

    def unplug(self):
        self.dead = True
        os.write(self.w, b"x")

    def read(self):
        os.read(self.r, 4096)
        if self.dead:
            raise OSError(19, "No such device")
        events, self.queue = self.queue, []
        return events

    def close(self):
        pass


class FakeInput:
    """Registro de dispositivos falsos + contagem de quantas vezes cada um foi aberto."""

    def __init__(self, folder):
        self.folder = folder
        self.specs = {}      # nome -> (rótulo, é teclado)
        self.blocked = set()  # nomes sem permissão de leitura
        self.opens = {}
        self.devices = {}

    def add(self, name, label, keyboard, blocked=False):
        self.specs[name] = (label, keyboard)
        if blocked:
            self.blocked.add(name)
        (self.folder / name).touch()

    def open(self, path):
        name = os.path.basename(path)
        self.opens[name] = self.opens.get(name, 0) + 1
        if name in self.blocked:
            raise PermissionError(13, "Permission denied")
        label, keyboard = self.specs[name]
        self.devices[name] = FakeDevice(path, label, keyboard)
        return self.devices[name]

    def list(self, folder):
        return sorted(str(p) for p in self.folder.glob("event*"))


@pytest.fixture
def fake(tmp_path, monkeypatch):
    fi = FakeInput(tmp_path)
    monkeypatch.setattr(linux_input.evdev, "InputDevice", fi.open)
    monkeypatch.setattr(linux_input.evdev, "list_devices", fi.list)
    monkeypatch.setattr(LinuxListener, "INPUT_DIR", str(tmp_path))
    return fi


def test_dirwatch_reports_create_attrib_delete(tmp_path):
    watch = DirWatch(str(tmp_path))
    try:
        f = tmp_path / "event7"
        f.touch()
        os.chmod(f, 0o600)
        f.unlink()
        assert wait_until(lambda: True)
        time.sleep(0.05)
        events = watch.read()
        masks = [m for m, name in events if name == "event7"]
        assert any(m & IN_CREATE for m in masks)
        assert any(m & IN_ATTRIB for m in masks)
        assert any(m & IN_DELETE for m in masks)
        assert watch.read() == []  # nada pendente: não bloqueia
    finally:
        watch.close()


def test_hotplug_keys_and_no_polling(fake):
    fake.add("event0", "Teclado", keyboard=True)
    fake.add("event1", "Mouse", keyboard=False)
    got, changes = [], []
    lst = LinuxListener(lambda c, d: got.append((c, d)), on_change=changes.append)
    lst.start()
    try:
        assert lst.ready.wait(2)
        assert lst.keyboards() == ["Teclado"]
        assert lst.status == "ok"

        kb = fake.devices["event0"]
        kb.push(30, 1)
        kb.push(30, 2)  # repetição automática do kernel: ignorada
        kb.push(30, 0)
        assert wait_until(lambda: len(got) == 2)
        assert got == [(30, True), (30, False)]

        fake.add("event2", "Teclado USB", keyboard=True)  # pluga outro teclado
        assert wait_until(lambda: sorted(lst.keyboards()) == ["Teclado", "Teclado USB"])

        # Parado, a thread do teclado não pode acordar nenhuma vez (é isso que gasta bateria).
        time.sleep(0.1)
        before = wakeups(lst._thread)
        time.sleep(0.5)
        assert wakeups(lst._thread) == before, "a thread acordou sem ter tecla nem dispositivo novo"
        assert fake.opens["event1"] == 1  # o mouse nunca é reaberto
        assert fake.opens["event0"] == 1

        (fake.folder / "event0").unlink()  # desconecta o primeiro
        assert wait_until(lambda: lst.keyboards() == ["Teclado USB"])

        fake.devices["event2"].unplug()  # erro de leitura também remove
        assert wait_until(lambda: lst.keyboards() == [])
        assert wait_until(lambda: lst.status == "no-permission")
        assert any("removido" in c for c in changes)
    finally:
        t0 = time.monotonic()
        lst.stop()
        assert time.monotonic() - t0 < 1, "stop() demorou: o laço não acordou"
    assert not lst._thread.is_alive()


def test_permission_granted_later(fake):
    fake.add("event3", "Teclado", keyboard=True, blocked=True)
    lst = LinuxListener(lambda c, d: None)
    lst.start()
    try:
        assert lst.ready.wait(2)
        assert lst.keyboards() == []
        fake.blocked.discard("event3")
        os.chmod(fake.folder / "event3", 0o640)  # o udev ajustando a permissão
        assert wait_until(lambda: lst.keyboards() == ["Teclado"])
    finally:
        lst.stop()


def test_fallback_without_inotify(fake, monkeypatch):
    def broken(*_a, **_k):
        raise OSError(24, "Too many open files")

    monkeypatch.setattr(linux_input, "DirWatch", broken)
    monkeypatch.setattr(LinuxListener, "FALLBACK_RESCAN_SECONDS", 0.05)
    fake.add("event0", "Teclado", keyboard=True)
    fake.add("event9", "Mouse", keyboard=False)
    lst = LinuxListener(lambda c, d: None)
    lst.start()
    try:
        assert lst.ready.wait(2)
        fake.add("event1", "Outro", keyboard=True)
        assert wait_until(lambda: len(lst.keyboards()) == 2)  # achou pela varredura
        time.sleep(0.3)  # várias varreduras depois...
        assert fake.opens["event9"] == 1  # ...o mouse continua aberto uma vez só
    finally:
        lst.stop()
