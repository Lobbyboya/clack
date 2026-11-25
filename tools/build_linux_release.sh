#!/usr/bin/env bash
# Monta dist/clack-<versão>-linux.tar.gz a partir do commit atual (só arquivos versionados).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' clack/__init__.py)"
NAME="clack-$VERSION-linux"
mkdir -p dist
git archive --format=tar.gz --prefix="$NAME/" -o "dist/$NAME.tar.gz" HEAD -- \
    clack packs gui bin assets clack.service requirements-linux.txt \
    install.sh uninstall.sh LICENSE SOUNDS-LICENSES.md README.md
echo "dist/$NAME.tar.gz"
