import os
from contextlib import contextmanager
from functools import wraps

import psutil
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QFileDialog

from tomial_clicky_tooth._qapp import app

# Pin the font size for testing so that macOS CI with its tiny screens and huge
# default font size doesn't break all the layout tests.
app.setStyleSheet("QWidget: {font-size: 11pt}")


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


class CloseBlockingDialog(object):
    """Anything inheriting from QtWidgets.QDialog blocks the program until
    it is closed (normally by the user). This context manager launches a
    background process which periodically closes any open visible QDialogs.

    .. code-block:: python

        with CloseBlockingDialog():
            QtWidgets.QMessageBox.aboutQt(None, "Blocking Dialog")

    """
    def __init__(self, type=QtWidgets.QDialog):
        self.type = type

    def __enter__(self):
        self._timer = timer = QtCore.QTimer()
        timer.setInterval(200)
        timer.timeout.connect(self._handle_dialogs)
        timer.start()
        self.closed = None
        return self

    def _handle_dialogs(self):
        for widget in app.allWidgets():
            if isinstance(widget, (QtWidgets.QDialog, self.type)):
                if widget.isVisible():
                    self._timer.stop()
                    self.closed = widget
                    self.handle_dialog(widget)

    @staticmethod
    def handle_dialog(dialog: QtWidgets.QDialog):
        dialog.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._timer.stop()
        if exc_val:
            return
        assert self.closed is not None, "No dialog appeared."
        assert isinstance(self.closed, self.type), \
            repr(self.closed) + " is not a " + str(self.type)


class MockFileDialog:
    def __init__(self, *paths):
        self.paths = [os.path.realpath(i) for i in paths]

    @wraps(QFileDialog.getOpenFileName)
    def getOpenFileName(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        assert len(self.paths) == 1
        return self.paths[0], os.path.splitext(self.paths[0])[1]

    def getOpenFileNames(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self.paths, os.path.splitext(self.paths[0])[1]

    def getSaveFileName(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self.paths[0], os.path.splitext(self.paths[0])

    def getExistingDirectory(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        assert len(self.paths) == 1
        assert os.path.isdir(self.paths[0])
        return self.paths[0]


@contextmanager
def select_file(*paths):
    """Mimic the user choosing a given file in an open or save as dialog."""
    selector = MockFileDialog(*paths)
    QtWidgets.QFileDialog = selector
    yield selector
    QtWidgets.QFileDialog = QFileDialog
