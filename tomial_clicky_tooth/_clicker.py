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
    """A vtkplotlib.QtFigure() which places landmarks on left click and removes
    then on right click.

    * Models are opened and closed via open_model() and close_model() methods`.
    * The landmark markers are stored in the markers attribute or can be read or
      written in bulk via the landmarks property.
    * Landmark highlighting is controlled via the highlight() method.
    * A marker placed or removed by user interaction emits a marker_changed
      signal with the removed marker (or None) and the newly placed marker (or
      None as arguments.

    """
    def __init__(self, key_generator=None):
        """
        Args:
            key_generator:
                A function which returns a key to store the next newly placed
                landmark each time it is called. Defaults to a simple counter.

        """
        super().__init__()
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

        self.markers = {}
        if key_generator is None:
            key_generator = itertools.count().__next__
        self.key_generator = key_generator

        # Disable VTK's default behaviour of translating QKeyEvents to the VTK
        # equivalents. Instead forward events up the usual chain of this widget
        # and its parents.
        self.vtkWidget.keyPressEvent = self.keyPressEvent

        vpl.interactive.OnClick("Left", self, self._left_click_callback)
        vpl.interactive.OnClick("Right", self, self._right_click_callback)
        self._reset_camera = False

    def _left_click_callback(self, pick: vpl.interactive.pick):
        if pick.actor is self.mesh_plot.actor:  # pragma: no branch
            self.spawn_marker(pick.point)

    def _right_click_callback(self, pick: vpl.interactive.pick):
        if pick.actor is not None:  # pragma: no branch
            marker = self._nearest_marker(np.array(pick.point))
            if marker is not None:
                self._remove_marker(marker.key)
                self.marker_changed.emit(marker, None)

    def open_model(self, path):
        """Open a model and pre-orientate it.

        Preserve any existing landmarks. Create an error pop-up dialog if the
        model can't be read.

        """
        self.close_model()
        self.path = Path(path)

        # Read the model directly from file
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

    marker_changed = QtCore.pyqtSignal(object, object)

    def close_model(self):
        """Close the model. Do nothing is there is no model to close."""
        if self.mesh_plot is not None:
            self -= self.mesh_plot
            self.path = None
            self.mesh = None
            self.mesh_plot = None
            self.odometry = None
        self.mesh_plot = None

    def _nearest_marker(self, xyz, max_distance=3):
        """Find the landmark marker closest to a given point. Returns None if no
        landmark is less than max_distance away."""
        best = None
        best_distance = max_distance**2
        for marker in self.markers.values():
            distance = sum((i - j)**2 for (i, j) in zip(marker.point, xyz))
            if distance < best_distance:
                best_distance = distance
                best = marker
        return best

    @property
    def landmarks(self):
        """Export the landmarks into an array of keys and an array of points."""
        keys = np.array(list(self.markers.keys()), object)
        return keys, np.array([self.markers[i].point for i in keys])

    @landmarks.setter
    def landmarks(self, landmarks):
        self.clear()
        for (i, j) in zip(*landmarks):
            if j is not None and np.isfinite(j).all():
                self._spawn_marker(j, i)
        self.update()

    def _remove_marker(self, key):
        marker = self.markers.pop(key)
        self -= marker
        return marker

    def clear(self):
        """Programmatically delete all markers. Does not trigger a re-render or
        emit any marker_changed signals."""
        for key in list(self.markers):
            self._remove_marker(key)

    def _spawn_marker(self, xyz, key=None):
        if key is None:
            key = self.key_generator()
        if key in self.markers:
            self._remove_marker(key)

        marker = vpl.scatter(xyz, color=Colors.MARKER, fig=self,
                             use_cursors=True)
        marker.key = key

        self.markers[marker.key] = marker
        return marker

    def spawn_marker(self, point, key=None):
        marker = self._spawn_marker(point, key)
        self.marker_changed.emit(None, marker)

    def highlight(self, keys):
        """Highlight the markers within a set of keys."""
        keys = set(keys)
        for marker in self.markers.values():

            if marker.key in keys:
                color = Colors.HIGHLIGHTED
            else:
                color = Colors.MARKER

            marker.color = color
        self.update()
