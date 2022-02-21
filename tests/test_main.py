import pytest
from tomial_tooth_collection_api import model

from tomial_clicky_tooth._ui import main, ManualLandmarkSelection
from tests import CloseBlockingDialog

pytestmark = pytest.mark.order(8)


def test_main():
    """Test the CLI. To be expanded when we actually have a significant CLI."""
    with CloseBlockingDialog(type=ManualLandmarkSelection):
        self = main(["a", "b", "c"], path=model("1L"))
    assert self.clicker.stl_path == model("1L")
