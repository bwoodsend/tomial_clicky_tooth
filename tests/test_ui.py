import tempfile
import time
from pathlib import Path
import shutil
import os

import pytest
import numpy as np
from PyQt5 import QtTest, QtCore
import pyperclip
from vtkmodules.vtkRenderingCore import vtkCoordinate
from motmot import geometry
from pangolin import Palmer
import tomial_tooth_collection_api

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth import _csv
from tomial_clicky_tooth._ui import ManualLandmarkSelection
from tests import xvfb_size, select_file
from tests.test_csv import INVALID_CSVs, assert_text_equivalent

pytestmark = pytest.mark.order(5)


def screen_coordinates(figure, world):
    """Convert 3D coordinates to 2D pixel numbers in the model renderer."""
    c = vtkCoordinate()
    c.SetCoordinateSystemToWorld()
    c.SetValue(*world)
    x, y = map(int, c.GetComputedDoubleViewportValue(figure.renderer))
    _x, _y = figure.render_size
    return x, _y - y


def click(self, point, button="L"):
    """Click on a 3D point in the renderer."""
    click_2d(self, *screen_coordinates(self.clicker, point), button=button)


def click_2d(self, x, y, button="L"):
    """Click on a given pixel in the model renderer."""
    button = {
        "L": QtCore.Qt.MouseButton.LeftButton,
        "R": QtCore.Qt.MouseButton.RightButton
    }[button]
    QtTest.QTest.mouseClick(self.clicker.vtkWidget, button,
                            QtCore.Qt.KeyboardModifier.NoModifier,
                            QtCore.QPoint(x, y))


def highlight(mesh_plot, point):
    """Color the area around a given point on the mesh.

    This is purely to make it easier to see where some other event (such as a
    mouse click) should be happening. It has no functional purpose.

    """
    mesh_plot.scalars = -geometry.magnitude_sqr(mesh_plot.vertices -
                                                point).clip(max=16)
    mesh_plot.cmap = ["w", "r"]


def tips(mesh, occlusal):
    """Find all locally high points on a mesh.

    This are ideal for clicking on because they are guaranteed to be visible
    when the model is viewed from above.

    """
    return mesh.vertices[mesh.local_maxima(occlusal(mesh.vertices))]


def remove_close(points):
    """Pick out 10 points which are at least 10mm apart from each other."""
    out = np.empty((10, 3), dtype=points.dtype)
    points = iter(points)
    for i in range(10):
        for point in points:
            if (geometry.magnitude_sqr(out[:i] - point) > 100).all():
                out[i] = point
                break
        else:
            raise
    return out


def select_rows(self, *row_numbers):
    """Set the row selection for the UI's table."""
    model = self.table.table.selectionModel()
    selection = QtCore.QItemSelection()
    index = model.model().index
    for i in row_numbers:
        selection.select(index(i, 0), index(i, self.table.shape[1] - 1))
    model.select(selection, model.SelectCurrent)


def test_clicking():
    """Test left and right clicking on the renderer."""
    self = ManualLandmarkSelection(["a", "b", "c", "d"])
    self.show()

    self._open_model(tomial_tooth_collection_api.model("1L"))
    app.processEvents()
    assert np.array(self.table).shape == (4, 3)
    assert np.isnan(np.array(self.table)).all()

    points = remove_close(tips(self.clicker.mesh, self.clicker.odom.occlusal))
    highlight(self.clicker.stl_plot, points[0])

    assert self.table.highlighted_rows() == [0]
    click(self, points[0])
    assert self.table.highlighted_rows() == [1]
    assert np.allclose(self.table[0], points[0], atol=1)
    assert np.allclose(self.clicker.cursors[0].point, points[0], atol=1)

    highlight(self.clicker.stl_plot, points[1])
    click(self, points[1])
    assert self.table.highlighted_rows() == [2]
    assert np.allclose(self.table[1], points[1], atol=1)
    assert np.allclose(self.clicker.cursors[1].point, points[1], atol=1)
    self.clicker.stl_plot.scalars = None

    click(self, points[4], button="R")
    assert sorted(self.clicker.cursors.keys()) == [0, 1]
    click(self, points[0], button="R")
    assert sorted(self.clicker.cursors.keys()) == [1]
    click(self, points[0], button="R")
    assert sorted(self.clicker.cursors.keys()) == [1]

    self.close()


