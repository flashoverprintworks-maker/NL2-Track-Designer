"""
3D preview of the track using PyOpenGL inside a QOpenGLWidget.

Renders:
  - two rails, offset left/right of the center spline by half the track
    gauge, so banking is actually visible (not just a single wire)
  - cross-ties connecting the rails every few samples, which is what
    really sells the banking/roll visually
  - a ground grid for spatial reference
  - the start point highlighted

Camera: left-drag to orbit, right-drag (or Shift+left-drag) to pan,
scroll wheel to zoom. View auto-fits to the track's bounding box
whenever a new track is loaded.
"""

import math

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat

from OpenGL.GL import *

from nl2designer.geometry import v_add, v_sub, v_scale, v_cross, v_normalize, v_dot

TRACK_GAUGE = 1.435  # meters between rails (NL2/real-world standard gauge)
TIE_EVERY_N_POINTS = 8


def _perspective_matrix(fovy_deg, aspect, near, far):
    """Column-major 4x4 perspective matrix, equivalent to gluPerspective,
    built from core GL primitives only (no GLU dependency)."""
    f = 1.0 / math.tan(math.radians(fovy_deg) / 2.0)
    m = [0.0] * 16
    m[0] = f / aspect
    m[5] = f
    m[10] = (far + near) / (near - far)
    m[11] = -1.0
    m[14] = (2 * far * near) / (near - far)
    return m


def _look_at_matrix(eye, target, up):
    """Column-major 4x4 view matrix, equivalent to gluLookAt."""
    f = v_normalize(v_sub(target, eye))
    s = v_normalize(v_cross(f, up))
    u = v_cross(s, f)
    m = [
        s[0], u[0], -f[0], 0.0,
        s[1], u[1], -f[1], 0.0,
        s[2], u[2], -f[2], 0.0,
        -v_dot(s, eye), -v_dot(u, eye), v_dot(f, eye), 1.0,
    ]
    return m


