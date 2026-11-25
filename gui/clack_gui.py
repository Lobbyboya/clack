#!/usr/bin/env python3
"""Clack Control: painel GTK4/libadwaita para o daemon do clack (visual glass)."""

import json
import os
import socket
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = "dev.renan.ClackControl"
ROOT = Path(__file__).resolve().parent.parent
PACKS_DIR = ROOT / "packs"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SOCKET_PATH = RUNTIME / "clack.sock"
SERVICE = "clack.service"
POLL_MS = 2000

CSS = """
window.clack { background-color: transparent; }

.aurora {
  background-color: alpha(#0e0c1e, 0.90);
  background-image:
    radial-gradient(circle farthest-side at 10% 0%, alpha(#7c5cff, 0.42), transparent),
    radial-gradient(circle farthest-side at 100% 35%, alpha(#00c6ff, 0.26), transparent),
    radial-gradient(circle farthest-side at 40% 105%, alpha(#ff4fa3, 0.22), transparent);
  color: #f1effa;
}
.aurora headerbar { background: transparent; box-shadow: none; color: #f1effa; }

.glass {
  background-color: alpha(white, 0.06);
  border: 1px solid alpha(white, 0.11);
  border-radius: 22px;
  box-shadow: inset 0 1px alpha(white, 0.10), 0 10px 30px alpha(black, 0.28);
  padding: 18px;
}
.section { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: alpha(white, 0.55); }
.dim { color: alpha(white, 0.60); }

/* botão de ligar */
.power {
  min-width: 104px; min-height: 104px; border-radius: 999px; padding: 0;
  background: alpha(white, 0.07); border: 1px solid alpha(white, 0.16);
  color: alpha(white, 0.55); box-shadow: inset 0 1px alpha(white, 0.12);
  transition: all 250ms ease;
}
.power:hover { background: alpha(white, 0.12); }
.power:checked {
  background-image: linear-gradient(135deg, #7c5cff, #00c6ff);
  border-color: alpha(white, 0.35); color: white;
  box-shadow: 0 0 36px alpha(#7c5cff, 0.65), 0 0 70px alpha(#00c6ff, 0.25);
}
.hero-title { font-size: 26px; font-weight: 800; }

/* volume */
.big-num { font-size: 38px; font-weight: 800; font-feature-settings: "tnum"; }
scale.glow trough { min-height: 8px; border-radius: 99px; background: alpha(white, 0.12); border: none; }
scale.glow highlight {
  border-radius: 99px; border: none;
  background-image: linear-gradient(90deg, #7c5cff, #00c6ff);
}
scale.glow slider {
  min-width: 22px; min-height: 22px; border-radius: 99px; background: white; border: none;
  box-shadow: 0 0 14px alpha(#00c6ff, 0.7), 0 2px 6px alpha(black, 0.4);
}

/* pacotes */
flowbox.packs { background: transparent; }
flowbox.packs > flowboxchild {
  padding: 12px 14px; border-radius: 16px;
  background-color: alpha(white, 0.05); border: 1px solid alpha(white, 0.08);
  transition: all 200ms ease;
}
flowbox.packs > flowboxchild:hover { background-color: alpha(white, 0.10); }
flowbox.packs > flowboxchild:selected {
  background-image: linear-gradient(135deg, alpha(#7c5cff, 0.55), alpha(#00c6ff, 0.35));
  border-color: alpha(white, 0.35); color: white;
  box-shadow: 0 0 20px alpha(#7c5cff, 0.40);
}
.tile-title { font-weight: 700; }
.tile-desc { font-size: 11px; color: alpha(white, 0.62); }

entry.glass-entry {
  min-height: 46px; border-radius: 14px; padding: 0 14px;
  background-color: alpha(black, 0.22); border: 1px solid alpha(white, 0.10);
  color: white; box-shadow: none;
}
entry.glass-entry:focus-within { border-color: alpha(#00c6ff, 0.7); box-shadow: 0 0 0 3px alpha(#00c6ff, 0.18); }

/* serviço */
.dot { min-width: 10px; min-height: 10px; border-radius: 99px; background: #6b6880; }
.dot.on { background: #3ce6a0; box-shadow: 0 0 10px #3ce6a0; }
button.pill {
  border-radius: 99px; padding: 6px 18px; font-weight: 700; border: 1px solid alpha(white, 0.15);
  background: alpha(white, 0.08); color: white;
}
button.pill:hover { background: alpha(white, 0.16); }
button.pill.go { background-image: linear-gradient(135deg, #7c5cff, #00c6ff); border-color: transparent; }
button.pill.stop { background: alpha(#ff4f6d, 0.25); border-color: alpha(#ff4f6d, 0.5); }
button.round { border-radius: 99px; min-width: 34px; min-height: 34px; background: alpha(white, 0.08); color: white; }
button.round:hover { background: alpha(white, 0.16); }
switch { background: alpha(white, 0.14); }
switch:checked { background-image: linear-gradient(90deg, #7c5cff, #00c6ff); }

.chip {
  padding: 6px 12px; border-radius: 99px; font-size: 12px;
  background: alpha(white, 0.07); border: 1px solid alpha(white, 0.10);
}
.chip.warn { background: alpha(#ffb84f, 0.15); border-color: alpha(#ffb84f, 0.4); }
"""


