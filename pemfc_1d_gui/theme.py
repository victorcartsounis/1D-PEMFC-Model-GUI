"""Colours, typography and the application stylesheet.

Qt's stock widgets carry whatever chrome the platform style gives them, which
on a plain Linux or Windows desktop is a hard grey with a saturated blue
highlight. Everything visual is therefore defined here as a small set of
tokens, and every widget reads its colours from them rather than hard-coding a
hex value -- which is also what makes the dark palette a swap of one object
instead of a second pass over the whole interface.

The accent is deliberately desaturated. This is a tool for reading numbers off
plots for hours, so the interface is neutral and the only saturated colour in
the window is the data.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

#: Preferred UI faces, best first. The first one installed on the machine wins.
FONT_STACK = ("Inter", "Segoe UI Variable", "Segoe UI", "SF Pro Text",
              "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans")

#: Preferred monospace faces, for the logs.
MONO_STACK = ("JetBrains Mono", "Cascadia Code", "SF Mono", "Ubuntu Mono",
              "Noto Sans Mono", "DejaVu Sans Mono")


@dataclass(frozen=True)
class Palette:
    """One complete set of colours."""

    name: str
    dark: bool

    # surfaces, back to front
    window: str          # the application background
    surface: str         # cards, panels, editors
    surface_alt: str     # subtle fills: hints, table stripes, disabled
    surface_hover: str

    # lines
    border: str
    border_strong: str

    # type
    text: str
    text_muted: str
    text_faint: str

    # the one accent
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_wash: str     # accent at low opacity, for selected rows
    on_accent: str       # type drawn on top of the accent

    # states
    warning: str
    warning_wash: str
    danger: str
    danger_wash: str
    modified: str        # a field edited away from its default

    # the cell diagram
    gdl: str
    gdl_fill: str
    catalyst: str
    catalyst_fill: str
    membrane: str
    membrane_fill: str
    diagram_bg: str

    @property
    def transport_colors(self) -> tuple[str, ...]:
        """Eight distinguishable hues, one per transport process."""
        return (("#8ab4f8", "#c9a9e9", "#f0a868", "#7fc9c4",
                 "#9cc47f", "#e08e9b", "#d4b96a", "#89b8d4") if self.dark else
                ("#3b6ea5", "#7857a8", "#b5651d", "#2f7d7a",
                 "#4f7a3f", "#a63d5a", "#8a6d1f", "#2c6b8f"))


LIGHT = Palette(
    name="light", dark=False,
    window="#f4f5f7", surface="#ffffff", surface_alt="#f0f2f5",
    surface_hover="#e8ebef",
    border="#e1e4e9", border_strong="#c7ccd4",
    text="#1b1f26", text_muted="#5c646f", text_faint="#8b939e",
    accent="#3d6b9e", accent_hover="#35608f", accent_pressed="#2d5480",
    accent_wash="#e8eff7", on_accent="#ffffff",
    warning="#8a5a10", warning_wash="#fbf3e4",
    danger="#a52b22", danger_wash="#fbecea",
    modified="#fdf6e8",
    gdl="#6f7f96", gdl_fill="#e2e8f0",
    catalyst="#9c7a44", catalyst_fill="#f2e9da",
    membrane="#3f7b7c", membrane_fill="#d3e6e4",
    diagram_bg="#fafbfc",
)

DARK = Palette(
    name="dark", dark=True,
    window="#16181d", surface="#1e2127", surface_alt="#262a31",
    surface_hover="#2e333b",
    border="#2e333b", border_strong="#434a55",
    text="#e4e7ec", text_muted="#9aa3af", text_faint="#6d7681",
    accent="#6ea8de", accent_hover="#82b6e6", accent_pressed="#5b95cb",
    accent_wash="#233240", on_accent="#0f1216",
    warning="#d9a441", warning_wash="#332915",
    danger="#e07a6f", danger_wash="#331f1d",
    modified="#332d20",
    gdl="#8b9bb3", gdl_fill="#2a303a",
    catalyst="#bd9a62", catalyst_fill="#332c20",
    membrane="#5fa3a4", membrane_fill="#1e2e2e",
    diagram_bg="#1a1d22",
)

_active: Palette = LIGHT


def active() -> Palette:
    """The palette the interface is currently drawn in."""
    return _active


def set_active(palette: Palette) -> None:
    global _active
    _active = palette


def font_family() -> str:
    """The CSS font-family list, best face first."""
    return ", ".join(f'"{name}"' for name in FONT_STACK) + ", sans-serif"


def mono_family() -> str:
    return ", ".join(f'"{name}"' for name in MONO_STACK) + ", monospace"


def monospace_font(size: int = 10) -> QFont:
    """A monospace QFont, picking the first face the machine actually has."""
    font = QFont()
    font.setFamilies(list(MONO_STACK))
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(size)
    return font


def apply(application: QApplication, palette: Palette) -> None:
    """Dress the whole application in ``palette``."""
    set_active(palette)
    application.setStyle("Fusion")   # a neutral base for the stylesheet
    application.setPalette(_qt_palette(palette))
    application.setStyleSheet(stylesheet(palette))

    font = QFont()
    font.setFamilies(list(FONT_STACK))
    font.setPointSize(10)
    application.setFont(font)


def _qt_palette(palette: Palette) -> QPalette:
    """A QPalette for the parts a stylesheet cannot reach.

    Tooltips, text selection and the disabled-text colour are resolved from
    the palette rather than from CSS, so they have to be set here or they keep
    the platform style's own colours and stand out.
    """
    role = QPalette.ColorRole
    group = QPalette.ColorGroup
    qt = QPalette()
    qt.setColor(role.Window, QColor(palette.window))
    qt.setColor(role.WindowText, QColor(palette.text))
    qt.setColor(role.Base, QColor(palette.surface))
    qt.setColor(role.AlternateBase, QColor(palette.surface_alt))
    qt.setColor(role.Text, QColor(palette.text))
    qt.setColor(role.Button, QColor(palette.surface))
    qt.setColor(role.ButtonText, QColor(palette.text))
    qt.setColor(role.Highlight, QColor(palette.accent))
    qt.setColor(role.HighlightedText, QColor(palette.on_accent))
    qt.setColor(role.ToolTipBase, QColor(palette.surface))
    qt.setColor(role.ToolTipText, QColor(palette.text))
    # Fusion derives the outline of a check box, a radio button and a spin
    # arrow from these shading roles. Left at their defaults they come out
    # near-white on a white card, which makes an unchecked control invisible.
    qt.setColor(role.Light, QColor(palette.surface))
    qt.setColor(role.Midlight, QColor(palette.surface_alt))
    qt.setColor(role.Mid, QColor(palette.border_strong))
    qt.setColor(role.Dark, QColor(palette.text_faint))
    qt.setColor(role.Shadow, QColor(palette.border_strong))
    qt.setColor(role.PlaceholderText, QColor(palette.text_faint))
    qt.setColor(role.Link, QColor(palette.accent))
    for disabled in (role.Text, role.ButtonText, role.WindowText):
        qt.setColor(group.Disabled, disabled, QColor(palette.text_faint))
    return qt


def stylesheet(p: Palette) -> str:
    """The application stylesheet for one palette."""
    return f"""
