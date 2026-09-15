"""The settings of a GUI run, and their on-disk JSON form.

A :class:`GuiConfig` holds everything the two configuration panels edit: the
material parameters that become a ``Params`` instance, and the solver settings
that become the arguments of ``pemfc_1d.model.solve``. Defaults are read from
``Params()`` and from the signature of ``solve`` rather than restated here, so
the dialog opens showing exactly what ``run_example.py`` would run.

The same object is what File > Import/Export configuration reads and writes,
and what is dropped into each run directory as ``config.json`` so a GUI run can
be reproduced.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

from pemfc_1d.model import DEFAULT_MAX_NODES
from pemfc_1d.params import Params

from .paramfields import SWEEP_FIELD, THICKNESS_FIELD, editable_names

#: Written into the JSON so a future format change can be detected.
CONFIG_VERSION = 1

#: Defaults of the solver arguments, matching ``run_example.py``.
DEFAULT_TOL = 1e-4
DEFAULT_N_PER_REGION = 11
DEFAULT_REFINE_FACTOR = 12
DEFAULT_OUTDIR = "results"

#: Defaults of the voltage sweep, matching ``Params._default_voltage_sweep``.
DEFAULT_SWEEP_START = 1.15
DEFAULT_SWEEP_STOP = 1.00
DEFAULT_SWEEP_STEP = 0.05


def default_material() -> dict[str, Any]:
    """Every editable ``Params`` scalar at its default, plus ``L`` in metres."""
    defaults = Params()
    material: dict[str, Any] = {}
    for name in editable_names():
        if name == SWEEP_FIELD:
            continue  # the sweep is a solver setting in the GUI, not a material
        value = getattr(defaults, name)
        material[name] = ([float(v) for v in value] if name == THICKNESS_FIELD
                          else float(value))
    return material


def sweep_from_range(start: float, stop: float, step: float) -> list[float]:
    """The voltages a start/stop/step triple stands for.

    Built with the same expression as ``Params._default_voltage_sweep`` so the
    GUI's default sweep is bit-identical to the command line's, including the
    1e-9 nudge that keeps the endpoint in.
    """
    magnitude = abs(step)
    if magnitude <= 0:
        return [float(start)]
    if stop <= start:
        return [float(v) for v in np.arange(start, stop - 1e-9, -magnitude)]
    return [float(v) for v in np.arange(start, stop + 1e-9, magnitude)]


@dataclass
class SweepConfig:
    """How the voltages to solve are specified."""

    #: "range" builds them from start/stop/step; "list" uses ``voltages``.
    mode: str = "range"
    start: float = DEFAULT_SWEEP_START
    stop: float = DEFAULT_SWEEP_STOP
    step: float = DEFAULT_SWEEP_STEP
    voltages: list[float] = field(
        default_factory=lambda: sweep_from_range(DEFAULT_SWEEP_START,
                                                 DEFAULT_SWEEP_STOP,
                                                 DEFAULT_SWEEP_STEP))

    def resolved(self) -> list[float]:
        """The voltages this configuration actually solves, in sweep order."""
        if self.mode == "range":
            return sweep_from_range(self.start, self.stop, self.step)
        return list(self.voltages)


@dataclass
class SolverConfig:
    """The arguments passed to ``solve`` and to the convergence check."""

    tol: float = DEFAULT_TOL
    n_per_region: int = DEFAULT_N_PER_REGION
    max_nodes: int = DEFAULT_MAX_NODES
    convergence_check: bool = True
    refine_factor: int = DEFAULT_REFINE_FACTOR
    outdir: str = DEFAULT_OUTDIR


@dataclass
class GuiConfig:
    """Everything one run of the model is configured with."""

    material: dict[str, Any] = field(default_factory=default_material)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)

    # ------------------------------------------------------------ building
    def build_params(self) -> Params:
        """The ``Params`` instance this configuration describes."""
        kwargs: dict[str, Any] = {}
        for name, value in self.material.items():
            kwargs[name] = (np.asarray(value, dtype=float)
                            if name == THICKNESS_FIELD else float(value))
        kwargs[SWEEP_FIELD] = np.asarray(self.sweep.resolved(), dtype=float)
        return Params(**kwargs)

    def modified_material(self) -> dict[str, tuple[Any, Any]]:
        """Material values that differ from the defaults, as name -> (default, current)."""
        defaults = default_material()
        changed = {}
        for name, value in self.material.items():
            if name not in defaults:
                continue
            if name == THICKNESS_FIELD:
                if [float(v) for v in value] != defaults[name]:
                    changed[name] = (defaults[name], list(value))
            elif float(value) != defaults[name]:
                changed[name] = (defaults[name], float(value))
        return changed

    def equivalent_command(self) -> str:
        """The ``run_example.py`` invocation that would reproduce this run.

        Only the solver settings have command-line equivalents, so when the
        material parameters have been edited the command is annotated rather
        than presented as sufficient -- ``config.json`` in the run directory is
        what actually carries those.
        """
        voltages = " ".join(f"{v:g}" for v in self.sweep.resolved())
        parts = ["python run_example.py", f"--voltages {voltages}",
                 f"--tol {self.solver.tol:g}",
                 f"--n-per-region {self.solver.n_per_region}",
                 f"--max-nodes {self.solver.max_nodes}"]
        if self.solver.convergence_check:
            parts.append(f"--refine-factor {self.solver.refine_factor}")
        else:
            parts.append("--no-convergence-check")
        if self.solver.outdir != DEFAULT_OUTDIR:
            parts.append(f"--outdir {self.solver.outdir}")
        command = " ".join(parts)

        changed = self.modified_material()
        if changed:
            command += (f"    # NOTE: {len(changed)} material parameter(s) were "
                        f"edited in the GUI and are not on this command line; "
                        f"see config.json in this directory")
        return command

    def log_command(self) -> str:
        """The ``Command`` line recorded in ``metrics.log``.

        The run log exists to say what was actually run, so this names the GUI
        rather than presenting the reproduction command as if it had been
        typed. The equivalent command line follows it, which is what someone
        re-running the sweep without the GUI needs.
        """
        return f"run_gui.py (PySide6 front end)  |  equivalent: {self.equivalent_command()}"

    # --------------------------------------------------------------- JSON
    def to_dict(self) -> dict[str, Any]:
        return {"config_version": CONFIG_VERSION,
                "material": dict(self.material),
                "sweep": asdict(self.sweep),
                "solver": asdict(self.solver)}

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n",
                        encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuiConfig":
        """Rebuild a configuration, filling anything absent with the default.

        Unknown keys are dropped rather than raising, so a file written by a
        later version stays loadable, and a file listing only the handful of
        parameters someone cares about is a valid input.
        """
        version = data.get("config_version", CONFIG_VERSION)
        if version > CONFIG_VERSION:
            raise ValueError(
                f"configuration was written by a newer version of the GUI "
                f"(format {version}, this build understands {CONFIG_VERSION})")

        material = default_material()
        for name, value in (data.get("material") or {}).items():
            if name not in material:
                continue
            material[name] = ([float(v) for v in value]
                              if name == THICKNESS_FIELD else float(value))

        sweep = SweepConfig()
        for name, value in (data.get("sweep") or {}).items():
            if hasattr(sweep, name):
                setattr(sweep, name, value)

        solver = SolverConfig()
        for name, value in (data.get("solver") or {}).items():
            if hasattr(solver, name):
                setattr(solver, name, value)

        return cls(material=material, sweep=sweep, solver=solver)

    @classmethod
    def load(cls, path: str | Path) -> "GuiConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("a configuration file must hold a JSON object")
        return cls.from_dict(data)

    def copy(self) -> "GuiConfig":
        return replace(self, material=dict(self.material),
                       sweep=replace(self.sweep),
                       solver=replace(self.solver))
