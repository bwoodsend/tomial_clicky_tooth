import tempfile
from pathlib import Path
import shutil
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
import numpy as np
from PyQt5 import QtTest, QtCore, QtGui
import pyperclip
from vtkmodules.vtkRenderingCore import vtkCoordinate
from motmot import geometry
from pangolin import Palmer
import vtkplotlib as vpl
import tomial_tooth_collection_api

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth import _csv_io
from tomial_clicky_tooth._ui import UI
from tests import xvfb_size, select_file, CloseBlockingDialog
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
    heights = occlusal(mesh.vertices)
    ids = mesh.local_maxima(heights, boundaries=False)
    ids = ids[np.argsort(heights[ids])[::-1]]
    return mesh.vertices[ids]


def remove_close(points):
    """Pick out 8 points which are at least 10mm apart from each other."""
    out = np.empty((8, 3), dtype=points.dtype)
    points = iter(points)
    for i in range(8):
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


def action(menu, name):
    """Find a button in a menu of the menu bar."""
    available = [i.text().replace("&", "") for i in menu.actions()]
    for (i, text) in enumerate(available):
        if name.replace("&", "") == text:
            return menu.actions()[i]
    raise ValueError(f"Action named '{name}' not found in {available}")


def test_clicking():
    """Test left and right clicking on the renderer."""
    self = UI(["a", "b", "c", "d"])
    self.show()

    self._open_model(tomial_tooth_collection_api.model("1L"))
    app.processEvents()
    assert np.array(self.table).shape == (4, 3)
    assert np.isnan(np.array(self.table)).all()

    points = remove_close(
        tips(self.clicker.mesh, self.clicker.odometry.occlusal))
    highlight(self.clicker.mesh_plot, points[0])

    assert self.table.highlighted_rows() == [0]
    click(self, points[0])
    assert self.table.highlighted_rows() == [1]
    assert np.allclose(self.table[0], points[0], atol=1)
    assert np.allclose(self.clicker.markers[0].point, points[0], atol=1)

    highlight(self.clicker.mesh_plot, points[1])
    click(self, points[1])
    assert self.table.highlighted_rows() == [2]
    assert np.allclose(self.table[1], points[1], atol=1)
    assert np.allclose(self.clicker.markers[1].point, points[1], atol=1)

    highlight(self.clicker.mesh_plot, points[3])
    select_rows(self, 3)
    click(self, points[3])
    assert self.table.highlighted_rows() == [3]
    assert np.allclose(self.table[3], points[3], atol=1)
    assert np.allclose(self.clicker.markers[3].point, points[3], atol=1)

    highlight(self.clicker.mesh_plot, points[4])
    click(self, points[4])
    assert self.table.highlighted_rows() == [3]
    assert np.allclose(self.table[3], points[4], atol=1)
    assert np.allclose(self.clicker.markers[3].point, points[4], atol=1)

    select_rows(self)
    highlight(self.clicker.mesh_plot, points[5])
    click(self, points[5])
    assert self.table.highlighted_rows() == [2]
    assert np.allclose(self.table[2], points[5], atol=1)
    assert np.allclose(self.clicker.markers[2].point, points[5], atol=1)

    self.clicker.mesh_plot.scalars = None

    click(self, points[5], button="R")
    assert sorted(self.clicker.markers.keys()) == [0, 1, 3]
    click(self, points[4], button="R")
    assert sorted(self.clicker.markers.keys()) == [0, 1]
    click(self, points[0], button="R")
    assert sorted(self.clicker.markers.keys()) == [1]
    click(self, points[0], button="R")
    assert sorted(self.clicker.markers.keys()) == [1]

    # Clicking on empty space should do nothing.
    click_2d(self, 10, 10)
    assert sorted(self.clicker.markers.keys()) == [1]
    click_2d(self, 10, 10, button="R")
    assert sorted(self.clicker.markers.keys()) == [1]

    self.close()


def test_highlight():
    """Test highlighting table rows highlights the corresponding placed markers
    in the renderer."""
    self = UI(Palmer.range("LL5", "LR5"),
              tomial_tooth_collection_api.model("1L"))
    self.show()
    points = remove_close(
        tips(self.clicker.mesh, self.clicker.odometry.occlusal))
    self.points = points

    assert self.clicker.markers[0].color == (.9, 0, 0)
    assert self.clicker.markers[1].color == (0, 0, 0)
    select_rows(self, 0)
    assert self.clicker.markers[0].color == (.9, 0, 0)
    assert self.clicker.markers[1].color == (0, 0, 0)
    select_rows(self, 1)
    assert self.clicker.markers[0].color == (0, 0, 0)
    assert self.clicker.markers[1].color == (.9, 0, 0)
    select_rows(self, 2)
    assert self.clicker.markers[0].color == (0, 0, 0)
    assert self.clicker.markers[1].color == (0, 0, 0)

    select_rows(self, 0, 2, 1)
    assert self.clicker.markers[0].color == (.9, 0, 0)
    assert self.clicker.markers[1].color == (.9, 0, 0)

    self.close()


