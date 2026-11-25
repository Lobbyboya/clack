# Receita do PyInstaller: gera dist/Clack (Windows/Linux) ou dist/Clack.app (macOS).
# Uso: pyinstaller desktop/clack.spec --noconfirm
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = re.search(r'__version__ = "(.+)"', (ROOT / "clack" / "__init__.py").read_text()).group(1)

datas = [
    (str(ROOT / "packs"), "packs"),
    (str(ROOT / "assets" / "icon.png"), "assets"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "SOUNDS-LICENSES.md"), "."),
]
ICON = {"win32": "icon.ico", "darwin": "icon.icns"}.get(sys.platform, "icon.png")
ICON_PATH = str(ROOT / "assets" / ICON)
hiddenimports = []
if sys.platform == "win32":
    hiddenimports += ["pynput.keyboard._win32", "pynput.mouse._win32", "pynput._util.win32"]

a = Analysis(
    [str(ROOT / "desktop" / "clack_desktop.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Clack",
    console=False,
    icon=ICON_PATH,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Clack", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Clack.app",
        icon=ICON_PATH,
        bundle_identifier="dev.renan.clack",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "Clack",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        },
    )
