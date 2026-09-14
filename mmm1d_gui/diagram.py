"""The MEA cross-section, drawn from the model's own geometry.

This is an original drawing rather than a bitmap, which buys three things the
project needs: it is the repository's own work rather than a figure lifted
from the reference paper, it redraws itself from ``Params.L`` so the picture is
of the cell actually configured, and it scales and re-themes without a second
asset.

The one liberty taken with the geometry is the horizontal scale. Drawn true to
size the catalyst layers would be a sixteenth the width of the diffusion
layers and effectively invisible, so layer widths are compressed through
:data:`WIDTH_COMPRESSION` -- thicker layers still read as thicker, but every
layer stays wide enough to label and to click. Each layer prints its true
thickness, and the ruler underneath is drawn to the real scale, so nothing is
misrepresented.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetricsF, QPainter,
                           QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import QSizePolicy, QWidget

from mmm1d.params import Params
from mmm1d.state import Region

from . import theme

#: Exponent applied to layer thickness to get drawn width. 1.0 would be true
#: to scale and illegible; 0 would make every layer equal and throw away the
#: information that the diffusion layers are much the thicker.
WIDTH_COMPRESSION = 0.34

#: Fraction of the widget's height the cell body occupies.
BODY_TOP, BODY_BOTTOM = 0.17, 0.74

#: Space either side of the cell for the gas channel labels and arrows.
GUTTER = 64.0


@dataclass(frozen=True)
class LayerStyle:
    """How one layer is drawn and what it is called."""

    name: str
    full_name: str
    line: str    # attribute on the palette for the outline
    fill: str    # attribute on the palette for the interior


LAYER_STYLES: dict[Region, LayerStyle] = {
    Region.AGDL: LayerStyle("AGDL", "Anode gas diffusion layer",
                            "gdl", "gdl_fill"),
    Region.ACL: LayerStyle("ACL", "Anode catalyst layer",
                           "catalyst", "catalyst_fill"),
    Region.PEM: LayerStyle("PEM", "Polymer electrolyte membrane",
                           "membrane", "membrane_fill"),
    Region.CCL: LayerStyle("CCL", "Cathode catalyst layer",
                           "catalyst", "catalyst_fill"),
    Region.CGDL: LayerStyle("CGDL", "Cathode gas diffusion layer",
                            "gdl", "gdl_fill"),
}


class MEADiagram(QWidget):
    """A clickable cross-section of the membrane electrode assembly."""

    #: A layer was clicked; carries the ``Region`` value.
    layerClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._params = Params()
        self._hovered: Region | None = None
        self._selected: Region | None = None
        self.setMouseTracking(True)
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        self.setToolTip("Click a layer for the equations that govern it.")

    # ---------------------------------------------------------------- state
    def set_params(self, params: Params) -> None:
        """Redraw for a different cell geometry."""
        self._params = params
        self.update()

    def select(self, region: Region | None) -> None:
        self._selected = region
        self.update()

    def refresh_theme(self) -> None:
        self.update()

    # --------------------------------------------------------------- layout
    def _widths(self) -> np.ndarray:
        """Drawn width of each layer, as a fraction of the cell body."""
        compressed = np.asarray(self._params.L, dtype=float) ** WIDTH_COMPRESSION
        return compressed / compressed.sum()

    def _body_rect(self) -> QRectF:
        top = self.height() * BODY_TOP
        bottom = self.height() * BODY_BOTTOM
        return QRectF(GUTTER, top, max(1.0, self.width() - 2 * GUTTER),
                      max(1.0, bottom - top))

    def _layer_rects(self) -> dict[Region, QRectF]:
        body = self._body_rect()
        rects: dict[Region, QRectF] = {}
        x = body.left()
        for region, fraction in zip(Region, self._widths()):
            width = body.width() * float(fraction)
            rects[region] = QRectF(x, body.top(), width, body.height())
            x += width
        return rects

    def _layer_at(self, position: QPointF) -> Region | None:
        for region, rect in self._layer_rects().items():
            if rect.contains(position):
                return region
        return None

    # --------------------------------------------------------------- events
    def mouseMoveEvent(self, event) -> None:  # noqa: D102 - Qt override
        hovered = self._layer_at(event.position())
        if hovered != self._hovered:
            self._hovered = hovered
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor if hovered
                                   is not None else Qt.CursorShape.ArrowCursor))
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: D102 - Qt override
        if self._hovered is not None:
            self._hovered = None
            self.unsetCursor()
            self.update()

    def mousePressEvent(self, event) -> None:  # noqa: D102 - Qt override
        if event.button() != Qt.MouseButton.LeftButton:
            return
        region = self._layer_at(event.position())
        if region is None:
            return
        self._selected = region
        self.update()
        self.layerClicked.emit(int(region))

    # -------------------------------------------------------------- drawing
    def paintEvent(self, event) -> None:  # noqa: D102 - Qt override
        palette = theme.active()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        self._draw_background(painter, palette)
        rects = self._layer_rects()
        self._draw_electrode_spans(painter, palette, rects)
        for region, rect in rects.items():
            self._draw_layer(painter, palette, region, rect)
        self._draw_channels(painter, palette)
        self._draw_ruler(painter, palette, rects)

    def _draw_background(self, painter: QPainter, p: theme.Palette) -> None:
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                            10, 10)
        painter.fillPath(path, QColor(p.diagram_bg))
        painter.setPen(QPen(QColor(p.border), 1.0))
        painter.drawPath(path)

    def _draw_layer(self, painter: QPainter, p: theme.Palette,
                    region: Region, rect: QRectF) -> None:
        style = LAYER_STYLES[region]
        line = QColor(getattr(p, style.line))
        fill = QColor(getattr(p, style.fill))
        selected = region == self._selected
        hovered = region == self._hovered

        if selected:
            fill = _mix(fill, QColor(p.accent), 0.22)
        elif hovered:
            fill = _mix(fill, QColor(p.accent), 0.10)

        painter.fillRect(rect, fill)
        painter.setPen(QPen(line if selected else QColor(p.border_strong),
                            2.0 if selected else 1.0))
        painter.drawRect(rect)

        if selected:
            painter.setPen(QPen(QColor(p.accent), 2.5))
            painter.drawLine(rect.topLeft() + QPointF(0, 1),
                             rect.topRight() + QPointF(0, 1))

        # Acronym, centred, dropped to a vertical layout when the column is
        # too narrow to take it horizontally.
        painter.setPen(QColor(p.text))
        label_font = QFont(painter.font())
        label_font.setPointSizeF(max(7.5, min(11.0, rect.width() / 4.6)))
        label_font.setBold(True)
        painter.setFont(label_font)

        metrics = QFontMetricsF(label_font)
        if metrics.horizontalAdvance(style.name) <= rect.width() - 6:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, style.name)
        else:
            painter.save()
            painter.translate(rect.center())
            painter.rotate(-90)
            painter.drawText(QRectF(-rect.height() / 2, -rect.width() / 2,
                                    rect.height(), rect.width()),
                             Qt.AlignmentFlag.AlignCenter, style.name)
            painter.restore()

        # True thickness, under the layer.
        thickness = self._params.L[int(region)] * 1e6
        small = QFont(painter.font())
        small.setPointSizeF(8.0)
        small.setBold(False)
        painter.setFont(small)
        painter.setPen(QColor(p.text_muted))
        painter.drawText(QRectF(rect.left() - 12, rect.bottom() + 3,
                                rect.width() + 24, 15),
                         Qt.AlignmentFlag.AlignCenter,
                         _format_thickness(thickness))

    def _draw_electrode_spans(self, painter: QPainter, p: theme.Palette,
                              rects: dict[Region, QRectF]) -> None:
        """The anode and cathode brackets above the cell."""
        font = QFont(painter.font())
        font.setPointSizeF(9.0)
        font.setBold(True)
        painter.setFont(font)

        spans = (("ANODE  ·  H₂ → 2H⁺ + 2e⁻",
                  rects[Region.AGDL].left(), rects[Region.ACL].right()),
                 ("CATHODE  ·  ½O₂ + 2H⁺ + 2e⁻ → H₂O",
                  rects[Region.CCL].left(), rects[Region.CGDL].right()))
        y = rects[Region.AGDL].top() - 9
        for text, left, right in spans:
            painter.setPen(QPen(QColor(p.border_strong), 1.0))
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            painter.drawLine(QPointF(left, y), QPointF(left, y + 5))
            painter.drawLine(QPointF(right, y), QPointF(right, y + 5))
            painter.setPen(QColor(p.text_muted))
            painter.drawText(QRectF(left, y - 21, right - left, 17),
                             Qt.AlignmentFlag.AlignCenter, text)

    def _draw_channels(self, painter: QPainter, p: theme.Palette) -> None:
        """What each gas channel feeds the cell, drawn in the side gutters."""
        body = self._body_rect()
        middle = body.center().y()

        font = QFont(painter.font())
        font.setPointSizeF(8.5)
        font.setBold(False)
        painter.setFont(font)

        for text, direction in (("H\u2082 in", 1), ("air in", -1)):
            if direction > 0:
                label = QRectF(6, middle - 25, body.left() - 14, 15)
                tip = QPointF(body.left() - 7, middle + 3)
            else:
                label = QRectF(body.right() + 8, middle - 25,
                               self.width() - body.right() - 14, 15)
                tip = QPointF(body.right() + 7, middle + 3)

            painter.setPen(QColor(p.text_muted))
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, text)
            painter.setPen(QColor(p.accent))
            _arrow(painter, tip, direction, 12.0)

    def _draw_ruler(self, painter: QPainter, p: theme.Palette,
                    rects: dict[Region, QRectF]) -> None:
        """A true-to-scale bar showing how compressed the drawing is."""
        body = self._body_rect()
        total = float(np.sum(self._params.L)) * 1e6
        y = self.height() * 0.90
        left, right = body.left(), body.right()

        painter.setPen(QPen(QColor(p.border_strong), 1.0))
        painter.drawLine(QPointF(left, y), QPointF(right, y))
        for end in (left, right):
            painter.drawLine(QPointF(end, y - 4), QPointF(end, y + 4))

        # Where the interfaces really sit, at true scale.
        cumulative = np.asarray(self._params.Lsum, dtype=float)
        if total > 0:
            painter.setPen(QPen(QColor(p.text_faint), 1.0, Qt.PenStyle.DotLine))
            for position in cumulative[1:-1]:
                x = left + (right - left) * float(position * 1e6) / total
                painter.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))

        font = QFont(painter.font())
        font.setPointSizeF(8.0)
        painter.setFont(font)
        painter.setPen(QColor(p.text_faint))
        painter.drawText(
            QRectF(left, y + 5, right - left, 15),
            Qt.AlignmentFlag.AlignCenter,
            f"true scale · {_format_thickness(total)} across · "
            f"layer widths above are compressed for legibility")


def _arrow(painter: QPainter, tip: QPointF, direction: int, size: float) -> None:
    """A small solid triangle pointing left (-1) or right (+1)."""
    head = QPolygonF([tip,
                      QPointF(tip.x() - direction * size, tip.y() - size * 0.42),
                      QPointF(tip.x() - direction * size, tip.y() + size * 0.42)])
    painter.setBrush(painter.pen().color())
    painter.drawPolygon(head)
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _mix(base: QColor, other: QColor, amount: float) -> QColor:
    """``base`` blended ``amount`` of the way towards ``other``."""
    return QColor(round(base.red() + (other.red() - base.red()) * amount),
                  round(base.green() + (other.green() - base.green()) * amount),
                  round(base.blue() + (other.blue() - base.blue()) * amount))


def _format_thickness(microns: float) -> str:
    if microns >= 100:
        return f"{microns:.0f} µm"
    if microns >= 10:
        return f"{microns:.4g} µm"
    return f"{microns:.3g} µm"