def test_delete():
    """Test the delete and clear all buttons."""
    self = UI(Palmer.range("LL4", "LR4"),
              tomial_tooth_collection_api.model("1L"))
    self.show()
    points = remove_close(
        tips(self.clicker.mesh, self.clicker.odometry.occlusal))
    self.points = points

    select_rows(self, 0, 1, 2)
    self.table.delete_button.click()
    for i in range(3):
        assert i not in self.clicker.markers
    for i in range(3, 8):
        assert self.clicker.markers[i]
    assert self.table[:3] == [None] * 3
    assert (self.table[3:] == points[3:]).all()

    self.table.clear_all_button.click()
    assert self.table[:] == [None] * 8
    assert self.clicker.markers == {}
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

    self = UI(names)
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
        self.clicker.spawn_marker(point)
    app.processEvents()
    assert self.table.width() > old_size.width()
    assert self.table.height() == old_size.height()
    assert not self.table.table.horizontalScrollBar().isVisible()

    self.close()


def test_paste():
    """Test pasting points into the landmark table."""
    self = UI(Palmer.range(0, "LR5"))
    self.show()
    app.processEvents()

    # Basic paste one point.
    pyperclip.copy("123\t456\t789")
    action(self.menu_bar["&Edit"], "Paste").trigger()
    assert self.table[0] == (123, 456, 789)
    assert self.clicker.markers[0].point == (123, 456, 789)

    # Populate the table.
    points = np.c_[np.arange(5) * 4, np.random.random(5), np.random.random(5)]
    self.points = points
    self.clicker.reset_camera()
    self.clicker.update()
    assert np.all(self.points == points)

    # Test that various invalid CSVs don't write to the table before realising
    # that they are invalid.
    for text in INVALID_CSVs:
        assert _csv_io.parse_points(text) is None
        pyperclip.copy(text)
        self.table.paste()
        assert np.all(self.points == points)

    # Ensure that trailing newlines don't cause the next point to be overwritten
    # with a blank.
    self.table.table.selectRow(3)
    pyperclip.copy("0,0,0\n")
    self.table.paste()
    assert self.table[3] == (0, 0, 0)
    assert np.all(self.clicker.markers[4].point == points[4])

    # Paste overwriting all values, including replacing points with blanks.
    pyperclip.copy(",,\r\n1, .5, .3\r\n,,\r\n3,.2,.6\r\n,,")
    self.table.table.selectRow(0)
    self.table.paste()
    assert len(self.clicker.markers) == 2
    assert self.clicker.markers[1].point == (1, .5, .3)
    assert self.clicker.markers[3].point == (3, .2, .6)

    # Paste starting from the middle of the table so that the last two values in
    # the clipboard don't fit into the table and should be discarded.
    self.table.table.selectRow(2)
    self.table.paste()
    assert len(self.clicker.markers) == 2
    assert self.clicker.markers[1].point == (1, .5, .3)
    assert self.clicker.markers[3].point == (1, .5, .3)

    # With nothing selected, paste starting from the top.
    select_rows(self)
    self.table.paste()
    assert len(self.clicker.markers) == 2
    assert self.clicker.markers[1].point == (1, .5, .3)
    assert self.clicker.markers[3].point == (3, .2, .6)

    self.close()


def test_copy():
    """Test the copy and cut buttons."""
    pyperclip.copy("")

    points = np.c_[np.arange(5) * 5, np.zeros(5), np.ones(5)]
    self = UI(Palmer.range(0, "LR5"), points=points)
    self.show()
    app.processEvents()

    action(self.menu_bar["&Edit"], "Copy").trigger()
    assert pyperclip.paste() == "0.0\t0.0\t1.0"

    select_rows(self, 1, 2, 4)
    self.table.copy()
    assert pyperclip.paste() == "5.0\t0.0\t1.0\n10.0\t0.0\t1.0\n20.0\t0.0\t1.0"

    select_rows(self, 0, 2)
    action(self.menu_bar["&Edit"], "Cut").trigger()
    assert pyperclip.paste() == "0.0\t0.0\t1.0\n10.0\t0.0\t1.0"
    assert sorted(self.clicker.markers) == [1, 3, 4]

    self.close()


