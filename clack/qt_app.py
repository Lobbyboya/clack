"""Clack para Windows e macOS: janela Qt com visual glass + ícone na bandeja.

O motor (teclado + som) roda no mesmo processo. Fechar a janela só a esconde: o
Clack continua tocando e fica na bandeja (Windows) ou na barra de menus (macOS).
"""

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTextLayout,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import autostart, listeners
from .engine import Engine
from .packs import PACKS_DIR

APP_NAME = "Clack"
SERVER_NAME = "dev.renan.clack.desktop"
VIOLET = QColor("#7c5cff")
CYAN = QColor("#00c6ff")
TEXT = QColor("#f1effa")


def resource(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def pack_infos() -> list[tuple[str, str, str]]:
    import json
    out = []
    for meta_path in sorted(PACKS_DIR.glob("*/pack.json")):
        name = meta_path.parent.name
        if name.startswith("_"):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        out.append((name, meta.get("name", name), meta.get("description", "")))
    return out


QSS = """
* { color: #f1effa; font-size: 13px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; height: 0; }

QFrame#card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.11);
  border-radius: 22px;
}
QLabel#section { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: rgba(255,255,255,0.55); }
QLabel#heroTitle { font-size: 26px; font-weight: 800; }
QLabel#dim, #desc { color: rgba(255,255,255,0.62); }
#desc { font-size: 11px; }
QLabel#bigNum { font-size: 38px; font-weight: 800; }
QLabel#tileTitle, QLabel#strong { font-weight: 700; }

QFrame#tile {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
}
QFrame#tile:hover { background: rgba(255,255,255,0.10); }
QFrame#tile[selected="true"] {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
              stop:0 rgba(124,92,255,0.60), stop:1 rgba(0,198,255,0.38));
  border: 1px solid rgba(255,255,255,0.38);
}
QFrame#tile[selected="true"] #desc { color: rgba(255,255,255,0.85); }

QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: rgba(255,255,255,0.12); }
QSlider::sub-page:horizontal {
  height: 8px; border-radius: 4px;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c5cff, stop:1 #00c6ff);
}
QSlider::handle:horizontal {
  width: 22px; height: 22px; margin: -7px 0; border-radius: 11px;
  background: white; border: 2px solid rgba(0,198,255,0.55);
}

QLineEdit {
  min-height: 44px; border-radius: 14px; padding: 0 14px;
  background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.10);
  selection-background-color: #7c5cff;
}
QLineEdit:focus { border: 1px solid rgba(0,198,255,0.75); }

QPushButton {
  border-radius: 17px; padding: 8px 18px; font-weight: 700;
  background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
}
QPushButton:hover { background: rgba(255,255,255,0.16); }
QPushButton:pressed { background: rgba(255,255,255,0.22); }
QPushButton#go {
  border: none;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c5cff, stop:1 #00c6ff);
}
QPushButton#danger { background: rgba(255,79,109,0.22); border: 1px solid rgba(255,79,109,0.55); }
QPushButton#danger:hover { background: rgba(255,79,109,0.35); }

QLabel#chipWarn {
  padding: 8px 12px; border-radius: 12px; font-size: 12px;
  background: rgba(255,184,79,0.14); border: 1px solid rgba(255,184,79,0.45);
}
QMenu { background: #1d1a33; border: 1px solid rgba(255,255,255,0.15); padding: 6px; border-radius: 10px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: rgba(124,92,255,0.55); }
QToolTip { background: #1d1a33; color: #f1effa; border: 1px solid rgba(255,255,255,0.2); }
"""


# --- desenhos --------------------------------------------------------------------------
def draw_power_icon(p: QPainter, center: QPointF, r: float, color: QColor):
    pen = QPen(color, max(2.0, r * 0.22), Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    rect = QRectF(center.x() - r, center.y() - r, 2 * r, 2 * r)
    p.drawArc(rect, int(120 * 16), int(300 * 16))          # anel aberto no topo
    p.drawLine(QPointF(center.x(), center.y() - r * 1.15), QPointF(center.x(), center.y() - r * 0.15))


class Aurora(QWidget):
    """Fundo escuro com manchas de luz roxa, ciano e rosa."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(14, 12, 30))
        for cx, cy, rad, color, alpha in ((0.10, 0.0, 0.95, "#7c5cff", 110),
                                          (1.0, 0.35, 0.75, "#00c6ff", 70),
                                          (0.40, 1.05, 0.85, "#ff4fa3", 55)):
            g = QRadialGradient(QPointF(cx * w, cy * h), rad * max(w, h) * 0.75)
            c = QColor(color)
            c.setAlpha(alpha)
            g.setColorAt(0, c)
            c2 = QColor(color)
            c2.setAlpha(0)
            g.setColorAt(1, c2)
            p.fillRect(self.rect(), g)


class PowerButton(QAbstractButton):
    SIZE = 150
    CIRCLE = 104

    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Ligar ou desligar os sons")
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def hitButton(self, pos):
        c = QPointF(self.width() / 2, self.height() / 2)
        return math.hypot(pos.x() - c.x(), pos.y() - c.y()) <= self.CIRCLE / 2

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.CIRCLE / 2
        on = self.isChecked() and self.isEnabled()
        if on:  # brilho em volta
            g = QRadialGradient(c, self.SIZE / 2)
            glow = QColor(VIOLET)
            glow.setAlpha(150)
            g.setColorAt(r / (self.SIZE / 2) * 0.9, glow)
            glow.setAlpha(0)
            g.setColorAt(1.0, glow)
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, self.SIZE / 2, self.SIZE / 2)
        circle = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        if on:
            lg = QLinearGradient(circle.topLeft(), circle.bottomRight())
            lg.setColorAt(0, VIOLET)
            lg.setColorAt(1, CYAN)
            p.setBrush(lg)
            p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        else:
            p.setBrush(QColor(255, 255, 255, 30 if self._hover else 18))
            p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawEllipse(circle)
        icon_color = QColor("white") if on else QColor(255, 255, 255, 140 if self.isEnabled() else 70)
        draw_power_icon(p, c, r * 0.38, icon_color)


class ToggleSwitch(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(48, 28)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(48, 28)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(Qt.NoPen)
        if self.isChecked():
            lg = QLinearGradient(track.topLeft(), track.topRight())
            lg.setColorAt(0, VIOLET)
            lg.setColorAt(1, CYAN)
            p.setBrush(lg)
        else:
            p.setBrush(QColor(255, 255, 255, 40))
        p.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        d = track.height() - 6
        x = track.right() - d - 3 if self.isChecked() else track.left() + 3
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, track.top() + 3, d, d))


class SpeakerIcon(QWidget):
    def __init__(self):
        super().__init__()
        self.level = 60
        self.setFixedSize(30, 30)

    def set_level(self, v: int):
        self.level = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(255, 255, 255, 160)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        body = QPainterPath()
        body.moveTo(4, 11)
        body.lineTo(9, 11)
        body.lineTo(15, 5)
        body.lineTo(15, 25)
        body.lineTo(9, 19)
        body.lineTo(4, 19)
        body.closeSubpath()
        p.drawPath(body)
        p.setPen(QPen(col, 2.2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        if self.level == 0:
            p.drawLine(QPointF(19, 11), QPointF(27, 19))
            p.drawLine(QPointF(27, 11), QPointF(19, 19))
            return
        waves = 1 if self.level < 34 else 2 if self.level < 67 else 3
        for i in range(waves):
            rr = 5 + i * 4.5
            p.drawArc(QRectF(15 - rr, 15 - rr, 2 * rr, 2 * rr), -50 * 16, 100 * 16)


class Dot(QWidget):
    def __init__(self):
        super().__init__()
        self.color = QColor("#6b6880")
        self.setFixedSize(18, 18)

    def set_color(self, color: str):
        self.color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(9, 9)
        g = QRadialGradient(c, 9)
        halo = QColor(self.color)
        halo.setAlpha(120)
        g.setColorAt(0.4, halo)
        halo.setAlpha(0)
        g.setColorAt(1, halo)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, 9, 9)
        p.setBrush(self.color)
        p.drawEllipse(c, 4.5, 4.5)


class ElidedText(QWidget):
    """Texto com quebra de linha que termina em "…" quando passa do limite de linhas."""

    def __init__(self, text: str, max_lines: int = 2):
        super().__init__()
        self.text = text
        self.max_lines = max_lines
        self.setObjectName("desc")
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def _line_height(self) -> int:
        return self.fontMetrics().lineSpacing()

    def sizeHint(self):
        return QSize(100, self._line_height() * self.max_lines)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        fm = self.fontMetrics()
        layout = QTextLayout(self.text, self.font())
        layout.beginLayout()
        y = 0
        for i in range(self.max_lines):
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(self.width())
            start, length = line.textStart(), line.textLength()
            if i == self.max_lines - 1 and start + length < len(self.text):
                rest = self.text[start:]
                p.drawText(0, y + fm.ascent(), fm.elidedText(rest, Qt.ElideRight, self.width()))
            else:
                p.drawText(0, y + fm.ascent(), self.text[start:start + length].rstrip())
            y += fm.lineSpacing()
        layout.endLayout()


class PackTile(QFrame):
    clicked = Signal(str)

    def __init__(self, name: str, title: str, desc: str):
        super().__init__()
        self.name = name
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("selected", False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 11, 14, 11)
        lay.setSpacing(3)
        t = QLabel(title)
        t.setObjectName("tileTitle")
        d = ElidedText(desc, max_lines=2)
        for w in (t, d):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            lay.addWidget(w)

    def set_selected(self, on: bool):
        if self.property("selected") != on:
            self.setProperty("selected", on)
            self.style().unpolish(self)
            self.style().polish(self)
            for child in self.findChildren(QWidget):
                child.style().unpolish(child)
                child.style().polish(child)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.name)


def card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)
    if title:
        lay.addWidget(label(title.upper(), "section"))
    return frame, lay


def label(text: str = "", name: str | None = None, align=None) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if align is not None:
        lbl.setAlignment(align)
    return lbl


# --- janela ----------------------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self, engine: Engine):
        super().__init__()
        self.engine = engine
        self.packs = pack_infos()
        self.tray = None
        self.quitting = False
        self._told_about_tray = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource("assets/icon.png"))))
        self.resize(500, 820)
        self.setMinimumWidth(430)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bg = Aurora()
        root.addWidget(bg)
        bg_lay = QVBoxLayout(bg)
        bg_lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bg_lay.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        col = QVBoxLayout(content)
        col.setContentsMargins(18, 18, 18, 24)
        col.setSpacing(14)

        col.addWidget(self.build_hero())
        col.addWidget(self.build_volume())
        col.addWidget(self.build_packs())
        col.addWidget(self.build_test())
        col.addWidget(self.build_system())
        col.addStretch(1)

        self.refresh()
        # Atualiza o status só com a janela à vista: na bandeja, nada acorda a CPU.
        self.timer = QTimer(self, interval=1500)
        self.timer.timeout.connect(self.refresh_status)

    # --- construção --------------------------------------------------------------
    def build_hero(self):
        frame, lay = card()
        lay.setSpacing(4)
        self.power = PowerButton()
        self.power.toggled.connect(self.on_power)
        lay.addWidget(self.power, 0, Qt.AlignHCenter)
        self.hero_title = label("", "heroTitle", Qt.AlignHCenter)
        self.hero_sub = label("", "dim", Qt.AlignHCenter)
        lay.addWidget(self.hero_title)
        lay.addWidget(self.hero_sub)
        lay.addSpacing(6)
        return frame

    def build_volume(self):
        frame, lay = card("Volume")
        row = QHBoxLayout()
        self.vol_label = label("", "bigNum")
        self.speaker = SpeakerIcon()
        row.addWidget(self.vol_label, 1)
        row.addWidget(self.speaker)
        lay.addLayout(row)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setFixedHeight(26)
        self.slider.setCursor(Qt.PointingHandCursor)
        self.slider.valueChanged.connect(self.on_volume_moved)
        self.slider.sliderReleased.connect(self.save_volume)
        self.vol_timer = QTimer(self, singleShot=True, interval=200)
        self.vol_timer.timeout.connect(self.save_volume)
        lay.addWidget(self.slider)
        return frame

    def build_packs(self):
        frame, lay = card("Pacote de som")
        grid = QGridLayout()
        grid.setSpacing(10)
        self.tiles: dict[str, PackTile] = {}
        for i, (name, title, desc) in enumerate(self.packs):
            tile = PackTile(name, title, desc)
            tile.clicked.connect(self.on_pack)
            grid.addWidget(tile, i // 2, i % 2)
            self.tiles[name] = tile
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        return frame

    def build_test(self):
        frame, lay = card("Testar")
        row = QHBoxLayout()
        row.setSpacing(10)
        self.test_entry = QLineEdit()
        self.test_entry.setPlaceholderText("Digite aqui para ouvir o pacote…")
        listen = QPushButton("Ouvir")
        listen.setCursor(Qt.PointingHandCursor)
        listen.setToolTip("Toca uma tecla do pacote escolhido")
        listen.clicked.connect(self.engine.preview)
        row.addWidget(self.test_entry, 1)
        row.addWidget(listen)
        lay.addLayout(row)
        return frame

    def build_system(self):
        frame, lay = card("Sistema")
        row = QHBoxLayout()
        row.setSpacing(10)
        self.dot = Dot()
        self.status_label = label("", "strong")
        row.addWidget(self.dot)
        row.addWidget(self.status_label, 1)
        lay.addLayout(row)

        self.warn = label("", "chipWarn")
        self.warn.setWordWrap(True)
        self.warn.hide()
        lay.addWidget(self.warn)

        self.perm_row = QHBoxLayout()
        self.perm_btn = QPushButton("Abrir Ajustes do Sistema")
        self.perm_btn.setObjectName("go")
        self.perm_btn.clicked.connect(open_privacy_settings)
        self.relaunch_btn = QPushButton("Reabrir o Clack")
        self.relaunch_btn.clicked.connect(relaunch)
        for b in (self.perm_btn, self.relaunch_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.hide()
            self.perm_row.addWidget(b)
        self.perm_row.addStretch(1)
        lay.addLayout(self.perm_row)

        auto = QHBoxLayout()
        txt = QVBoxLayout()
        txt.setSpacing(2)
        txt.addWidget(label("Iniciar com o sistema"))
        where = "Windows" if sys.platform == "win32" else "macOS" if sys.platform == "darwin" else "sistema"
        txt.addWidget(label(f"Abre o Clack escondido ao entrar no {where}", "desc"))
        self.autostart = ToggleSwitch()
        self.autostart.setChecked(safe_autostart_enabled())
        self.autostart.toggled.connect(self.on_autostart)
        auto.addLayout(txt, 1)
        auto.addWidget(self.autostart, 0, Qt.AlignVCenter)
        lay.addLayout(auto)

        place = "na barra de menus" if sys.platform == "darwin" else "na bandeja, perto do relógio"
        hint = label(f"Fechar a janela não desliga o Clack: ele continua {place}.", "desc")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        quit_row = QHBoxLayout()
        quit_btn = QPushButton("Sair do Clack")
        quit_btn.setObjectName("danger")
        quit_btn.setCursor(Qt.PointingHandCursor)
        quit_btn.clicked.connect(self.quit_app)
        quit_row.addStretch(1)
        quit_row.addWidget(quit_btn)
        lay.addLayout(quit_row)
        return frame

    # --- estado ----------------------------------------------------------------------
    def refresh(self):
        cfg = self.engine.cfg
        self.power.blockSignals(True)
        self.power.setChecked(cfg["enabled"])
        self.power.blockSignals(False)
        self.power.update()
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(cfg["volume"])
            self.slider.blockSignals(False)
        self.update_volume_label(self.slider.value())
        for name, tile in self.tiles.items():
            tile.set_selected(name == cfg["pack"])
        title = next((t for n, t, _ in self.packs if n == cfg["pack"]), cfg["pack"])
        self.hero_title.setText("Ligado" if cfg["enabled"] else "Desligado")
        self.hero_sub.setText(f"{title} · volume {cfg['volume']}%")
        if self.tray is not None:
            self.tray.sync()
        self.refresh_status()

    def refresh_status(self):
        lst = self.engine.listener
        status = lst.status if lst else listeners.ERROR
        warn = ""
        perm = False
        if status == listeners.OK:
            self.dot.set_color("#3ce6a0")
            self.status_label.setText("Ouvindo o teclado")
        elif status == listeners.NO_PERMISSION:
            self.dot.set_color("#ffb84f")
            self.status_label.setText("Sem permissão para ouvir o teclado")
            if sys.platform == "darwin":
                perm = True
                warn = ("Ative o Clack em Ajustes do Sistema › Privacidade e Segurança › "
                        "Monitoramento de Entrada e depois reabra o app.")
            else:
                warn = lst.detail if lst else ""
        else:
            self.dot.set_color("#ff4f6d")
            self.status_label.setText("Erro ao ouvir o teclado")
            warn = lst.detail if lst else ""
        if self.engine.audio_error:
            warn = (warn + "\n" if warn else "") + f"Sem saída de áudio: {self.engine.audio_error}"
        self.warn.setText(warn)
        self.warn.setVisible(bool(warn))
        self.perm_btn.setVisible(perm)
        self.relaunch_btn.setVisible(perm)

    def update_volume_label(self, v: int):
        self.vol_label.setText(f"{v}%")
        self.speaker.set_level(v)

    # --- ações -------------------------------------------------------------------------
    def on_power(self, on: bool):
        self.engine.set_enabled(on)
        self.refresh()

    def on_volume_moved(self, v: int):
        self.update_volume_label(v)
        self.vol_timer.start()

    def save_volume(self):
        if self.slider.value() != self.engine.cfg["volume"]:
            self.engine.set_volume(self.slider.value())
            self.refresh()

    def on_pack(self, name: str):
        if name != self.engine.cfg["pack"]:
            self.engine.set_pack(name)
            self.refresh()
        self.engine.preview()

    def on_autostart(self, on: bool):
        try:
            autostart.set_enabled(on)
        except OSError as exc:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(not on)
            self.autostart.blockSignals(False)
            self.warn.setText(f"Não consegui mudar a inicialização: {exc}")
            self.warn.show()

    def show_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.quitting = True
        QApplication.instance().quit()

    def showEvent(self, e):
        self.refresh_status()
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def closeEvent(self, e):
        if self.quitting or self.tray is None or not QSystemTrayIcon.isSystemTrayAvailable():
            self.quitting = True
            e.accept()
            QApplication.instance().quit()
            return
        e.ignore()
        self.hide()
        if not self._told_about_tray:
            self._told_about_tray = True
            self.tray.showMessage(APP_NAME, "O Clack continua tocando aqui. Clique no ícone para abrir.",
                                  QIcon(str(resource("assets/icon.png"))), 4000)


class Tray(QSystemTrayIcon):
    def __init__(self, window: MainWindow):
        super().__init__(QIcon(str(resource("assets/icon.png"))), window)
        self.window = window
        self.setToolTip(APP_NAME)
        menu = QMenu()
        open_act = QAction("Abrir o Clack", menu)
        open_act.triggered.connect(window.show_window)
        self.toggle_act = QAction("Som ligado", menu, checkable=True)
        self.toggle_act.toggled.connect(self.on_toggle)
        quit_act = QAction("Sair", menu)
        quit_act.triggered.connect(window.quit_app)
        menu.addAction(open_act)
        menu.addAction(self.toggle_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        self.menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)
        window.tray = self
        self.sync()

    def sync(self):
        self.toggle_act.blockSignals(True)
        self.toggle_act.setChecked(self.window.engine.cfg["enabled"])
        self.toggle_act.blockSignals(False)

    def on_toggle(self, on: bool):
        self.window.engine.set_enabled(on)
        self.window.refresh()

    def on_activated(self, reason):
        # No macOS o clique abre o menu; no Windows o clique simples abre a janela.
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) and sys.platform != "darwin":
            self.window.show_window()


# --- utilidades do sistema ----------------------------------------------------------------
def safe_autostart_enabled() -> bool:
    try:
        return autostart.is_enabled()
    except OSError:
        return False


def open_privacy_settings():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(
        "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"))


def app_bundle() -> Path | None:
    """Caminho do Clack.app quando rodando empacotado no macOS."""
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


def relaunch():
    """Abre uma cópia nova do app e fecha esta (o macOS só aplica a permissão assim)."""
    from PySide6.QtCore import QProcess
    bundle = app_bundle() if sys.platform == "darwin" else None
    if bundle is not None:
        # Espera esta cópia fechar, senão o "open" só traz a janela atual para frente.
        QProcess.startDetached("/bin/sh", ["-c", 'sleep 1; open -n "$0"', str(bundle)])
    else:
        program, *args = autostart.launch_command()
        args.remove("--hidden")
        QProcess.startDetached(program, args)
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, MainWindow):
            widget.quitting = True
    QApplication.quit()


def setup_app(argv) -> QApplication:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Clack")
    app.setStyle("Fusion")
    # Barra de título escura no Windows 11 e janela escura no macOS (Qt 6.8+).
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyleSheet(QSS)
    app.setWindowIcon(QIcon(str(resource("assets/icon.png"))))
    app.setQuitOnLastWindowClosed(False)
    return app


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        from .selftest import run
        i = argv.index("--selftest")
        out = argv[i + 1] if i + 1 < len(argv) else "clack-selftest.json"
        return run(out)

    hidden = "--hidden" in argv
    app = setup_app(argv)

    # Uma instância só: se já tem um Clack aberto, pede para ele mostrar a janela.
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return 0
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    engine = Engine()
    engine.start()
    window = MainWindow(engine)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = Tray(window)
        tray.show()
    else:
        hidden = False  # sem bandeja não dá para começar escondido

    def on_second_instance():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.disconnected.connect(conn.deleteLater)
            window.show_window()

    def on_app_state(state):
        # macOS: clique no ícone do Dock com a janela escondida mostra a janela de novo.
        if state == Qt.ApplicationActive and not window.isVisible() and not window.quitting:
            window.show_window()

    server.newConnection.connect(on_second_instance)
    if sys.platform == "darwin":
        app.applicationStateChanged.connect(on_app_state)

    if not hidden:
        window.show_window()
    code = app.exec()
    engine.stop()
    return code


if __name__ == "__main__":
    sys.exit(main())
