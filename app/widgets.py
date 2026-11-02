"""Componentes visuales reutilizables de Foxy Lancer."""
import os

from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPainterPath
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QGraphicsDropShadowEffect,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox,
)

from . import theme as th
from . import logic

AVATAR_COLORS = ["#155bd5", "#0f766e", "#7c3aed", "#c2410c", "#be185d", "#4338ca", "#0e7490", "#a21caf"]


# ------------------------------------------------------------------ utilidades
def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def lbl(text="", kind=None, wrap=False):
    label = QLabel(str(text))
    if kind:
        label.setObjectName(kind)
    label.setWordWrap(wrap)
    return label


def btn(text, kind=None, slot=None, tip=None):
    b = QPushButton(text)
    if kind:
        b.setObjectName(kind)
    if slot is not None:
        b.clicked.connect(lambda checked=False, s=slot: s())
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def add_shadow(widget, blur=22, dy=4):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(10, 25, 50, th.T.get("shadow_alpha", 30)))
    widget.setGraphicsEffect(effect)


def hsep():
    f = QFrame()
    f.setObjectName("sep")
    f.setFixedHeight(1)
    return f


def info_box(parent, title, text):
    QMessageBox.information(parent, title, text)


def toast(parent, text, ms=2600):
    """Aviso flotante breve en la esquina inferior derecha de la ventana."""
    top = parent.window() if parent is not None else None
    if top is None:
        return
    t = th.T
    label = QLabel(text, top)
    label.setStyleSheet(
        f"background:{t['text']}; color:{t['surface']}; border-radius:10px; padding:11px 16px; font-weight:600; font-size:11pt;")
    label.adjustSize()
    label.move(max(10, top.width() - label.width() - 26), max(10, top.height() - label.height() - 46))
    label.show()
    label.raise_()
    QTimer.singleShot(ms, label.deleteLater)


# ------------------------------------------------------------------- avatares
def make_avatar(name, size=44, photo=None):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    p.setClipPath(path)
    src = QPixmap(photo) if photo and os.path.exists(photo) else QPixmap()
    if not src.isNull():
        src = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                         Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((size - src.width()) // 2, (size - src.height()) // 2, src)
    else:
        seed = sum(ord(c) for c in str(name or "?"))
        p.fillRect(QRectF(0, 0, size, size), QColor(AVATAR_COLORS[seed % len(AVATAR_COLORS)]))
        p.setPen(QColor("#ffffff"))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(max(10, int(size * 0.38)))
        p.setFont(f)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, logic.initials(name))
    p.end()
    return pm


class Avatar(QLabel):
    def __init__(self, name, size=44, photo=None):
        super().__init__()
        self.setFixedSize(size, size)
        self.setPixmap(make_avatar(name, size, photo))
        self.setStyleSheet("background:transparent; border:none;")


# --------------------------------------------------------------- piezas simples
def badge(text, tone="neutral"):
    t = th.T
    fg = t.get(tone, t["neutral"])
    bg = t.get(tone + "_bg", t["neutral_bg"])
    label = QLabel(text)
    label.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:9px; padding:3px 10px; font-weight:700; font-size:10pt;")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def state_badge(state):
    return badge(state, logic.tone_for(state))


def chip(text):
    t = th.T
    label = QLabel(text)
    label.setStyleSheet(f"background:{t['primary_soft']}; color:{t['primary_text']}; border-radius:8px; padding:4px 10px; font-weight:600; font-size:10pt;")
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def row_widget(items, spacing=6, stretch_end=True):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(spacing)
    for it in items:
        h.addWidget(it)
    if stretch_end:
        h.addStretch(1)
    return w


def chips_row(skills_text, maximum=5):
    skills = logic.parse_skills(skills_text)
    items = [chip(s) for s in skills[:maximum]]
    if len(skills) > maximum:
        items.append(chip(f"+{len(skills) - maximum}"))
    return row_widget(items)


def badges_row(badges):
    return row_widget([badge(text, tone) for _, text, tone in badges], spacing=6)


def stars_label(score, count=None):
    label = QLabel(logic.stars(score, count))
    label.setStyleSheet(f"color:{th.T['warn']}; font-weight:700;")
    return label


def progress(value, maximum=100):
    from PySide6.QtWidgets import QProgressBar
    bar = QProgressBar()
    bar.setRange(0, maximum)
    bar.setValue(int(value))
    bar.setTextVisible(False)
    return bar


class Card(QFrame):
    def __init__(self, shadow=True, pad=(18, 16, 18, 16), spacing=10, horizontal=False):
        super().__init__()
        self.setObjectName("card")
        self.lay = QHBoxLayout(self) if horizontal else QVBoxLayout(self)
        self.lay.setContentsMargins(*pad)
        self.lay.setSpacing(spacing)
        if shadow:
            add_shadow(self)


class KPICard(Card):
    def __init__(self, title, value, delta=None, hint="vs. 30 días anteriores"):
        super().__init__(pad=(18, 15, 18, 15), spacing=4)
        self.lay.addWidget(lbl(title, "muted"))
        v = lbl(value, "kpiValue")
        self.lay.addWidget(v)
        t = th.T
        if delta is None:
            txt, color = "— sin variación", t["muted"]
        elif delta >= 0:
            txt, color = f"▲ {delta:.1f}%", t["success"]
        else:
            txt, color = f"▼ {abs(delta):.1f}%", t["danger"]
        d = QLabel(f"{txt}  <span style='color:{t['muted']}; font-weight:400;'>{hint}</span>")
        d.setTextFormat(Qt.TextFormat.RichText)
        d.setStyleSheet(f"color:{color}; font-weight:700; font-size:10pt;")
        self.lay.addWidget(d)


