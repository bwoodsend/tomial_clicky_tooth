import sys

from pangolin import Palmer
import ptpython

from tomial_clicky_tooth._ui import *


class Interact(QtCore.QThread):  # pragma: no cover
    def __init__(self, namespace):
        self.namespace = namespace
        super().__init__()

    def run(self):
        ptpython.embed(self.namespace)
        self.namespace["self"].close()


def debug(names=None, path=None, points=None):
    self = UI(names, path, points)
    self.show()
    t = Interact({**locals(), **globals()})
    t.start()
    app.exec()


if __name__ == '__main__':
    debug(None, *sys.argv[1:])
