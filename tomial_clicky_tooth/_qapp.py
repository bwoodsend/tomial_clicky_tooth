from pathlib import Path

from PyQt6 import QtWidgets, QtGui

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
app.setApplicationName("Tomial Clicky Tooth")

icon = Path(__file__).with_name("favicon.png")
assert icon.exists()
app.setWindowIcon(QtGui.QIcon(str(icon)))
