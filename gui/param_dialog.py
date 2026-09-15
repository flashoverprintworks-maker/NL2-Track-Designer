from PySide6.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QComboBox, QLineEdit,
    QDialogButtonBox, QVBoxLayout, QLabel,
)

from gui.registry import ELEMENT_TYPES
from gui.units import m_to_ft, ft_to_m


class ParamDialog(QDialog):
    """Auto-generated form for editing one element's parameters, based on
    the param spec list in registry.ELEMENT_TYPES. Adding a new element
    type or parameter to the registry needs no changes here.

    `units` is "m" or "ft" - it only affects how fields whose unit label
    is exactly "m" (lengths/radii/heights) are displayed and entered;
    the underlying stored values (and everything else - angles, turn
    counts, etc.) are always meters/degrees, since that's what the
    engine and the NL2 export need regardless of display preference.
    """

    def __init__(self, type_key: str, params: dict, display_name: str, units: str = "m", parent=None):
        super().__init__(parent)
        self.type_key = type_key
        self.units = units
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
                form.addRow(key, w)
                self._fields[key] = ("choice", w)
            else:
                raise ValueError(f"Unknown param kind '{kind}' for {key}")

        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

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