def test_highlight():
    """Test highlighting table rows highlights the corresponding placed markers
    in the renderer."""
    self = ManualLandmarkSelection(Palmer.range("LL5", "LR5"),
                                   tomial_tooth_collection_api.model("1L"))
    self.show()
    points = remove_close(tips(self.clicker.mesh, self.clicker.odom.occlusal))
    self.set_points(points)

    assert self.clicker.cursors[0].color == (.9, 0, 0)
    assert self.clicker.cursors[1].color == (0, 0, 0)
    select_rows(self, 0)
    assert self.clicker.cursors[0].color == (.9, 0, 0)
    assert self.clicker.cursors[1].color == (0, 0, 0)
    select_rows(self, 1)
    assert self.clicker.cursors[0].color == (0, 0, 0)
    assert self.clicker.cursors[1].color == (.9, 0, 0)
    select_rows(self, 2)
    assert self.clicker.cursors[0].color == (0, 0, 0)
    assert self.clicker.cursors[1].color == (0, 0, 0)

    select_rows(self, 0, 2, 1)
    assert self.clicker.cursors[0].color == (.9, 0, 0)
    assert self.clicker.cursors[1].color == (.9, 0, 0)

    self.close()


def test_delete():
    """Test the delete and clear all buttons."""
    self = ManualLandmarkSelection(Palmer.range("LL5", "LR5"),
                                   tomial_tooth_collection_api.model("1L"))
    self.show()
    points = remove_close(tips(self.clicker.mesh, self.clicker.odom.occlusal))
    self.set_points(points)

    select_rows(self, 0, 1, 2)
    self.table.delete_button.click()
    for i in range(3):
        assert i not in self.clicker.cursors
    for i in range(3, 10):
        assert self.clicker.cursors[i]
    assert self.table[:3] == [None] * 3
    assert (self.table[3:] == points[3:]).all()

    self.table.clear_all_button.click()
    assert self.table[:] == [None] * 10
    assert self.clicker.cursors == {}
    assert len(self.clicker.plots) == 1

    self.close()


@pytest.mark.parametrize("long_names", [False, True])
@pytest.mark.parametrize("show", ["show", "showMaximized", "showFullScreen"])
def test_table_layout(long_names, show):
    """Ensure that the table reactively takes as much horizontal space as it
    needs to avoid needing a horizontal scroll bar, but no more.

    """
    names = Palmer.range()
    if long_names:
        names = [
            f"The bit on the {i} where the landmark needs to go" for i in names
        ]

    self = ManualLandmarkSelection(names)
    self._open_model(tomial_tooth_collection_api.model("1L"))

    getattr(self, show)()
    # Xvfb has no concept of maximised/fullscreen mode and Qt can't detect its
    # screen size so manually set it to use the full screen.
    if xvfb_size():
        if show == "showMaximized":
            return
        if show == "showFullScreen":
            self.resize(*xvfb_size())

    # If not using maximised/fullscreen mode, make the window tiny.
    if show == "show":
        self.resize(600, 400)
    target_width = self.table.table.sizeHint().width()

    for i in range(3):
        app.processEvents()
        if self.table.table.width() == target_width:
            break
    assert self.table.table.width() == target_width

    assert not self.table.table.horizontalScrollBar().isVisible()
    assert target_width < self.table.width() < target_width + 50

    # The table should expand horizontally a bit when landmarks are added to fit
    # the coordinates.
    old_size = self.table.size()
    for point in self.clicker.mesh.vectors[[1000, 20000], 0]:
        self.clicker.spawn_cursor(point)
    app.processEvents()
    assert self.table.width() > old_size.width()
    assert self.table.height() == old_size.height()
    assert not self.table.table.horizontalScrollBar().isVisible()

    self.close()


