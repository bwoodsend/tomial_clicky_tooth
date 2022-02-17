import io
import csv
from pathlib import Path
import math


def parse_points(text):
    """Parse 3D points from a comma separated value formatted table.

    This function is deliberately fussy about the input. Only an n x 3
    table with rows of either 3 empty cells of 3 floats. No metadata rows or
    columns are allowed.

    If any of the above conditions are not satisfied then `None` is returned
    silently.

    """
    try:
        dialect = csv.Sniffer().sniff(text)
    except csv.Error:
        return
    reader = csv.reader(io.StringIO(text), dialect)

    points = []
    for point in reader:
        if point == ["", "", ""]:
            points.append(None)
        elif len(point) == 3 and all(point):
            try:
                points.append(tuple(map(float, point)))
            except ValueError:
                return
        else:
            return

    return points


def read(path):
    """Read a landmarks CSV file."""
    text = Path(path).read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text))

    points = []
    for (i, (name, *point)) in enumerate(reader):
        if i == 0 and all(i.isalpha() for i in point):
            continue
        try:
            point = tuple(map(float, point))
            if len(point) != 3:
                point = None
        except ValueError:
            point = None
        points.append(point)

    return points


def writes(points, *, names=None):
    """Serialise landmarks and their names to a landmarks CSV file."""
    if names is None:
        names = [""] * len(points)

    file = io.StringIO()
    writer = csv.writer(file)
    writer.writerow(("Landmarks", "X", "Y", "Z"))
    for (name, point) in zip(names, points):
        if point is None:
            point = ("", "", "")
        elif any(map(math.isnan, point)):
            point = ("", "", "")
        else:
            point = (str(i) for i in point)
        writer.writerow((name, *point))

    return file.getvalue()
