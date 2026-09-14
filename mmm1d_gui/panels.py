"""The material and simulation configuration panels.

Both panels are plain editors over :class:`mmm1d_gui.config.GuiConfig`: they
are filled from one with :meth:`load_from` and read back into one with
:meth:`apply_to`. Neither talks to the solver, so a validation mistake stops at
the panel instead of reaching the model.

Values are entered as text rather than in spin boxes because the parameters
span thirteen orders of magnitude -- 1e-13 m^2 to 9.6e4 C/mol -- and a spin box
cannot show that without losing digits. The default text is Python's ``repr``,
which is the shortest string that reads back as the identical float, so opening
the panel and pressing Run cannot perturb a parameter.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QRadioButton,
                               QScrollArea, QSizePolicy, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from mmm1d.metrics import GB_PER_1000_NODES, REFINEMENT_NODE_CEILING
from mmm1d.model import DEFAULT_MAX_NODES

from . import theme
from .config import GuiConfig, SolverConfig, SweepConfig, default_material
from .paramfields import (LAYER_NAMES, PARAM_GROUPS, THICKNESS_FIELD,
                          ParamField, uncatalogued_fields)


def _hint_style() -> str:
    return f"color: {theme.active().text_muted}; background: transparent;"


def _warning_style() -> str:
    return f"color: {theme.active().warning}; background: transparent;"


def _format(value: float) -> str:
    """Shortest text that reads back as exactly ``value``."""
    return repr(float(value))


def _format_microns(value: float) -> str:
    """Text for a thickness that has been scaled from metres to microns.

    ``160e-6 * 1e6`` is 160.00000000000003, not 160, so ``repr`` would both
    print noise and fail to read back as the thickness it came from. Twelve
    significant digits drop the rounding error while keeping any thickness
    someone would realistically type, so the value survives the trip to the
    editor and back unchanged.
    """
    return f"{float(value):.12g}"


class NumberEdit(QLineEdit):
    """A line edit for one float, in decimal or scientific notation."""

    def __init__(self, value: float, on_change: Callable[[], None],
                 parent: QWidget | None = None,
                 formatter: Callable[[float], str] = _format) -> None:
        super().__init__(formatter(value), parent)
        self._format = formatter
        self._default_text = formatter(value)
        validator = QDoubleValidator(self)
        validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        self.setValidator(validator)
        self.setMinimumWidth(110)
        self.textChanged.connect(self._restyle)
        self.textChanged.connect(lambda _: on_change())

    def value(self) -> float:
        """The number entered, raising ``ValueError`` if it is not one."""
        return float(self.text().strip())

    def is_valid(self) -> bool:
        try:
            self.value()
        except ValueError:
            return False
        return True

    def set_value(self, value: float) -> None:
        self.setText(self._format(value))

    def set_default(self, value: float) -> None:
        """Change what counts as unmodified, without touching the content."""
        self._default_text = self._format(value)
        self._restyle()

    def reset(self) -> None:
        self.setText(self._default_text)

    def _restyle(self) -> None:
        """Flag the field's state as a property the stylesheet selects on.

        Setting colours inline here instead would override the theme and
        survive a palette change, so the state is declared and the stylesheet
        decides what it looks like.
        """
        if not self.is_valid():
            state = "invalid"
        elif self.text().strip() != self._default_text:
            state = "modified"
        else:
            state = "default"
        if self.property("state") != state:
            self.setProperty("state", state)
            self.style().unpolish(self)
            self.style().polish(self)


# =============================================================================
# MATERIAL
# =============================================================================

class MaterialPanel(QScrollArea):
    """Editor for every constructor argument of ``Params`` bar the sweep."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._edits: dict[str, NumberEdit] = {}
        self._thickness_edits: list[NumberEdit] = []

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        defaults = default_material()
        for group in PARAM_GROUPS:
            if group.title == "Layer thicknesses":
                layout.addWidget(self._build_thickness_group(group.description,
                                                             defaults))
            else:
                layout.addWidget(self._build_group(group.title,
                                                   group.description,
                                                   group.entries, defaults))

        extra = uncatalogued_fields()
        if extra:
            # A field added to Params since paramfields.py was written. Better
            # exposed with a bare name than quietly missing from the editor.
            entries = tuple(ParamField(name, name) for name in extra)
            layout.addWidget(self._build_group(
                "Other parameters",
                "Present in Params but not yet described in the GUI's field "
                "catalogue.", entries, defaults))

        reset = QPushButton("Reset all material parameters to defaults")
        reset.clicked.connect(self.reset_all)
        layout.addWidget(reset)
        layout.addStretch(1)

        self.setWidget(body)
        self.setWidgetResizable(True)

    # ----------------------------------------------------------- building
    def _build_group(self, title: str, description: str,
                     entries: tuple[ParamField, ...],
                     defaults: dict) -> QGroupBox:
        box = QGroupBox(title)
        outer = QVBoxLayout(box)
        outer.addWidget(_hint(description))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for entry in entries:
            edit = NumberEdit(defaults[entry.name], self.changed.emit)
            tooltip = f"Params.{entry.name}"
            if entry.tooltip:
                tooltip += f"\n\n{entry.tooltip}"
            edit.setToolTip(tooltip)
            self._edits[entry.name] = edit

            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(edit, 1)
            if entry.unit:
                unit = QLabel(entry.unit)
                unit.setStyleSheet(_hint_style())
                unit.setObjectName("unitLabel")
                unit.setMinimumWidth(54)
                row.addWidget(unit)
            container = QWidget()
            container.setLayout(row)

            label = QLabel(entry.label)
            label.setToolTip(tooltip)
            form.addRow(label, container)
        outer.addLayout(form)
        return box

    def _build_thickness_group(self, description: str,
                               defaults: dict) -> QGroupBox:
        box = QGroupBox("Layer thicknesses")
        outer = QVBoxLayout(box)
        outer.addWidget(_hint(description))

        grid = QGridLayout()
        for column, (name, metres) in enumerate(zip(LAYER_NAMES,
                                                    defaults[THICKNESS_FIELD])):
            heading = QLabel(name)
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading.setStyleSheet("font-weight: bold;")
            edit = NumberEdit(metres * 1e6, self.changed.emit,
                              formatter=_format_microns)
            edit.setMinimumWidth(60)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setToolTip(f"Thickness of the {name} in microns "
                            f"(Params.L[{column}])")
            self._thickness_edits.append(edit)
            grid.addWidget(heading, 0, column)
            grid.addWidget(edit, 1, column)
        units = QLabel("microns")
        units.setStyleSheet(_hint_style())
        units.setObjectName("unitLabel")
        grid.addWidget(units, 2, 0, 1, len(LAYER_NAMES),
                       Qt.AlignmentFlag.AlignRight)
        outer.addLayout(grid)
        return box

    # ----------------------------------------------------------- public API
    def load_from(self, config: GuiConfig) -> None:
        for name, edit in self._edits.items():
            if name in config.material:
                edit.set_value(config.material[name])
        thicknesses = config.material.get(THICKNESS_FIELD, [])
        for edit, metres in zip(self._thickness_edits, thicknesses):
            edit.set_value(metres * 1e6)

    def apply_to(self, config: GuiConfig) -> None:
        for name, edit in self._edits.items():
            config.material[name] = edit.value()
        config.material[THICKNESS_FIELD] = [edit.value() * 1e-6
                                            for edit in self._thickness_edits]

    def invalid_fields(self) -> list[str]:
        """Names of every field whose text is not a number."""
        bad = [name for name, edit in self._edits.items() if not edit.is_valid()]
        bad += [f"{THICKNESS_FIELD}[{i}] ({LAYER_NAMES[i]})"
                for i, edit in enumerate(self._thickness_edits)
                if not edit.is_valid()]
        return bad

    def modified_count(self) -> int:
        """How many fields currently differ from the model's defaults."""
        defaults = default_material()
        count = sum(1 for name, edit in self._edits.items()
                    if edit.is_valid() and edit.value() != defaults[name])
        count += sum(1 for edit, metres in zip(self._thickness_edits,
                                               defaults[THICKNESS_FIELD])
                     if edit.is_valid() and edit.value() * 1e-6 != metres)
        return count

    def refresh_theme(self) -> None:
        """Re-apply the colours of the labels that carry their own styling.

        Hints and unit captions are the only widgets here with a per-widget
        stylesheet -- everything else is covered by the application sheet --
        so a palette change only has to reach those.
        """
        for label in self.findChildren(QLabel):
            if label.objectName() == "hintLabel":
                label.setStyleSheet(_hint_style())
            elif label.objectName() == "unitLabel":
                label.setStyleSheet(_hint_style())

    def reset_all(self) -> None:
        for edit in self._edits.values():
            edit.reset()
        for edit in self._thickness_edits:
            edit.reset()