* {{
    font-family: {font_family()};
}}

QWidget {{
    background: {p.window};
    color: {p.text};
}}

QToolTip {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 6px;
    padding: 6px 9px;
}}

/* ---------------------------------------------------------------- menus */
QMenuBar {{
    background: {p.window};
    border-bottom: 1px solid {p.border};
    padding: 2px 6px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 11px;
    border-radius: 6px;
}}
QMenuBar::item:selected {{ background: {p.surface_hover}; }}
QMenu {{
    background: {p.surface};
    border: 1px solid {p.border_strong};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 26px 7px 14px;
    border-radius: 5px;
}}
QMenu::item:selected {{ background: {p.accent_wash}; color: {p.text}; }}
QMenu::item:disabled {{ color: {p.text_faint}; }}
QMenu::separator {{
    height: 1px;
    background: {p.border};
    margin: 5px 9px;
}}

/* -------------------------------------------------------------- toolbar */
QToolBar {{
    background: {p.window};
    border: none;
    border-bottom: 1px solid {p.border};
    padding: 5px 8px;
    spacing: 3px;
}}
QToolBar::separator {{
    background: {p.border};
    width: 1px;
    margin: 5px 7px;
}}
QToolButton {{
    background: transparent;
    color: {p.text};
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 6px 12px;
    font-weight: 500;
}}
QToolButton:hover {{ background: {p.surface_hover}; }}
QToolButton:pressed {{ background: {p.border}; }}
QToolButton:disabled {{ color: {p.text_faint}; }}
QToolButton#primaryAction {{
    background: {p.accent};
    color: {p.on_accent};
}}
QToolButton#primaryAction:hover {{ background: {p.accent_hover}; }}
QToolButton#primaryAction:pressed {{ background: {p.accent_pressed}; }}
QToolButton#primaryAction:disabled {{
    background: {p.surface_alt};
    color: {p.text_faint};
}}

