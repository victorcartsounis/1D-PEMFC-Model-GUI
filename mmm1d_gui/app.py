"""The main window.

Everything the application does passes through here: the two configuration
panels on the left, the diagram and equations and plots on the right, and the
run itself, which follows ``run_example.py`` step for step -- solve, collect
metrics, optionally refine the mesh, then write one timestamped directory under
``results/`` holding the three figures and ``metrics.log``.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QGroupBox, QLabel,
                               QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from mmm1d.metrics import create_run_directory, write_run_log
from mmm1d.state import Region

from . import theme
from .about import AboutDialog
from .config import GuiConfig
from .dataio import DataImportError, read_polarization_data
from .diagram import MEADiagram
from .equationview import EquationView
from .panels import MaterialPanel, SimulationPanel
from .plots import FIGURE_FILENAMES, FigureView, build_figures
from .runner import RunOutcome, SweepRunner
from .transportbar import TransportBar

WINDOW_TITLE = "1D PEM Fuel Cell Model"


class MainWindow(QMainWindow):
    """The application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1440, 900)

        self.config = GuiConfig()
        self.runner = SweepRunner(self)
        self.experimental: np.ndarray | None = None
        self.outcome: RunOutcome | None = None
        self.run_directory: Path | None = None
        self.log_path: Path | None = None

        self._build_ui()
        self._build_actions()
        self._connect()
        self.set_theme(theme.active())
        self._set_running(False)
        self._status("Ready. Configure the run on the left, then press Run.")

    # =========================================================== construction
    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.material_panel = MaterialPanel()
        self.simulation_panel = SimulationPanel()
        self.config_tabs = QTabWidget()
        self.config_tabs.addTab(self.simulation_panel, "Simulation")
        self.config_tabs.addTab(self.material_panel, "Material")
        self.config_tabs.setMinimumWidth(450)
        splitter.addWidget(self.config_tabs)

        self.view_tabs = QTabWidget()
        self.view_tabs.addTab(self._build_cell_tab(), "Cell and equations")
        self.figure_views = {
            "polarization": FigureView(
                "The polarization curve appears here once a sweep has run.\n\n"
                "Cell voltage and power density against current density."),
            "potentials": FigureView(
                "The profiles of the eight quantities across the MEA appear "
                "here once a sweep has run.\n\nOne curve per cell voltage, "
                "each panel spanning only the layers where that quantity is "
                "defined."),
            "fluxes": FigureView(
                "The eight fluxes appear here once a sweep has run.\n\n"
                "The second half of each potential/flux pair."),
        }
        self.view_tabs.addTab(self.figure_views["polarization"],
                              "Polarization curve")
        self.view_tabs.addTab(self.figure_views["potentials"], "Profiles")
        self.view_tabs.addTab(self.figure_views["fluxes"], "Fluxes")
        self.view_tabs.addTab(self._build_log_tab(), "Log")
        splitter.addWidget(self.view_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 940])
        self.setCentralWidget(splitter)

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setRange(0, 0)   # indeterminate: see runner.py
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)

    def _build_cell_tab(self) -> QWidget:
        self.diagram = MEADiagram()
        self.transport_bar = TransportBar()
        self.equation_view = EquationView()

        self.cell_hint = QLabel(
            "Click a layer for the equations that govern it, or a process "
            "below to follow it across the whole cell.")
        self.cell_hint.setWordWrap(True)
        self.cell_hint.setObjectName("cellHint")

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(9)
        top_layout.addWidget(self.cell_hint)
        top_layout.addWidget(self.diagram, 1)
        top_layout.addWidget(self.transport_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(self.equation_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([370, 430])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        return container

    def _build_log_tab(self) -> QWidget:
        monospace = theme.monospace_font()

        self.progress_log = QPlainTextEdit()
        self.progress_log.setReadOnly(True)
        self.progress_log.setFont(monospace)
        self.progress_log.setPlaceholderText(
            "Progress of the current run appears here.")

        self.metrics_log = QPlainTextEdit()
        self.metrics_log.setReadOnly(True)
        self.metrics_log.setFont(monospace)
        self.metrics_log.setPlaceholderText(
            "metrics.log appears here once a run has finished. It records what "
            "was run, when, against which revision of the code, and how far "
            "the current density moves when the mesh is refined.")
        self.metrics_log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(_titled("Run progress", self.progress_log))
        splitter.addWidget(_titled("metrics.log", self.metrics_log))
        splitter.setSizes([220, 520])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        return container

    def _build_actions(self) -> None:
        self.action_import_data = QAction("Import measured data...", self)
        self.action_import_data.setToolTip(
            "Overlay a two-column file of current density and cell voltage on "
            "the polarization curve.")
        self.action_clear_data = QAction("Clear imported data", self)
        self.action_import_config = QAction("Import configuration...", self)
        self.action_export_config = QAction("Export configuration...", self)
        self.action_export_log = QAction("Export log...", self)
        self.action_export_figures = QAction("Export figures...", self)
        self.action_open_folder = QAction("Open run folder", self)
        self.action_quit = QAction("Quit", self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)

        self.action_run = QAction("Run simulation", self)
        self.action_run.setShortcut(QKeySequence("Ctrl+R"))
        self.action_stop = QAction("Stop", self)
        self.action_reset = QAction("Reset all settings to defaults", self)
        self.action_about = QAction("About", self)

        self.action_light = QAction("Light", self, checkable=True, checked=True)
        self.action_dark = QAction("Dark", self, checkable=True)
        appearance = QActionGroup(self)
        appearance.addAction(self.action_light)
        appearance.addAction(self.action_dark)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.action_import_data)
        file_menu.addAction(self.action_clear_data)
        file_menu.addSeparator()
        file_menu.addAction(self.action_import_config)
        file_menu.addAction(self.action_export_config)
        file_menu.addSeparator()
        file_menu.addAction(self.action_export_log)
        file_menu.addAction(self.action_export_figures)
        file_menu.addAction(self.action_open_folder)
        file_menu.addSeparator()
        file_menu.addAction(self.action_quit)

        run_menu = self.menuBar().addMenu("&Simulation")
        run_menu.addAction(self.action_run)
        run_menu.addAction(self.action_stop)
        run_menu.addSeparator()
        run_menu.addAction(self.action_reset)

        view_menu = self.menuBar().addMenu("&View")
        appearance_menu = view_menu.addMenu("Appearance")
        appearance_menu.addAction(self.action_light)
        appearance_menu.addAction(self.action_dark)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.action_about)

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addAction(self.action_import_data)
        toolbar.addSeparator()
        toolbar.addAction(self.action_run)
        toolbar.addAction(self.action_stop)
        toolbar.addSeparator()
        toolbar.addAction(self.action_export_log)
        toolbar.addAction(self.action_export_figures)

        # Run is the one action the window exists for, so it is the only one
        # painted in the accent colour.
        run_button = toolbar.widgetForAction(self.action_run)
        if run_button is not None:
            run_button.setObjectName("primaryAction")

    def _connect(self) -> None:
        self.diagram.layerClicked.connect(self._show_layer)
        self.transport_bar.transportClicked.connect(self._show_transport)

        self.action_import_data.triggered.connect(self.import_data)
        self.action_clear_data.triggered.connect(self.clear_data)
        self.action_import_config.triggered.connect(self.import_config)
        self.action_export_config.triggered.connect(self.export_config)
        self.action_export_log.triggered.connect(self.export_log)
        self.action_export_figures.triggered.connect(self.export_figures)
        self.action_open_folder.triggered.connect(self.open_run_folder)
        self.action_quit.triggered.connect(self.close)
        self.action_run.triggered.connect(self.run_simulation)
        self.action_stop.triggered.connect(self.runner.cancel)
        self.action_reset.triggered.connect(self.reset_settings)
        self.action_about.triggered.connect(self.show_about)
        self.action_light.triggered.connect(
            lambda: self.set_theme(theme.LIGHT))
        self.action_dark.triggered.connect(
            lambda: self.set_theme(theme.DARK))

        self.runner.message.connect(self.append_log)
        self.runner.stage.connect(self._status)
        self.runner.finished.connect(self._on_finished)
        self.runner.failed.connect(self._on_failed)
        self.runner.stateChanged.connect(self._set_running)

        self.material_panel.changed.connect(self._refresh_title)
        self.material_panel.changed.connect(self._on_material_changed)
        self.simulation_panel.changed.connect(self._refresh_title)

    # ================================================== diagram and equations
    def _show_layer(self, value: int) -> None:
        self.equation_view.show_layer(Region(value))
        self.transport_bar.select(None)

    def _show_transport(self, row: int) -> None:
        self.equation_view.show_transport(row)
        self.diagram.select(None)

    # ============================================================= appearance
    def set_theme(self, palette: theme.Palette) -> None:
        """Repaint the whole interface in ``palette``."""
        application = QApplication.instance()
        if application is None:
            return
        theme.apply(application, palette)
        self.action_light.setChecked(not palette.dark)
        self.action_dark.setChecked(palette.dark)

        self.cell_hint.setStyleSheet(
            f"color: {palette.text_muted}; background: transparent;")
        self.diagram.refresh_theme()
        self.transport_bar.refresh_theme()
        self.equation_view.refresh_theme()
        self.material_panel.refresh_theme()
        self.simulation_panel.refresh_theme()
        for view in self.figure_views.values():
            view.refresh_theme()

    # ================================================================ running
    def run_simulation(self) -> None:
        """Validate the panels, then hand the settings to the worker."""
        if self.runner.busy:
            return

        problems = list(self.simulation_panel.problems())
        invalid = self.material_panel.invalid_fields()
        if invalid:
            problems.append("these material fields are not numbers: "
                            + ", ".join(invalid))
        if problems:
            QMessageBox.warning(
                self, "Cannot run yet",
                "The configuration has to be fixed first:\n\n"
                + "\n".join(f"  • {problem}" for problem in problems))
            return

        self.simulation_panel.apply_to(self.config)
        self.material_panel.apply_to(self.config)
        self._sync_diagram()

        for view in self.figure_views.values():
            view.clear()   # figures are closed when the next set is built
        self.outcome = None
        self.run_directory = None
        self.log_path = None
        self.metrics_log.clear()

        self.progress_log.clear()
        self.append_log("=" * 68)
        self.append_log(self.config.equivalent_command())
        self.append_log("=" * 68)
        self.runner.start(self.config.copy())

    def _on_finished(self, outcome: RunOutcome) -> None:
        """Build the figures and write the run directory."""
        self.outcome = outcome
        self._status("Drawing figures...")
        QApplication.processEvents()

        figures = build_figures(outcome.result, self.experimental)
        for key, view in self.figure_views.items():
            view.set_figure(figures[key])

        try:
            self._save_run(outcome, figures)
        except OSError as error:
            self.append_log(f"Could not write the run directory: {error}")
            QMessageBox.warning(
                self, "Results not saved",
                f"The sweep finished and the figures are shown, but writing "
                f"the run directory failed:\n\n{error}")
            self._status("Finished, but the results could not be saved.")
            return

        worst = outcome.metrics.worst_relative_change
        certified = (f"worst |dI|/I {worst * 100:.3f}%"
                     if np.isfinite(worst) else "no convergence check")
        self._status(f"Finished: {outcome.solved_voltages} voltage(s) in "
                     f"{outcome.elapsed_seconds:.1f} s, {certified}. "
                     f"Saved to {self.run_directory}/")
        self.view_tabs.setCurrentWidget(self.figure_views["polarization"])
        self._update_export_actions()

    def _save_run(self, outcome: RunOutcome, figures: dict) -> None:
        """Write the run directory, in the layout ``run_example.py`` uses."""
        directory = create_run_directory(outcome.config.solver.outdir)
        for key, filename in FIGURE_FILENAMES.items():
            figures[key].savefig(directory / filename, dpi=150)
        log_path = write_run_log(outcome.metrics, directory,
                                 command=outcome.config.log_command())
        # Sidecar, so a GUI run whose material parameters were edited can be
        # reproduced -- the command line above carries only the solver settings.
        outcome.config.save(directory / "config.json")

        self.run_directory = directory
        self.log_path = log_path
        self.metrics_log.setPlainText(log_path.read_text(encoding="utf-8"))
        self.append_log(f"Run saved to {directory}/ "
                        f"(figures, {log_path.name} and config.json)")

    def _on_failed(self, message: str) -> None:
        self.append_log(f"FAILED: {message}")
        self._status("The run failed.")
        QMessageBox.critical(self, "The run failed", message)

    def _set_running(self, running: bool) -> None:
        self.action_run.setEnabled(not running)
        self.action_stop.setEnabled(running)
        self.action_import_config.setEnabled(not running)
        self.action_reset.setEnabled(not running)
        self.config_tabs.setEnabled(not running)
        self.progress.setVisible(running)
        if running:
            self.action_stop.setToolTip(
                "Stop after the sweep in progress. solve_bvp cannot be "
                "interrupted part way, so this takes effect by skipping the "
                "convergence check.")
        self._update_export_actions()

    def _update_export_actions(self) -> None:
        has_log = self.log_path is not None
        has_run = self.run_directory is not None
        self.action_export_log.setEnabled(has_log)
        self.action_export_figures.setEnabled(has_run)
        self.action_open_folder.setEnabled(has_run)
        self.action_clear_data.setEnabled(self.experimental is not None)

    # ============================================================ import data
    def import_data(self) -> None:
        """Load measured polarization data to overlay on the curve."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import measured polarization data", "",
            "Data files (*.csv *.txt *.dat);;All files (*)")
        if not path:
            return
        try:
            data, note = read_polarization_data(path)
        except (DataImportError, OSError, UnicodeDecodeError) as error:
            QMessageBox.warning(
                self, "Could not import the file",
                f"{error}\n\nExpected two columns: current density in A/cm^2 "
                f"and cell voltage in V, separated by commas, semicolons, "
                f"tabs or spaces. A header row is optional.")
            return

        self.experimental = data
        self.append_log(f"Imported {Path(path).name}: {note}")
        self.append_log("No agreement metric is computed from it: the overlay "
                        "is a visual comparison only.")
        self._status(f"Imported {len(data)} points from {Path(path).name}. "
                     f"They are drawn on the polarization curve.")
        self._update_export_actions()

        if self.outcome is not None:
            # Redraw so the overlay appears without needing another sweep.
            for view in self.figure_views.values():
                view.clear()
            figures = build_figures(self.outcome.result, self.experimental)
            for key, view in self.figure_views.items():
                view.set_figure(figures[key])

    def clear_data(self) -> None:
        self.experimental = None
        self._status("Imported data cleared.")
        self._update_export_actions()
        if self.outcome is not None:
            for view in self.figure_views.values():
                view.clear()
            figures = build_figures(self.outcome.result, None)
            for key, view in self.figure_views.items():
                view.set_figure(figures[key])

    # ======================================================== import / export
    def import_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import configuration", "", "JSON files (*.json);;All files (*)")
        if not path:
            return
        try:
            config = GuiConfig.load(path)
        except (ValueError, OSError, UnicodeDecodeError) as error:
            QMessageBox.warning(self, "Could not import the configuration",
                                str(error))
            return
        self.config = config
        self.material_panel.load_from(config)
        self.simulation_panel.load_from(config)
        self._sync_diagram()
        self._status(f"Configuration loaded from {Path(path).name}.")
        self._refresh_title()

    def export_config(self) -> None:
        self.simulation_panel.apply_to(self.config)
        self.material_panel.apply_to(self.config)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export configuration", "pemfc_config.json",
            "JSON files (*.json);;All files (*)")
        if not path:
            return
        try:
            self.config.save(path)
        except OSError as error:
            QMessageBox.warning(self, "Could not save", str(error))
            return
        self._status(f"Configuration written to {path}.")

    def export_log(self) -> None:
        """Save a copy of the finished run's ``metrics.log``."""
        if self.log_path is None:
            return
        suggested = (f"{self.run_directory.name}_metrics.log"
                     if self.run_directory else "metrics.log")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export log", suggested, "Log files (*.log);;All files (*)")
        if not path:
            return
        try:
            Path(path).write_text(
                self.metrics_log.toPlainText(), encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, "Could not save the log", str(error))
            return
        self._status(f"Log written to {path}.")

    def export_figures(self) -> None:
        """Copy the run's three figures somewhere else."""
        if self.run_directory is None:
            return
        target = QFileDialog.getExistingDirectory(
            self, "Directory to copy the figures into")
        if not target:
            return
        copied = []
        try:
            for filename in FIGURE_FILENAMES.values():
                source = self.run_directory / filename
                if source.exists():
                    shutil.copy2(source, Path(target) / filename)
                    copied.append(filename)
        except OSError as error:
            QMessageBox.warning(self, "Could not copy the figures", str(error))
            return
        self._status(f"Copied {len(copied)} figure(s) to {target}.")

    def open_run_folder(self) -> None:
        if self.run_directory is None:
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.run_directory.resolve())))

    # ================================================================ general
    def reset_settings(self) -> None:
        answer = QMessageBox.question(
            self, "Reset settings",
            "Put every material parameter and every solver setting back to "
            "the values the model ships with?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.config = GuiConfig()
        self.material_panel.load_from(self.config)
        self.simulation_panel.load_from(self.config)
        self._sync_diagram()
        self._status("Settings reset to the model's defaults.")
        self._refresh_title()

    def show_about(self) -> None:
        AboutDialog(WINDOW_TITLE, self).exec()

    def _on_material_changed(self) -> None:
        """Keep the diagram showing the geometry that is actually configured."""
        if self.material_panel.invalid_fields():
            return
        self.material_panel.apply_to(self.config)
        self._sync_diagram()

    def append_log(self, text: str) -> None:
        self.progress_log.appendPlainText(text)
        scrollbar = self.progress_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _sync_diagram(self) -> None:
        """Redraw the cell for the thicknesses currently configured."""
        try:
            self.diagram.set_params(self.config.build_params())
        except (TypeError, ValueError):
            pass   # a half-typed field; the diagram keeps the last good shape

    def _refresh_title(self) -> None:
        modified = self.material_panel.modified_count()
        self.setWindowTitle(
            f"{WINDOW_TITLE} — {modified} material parameter(s) changed"
            if modified else WINDOW_TITLE)

    def closeEvent(self, event) -> None:  # noqa: D102 - Qt override
        if not self.runner.busy:
            event.accept()
            return
        answer = QMessageBox.question(
            self, "A sweep is still running",
            "The solver cannot be interrupted part way. Close anyway and "
            "abandon the run?")
        event.setAccepted(answer == QMessageBox.StandardButton.Yes)


def _titled(title: str, widget: QWidget) -> QWidget:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.addWidget(widget)
    return box


def main() -> int:
    """Start the application and run it until the window is closed."""
    application = QApplication(sys.argv)
    application.setApplicationName(WINDOW_TITLE)
    # Before the window is built, so every widget is created already dressed
    # rather than being restyled a frame later.
    theme.apply(application, theme.LIGHT)
    window = MainWindow()
    window.show()
    return application.exec()
