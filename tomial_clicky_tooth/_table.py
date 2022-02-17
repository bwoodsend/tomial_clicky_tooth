from textwrap import wrap
import platform

import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
import pyperclip

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth import _misc, _csv_io


class _QTable(QtWidgets.QTableWidget):

    # On macOS, the scroll bar hovers over the table instead of slotting in
    # next to it.
    ignore_scroll_bar_width = platform.system() == "Darwin"

    def keyPressEvent(self, event):
        if event.modifiers() == QtCore.Qt.NoModifier:
            if event.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
                event.ignore()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def sizeHint(self) -> QtCore.QSize:
        """Use exactly the required amount of horizontal space to fit all table
        cells without resorting to abbreviating or scroll bars."""
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        width = self.verticalHeader().width() + 2
        if not self.ignore_scroll_bar_width:  # pragma: no cover
            if self.verticalScrollBar().isVisible():
                width += self.verticalScrollBar().sizeHint().width()
        for i in range(self.columnCount()):
            width += self.columnWidth(i)

        return QtCore.QSize(width, super().sizeHint().height())


def button(callback):
    name = callback.__name__.replace("_", " ").strip().title()
    out = QtWidgets.QPushButton(name)
    out.released.connect(callback)
    return out


class LandmarkTable(QtWidgets.QWidget):

    COLUMNS = ["Landmark", "X", "Y", "Z"]
    COLUMN_NUMBERS = {name: i for (i, name) in enumerate(COLUMNS)}

    def __init__(self, names, parent=None):
        self.names = names
        super().__init__(parent)

        self.table = table = _QTable()
        self.points = {}

        self.box = QtWidgets.QVBoxLayout()
        self.setLayout(self.box)
        self.box.addWidget(table)

        # The table should strictly obey its horizontal size hint but use as
        # much vertical space as is available.
        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed,
                                       QtWidgets.QSizePolicy.Ignored)
        self.setSizePolicy(policy)

        self.font = QtGui.QFont()
        self.font.setPixelSize(16)
        self.table.setFont(self.font)

        self.setup_buttons()

        table.setColumnCount(len(self.COLUMNS))
        table.setHorizontalHeaderLabels(self.COLUMNS)
        table.setSizeAdjustPolicy(table.AdjustToContents)
        table.setSelectionBehavior(table.SelectRows)
        table.horizontalHeader().setMinimumSectionSize(50)

        self.load_table_contents(names)
        self.table.setWordWrap(True)
        self.table.itemChanged.connect(self.table.adjustSize)

        self._suppress_itemSelectionChanged = False
        self.table.itemSelectionChanged.connect(
            self._filter_itemSelectionChanged)

        self.increment_focus()

    def setup_buttons(self):
        buttons_layout = QtWidgets.QGridLayout()
        self.box.addLayout(buttons_layout)

        self.cut_button = button(self.cut)
        self.copy_button = button(self.copy)
        self.paste_button = button(self.paste)
        self.delete_button = button(self.delete)
        self.clear_all_button = button(self.clear_all)
        self.save_button = button(self.save)

        for (i, _button) in enumerate([
                self.delete_button,
                self.clear_all_button,
                self.cut_button,
                self.copy_button,
                self.paste_button,
                self.save_button,
        ]):
            buttons_layout.addWidget(_button, *divmod(i, 2))

        self.delete_button.setShortcut(QtCore.Qt.Key_Delete)
        self.cut_button.setShortcut(QtGui.QKeySequence.StandardKey.Cut)
        self.copy_button.setShortcut(QtGui.QKeySequence.StandardKey.Copy)
        self.paste_button.setShortcut(QtGui.QKeySequence.StandardKey.Paste)

    @property
    def shape(self):
        return self.table.rowCount(), self.table.columnCount()

    def load_table_contents(self, names):
        self.table.setRowCount(len(names))

        self.items = np.empty(self.shape, object)

        for (i, name) in enumerate(names):
            for j in range(1, len(self.COLUMNS)):
                self.table.setItem(i, j, QtWidgets.QTableWidgetItem(""))

            cell = QtWidgets.QTableWidgetItem("\n".join(wrap(str(name), 40)))
            self.table.setItem(i, 0, cell)

        self.table.adjustSize()

    def clear_all(self):
        del self[:]
        self.landmarks_changed.emit(np.array(self))

    def delete(self):
        del self[self.highlighted_rows()]
        self.landmarks_changed.emit(np.array(self))

    def increment_focus(self):
        current_focus = self.highlighted_rows()
        if len(current_focus):
            start = current_focus[0]
        else:
            start = 0

        for i in range(start, self.shape[0]):
            if self[i] is None:
                self.table.selectRow(i)
                return

        if len(current_focus) == 0:
            self.table.selectRow(i)

    def highlighted_rows(self):
        return sorted(set([i.row() for i in self.table.selectedItems()]))

    landmarks_changed = QtCore.pyqtSignal(object)
    itemSelectionChanged = QtCore.pyqtSignal()

    @_misc.multiitemsable
    @_misc.sliceable
    def __getitem__(self, index):
        return self.points.get(index)

    def __len__(self):
        return self.table.rowCount()

    @_misc.multiitemsable
    @_misc.sliceable
    def __setitem__(self, index, point):
        if point is None or np.isnan(point).all():
            texts = [""] * 3
            point = None
        else:
            texts = np.round(point, 3).astype(str)
            point = tuple(point)
        self.points[index] = point
        for (i, ax) in enumerate("XYZ"):
            self.table.item(index, self.COLUMN_NUMBERS[ax]).setText(texts[i])

    @_misc.multiitemsable
    @_misc.sliceable
    def __delitem__(self, index):
        self[index] = None

    def __array__(self):
        return np.array([(np.nan,) * 3 if i is None else i for i in self[:]])

    def save(self):
        options = dict(
            caption="Save points .csv file",
            directory=str(self.default_save_name()),
            filter="Basic Spreadsheet (*.csv)",
        )

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, **options)
        self._save(path)

    def _save(self, path):
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(_csv_io.writes(np.array(self), names=self.names))

    def default_save_name(self):
        return ""

    def _filter_itemSelectionChanged(self):
        if not self._suppress_itemSelectionChanged:
            self.itemSelectionChanged.emit()

    def cut(self):
        self.copy()
        self.delete()

    def copy(self):
        points = self[self.highlighted_rows()]
        csv = "\n".join("\t".join(map(str, row or [''] * 3)) for row in points)
        pyperclip.copy(csv)

    def paste(self):
        text = pyperclip.paste()
        if not text:
            return
        points = _csv_io.parse_points(text)
        if points is None:
            return
        start = self.highlighted_rows()[0]
        for (i, point) in zip(range(start, len(self)), points):
            self[i] = point
        self.landmarks_changed.emit(np.array(self))


if __name__ == "__main__":
    from pangolin import Palmer

    self = LandmarkTable(Palmer.range())
    self.show()

    for i in range(3, 7):
        self[i] = np.random.random(3)

    app.exec_()
