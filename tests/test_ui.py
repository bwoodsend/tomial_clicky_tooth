import numpy as np
from PyQt5 import QtTest, QtCore
from vtkmodules.vtkRenderingCore import vtkCoordinate
from motmot import geometry
from pangolin import Palmer
import tomial_tooth_collection_api

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth._ui import ManualLandmarkSelection


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
    for i in range(self.table.shape[0]):
        for j in range(self.table.shape[1]):
            self.table.table.item(i, j).setSelected(i in row_numbers)


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
