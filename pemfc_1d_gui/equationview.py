"""The panel that renders a layer's or a transport process's equations.

A ``QTextBrowser`` does the layout; the maths is rasterised by
:mod:`pemfc_1d_gui.mathrender` and registered as document resources, so an
equation is written into the HTML as a plain ``<img>`` and flows with the text.
"""
from __future__ import annotations

import html

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPixmap, QTextDocument
from PySide6.QtWidgets import QTextBrowser, QWidget

from pemfc_1d.state import Quantity, Region

from . import theme
from .equations import (LAYER_DOCS, TRANSPORT_DOCS, EquationGroup, LayerDoc,
                        TransportDoc, groups_for_quantity)
from .mathrender import logical_size, render_math

#: Point size the equations are rendered at.
EQUATION_FONT_SIZE = 12.5


class EquationView(QTextBrowser):
    """Shows the governing equations of whatever the diagram has selected.

    Equations are supplied to the document through :meth:`loadResource` rather
    than ``QTextDocument.addResource``: ``setHtml`` clears the document, and
    with it any resource registered beforehand, so the pixmaps have to be
    handed over on demand as the document lays the page out.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self._pixmaps: dict[str, QPixmap] = {}
        self._last: tuple[str, object] = ("overview", None)
        self.show_overview()

    def refresh_theme(self) -> None:
        """Redraw the current page in the new palette.

        The equations are rasterised in the text colour, so a palette change
        means re-rendering them rather than restyling: the page that is open
        is simply built again.
        """
        kind, value = self._last
        if kind == "layer":
            self.show_layer(value)
        elif kind == "transport":
            self.show_transport(value)
        else:
            self.show_overview()

    def loadResource(self, resource_type: int, name: QUrl):  # noqa: N802
        """Hand the document a rendered equation, by the URL in its img tag."""
        if resource_type == int(QTextDocument.ResourceType.ImageResource):
            pixmap = self._pixmaps.get(name.toString())
            if pixmap is not None:
                return pixmap
        return super().loadResource(resource_type, name)

    # ----------------------------------------------------------- public API
    def show_overview(self) -> None:
        """The landing page, shown before anything has been clicked."""
        self._last = ("overview", None)
        self._pixmaps.clear()
        body = [
            "<h2>Membrane electrode assembly</h2>",
            "<p>The model resolves eight coupled quantities across the five "
            "layers of the MEA. Each obeys a second-order transport equation, "
            "written as a potential/flux pair &mdash; a constitutive law for "
            "the flux and a balance for its divergence &mdash; which gives 16 "
            "first-order equations per layer and 80 in total.</p>",
            "<p><b>Click a layer</b> in the diagram above for the equations "
            "that govern it, or <b>one of the eight processes</b> beneath it "
            "to follow that process across the whole cell.</p>",
            "<table cellpadding='5' cellspacing='0' width='100%'>",
            "<tr><td><b>Layer</b></td><td><b>Resolves</b></td></tr>",
        ]
        for region in Region:
            doc = LAYER_DOCS[region]
            names = ", ".join(_QUANTITY_LABELS[q] for q in doc.quantities)
            body.append(
                f"<tr><td valign='top'><b>{doc.name}</b><br>"
                f"<span style='color:{theme.active().text_muted}'>"
                f"{html.escape(doc.subtitle)}</span>"
                f"</td><td valign='top'>{names}</td></tr>")
        body.append("</table>")
        self._render(body)

    def show_layer(self, region: Region) -> None:
        """The equations of one MEA layer."""
        self._last = ("layer", region)
        self._pixmaps.clear()
        doc = LAYER_DOCS[region]
        body = [
            f"<h2>{html.escape(doc.name)} &mdash; "
            f"{html.escape(doc.subtitle)}</h2>",
            f"<p>{html.escape(doc.description)}</p>",
            _quantity_chips(doc),
        ]
        for group in doc.groups:
            body.extend(self._group_html(group))
        body.extend(_caveats_html(doc.caveats))
        self._render(body)

    def show_transport(self, row: int) -> None:
        """One transport process, followed layer by layer."""
        self._last = ("transport", row)
        self._pixmaps.clear()
        doc: TransportDoc = TRANSPORT_DOCS[row]
        body = [
            f"<h2>{html.escape(doc.title)}</h2>",
            f"<p>{html.escape(doc.description)}</p>",
        ]
        if doc.note:
            body.append(_note_html(doc.note))

        regions = ", ".join(LAYER_DOCS[r].name for r in doc.regions)
        body.append(f"<p style='color:{theme.active().text_muted}'>"
                    f"<b>Resolved in:</b> {regions}</p>")

        for layer_doc, group in groups_for_quantity(doc.quantity):
            palette = theme.active()
            body.append(
                f"<h3 style='color:{palette.accent}'>"
                f"{html.escape(layer_doc.name)}"
                f"<span style='color:{palette.text_muted}; "
                f"font-weight:normal'> &nbsp;"
                f"{html.escape(layer_doc.subtitle)}</span></h3>")
            body.extend(self._group_html(group, heading=False))
        self._render(body)

    # -------------------------------------------------------------- helpers
    def _group_html(self, group: EquationGroup, heading: bool = True) -> list[str]:
        parts = []
        if heading:
            parts.append(f"<h3 style='color:{theme.active().accent}'>"
                         f"{html.escape(group.title)}</h3>")
        for equation in group.equations:
            parts.append(self._equation_html(equation.latex))
            if equation.caption:
                parts.append(
                    f"<p style='margin-left:24px; margin-top:0; "
                    f"color:{theme.active().text_muted}'>"
                    f"<i>{html.escape(equation.caption)}</i></p>")
        if group.note:
            parts.append(_note_html(group.note))
        return parts

    def _equation_html(self, latex: str) -> str:
        """Rasterise one equation and reference it by a private URL."""
        try:
            pixmap = render_math(latex, EQUATION_FONT_SIZE, _text_color(self))
        except Exception:
            # A broken font cache should degrade to readable source, not crash.
            return (f"<pre style='margin-left:24px; "
                    f"color:{theme.active().text}'>"
                    f"{html.escape(latex)}</pre>")

        name = f"eqimg:{len(self._pixmaps)}"
        self._pixmaps[name] = pixmap
        width, height = logical_size(pixmap)
        return (f"<p style='margin-left:24px; margin-bottom:2px'>"
                f"<img src='{name}' width='{width}' height='{height}'></p>")

    def _render(self, body: list[str]) -> None:
        self.setHtml(f"<div style='font-size:10.5pt'>{''.join(body)}</div>")
        self.verticalScrollBar().setValue(0)


_QUANTITY_LABELS: dict[Quantity, str] = {
    Quantity.PHI_E: "electron potential",
    Quantity.PHI_P: "proton potential",
    Quantity.T: "temperature",
    Quantity.LAMBDA: "dissolved water",
    Quantity.W_H2O: "water vapour",
    Quantity.W_O2: "oxygen",
    Quantity.SATURATION: "liquid water",
    Quantity.P_GAS: "gas pressure",
}


def _quantity_chips(doc: LayerDoc) -> str:
    palette = theme.active()
    chips = "".join(
        f"<span style='background:{palette.accent_wash}; "
        f"color:{palette.accent}; padding:2px 7px'>"
        f"&nbsp;{_QUANTITY_LABELS[q]}&nbsp;</span>&nbsp;"
        for q in doc.quantities)
    return (f"<p style='color:{palette.text_muted}'><b>Resolves "
            f"{len(doc.quantities)} of the 8 quantities:</b><br>{chips}</p>")


def _note_html(text: str) -> str:
    palette = theme.active()
    return (f"<p style='margin-left:24px; background:{palette.surface_alt}; "
            f"padding:7px 10px; color:{palette.text_muted}'>"
            f"{html.escape(text)}</p>")


def _caveats_html(caveats: tuple[str, ...]) -> list[str]:
    if not caveats:
        return []
    palette = theme.active()
    parts = [f"<h3 style='color:{palette.warning}'>Active simplifications</h3>",
             f"<p style='color:{palette.text_muted}'>Behaviour of this version "
             f"of the model that the equations above do not show on their "
             f"own:</p>",
             "<ul>"]
    parts += [f"<li style='margin-bottom:6px'>{html.escape(c)}</li>"
              for c in caveats]
    parts.append("</ul>")
    return parts


def _text_color(widget: QWidget) -> str:
    """Hex colour the equations should be drawn in, from the current palette."""
    return widget.palette().windowText().color().name()