def test_paste():
    """Test pasting points into the landmark table."""
    self = ManualLandmarkSelection(Palmer.range(0, "LR5"))
    self.show()
    app.processEvents()

    # Basic paste one point.
    pyperclip.copy("123\t456\t789")
    self.table.paste_button.click()
    assert self.table[0] == (123, 456, 789)
    assert self.clicker.cursors[0].point == (123, 456, 789)

    # Populate the table.
    points = np.c_[np.arange(5) * 4, np.random.random(5), np.random.random(5)]
    self.set_points(points)
    self.clicker.reset_camera()
    self.clicker.update()
    assert np.all(self.get_points() == points)

    # Test that various invalid CSVs don't write to the table before realising
    # that they are invalid.
    for text in INVALID_CSVs:
        assert _csv.parse_points(text) is None
        pyperclip.copy(text)
        self.table.paste_button.click()
        assert np.all(self.get_points() == points)

    # Ensure that trailing newlines don't cause the next point to be overwritten
    # with a blank.
    self.table.table.selectRow(3)
    pyperclip.copy("0,0,0\n")
    self.table.paste()
    assert self.table[3] == (0, 0, 0)
    assert np.all(self.clicker.cursors[4].point == points[4])

    # Paste overwriting all values, including replacing points with blanks.
    pyperclip.copy(",,\r\n1, .5, .3\r\n,,\r\n3,.2,.6\r\n,,")
    self.table.table.selectRow(0)
    self.table.paste()
    assert len(self.clicker.cursors) == 2
    assert self.clicker.cursors[1].point == (1, .5, .3)
    assert self.clicker.cursors[3].point == (3, .2, .6)

    # Paste starting from the middle of the table so that the last two values in
    # the clipboard don't fit into the table and should be discarded.
    self.table.table.selectRow(2)
    self.table.paste()
    assert len(self.clicker.cursors) == 2
    assert self.clicker.cursors[1].point == (1, .5, .3)
    assert self.clicker.cursors[3].point == (1, .5, .3)

    self.close()


def test_copy():
    """Test the copy and cut buttons."""
    pyperclip.copy("")

    points = np.c_[np.arange(5) * 5, np.zeros(5), np.ones(5)]
    self = ManualLandmarkSelection(Palmer.range(0, "LR5"), points=points)
    self.show()
    app.processEvents()

    self.table.copy_button.click()
    assert pyperclip.paste() == "0.0\t0.0\t1.0"

    select_rows(self, 1, 2, 4)
    self.table.copy()
    assert pyperclip.paste() == "5.0\t0.0\t1.0\n10.0\t0.0\t1.0\n20.0\t0.0\t1.0"

    select_rows(self, 0, 2)
    self.table.cut_button.click()
    assert pyperclip.paste() == "0.0\t0.0\t1.0\n10.0\t0.0\t1.0"
    assert sorted(self.clicker.cursors) == [1, 3, 4]

    self.close()


def test_save():
    points = np.arange(6).reshape((2, 3))
    self = ManualLandmarkSelection(["foo", "bar"], points=points)
    self.show()
    app.processEvents()

    def _test_write(name):
        csv_path = os.path.join(root, name)
        with select_file(csv_path):
            self.table.save()
        with open(csv_path) as f:
            assert_text_equivalent(f.read(),
                                   "Landmarks,X,Y,Z\nfoo,0,1,2\nbar,3,4,5\n")

    with tempfile.TemporaryDirectory() as root:
        assert self.table.default_save_name() == ""
        _test_write("foo.csv")
        with select_file(tomial_tooth_collection_api.model("1L")):
            self.open_model()
        assert self.table.default_save_name() == "1L.csv"
        _test_write("1L.csv")

    self.close()
