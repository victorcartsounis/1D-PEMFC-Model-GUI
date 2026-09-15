"""PySide6 desktop front end for the 1D PEM fuel cell model.

The package is a *view* onto :mod:`pemfc_1d`, which is a separate project
installed as a dependency: this edits a ``Params`` set, calls ``pemfc_1d.solve``
and the metrics helpers exactly as that package's own command-line runner does,
and writes the same ``results/run_YYYYmmdd_HHMMSS/`` directory. Nothing in
:mod:`pemfc_1d` imports from here -- it does not know this exists -- so the
solver keeps working with the interface absent, and a bug in this window cannot
change a number the model produces.

The names it is entitled to import are the ones :mod:`pemfc_1d` exports; the
model's own ``tests/test_public_api.py`` pins that list.

Run it with::

    pemfc-1d-gui
"""
from __future__ import annotations

__version__ = "0.3.0"

__all__ = ["main", "__version__"]


def main() -> int:
    """Start the application. Imported lazily so ``import pemfc_1d_gui`` is cheap."""
    from .app import main as _main
    return _main()