class Track3DView(QOpenGLWidget):
    def __init__(self, parent=None):
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setSamples(4)  # anti-aliasing
        QSurfaceFormat.setDefaultFormat(fmt)
        super().__init__(parent)

        self.points = []
        self.heartline_points = []
        self._center = [0.0, 0.0, 0.0]
        self._radius = 50.0

        # Camera state (orbit around self._center).
        self.azimuth_deg = 45.0
        self.elevation_deg = 25.0
        self.distance = 150.0
        self.pan = [0.0, 0.0, 0.0]

        self._last_mouse = None
        self.setMinimumHeight(300)
        self.setFocusPolicy(Qt.StrongFocus)

    # ------------------------------------------------------------------
    def set_points(self, points, heartline_points=None):
        self.points = points
        self.heartline_points = heartline_points or []
        if points:
            xs = [p.pos[0] for p in points]
            ys = [p.pos[1] for p in points]
            zs = [p.pos[2] for p in points]
            self._center = [
                (min(xs) + max(xs)) / 2.0,
                (min(ys) + max(ys)) / 2.0,
                (min(zs) + max(zs)) / 2.0,
            ]
            span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 10.0)
            self._radius = span / 2.0
            self.distance = span * 1.6
            self.pan = [0.0, 0.0, 0.0]
        self.update()

    # ------------------------------------------------------------------
    def initializeGL(self):
        glClearColor(0.09, 0.10, 0.12, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glLineWidth(2.0)

    def resizeGL(self, w, h):
        glViewport(0, 0, max(w, 1), max(h, 1))

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        w = max(self.width(), 1)
        h = max(self.height(), 1)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        proj = _perspective_matrix(45.0, w / h, 0.1, max(self.distance * 20, 500.0))
        glMultMatrixf(proj)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        eye = self._camera_eye()
        target = v_add(self._center, self.pan)
        view = _look_at_matrix(eye, target, [0.0, 1.0, 0.0])
        glMultMatrixf(view)

        self._draw_ground_grid()
        if self.points:
            self._draw_track()
        if self.heartline_points:
            self._draw_heartline()
        self._draw_closure_guide()

    # ------------------------------------------------------------------
    def _camera_eye(self):
        az = math.radians(self.azimuth_deg)
        el = math.radians(self.elevation_deg)
        x = self.distance * math.cos(el) * math.sin(az)
        y = self.distance * math.sin(el)
        z = self.distance * math.cos(el) * math.cos(az)
        target = v_add(self._center, self.pan)
        return [target[0] + x, target[1] + y, target[2] + z]

    def _draw_ground_grid(self):
        ground_y = self._center[1] - self._radius - 1.0
        size = max(self._radius * 3.0, 40.0)
        step = max(size / 20.0, 1.0)

        glColor3f(0.25, 0.27, 0.30)
        glBegin(GL_LINES)
        n = int(size / step)
        cx, cz = self._center[0], self._center[2]
        for i in range(-n, n + 1):
            x = cx + i * step
            glVertex3f(x, ground_y, cz - size)
            glVertex3f(x, ground_y, cz + size)
            z = cz + i * step
            glVertex3f(cx - size, ground_y, z)
            glVertex3f(cx + size, ground_y, z)
        glEnd()

    def _rail_positions(self, p):
        half = TRACK_GAUGE / 2.0
        left_offset = v_scale(p.left, half)
        return v_add(p.pos, left_offset), v_sub(p.pos, left_offset)

    def _draw_track(self):
        # Rails.
        glColor3f(0.85, 0.85, 0.9)
        glBegin(GL_LINE_STRIP)
        for p in self.points:
            l, _ = self._rail_positions(p)
            glVertex3f(*l)
        glEnd()
        glBegin(GL_LINE_STRIP)
        for p in self.points:
            _, r = self._rail_positions(p)
            glVertex3f(*r)
        glEnd()

        # Ties (also doubles as the clearest visual read on banking).
        glColor3f(0.55, 0.4, 0.25)
        glBegin(GL_LINES)
        for i, p in enumerate(self.points):
            if i % TIE_EVERY_N_POINTS != 0:
                continue
            l, r = self._rail_positions(p)
            glVertex3f(*l)
            glVertex3f(*r)
        glEnd()

        # Start marker.
        glColor3f(0.3, 0.9, 0.4)
        glPointSize(9.0)
        glBegin(GL_POINTS)
        glVertex3f(*self.points[0].pos)
        glEnd()

    def _draw_heartline(self):
        """Thin dashed yellow reference line showing the design path
        (heartline) the rails were offset from - lets you see how much
        the offset is actually shifting things, especially in loops."""
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(2, 0x00FF)
        glColor3f(0.95, 0.85, 0.35)
        glLineWidth(1.3)
        glBegin(GL_LINE_STRIP)
        for p in self.heartline_points:
            glVertex3f(*p.pos)
        glEnd()
        glLineWidth(2.0)
        glDisable(GL_LINE_STIPPLE)

    def _draw_closure_guide(self):
        """Dashed red/orange line from the end of the track straight back
        to the start - the vector you'd want to close a loop along, shown
        at a glance instead of just as numbers in the closure readout."""
        if len(self.points) < 2:
            return
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(3, 0x3333)
        glColor3f(0.95, 0.35, 0.25)
        glLineWidth(1.6)
        glBegin(GL_LINES)
        glVertex3f(*self.points[-1].pos)
        glVertex3f(*self.points[0].pos)
        glEnd()
        glLineWidth(2.0)
        glDisable(GL_LINE_STIPPLE)

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, event):
        self._last_mouse = event.position()

    def mouseMoveEvent(self, event):
        if self._last_mouse is None:
            self._last_mouse = event.position()
            return
        dx = event.position().x() - self._last_mouse.x()
        dy = event.position().y() - self._last_mouse.y()
        self._last_mouse = event.position()

        panning = bool(event.buttons() & Qt.RightButton) or bool(event.modifiers() & Qt.ShiftModifier)
        if panning:
            scale = self.distance * 0.0015
            az = math.radians(self.azimuth_deg)
            right = [math.cos(az), 0, -math.sin(az)]
            up = [0, 1, 0]
            self.pan = v_add(self.pan, v_scale(right, -dx * scale))
            self.pan = v_add(self.pan, v_scale(up, dy * scale))
        elif event.buttons() & Qt.LeftButton:
            self.azimuth_deg -= dx * 0.4
            self.elevation_deg = max(-89, min(89, self.elevation_deg + dy * 0.4))
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 0.9 if delta > 0 else 1.1
        self.distance = max(5.0, self.distance * factor)
        self.update()
