"""The Help > About dialog.

Split out of the window because it is the one place the project's authorship,
its sources and its contact details are stated, and those are worth keeping
somewhere findable rather than buried in a window three hundred lines long.

The dialog is a plain ``QLabel`` rather than ``QMessageBox.about`` so that the
links in it are actually clickable: the message box renders rich text but does
not open external links unless its label is reconfigured afterwards.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QVBoxLayout,
                               QWidget)

from mmm1d import __version__ as model_version

# --- Authorship and contact --------------------------------------------------
AUTHOR = "Victor Constantin Cartsounis"
INSTITUTION = "CEFET-MG"
SUPERVISOR = "Sidney Nicodemos da Silva"

GITHUB_USER = "victorcartsounis"
GITHUB_PROFILE = f"https://github.com/{GITHUB_USER}"
REPOSITORY = f"{GITHUB_PROFILE}/1D-PEMFC-Model"

#: Shown with the usual Brazilian grouping; the link carries the bare digits,
#: which is what a dialler expects.
PHONE_DISPLAY = "+55 31 99893-1400"
PHONE_LINK = "tel:+5531998931400"

# --- Sources -----------------------------------------------------------------
PAPER_DOI = "https://doi.org/10.1016/j.cpc.2018.07.023"
REFERENCE_IMPLEMENTATION = \
    "https://github.com/Isomorph-Electrochemical-Cells/PEMFC-1DMMM"


def about_html(window_title: str) -> str:
    """The body of the dialog."""
    return f"""
<h2 style='margin-bottom:2px'>{window_title}</h2>
<p style='color:#555; margin-top:0'>mmm1d {model_version}</p>

<p>A one-dimensional, steady-state, non-isothermal, two-phase,
macro-homogeneous membrane electrode assembly model for polymer electrolyte
membrane fuel cells.</p>

<p>This window only configures and displays the model. Every number it shows
comes from the same code <code>run_example.py</code> runs, and each run is
written to disk in the same layout.</p>

<h3 style='color:#1d4ed8; margin-bottom:2px'>Author</h3>
<p style='margin-top:0'>
<b>{AUTHOR}</b><br>
{INSTITUTION} &mdash; written as the codebase for a master's thesis,<br>
supervised by {SUPERVISOR}.
</p>
<table cellpadding='2' cellspacing='0'>
<tr><td style='color:#555'>GitHub&nbsp;&nbsp;</td>
    <td><a href='{GITHUB_PROFILE}'>{GITHUB_USER}</a></td></tr>
<tr><td style='color:#555'>Repository&nbsp;&nbsp;</td>
    <td><a href='{REPOSITORY}'>{GITHUB_USER}/1D-PEMFC-Model</a></td></tr>
<tr><td style='color:#555'>Phone&nbsp;&nbsp;</td>
    <td><a href='{PHONE_LINK}'>{PHONE_DISPLAY}</a></td></tr>
</table>

<h3 style='color:#1d4ed8; margin-bottom:2px'>Physics reference</h3>
<p style='margin-top:0'>R. Vetter and J. O. Schumacher, <i>Free open reference
implementation of a two-phase PEM fuel cell model</i>,
Comput. Phys. Commun. <b>234</b> (2019) 223-234.<br>
<a href='{PAPER_DOI}'>{PAPER_DOI}</a></p>
<p>The authors' MATLAB reference implementation, published alongside the paper,
was consulted during development:<br>
<a href='{REFERENCE_IMPLEMENTATION}'>{REFERENCE_IMPLEMENTATION}</a></p>

<p style='color:#555'>Released under the BSD-3-Clause license. Cite the paper
above for the model formulation, and this repository for the implementation.</p>
"""


class AboutDialog(QDialog):
    """Who wrote this, what it implements, and how to get in touch."""

    def __init__(self, window_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {window_title}")
        self.setMinimumWidth(520)

        body = QLabel(about_html(window_title))
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setOpenExternalLinks(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(body)
        layout.addSpacing(6)
        layout.addWidget(buttons)
