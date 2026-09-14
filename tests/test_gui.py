"""Tests for the PySide6 front end.

The point of these is the boundary between the GUI and the model: the window
must not be able to perturb a parameter on its way to ``solve``. The heaviest
check is therefore :func:`test_panel_round_trip_leaves_every_param_field_bit_identical`,
which drives a full pass through the editors and compares every field of
``Params`` against a freshly constructed default.

They run headless through Qt's offscreen platform, and skip themselves when
PySide6 is not installed -- the model does not need it.
"""
from __future__ import annotations

import dataclasses
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="the GUI is optional; install PySide6-Essentials")

from PySide6.QtWidgets import QApplication  # noqa: E402

from mmm1d.model import DEFAULT_MAX_NODES  # noqa: E402
from mmm1d.params import Params  # noqa: E402
from mmm1d.state import ACTIVE_REGIONS, Quantity, Region  # noqa: E402
from mmm1d_gui.about import (GITHUB_PROFILE, PHONE_DISPLAY,  # noqa: E402
                             PHONE_LINK, REPOSITORY, about_html)
from mmm1d_gui.config import GuiConfig, sweep_from_range  # noqa: E402
from mmm1d_gui.dataio import DataImportError, read_polarization_data  # noqa: E402
from mmm1d_gui.equations import (LAYER_DOCS, TRANSPORT_DOCS,  # noqa: E402
                                 groups_for_quantity)
from mmm1d_gui.paramfields import (catalogued_names, editable_names,  # noqa: E402
                                   uncatalogued_fields)


@pytest.fixture(scope="session")
def qt_app():
    """One QApplication for the whole session; Qt allows no more."""
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture()
def window(qt_app):
    from mmm1d_gui.app import MainWindow

    main_window = MainWindow()
    yield main_window
    main_window.close()


# =============================================================================
# THE GUI MUST NOT PERTURB THE MODEL
# =============================================================================

def test_default_config_builds_the_models_own_defaults():
    """An untouched GUI describes exactly ``Params()``."""
    built = GuiConfig().build_params()
    default = Params()
    for field in dataclasses.fields(Params):
        assert np.array_equal(np.asarray(getattr(built, field.name)),
                              np.asarray(getattr(default, field.name))), \
            f"{field.name} differs from the model's default"


def test_panel_round_trip_leaves_every_param_field_bit_identical(window):
    """Opening the editors and reading them back must change nothing.

    The thicknesses are the trap here: they are shown in microns, and the
    scaling has to survive the trip in both directions.
    """
    config = GuiConfig()
    window.material_panel.load_from(config)
    window.simulation_panel.load_from(config)
    window.material_panel.apply_to(config)
    window.simulation_panel.apply_to(config)

    built, default = config.build_params(), Params()
    differing = [field.name for field in dataclasses.fields(Params)
                 if not np.array_equal(np.asarray(getattr(built, field.name)),
                                       np.asarray(getattr(default, field.name)))]
    assert not differing, f"the editors perturbed {differing}"
    assert window.material_panel.modified_count() == 0


def test_default_sweep_matches_the_parameter_sets_own_sweep():
    assert np.array_equal(np.asarray(GuiConfig().sweep.resolved()),
                          Params().U_list)


def test_default_solver_settings_match_run_example():
    solver = GuiConfig().solver
    assert solver.tol == 1e-4
    assert solver.n_per_region == 11
    assert solver.max_nodes == DEFAULT_MAX_NODES
    assert solver.convergence_check is True
    assert solver.refine_factor == 12
    assert solver.outdir == "results"


# =============================================================================
# CONFIGURATION
# =============================================================================

def test_config_survives_a_json_round_trip(tmp_path):
    config = GuiConfig()
    config.material["RH_C"] = 0.55
    config.material["L"] = [1e-4, 2e-5, 3e-5, 2e-5, 1e-4]
    config.solver.tol = 1e-5
    config.sweep.mode = "list"
    config.sweep.voltages = [0.9, 0.8]

    reloaded = GuiConfig.load(config.save(tmp_path / "c.json"))
    assert reloaded.material["RH_C"] == 0.55
    assert reloaded.material["L"] == [1e-4, 2e-5, 3e-5, 2e-5, 1e-4]
    assert reloaded.solver.tol == 1e-5
    assert reloaded.sweep.resolved() == [0.9, 0.8]


def test_partial_config_fills_the_rest_from_the_defaults(tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"material": {"RH_A": 0.5},
                                "solver": {"tol": 1e-6}}))
    config = GuiConfig.load(path)
    assert config.material["RH_A"] == 0.5
    assert config.material["P_A"] == Params().P_A
    assert config.solver.max_nodes == DEFAULT_MAX_NODES


