"""Tema visual de Foxy Lancer (claro / oscuro) con contraste alto.

Los colores viven en dos diccionarios; `T` apunta siempre al tema activo.
La hoja de estilos se aplica solo a la ventana principal, así la pantalla de
inicio de sesión conserva exactamente su diseño original.
"""
import os
import tempfile
from string import Template

LIGHT = {
    "name": "claro",
    "bg": "#f3f6fb", "surface": "#ffffff", "surface2": "#eef3fa", "border": "#d3ddec", "border_strong": "#9fb0c8",
    "text": "#0f1f3a", "muted": "#475a75", "text_inverse": "#ffffff",
    "primary": "#155bd5", "primary_hover": "#104bb2", "on_primary": "#ffffff",
    "primary_soft": "#e2ecff", "primary_text": "#0f47aa",
    "success": "#0b6b3a", "success_bg": "#def5e8",
    "warn": "#7a4a00", "warn_bg": "#fff0cf",
    "danger": "#b42318", "danger_bg": "#fde8e6", "danger_btn": "#c62828",
    "info": "#0f47aa", "info_bg": "#e2ecff",
    "neutral": "#3b4a63", "neutral_bg": "#e8edf5",
    "secondary_bg": "#e4edfa", "secondary_text": "#123e78", "secondary_hover": "#d2e2f8",
    "disabled_bg": "#d5deeb", "disabled_text": "#4a5a73",
    "hero1": "#0f4bb8", "hero2": "#1f63dc", "on_hero": "#ffffff", "on_hero_muted": "#e8f1ff",
    "slot_sel_bg": "#0f1f3a", "slot_sel_text": "#ffffff", "shadow_alpha": 30,
    "chart1": "#155bd5", "chart2": "#0b8a5f", "chart3": "#c2610c", "chart4": "#7c3aed",
    "chart5": "#be185d", "chart6": "#0e7490",
}

DARK = {
    "name": "oscuro",
    "bg": "#0d1626", "surface": "#15233a", "surface2": "#1b2c47", "border": "#2b3f5f", "border_strong": "#5b7397",
    "text": "#e8eef9", "muted": "#a9b9d0", "text_inverse": "#0d1626",
    "primary": "#2f6fe4", "primary_hover": "#2559c4", "on_primary": "#ffffff",
    "primary_soft": "#1d3a6b", "primary_text": "#a8c9ff",
    "success": "#7ee2a8", "success_bg": "#12392a",
    "warn": "#ffd17a", "warn_bg": "#43320c",
    "danger": "#ffaaa3", "danger_bg": "#4a1d1a", "danger_btn": "#d13c3c",
    "info": "#a8c9ff", "info_bg": "#1d3a6b",
    "neutral": "#c9d5e8", "neutral_bg": "#26364f",
    "secondary_bg": "#22385a", "secondary_text": "#dbe8ff", "secondary_hover": "#2c4875",
    "disabled_bg": "#26364f", "disabled_text": "#9db0cc",
    "hero1": "#16408f", "hero2": "#1f58c4", "on_hero": "#ffffff", "on_hero_muted": "#e1ecff",
    "slot_sel_bg": "#2f6fe4", "slot_sel_text": "#ffffff", "shadow_alpha": 90,
    "chart1": "#6ea2ff", "chart2": "#4fd1a1", "chart3": "#ffb066", "chart4": "#b794f6",
    "chart5": "#f78fb8", "chart6": "#5fd0e8",
}

T = dict(LIGHT)
_CHECK_ICON = None


def set_theme(name):
    """Activa 'claro' u 'oscuro' modificando `T` en el mismo diccionario."""
    src = DARK if name == "oscuro" else LIGHT
    T.clear()
    T.update(src)
    return T


def is_dark():
    return T.get("name") == "oscuro"


def chart_colors():
    return [T["chart1"], T["chart2"], T["chart3"], T["chart4"], T["chart5"], T["chart6"]]


