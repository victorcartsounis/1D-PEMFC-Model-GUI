"""PySide6 desktop front end for the 1D PEM fuel cell model.

The package is a *view* onto :mod:`mmm1d`: it edits a ``Params`` set, calls
``mmm1d.model.solve`` and the metrics helpers exactly as ``run_example.py``
does, and writes the same ``results/run_YYYYmmdd_HHMMSS/`` directory. Nothing
in :mod:`mmm1d` imports from here, so the solver keeps working with the GUI
absent, and a GUI bug cannot change a number the model produces.

Run it with::

    python run_gui.py
"""
from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """Start the application. Imported lazily so ``import mmm1d_gui`` is cheap."""
    from .app import main as _main
    return _main()