def test_config_from_a_newer_format_is_refused(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"config_version": 99}))
    with pytest.raises(ValueError, match="newer version"):
        GuiConfig.load(path)


def test_modified_material_reports_only_what_changed():
    config = GuiConfig()
    assert config.modified_material() == {}
    config.material["k_CL"] = 0.5
    assert set(config.modified_material()) == {"k_CL"}


def test_log_command_names_the_gui_not_the_command_line():
    """The run log has to say what was actually run."""
    command = GuiConfig().log_command()
    assert command.startswith("run_gui.py")
    assert "run_example.py" in command, "the reproduction command is still useful"


def test_edited_material_is_flagged_on_the_reproduction_command():
    config = GuiConfig()
    config.material["eps_p_GDL"] = 0.5
    assert "config.json" in config.equivalent_command()


@pytest.mark.parametrize("start, stop, step, expected", [
    (1.15, 1.00, 0.05, [1.15, 1.10, 1.05, 1.00]),
    (1.0, 1.0, 0.05, [1.0]),
    (0.9, 0.9, 0.0, [0.9]),
])
def test_sweep_from_range(start, stop, step, expected):
    assert np.allclose(sweep_from_range(start, stop, step), expected)


# =============================================================================
# THE FIELD CATALOGUE
# =============================================================================

def test_every_editable_param_is_reachable_in_the_editor():
    """A field added to ``Params`` must not silently vanish from the GUI."""
    assert uncatalogued_fields() == [], \
        "these Params fields have no entry in paramfields.PARAM_GROUPS"


def test_the_catalogue_invents_no_fields():
    assert catalogued_names() <= set(editable_names())


# =============================================================================
# EQUATIONS
# =============================================================================

def test_every_layer_documents_every_quantity_it_resolves():
    for region in Region:
        doc = LAYER_DOCS[region]
        documented = {group.quantity for group in doc.groups}
        for quantity in Quantity:
            if region in ACTIVE_REGIONS[quantity]:
                assert quantity in documented, \
                    f"{doc.name} resolves {quantity.name} but shows no equations"


def test_no_layer_documents_a_quantity_it_does_not_resolve():
    for region in Region:
        doc = LAYER_DOCS[region]
        for group in doc.groups:
            if group.quantity is None:
                continue   # a reaction, which belongs to no single quantity
            assert region in ACTIVE_REGIONS[group.quantity], \
                f"{doc.name} shows {group.quantity.name}, which it does not resolve"


def test_every_transport_process_resolves_to_equations():
    assert len(TRANSPORT_DOCS) == 8, "the model couples eight PDEs"
    for doc in TRANSPORT_DOCS:
        assert groups_for_quantity(doc.quantity), \
            f"'{doc.title}' maps to {doc.quantity.name}, which no layer documents"


def test_every_equation_renders():
    """mathtext is a subset of LaTeX; an unsupported macro must not ship."""
    from mmm1d_gui.mathrender import render_math

    for region in Region:
        for group in LAYER_DOCS[region].groups:
            for equation in group.equations:
                pixmap = render_math(equation.latex)
                assert not pixmap.isNull(), f"failed to render: {equation.latex}"


# =============================================================================
# IMPORTING MEASURED DATA
# =============================================================================

@pytest.mark.parametrize("text, expected", [
    ("0.1,0.95\n0.5,0.80\n", [[0.1, 0.95], [0.5, 0.80]]),
    ("0.1 0.95\n0.5 0.80\n", [[0.1, 0.95], [0.5, 0.80]]),
    ("0.1\t0.95\n0.5\t0.80\n", [[0.1, 0.95], [0.5, 0.80]]),
    ("# a comment\n\n0.1;0.95\n", [[0.1, 0.95]]),
    ("I [A/cm2],U [V]\n0.1,0.95\n", [[0.1, 0.95]]),
])
def test_polarization_data_formats(tmp_path, text, expected):
    path = tmp_path / "data.csv"
    path.write_text(text)
    data, _ = read_polarization_data(path)
    assert np.allclose(data, expected)


def test_a_voltage_first_header_swaps_the_columns(tmp_path):
    path = tmp_path / "swapped.csv"
    path.write_text("U [V];I [A/cm^2]\n0.95;0.1\n0.80;0.5\n")
    data, note = read_polarization_data(path)
    assert np.allclose(data, [[0.1, 0.95], [0.5, 0.80]])
    assert "header" in note


@pytest.mark.parametrize("text", ["", "1.0\n2.0\n", "0.1,not-a-number\n0.2,0.3\n"])
def test_unreadable_data_is_refused(tmp_path, text):
    path = tmp_path / "bad.csv"
    path.write_text(text)
    with pytest.raises(DataImportError):
        read_polarization_data(path)


