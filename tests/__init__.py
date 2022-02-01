import os

import psutil


def xvfb_size():
    """Get the screen size of an Xvfb virtual display server."""
    for process in psutil.process_iter(["name"]):
        if process.info["name"] == "Xvfb":
            if os.environ["DISPLAY"] in process.cmdline():
                break
    else:
        return

    index = process.cmdline().index("-screen")
    _, monitor, size = process.cmdline()[index:index + 3]
    width, height, depth = map(int, size.split("x"))

    return width, height