/* ----------------------------------------------------------------- tabs */
QTabWidget::pane {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 10px;
    top: -1px;
}}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent;
    color: {p.text_muted};
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 7px 15px;
    margin: 2px 3px 5px 0;
    font-weight: 500;
}}
QTabBar::tab:hover {{ color: {p.text}; background: {p.surface_hover}; }}
QTabBar::tab:selected {{
    background: {p.surface};
    color: {p.text};
    border-color: {p.border};
}}

/* --------------------------------------------------------------- groups */
QGroupBox {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 10px;
    margin-top: 11px;
    padding: 14px 13px 13px 13px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {p.text};
    background: {p.surface};
}}

/* ---------------------------------------------------------------- input */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 7px;
    padding: 6px 9px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {p.text_faint};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {p.accent};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {p.surface_alt};
    color: {p.text_faint};
    border-color: {p.border};
}}
QLineEdit[state="modified"] {{
    background: {p.modified};
    border-color: {p.warning};
}}
QLineEdit[state="invalid"] {{
    background: {p.danger_wash};
    border-color: {p.danger};
}}
/* The spin buttons are hidden rather than styled. Qt stylesheets cannot draw
   an arrow without an image file, and the style's own buttons are laid out for
   a square field so they spill over the rounded corner. Hiding them also makes
   every numeric field in the window the same thing -- a box you type into --
   and the up and down keys still step the value. */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0;
    border: none;
    background: transparent;
}}
/* The spin buttons are left to Fusion for the same reason as the check and
   radio marks: styling the subcontrol takes drawing away from the style, and
   a border-triangle renders as a filled block rather than an arrow. */

/* -------------------------------------------------------------- buttons */
QPushButton {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 7px;
    padding: 7px 15px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {p.surface_hover}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.border}; }}
QPushButton:default {{
    background: {p.accent};
    color: {p.on_accent};
    border-color: {p.accent};
}}
QPushButton:default:hover {{ background: {p.accent_hover}; }}

/* ------------------------------------------------------- checks, radios */
QCheckBox, QRadioButton {{
    spacing: 8px;
    padding: 2px 0;
    background: transparent;
}}
/* A radio button is drawable in pure CSS -- a thick accent border with the
   surface showing through the middle is a filled dot -- so it is styled here.
   A check box is not: a tick needs an image, and styling the subcontrol takes
   drawing away from the style, so a checked box would come out as a plain
   filled square. That one is left to Fusion, which draws the tick itself and
   tints it with the palette's Highlight. */
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {p.border_strong};
    border-radius: 8px;
    background: {p.surface};
}}
QRadioButton::indicator:hover {{ border-color: {p.accent}; }}
QRadioButton::indicator:checked {{
    border: 1px solid {p.accent};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                                stop:0 {p.accent}, stop:0.5 {p.accent},
                                stop:0.55 {p.surface}, stop:1 {p.surface});
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {p.text_faint}; }}

/* ------------------------------------------------------------- scrolling */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {p.border_strong};
    border-radius: 4px;
    min-height: 28px;
    min-width: 28px;
}}
QScrollBar::handle:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* --------------------------------------------------------------- panels */
QPlainTextEdit, QTextBrowser {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: 9px;
    padding: 8px;
}}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 7px; }}
QSplitter::handle:vertical {{ height: 7px; }}
QSplitter::handle:hover {{ background: {p.accent_wash}; }}

QStatusBar {{
    background: {p.window};
    border-top: 1px solid {p.border};
    color: {p.text_muted};
    padding: 2px 6px;
}}
QStatusBar::item {{ border: none; }}

QProgressBar {{
    background: {p.surface_alt};
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 4px;
}}

QDialog {{ background: {p.window}; }}
QLabel {{ background: transparent; }}

/* Containers that only exist to hold a layout, and so should show whatever
   card they sit on rather than painting the window colour over it. */
QStackedWidget, #sweepEditor, #sweepRangeRow {{ background: transparent; }}
"""
