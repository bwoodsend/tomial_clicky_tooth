import io
from pathlib import Path
import re

import pytest
from pangolin import JawType, Palmer

from tomial_clicky_tooth._landmark_templates import LandmarksContext, \
    LandmarksTemplate, LandmarksUndefined, InvalidKey, ParseError

pytestmark = pytest.mark.order(1)


def test_rule_evaluation():
    """Test expansion of () syntax in tooth name rules."""
    self = LandmarksContext(JawType("L"), "R")

    assert self("hello world") == ["Hello world"]
    assert self("(a)(s)(1-2)") == ["LR1", "LR2"]
    assert self("(a)(s)(3-5,8)") == ["LR3", "LR4", "LR5", "LR8"]
    assert self("(A) (S) canine") == ["Lower right canine"]
    assert self("(-3,7-)") == ["1", "2", "3", "7", "8"]

    self = LandmarksContext(JawType(primary=True), "L")
    assert self("(s)(4-)") == ["LD", "LE"]
    assert self("(-)") == ["A", "B", "C", "D", "E"]


def test_asymmetric():
    HERE = Path(__file__).parent

    self = LandmarksTemplate.from_file(HERE / "asymmetric.yaml")
    assert self.evaluate(JawType(arch_type="L")) == [
        "LL5", "LL3", "LL1", "The middle", "LR1", "LR3", "LR5"
    ]
    assert self.evaluate(JawType(arch_type="U")) == [
        "Something on the left", "UR1", "UR2", "UR3", "UR4"
    ]
    with pytest.raises(LandmarksUndefined, match=re.escape(str(JawType()))):
        self.evaluate(JawType())

    self = LandmarksTemplate.from_file(io.StringIO("- '(a)(s)(-)'"))
    assert self.evaluate(JawType(primary=True)) == Palmer.range(primary=True)

    with pytest.raises(InvalidKey, match="'cake' is .* of 'adult', 'primary'"):
        LandmarksTemplate.from_file(io.StringIO("cake:\n  - 'foo'\n"))

    with pytest.raises(InvalidKey,
                       match=r"'cake' \(located at primary->upper->cake\) is "):
        LandmarksTemplate.from_file(
            io.StringIO("""
            primary:
              upper:
                cake:
                  - 'foo'
        """))

    with pytest.raises(ParseError, match="Value at primary should.*not a str."):
        LandmarksTemplate.from_file(io.StringIO("primary: eggs"))
