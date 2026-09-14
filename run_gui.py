"""Graphical entry point: opens the PySide6 window for the model.

The window configures a run, shows what governs each layer of the cell, and
displays the figures; the sweep itself is the same call ``run_example.py``
makes, and writes the same timestamped directory under ``results/``.

Examples
--------
    python run_gui.py
"""
import sys


def main() -> int:
    try:
        from mmm1d_gui import main as run
    except ImportError as error:
        if "PySide6" not in str(error):
            raise
        print("PySide6 is not installed, so the window cannot be opened.\n"
              "Install it with one of:\n"
              "    poetry install --with gui\n"
              "    pip install PySide6-Essentials\n\n"
              "The model itself does not need it: run_example.py works "
              "without PySide6.", file=sys.stderr)
        return 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
