from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtCore import Qt, QRectF, QPointF

from nl2designer.physics import LIMIT_VERTICAL_G_MAX, LIMIT_VERTICAL_G_MIN, LIMIT_LATERAL_G


class GForceChart(QWidget):
    """Vertical G and lateral G plotted against distance along the track,
    with dashed reference lines at the ASTM F2291-referenced brief-peak
    comfort limits (see physics.py). Native QPainter, no chart library
    dependency, consistent with the other preview widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.g_forces = []  # list of (vertical_g, lateral_g)
        self.speeds = []  # m/s, parallel to points
        self.setMinimumHeight(220)

    def set_data(self, points, g_forces, speeds):
        self.points = points
        self.g_forces = g_forces
        self.speeds = speeds
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(24, 26, 30))

        if not self.points or not self.g_forces:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignCenter, "Add elements to see estimated speed and G-forces")
            return

        margin_left, margin_right, margin_top, margin_bottom = 46, 14, 24, 28
        rect = QRectF(margin_left, margin_top,
                       self.width() - margin_left - margin_right,
                       self.height() - margin_top - margin_bottom)

        distances = [p.distance for p in self.points]
        vgs = [g[0] for g in self.g_forces]
        lgs = [g[1] for g in self.g_forces]

        g_min = min(vgs + lgs + [LIMIT_VERTICAL_G_MIN, -LIMIT_LATERAL_G]) - 0.5
        g_max = max(vgs + lgs + [LIMIT_VERTICAL_G_MAX, LIMIT_LATERAL_G]) + 0.5
        d_min, d_max = distances[0], max(distances[-1], distances[0] + 1e-6)

        def tf(d, g):
            x = rect.left() + (d - d_min) / (d_max - d_min) * rect.width()
            y = rect.bottom() - (g - g_min) / (g_max - g_min) * rect.height()
            return x, y

        # Zero-G and reference limit lines.
        for value, color, label in [
            (0.0, (90, 90, 100), None),
            (1.0, (70, 70, 80), None),
            (LIMIT_VERTICAL_G_MAX, (200, 90, 70), f"+{LIMIT_VERTICAL_G_MAX:.1f}G limit"),
            (LIMIT_VERTICAL_G_MIN, (200, 90, 70), f"{LIMIT_VERTICAL_G_MIN:.1f}G limit"),
            (LIMIT_LATERAL_G, (200, 160, 70), f"\u00b1{LIMIT_LATERAL_G:.1f}G lateral limit"),
            (-LIMIT_LATERAL_G, (200, 160, 70), None),
        ]:
            if not (g_min <= value <= g_max):
                continue
            _, y = tf(d_min, value)
            pen = QPen(QColor(*color))
            pen.setStyle(Qt.DashLine if value not in (0.0, 1.0) else Qt.DotLine)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            if label:
                painter.setPen(QColor(*color))
                painter.setFont(QFont("Sans", 8))
                painter.drawText(QPointF(rect.right() - 110, y - 3), label)

        # Y axis labels.
        painter.setPen(QColor(150, 150, 150))
        painter.setFont(QFont("Sans", 8))
        for g_tick in range(int(g_min) - 1, int(g_max) + 2):
            if not (g_min <= g_tick <= g_max):
                continue
            _, y = tf(d_min, g_tick)
            painter.drawText(QPointF(4, y + 4), f"{g_tick:+d}G")

        # Vertical G line (blue) and lateral G line (orange).
        for series, color, name in [(vgs, (90, 170, 250), "Vertical G"), (lgs, (250, 170, 90), "Lateral G")]:
            pen = QPen(QColor(*color))
            pen.setWidthF(1.8)
            painter.setPen(pen)
            poly = QPolygonF([QPointF(*tf(d, g)) for d, g in zip(distances, series)])
            painter.drawPolyline(poly)

        painter.setFont(QFont("Sans", 9))
        painter.setPen(QColor(90, 170, 250))
        painter.drawText(QPointF(margin_left, 16), "Vertical G")
        painter.setPen(QColor(250, 170, 90))
        painter.drawText(QPointF(margin_left + 80, 16), "Lateral G")

        painter.setPen(QColor(150, 150, 150))
        painter.drawText(QPointF(rect.left(), self.height() - 8), "distance along track \u2192")
