from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from PySide6.QtCore import Qt, QRectF, QPointF


class TrackPreview(QWidget):
    """Draws two simple 2D views of the built track:
      - top-down (X across, Z as depth) on the left
      - side profile (distance-along-track across, height up) on the right
    This intentionally avoids a full 3D dependency (OpenGL/etc.) so the
    app stays a single `pip install PySide6` away from running. A real
    3D preview is a natural follow-up once this MVP is validated."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []  # list of nl2designer.geometry.TrackPoint (rail path)
        self.heartline_points = []  # optional reference path
        self.setMinimumHeight(280)

    def set_points(self, points, heartline_points=None):
        self.points = points
        self.heartline_points = heartline_points or []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(24, 26, 30))

        if not self.points:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignCenter, "Add elements to see a preview")
            return

        w = self.width()
        h = self.height()
        half_w = w / 2

        self._draw_top_down(painter, QRectF(10, 10, half_w - 20, h - 20))
        self._draw_side_profile(painter, QRectF(half_w + 10, 10, half_w - 20, h - 20))

        painter.setPen(QColor(90, 90, 100))
        painter.drawLine(int(half_w), 0, int(half_w), h)

    def _draw_label(self, painter, rect, text):
        painter.setPen(QColor(170, 170, 180))
        painter.setFont(QFont("Sans", 9))
        painter.drawText(rect.adjusted(4, 2, -4, -2), Qt.AlignTop | Qt.AlignLeft, text)

    def _fit_transform(self, xs, ys, rect: QRectF, pad_frac=0.08):
        """Returns a function mapping (x, y) data coords -> QPointF pixel
        coords, fit to `rect` with equal aspect ratio and a small margin."""
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)

        pad = pad_frac * max(span_x, span_y)
        min_x -= pad; max_x += pad
        min_y -= pad; max_y += pad
        span_x = max_x - min_x
        span_y = max_y - min_y

        scale = min(rect.width() / span_x, rect.height() / span_y)

        def transform(x, y):
            px = rect.left() + (x - min_x) * scale
            # flip Y so "up" in data is up on screen
            py = rect.bottom() - (y - min_y) * scale
            return px, py

        return transform

    def _draw_polyline(self, painter, pts_xy, rect, color, label, dashed=False, transform=None):
        xs = [p[0] for p in pts_xy]
        ys = [p[1] for p in pts_xy]
        tf = transform or self._fit_transform(xs, ys, rect)

        pen = QPen(QColor(*color))
        pen.setWidthF(1.5 if dashed else 2.0)
        if dashed:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)

        polygon = QPolygonF([QPointF(*tf(x, y)) for x, y in pts_xy])
        painter.drawPolyline(polygon)

        if not dashed:
            sx, sy = tf(pts_xy[0][0], pts_xy[0][1])
            painter.setBrush(QColor(80, 220, 120))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(sx, sy), 4, 4)
            self._draw_label(painter, rect, label)

        return tf

    def _draw_top_down(self, painter, rect):
        pts_xy = [(p.pos[0], p.pos[2]) for p in self.points]
        tf = self._draw_polyline(painter, pts_xy, rect, (90, 170, 250), "Top-down (X / Z)  \u2014  solid = rails, dashed = heartline")
        if self.heartline_points:
            hl_xy = [(p.pos[0], p.pos[2]) for p in self.heartline_points]
            self._draw_polyline(painter, hl_xy, rect, (250, 220, 90), "", dashed=True, transform=tf)
        self._draw_closure_guide(painter, pts_xy[-1], pts_xy[0], tf)

    def _draw_side_profile(self, painter, rect):
        pts_xy = [(p.distance, p.pos[1]) for p in self.points]
        tf = self._draw_polyline(painter, pts_xy, rect, (250, 170, 90), "Side profile (distance / height)  \u2014  solid = rails, dashed = heartline")
        if self.heartline_points:
            hl_xy = [(p.distance, p.pos[1]) for p in self.heartline_points]
            self._draw_polyline(painter, hl_xy, rect, (120, 210, 255), "", dashed=True, transform=tf)
        # No closure guide on the side profile pane - "distance" on this
        # axis is cumulative arc length, not a spatial coordinate, so a
        # straight line back to (0, start_height) wouldn't mean anything.

    def _draw_closure_guide(self, painter, end_xy, start_xy, transform):
        """Dashed red/orange line from the end of the track straight back
        to the start - the vector you'd want to close a loop along."""
        pen = QPen(QColor(240, 90, 65))
        pen.setWidthF(1.4)
        pen.setStyle(Qt.DashDotLine)
        painter.setPen(pen)
        ex, ey = transform(*end_xy)
        sx, sy = transform(*start_xy)
        painter.drawLine(QPointF(ex, ey), QPointF(sx, sy))
