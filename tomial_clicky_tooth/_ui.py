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


def show_clicker(show_name):
    """Wrap QWidget.show*() variants so they can all call clicker.show() in
    addition to QWidget.show()."""
    def show(self):
        self.clicker.show()
        getattr(super(type(self), self), show_name)()

    return show


class ManualLandmarkSelection(QtWidgets.QWidget):
    def __init__(self, landmark_names, stl_path=None, points=None, parent=None):
        super().__init__(parent)

        self.h_box = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_box)

        self.paths = None

        self.setWindowTitle("Manual Landmark Selection")

        ### table ###
        self.table = LandmarkTable(landmark_names)
        self.h_box.addWidget(self.table)
        # table button actions
        self.table.default_save_name = self.save_csv_name

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

        # clicker actions to control table
        self.clicker.cursor_changed.connect(self.cursor_changed_by_clicker_cb)

        self.menu_bar = self.setup_menu_bar()

        # optionally start with some landmarks already picked
        if points is not None:
            self.set_points(points)

    show = show_clicker("show")
    showMaximized = show_clicker("showMaximized")
    showMinimized = show_clicker("showMinimized")
    showFullScreen = show_clicker("showFullScreen")
    showNormal = show_clicker("showNormal")

    def setup_menu_bar(self):
        menu_bar = QtWidgets.QMenuBar(self)

        file_menu = menu_bar.addMenu("&File")

        open_action = QtWidgets.QAction("&Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_model)
        file_menu.addAction(open_action)

        edit_menu = menu_bar.addMenu("&Edit")

        clear_markers_action = QtWidgets.QAction("Clear markers", self)
        clear_markers_action.triggered.connect(self.table.clear_all)
        edit_menu.addAction(clear_markers_action)

        menu_bar.adjustSize()

        return menu_bar

    def open_model(self):
        options = dict(
            caption="Open an .STL file",
            filter="3D Model file (*.stl)",
        )

        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, **options)
        self._open_model(path)

    def _open_model(self, path):
        if path:
            path = Path(path)
            self.setWindowTitle(path.stem)
            self.clicker.close_stl()
            self.clicker.open_stl(path)

    def table_selection_changed_cb(self):
        """Highlights the markers on the model that are selected in the table"""
        rows = self.table.highlighted_rows()
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

    def save_csv_name(self):
        return self.clicker.stl_path.stem + ".csv"

    def get_points(self):
        return np.array(self.table)

    def set_clicker_points(self, points):
        if isinstance(points, (str, os.PathLike)):
            points = excel_io.read_points(points)[1]
        self.clicker.landmarks = np.arange(len(points)), points
        self.table_selection_changed_cb()

    def set_table_points(self, points):
        if isinstance(points, (str, os.PathLike)):
            points = excel_io.read_points(points)[1]
        self.table[:] = points

    def set_points(self, points):
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
        # No shift/ctrl/alt/etc keys pressed
        if event.modifiers() == QtCore.Qt.NoModifier:
            if event.key() == QtCore.Qt.Key_Left:
                self.switch_model("<")
            elif event.key() == QtCore.Qt.Key_Right:
                self.switch_model(">")

    def closeEvent(self, event):
        self.clicker.closeEvent(event)


class Interact(QtCore.QThread):
    def __init__(self, namespace):
        self.namespace = namespace
        super().__init__()

    def run(self):
        import code
        import readline
        import rlcompleter

        readline.set_completer(rlcompleter.Completer(self.namespace).complete)
        readline.parse_and_bind("tab: complete")
        code.InteractiveConsole(self.namespace).interact()


def main(names, path=None, points=None):
    self = ManualLandmarkSelection(names, path, points)
    t = Interact({**locals(), **globals()})
    t.start()
    self.show()
    app.exec()

    return self
