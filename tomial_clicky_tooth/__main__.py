import sys
from pathlib import Path

from pangolin import Palmer

from tomial_clicky_tooth._ui import main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        csv_path = path.with_suffix(".csv")
        if not csv_path.exists():
            csv_path = None
    else:
        csv_path = path = None

    self = main(Palmer.range(), path, csv_path)
