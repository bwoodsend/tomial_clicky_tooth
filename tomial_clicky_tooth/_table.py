from textwrap import wrap

import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth import _misc


class _QTable(QtWidgets.QTableWidget):

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


def button(callback):
    name = callback.__name__.replace("_", " ").strip().title()
    out = QtWidgets.QPushButton(name)
    out.released.connect(callback)
    return out


class LandmarkTable(QtWidgets.QWidget):

    COLUMNS = ["Name", "X", "Y", "Z"]
    COLUMN_NUMBERS = {name: i for (i, name) in enumerate(COLUMNS)}

    def __init__(self, names, parent=None):
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
        buttons_layout = QtWidgets.QGridLayout()
        self.box.addLayout(buttons_layout)

        self.shift_up_button = button(self.shift_selected_up)
        self.shift_down_button = button(self.shift_selected_down)
        self.delete_button = button(self.delete_selected)
        self.clear_all_button = button(self.clear_all)
        self.save_button = button(self.save)

        for (i, _button) in enumerate([
                self.shift_up_button,
                self.delete_button,
                self.save_button,
                self.shift_down_button,
                self.clear_all_button,
        ]):
            buttons_layout.addWidget(_button, *divmod(i, 3))
        self.delete_button.setShortcut(QtCore.Qt.Key_Delete)

    @property
    def shape(self):
        return self.table.rowCount(), self.table.columnCount()

    def load_table_contents(self, names):
        self.table.setRowCount(len(names))

        self.items = np.empty(self.shape, object)

        for (i, name) in enumerate(names):
            for j in range(len(self.COLUMNS)):
                self.table.setItem(i, j, QtWidgets.QTableWidgetItem(""))

            wrapped = wrap(str(name), 30)
            cell = QtWidgets.QTableWidgetItem("\n".join(wrapped))
            self.table.setItem(i, 0, cell)

        self.update_sizes()

    def clear_all(self):
        del self[:]
        self.landmarks_changed.emit(np.array(self))

    def delete_selected(self):
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

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, **options)
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
