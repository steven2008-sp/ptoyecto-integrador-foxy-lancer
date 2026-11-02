"""Gráficos dibujados con QPainter (sin dependencias extra)."""
import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QSizePolicy

from . import theme as th


def nice_max(v):
    if v <= 4:
        return 4
    mag = 10 ** int(math.floor(math.log10(v)))
    for m in (1, 2, 2.5, 4, 5, 10):
        if v <= m * mag:
            return m * mag
    return 10 * mag


def _font(px, bold=False):
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setBold(bold)
    return f


class LineChart(QWidget):
    """Líneas con área, cuadrícula y tooltip al pasar el mouse."""

    def __init__(self):
        super().__init__()
        self.labels, self.series = [], []
        self._hover = None
        self.setMinimumHeight(250)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, labels, series):
        """series: lista de (nombre, valores, color)."""
        self.labels, self.series = list(labels), list(series)
        self._hover = None
        self.update()

    def _plot(self):
        return QRectF(46, 14, max(10, self.width() - 46 - 18), max(10, self.height() - 14 - 56))

    def _x(self, i, plot):
        n = len(self.labels)
        if n <= 1:
            return plot.center().x()
        return plot.left() + i * plot.width() / (n - 1)

    def mouseMoveEvent(self, e):
        if not self.labels:
            return
        plot = self._plot()
        best, dist = None, 1e9
        for i in range(len(self.labels)):
            d = abs(self._x(i, plot) - e.position().x())
            if d < dist:
                best, dist = i, d
        self._hover = best
        self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def paintEvent(self, e):
        t = th.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = self._plot()
        vmax = nice_max(max([max(v) for _, v, _ in self.series if v] + [1]))
        p.setFont(_font(12))
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(QColor(t["border"]), 1, Qt.PenStyle.DashLine if i else Qt.PenStyle.SolidLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(t["muted"]))
            val = vmax * i / 4
            txt = f"{val:.0f}" if val == int(val) else f"{val:.1f}"
            p.drawText(QRectF(0, y - 9, plot.left() - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, txt)
        n = len(self.labels)
        step = max(1, math.ceil(n / 8)) if n else 1
        p.setPen(QColor(t["muted"]))
        for i, lab in enumerate(self.labels):
            if i % step == 0 or i == n - 1:
                x = self._x(i, plot)
                p.drawText(QRectF(x - 34, plot.bottom() + 6, 68, 18), Qt.AlignmentFlag.AlignCenter, str(lab))
        for name, values, color in self.series:
            if not values:
                continue
            pts = [QPointF(self._x(i, plot), plot.bottom() - plot.height() * (v / vmax)) for i, v in enumerate(values)]
            path = QPainterPath(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            area = QPainterPath(path)
            area.lineTo(QPointF(pts[-1].x(), plot.bottom()))
            area.lineTo(QPointF(pts[0].x(), plot.bottom()))
            area.closeSubpath()
            grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
            c1 = QColor(color)
            c1.setAlpha(70)
            c2 = QColor(color)
            c2.setAlpha(4)
            grad.setColorAt(0, c1)
            grad.setColorAt(1, c2)
            p.fillPath(area, QBrush(grad))
            p.setPen(QPen(QColor(color), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(path)
            p.setBrush(QColor(t["surface"]))
            for pt in pts:
                p.drawEllipse(pt, 3.6, 3.6)
        # leyenda
        x = plot.left()
        ly = self.height() - 20
        p.setFont(_font(12, True))
        for name, _, color in self.series:
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x + 5, ly + 8), 5, 5)
            p.setPen(QColor(t["text"]))
            w = p.fontMetrics().horizontalAdvance(name)
            p.drawText(QRectF(x + 15, ly, w + 6, 18), Qt.AlignmentFlag.AlignVCenter, name)
            x += w + 40
        # tooltip
        if self._hover is not None and self.labels:
            i = self._hover
            x = self._x(i, plot)
            p.setPen(QPen(QColor(t["border_strong"]), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            lines = [str(self.labels[i])] + [f"{name}: {values[i]}" for name, values, _ in self.series if i < len(values)]
            p.setFont(_font(12, True))
            w = max(p.fontMetrics().horizontalAdvance(s) for s in lines) + 22
            h = 12 + 19 * len(lines)
            bx = min(max(plot.left(), x + 12), self.width() - w - 6)
            box = QRectF(bx, plot.top() + 6, w, h)
            p.setPen(QPen(QColor(t["border"]), 1))
            p.setBrush(QColor(t["surface"]))
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor(t["text"]))
            for k, s in enumerate(lines):
                p.drawText(QRectF(box.left() + 11, box.top() + 6 + 19 * k, w - 14, 19), Qt.AlignmentFlag.AlignVCenter, s)
        p.end()


class HBarChart(QWidget):
    """Barras horizontales con etiqueta y valor."""

    ROW = 34

    def __init__(self):
        super().__init__()
        self.items = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(60)

    def set_data(self, items):
        """items: lista de (etiqueta, valor, color|None)."""
        self.items = list(items)
        self.setFixedHeight(max(60, len(self.items) * self.ROW + 8))
        self.update()

    def paintEvent(self, e):
        t = th.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.items:
            p.setPen(QColor(t["muted"]))
            p.setFont(_font(13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos todavía")
            p.end()
            return
        vmax = max([v for _, v, _ in self.items] + [1])
        label_w = min(180, int(self.width() * 0.38))
        val_w = 54
        bar_x = label_w + 8
        bar_w = max(10, self.width() - bar_x - val_w)
        colors = th.chart_colors()
        p.setFont(_font(12))
        fm = p.fontMetrics()
        for i, (label, value, color) in enumerate(self.items):
            y = 4 + i * self.ROW
            p.setPen(QColor(t["text"]))
            p.drawText(QRectF(0, y, label_w, self.ROW - 8), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       fm.elidedText(str(label), Qt.TextElideMode.ElideRight, label_w))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t["surface2"]))
            p.drawRoundedRect(QRectF(bar_x, y + 6, bar_w, 14), 7, 7)
            w = max(6.0, bar_w * (value / vmax)) if value else 0
            if w:
                p.setBrush(QColor(color or colors[i % len(colors)]))
                p.drawRoundedRect(QRectF(bar_x, y + 6, w, 14), 7, 7)
            p.setPen(QColor(t["text"]))
            p.setFont(_font(12, True))
            p.drawText(QRectF(bar_x + bar_w + 8, y, val_w - 8, self.ROW - 8), Qt.AlignmentFlag.AlignVCenter, str(value))
            p.setFont(_font(12))
        p.end()


class DonutChart(QWidget):
    def __init__(self):
        super().__init__()
        self.items = []
        self.center_text = ""
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, items, center_text=""):
        """items: lista de (etiqueta, valor, color|None)."""
        self.items = [i for i in items if i[1] > 0]
        self.center_text = center_text
        self.update()

    def paintEvent(self, e):
        t = th.T
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = sum(v for _, v, _ in self.items)
        if not total:
            p.setPen(QColor(t["muted"]))
            p.setFont(_font(13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos todavía")
            p.end()
            return
        size = min(self.height() - 16, int(self.width() * 0.5), 230)
        rect = QRectF(10, (self.height() - size) / 2, size, size)
        colors = th.chart_colors()
        angle = 90 * 16
        for i, (label, value, color) in enumerate(self.items):
            span = -int(round(360 * 16 * value / total))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color or colors[i % len(colors)]))
            p.drawPie(rect, angle, span)
            angle += span
        hole = size * 0.58
        c = rect.center()
        p.setBrush(QColor(t["surface"]))
        p.drawEllipse(c, hole / 2, hole / 2)
        p.setPen(QColor(t["text"]))
        p.setFont(_font(24, True))
        p.drawText(QRectF(c.x() - hole / 2, c.y() - 22, hole, 30), Qt.AlignmentFlag.AlignCenter, self.center_text or str(total))
        p.setPen(QColor(t["muted"]))
        p.setFont(_font(12))
        p.drawText(QRectF(c.x() - hole / 2, c.y() + 6, hole, 20), Qt.AlignmentFlag.AlignCenter, "total")
        lx = rect.right() + 22
        ly = max(10, (self.height() - len(self.items) * 26) / 2)
        for i, (label, value, color) in enumerate(self.items):
            y = ly + i * 26
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color or colors[i % len(colors)]))
            p.drawRoundedRect(QRectF(lx, y + 5, 12, 12), 3, 3)
            p.setPen(QColor(t["text"]))
            p.setFont(_font(12))
            pct = value * 100 / total
            p.drawText(QRectF(lx + 20, y, max(40, self.width() - lx - 24), 22), Qt.AlignmentFlag.AlignVCenter,
                       f"{label}: {value} ({pct:.0f}%)")
        p.end()
