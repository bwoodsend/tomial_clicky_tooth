import os
from pathlib import Path
import re

import pytest
import mss


def pytest_addoption(parser):
    parser.addoption("--screenshot-on-fail", action="store_true",
                     help="Screenshot on failed tests.")


def pytest_configure(config):
    if config.getvalue("screenshot_on_fail"):
        root: Path = config.rootpath / ".screenshots"
        root.mkdir(exist_ok=True)
        for path in root.iterdir():
            os.remove(path)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()

    if not item.config.getvalue("screenshot_on_fail"):
        return
    if result.when != "call" or result.passed:
        return

    with mss.mss() as screen:
        name = re.sub(r"[^\w.\-]+", " ", item.nodeid) + ".png"
        screen.shot(output=str(item.config.rootdir / ".screenshots" / name))


def pytest_report_header(config):
    """Add virtual screen size to pytest's header."""
    from tests import xvfb_size
    return ["Xvfb display: {}".format(xvfb_size())]


@pytest.fixture(autouse=True)
def close_all_windows():
    """Close all open Qt Windows before and after each test."""
    from tomial_clicky_tooth._qapp import app

    def _close_all_windows():
        for window in app.allWindows():
            try:
                window.close()
            except RuntimeError:
                pass

    _close_all_windows()
    yield
    _close_all_windows()
