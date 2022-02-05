import pytest

from tomial_clicky_tooth._csv import parse_points

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
