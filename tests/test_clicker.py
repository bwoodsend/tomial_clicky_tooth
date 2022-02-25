from pathlib import Path

import pytest
import tomial_tooth_collection_api
import vtkplotlib as vpl

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth._clicker import ClickableFigure

pytestmark = pytest.mark.order(2)


def test_file_orientation():
    """Test that the initial orientation is the occlusal view."""
    self = ClickableFigure()
    self.show(block=False)
    assert len(self.plots) == 0

    path = tomial_tooth_collection_api.model("1L")
    self.open_model(path)
    app.processEvents()
    assert len(self.plots) == 1

    # Verify that the odometry worked.
    assert self.odometry.occlusal([0, 1, 0]) > .9
    assert self.odometry.forwards([1, 0, 0]) > .9

    # And that the camera has adjusted itself correctly to match.
    vpl.scatter([0, 10, 0], radius=3, color="g", fig=self)
    vpl.scatter([0, -10, 0], radius=3, color="r", fig=self)
    self.mesh_plot.color = "b"
    app.processEvents()
    r, g, b = _principle_color(self)
    assert r < g < b

    self.close()


def _principle_color(figure):
    """Get an average non-background RGB color."""
    figure.background_color = "black"
    image = vpl.screenshot_fig(fig=figure)
    return image[(image != 0).any(-1)].mean(0)


@pytest.mark.filterwarnings("ignore")
def test_non_dental_model():
    """Test opening a model that is unlikely to pass through the pre-orientation
    step due to its not being a dental model. The pre-orientation should be
    skipped over silently."""
    self = ClickableFigure()
    self.show(block=False)

    self.open_model(Path(__file__).with_name("one-triangle.stl"))
    assert self.odometry is None
    assert self.mesh is not None

    self.close()