# =============================================================================
# SIMULATION
# =============================================================================

class SimulationPanel(QScrollArea):
    """Editor for the voltage sweep and the solver settings."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        layout.addWidget(self._build_sweep_group())
        layout.addWidget(self._build_solver_group())
        layout.addWidget(self._build_convergence_group())
        layout.addWidget(self._build_output_group())
        layout.addStretch(1)
        self.setWidget(body)
        self.setWidgetResizable(True)
        self._refresh()

    # ----------------------------------------------------------- building
    def _build_sweep_group(self) -> QGroupBox:
        box = QGroupBox("Voltage sweep")
        layout = QVBoxLayout(box)
        layout.addWidget(_hint(
            "Solved in the order given. Each voltage starts from the previous "
            "converged solution, so the sweep must run downwards from open "
            "circuit -- starting low, or skipping too far, leaves the solver "
            "without a usable initial guess."))

        defaults = SweepConfig()
        self._mode_range = QRadioButton("Range")
        self._mode_list = QRadioButton("Explicit list")
        self._mode_range.setChecked(True)
        modes = QButtonGroup(box)
        modes.addButton(self._mode_range)
        modes.addButton(self._mode_list)
        for button in (self._mode_range, self._mode_list):
            button.toggled.connect(self._refresh)

        # The two modes sit on their own row and the editor for the selected
        # one is swapped in underneath. Laying the radio and its fields out
        # side by side instead made this group 539px wide -- wider than the
        # whole panel -- which is what was clipping the left-hand side.
        modes_row = QHBoxLayout()
        modes_row.setContentsMargins(0, 0, 0, 4)
        modes_row.addWidget(self._mode_range)
        modes_row.addSpacing(14)
        modes_row.addWidget(self._mode_list)
        modes_row.addStretch(1)
        layout.addLayout(modes_row)

        self._start = _voltage_box(defaults.start, self._refresh)
        self._stop = _voltage_box(defaults.stop, self._refresh)
        self._step = _voltage_box(defaults.step, self._refresh, minimum=0.001)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for label, widget in (("from", self._start), ("to", self._stop),
                              ("step", self._step)):
            caption = QLabel(label)
            caption.setStyleSheet(_hint_style())
            caption.setObjectName("unitLabel")
            row.addWidget(caption)
            row.addWidget(widget)
        volts = QLabel("V")
        volts.setStyleSheet(_hint_style())
        volts.setObjectName("unitLabel")
        row.addWidget(volts)
        row.addStretch(1)
        self._range_row = QWidget()
        self._range_row.setObjectName("sweepRangeRow")
        self._range_row.setLayout(row)

        self._list_edit = QLineEdit(
            " ".join(f"{v:g}" for v in defaults.resolved()))
        self._list_edit.setPlaceholderText("1.15 1.10 1.05 1.00")
        self._list_edit.setToolTip("Voltages in volts, separated by spaces or "
                                   "commas.")
        self._list_edit.textChanged.connect(self._refresh)

        self._sweep_editor = QStackedWidget()
        self._sweep_editor.setObjectName("sweepEditor")
        self._sweep_editor.addWidget(self._range_row)
        self._sweep_editor.addWidget(self._list_edit)
        layout.addWidget(self._sweep_editor)

        self._sweep_preview = QLabel()
        self._sweep_preview.setWordWrap(True)
        self._sweep_preview.setStyleSheet(_hint_style())
        layout.addWidget(self._sweep_preview)
        return box

    def _build_solver_group(self) -> QGroupBox:
        box = QGroupBox("Solver")
        layout = QVBoxLayout(box)
        layout.addWidget(_hint(
            "Passed straight through to scipy.integrate.solve_bvp, which "
            "solves all five layers as one stacked 80-equation system."))
        defaults = SolverConfig()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._tol = NumberEdit(defaults.tol, self._refresh)
        self._tol.setToolTip("Tolerance for solve_bvp. 1e-4 is the RelTol of "
                             "the MATLAB reference implementation.")
        form.addRow("Tolerance", self._tol)

        self._n_per_region = QSpinBox()
        self._n_per_region.setRange(3, 2001)
        self._n_per_region.setValue(defaults.n_per_region)
        self._n_per_region.valueChanged.connect(self._refresh)
        self._n_per_region.setToolTip("Initial mesh points per layer, before "
                                      "any adaptive refinement.")
        form.addRow("Initial mesh points per layer", self._n_per_region)

        self._max_nodes = QSpinBox()
        self._max_nodes.setRange(16, 200_000)
        self._max_nodes.setValue(defaults.max_nodes)
        self._max_nodes.valueChanged.connect(self._refresh)
        self._max_nodes.setToolTip(
            f"Ceiling on adaptive mesh refinement. The default "
            f"{DEFAULT_MAX_NODES} is MATLAB bvp4c's floor(10000/n) for this "
            f"80-equation system, which is the ceiling the reference "
            f"implementation ran on.")
        form.addRow("Maximum mesh nodes", self._max_nodes)
        layout.addLayout(form)

        self._nodes_hint = QLabel()
        self._nodes_hint.setWordWrap(True)
        layout.addWidget(self._nodes_hint)
        return box

    def _build_convergence_group(self) -> QGroupBox:
        box = QGroupBox("Convergence check")
        layout = QVBoxLayout(box)
        layout.addWidget(_hint(
            "Re-solves the whole sweep on a finer mesh and records how far the "
            "current density moves. This is the number that certifies a run: "
            "solve_bvp's own success flag cannot, because it reports failure "
            "wherever the mesh cannot resolve the sorption discontinuity, "
            "however close to converged the current density is."))
        defaults = SolverConfig()

        self._convergence = QCheckBox("Run the convergence check after the sweep")
        self._convergence.setChecked(defaults.convergence_check)
        self._convergence.toggled.connect(self._refresh)
        layout.addWidget(self._convergence)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._refine_factor = QSpinBox()
        self._refine_factor.setRange(2, 200)
        self._refine_factor.setValue(defaults.refine_factor)
        self._refine_factor.valueChanged.connect(self._refresh)
        form.addRow("Mesh refinement factor", self._refine_factor)
        layout.addLayout(form)

        self._refine_hint = QLabel()
        self._refine_hint.setWordWrap(True)
        self._refine_hint.setStyleSheet(_hint_style())
        layout.addWidget(self._refine_hint)
        return box

    def _build_output_group(self) -> QGroupBox:
        box = QGroupBox("Output")
        layout = QVBoxLayout(box)
        layout.addWidget(_hint(
            "Each run writes one timestamped folder here holding "
            "potentials.png, fluxes.png, polarization_curve.png, metrics.log "
            "and the configuration it was run with -- the same layout "
            "run_example.py produces."))

        row = QHBoxLayout()
        self._outdir = QLineEdit(SolverConfig().outdir)
        self._outdir.textChanged.connect(self._refresh)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._choose_outdir)
        row.addWidget(self._outdir, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        return box

    def _choose_outdir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Directory to write run folders into", self._outdir.text())
        if chosen:
            self._outdir.setText(chosen)

    # ------------------------------------------------------------- refresh
    def _refresh(self, *_: object) -> None:
        self._sweep_editor.setCurrentIndex(
            0 if self._mode_range.isChecked() else 1)
        self._refine_factor.setEnabled(self._convergence.isChecked())

        voltages = self.resolved_voltages()
        if voltages is None:
            self._sweep_preview.setText(
                "Cannot read the voltage list: give numbers separated by "
                "spaces or commas.")
            self._sweep_preview.setStyleSheet(_warning_style())
        elif not voltages:
            self._sweep_preview.setText("This sweep is empty -- nothing "
                                        "would be solved.")
            self._sweep_preview.setStyleSheet(_warning_style())
        else:
            shown = " ".join(f"{v:.3f}" for v in voltages[:12])
            if len(voltages) > 12:
                shown += f" ... ({len(voltages) - 12} more)"
            ascending = len(voltages) > 1 and voltages[1] > voltages[0]
            self._sweep_preview.setText(
                f"{len(voltages)} voltage{'s' if len(voltages) != 1 else ''}: "
                f"{shown}" + ("\nThis sweep runs upwards. Continuation expects "
                              "it to start at open circuit and descend."
                              if ascending else ""))
            self._sweep_preview.setStyleSheet(
                _warning_style() if ascending else _hint_style())

        nodes = self._max_nodes.value()
        memory = nodes * GB_PER_1000_NODES / 1000
        if nodes > DEFAULT_MAX_NODES:
            self._nodes_hint.setText(
                f"~{memory:.1f} GB of peak memory. Above the reference "
                f"implementation's {DEFAULT_MAX_NODES}-node ceiling: the "
                f"solver will keep clustering nodes around the sorption "
                f"discontinuity without the error estimate dropping, so this "
                f"buys resolution everywhere else at roughly "
                f"{GB_PER_1000_NODES} GB per 1000 nodes.")
            self._nodes_hint.setStyleSheet(_warning_style())
        else:
            self._nodes_hint.setText(f"~{memory:.2f} GB of peak memory.")
            self._nodes_hint.setStyleSheet(_hint_style())

        refined = min(self._refine_factor.value() * nodes,
                      REFINEMENT_NODE_CEILING)
        if refined <= nodes:
            self._refine_hint.setText(
                f"The check would be skipped: the refined solve is capped at "
                f"{REFINEMENT_NODE_CEILING} nodes, which is already at or "
                f"below the {nodes} nodes of the base sweep.")
            self._refine_hint.setStyleSheet(_warning_style())
        else:
            self._refine_hint.setText(
                f"Refined solve: {refined} nodes "
                f"(~{refined * GB_PER_1000_NODES / 1000:.1f} GB), capped at "
                f"{REFINEMENT_NODE_CEILING} so that asking for a check can "
                f"never itself exhaust memory. It roughly doubles the run time.")
            self._refine_hint.setStyleSheet(_hint_style())

        self.changed.emit()

    # ----------------------------------------------------------- public API
    def resolved_voltages(self) -> list[float] | None:
        """The sweep as configured, or ``None`` if the list cannot be read."""
        if self._mode_range.isChecked():
            return SweepConfig(mode="range", start=self._start.value(),
                               stop=self._stop.value(),
                               step=self._step.value()).resolved()
        text = self._list_edit.text().replace(",", " ").split()
        try:
            return [float(piece) for piece in text]
        except ValueError:
            return None

    def load_from(self, config: GuiConfig) -> None:
        sweep, solver = config.sweep, config.solver
        blocked = [self._mode_range, self._mode_list, self._list_edit,
                   self._start, self._stop, self._step, self._tol,
                   self._n_per_region, self._max_nodes, self._convergence,
                   self._refine_factor, self._outdir]
        for widget in blocked:
            widget.blockSignals(True)
        try:
            self._mode_range.setChecked(sweep.mode == "range")
            self._mode_list.setChecked(sweep.mode != "range")
            self._start.setValue(sweep.start)
            self._stop.setValue(sweep.stop)
            self._step.setValue(sweep.step)
            self._list_edit.setText(" ".join(f"{v:g}" for v in sweep.voltages))
            self._tol.set_value(solver.tol)
            self._n_per_region.setValue(solver.n_per_region)
            self._max_nodes.setValue(solver.max_nodes)
            self._convergence.setChecked(solver.convergence_check)
            self._refine_factor.setValue(solver.refine_factor)
            self._outdir.setText(solver.outdir)
        finally:
            for widget in blocked:
                widget.blockSignals(False)
        self._refresh()

    def apply_to(self, config: GuiConfig) -> None:
        voltages = self.resolved_voltages() or []
        config.sweep = SweepConfig(
            mode="range" if self._mode_range.isChecked() else "list",
            start=self._start.value(), stop=self._stop.value(),
            step=self._step.value(), voltages=voltages)
        config.solver = SolverConfig(
            tol=self._tol.value(), n_per_region=self._n_per_region.value(),
            max_nodes=self._max_nodes.value(),
            convergence_check=self._convergence.isChecked(),
            refine_factor=self._refine_factor.value(),
            outdir=self._outdir.text().strip() or SolverConfig().outdir)

    def refresh_theme(self) -> None:
        """Re-apply the colours of the hint labels, then recompute them.

        The solver hints switch between the muted and the warning colour
        depending on their content, so the refresh runs the same pass that
        writes them rather than trying to restyle them in place.
        """
        for label in self.findChildren(QLabel):
            if label.objectName() in ("hintLabel", "unitLabel"):
                label.setStyleSheet(_hint_style())
        self._refresh()

    def problems(self) -> list[str]:
        """Human-readable reasons this configuration cannot be run."""
        issues = []
        if not self._tol.is_valid():
            issues.append("the tolerance is not a number")
        elif self._tol.value() <= 0:
            issues.append("the tolerance must be greater than zero")
        voltages = self.resolved_voltages()
        if voltages is None:
            issues.append("the voltage list could not be read")
        elif not voltages:
            issues.append("the voltage sweep is empty")
        return issues


# =============================================================================
# SHARED
# =============================================================================

def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("hintLabel")
    label.setStyleSheet(_hint_style())
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return label


def _voltage_box(value: float, on_change: Callable[[], None],
                 minimum: float = 0.0):
    from PySide6.QtWidgets import QDoubleSpinBox

    box = QDoubleSpinBox()
    box.setDecimals(3)
    box.setRange(minimum, 2.0)
    box.setSingleStep(0.01)
    box.setValue(value)
    box.valueChanged.connect(on_change)
    box.setMaximumWidth(78)
    return box