def send(action: str, value=None) -> dict | None:
    """Fala com o daemon pelo socket. None = daemon fora do ar."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect(str(SOCKET_PATH))
            s.sendall(json.dumps({"action": action, "value": value}).encode())
            return json.loads(s.recv(65536))
    except (OSError, json.JSONDecodeError):
        return None


def systemctl(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args, SERVICE],
                          capture_output=True, text=True)


def load_packs() -> list[tuple[str, str, str]]:
    """(nome da pasta, título, descrição), sem os pacotes ocultos (_mouse)."""
    packs = []
    for meta_path in sorted(PACKS_DIR.glob("*/pack.json")):
        name = meta_path.parent.name
        if name.startswith("_"):
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError):
            meta = {}
        packs.append((name, meta.get("name", name), meta.get("description", "")))
    return packs


def label(text="", *classes, xalign=0.0, **kw) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=xalign, **kw)
    for c in classes:
        lbl.add_css_class(c)
    return lbl


def card(title: str | None = None) -> tuple[Gtk.Box, Gtk.Box]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.add_css_class("glass")
    if title:
        box.append(label(title.upper(), "section"))
    return box, box


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Clack", default_width=500, default_height=820)
        self.add_css_class("clack")
        self.packs = load_packs()
        self.updating = False          # evita reenviar ao daemon o que veio dele
        self.volume_timer = 0
        self.last_keyboards = object()

        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        view.add_css_class("aurora")
        header = Adw.HeaderBar()
        header.set_title_widget(label("Clack", "tile-title", xalign=0.5))
        view.add_top_bar(header)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        clamp = Adw.Clamp(maximum_size=560, margin_top=6, margin_bottom=24,
                          margin_start=16, margin_end=16)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        clamp.set_child(col)
        scroller.set_child(clamp)
        view.set_content(scroller)

        col.append(self.build_hero())
        self.sound_cards = [self.build_volume(), self.build_packs(), self.build_test()]
        for c in self.sound_cards:
            col.append(c)
        col.append(self.build_service())

        self.refresh()
        GLib.timeout_add(POLL_MS, self.refresh)

    # --- construção ------------------------------------------------------------
    def build_hero(self):
        box, _ = card()
        box.set_spacing(10)
        box.set_margin_top(4)
        self.power = Gtk.ToggleButton(halign=Gtk.Align.CENTER, margin_top=8)
        self.power.add_css_class("power")
        icon = Gtk.Image.new_from_icon_name("system-shutdown-symbolic")
        icon.set_pixel_size(42)
        self.power.set_child(icon)
        self.power.set_tooltip_text("Ligar ou desligar os sons")
        self.power.connect("toggled", self.on_enabled)
        box.append(self.power)
        self.hero_title = label("", "hero-title", xalign=0.5, margin_top=6)
        self.hero_sub = label("", "dim", xalign=0.5)
        box.append(self.hero_title)
        box.append(self.hero_sub)
        return box

    def build_volume(self):
        box, _ = card("Volume")
        row = Gtk.Box(spacing=12)
        self.vol_icon = Gtk.Image.new_from_icon_name("audio-volume-medium-symbolic")
        self.vol_icon.set_pixel_size(22)
        self.vol_icon.add_css_class("dim")
        self.vol_label = label("", "big-num", hexpand=True)
        row.append(self.vol_label)
        row.append(self.vol_icon)
        box.append(row)
        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol_scale.add_css_class("glow")
        self.vol_scale.set_draw_value(False)
        self.vol_scale.connect("value-changed", self.on_volume)
        box.append(self.vol_scale)
        return box

    def build_packs(self):
        box, _ = card("Pacote de som")
        self.flow = Gtk.FlowBox(homogeneous=True, max_children_per_line=2, min_children_per_line=2,
                                row_spacing=10, column_spacing=10,
                                selection_mode=Gtk.SelectionMode.SINGLE,
                                activate_on_single_click=True)
        self.flow.add_css_class("packs")
        self.tiles = []
        for _, title, desc in self.packs:
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            tile.append(label(title, "tile-title"))
            d = label(desc, "tile-desc", wrap=True, lines=2,
                      ellipsize=3, max_width_chars=1)  # 3 = Pango.EllipsizeMode.END
            d.set_tooltip_text(desc)
            tile.append(d)
            self.flow.append(tile)
            self.tiles.append(tile.get_parent())
        self.flow.connect("selected-children-changed", self.on_pack)
        box.append(self.flow)
        return box

    def build_test(self):
        box, _ = card("Testar")
        entry = Gtk.Entry(placeholder_text="Digite aqui para ouvir o pacote…")
        entry.add_css_class("glass-entry")
        box.append(entry)
        return box

    def build_service(self):
        box, _ = card("Serviço")
        row = Gtk.Box(spacing=10)
        self.dot = Gtk.Box(valign=Gtk.Align.CENTER)
        self.dot.add_css_class("dot")
        self.svc_label = label("", "tile-title", hexpand=True)
        restart = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER,
                             tooltip_text="Reiniciar o daemon")
        restart.add_css_class("round")
        restart.connect("clicked", lambda *_: self.run_systemctl("restart", "Daemon reiniciado"))
        self.svc_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.svc_button.add_css_class("pill")
        self.svc_button.connect("clicked", self.on_service_button)
        for w in (self.dot, self.svc_label, restart, self.svc_button):
            row.append(w)
        box.append(row)

        auto = Gtk.Box(spacing=10)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        txt.append(label("Iniciar com a sessão"))
        txt.append(label("Abre o clack sozinho ao entrar no GNOME", "tile-desc"))
        self.autostart = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.autostart.connect("notify::active", self.on_autostart)
        auto.append(txt)
        auto.append(self.autostart)
        box.append(auto)

        box.append(label("TECLADOS", "section", margin_top=4))
        self.kbd_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, row_spacing=6,
                                   column_spacing=6, max_children_per_line=3)
        box.append(self.kbd_box)
        return box

    # --- leitura do estado -------------------------------------------------------
    def refresh(self) -> bool:
        state = send("status")
        running = bool(state and state.get("ok"))
        self.updating = True
        try:
            self.power.set_sensitive(running)
            for c in self.sound_cards:
                c.set_sensitive(running)
            names = [n for n, _, _ in self.packs]
            if running:
                self.power.set_active(state["enabled"])
                if not self.volume_timer:      # não briga com o usuário arrastando
                    self.vol_scale.set_value(state["volume"])
                self.update_volume_label()
                if state["pack"] in names:
                    self.flow.select_child(self.tiles[names.index(state["pack"])])
                title = next((t for n, t, _ in self.packs if n == state["pack"]), state["pack"])
                self.hero_title.set_label("Ligado" if state["enabled"] else "Desligado")
                self.hero_sub.set_label(f"{title} · volume {state['volume']}%")
            else:
                self.power.set_active(False)
                self.hero_title.set_label("Daemon parado")
                self.hero_sub.set_label("Inicie o serviço lá embaixo")

            self.svc_label.set_label("Rodando" if running else "Parado")
            if running:
                self.dot.add_css_class("on")
            else:
                self.dot.remove_css_class("on")
            self.svc_button.set_label("Parar" if running else "Iniciar")
            self.svc_button.remove_css_class("go" if running else "stop")
            self.svc_button.add_css_class("stop" if running else "go")
            self.autostart.set_active(systemctl("is-enabled").stdout.strip() == "enabled")
            self.show_keyboards(state.get("teclados", []) if running else None)
        finally:
            self.updating = False
        return True

    def show_keyboards(self, names):
        if names == self.last_keyboards:
            return
        self.last_keyboards = names
        self.kbd_box.remove_all()
        if names is None:
            items = [("Daemon parado", "dialog-information-symbolic", False)]
        elif not names:
            items = [("Nenhum teclado legível (grupo 'input'?)", "dialog-warning-symbolic", True)]
        else:
            items = [(n, "input-keyboard-symbolic", False) for n in names]
        for title, icon, warn in items:
            chip = Gtk.Box(spacing=6)
            chip.add_css_class("chip")
            if warn:
                chip.add_css_class("warn")
            chip.append(Gtk.Image.new_from_icon_name(icon))
            chip.append(label(title))
            self.kbd_box.append(chip)

    def update_volume_label(self):
        v = int(self.vol_scale.get_value())
        self.vol_label.set_label(f"{v}%")
        icon = ("audio-volume-muted-symbolic" if v == 0 else
                "audio-volume-low-symbolic" if v < 34 else
                "audio-volume-medium-symbolic" if v < 67 else "audio-volume-high-symbolic")
        self.vol_icon.set_from_icon_name(icon)

    # --- ações -------------------------------------------------------------------
    def command(self, action, value=None):
        reply = send(action, value)
        if reply is None:
            self.toast("O daemon não está rodando")
        elif not reply.get("ok"):
            self.toast(f"Erro: {reply.get('error')}")
        else:
            GLib.idle_add(lambda: self.refresh() and False)

    def on_enabled(self, button):
        if not self.updating:
            self.command("on" if button.get_active() else "off")

    def on_volume(self, _scale):
        self.update_volume_label()
        if self.updating:
            return
        if self.volume_timer:
            GLib.source_remove(self.volume_timer)
        self.volume_timer = GLib.timeout_add(150, self.flush_volume)

    def flush_volume(self):
        self.volume_timer = 0
        self.command("volume", int(self.vol_scale.get_value()))
        return False

    def on_pack(self, flow):
        if self.updating:
            return
        sel = flow.get_selected_children()
        if sel:
            self.command("pack", self.packs[sel[0].get_index()][0])

    def on_service_button(self, _):
        if send("status") is None:
            self.run_systemctl("start", "Daemon iniciado")
        else:
            self.run_systemctl("stop", "Daemon parado")

    def on_autostart(self, switch, _):
        if not self.updating:
            on = switch.get_active()
            self.run_systemctl("enable" if on else "disable",
                               "Inicia com a sessão" if on else "Não inicia mais sozinho")

    def run_systemctl(self, verb, ok_msg):
        res = systemctl(verb)
        self.toast(ok_msg if res.returncode == 0 else f"systemctl {verb} falhou: {res.stderr.strip()}")
        GLib.timeout_add(600, lambda: self.refresh() and False)

    def toast(self, msg):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(msg), timeout=2))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.get_active_window() or Window(self)
        win.present()


if __name__ == "__main__":
    raise SystemExit(App().run(None))
