import re

import numpy as np
import pytest

from tomial_clicky_tooth._csv import parse_points, read, writes

pytestmark = pytest.mark.order(1)

INVALID_CSVs = [
    "",
    "5 6 7\n1 2",
    "cake",
    "\n123\t456\t789",
    "1 2 3\n\n",
    "10 11 1q",
]


def test_csv_parse():
    assert parse_points("-1 10 2.3\n3 4 1e-3") == [(-1, 10, 2.3), (3, 4, 1e-3)]
    assert parse_points("\t\t\n2\t3\t4") == [None, (2, 3, 4)]
    assert parse_points("-1.2, 2.3, 3.4\n,,") == [(-1.2, 2.3, 3.4), None]
    assert parse_points('"1", "3", "5"') == [(1, 3, 5)]

    for csv in INVALID_CSVs:
        assert parse_points(csv) is None


def test_writes():
    """Test tomial_clicky_tooth._csv.writes() on both NumPy arrays and plain
    lists of tuples."""
    points = [None, (.1, .2, .3)]
    target = "Landmarks,X,Y,Z\n,,,\n,0.1,0.2,0.3\n"
    assert_text_equivalent(writes(points), target)

    points[0] = (np.nan,) * 3
    assert_text_equivalent(writes(points), target)

    names = "foo", "bar"
    target = "Landmarks,X,Y,Z\nfoo,,,\nbar,0.1,0.2,0.3\n"
    assert_text_equivalent(writes(points, names=names), target)


def assert_text_equivalent(x, y):
    """A string equals assertion which ignores mismatching line endings."""
    x, y = (re.sub("\r\n|\r|\n", "\n", i) for i in (x, y))
    assert x == y
