import json
import shutil
from pathlib import Path
import re
import functools
import contextlib

import appdirs
import strictyaml
from PyQt5 import QtWidgets, QtCore
from pangolin import JawType

from tomial_clicky_tooth._landmark_templates import LandmarksTemplate, \
    ParseError

CACHE = Path(appdirs.user_cache_dir("tomial_clicky_tooth"))
CACHE.mkdir(parents=True, exist_ok=True)


class LandmarksSelector(QtWidgets.QWidget):
    _cache_path = CACHE / "state.json"

    def __init__(self):
        super().__init__()
        self.setLayout(QtWidgets.QHBoxLayout())

        self.template_selection = QtWidgets.QComboBox()
        self._repopulate()
        self.template_selection.activated.connect(self._state_change)

        self.adult = QtWidgets.QRadioButton("Adult")
        self.deciduous = QtWidgets.QRadioButton("Primary")
        self.upper = QtWidgets.QRadioButton("Maxilla")
        self.lower = QtWidgets.QRadioButton("Mandible")

        _ = QtWidgets.QButtonGroup(self)
        _.addButton(self.upper)
        _.addButton(self.lower)

        _ = QtWidgets.QButtonGroup(self)
        _.addButton(self.adult)
        _.addButton(self.deciduous)

        grid = QtWidgets.QGridLayout()
        self.layout().addWidget(self.template_selection)
        self.layout().addLayout(grid)
        grid.addWidget(self.upper, 0, 0)
        grid.addWidget(self.lower, 1, 0)
        grid.addWidget(self.adult, 0, 1)
        grid.addWidget(self.deciduous, 1, 1)

        try:
            state = json.loads(self._cache_path.read_bytes())
        except:
            state = {}
        self.state = state

        self.upper.toggled.connect(self._state_change)
        self.adult.toggled.connect(self._state_change)

    def _repopulate(self):
        template = self.template_selection.currentText()
        self.template_selection.clear()
        self.paths = {i.stem: i for i in Path(__file__).parent.glob("*.yaml")}
        self.paths.update({i.stem: i for i in CACHE.glob("*.yaml")})
        for (i, name) in enumerate(sorted(self.paths)):
            yaml = self.paths[name].read_text(encoding="utf-8")
            description = strictyaml.load(yaml).data.get("description")
            self.template_selection.addItem(name)
            self.template_selection.setItemData(i, description,
                                                QtCore.Qt.ToolTipRole)
        self.template_selection.addItem("Import...")
        self.template_selection.setItemData(i + 1, "Import from YAML file",
                                            QtCore.Qt.ToolTipRole)
        self.template_selection.setCurrentText(template)

    @property
    def primary(self):
        return self.deciduous.isChecked()

    @primary.setter
    def primary(self, state):
        self.deciduous.setChecked(state)
        self.adult.setChecked(not state)

    @property
    def arch_type(self):
        return "UL"[self.lower.isChecked()]

    @arch_type.setter
    def arch_type(self, state):
        self.upper.setChecked(state == "U")
        self.lower.setChecked(state == "L")

    @property
    def template(self):
        return self._template

    @template.setter
    def template(self, x):
        if isinstance(x, str):
            path = self.paths[x]
        else:
            assert isinstance(x, Path)
            path = x

        try:
            template = LandmarksTemplate.from_file(path)
            template.name
        except ParseError as ex:
            self.template_selection.setCurrentText(self._template.name)
            message = re.sub(r"'([^']+)'", r"<code>\1</code>", str(ex))
            QtWidgets.QMessageBox.critical(
                self, "Invalid landmarks template",
                f"The file provided is invalid. {message}")
            self.template_selection.setCurrentText(self._template.name)
            return

        if isinstance(x, Path):
            CACHE.mkdir(parents=True, exist_ok=True)
            shutil.copy(x, CACHE / (x.stem + ".yaml"))
            self._repopulate()
        self.template_selection.setCurrentText(template.name)
        self._template = template

    @functools.cached_property
    def landmarks(self):
        return self.template.evaluate(JawType(self.arch_type, self.primary))

    @property
    def state(self):
        return {
            "primary": self.primary,
            "arch_type": self.arch_type,
            "template": self.template.name
        }

    @state.setter
    def state(self, state):
        self.primary = state.get("primary", False)
        self.arch_type = state.get("arch_type", "L")
        self.template = state.get("template", "Default")
        with contextlib.suppress(AttributeError):
            del self.landmarks

    def _state_change(self):
        if self.template_selection.currentText() == "Import...":
            source, _ = QtWidgets.QFileDialog.getOpenFileName(
                filter="YAML landmarks template file (*.yaml *.yml)")
            if not source:
                self.template_selection.setCurrentText(self.template.name)
                return
            self.template = Path(source)
        else:
            self.template = self.template_selection.currentText()

        CACHE.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self.state), encoding="utf-8")
        try:
            del self.landmarks
        except AttributeError:
            pass
        self.changed.emit(self.landmarks)

    changed = QtCore.pyqtSignal(object)
