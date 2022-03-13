import sys

from pangolin import Palmer

from tomial_clicky_tooth._ui import *


class Interact(QtCore.QThread):  # pragma: no cover
    def __init__(self, namespace):
        self.namespace = namespace
        super().__init__()

    def run(self):
        import code
        import readline
        import rlcompleter

        readline.set_completer(rlcompleter.Completer(self.namespace).complete)
        readline.parse_and_bind("tab: complete")
        code.InteractiveConsole(self.namespace).interact()


def debug(names, path=None, points=None):
    self = UI(names, path, points)
    self.show()
    t = Interact({**locals(), **globals()})
    t.start()
    app.exec()


if __name__ == '__main__':
    debug(Palmer.range(), *sys.argv[1:])
