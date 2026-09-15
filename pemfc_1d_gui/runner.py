"""Running a sweep off the GUI thread.

The worker calls ``pemfc_1d.model.solve`` and the metrics helpers in exactly the
order ``run_example.py`` does, so a GUI run and a command-line run with the
same settings produce the same numbers. Nothing here touches matplotlib: the
figures are built on the GUI thread once the sweep is back, because a Qt canvas
may only be created there.

``solve_bvp`` is a single opaque call per sweep, so there is no per-voltage
progress to report and no safe point at which to interrupt it. Cancellation is
therefore cooperative and coarse: the flag is read between the sweep and the
refined solve of the convergence check, which is the one place the work can be
abandoned without leaving a half-built result behind.
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from pemfc_1d.metrics import (RunMetrics, SolverSettings, convergence_metrics,
                              sweep_metrics)
from pemfc_1d.model import SweepResult, solve

from .config import GuiConfig


@dataclass
class RunOutcome:
    """What one finished sweep hands back to the window."""

    config: GuiConfig
    result: SweepResult
    metrics: RunMetrics
    warnings: list[str]
    elapsed_seconds: float
    cancelled: bool = False

    @property
    def solved_voltages(self) -> int:
        return len(self.result.voltages)

    @property
    def requested_voltages(self) -> int:
        return len(self.config.sweep.resolved())


class SweepWorker(QObject):
    """Runs one sweep, then emits either :attr:`finished` or :attr:`failed`."""

    #: A line for the log pane, as the run reaches each stage.
    message = Signal(str)
    #: A short line for the status bar.
    stage = Signal(str)
    finished = Signal(object)   # RunOutcome
    failed = Signal(str)

    def __init__(self, config: GuiConfig) -> None:
        super().__init__()
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        """Ask the run to stop at the next point it can.

        The sweep in progress still has to finish -- see the module docstring
        -- so this takes effect by skipping the convergence check.
        """
        self._cancelled = True

    def run(self) -> None:
        """Entry point, connected to the thread's ``started`` signal."""
        try:
            self._run()
        except MemoryError:
            self.failed.emit(
                "Ran out of memory. The collocation Jacobian needs roughly "
                "0.85 GB per 1000 mesh nodes, so lowering the maximum node "
                "count, or shortening the sweep, is what makes this fit.")
        except Exception as error:  # surfaced in a dialog rather than a crash
            self.failed.emit(f"{type(error).__name__}: {error}")

    def _run(self) -> None:
        config = self._config
        params = config.build_params()
        voltages = np.asarray(config.sweep.resolved(), dtype=float)
        solver = config.solver

        self.message.emit(
            f"Solving {len(voltages)} voltage(s) from {voltages[0]:.3f} V to "
            f"{voltages[-1]:.3f} V, tol={solver.tol:g}, "
            f"max_nodes={solver.max_nodes}.")
        self.stage.emit(f"Solving {len(voltages)} voltages...")

        collected: list[str] = []
        started = time.perf_counter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = solve(voltages=voltages, tol=solver.tol,
                           n_per_region=solver.n_per_region,
                           max_nodes=solver.max_nodes, params=params)
        elapsed = time.perf_counter() - started
        collected += [str(w.message) for w in caught]
        for text in collected:
            self.message.emit(f"warning: {text}")

        if not len(result.voltages):
            self.failed.emit(
                "No voltage converged, so there is nothing to plot. The sweep "
                "has to start near open circuit -- the first voltage is the "
                "only one solved without a previous solution to start from.")
            return

        if len(result.voltages) < len(voltages):
            self.message.emit(
                f"The sweep stopped early: {len(result.voltages)} of "
                f"{len(voltages)} voltages were solved.")

        self.message.emit(f"Sweep finished in {elapsed:.1f} s.")

        requested = SolverSettings(tol=solver.tol,
                                   n_per_region=solver.n_per_region,
                                   max_nodes=solver.max_nodes,
                                   voltages=result.voltages)
        metrics = sweep_metrics(result, requested, elapsed)

        for voltage, current, power in zip(result.voltages,
                                           result.current_densities,
                                           result.power_densities):
            self.message.emit(f"  U = {voltage:6.3f} V    "
                              f"I = {current:8.4f} A/cm^2    "
                              f"P = {power:8.4f} W/cm^2")

        if solver.convergence_check and not self._cancelled:
            self.stage.emit("Refining the mesh to measure convergence...")
            self.message.emit(
                f"Re-solving on a mesh refined by {solver.refine_factor}x to "
                f"measure how far the current density moves.")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                metrics = convergence_metrics(metrics, solver.refine_factor,
                                              result.params)
            for warning in caught:
                collected.append(str(warning.message))
                self.message.emit(f"warning: {warning.message}")
            worst = metrics.worst_relative_change
            self.message.emit(
                f"Worst |dI|/I under refinement: {worst * 100:.3f}%"
                if np.isfinite(worst)
                else f"Convergence check: {metrics.convergence_note}")
        elif self._cancelled:
            metrics.convergence_note = "skipped: the run was cancelled"
            self.message.emit("Convergence check skipped: run cancelled.")

        self.finished.emit(RunOutcome(config=config, result=result,
                                      metrics=metrics, warnings=collected,
                                      elapsed_seconds=elapsed,
                                      cancelled=self._cancelled))


class SweepRunner(QObject):
    """Owns the worker and the thread it lives on."""

    message = Signal(str)
    stage = Signal(str)
    finished = Signal(object)
    failed = Signal(str)
    stateChanged = Signal(bool)   # True while a sweep is running

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: SweepWorker | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def start(self, config: GuiConfig) -> None:
        """Begin a sweep. Does nothing if one is already running."""
        if self.busy:
            return
        thread = QThread()
        worker = SweepWorker(config)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.message.connect(self.message)
        worker.stage.connect(self.stage)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)

        self._thread, self._worker = thread, worker
        self.stateChanged.emit(True)
        thread.start()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _teardown(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = self._worker = None
        self.stateChanged.emit(False)

    def _on_finished(self, outcome: RunOutcome) -> None:
        self._teardown()
        self.finished.emit(outcome)

    def _on_failed(self, message: str) -> None:
        self._teardown()
        self.failed.emit(message)
