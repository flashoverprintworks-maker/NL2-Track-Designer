"""
NL2 Track Designer - GUI (milestone 2)

Run with:  python main.py

Layout:
  left    - Element palette. Drag an element onto the track list, or
            double-click to append it to the end.
  middle  - Track list. Drag to reorder. Double-click an item to edit
            its parameters. Del key removes the selected item.
  right   - Live preview (top-down + side profile) and a text summary,
            regenerated automatically whenever the track changes.
"""

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # so nl2designer/ is importable

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QListWidgetItem,
    QAbstractItemView, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QTextEdit, QLineEdit, QFileDialog, QMessageBox, QToolBar,
    QTabWidget, QDoubleSpinBox, QComboBox, QCheckBox,
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtCore import Qt, Signal

from nl2designer.track import Track
from nl2designer.export_csv import export_csv, validate_points

from gui.registry import ELEMENT_TYPES, default_params, build_element
from gui.param_dialog import ParamDialog
from gui.canvas import TrackPreview
from gui.canvas3d import Track3DView
from gui.gforce_chart import GForceChart
from gui.project_io import save_project, load_project
from gui.units import m_to_ft, ft_to_m, ms_to_kmh, kmh_to_ms, ms_to_mph, mph_to_ms


class ElementPalette(QListWidget):
    """The list of element types you can drag into the track."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        for key, spec in ELEMENT_TYPES.items():
            item = QListWidgetItem(spec["label"])
            item.setData(Qt.UserRole, key)
            item.setToolTip("Drag onto the track list, or double-click to append")
            self.addItem(item)

    def mimeData(self, items):
        md = super().mimeData(items)
        if items:
            md.setText(items[0].data(Qt.UserRole))
        return md


class TrackList(QListWidget):
    """The ordered list of elements that makes up the ride. Accepts drops
    from the palette (adds a new element) and reorders internally."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def _row_at(self, event) -> int:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        row = self.indexAt(pos).row()
        return row if row >= 0 else self.count()

    def dropEvent(self, event):
        source = event.source()
        if source is self:
            super().dropEvent(event)
            self.changed.emit()
            return
        if isinstance(source, ElementPalette):
            type_key = event.mimeData().text()
            if type_key in ELEMENT_TYPES:
                row = self._row_at(event)
                self.insert_element(row, type_key)
                event.acceptProposedAction()
                self.changed.emit()
            return
        event.ignore()

    def insert_element(self, row: int, type_key: str, name: str = "", params: dict = None):
        spec = ELEMENT_TYPES[type_key]
        params = params if params is not None else default_params(type_key)
        display_name = name or spec["label"]
        item = QListWidgetItem(display_name)
        item.setData(Qt.UserRole, {"type": type_key, "name": display_name, "params": params})
        self.insertItem(row, item)
        return item

    def append_element(self, type_key: str):
        self.insert_element(self.count(), type_key)
        self.changed.emit()

    def item_data_list(self):
        out = []
        for i in range(self.count()):
            out.append(self.item(i).data(Qt.UserRole))
        return out

    def remove_selected(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))
        self.changed.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NL2 Track Designer")
        self.resize(1200, 720)
        self.current_project_path = None
        self.units = "m"  # "m" or "ft" - display only, engine/export always metric

        # --- Left: palette ---------------------------------------------
        palette_box = QWidget()
        palette_layout = QVBoxLayout(palette_box)
        palette_layout.addWidget(QLabel("<b>Elements</b>  (drag or double-click)"))
        self.palette = ElementPalette()
        self.palette.itemDoubleClicked.connect(self._append_from_palette)
        palette_layout.addWidget(self.palette)

        # --- Middle: track list + controls -------------------------------
        track_box = QWidget()
        track_layout = QVBoxLayout(track_box)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Track name:"))
        self.name_edit = QLineEdit("My Coaster")
        self.name_edit.editingFinished.connect(self._refresh)
        name_row.addWidget(self.name_edit)

        name_row.addWidget(QLabel("Heartline offset:"))
        self.heartline_spin = QDoubleSpinBox()
        self.heartline_spin.setDecimals(2)
        self.heartline_spin.setToolTip(
            "Distance from the design path (heartline - where a rider's\n"
            "center of mass travels) down to the physical rail centerline.\n"
            "~1.0-1.2m is typical for a sit-down coaster. Set to 0 to export\n"
            "the heartline itself with no offset."
        )
        self._apply_units_to_heartline_spin()
        self.heartline_spin.setValue(1.1)
        self.heartline_spin.valueChanged.connect(self._refresh)
        name_row.addWidget(self.heartline_spin)
        track_layout.addLayout(name_row)

        style_row = QHBoxLayout()
        self.arrow_style_check = QCheckBox("Arrow Dynamics style (abrupt transitions)")
        self.arrow_style_check.setToolTip(
            "Forces every element's pitch/yaw/roll transitions to constant-\n"
            "rate instead of smoothly eased - the G-force arrives all at once\n"
            "at each element boundary, matching the un-eased, hand-drafted\n"
            "feel of pre-CAD track (Arrow Dynamics being the classic example),\n"
            "instead of the gradual clothoid-style ramps modern manufacturers use."
        )
        self.arrow_style_check.stateChanged.connect(self._refresh)
        style_row.addWidget(self.arrow_style_check)

        style_row.addWidget(QLabel("Roughness (deg):"))
        self.roughness_spin = QDoubleSpinBox()
        self.roughness_spin.setRange(0.0, 3.0)
        self.roughness_spin.setSingleStep(0.1)
        self.roughness_spin.setDecimals(2)
        self.roughness_spin.setValue(0.0)
        self.roughness_spin.setToolTip(
            "Peak degrees of banking \"wobble\" layered onto the finished rail\n"
            "path - stands in for the imprecise, hand-surveyed feel of track\n"
            "built without modern measurement/CAD tools. 0 = off. Try 0.3-0.8\n"
            "before going further; it adds up fast."
        )
        self.roughness_spin.valueChanged.connect(self._refresh)
        style_row.addWidget(self.roughness_spin)
        style_row.addStretch()
        track_layout.addLayout(style_row)

        physics_row = QHBoxLayout()
        physics_row.addWidget(QLabel("Start speed:"))
        self.start_speed_spin = QDoubleSpinBox()
        self.start_speed_spin.setDecimals(1)
        self.start_speed_spin.setToolTip(
            "Speed at the very first point of the track (e.g. leaving the\n"
            "station). Energy conservation carries this forward for the\n"
            "estimated speed/G-force chart. If your layout includes a chain\n"
            "lift, treat the pre-lift-crest numbers as not physically\n"
            "meaningful - a real lift is chain-driven, not momentum-driven."
        )
        self._apply_units_to_speed_spin()
        self._set_start_speed_spin_from_ms(2.0)  # ~7 km/h, leaving the station slowly
        self.start_speed_spin.valueChanged.connect(self._refresh)
        physics_row.addWidget(self.start_speed_spin)

        physics_row.addWidget(QLabel("Friction:"))
        self.friction_spin = QDoubleSpinBox()
        self.friction_spin.setRange(0.0, 0.15)
        self.friction_spin.setSingleStep(0.005)
        self.friction_spin.setDecimals(3)
        self.friction_spin.setValue(0.02)
        self.friction_spin.setToolTip(
            "Simplified rolling resistance + air drag coefficient (unitless).\n"
            "0 = frictionless/idealized. Real losses depend on train mass,\n"
            "wheel type, and speed-squared drag, none of which this models -\n"
            "treat this as a rough dial, not an engineering figure."
        )
        self.friction_spin.valueChanged.connect(self._refresh)
        physics_row.addWidget(self.friction_spin)
        physics_row.addStretch()
        track_layout.addLayout(physics_row)

        self.track_list = TrackList()
        self.track_list.changed.connect(self._refresh)
        self.track_list.itemDoubleClicked.connect(self._edit_item)
        self.track_list.currentRowChanged.connect(self._update_closure_labels)
        track_layout.addWidget(self.track_list)

        closure_box = QWidget()
        closure_layout = QVBoxLayout(closure_box)
        closure_layout.setContentsMargins(0, 4, 0, 4)
        closure_layout.setSpacing(2)
        title = QLabel("<b>Distance back to start</b> (helps close the loop)")
        closure_layout.addWidget(title)
        self.closure_end_label = QLabel("End of track: -")
        self.closure_selected_label = QLabel("Selected element: -")
        for lbl in (self.closure_end_label, self.closure_selected_label):
            lbl.setStyleSheet("font-family: monospace;")
            lbl.setWordWrap(True)
            closure_layout.addWidget(lbl)
        track_layout.addWidget(closure_box)

        btn_row = QHBoxLayout()
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        up_btn = QPushButton("Move up")
        up_btn.clicked.connect(lambda: self._move_selected(-1))
        down_btn = QPushButton("Move down")
        down_btn.clicked.connect(lambda: self._move_selected(1))
        btn_row.addWidget(remove_btn)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        track_layout.addLayout(btn_row)

        # --- Right: preview + summary -----------------------------------
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)

        preview_tabs = QTabWidget()
        self.preview3d = Track3DView()
        self.preview = TrackPreview()
        self.gforce_chart = GForceChart()
        preview_tabs.addTab(self.preview3d, "3D")
        preview_tabs.addTab(self.preview, "2D (top-down / profile)")
        preview_tabs.addTab(self.gforce_chart, "Speed / G-Forces")
        right_layout.addWidget(preview_tabs, stretch=3)

        hint = QLabel("3D controls: left-drag orbit, right-drag (or Shift+drag) pan, scroll to zoom.")
        hint.setStyleSheet("color: #888;")
        right_layout.addWidget(hint)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(220)
        right_layout.addWidget(self.summary_text, stretch=1)

        # --- Assemble ------------------------------------------------------
        splitter = QSplitter()
        splitter.addWidget(palette_box)
        splitter.addWidget(track_box)
        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 3)
        self.setCentralWidget(splitter)

        self._build_menu()

        del_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.track_list)
        del_shortcut.activated.connect(self._remove_selected)

        # Undo/redo: snapshot-based (see _capture_state/_restore_state).
        # Keyboard shortcuts are attached to the toolbar actions below.
        self._undo_stack = []
        self._redo_stack = []
        self._last_committed_state = None
        self._restoring = False

        self._refresh()

    # ------------------------------------------------------------------
    def _build_menu(self):
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)

        new_action = QAction("New", self)
        new_action.triggered.connect(self._new_project)
        toolbar.addAction(new_action)

        open_action = QAction("Open...", self)
        open_action.triggered.connect(self._open_project)
        toolbar.addAction(open_action)

        save_action = QAction("Save...", self)
        save_action.triggered.connect(self._save_project)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        toolbar.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Y")])
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        toolbar.addAction(self.redo_action)

        toolbar.addSeparator()

        export_action = QAction("Export CSV for NL2...", self)
        export_action.triggered.connect(self._export_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Units: "))
        self.units_combo = QComboBox()
        self.units_combo.addItems(["Meters", "Feet"])
        self.units_combo.currentIndexChanged.connect(self._on_units_changed)
        toolbar.addWidget(self.units_combo)

    def _apply_units_to_heartline_spin(self):
        """Reconfigure the heartline spinbox's range/step/suffix for the
        current display units, preserving its current value (converted)."""
        current_m = self._heartline_offset_m() if hasattr(self, "heartline_spin") else 1.1
        if self.units == "ft":
            self.heartline_spin.setRange(0.0, m_to_ft(3.0))
            self.heartline_spin.setSingleStep(0.1)
            self.heartline_spin.setSuffix(" ft")
        else:
            self.heartline_spin.setRange(0.0, 3.0)
            self.heartline_spin.setSingleStep(0.05)
            self.heartline_spin.setSuffix(" m")
        self._set_heartline_spin_from_m(current_m)

    def _heartline_offset_m(self) -> float:
        """Current heartline offset in meters, converting from the spin
        box's displayed units if needed."""
        v = self.heartline_spin.value()
        return ft_to_m(v) if self.units == "ft" else v

    def _set_heartline_spin_from_m(self, meters: float):
        v = m_to_ft(meters) if self.units == "ft" else meters
        self.heartline_spin.blockSignals(True)
        self.heartline_spin.setValue(v)
        self.heartline_spin.blockSignals(False)

    def _apply_units_to_speed_spin(self):
        """Same idea as _apply_units_to_heartline_spin, but for the start-
        speed field: km/h when metric, mph when imperial (matching what
        people actually use for vehicle speeds in each system, rather
        than literally converting the length-unit toggle)."""
        current_ms = self._start_speed_ms() if hasattr(self, "start_speed_spin") else 2.0
        if self.units == "ft":
            self.start_speed_spin.setRange(0.0, ms_to_mph(60.0))
            self.start_speed_spin.setSingleStep(0.5)
            self.start_speed_spin.setSuffix(" mph")
        else:
            self.start_speed_spin.setRange(0.0, ms_to_kmh(60.0))
            self.start_speed_spin.setSingleStep(0.5)
            self.start_speed_spin.setSuffix(" km/h")
        self._set_start_speed_spin_from_ms(current_ms)

    def _start_speed_ms(self) -> float:
        v = self.start_speed_spin.value()
        return mph_to_ms(v) if self.units == "ft" else kmh_to_ms(v)

    def _set_start_speed_spin_from_ms(self, ms: float):
        v = ms_to_mph(ms) if self.units == "ft" else ms_to_kmh(ms)
        self.start_speed_spin.blockSignals(True)
        self.start_speed_spin.setValue(v)
        self.start_speed_spin.blockSignals(False)

    def _on_units_changed(self, idx: int):
        new_units = "m" if idx == 0 else "ft"
        if new_units == self.units:
            return
        current_m = self._heartline_offset_m()
        current_speed_ms = self._start_speed_ms()
        self.units = new_units
        self._apply_units_to_heartline_spin()
        self._set_heartline_spin_from_m(current_m)
        self._apply_units_to_speed_spin()
        self._set_start_speed_spin_from_ms(current_speed_ms)
        self._refresh()

    # ------------------------------------------------------------------
    def _append_from_palette(self, item: QListWidgetItem):
        type_key = item.data(Qt.UserRole)
        self.track_list.append_element(type_key)

    def _edit_item(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        dlg = ParamDialog(data["type"], data["params"], data["name"], units=self.units, parent=self)
        if dlg.exec() == ParamDialog.Accepted:
            data["params"] = dlg.result_params()
            data["name"] = dlg.result_name() or ELEMENT_TYPES[data["type"]]["label"]
            item.setData(Qt.UserRole, data)
            item.setText(data["name"])
            self._refresh()

    def _remove_selected(self):
        self.track_list.remove_selected()

    def _move_selected(self, delta: int):
        row = self.track_list.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= self.track_list.count():
            return
        item = self.track_list.takeItem(row)
        self.track_list.insertItem(new_row, item)
        self.track_list.setCurrentRow(new_row)
        self._refresh()

    # ------------------------------------------------------------------
    def _build_track(self):
        """Returns (track, heartline_points, rail_points, warnings,
        row_element_counts) or raises with a friendly message.
        row_element_counts[i] is how many flattened ElementSpecs track
        list row i produced (composites like Immelmann/Cobra Roll/Lift
        Hill expand to more than one) - needed to look up "position after
        row N" for the closure readout."""
        track = Track(
            name=self.name_edit.text() or "Untitled Track",
            heartline_offset=self._heartline_offset_m(),
            arrow_style=self.arrow_style_check.isChecked(),
            roughness_deg=self.roughness_spin.value(),
            start_speed_ms=self._start_speed_ms(),
            friction_coef=self.friction_spin.value(),
        )
        row_element_counts = []
        for entry in self.track_list.item_data_list():
            spec = build_element(entry["type"], entry["params"], entry["name"])
            row_element_counts.append(len(spec) if isinstance(spec, list) else 1)
            track.add(spec)
        if not track.elements:
            return track, [], [], [], row_element_counts
        heartline_points = track.build()
        rail_points = track.build_rail_points()
        warnings = validate_points(rail_points)
        return track, heartline_points, rail_points, warnings, row_element_counts

    def _closest_point(self, points, target_distance):
        if not points:
            return None
        return min(points, key=lambda p: abs(p.distance - target_distance))

    def _format_closure(self, offset: dict) -> str:
        def fmt(v):
            v = m_to_ft(v) if self.units == "ft" else v
            return f"{v:+.1f}"
        unit = "ft" if self.units == "ft" else "m"
        return (f"\u0394X={fmt(offset['dx'])}{unit}  \u0394Y={fmt(offset['dy'])}{unit}  "
                f"\u0394Z={fmt(offset['dz'])}{unit}  dist={fmt(offset['distance']).lstrip('+')}{unit}")

    def _update_closure_labels(self, *_args):
        track = getattr(self, "_last_track", None)
        rail_points = getattr(self, "_last_rail_points", None)
        row_distances = getattr(self, "_last_row_distances", None)
        if not track or not rail_points:
            self.closure_end_label.setText("End of track: -")
            self.closure_selected_label.setText("Selected element: -")
            return

        end_offset = track.closure_offset(rail_points)
        self.closure_end_label.setText("End of track:      " + self._format_closure(end_offset))

        row = self.track_list.currentRow()
        if row is None or row < 0 or not row_distances or row >= len(row_distances):
            self.closure_selected_label.setText("Selected element:  (select an item in the track list)")
            return
        target_dist = row_distances[row]
        point = self._closest_point(rail_points, target_dist)
        start = rail_points[0].pos
        dx, dy, dz = point.pos[0] - start[0], point.pos[1] - start[1], point.pos[2] - start[2]
        offset = {"dx": dx, "dy": dy, "dz": dz, "distance": math.sqrt(dx * dx + dy * dy + dz * dz)}
        self.closure_selected_label.setText("Selected element:  " + self._format_closure(offset))

    # --- Undo/redo -----------------------------------------------------
    def _capture_state(self) -> dict:
        return {
            "track_name": self.name_edit.text(),
            "items": self.track_list.item_data_list(),
            "heartline_offset": self._heartline_offset_m(),
            "arrow_style": self.arrow_style_check.isChecked(),
            "roughness_deg": self.roughness_spin.value(),
            "start_speed_ms": self._start_speed_ms(),
            "friction_coef": self.friction_spin.value(),
        }

    def _restore_state(self, state: dict):
        self._restoring = True
        try:
            self.track_list.clear()
            self.name_edit.setText(state["track_name"])
            self._set_heartline_spin_from_m(state["heartline_offset"])
            self.arrow_style_check.setChecked(state["arrow_style"])
            self.roughness_spin.setValue(state["roughness_deg"])
            self._set_start_speed_spin_from_ms(state["start_speed_ms"])
            self.friction_spin.setValue(state["friction_coef"])
            for entry in state["items"]:
                self.track_list.insert_element(
                    self.track_list.count(), entry["type"], entry.get("name", ""), entry.get("params")
                )
        finally:
            self._restoring = False
        self._refresh()

    def _update_undo_redo_actions(self):
        self.undo_action.setEnabled(bool(self._undo_stack))
        self.redo_action.setEnabled(bool(self._redo_stack))

    def _undo(self):
        if not self._undo_stack:
            return
        current = self._capture_state()
        self._redo_stack.append(current)
        prev_state = self._undo_stack.pop()
        self._last_committed_state = prev_state
        self._update_undo_redo_actions()
        self._restore_state(prev_state)

    def _redo(self):
        if not self._redo_stack:
            return
        current = self._capture_state()
        self._undo_stack.append(current)
        next_state = self._redo_stack.pop()
        self._last_committed_state = next_state
        self._update_undo_redo_actions()
        self._restore_state(next_state)

    def _refresh(self):
        if not self._restoring:
            current_state = self._capture_state()
            if self._last_committed_state is not None and current_state != self._last_committed_state:
                self._undo_stack.append(self._last_committed_state)
                self._redo_stack.clear()
                if len(self._undo_stack) > 100:
                    self._undo_stack.pop(0)
                self._update_undo_redo_actions()
            self._last_committed_state = current_state

        try:
            track, heartline_points, rail_points, warnings, row_element_counts = self._build_track()
        except Exception as exc:  # noqa: BLE001 - surface any build error to the user
            self.summary_text.setPlainText(f"Error building track:\n{exc}")
            self.preview.set_points([])
            self.preview3d.set_points([])
            self._last_track = None
            self._last_rail_points = None
            self._last_row_distances = None
            self._update_closure_labels()
            return

        self.preview.set_points(rail_points, heartline_points)
        self.preview3d.set_points(rail_points, heartline_points)

        self._last_track = track
        self._last_rail_points = rail_points
        self._last_row_distances = track.row_end_distances(row_element_counts) if track.elements else []
        self._update_closure_labels()

        if not rail_points:
            self.summary_text.setPlainText("Add elements to the track list to see a summary here.")
            self.gforce_chart.set_data([], [], [])
            return

        speeds = track.speed_profile(rail_points)
        gforces = track.g_forces(rail_points, speeds)
        self.gforce_chart.set_data(rail_points, gforces, speeds)
        physics_warnings = track.physics_warnings(rail_points)

        lines = [track.summary(), ""]
        lines.append(f"{len(rail_points)} sample points, {rail_points[-1].distance:.1f} m total.")
        lines.append(f"Heartline offset: {track.heartline_offset:.2f} m "
                      f"(rails exported {track.heartline_offset:.2f} m below the design path).")
        if track.arrow_style or track.roughness_deg > 0:
            style_bits = []
            if track.arrow_style:
                style_bits.append("abrupt (Arrow-style) transitions")
            if track.roughness_deg > 0:
                style_bits.append(f"{track.roughness_deg:.2f} deg roughness")
            lines.append(f"Track style: {', '.join(style_bits)}.")

        top_speed_ms = max(speeds)
        top_speed_disp = ms_to_mph(top_speed_ms) if self.units == "ft" else ms_to_kmh(top_speed_ms)
        speed_unit = "mph" if self.units == "ft" else "km/h"
        max_vg = max(g[0] for g in gforces)
        min_vg = min(g[0] for g in gforces)
        max_lg = max(abs(g[1]) for g in gforces)
        lines.append(f"Estimated top speed: {top_speed_disp:.1f} {speed_unit}.  "
                      f"Vertical G range: {min_vg:+.1f} to {max_vg:+.1f}.  Peak lateral G: {max_lg:.1f}.")
        if physics_warnings:
            lines.append(f"\n{len(physics_warnings)} speed/G-force note(s):")
            lines.extend("  " + w for w in physics_warnings[:6])
            if len(physics_warnings) > 6:
                lines.append(f"  ... and {len(physics_warnings) - 6} more (see Speed / G-Forces tab)")

        if self.units == "ft":
            lines.append("(Display units: feet. Figures above are always meters - "
                          "NL2 export is always metric regardless of display units.)")
        if warnings:
            lines.append(f"\n{len(warnings)} geometry warning(s):")
            lines.extend("  " + w for w in warnings[:8])
            if len(warnings) > 8:
                lines.append(f"  ... and {len(warnings) - 8} more")
        else:
            lines.append("Geometry OK (frame stayed orthonormal).")
        self.summary_text.setPlainText("\n".join(lines))

    def _reset_undo_history(self):
        self._undo_stack = []
        self._redo_stack = []
        self._last_committed_state = None
        self._update_undo_redo_actions()

    # ------------------------------------------------------------------
    def _new_project(self):
        self.track_list.clear()
        self.name_edit.setText("My Coaster")
        self._set_heartline_spin_from_m(1.1)
        self.arrow_style_check.setChecked(False)
        self.roughness_spin.setValue(0.0)
        self._set_start_speed_spin_from_ms(2.0)
        self.friction_spin.setValue(0.02)
        self.current_project_path = None
        self._reset_undo_history()
        self._refresh()

    def _save_project(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save project", "", "NL2 Designer Project (*.json)")
        if not path:
            return
        items = self.track_list.item_data_list()
        save_project(
            path, self.name_edit.text(), items, self._heartline_offset_m(),
            self.arrow_style_check.isChecked(), self.roughness_spin.value(),
            self._start_speed_ms(), self.friction_spin.value(),
        )
        self.current_project_path = path

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", "NL2 Designer Project (*.json)")
        if not path:
            return
        try:
            (track_name, items, heartline_offset, arrow_style, roughness_deg,
             start_speed_ms, friction_coef) = load_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self.track_list.clear()
        self.name_edit.setText(track_name)
        self._set_heartline_spin_from_m(heartline_offset)
        self.arrow_style_check.setChecked(arrow_style)
        self.roughness_spin.setValue(roughness_deg)
        self._set_start_speed_spin_from_ms(start_speed_ms)
        self.friction_spin.setValue(friction_coef)
        for entry in items:
            self.track_list.insert_element(
                self.track_list.count(), entry["type"], entry.get("name", ""), entry.get("params")
            )
        self.current_project_path = path
        self._reset_undo_history()
        self._refresh()

    def _export_csv(self):
        try:
            track, heartline_points, rail_points, warnings, _row_counts = self._build_track()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Cannot export", str(exc))
            return
        if not rail_points:
            QMessageBox.warning(self, "Nothing to export", "Add at least one element first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Track Spline CSV", "", "CSV (*.csv)")
        if not path:
            return
        export_csv(rail_points, path)
        msg = (f"Exported {len(rail_points)} points to:\n{path}\n\n"
               f"(rail path, {track.heartline_offset:.2f}m below the design heartline)\n\n"
               f"In NL2: Coaster tab -> Import -> Track Spline.")
        if warnings:
            msg += f"\n\nNote: {len(warnings)} geometry warning(s) were found - see the summary panel."
        QMessageBox.information(self, "Exported", msg)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
