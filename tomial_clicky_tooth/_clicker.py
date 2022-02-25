import itertools
from pathlib import Path

import numpy as np
from PyQt5 import QtWidgets, QtCore
import vtkplotlib as vpl
from motmot import Mesh


class Colors:
    BACKGROUND = (40, 80, 150)
    MARKER = "black"
    HIGHLIGHTED = (.9, 0, 0)


class InvalidModelError(Exception):
    pass


class ClickableFigure(vpl.QtFigure2):
    def __init__(self, initial_path=None, parent=None, key_generator=None):
        super().__init__(parent=parent)
        vpl.scf(None)

        self.add_preset_views()
        # The renderer should eat as much space as it can get.
        self.setSizePolicy(
            QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                                  QtWidgets.QSizePolicy.MinimumExpanding))

        self.mesh_plot = None
        self.path = None
        self.mesh = None
        self.odometry = None
        if initial_path is not None:
            try:
                self.open_model(initial_path)
            except InvalidModelError:
                pass

        self.cursors = {}
        if key_generator is None:
            key_generator = itertools.count().__next__
        self.key_generator = key_generator

        # Disable VTK's default behaviour of translating QKeyEvents to the VTK
        # equivalents. Instead forward events up the usual chain of this widget
        # and its parents.
        self.vtkWidget.keyPressEvent = self.keyPressEvent

        vpl.interactive.OnClick("Left", self, self.left_click_cb)
        vpl.interactive.OnClick("Right", self, self.right_click_cb)
        self._reset_camera = False

    def left_click_cb(self, pick: vpl.interactive.pick):
        if pick.actor is self.mesh_plot.actor:  # pragma: no branch
            self.spawn_cursor(pick.point)

    def right_click_cb(self, pick: vpl.interactive.pick):
        if pick.actor is not None:  # pragma: no branch
            cursor = self.nearest_cursor(np.array(pick.point))
            if cursor is not None:
                self.remove_cursor(cursor.key)
                self.cursor_changed.emit(cursor, None)

    def open_model(self, path):
        self.close_stl()
        self.path = Path(path)

        # Read the stl directly from file
        try:
            mesh = Mesh(path)
        except:
            path = path.resolve()
            QtWidgets.QMessageBox.critical(
                self, "Invalid model file",
                f'<a href="{path.as_uri()}">{path.name}</a> located in '
                f'<a href="{path.parent.as_uri()}">{path.parent}</a> is '
                f'invalid.')
            raise InvalidModelError

        self.mesh = mesh
        self.mesh_plot = vpl.mesh_plot(mesh, fig=self)

        try:
            # Just because we can...
            # Automatically set the camera angle to the occlusal view and set
            # the directions for the preset camera direction buttons so that
            # the shark matches the patient.
            from tomial_odometry import Odometry
            from pangolin import arch_type

            self.odometry = Odometry(mesh, arch_type(Path(self.path).stem))
            self.view_buttons.init_default()
            self.view_buttons.rotate(self.odometry.axes)
            vpl.view(camera_position=self.odometry.occlusal,
                     up_view=self.odometry.forwards, fig=self)

        except:
            pass

        self.reset_camera()

    #                                 (old   , new   )
    cursor_changed = QtCore.pyqtSignal(object, object)

    def close_stl(self):
        if self.mesh_plot is not None:
            self -= self.mesh_plot
            self.path = None
            self.mesh = None
            self.mesh_plot = None
            self.odometry = None
        self.mesh_plot = None

    def nearest_cursor(self, xyz, max_distance=3):
        best = None
        best_distance = max_distance**2
        for cursor in self.cursors.values():
            distance = sum((i - j)**2 for (i, j) in zip(cursor.point, xyz))
            if distance < max_distance and distance < best_distance:
                best_distance = distance
                best = cursor
        return best

    @property
    def landmarks(self):
        keys = np.array(list(self.cursors.keys()), object)
        return keys, np.array([self.cursors[i].point for i in keys])

    @landmarks.setter
    def landmarks(self, landmarks):
        self.clear()
        for (i, j) in zip(*landmarks):
            if j is not None and np.isfinite(j).all():
                self._spawn_cursor(j, i)
        self.update()

    def remove_cursor(self, key):
        cursor = self.cursors.pop(key)
        self -= cursor
        return cursor

    def clear(self):
        for key in list(self.cursors):
            self.remove_cursor(key)

    def _spawn_cursor(self, xyz, key=None):
        if key is None:
            key = self.key_generator()
        if key in self.cursors:
            self.remove_cursor(key)

        cursor = vpl.scatter(xyz, color=Colors.MARKER, fig=self,
                             use_cursors=True)
        cursor.key = key

        self.cursors[cursor.key] = cursor
        return cursor

    def spawn_cursor(self, point, key=None):
        cursor = self._spawn_cursor(point, key)
        self.cursor_changed.emit(None, cursor)

    def highlight_markers(self, marker_indices):
        marker_indices = set(marker_indices)
        for cursor in self.cursors.values():

            if cursor.key in marker_indices:
                color = Colors.HIGHLIGHTED
            else:
                color = Colors.MARKER

            cursor.color = color
        self.update()
