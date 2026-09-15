"""LaTeX snippets rendered to pixmaps with matplotlib's mathtext.

Qt has no maths renderer, but matplotlib is already a dependency of the model
and its mathtext engine understands the subset of LaTeX the equation panel
needs. Each snippet is drawn onto a transparent figure, saved to an in-memory
PNG and cached, so scrolling the panel costs nothing after the first pass.

Only mathtext syntax is available -- single expressions, no ``\\text{}`` and no
``align`` environments -- which is why :mod:`pemfc_1d_gui.equations` keeps every
equation to one line and spells words with ``\\mathrm{}``.
"""
from __future__ import annotations

from io import BytesIO

from matplotlib.figure import Figure
from PySide6.QtGui import QPixmap

#: Resolution equations are rasterised at. Higher than the screen's logical
#: DPI so the glyphs stay sharp; the pixmap is scaled back down for layout.
RENDER_DPI = 200

#: DPI Qt lays text out at, which is what the rasterised equation has to be
#: scaled back to. Sizing it at 72 instead -- the number of points in an inch
#: -- makes every equation come out a third too small beside the prose.
DISPLAY_DPI = 96.0

_CACHE: dict[tuple, QPixmap] = {}


def render_math(latex: str, fontsize: float = 12.0, color: str = "#202020") -> QPixmap:
    """Render ``latex`` (without the surrounding ``$``) to a transparent pixmap.

    The returned pixmap carries a device pixel ratio, so ``pixmap.width()``
    is in physical pixels while :func:`logical_size` gives the size the layout
    should reserve for it.
    """
    key = (latex, fontsize, color)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    figure = Figure(figsize=(0.01, 0.01), dpi=RENDER_DPI)
    figure.patch.set_alpha(0.0)
    figure.text(0.0, 0.0, f"${latex}$", fontsize=fontsize, color=color)

    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=RENDER_DPI, transparent=True,
                   bbox_inches="tight", pad_inches=0.02)

    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    _CACHE[key] = pixmap
    return pixmap


def logical_size(pixmap: QPixmap) -> tuple[int, int]:
    """Size in layout units of a pixmap rendered at :data:`RENDER_DPI`."""
    scale = DISPLAY_DPI / RENDER_DPI
    return max(1, round(pixmap.width() * scale)), max(1, round(pixmap.height() * scale))


def mathtext_is_available() -> bool:
    """Whether a snippet can be rendered at all.

    A broken matplotlib font cache is the one realistic failure, and the
    equation panel falls back to plain text rather than dying if it hits it.
    """
    try:
        render_math(r"x")
    except Exception:  # pragma: no cover - depends on the font cache
        return False
    return True