def test_save():
    points = np.arange(6).reshape((2, 3))
    self = UI(["foo", "bar"], points=points)
    self.show()
    app.processEvents()

    def _test_write(name):
        csv_path = os.path.join(root, name)
        with select_file(csv_path):
            self.table.save_as()
        with open(csv_path) as f:
            assert_text_equivalent(f.read(),
                                   "Landmarks,X,Y,Z\nfoo,0,1,2\nbar,3,4,5\n")

    with tempfile.TemporaryDirectory() as root:
        assert self.table.default_csv_path() == ""
        _test_write("foo.csv")
        with select_file(tomial_tooth_collection_api.model("1L")):
            self.open_model()
        self.points = points
        assert self.table.default_csv_path().name == "1L.csv"
        _test_write("1L.csv")

    self.close()


def key_press(widget, key, modifier=QtCore.Qt.NoModifier):
    """Send keyboard events."""
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifier)
    app.sendEvent(widget, event)


def test_model_switching():
    """Test iterating through a directory of models."""
    from PyQt5.QtCore import Qt

    # Put several models and a points file in a single directory.
    with tempfile.TemporaryDirectory() as root:
        root = Path(root)
        files = [
            Path(shutil.copy(tomial_tooth_collection_api.model(name), root))
            for name in ["1L", "1U", "2L", "2U"]
        ]

        self = UI(Palmer.range(), path=files[0])
        self.show()
        app.processEvents()

        assert self.clicker.path == files[0]
        self.buttons[1].click()
        assert self.clicker.path != files[0]
        assert self.clicker.path in files
        self.buttons[0].click()
        assert self.clicker.path == files[0]

        key_press(self, Qt.Key_Right)
        assert self.clicker.path != files[0]
        key_press(self, Qt.Key_Left)
        assert self.clicker.path == files[0]

        key_press(self, Qt.Key_Left, Qt.ShiftModifier)
        assert self.clicker.path == files[0]
        key_press(self.table.table, Qt.Key_Up)
        assert self.clicker.path == files[0]
        key_press(self.table.table, Qt.Key_Left, Qt.ShiftModifier)
        assert self.clicker.path == files[0]

        # It shouldn't matter which portion of the UI currently has focus.
        key_press(self.clicker, Qt.Key_Right)
        assert self.clicker.path != files[0]
        key_press(self.clicker.vtkWidget, Qt.Key_Left)
        assert self.clicker.path == files[0]
        key_press(self.table, Qt.Key_Right)
        assert self.clicker.path != files[0]
        key_press(self.table.table, Qt.Key_Left)
        assert self.clicker.path == files[0]

        # Check the orientation is adjusting to each model.
        up = self.clicker.odometry.up
        forwards = self.clicker.odometry.forwards
        while not self.clicker.path.name.startswith("1U"):
            self.buttons[0].click()
        view = vpl.view(fig=self.clicker)
        camera_direction = geometry.UnitVector(
            np.array(view["focal_point"]) - view["camera_position"])
        assert camera_direction(up) > .9
        assert forwards(view["up_view"]) > .9

        # With a landmarks file present, it should be picked up.
        shutil.copy(Path(__file__).with_name("1L.csv"), root)
        while not self.clicker.path.name.startswith("1L"):
            self.switch_model(">")
        assert len(self.clicker.markers) == 14
        self.switch_model(">")
        assert len(self.clicker.markers) == 0

        # Without appropriate thread control, the UI will crash if the user
        # holds either left or right keys for around >30 seconds.
        with ThreadPoolExecutor() as pool:
            clicks = [pool.submit(self.buttons[0].click) for i in range(200)]
            [i.result() for i in clicks]
        app.processEvents()

    # Verify that nothing happens if the STL is deleted.
    assert not self.clicker.path.exists()
    old_points = np.arange(12).reshape((4, 3))
    self.points = old_points
    old_stl_plot = self.clicker.mesh_plot
    self.buttons[0].click()
    assert self.clicker.mesh_plot is old_stl_plot
    assert np.array_equal(self.points[:4], old_points)

    self.close()


def test_custom_files_index(tmpdir):
    """Test a custom implementation of UI.files_index() which iterates over a
    predefined set of files instead of over a directory."""
    files = [
        Path(shutil.copy(tomial_tooth_collection_api.model("1L"), tmpdir)),
        tomial_tooth_collection_api.model("2L"),
    ]

    class CustomFileList(UI):
        def files_index(self):
            try:
                return files, files.index(self.path)
            except ValueError:
                return None, None

        def csv_path(self):
            return tmpdir / f"foo-{self.path.name}.csv"

    self = CustomFileList(Palmer.range(), files[0])
    self.show()

    assert self.path == files[0]
    assert self.model_name_indicator.text() == "1L"
    assert self.model_number_indicator.text() == "(1/2)"
    assert self.table.default_csv_path() == tmpdir / "foo-1L.stl.gz.csv"
    self.table.save()
    assert self.table.default_csv_path().exists()

    self.switch_model(">")
    assert self.path == files[1]
    assert self.model_name_indicator.text() == "2L"
    assert self.model_number_indicator.text() == "(2/2)"

    self.switch_model(">")
    assert self.path == files[0]
    assert self.model_name_indicator.text() == "1L"
    assert self.model_number_indicator.text() == "(1/2)"

    self._open_model(tomial_tooth_collection_api.model("2U"))
    assert self.path == tomial_tooth_collection_api.model("2U")
    assert self.model_name_indicator.text() == "2U"
    assert self.model_number_indicator.text() == ""


