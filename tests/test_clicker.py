import tomial_tooth_collection_api
import vtkplotlib as vpl

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth._clicker import ClickerQtWidget


def test_file_orientation():
    """Test that the initial orientation is the occlusal view."""
    self = ClickerQtWidget()
    self.show(block=False)
    assert len(self.plots) == 0

    path = tomial_tooth_collection_api.model("1L")
    self.open_stl(path)
    app.processEvents()
    assert len(self.plots) == 1

    # Verify that the odometry worked.
    assert self.odom.occlusal([0, 1, 0]) > .9
    assert self.odom.forwards([1, 0, 0]) > .9

    # And that the camera has adjusted itself correctly to match.
    self.stl_plot.tri_scalars = (self.mesh.units + 1) / 2
    app.processEvents()
    assert _principle_color(self).argmax() == 1

    self.close()


def _principle_color(figure):
    """Get an average non-background RGB color."""
    figure.background_color = "black"
    image = vpl.screenshot_fig(fig=figure)
    return image[(image != 0).any(-1)].mean(0)
