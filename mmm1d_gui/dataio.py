"""Reading measured polarization data for comparison against a sweep.

The model has no validation code: agreement with measurements is a separate
question from the numerical convergence the run log reports, and the repository
does not yet carry the measurements it would need. What this module does is the
part that can be done honestly -- read a two-column file and hand it to the
polarization plot as an overlay, so a run can be eyeballed against data.

No agreement metric is computed. When one is added it belongs beside the
convergence metrics in ``mmm1d.metrics``, reported per region of the curve
(kinetic, ohmic, mass transport), because a whole-curve error hides a missed
limiting current.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

#: Header words that identify a current density column and a voltage column.
_CURRENT_WORDS = ("i ", "i[", "i_", "current", "j ", "j[", "j_", "a/cm")
_VOLTAGE_WORDS = ("u ", "u[", "u_", "voltage", "volt", "v ", "v[", "v_", "e_cell")


class DataImportError(ValueError):
    """Raised when a file cannot be read as polarization data."""


def read_polarization_data(path: str | Path) -> tuple[np.ndarray, str]:
    """Read current density and cell voltage from a two-column text file.

    Accepts comma, semicolon, tab or whitespace separators, ignores blank
    lines and lines starting with ``#``, and tolerates one header row. The
    column order is taken from that header when it names them; otherwise the
    file is read as current density first, voltage second.

    Returns an (n, 2) array of ``[I in A/cm^2, U in V]`` and a sentence
    describing how the file was interpreted, which the caller shows to the
    user so a wrong guess is visible rather than silent.
    """
    path = Path(path)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        raise DataImportError(f"{path.name} holds no data rows.")

    delimiter = _sniff_delimiter(lines[0])
    rows = list(csv.reader(lines, delimiter=delimiter,
                           skipinitialspace=True)) if delimiter else \
        [line.split() for line in lines]

    swapped = False
    note = "read as current density [A/cm^2] first, cell voltage [V] second"
    first_data_line = 1
    if _looks_like_a_header(rows[0]):
        header = rows.pop(0)
        swapped = _header_says_voltage_first(header)
        note = (f"column order taken from the header "
                f"{', '.join(c.strip() for c in header[:2])}")
        first_data_line = 2
        if not rows:
            raise DataImportError(
                f"{path.name}: the first line holds no numbers, so it was "
                f"taken as a header -- but no data rows follow it.")

    values = []
    for number, row in enumerate(rows, start=first_data_line):
        cells = [cell for cell in row if cell.strip()]
        if len(cells) < 2:
            raise DataImportError(
                f"{path.name} line {number}: expected two columns, found "
                f"{len(cells)}.")
        try:
            values.append([float(cells[0]), float(cells[1])])
        except ValueError as error:
            raise DataImportError(
                f"{path.name} line {number}: {error}") from error

    data = np.asarray(values, dtype=float)
    if swapped:
        data = data[:, ::-1]
    if not np.all(np.isfinite(data)):
        raise DataImportError(f"{path.name} holds non-finite values.")

    return data, f"{len(data)} points, {note}."


def _sniff_delimiter(line: str) -> str | None:
    for candidate in (",", ";", "\t"):
        if candidate in line:
            return candidate
    return None


def _looks_like_a_header(row: list[str]) -> bool:
    """Whether a row names the columns rather than holding data.

    A row counts as a header only when *none* of its first two cells is a
    number. A row where one cell parses and the other does not is a damaged
    data row, and skipping it as a header would drop a measurement silently.
    """
    cells = [cell for cell in row if cell.strip()][:2]
    if not cells:
        return True
    for cell in cells:
        try:
            float(cell)
        except ValueError:
            continue
        return False
    return True


def _header_says_voltage_first(header: list[str]) -> bool:
    """Whether a header row names voltage before current density."""
    if len(header) < 2:
        return False
    first = header[0].strip().lower() + " "
    second = header[1].strip().lower() + " "
    first_is_voltage = any(word in first for word in _VOLTAGE_WORDS)
    second_is_current = any(word in second for word in _CURRENT_WORDS)
    return first_is_voltage and second_is_current
