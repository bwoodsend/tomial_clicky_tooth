import collections
import os
import re
import threading
from pathlib import Path

import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth import _csv_io
from tomial_clicky_tooth._clicker import ClickableFigure, InvalidModelError
from tomial_clicky_tooth._table import LandmarkTable


class SwitchModelButton(QtWidgets.QPushButton):
    def __init__(self, direction):
        super().__init__(direction)
        self.released.connect(self._callback)

    def _callback(self):
        self.callback(self.text())

    def callback(self, direction):
        """Override this method in the parent class."""


def show_clicker(show_name):
    """Wrap QWidget.show*() variants so they can all call clicker.show() in
    addition to QWidget.show()."""
    def show(self):
        self.clicker.show()
        getattr(QtWidgets.QWidget, show_name)(self)

    return show


class LazyMenuBar(QtWidgets.QMenuBar):
    """A menu bar whose submenus can be accessed via menu_bar["Name"] and are
    created automatically if they don't exist."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._menus = {}

    def __getitem__(self, menu):
        if menu not in self._menus:
            self._menus[menu] = self.addMenu(menu)
        return self._menus[menu]


class UI(QtWidgets.QWidget):
    def __init__(self, landmark_names, path=None, points=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle(app.applicationName() + " [*]")

        self.h_box = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_box)

        self._thread_lock = threading.Lock()

        ### table ###
        self.table = LandmarkTable(landmark_names)
        self.h_box.addWidget(self.table)
        # table button actions
        self.table.default_csv_path = self.csv_path

        ### clicker ###
        self.clicker_qwidget = ClickableFigure(key_generator=self.key_generator)
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
            button.callback = self.switch_model
            self.buttons.append(button)
        self.model_name_indicator = QtWidgets.QLabel()
        self.model_number_indicator = QtWidgets.QLabel()
        hbox.addWidget(self.buttons[0])
        hbox.addWidget(self.model_name_indicator)
        hbox.addWidget(self.model_number_indicator)
        hbox.addWidget(self.buttons[1])
        hbox.addStretch()

        ### tie them together ###

        # table actions to control the clicker
        self.table.itemSelectionChanged.connect(self.table_selection_changed_cb)
        self.table.landmarks_changed.connect(self.set_clicker_points)
        self.table.landmarks_changed.connect(self._log_state)

        # clicker actions to control table
        self.clicker.marker_changed.connect(self.marker_changed_by_clicker_cb)
        self.clicker.marker_changed.connect(self._log_state)

        self.menu_bar = LazyMenuBar(self)
        self.setup_menu_bar(self.menu_bar)
        self.table.setup_menu_bar(self.menu_bar, self)
        self.menu_bar.adjustSize()

        # optionally start with some landmarks already picked
        if points is not None:
            self.points = points
        self._history = History(self.points)
        self._update_modified_state_indicators()
        self._open_model(path)

    show = show_clicker("show")
    showMaximized = show_clicker("showMaximized")
    showMinimized = show_clicker("showMinimized")
    showFullScreen = show_clicker("showFullScreen")
    showNormal = show_clicker("showNormal")

    def setup_menu_bar(self, bar: LazyMenuBar):
        bar["&File"].addAction(
            QtWidgets.QAction("&Open", self, shortcut="Ctrl+O",
                              triggered=self.open_model))

        bar["&Edit"].addAction(
            QtWidgets.QAction("Clear markers", self,
                              triggered=self.table.clear_all))
        bar["&Edit"].addSeparator()
        bar["&Edit"].addAction(
            QtWidgets.QAction("&Undo", self, triggered=self.undo,
                              shortcut=QtGui.QKeySequence.Undo))
        bar["&Edit"].addAction(
            QtWidgets.QAction("&Redo", self, triggered=self.redo,
                              shortcut=QtGui.QKeySequence("Shift+Ctrl+Z")))
        self.addAction(
            QtWidgets.QAction("Redo", self, triggered=self.redo,
                              shortcut=QtGui.QKeySequence("Ctrl+Y")))

        bar["&About"].addAction(
            QtWidgets.QAction("Terms And Conditions", self,
                              triggered=self.show_licenses))

        return bar

    def open_model(self):
        filter = " ".join("*" + i for i in SUFFIXES)
        options = dict(caption="Open an .STL file",
                       filter=f"3D Model file ({filter})")

        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, **options)
        self._open_model(path)

    def _open_model(self, path):
        if not path:
            return
        path = Path(path)
        self.clicker.close_model()
        try:
            self.clicker.open_model(path)
        except InvalidModelError:
            del self.points
        else:
            csv_path = path.with_name(SUFFIX_RE.sub(r"\1.csv", path.name))
            if csv_path.exists():
                self.points = csv_path
            else:
                del self.points

        self.model_name_indicator.setText(SUFFIX_RE.match(path.name)[1])
        files, index = self.files_index()
        if index is not None:
            self.model_number_indicator.setText(f"({index + 1}/{len(files)})")
        else:
            self.model_number_indicator.setText("")

        self._history = History(self.points)
        self.clicker.update()
        self._update_modified_state_indicators()

    def table_selection_changed_cb(self):
        """Highlights the markers on the model that are selected in the table"""
        rows = self.table.highlighted_rows()
        self.clicker.highlight(rows)

    def key_generator(self):
        rows = self.table.highlighted_rows()
        if len(rows) == 0:
            self.table.increment_selection()
            rows = self.table.highlighted_rows()
        return rows[0]

    def marker_changed_by_clicker_cb(self, old, new):
        if old is not None:
            del self.table[old.key]
        if new is not None:
            self.table[new.key] = new.point
        self.table.increment_selection()

    def csv_path(self):
        """Save path for the CSV file."""
        if self.clicker.path is not None:
            return self.clicker.path.with_name(
                SUFFIX_RE.match(self.clicker.path.name)[1] + ".csv")
        return ""

    @property
    def points(self):
        return np.array(self.table)

    @points.setter
    def points(self, points):
        if isinstance(points, (str, os.PathLike)):
            points = _csv_io.read(points)

        self.set_clicker_points(points)
        self.table[:] = points

    @points.deleter
    def points(self):
        self.clicker.clear()
        del self.table[:]
        self.clicker.update()

    def set_clicker_points(self, points):
        self.clicker.landmarks = np.arange(len(points)), points
        self.table_selection_changed_cb()

    def files_index(self):
        """List models to process (including those already processed) and the
        index of the model currently open.

        Returns:
            paths:
                A file path for each model.
            index:
                The index of the currently opened model.

        This method is intended to be overridable in subclasses. It's default
        behaviour is to iterate through the directory the currently open model
        is stored in.

        If no model is open or the currently open model has disappeared from the
        filesystem, then return a pair of nones.

        """
        if self.path is None:
            return None, None
        paths = [
            i for i in self.clicker.path.parent.glob("*")
            if SUFFIX_RE.match(i.name)
        ]
        try:
            index = paths.index(self.clicker.path)
        except ValueError:
            return None, None
        return paths, index

    @property
    def path(self):
        """The filename of the currently opened model."""
        return self.clicker.path

    def switch_model(self, direction):
        # This function needs a lock to be made thread safe but shouldn't
        # allow events to queue up if the user holds down one of the arrow
        # keys.
        if self._thread_lock.locked():
            return
        with self._thread_lock:
            paths, index = self.files_index()
            if paths is None:
                return
            path = paths[(index + {"<": -1, ">": 1}[direction]) % len(paths)]
            self._open_model(path)

    def keyPressEvent(self, event):
        # No shift/ctrl/alt/etc keys pressed
        if int(event.modifiers() & (~QtCore.Qt.KeypadModifier)) == 0:
            if event.key() == QtCore.Qt.Key_Left:
                self.switch_model("<")
                return
            elif event.key() == QtCore.Qt.Key_Right:
                self.switch_model(">")
                return
        self.table.table.keyPressEvent(event)

    def closeEvent(self, event):
        self.clicker.closeEvent(event)

    def show_licenses(self):
        """Open a licenses viewer window."""

        import pkg_resources
        import lamancha.pyqt5

        components = {"python": lamancha.python}
        for distribution in pkg_resources.require("tomial_clicky_tooth"):
            try:
                component = lamancha.Distribution(distribution)
            except (lamancha.exceptions.NoLicense,
                    lamancha.exceptions.FrozenEditable):
                continue
            components[component.name] = component

        self._licenses = QtWidgets.QWidget()
        self._licenses.setLayout(QtWidgets.QVBoxLayout())
        self._licenses.layout().addWidget(QtWidgets.QLabel(
            "Clicky Tooth's own code is just one small cog connecting a "
            f"network of {len(components) - 1} other open source packages."
        ))  # yapf: disable
        self._licenses.layout().addWidget(
            lamancha.pyqt5.TermsAndConditions(components.values()))
        lamancha.pyqt5.TermsAndConditions.centerise(self._licenses)
        self._licenses.show()

    def _log_state(self, *_):
        """Record the current landmark positions for undo/redo."""
        with self._thread_lock:
            self._history.position += 1
            # If the user has just pressed undo then overwrite (by removing) the
            # undone states.
            while self._history.position < len(self._history):
                self._history.pop()
            if self._history.saved_position >= len(self._history):
                self._history.saved_position = -1
            self._history.append(self.points)
            self._update_modified_state_indicators()

    def _update_modified_state_indicators(self):
        self.setWindowModified(self._history.modified)
        self.table.save_button.setEnabled(self._history.modified)

    def undo(self):
        """Undo a change made via user interaction."""
        with self._thread_lock:
            if self._history.position > 0:
                self._history.position -= 1
                self.points = self._history[self._history.position]
                self._update_modified_state_indicators()

    def redo(self):
        """Reapply a change reverted by undo()."""
        with self._thread_lock:
            if self._history.position < len(self._history) - 1:
                self._history.position += 1
                self.points = self._history[self._history.position]
                self._update_modified_state_indicators()


SUFFIXES = [".stl", ".stl.gz", ".stl.bz2", ".stl.xz"]
SUFFIX_RE = re.compile("(.*)(" + "|".join(map(re.escape, SUFFIXES)) + ")$")


class History(collections.deque):
    """A state history for undo/redo operations."""
    def __init__(self, state):
        self.position = 0
        self.saved_position = 0
        super().__init__([state])

    @property
    def modified(self):
        """True if the current state has been modified since it was last saved
        (excluding if it was modified but reverted)."""
        return self.position != self.saved_position


def main(names, path=None, points=None):
    self = UI(names, path, points)
    self.show()
    app.exec()
    return self
