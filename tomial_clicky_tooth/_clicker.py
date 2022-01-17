import os
import sys
import itertools
from pathlib import Path

import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
import vtkplotlib as vpl
from motmot import geometry, Mesh

from tomial_clicky_tooth._qapp import app


class Colors:
    BACKGROUND = (40, 80, 150)
    MARKER = "black"
    HIGHLIGHTED = "red"


def _vtk_key_to_Qt(code, symbol):
    if code:
        return ord(code)
    else:
        return getattr(QtCore.Qt, "Key_" + symbol, None) \
            or getattr(QtCore.Qt, "Key_" + symbol.split("_")[0], None)


class ClickerQtWidget(vpl.QtFigure2):

    def __init__(self, path=None, parent=None, key_gen=None):
        super().__init__(parent=parent)
        vpl.scf(None)

        self.add_preset_views()

        self.stl_plot = None
        if path is not None:
            self.open_stl(path)

        self.cursors = {}
        if key_gen is None:
            key_gen = (i for i in itertools.count()
                       if i not in self.cursors.keys()).__next__
        self.key_gen = key_gen

        vpl.interactive.OnClick("Left", self, self.left_click_cb)
        vpl.interactive.OnClick("Right", self, self.right_click_cb)
        self.style.AddObserver("KeyPressEvent", self.key_press_cb)
        self._reset_camera = False

    def left_click_cb(self, pick: vpl.interactive.pick):
        if pick.actor is self.stl_plot.actor:
            self.spawn_cursor(pick.point)

    def right_click_cb(self, pick: vpl.interactive.pick):
        if pick.actor is not None:
            cursor = self.get_cursor_near_point(np.array(pick.point))
            if cursor is not None:
                self.remove_cursor(cursor)
                self.cursor_changed.emit(cursor, None)

    def key_press_cb(self, style, event_name):
        modifiers = QtCore.Qt.KeyboardModifiers()
        key = _vtk_key_to_Qt(style.GetInteractor().GetKeyCode(),
                             style.GetInteractor().GetKeySym())
        if key is None:
            return
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers)
        QtWidgets.QApplication.sendEvent(self, event)

    def open_stl(self, stl_path):
        if stl_path is None:
            return
        self.close_stl()

        # Read the stl directly from file
        mesh = Mesh(stl_path)
        self.stl_path = stl_path

        self.stl_plot = vpl.mesh_plot(mesh, fig=self)

        try:
            # Just because we can...
            # Automatically set the camera angle to the occlusal view and set
            # the directions for the preset camera direction buttons so that
            # the shark matches the patient.
            from tomial_odometry import Odometry
            from pangolin import arch_type

            self.odom = Odometry(mesh, arch_type(Path(self.stl_path).stem))
            self.view_buttons.init_default()
            self.view_buttons.rotate(
                np.array([self.odom.right, self.odom.forwards, self.odom.up]))
            vpl.view(self.odom.center_of_mass,
                     camera_direction=-self.odom.occlusal,
                     up_view=self.odom.forwards, fig=self)

        except () as ex:
            print(repr(ex))

        self.reset_camera()

    #                                 (old   , new   )
    cursor_changed = QtCore.pyqtSignal(object, object)

    def close_stl(self):
        if self.stl_plot is not None:
            self -= self.stl_plot
        self.stl_plot = None

    def get_cursor_near_point(self, xyz, max_distance=3):
        if len(self.cursors) == 0:
            return
        keys, positions = self.landmarks
        displacements = positions - xyz
        distances = geometry.magnitude(displacements)

        closest_arg = np.nanargmin(distances)
        closest_distance = distances[closest_arg]
        #print("closest distance", round(closest_distance, 3), "mm. Threshold is", max_distance)
        if closest_distance <= max_distance:
            return self.cursors[keys[closest_arg]]
        else:
            return

    @property
    def landmarks(self):
        keys = np.array(list(self.cursors.keys()), object)
        return keys, np.array(
            [self.cursors[i].source.GetFocalPoint() for i in keys])

    @landmarks.setter
    def landmarks(self, landmarks):
        self.clear(update=False)
        [self._spawn_cursor(j, i, False) for (i, j) in zip(*landmarks)]
        self.update()

    def remove_cursor_key(self, key, cb=False, update=True):
        return self.remove_cursor(self.cursors.pop(key), cb, update)

    def remove_cursor(self, cursor, cb=False, update=True):
        self.cursors.pop(cursor.key, None)
        self -= cursor
        if update:
            self.update()
        if cb:
            self.cursor_changed.emit(cursor, None)
        return cursor

    def clear(self, update=True):
        for key in list(self.cursors):
            self.remove_cursor_key(key, cb=False, update=False)
        if update:
            self.update()

    def rename_cursor(self, old, new):
        #print("rename", repr(old), "->", repr(new))

        if new in self.cursors:
            self.remove_cursor_key(new, cb=False)

        if old not in self.cursors:
            return

        cursor = self.cursors.pop(old)
        cursor.key = new
        self.cursors[new] = cursor

    def _spawn_cursor(self, xyz, key=None, update=True):
        #print("spawn cursor at", np.round(xyz, 3))

        key = key or self.key_gen()
        if key in self.cursors:
            self.remove_cursor_key(key)

        cursor = vpl.scatter(xyz, color=Colors.MARKER, fig=self,
                             use_cursors=True)
        cursor.key = key
        if update:
            self.update()

        self.cursors[cursor.key] = cursor
        return cursor

    def spawn_cursor(self, point, key=None, update=True):
        cursor = self._spawn_cursor(point, key, update)
        self.cursor_changed.emit(None, cursor)

    def get_cursor(self, key):
        return self.cursors.get(key, None)

    def highlight_markers(self, marker_indices):
        marker_indices = set(marker_indices)
        for cursor in self.cursors.values():

            if cursor.key in marker_indices:
                color = Colors.HIGHLIGHTED
            else:
                color = Colors.MARKER

            #print("setting color", color)
            cursor.color = color
        self.update()

    #def keyPressEvent(self, event):
    #    print(event)
    #    if self.parent():
    #        self.parent().keyPressEvent(event)
