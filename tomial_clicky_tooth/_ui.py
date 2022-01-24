import os
from pathlib import Path

import numpy as np
from PyQt5 import QtWidgets, QtCore

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth._clicker import ClickerQtWidget
from tomial_clicky_tooth._table import LandmarkTable


class SwitchModelButton(QtWidgets.QPushButton):

    def __init__(self, direction):
        super().__init__(direction)
        self.released.connect(self._callback)

    def _callback(self):
        self.callback(self.text())

    def callback(self, direction):
        """Override this method in the parent class."""
        print(self.text(), "released")


class ManualLandmarkSelection(QtWidgets.QWidget):

    def __init__(self, landmark_names, stl_path=None, points=None, parent=None):
        super().__init__(parent)

        self.h_box = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_box)

        self.menu_bar = self.setup_menu_bar()
        self.paths = None

        self.setWindowTitle("Manual Landmark Selection")

        ### table ###
        self.table = LandmarkTable(landmark_names)
        self.h_box.addWidget(self.table)
        # table button actions
        self.table.buttons["Clear all"].pressed.connect(self.clear_markers)
        self.table.default_save_name = self.save_csv_name
        self.table.buttons["Delete Marker(s)"].released.connect(
            self.clear_selected)

        ### clicker ###
        self.clicker_qwidget = ClickerQtWidget(stl_path, self, self.key_gen)
        self.clicker = self.clicker_qwidget

        self.right_vbox = QtWidgets.QVBoxLayout()
        self.h_box.addLayout(self.right_vbox)
        self.right_vbox.addWidget(self.clicker_qwidget)
        self.setShortcutEnabled(QtCore.Qt.LeftButton)

        ### Next/previous model buttons ###
        hbox = QtWidgets.QHBoxLayout()
        self.right_vbox.addLayout(hbox)
        self.buttons = []
        hbox.addStretch()
        for i in "<>":
            button = SwitchModelButton(i)
            hbox.addWidget(button)
            button.callback = self.switch_model
            self.buttons.append(button)
        hbox.addStretch()

        ### tie them together ###

        # table actions to control the clicker

        self.table.itemSelectionChanged.connect(self.table_selection_changed_cb)
        self.table.landmarks_changed.connect(self.set_clicker_points)
        #self.table.rename_cb = self.clicker.rename_cursor
        #self.table.remove_cb = self.clicker.remove_cursor_key

        # clicker actions to control table
        self.clicker.cursor_changed.connect(self.cursor_changed_by_clicker_cb)

        # optionally start with some landmarks already picked
        self.set_points(points)

    def show(self):
        super().show()
        self.clicker.show()

    def setup_menu_bar(self):
        menu_bar = QtWidgets.QMenuBar(self)

        file_menu = menu_bar.addMenu("&File")

        open_action = QtWidgets.QAction("&Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_model)
        file_menu.addAction(open_action)

        edit_menu = menu_bar.addMenu("&Edit")

        clear_markers_action = QtWidgets.QAction("Clear markers", self)
        clear_markers_action.triggered.connect(self.clear_markers)
        edit_menu.addAction(clear_markers_action)

        help_menu = menu_bar.addMenu("&Help")

        show_license_action = QtWidgets.QAction("About", self)
        show_license_action.triggered.connect(self.show_licence)
        help_menu.addAction(show_license_action)

        menu_bar.adjustSize()

        return menu_bar

    def open_model(self):
        options = dict(
            caption="Open an .STL file",
            #directory=str(config.stl_folder),
            filter="3D Model file (*.stl)",
        )

        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, **options)
        if path:
            path = Path(path)
            self.setWindowTitle(path.stem)
            self.clicker.close_stl()
            self.clicker.open_stl(path)

    def clear_markers(self):
        keys = list(self.clicker.cursors.keys())
        [self.clicker.remove_cursor_key(i, update=False) for i in keys]
        self.clicker.update()
        del self.table[:]
        self.table.table.selectRow(0)

    def clear_selected(self):
        keys = self.table.highlighted_rows()
        for key in keys:
            cursor = self.clicker.get_cursor(key)
            if cursor is not None:
                self.clicker.remove_cursor_key(key, cb=True, update=False)
        self.table.increment_focus()
        self.clicker.update()

    #def table_updated_cb(self):
    #    rows = self.table.highlighted_rows()

    #    #print(rows)
    #    for index in rows:
    #        #print(index)
    #        pos = self.table.get_position(index)
    #        #print("table pos", self.table.get_position(index))
    #        #print("table focus", self.table.hasFocus())
    #        if pos is not None and self.hasFocus():
    #            self.clicker.place_cursor(pos, index)
    #    self.clicker.renWin.Render()

    def table_selection_changed_cb(self):
        """Highlights the markers on the model that are selected in the table"""
        rows = self.table.highlighted_rows()
        #print("Highlight", rows)
        self.clicker.highlight_markers(rows)

    def key_gen(self):
        rows = self.table.highlighted_rows()
        if len(rows) == 0:
            self.table.increment_focus()
            rows = self.table.highlighted_rows()
        return rows[0]

    def cursor_changed_by_clicker_cb(self, old, new):
        if old is not None:
            del self.table[old.key]
        if new is not None:
            self.table[new.key] = new.point
        self.table.increment_focus()

    #def cursor_changed_by_table_cb(self, old_key, new_key):
    #    if cursor.key is not None:
    #        self.table.clear_position(cursor.key)

    #    self.table.increment_focus()
    #    self.clicker.renWin.Render()

    def save_csv_name(self):
        return self.clicker.stl_path.stem + ".csv"

    def show_licence(self):
        self.box = box = QtWidgets.QMessageBox()
        box.setText(LICENSE)
        box.setWindowTitle("About")
        box.show()

    def get_points(self):
        return np.array(self.table)

    def set_clicker_points(self, points):
        if isinstance(points, (str, os.PathLike)):
            points = excel_io.read_points(points)[1]
        self.clicker.landmarks = np.arange(len(points)), points

    def set_table_points(self, points):
        if isinstance(points, (str, os.PathLike)):
            points = excel_io.read_points(points)[1]
        self.table[:] = points

    def set_points(self, points):
        if points is None:
            return self.clear_markers()

        if isinstance(points, (str, os.PathLike)):
            points = excel_io.read_points(points)[1]

        self.set_clicker_points(points)
        self.set_table_points(points)

    def switch_model(self, direction):
        if getattr(self.clicker, "stl_path", None) is None:
            return
        if self.paths is None:
            paths = list(self.clicker.stl_path.parent.glob("*.stl"))
        else:
            paths = self.paths
        try:
            index = paths.index(self.clicker.stl_path)
        except ValueError:
            return
        path = paths[(index + {"<": -1, ">": 1}[direction]) % len(paths)]
        self.clicker.open_stl(path)
        self.clear_markers()
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.set_points(csv_path)
        self.clicker.update()

    def keyPressEvent(self, event):
        globals()["event"] = event
        #print(event)
        # No shift/ctrl/alt/etc keys pressed
        if event.modifiers() == QtCore.Qt.NoModifier:
            if event.key() == QtCore.Qt.Key_Left:
                self.switch_model("<")
            elif event.key() == QtCore.Qt.Key_Right:
                self.switch_model(">")

    def closeEvent(self, event):
        self.clicker.closeEvent(event)


def main(names, path=None, points=None):
    self = ManualLandmarkSelection(names, path, points)
    self.show()
    app.exec()

    return self
