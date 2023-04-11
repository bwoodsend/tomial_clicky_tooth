from pathlib import Path

import pytest

from tomial_clicky_tooth._qapp import app
from tomial_clicky_tooth._landmark_selector import LandmarksSelector
from tests import select_file, ChooseMessageBoxButton, reset

pytestmark = pytest.mark.order(2)


def test_persistence():
    reset()
    self = LandmarksSelector()
    self.show()

    assert not self.primary
    assert self.arch_type == "L"
    assert self.template.name == "Default"

    self._state_change()
    assert not self.primary
    assert self.arch_type == "L"
    assert self.template.name == "Default"

    self.upper.click()
    assert self.arch_type == "U"
    assert not self.lower.isChecked()
    assert self.adult.isChecked()

    self.deciduous.click()
    assert self.primary
    self.template_selection.setCurrentText("MHB")
    self.template_selection.activated.emit(0)
    assert self.template.name == "MHB"
    self.close()

    self = LandmarksSelector()
    self.show()
    assert self.primary
    assert self.arch_type == "U"
    assert self.template.name == "MHB"


def _combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_template_import():
    reset()
    self = LandmarksSelector()
    self.show()

    asymmetric = Path(__file__).with_name("asymmetric.yaml")
    with select_file(asymmetric):
        self.template_selection.setCurrentText("Import...")
        self.template_selection.activated.emit(0)
    assert "asymmetric" in _combo_items(self.template_selection)
    assert self.template_selection.currentText() == "asymmetric"
    assert self.template.name == "asymmetric"

    invalid = Path(__file__).with_name("invalid.yml")
    with select_file(invalid):
        with ChooseMessageBoxButton("OK"):
            self.template_selection.setCurrentText("Import...")
            self.template_selection.activated.emit(0)
    assert self.template.name == "asymmetric"
    assert self.template_selection.currentText() == "asymmetric"
    assert "invalid" not in _combo_items(self.template_selection)

    nameless = Path(__file__).with_name("nameless.yml")
    with select_file(nameless):
        with ChooseMessageBoxButton("OK"):
            self.template_selection.setCurrentText("Import...")
            self.template_selection.activated.emit(0)
    assert self.template.name == "asymmetric"
    assert self.template_selection.currentText() == "asymmetric"
    assert "invalid" not in _combo_items(self.template_selection)

    old = _combo_items(self.template_selection)
    with select_file(None):
        self.template_selection.setCurrentText("Import...")
        self.template_selection.activated.emit(0)
    assert self.template.name == "asymmetric"
    assert self.template_selection.currentText() == "asymmetric"
    assert _combo_items(self.template_selection) == old
