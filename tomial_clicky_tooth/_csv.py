import io
import csv


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
