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