# =============================================================================
# THE WINDOW
# =============================================================================

def test_the_window_opens_with_nothing_to_export(window):
    assert not window.action_export_log.isEnabled()
    assert not window.action_export_figures.isEnabled()
    assert window.outcome is None


def test_every_layer_and_transport_chip_can_be_shown(window):
    """Clicking anything on the diagram or the chips must produce a page."""
    for region in Region:
        window.equation_view.show_layer(region)
        assert LAYER_DOCS[region].subtitle in window.equation_view.toPlainText()
    for row, doc in enumerate(TRANSPORT_DOCS):
        window.equation_view.show_transport(row)
        assert doc.title in window.equation_view.toPlainText()


def test_the_diagram_is_drawn_from_the_configured_geometry(window):
    """The cell is drawn, not loaded, so it must follow Params.L."""
    from mmm1d.params import Params

    widths = window.diagram._widths()
    assert len(widths) == 5
    assert np.isclose(widths.sum(), 1.0)
    # thicker layers must still be drawn wider, even compressed
    thicknesses = Params().L
    assert (widths[0] > widths[1]) == (thicknesses[0] > thicknesses[1])
    assert widths.min() > 0.05, "a layer is too thin to label or to click"


def test_the_diagram_follows_a_change_of_thickness(window):
    import dataclasses

    import numpy as _np

    from mmm1d.params import Params

    before = window.diagram._widths().copy()
    thicker = dataclasses.replace(
        Params(), L=_np.array([400, 10, 25, 10, 160]) * 1e-6)
    window.diagram.set_params(thicker)
    after = window.diagram._widths()
    assert after[0] > before[0], "the redrawn AGDL is not wider"


def test_an_invalid_material_field_blocks_the_run(window):
    window.material_panel._edits["RH_A"].setText("not a number")
    assert "RH_A" in window.material_panel.invalid_fields()


def test_an_empty_sweep_is_reported_as_a_problem(window):
    window.simulation_panel._mode_list.setChecked(True)
    window.simulation_panel._list_edit.setText("")
    assert window.simulation_panel.problems()


# =============================================================================
# ABOUT
# =============================================================================

def test_about_states_the_author_and_how_to_reach_them():
    body = about_html("1D PEM Fuel Cell Model")
    for expected in ("Victor Constantin Cartsounis", "CEFET-MG",
                     GITHUB_PROFILE, REPOSITORY, PHONE_DISPLAY):
        assert expected in body, f"the About dialog no longer mentions {expected}"


def test_the_phone_link_is_diallable():
    """A tel: link has to carry bare digits, not the display grouping."""
    assert PHONE_LINK.startswith("tel:+")
    assert PHONE_LINK[4:].lstrip("+").isdigit()
    assert "".join(c for c in PHONE_DISPLAY if c.isdigit()) == PHONE_LINK[5:]


def test_about_dialog_opens_with_working_links(qt_app):
    from PySide6.QtWidgets import QLabel

    from mmm1d_gui.about import AboutDialog

    dialog = AboutDialog("1D PEM Fuel Cell Model")
    label = dialog.findChild(QLabel)
    assert label is not None
    assert label.openExternalLinks(), \
        "the GitHub and phone links would not open when clicked"
    dialog.close()


# =============================================================================
# APPEARANCE
# =============================================================================

def test_both_palettes_define_every_token():
    """A palette missing a colour would crash whichever widget reads it."""
    import dataclasses as _dc

    from mmm1d_gui import theme

    for palette in (theme.LIGHT, theme.DARK):
        for field in _dc.fields(palette):
            value = getattr(palette, field.name)
            if field.name in ("name", "dark"):
                continue
            assert isinstance(value, str) and value.startswith("#"), \
                f"{palette.name}.{field.name} is not a colour: {value!r}"
            assert len(value) == 7, f"{palette.name}.{field.name} = {value}"
        assert len(palette.transport_colors) == 8


def test_both_palettes_produce_a_stylesheet():
    from mmm1d_gui import theme

    for palette in (theme.LIGHT, theme.DARK):
        sheet = theme.stylesheet(palette)
        assert "QWidget" in sheet
        assert "{color}" not in sheet, "an unsubstituted placeholder got through"


def test_switching_to_dark_and_back_leaves_the_window_working(window):
    from mmm1d_gui import theme

    window.set_theme(theme.DARK)
    assert window.action_dark.isChecked()
    window.equation_view.show_layer(Region.CCL)
    assert "Cathode catalyst layer" in window.equation_view.toPlainText()

    window.set_theme(theme.LIGHT)
    assert window.action_light.isChecked()
    assert theme.active() is theme.LIGHT
