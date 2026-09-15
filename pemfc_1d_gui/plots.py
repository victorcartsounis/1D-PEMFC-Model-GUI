"""Matplotlib figures embedded in the window.

The figures themselves are built by ``pemfc_1d.postprocessing`` -- the same code
``run_example.py`` calls -- so what the window shows and what lands in the run
directory are the same picture. They are only wrapped in a Qt canvas here.

The backend is forced to Agg before pyplot is imported. ``postprocessing``
builds its figures through ``plt.subplots``, and under an interactive backend
that would quietly create a second set of top-level windows behind the
application; under Agg it creates nothing, and ``FigureCanvasQTAgg`` then
attaches the figure to a widget that lives in the layout.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402 - must follow the backend choice
import numpy as np  # noqa: E402
from matplotlib.backends.backend_qtagg import \
    FigureCanvasQTAgg  # noqa: E402
from matplotlib.backends.backend_qtagg import \
    NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (QLabel, QSizePolicy, QStackedWidget,  # noqa: E402
                               QVBoxLayout, QWidget)

from pemfc_1d.model import SweepResult  # noqa: E402
from pemfc_1d.postprocessing import (plot_polarization_curve,  # noqa: E402
                                     plot_potentials_and_fluxes)

from . import theme  # noqa: E402

#: Figure file names inside a run directory, matching ``run_example.py``.
FIGURE_FILENAMES = {"potentials": "potentials.png",
                    "fluxes": "fluxes.png",
                    "polarization": "polarization_curve.png"}


def build_figures(result: SweepResult,
                  experimental: np.ndarray | None = None) -> dict[str, Figure]:
    """The three figures of a sweep, keyed as in :data:`FIGURE_FILENAMES`.

    ``postprocessing`` names its figures, and ``plt.subplots(num=...)`` returns
    an existing figure of that name instead of a fresh one, so the previous
    run's figures are closed first -- otherwise a second run would draw on top
    of the first. Callers must therefore have called ``FigureView.clear()`` on
    any view still showing those figures before getting here.
    """
    plt.close("all")
    potentials, fluxes = plot_potentials_and_fluxes(result)
    polarization = plot_polarization_curve(result)
    if experimental is not None and len(experimental):
        overlay_experimental(polarization, experimental)
    return {"potentials": potentials, "fluxes": fluxes,
            "polarization": polarization}


def overlay_experimental(figure: Figure, data: np.ndarray) -> None:
    """Draw imported measurements over a polarization curve.

    ``data`` is an (n, 2) array of current density [A/cm^2] and cell voltage
    [V]. The overlay is a visual comparison only: no agreement metric is
    computed, because deciding what counts as agreement -- and over which
    region of the curve -- is a modelling question this build does not answer.
    """
    axis = figure.axes[0]
    axis.plot(data[:, 0], data[:, 1], "k^", markersize=5, linestyle="none",
              markerfacecolor="none", label="Imported data")
    axis.set_xlim(0, max(axis.get_xlim()[1], float(data[:, 0].max()) * 1.05))
    handles, labels = axis.get_legend_handles_labels()
    axis.legend(handles, labels, loc="lower left", fontsize=8)


class FigureView(QWidget):
    """One embedded figure, with the standard matplotlib toolbar."""

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        self._placeholder = QLabel(placeholder)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        self._stack.addWidget(self._placeholder)
        self._layout.addWidget(self._stack)

        self._canvas: FigureCanvasQTAgg | None = None
        self._toolbar: NavigationToolbar2QT | None = None
        self._holder: QWidget | None = None
        self.refresh_theme()

    def refresh_theme(self) -> None:
        """Restyle for the current palette.

        The figure itself is left alone deliberately. It is drawn by
        ``postprocessing`` and saved to the run directory, so restyling it for
        a dark interface would make the file on disk differ from the one
        ``run_example.py`` writes. Instead the plot keeps its white ground and
        is presented as a sheet of paper sitting on the dark surface.
        """
        palette = theme.active()
        self._placeholder.setStyleSheet(
            f"color: {palette.text_muted}; padding: 36px; "
            f"background: transparent;")
        if self._holder is not None:
            self._holder.setStyleSheet(_PAPER_STYLE)

    def set_figure(self, figure: Figure) -> None:
        """Replace whatever is shown with ``figure``."""
        self._drop_canvas()
        canvas = FigureCanvasQTAgg(figure)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Expanding)
        toolbar = NavigationToolbar2QT(canvas, self)

        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(canvas, 1)

        holder.setStyleSheet(_PAPER_STYLE)
        self._stack.addWidget(holder)
        self._stack.setCurrentWidget(holder)
        self._canvas, self._toolbar, self._holder = canvas, toolbar, holder
        canvas.draw_idle()

    def clear(self) -> None:
        """Go back to showing the placeholder."""
        self._drop_canvas()
        self._stack.setCurrentWidget(self._placeholder)

    def _drop_canvas(self) -> None:
        if self._holder is None:
            return
        self._stack.removeWidget(self._holder)
        self._holder.deleteLater()
        self._canvas = self._toolbar = self._holder = None


#: The figures keep matplotlib's white ground so that what is displayed and
#: what is saved are the same picture, so in a dark interface they are framed
#: as a sheet of paper rather than left to float.
_PAPER_STYLE = "QWidget { background: #ffffff; border-radius: 8px; }"
