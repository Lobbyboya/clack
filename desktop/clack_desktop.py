"""Ponto de entrada do app desktop (Windows/macOS). É este arquivo que o PyInstaller empacota."""

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    # Rodando do código-fonte: deixa o pacote "clack" importável.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clack.qt_app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
