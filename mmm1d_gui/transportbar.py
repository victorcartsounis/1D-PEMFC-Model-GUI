"""The eight coupled transport processes, as a row of selectable chips.

Drawing these into the cell diagram as a painted key would have been possible,
but making them real widgets costs nothing and gains keyboard focus, hover and
pressed states, tooltips, and a layout that reflows when the panel is narrow
rather than being clipped.

Qt ships no flow layout, so :class:`FlowLayout` is the small classic one: lay
children left to right, wrap when the row is full, and report the height that
wrapping produced so the parent can make room for it.
"""
from __future__ import annotations

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QLayout, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme
from .equations import TRANSPORT_DOCS


class FlowLayout(QLayout):
    """Lays widgets out in a row, wrapping onto the next line when full."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(QMargins(0, 0, 0, 0))

    # -- the five methods QLayout requires ---------------------------------
    def addItem(self, item) -> None:  # noqa: N802 - Qt override
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802 - Qt override
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802 - Qt override
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return self.minimumSize()

    # -- wrapping -----------------------------------------------------------
    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(),
                            margins.top() + margins.bottom())

    def _layout(self, rect: QRect, apply: bool) -> int:
        """Place the items, returning the total height used."""
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(),
                             -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > area.right() and line_height > 0:
                x = area.x()
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()


def _dot(color: str, size: int = 10) -> QPixmap:
    """A filled circle, used as the chip's colour swatch."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size - 1, size - 1)
    painter.end()
    return pixmap


class TransportBar(QWidget):
    """One chip per coupled transport process, at most one selected."""

    #: A chip was clicked; carries its index into ``TRANSPORT_DOCS``.
    transportClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        flow = FlowLayout(spacing=6)
        for index, doc in enumerate(TRANSPORT_DOCS):
            button = QPushButton(doc.title)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(doc.description)
            button.clicked.connect(
                lambda _checked, i=index: self.transportClicked.emit(i))
            self._group.addButton(button, index)
            self._buttons.append(button)
            flow.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(flow)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Minimum)
        self.refresh_theme()

    def select(self, index: int | None) -> None:
        """Check one chip, or clear the selection."""
        self._group.setExclusive(False)
        for position, button in enumerate(self._buttons):
            button.setChecked(index is not None and position == index)
        self._group.setExclusive(True)

    def refresh_theme(self) -> None:
        """Restyle after the palette has changed."""
        palette = theme.active()
        colors = palette.transport_colors
        for index, button in enumerate(self._buttons):
            color = colors[index % len(colors)]
            button.setIcon(_dot(color))
            button.setStyleSheet(f"""
                QPushButton {{
                    background: {palette.surface};
                    color: {palette.text_muted};
                    border: 1px solid {palette.border};
                    border-radius: 13px;
                    padding: 5px 13px;
                    font-weight: 500;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {palette.surface_hover};
                    color: {palette.text};
                    border-color: {palette.border_strong};
                }}
                QPushButton:checked {{
                    background: {palette.accent_wash};
                    color: {palette.text};
                    border-color: {color};
                }}
            """)
