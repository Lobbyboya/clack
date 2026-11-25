#!/usr/bin/env bash
# Remove o Clack instalado pelo install.sh. A configuração (~/.config/clack) fica.
set -euo pipefail

DEST="${CLACK_HOME:-$HOME/.local/share/clack}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ -f "$UNIT_DIR/clack.service" ]] && grep -q "$DEST/bin/clack" "$UNIT_DIR/clack.service"; then
    systemctl --user disable --now clack.service 2>/dev/null || true
    rm -f "$UNIT_DIR/clack.service"
    systemctl --user daemon-reload 2>/dev/null || true
fi
[[ "$(readlink "$HOME/.local/bin/clack" 2>/dev/null)" == "$DEST/bin/clack" ]] && rm -f "$HOME/.local/bin/clack"
grep -qs "$DEST/gui/clack_gui.py" "$APPS_DIR/dev.renan.ClackControl.desktop" \
    && rm -f "$APPS_DIR/dev.renan.ClackControl.desktop"
if [[ -f "$DEST/clack/daemon.py" ]]; then
    rm -rf "$DEST"
fi
echo "Clack removido. Sua configuração continua em ~/.config/clack (apague à mão se quiser)."
