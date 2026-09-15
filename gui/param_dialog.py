from PySide6.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QComboBox, QLineEdit,
    QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QWidget,
)

from gui.registry import ELEMENT_TYPES
from gui.units import m_to_ft, ft_to_m, ms_to_kmh, ms_to_mph
from nl2designer.physics import solve_radius_hill, solve_radius_flat_turn, solve_radius_loop


class ParamDialog(QDialog):
    """Auto-generated form for editing one element's parameters, based on
    the param spec list in registry.ELEMENT_TYPES. Adding a new element
    type or parameter to the registry needs no changes here.

    `units` is "m" or "ft" - it only affects how fields whose unit label
    is exactly "m" (lengths/radii/heights) are displayed and entered;
    the underlying stored values (and everything else - angles, turn
    counts, etc.) are always meters/degrees, since that's what the
    engine and the NL2 export need regardless of display preference.

    `entry_speed_ms` is the estimated speed (m/s) at the start of this
    element, if known - passing it enables "solve for radius from a
    target G-force" for the element types that support it (Hill Arc,
    Flat Turn, Vertical Loop - see registry.py's g_force_solve entries
    and physics.py's solve_radius_* functions). This is the one place
    this program works the way FVD++ does: forces-first instead of
    shape-first, for exactly the cases where the radius-to-G
    relationship is simple enough to solve directly rather than needing
    a full inverse-design system.
    """

    def __init__(self, type_key: str, params: dict, display_name: str, units: str = "m", parent=None,
                 on_change=None, entry_speed_ms: float = None):
        super().__init__(parent)
        self.type_key = type_key
        self.units = units
        self.entry_speed_ms = entry_speed_ms
        self.on_change = on_change  # optional callback(params_dict, name) fired on every field edit
        spec = ELEMENT_TYPES[type_key]
        self.setWindowTitle(f"Edit {spec['label']}")

        self._fields = {}
        self._length_keys = set()

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(f"<b>{spec['label']}</b>"))
        if units == "ft":
            outer.addWidget(QLabel("<i>Showing feet - stored/exported as meters either way.</i>"))

        form = QFormLayout()

        self.name_edit = QLineEdit(display_name)
        self.name_edit.textChanged.connect(self._notify_change)
        form.addRow("Name", self.name_edit)

        for entry in spec["params"]:
            key, kind = entry[0], entry[1]
            current = params.get(key, entry[2])
            if kind == "float":
                _, _, default, lo, hi, step, unit = entry
                is_length = unit == "m"
                if is_length and units == "ft":
                    disp_lo, disp_hi, disp_step = m_to_ft(lo), m_to_ft(hi), max(m_to_ft(step), 0.05)
                    disp_value = m_to_ft(float(current))
                    disp_unit = "ft"
                else:
                    disp_lo, disp_hi, disp_step = lo, hi, step
                    disp_value = float(current)
                    disp_unit = unit

                w = QDoubleSpinBox()
                w.setRange(disp_lo, disp_hi)
                w.setSingleStep(disp_step)
                w.setDecimals(3)
                w.setValue(disp_value)
                if disp_unit:
                    w.setSuffix(f" {disp_unit}")
                w.valueChanged.connect(self._notify_change)
                form.addRow(key, w)
                self._fields[key] = ("float", w)
                if is_length:
                    self._length_keys.add(key)
            elif kind == "choice":
                _, _, default, options = entry
                w = QComboBox()
                w.addItems(options)
                idx = w.findText(str(current))
                w.setCurrentIndex(idx if idx >= 0 else 0)
                w.currentIndexChanged.connect(self._notify_change)
                form.addRow(key, w)
                self._fields[key] = ("choice", w)
            else:
                raise ValueError(f"Unknown param kind '{kind}' for {key}")

        outer.addLayout(form)

        g_force_solve = spec.get("g_force_solve")
        if g_force_solve:
            outer.addWidget(self._build_g_force_solver(g_force_solve))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _build_g_force_solver(self, g_force_solve: dict) -> QWidget:
        """The 'type a target G-force, get a radius' panel - see the
        class docstring. Returns a QWidget ready to add to the dialog."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 6, 0, 0)

        mode = g_force_solve["mode"]
        if self.entry_speed_ms is None:
            hint = QLabel("<i>Solve-for-G-force unavailable (couldn't determine this element's entry speed).</i>")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            return box

        speed_kmh = ms_to_kmh(self.entry_speed_ms)
        speed_mph = ms_to_mph(self.entry_speed_ms)
        header = QLabel(
            f"<b>Solve for radius from target G-force</b> "
            f"(entry speed here: ~{speed_kmh:.0f} km/h / {speed_mph:.0f} mph)"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        if mode == "hill":
            hint = QLabel(
                "Positive (climbing) angle \u2192 target above 1.0G. "
                "Negative (diving) angle \u2192 target below 1.0G (airtime is negative)."
            )
        elif mode == "flat_turn":
            hint = QLabel("Target is lateral G, must be greater than 0.")
        elif mode == "loop":
            hint = QLabel("Target is the loop's bottom G (where forces peak), must be greater than 1.0.")
        else:
            hint = QLabel("")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addWidget(QLabel("Target G-force:"))
        self._g_target_spin = QDoubleSpinBox()
        self._g_target_spin.setRange(-3.0, 8.0)
        self._g_target_spin.setSingleStep(0.1)
        self._g_target_spin.setDecimals(2)
        self._g_target_spin.setValue(3.0 if mode != "flat_turn" else 1.5)
        row.addWidget(self._g_target_spin)

        solve_btn = QPushButton("Solve for radius")
        solve_btn.clicked.connect(lambda: self._solve_for_radius(g_force_solve))
        row.addWidget(solve_btn)
        layout.addLayout(row)

        return box

    def _solve_for_radius(self, g_force_solve: dict):
        mode = g_force_solve["mode"]
        radius_param = g_force_solve["radius_param"]
        target_g = self._g_target_spin.value()

        try:
            if mode == "hill":
                angle_widget = self._fields["angle_deg"][1]
                climbing = angle_widget.value() > 0
                radius_m = solve_radius_hill(self.entry_speed_ms, target_g, climbing)
            elif mode == "flat_turn":
                radius_m = solve_radius_flat_turn(self.entry_speed_ms, target_g)
            elif mode == "loop":
                radius_m = solve_radius_loop(self.entry_speed_ms, target_g)
            else:
                return
        except ValueError as exc:
            QMessageBox.warning(self, "Can't solve for that target", str(exc))
            return

        radius_widget = self._fields[radius_param][1]
        disp_value = m_to_ft(radius_m) if self.units == "ft" else radius_m
        lo, hi = radius_widget.minimum(), radius_widget.maximum()
        if not (lo <= disp_value <= hi):
            QMessageBox.warning(
                self, "Radius out of range",
                f"The solved radius ({disp_value:.1f} {'ft' if self.units == 'ft' else 'm'}) is outside "
                f"this field's allowed range ({lo:.1f}-{hi:.1f}). Setting it to the nearest allowed value.",
            )
            disp_value = max(lo, min(hi, disp_value))
        radius_widget.setValue(disp_value)  # triggers _notify_change -> live preview updates

    def _notify_change(self, *_args):
        if self.on_change is not None:
            self.on_change(self.result_params(), self.result_name())

    def result_params(self) -> dict:
        out = {}
        for key, (kind, w) in self._fields.items():
            if kind == "float":
                value = w.value()
                if key in self._length_keys and self.units == "ft":
                    value = ft_to_m(value)
                out[key] = value
            else:
                out[key] = w.currentText()
        return out

    def result_name(self) -> str:
        return self.name_edit.text().strip()
