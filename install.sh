#!/usr/bin/env bash
# Instala o Clack no Linux (daemon + painel GTK) para o usuário atual, sem sudo.
#   ./install.sh               instala em ~/.local/share/clack e liga o serviço
#   ./install.sh --no-service  instala sem mexer no systemd
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLACK_HOME:-$HOME/.local/share/clack}"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
WITH_SERVICE=1
[[ "${1:-}" == "--no-service" ]] && WITH_SERVICE=0

say()  { printf '\033[1;35m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; exit 1; }

hint_pkg() {  # sugere o comando de instalação da distro
    if command -v pacman >/dev/null; then echo "sudo pacman -S $1"
    elif command -v apt >/dev/null; then echo "sudo apt install $2"
    elif command -v dnf >/dev/null; then echo "sudo dnf install $3"
    else echo "instale: $1"; fi
}

# --- requisitos ---------------------------------------------------------------------
command -v python3 >/dev/null || die "python3 não encontrado. $(hint_pkg python python3 python3)"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || die "o Clack precisa do Python 3.11 ou mais novo."
python3 -c 'import venv, ensurepip' 2>/dev/null \
    || die "falta o módulo venv do Python. $(hint_pkg python python3-venv python3)"

# --- arquivos -------------------------------------------------------------------------
if [[ "$SRC" != "$DEST" ]]; then
    say "Copiando para $DEST"
    mkdir -p "$DEST"
    for item in clack packs gui bin assets clack.service requirements-linux.txt \
                install.sh uninstall.sh LICENSE SOUNDS-LICENSES.md README.md; do
        rm -rf "${DEST:?}/$item"
        cp -r "$SRC/$item" "$DEST/"
    done
fi
chmod +x "$DEST/bin/clack" "$DEST/gui/clack_gui.py" "$DEST/install.sh" "$DEST/uninstall.sh"

# --- ambiente Python ------------------------------------------------------------------
# --system-site-packages: aproveita o python-evdev da distro, que já vem compilado.
say "Preparando o ambiente Python"
if [[ ! -x "$DEST/.venv/bin/python" ]]; then
    python3 -m venv --system-site-packages "$DEST/.venv"
fi
PY="$DEST/.venv/bin/python"
"$PY" -m pip install --quiet --disable-pip-version-check -r "$DEST/requirements-linux.txt" || die \
"não consegui instalar as dependências. O evdev precisa ser compilado quando a distro não tem o pacote:
    $(hint_pkg python-evdev python3-evdev python3-evdev)
ou o compilador: $(hint_pkg 'base-devel linux-api-headers' 'build-essential python3-dev' 'gcc python3-devel')
Depois rode ./install.sh de novo."

if ! "$PY" -c 'import sounddevice' 2>/dev/null; then
    die "falta a biblioteca PortAudio. $(hint_pkg portaudio libportaudio2 portaudio)"
fi
(cd "$DEST" && "$PY" -c 'import clack.daemon') || die "a instalação ficou incompleta (clack.daemon não importa)."

# --- comando, atalho e serviço --------------------------------------------------------
mkdir -p "$BIN_DIR" "$APPS_DIR"
ln -sfn "$DEST/bin/clack" "$BIN_DIR/clack"
say "Comando 'clack' em $BIN_DIR/clack"

cat > "$APPS_DIR/dev.renan.ClackControl.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Clack
Comment=Controle dos sons de teclado mecânico
Exec=/usr/bin/env python3 "$DEST/gui/clack_gui.py"
Icon=$DEST/assets/icon.png
Terminal=false
Categories=Utility;
Keywords=teclado;som;keyboard;sound;
StartupWMClass=dev.renan.ClackControl
DESKTOP
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true
if ! /usr/bin/env python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' 2>/dev/null; then
    warn "o painel gráfico precisa de GTK4 + libadwaita para Python: $(hint_pkg 'python-gobject gtk4 libadwaita' 'python3-gi gir1.2-adw-1' 'python3-gobject libadwaita')"
fi

if [[ $WITH_SERVICE == 1 ]]; then
    mkdir -p "$UNIT_DIR"
    sed "s|%h/clack-linux|$DEST|" "$DEST/clack.service" > "$UNIT_DIR/clack.service"
    systemctl --user daemon-reload
    systemctl --user enable --now clack.service
    systemctl --user restart clack.service
    say "Serviço clack ligado (systemctl --user status clack)"
fi

if ! id -nG | tr ' ' '\n' | grep -qx input; then
    warn "seu usuário não está no grupo 'input', então o Clack não consegue ler o teclado. Rode:
    sudo usermod -aG input \$USER
e saia e entre de novo na sessão."
fi
say "Pronto! Abra o 'Clack' no menu de aplicativos ou use: clack status"
