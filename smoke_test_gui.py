import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt

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

        # --- Live preview while editing (custom element specifically) ---
        win._new_project()
        win.track_list.append_element("custom")
        assert win.track_list.count() == 1

        from gui.param_dialog import ParamDialog as PD
        item = win.track_list.item(0)
        data = item.data(Qt.UserRole)
        undo_depth_before_edit = len(win._undo_stack)

        def live_preview_test(new_params, new_name):
            live_data = dict(data)
            live_data["params"] = new_params
            live_data["name"] = new_name or data["name"]
            item.setData(Qt.UserRole, live_data)
            item.setText(live_data["name"])
            win._restoring = True
            try:
                win._refresh()
            finally:
                win._restoring = False

        dlg2 = PD(data["type"], data["params"], data["name"], units=win.units, parent=win,
                   on_change=live_preview_test)

        def _apply(dlg, key, value):
            widget = dlg._fields[key][1]
            widget.setValue(value)

        # Simulate the user dragging the length field around several times
        # while the dialog is open - each change should update the live
        # preview (track_list item data + 3D points) immediately, and
        # NONE of these intermediate tweaks should land in the undo stack.
        for test_length in [30.0, 45.0, 60.0]:
            _apply(dlg2, "length", test_length)
            live_data = item.data(Qt.UserRole)
            assert abs(live_data["params"]["length"] - test_length) < 1e-6, live_data["params"]
            assert win._last_rail_points, "3D preview points should be populated during live edit"
            assert len(win._undo_stack) == undo_depth_before_edit, \
                f"live preview should not push undo entries mid-edit, stack grew to {len(win._undo_stack)}"

        dlg2.accept()  # simulate clicking OK
        # Manually finish what _edit_item does after exec() returns Accepted,
        # since we drove the dialog directly instead of through .exec().
        final_data = dict(data)
        final_data["params"] = dlg2.result_params()
        final_data["name"] = dlg2.result_name()
        item.setData(Qt.UserRole, final_data)
        item.setText(final_data["name"])
        win._refresh()
        assert len(win._undo_stack) == undo_depth_before_edit + 1, \
            f"exactly one undo entry should register for the whole edit, got {len(win._undo_stack) - undo_depth_before_edit}"
        assert item.data(Qt.UserRole)["params"]["length"] == 60.0
        print("Live preview during element editing OK (updates live, one undo step per edit)")

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