def _check_icon_path():
    """Crea (una vez) la marca blanca de las casillas marcadas."""
    global _CHECK_ICON
    if _CHECK_ICON and os.path.exists(_CHECK_ICON):
        return _CHECK_ICON
    from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QPainterPath
    from PySide6.QtCore import Qt
    pm = QPixmap(18, 18)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#ffffff"), 2.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(4.5, 9.5)
    path.lineTo(7.8, 12.8)
    path.lineTo(13.5, 5.5)
    p.drawPath(path)
    p.end()
    path_png = os.path.join(tempfile.gettempdir(), "mypines_check.png")
    pm.save(path_png, "PNG")
    _CHECK_ICON = path_png
    return _CHECK_ICON


QSS = Template(r"""
QMainWindow, QDialog, QWidget#root, QWidget#page { background:$bg; color:$text; }
QWidget { color:$text; font-family:"Segoe UI","Inter","Arial"; font-size:10.5pt; }
QLabel { background:transparent; color:$text; }
QLabel#h1 { font-size:22pt; font-weight:700; }
QLabel#h2 { font-size:15pt; font-weight:700; }
QLabel#h3 { font-size:12pt; font-weight:700; }
QLabel#muted { color:$muted; }
QLabel#small { color:$muted; font-size:10pt; }
QLabel#accent { color:$primary_text; font-weight:700; }
QLabel#heroTitle { color:$on_hero; font-size:21pt; font-weight:700; }
QLabel#heroText { color:$on_hero_muted; font-size:11pt; }
QLabel#kpiValue { font-size:21pt; font-weight:700; }
QFrame#card { background:$surface; border:1px solid $border; border-radius:14px; }
QFrame#card2 { background:$surface2; border:1px solid $border; border-radius:12px; }
QFrame#topbar { background:$surface; border:none; border-bottom:1px solid $border; }
QFrame#sidebar { background:$surface; border:none; border-right:1px solid $border; }
QFrame#hero { border:none; border-radius:16px; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 $hero1,stop:1 $hero2); }
QFrame#sep { background:$border; border:none; max-height:1px; min-height:1px; }

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QComboBox {
  background:$surface; border:1px solid $border_strong; border-radius:9px; padding:8px 10px; color:$text;
  selection-background-color:$primary; selection-color:$on_primary; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus { border:2px solid $primary; }
QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled { color:$disabled_text; background:$surface2; }
QComboBox QAbstractItemView { background:$surface; color:$text; border:1px solid $border; selection-background-color:$primary_soft; selection-color:$primary_text; outline:0; padding:4px; }
QLineEdit#bigSearch { border:none; border-radius:10px; padding:13px 14px; font-size:11.5pt; }

QPushButton { background:$primary; color:$on_primary; border:none; border-radius:9px; padding:9px 16px; font-weight:600; }
QPushButton:hover { background:$primary_hover; }
QPushButton:disabled { background:$disabled_bg; color:$disabled_text; }
QPushButton#secondary { background:$secondary_bg; color:$secondary_text; border:1px solid $border; }
QPushButton#secondary:hover { background:$secondary_hover; }
QPushButton#secondary:disabled { background:$disabled_bg; color:$disabled_text; }
QPushButton#danger { background:$danger_btn; color:#ffffff; }
QPushButton#danger:hover { background:#a82020; }
QPushButton#ghost { background:transparent; color:$primary_text; padding:6px 10px; }
QPushButton#ghost:hover { background:$primary_soft; }
QPushButton#ghost:disabled { background:transparent; color:$disabled_text; }
QPushButton#heroBtn { background:$surface; color:$primary_text; }
QPushButton#heroBtn:hover { background:$primary_soft; }
QPushButton#iconBtn { background:$surface2; color:$text; border:1px solid $border; border-radius:9px; padding:8px 12px; font-size:12pt; }
QPushButton#iconBtn:hover { background:$primary_soft; }
QPushButton#navtab { background:transparent; color:$muted; padding:9px 14px; border-radius:9px; font-weight:600; }
QPushButton#navtab:hover { background:$primary_soft; color:$primary_text; }
QPushButton#navtab:checked { background:$primary_soft; color:$primary_text; }
QPushButton#side { background:transparent; color:$muted; padding:10px 14px; border-radius:9px; text-align:left; font-weight:600; }
QPushButton#side:hover { background:$primary_soft; color:$primary_text; }
QPushButton#side:checked { background:$primary; color:$on_primary; }
QPushButton#tab { background:$surface2; color:$muted; border:1px solid $border; border-radius:16px; padding:7px 15px; font-weight:600; }
QPushButton#tab:hover { background:$primary_soft; color:$primary_text; }
QPushButton#tab:checked { background:$primary; color:$on_primary; border:1px solid $primary; }
QPushButton#slot { background:$surface; color:$primary_text; border:2px solid $primary; border-radius:10px; padding:10px 0; font-weight:600; }
QPushButton#slot:hover { background:$primary_soft; }
QPushButton#slot:checked { background:$slot_sel_bg; color:$slot_sel_text; border:2px solid $slot_sel_bg; }
QPushButton#slot:disabled { background:$surface2; color:$disabled_text; border:2px solid $border; }
QToolButton { background:transparent; color:$text; border:1px solid transparent; border-radius:9px; padding:5px 9px; font-weight:600; }
QToolButton:hover { background:$primary_soft; }
QToolButton#avatarBtn { background:$surface2; border:1px solid $border; padding:4px 10px 4px 5px; }
QToolButton::menu-indicator { image:none; width:0; }
QToolButton#dots { font-size:14pt; padding:2px 8px; color:$muted; }
QToolButton#dots::menu-indicator { image:none; width:0; }

QScrollArea { border:none; background:transparent; }
QScrollBar:vertical { background:transparent; width:11px; margin:2px; }
QScrollBar::handle:vertical { background:$border_strong; border-radius:5px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:transparent; height:11px; margin:2px; }
QScrollBar::handle:horizontal { background:$border_strong; border-radius:5px; min-width:30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }

QCheckBox { color:$text; spacing:8px; }
QCheckBox::indicator { width:18px; height:18px; border:2px solid $border_strong; border-radius:5px; background:$surface; }
QCheckBox::indicator:hover { border-color:$primary; }
QCheckBox::indicator:checked { background:$primary; border:2px solid $primary; image:url($check_icon); }

QSlider::groove:horizontal { height:6px; background:$border; border-radius:3px; }
QSlider::sub-page:horizontal { background:$primary; border-radius:3px; }
QSlider::handle:horizontal { background:$primary; width:18px; height:18px; margin:-7px 0; border-radius:9px; border:2px solid $surface; }
QProgressBar { background:$border; border:none; border-radius:5px; max-height:10px; min-height:10px; color:transparent; }
QProgressBar::chunk { background:$primary; border-radius:5px; }

QTableWidget { background:$surface; border:none; gridline-color:$border; alternate-background-color:$surface2; selection-background-color:$primary_soft; selection-color:$text; outline:0; }
QTableWidget::item { padding:6px 10px; border-bottom:1px solid $border; }
QHeaderView::section { background:$surface2; color:$muted; padding:10px; border:none; border-bottom:1px solid $border; font-weight:700; }
QTableCornerButton::section { background:$surface2; border:none; }

QMenu { background:$surface; color:$text; border:1px solid $border; padding:6px; border-radius:8px; }
QMenu::item { padding:8px 24px 8px 14px; border-radius:6px; }
QMenu::item:selected { background:$primary_soft; color:$primary_text; }
QMenu::separator { height:1px; background:$border; margin:5px 8px; }
QToolTip { background:$surface; color:$text; border:1px solid $border; padding:6px; }
QMessageBox { background:$surface; }
QMessageBox QLabel { color:$text; min-width:280px; }
QMessageBox QPushButton { min-width:88px; }
QInputDialog QLabel { color:$text; }
QStatusBar { background:$surface; color:$muted; border-top:1px solid $border; }
QStatusBar::item { border:none; }
QCalendarWidget { background:$surface; color:$text; }
QCalendarWidget QWidget { alternate-background-color:$surface2; color:$text; }
QCalendarWidget QToolButton { color:$on_primary; background:$primary; border-radius:6px; padding:6px; }
QCalendarWidget QAbstractItemView { color:$text; background:$surface; selection-background-color:$primary; selection-color:$on_primary; }
QCalendarWidget QAbstractItemView:disabled { color:$disabled_text; }
QCalendarWidget QSpinBox { color:$text; background:$surface; }
""")


def build_stylesheet():
    values = dict(T)
    values["check_icon"] = _check_icon_path().replace("\\", "/")
    return QSS.substitute(values)


# ---------------------------------------------------------------- contraste
def _lum(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg, bg):
    a, b = _lum(fg), _lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)
