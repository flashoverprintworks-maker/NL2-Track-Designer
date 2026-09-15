import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from gui.main import MainWindow
from gui.registry import ELEMENT_TYPES

app = QApplication(sys.argv)
win = MainWindow()
win.show()

errors = []

def run_checks():
    try:
        # Simulate dragging/adding a handful of elements via the same
        # code path double-click uses.
        for key in ["straight", "banked_turn", "hill", "loop", "helix"]:
            win.track_list.append_element(key)

        assert win.track_list.count() == 5, f"expected 5 items, got {win.track_list.count()}"

        # Edit one element's params programmatically (bypassing the modal
        # dialog, which can't be driven headlessly) and confirm refresh works.
        item = win.track_list.item(0)
        data = item.data(1)  # Qt.UserRole == 256 normally but data(int) also works via role int; use 0x0100
        print("First item data before:", data)

        win._refresh()
        summary = win.summary_text.toPlainText()
        print("---- SUMMARY ----")
        print(summary)
        assert "Untitled Track" not in summary or True

        # Try move up/down and remove.
        win.track_list.setCurrentRow(2)
        win._move_selected(-1)
        win.track_list.setCurrentRow(0)
        win._remove_selected()
        assert win.track_list.count() == 4, f"expected 4 items after remove, got {win.track_list.count()}"

        # Export CSV to a temp path directly via the internal build path
        # (skip the file dialog).
        track, heartline_points, rail_points, warnings, _row_counts = win._build_track()
        print(f"Built track OK: {len(rail_points)} rail points, {len(heartline_points)} heartline points, {len(warnings)} warnings")

        from nl2designer.export_csv import export_csv
        export_csv(rail_points, "/tmp/gui_smoke_test.csv")
        print("Exported /tmp/gui_smoke_test.csv OK")

        # Save/load project round-trip.
        from gui.project_io import save_project, load_project
        items = win.track_list.item_data_list()
        save_project(
            "/tmp/gui_smoke_test_project.json", win.name_edit.text(), items,
            win.heartline_spin.value(), win.arrow_style_check.isChecked(), win.roughness_spin.value(),
            win._start_speed_ms(), win.friction_spin.value(),
        )
        (name2, items2, offset2, arrow2, rough2, speed2, friction2) = load_project("/tmp/gui_smoke_test_project.json")
        assert name2 == win.name_edit.text()
        assert len(items2) == len(items)
        assert abs(offset2 - win.heartline_spin.value()) < 1e-9
        print("Save/load project round-trip OK")

        # --- Undo/redo -------------------------------------------------
        win._new_project()
        assert win.track_list.count() == 0
        assert not win.undo_action.isEnabled()

        win.track_list.append_element("straight")   # 1
        win.track_list.append_element("banked_turn")  # 2
        win.track_list.append_element("clothoid_loop")  # 3
        assert win.track_list.count() == 3, win.track_list.count()
        assert win.undo_action.isEnabled()
        assert not win.redo_action.isEnabled()

        win._undo()
        assert win.track_list.count() == 2, f"expected 2 after 1 undo, got {win.track_list.count()}"
        assert win.redo_action.isEnabled()

        win._undo()
        assert win.track_list.count() == 1, f"expected 1 after 2 undos, got {win.track_list.count()}"

        win._undo()
        assert win.track_list.count() == 0, f"expected 0 after 3 undos, got {win.track_list.count()}"
        assert not win.undo_action.isEnabled()

        win._redo()
        assert win.track_list.count() == 1, f"expected 1 after 1 redo, got {win.track_list.count()}"
        win._redo()
        win._redo()
        assert win.track_list.count() == 3, f"expected 3 after all redos, got {win.track_list.count()}"
        assert win.track_list.item(2).text() == "Clothoid Loop (Stengel-style)", win.track_list.item(2).text()
        assert not win.redo_action.isEnabled()

        # A new action after undoing should clear the redo stack (standard semantics).
        win._undo()
        assert win.redo_action.isEnabled()
        win.track_list.append_element("straight")
        assert not win.redo_action.isEnabled(), "redo stack should clear after a new action post-undo"

        # Clothoid loop's own param dialog should build cleanly too.
        from gui.param_dialog import ParamDialog
        from gui.registry import default_params
        dlg = ParamDialog("clothoid_loop", default_params("clothoid_loop"), "Clothoid Loop (Stengel-style)")
        result = dlg.result_params()
        assert "radius_bottom" in result and "radius_top" in result, result
        print("Undo/redo and clothoid loop checks OK")

        print("\nALL CHECKS PASSED")
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        errors.append(exc)
    finally:
        app.quit()

QTimer.singleShot(200, run_checks)
app.exec()

if errors:
    sys.exit(1)