def test_no_model_open():
    """Make sure that we can't cause a crash by pressing buttons when no model
    is loaded."""
    self = UI(Palmer.range())
    self.show()
    app.processEvents()

    with select_file(None):
        self.open_model()
    assert self.clicker.path is None

    self.buttons[0].click()

    with select_file(None):
        self.table.save_as()

    self.points = [[1, 2, 3]]
    read, write = os.pipe()
    self.table._save(write)
    with open(read, "rb") as f:
        assert f.readlines()[1].startswith(b"*L8,1.0,2.0,3.0")

    self.close()


def test_invalid_model(tmpdir):
    """Test the various points where an invalid model may be loaded."""

    model, invalid, landmarks = [
        Path(shutil.copy(
            i, tmpdir)) for i in (tomial_tooth_collection_api.model("1L"),
                                  Path(__file__).with_name("invalid.stl"),
                                  Path(__file__).with_name("1L.csv"))
    ]

    # Open an invalid model on startup.
    with CloseBlockingDialog():
        self = UI(Palmer.range(), invalid)
    self.show()
    app.processEvents()
    assert self.clicker.path == invalid
    assert self.clicker.mesh is None
    assert self.clicker.mesh_plot is None

    # Via the open model dialog after opening a functional model.
    self._open_model(model)
    assert self.clicker.path == model
    assert np.isfinite(self.clicker.landmarks[1]).sum() == 3 * 14
    with CloseBlockingDialog():
        self._open_model(invalid)
    assert self.clicker.path == invalid
    assert self.clicker.mesh is None
    assert len(self.clicker.markers) == 0

    # By switching models via the buttons.
    self.buttons[0].click()
    assert self.clicker.path == model
    with CloseBlockingDialog():
        self.buttons[0].click()

    self.close()


def test_show_licenses():
    self = UI(Palmer.range())
    self.show()
    app.processEvents()

    self.show_licenses()
    assert self._licenses.isVisible()


def test_history(tmpdir):
    """Test undo/redo."""
    self = UI(Palmer.range())
    self.show()
    app.processEvents()

    assert len(self._history) == 1
    assert self._history.position == 0
    assert np.isnan(self._history[0]).all()
    assert not self.isWindowModified()

    files = [
        Path(shutil.copy(tomial_tooth_collection_api.model(name), tmpdir))
        for name in ["1L", "1U"]
    ]

    old_history = self._history
    self._open_model(files[0])
    assert self._history is not old_history
    assert len(self._history) == 1
    assert self._history.position == 0
    assert np.isnan(self._history[0]).all()
    assert not self.isWindowModified()

    pyperclip.copy("1\t2\t3\n4\t5\t6")
    action(self.menu_bar["&Edit"], "Paste").trigger()
    assert len(self._history) == 2
    assert self._history.position == 1
    assert np.array_equal(self.points[:2], self._history[1][:2])
    assert self.isWindowModified()

    self.undo()
    assert len(self._history) == 2
    assert np.isnan(self.points).all()
    assert not self.isWindowModified()
    self.undo()
    assert len(self._history) == 2
    assert np.isnan(self.points).all()
    assert not self.isWindowModified()

    self.clicker.spawn_marker((7, 8, 9))
    self.clicker.spawn_marker((10, 11, 12))
    assert len(self._history) == 3
    assert self.isWindowModified()
    self.table._save(tmpdir / "foo.csv")
    assert not self.isWindowModified()

    self.undo()
    self.clicker.spawn_marker((10, 11, 12))
    assert len(self._history) == 3
    assert self.isWindowModified()

    self.undo()
    assert self.isWindowModified()
    self.redo()
    assert sorted(self.clicker.markers) == [0, 2]
    self.redo()
    assert sorted(self.clicker.markers) == [0, 2]
    assert self.isWindowModified()

    self.clicker.spawn_marker((13, 14, 15))
    self.clicker.spawn_marker((16, 17, 18))
    for i in range(10):
        self.undo()
    for i in range(10):
        self.redo()
