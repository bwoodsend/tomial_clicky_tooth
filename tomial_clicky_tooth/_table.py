from textwrap import wrap

import numpy as np
from PyQt5.QtWidgets import (
    QApplication,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QFileDialog,
)
from PyQt5 import QtWidgets, QtGui, QtCore

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth import _misc


class _QTable(QTableWidget):

    def keyPressEvent(self, event):
        if event.modifiers() == QtCore.Qt.NoModifier:
            if event.key() == QtCore.Qt.Key_Left:
                event.ignore()
            elif event.key() == QtCore.Qt.Key_Right:
                event.ignore()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


class LandmarkTable(QWidget):

    COLUMNS = ["Name", "X", "Y", "Z"]
    COLUMN_NUMBERS = {name: i for (i, name) in enumerate(COLUMNS)}

    def __init__(self, names=(), parent=None):
        self.names = names
        super().__init__(parent)

        self.table = table = _QTable()
        self.points = {}

        self.box = QtWidgets.QVBoxLayout()
        self.setLayout(self.box)
        self.box.addWidget(table)

        policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                       QtWidgets.QSizePolicy.Minimum)
        self.setSizePolicy(policy)
        self.setFixedWidth(500)

        self.font = QtGui.QFont()
        self.font.setPixelSize(16)
        self.table.setFont(self.font)

        self.setup_buttons()

        table.setColumnCount(len(self.COLUMNS))
        table.setHorizontalHeaderLabels(self.COLUMNS)
        table.setSizeAdjustPolicy(
            QtWidgets.QAbstractScrollArea.AdjustToContents)
        table.setSelectionBehavior(table.SelectRows)

        self.load_table_contents(names)
        self.table.itemChanged.connect(self.update_sizes)

        self._suppress_itemSelectionChanged = False
        self.table.itemSelectionChanged.connect(
            self._filter_itemSelectionChanged)

        self.increment_focus()

    def setup_buttons(self):
        self.buttons_layout = QtWidgets.QGridLayout()
        self.box.addLayout(self.buttons_layout)

        button_names = [
            "Shift Selected Up",
            "Delete Marker(s)",
            "Clear all",
            "Shift Selected Down",
            "Save points",
        ]

        callbacks = [lambda: None] * 5
        callbacks[0] = self.shift_selected_up
        callbacks[3] = self.shift_selected_down
        callbacks[4] = self.save

        self.buttons = {}
        for (i, name) in enumerate(button_names):
            button = QtWidgets.QPushButton(name, self.table)
            button.pressed.connect(callbacks[i])
            self.buttons_layout.addWidget(button, *divmod(i, 3))
            self.buttons[name] = button
        self.buttons[button_names[1]].setShortcut(QtCore.Qt.Key_Delete)

    @property
    def shape(self):
        return self.table.rowCount(), self.table.columnCount()

    def load_table_contents(self, names):
        self.table.setRowCount(len(names))

        self.items = np.empty(self.shape, object)

        for (i, name) in enumerate(names):
            for j in range(len(self.COLUMNS)):
                self.table.setItem(i, j, QTableWidgetItem(""))

            wrapped = wrap(str(name), 30)
            self.table.setItem(i, 0,
                               QtWidgets.QTableWidgetItem("\n".join(wrapped)))

        self.update_sizes()

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

    def update_sizes(self):
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

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

        path, _ = QFileDialog.getSaveFileName(self, **options)
        if path:
            excel_io.write_points(path, np.array(self), self.names)

    def default_save_name(self):
        return ""

    def shift_selected(self, args, places=1):
        self._suppress_itemSelectionChanged = True

        args = np.asarray(args)[::-np.sign(places)]
        vals = [self[i] for i in args]
        for i in args:
            del self[i]

        new_args = args + places
        for (xyz, i) in zip(vals, new_args):
            if 0 <= i < self.shape[0]:
                self[i] = xyz

        model = self.table.selectionModel()
        indices = model.selectedIndexes()

        for index in indices:
            model.select(index, model.Deselect)

        for index in indices:
            new_index = model.model().index(index.row() + places,
                                            index.column())
            model.select(new_index, model.Select)


#        for (i, j) in zip(args, new_args):
#            if 0 <= j < self.shape[0]:
#                self.rename_cb(i, j)
#            else:
#                self.remove_cb(i)
        self.landmarks_changed.emit(np.array(self))

        self._suppress_itemSelectionChanged = False
        self.table.itemSelectionChanged.emit()

    def _filter_itemSelectionChanged(self):
        if not self._suppress_itemSelectionChanged:
            self.itemSelectionChanged.emit()

    def shift_selected_up(self):
        self.shift_selected(self.highlighted_rows(), -1)

    def shift_selected_down(self):
        self.shift_selected(self.highlighted_rows(), 1)

if __name__ == "__main__":
    from pangolin import Palmer

    self = LandmarkTable(Palmer.range())
    self.show()

    for i in range(3, 7):
        self[i] = np.random.random(3)

    app.exec_()