class EmptyState(Card):
    def __init__(self, icon, title, text, action_text=None, action=None):
        super().__init__(shadow=False, pad=(24, 34, 24, 34), spacing=8)
        i = lbl(icon)
        i.setStyleSheet("font-size:34pt; background:transparent;")
        i.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay.addWidget(i)
        t = lbl(title, "h3")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay.addWidget(t)
        d = lbl(text, "muted", wrap=True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lay.addWidget(d)
        if action_text and action:
            b = btn(action_text, slot=action)
            b.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            self.lay.addWidget(b, 0, Qt.AlignmentFlag.AlignCenter)


class PageHeader(QWidget):
    def __init__(self, title, subtitle=None, actions=None):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(lbl(title, "h1"))
        if subtitle:
            col.addWidget(lbl(subtitle, "muted", wrap=True))
        h.addLayout(col, 1)
        for a in actions or []:
            h.addWidget(a, 0, Qt.AlignmentFlag.AlignTop)


class PillTabs(QWidget):
    changed = Signal(str)

    def __init__(self, items, current=None):
        super().__init__()
        self._labels = dict(items)
        self.buttons = {}
        self.current = current or items[0][0]
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        for key, label in items:
            b = QPushButton(label)
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked=False, k=key: self.select(k))
            self.buttons[key] = b
            h.addWidget(b)
        h.addStretch(1)
        self.select(self.current, emit=False)

    def select(self, key, emit=True):
        self.current = key
        for k, b in self.buttons.items():
            b.setChecked(k == key)
        if emit:
            self.changed.emit(key)

    def set_label(self, key, text):
        if key in self.buttons:
            self.buttons[key].setText(text)


def page_scroll(inner):
    """Envuelve un widget en un QScrollArea sin marco."""
    inner.setObjectName("page")
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(inner)
    return area


def vbox(margins=(0, 0, 0, 0), spacing=12):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(*margins)
    v.setSpacing(spacing)
    return w, v


def two_line(title, sub=None):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 2, 0, 2)
    v.setSpacing(0)
    a = QLabel(str(title))
    a.setStyleSheet("font-weight:700;")
    v.addWidget(a)
    if sub:
        v.addWidget(lbl(sub, "small"))
    return w


class DataTable(QTableWidget):
    """Tabla con estilo del tema; las celdas pueden ser texto o widgets."""

    def __init__(self, headers, modes=None, row_height=58):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.row_height = row_height
        modes = modes or ["s"] * len(headers)
        hh = self.horizontalHeader()
        hh.setStretchLastSection(False)
        for i, m in enumerate(modes):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if m == "s" else QHeaderView.ResizeMode.ResizeToContents)

    def set_rows(self, rows, max_rows=200):
        self.setRowCount(0)
        rows = rows[:max_rows]
        self.setRowCount(len(rows))
        for r, cells in enumerate(rows):
            for c, cell in enumerate(cells):
                if isinstance(cell, QWidget):
                    self.setCellWidget(r, c, cell)
                else:
                    item = QTableWidgetItem("" if cell is None else str(cell))
                    self.setItem(r, c, item)
        self.fit_height()

    def fit_height(self):
        n = self.rowCount()
        self.setFixedHeight(self.horizontalHeader().height() + 36 + n * self.row_height + 4)


def action_cell(buttons):
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(4, 0, 4, 0)
    h.setSpacing(6)
    for b in buttons:
        h.addWidget(b)
    return w


def small_btn(text, kind="secondary", slot=None, tip=None):
    b = btn(text, kind, slot, tip)
    b.setStyleSheet("padding:6px 12px; font-size:10pt;")
    return b


# ------------------------------------------------------------ errores y avisos
def ui_error(parent, title, exc):
    """Muestra un error amigable (y lo registra) sin cerrar la aplicación."""
    import logging
    detail = str(exc)
    if isinstance(exc, (ValueError, PermissionError)):
        QMessageBox.warning(parent, title, detail)
        return
    logging.getLogger("mypines").exception("%s: %s", title, detail)
    errno = getattr(exc, "errno", None)
    if errno == 1146 or "doesn't exist" in detail.lower():
        hint = "\n\nFalta una tabla de Foxy Lancer. Cierra y vuelve a abrir la aplicación para que se creen automáticamente."
    elif errno == 1045 or "access denied" in detail.lower():
        hint = "\n\nMySQL rechazó el usuario o la contraseña. Revisá MYSQL_USER y MYSQL_PASSWORD en el archivo .env."
    elif errno == 2003 or "can't connect" in detail.lower():
        hint = "\n\nNo se pudo alcanzar el servidor MySQL. Comprobá que el servicio MySQL80 esté en ejecución."
    else:
        hint = "\n\nNo se borró ningún dato. Si el problema continúa, revisá el archivo mypines.log."
    QMessageBox.critical(parent, title, detail + hint)


def confirm(parent, title, text):
    answer = QMessageBox.question(parent, title, text,
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    return answer == QMessageBox.StandardButton.Yes
