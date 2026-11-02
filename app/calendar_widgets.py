"""Calendario mensual propio y selector de horarios (estilo agendador)."""
import calendar
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel

from . import theme as th
from . import logic

WEEKDAYS = ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"]


class MonthCalendar(QWidget):
    dateSelected = Signal(object)   # datetime.date
    monthChanged = Signal(int, int)

    def __init__(self, min_date=None):
        super().__init__()
        today = date.today()
        self.year, self.month = today.year, today.month
        self.min_date = min_date
        self.selected = None
        self.marks = {}   # date -> lista de colores
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        head = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("h3")
        prev_b, next_b = QPushButton("‹"), QPushButton("›")
        for b, step in ((prev_b, -1), (next_b, 1)):
            b.setObjectName("iconBtn")
            b.setFixedSize(38, 36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked=False, s=step: self.shift(s))
        head.addWidget(self.title, 1)
        head.addWidget(prev_b)
        head.addWidget(next_b)
        root.addLayout(head)
        self.grid = QGridLayout()
        self.grid.setSpacing(4)
        root.addLayout(self.grid)
        self.rebuild()

    def shift(self, step):
        m = self.month + step
        y = self.year
        if m == 0:
            m, y = 12, y - 1
        elif m == 13:
            m, y = 1, y + 1
        self.year, self.month = y, m
        self.rebuild()
        self.monthChanged.emit(y, m)

    def set_marks(self, marks):
        self.marks = dict(marks)
        self.rebuild()

    def select(self, d, emit=True):
        self.selected = d
        if (d.year, d.month) != (self.year, self.month):
            self.year, self.month = d.year, d.month
        self.rebuild()
        if emit:
            self.dateSelected.emit(d)

    def rebuild(self):
        t = th.T
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        self.title.setText(f"{logic.MESES[self.month - 1].upper()} {self.year}")
        for c, name in enumerate(WEEKDAYS):
            lab = QLabel(name)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(f"color:{t['muted']}; font-weight:700; font-size:10pt;")
            self.grid.addWidget(lab, 0, c)
        weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(self.year, self.month)
        while len(weeks) < 6:
            last = weeks[-1][-1]
            weeks.append([date.fromordinal(last.toordinal() + 1 + i) for i in range(7)])
        today = date.today()
        for r, week in enumerate(weeks):
            for c, d in enumerate(week):
                b = QPushButton(str(d.day))
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setFixedSize(44, 42)
                disabled = bool(self.min_date and d < self.min_date)
                other = d.month != self.month
                bg, fg, border, weight = "transparent", t["text"], "transparent", "500"
                marks = self.marks.get(d)
                if other:
                    fg = t["disabled_text"] if disabled else t["muted"]
                if disabled:
                    fg = t["disabled_text"]
                if marks and not disabled:
                    bg, fg, weight = t["primary_soft"], t["primary_text"], "700"
                if d == today:
                    border = t["primary"]
                if d == self.selected:
                    bg, fg, border, weight = t["primary"], t["on_primary"], t["primary"], "700"
                under = ""
                if marks and d != self.selected:
                    under = f"border-bottom:4px solid {marks[0]};"
                b.setStyleSheet(
                    f"QPushButton {{ background:{bg}; color:{fg}; border:2px solid {border}; {under} border-radius:21px; font-weight:{weight}; padding:0; }}"
                    f"QPushButton:hover {{ background:{t['primary_soft']}; color:{t['primary_text']}; }}"
                    f"QPushButton:disabled {{ background:transparent; color:{t['disabled_text']}; border:2px solid transparent; }}")
                b.setEnabled(not disabled)
                b.clicked.connect(lambda checked=False, dd=d: self.select(dd))
                self.grid.addWidget(b, r + 1, c, Qt.AlignmentFlag.AlignCenter)


class SlotPicker(QWidget):
    slotChanged = Signal(str)   # 'HH:MM'

    def __init__(self, slots=None, cols=3):
        super().__init__()
        self.slots = slots or logic.time_slots()
        self.cols = cols
        self.busy = set()
        self.earliest = None
        self.selected = None
        self.buttons = {}
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        self.render()

    def render(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        self.buttons = {}
        for i, s in enumerate(self.slots):
            b = QPushButton(logic.slot_label(s))
            b.setObjectName("slot")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            unavailable = s in self.busy or (self.earliest is not None and s < self.earliest)
            b.setEnabled(not unavailable)
            if unavailable:
                b.setToolTip("Horario no disponible")
            b.setChecked(s == self.selected and not unavailable)
            b.clicked.connect(lambda checked=False, ss=s: self.choose(ss))
            self.buttons[s] = b
            self.grid.addWidget(b, i // self.cols, i % self.cols)

    def choose(self, slot):
        self.selected = slot
        for s, b in self.buttons.items():
            b.setChecked(s == slot)
        self.slotChanged.emit(slot)

    def configure(self, busy=(), earliest=None):
        """busy: horarios ocupados ('HH:MM'); earliest: primer horario permitido hoy."""
        self.busy = set(busy)
        self.earliest = earliest
        if self.selected in self.busy or (earliest is not None and self.selected is not None and self.selected < earliest):
            self.selected = None
        self.render()
