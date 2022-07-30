from . import _qapp
from ._landmark_templates import LandmarksTemplate, LandmarksContext
from ._ui import UI, main


def _PyInstaller_hook_dir():  # pragma: no cover
    import os
    return [os.path.dirname(__file__)]
