"""A presentable catalogue of the editable fields of ``mmm1d.params.Params``.

``Params`` is a frozen dataclass whose fields carry their units and meanings
in comments, which the editor cannot read. This module restates them as data:
which group a field belongs to, what to call it on screen, and which unit to
print beside it.

The catalogue is checked against the dataclass at import time by
:func:`uncatalogued_fields`, so a field added to ``Params`` shows up in the
editor as soon as it exists rather than being silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Iterator

from mmm1d.params import Params

#: Field holding the five layer thicknesses; edited as five boxes in microns.
THICKNESS_FIELD = "L"
#: Field holding the default voltage sweep; edited on the simulation panel.
SWEEP_FIELD = "U_list"


@dataclass(frozen=True)
class ParamField:
    """One editable scalar of ``Params``."""

    name: str
    label: str
    unit: str = ""
    tooltip: str = ""


@dataclass(frozen=True)
class ParamGroup:
    """A titled block of fields, mirroring the sections of ``params.py``."""

    title: str
    description: str
    entries: tuple[ParamField, ...]


PARAM_GROUPS: tuple[ParamGroup, ...] = (
    ParamGroup(
        "Operating conditions",
        "What the cell is being run at. These are the settings an experiment "
        "would actually vary.",
        (
            ParamField("P_A", "Anode channel pressure", "Pa"),
            ParamField("P_C", "Cathode channel pressure", "Pa"),
            ParamField("RH_A", "Anode relative humidity", "-",
                       "Sets the vapour mass fraction in the anode channel."),
            ParamField("RH_C", "Cathode relative humidity", "-",
                       "Sets the vapour and oxygen mass fractions in the "
                       "cathode channel."),
            ParamField("s_C", "Saturation, cathode GDL/channel", "-",
                       "Also fixes the immobile saturation s_im, which is "
                       "derived from it."),
            ParamField("alpha_O2", "O₂ fraction in the dry oxidant", "-",
                       "0.21 for air; raise it for an oxygen-fed cell."),
            ParamField("T_A_celsius", "Anode plate temperature", "degC"),
            ParamField("T_C_celsius", "Cathode plate temperature", "degC"),
            ParamField("T_ref_celsius", "Correlation reference temp.", "degC",
                       "The temperature the Arrhenius corrections are "
                       "referred to; not an operating condition."),
        )),
    ParamGroup(
        "Layer thicknesses",
        "The five layers of the MEA, anode to cathode.",
        ()),  # filled in by the editor from THICKNESS_FIELD
    ParamGroup(
        "Electrode and membrane materials",
        "Structural and transport properties of the porous layers and the "
        "ionomer.",
        (
            ParamField("a_ACL", "Active area density, anode CL", "1/m"),
            ParamField("a_CCL", "Active area density, cathode CL", "1/m"),
            ParamField("eps_i_CL", "Ionomer fraction in the dry CL", "-"),
            ParamField("eps_p_GDL", "GDL porosity", "-"),
            ParamField("eps_p_CL", "CL porosity", "-"),
            ParamField("tau_GDL", "GDL pore tortuosity", "-"),
            ParamField("tau_CL", "CL pore tortuosity", "-"),
            ParamField("kappa_GDL", "GDL absolute permeability", "m^2"),
            ParamField("kappa_CL", "CL absolute permeability", "m^2",
                       "Note that the cathode CL currently uses kappa_GDL in "
                       "Darcy's law; see the layer's equation panel."),
            ParamField("sigma_e_GDL", "GDL electrical conductivity", "S/m"),
            ParamField("sigma_e_CL", "CL electrical conductivity", "S/m"),
            ParamField("k_GDL", "GDL thermal conductivity", "W/(m K)"),
            ParamField("k_CL", "CL thermal conductivity", "W/(m K)"),
            ParamField("k_PEM", "PEM thermal conductivity", "W/(m K)"),
            ParamField("V_m", "Molar volume, dry membrane", "m^3/mol"),
        )),
    ParamGroup(
        "Electrochemistry",
        "Kinetics of the two half reactions.",
        (
            ParamField("beta_HOR", "HOR symmetry factor", "-"),
            ParamField("beta_ORR", "ORR symmetry factor", "-"),
            ParamField("DeltaH", "Enthalpy of formation, liquid water", "J/mol"),
            ParamField("DeltaS_HOR", "HOR reaction entropy", "J/(mol K)"),
            ParamField("DeltaS_ORR", "ORR reaction entropy", "J/(mol K)"),
        )),
    ParamGroup(
        "Water properties",
        "Phase change, liquid water and the gas phase.",
        (
            ParamField("H_ec", "Enthalpy of evaporation", "J/mol",
                       "Also used as the enthalpy of sorption H_ad, which is "
                       "derived from it."),
            ParamField("rho_liq", "Liquid water density", "kg/m^3"),
            ParamField("mu_gas", "Gas dynamic viscosity", "Pa s"),
        )),
    ParamGroup(
        "Physical constants",
        "Editable so a unit system or a constant can be varied deliberately, "
        "but there is normally no reason to touch these.",
        (
            ParamField("M_H2O", "Molar mass, water", "kg/mol"),
            ParamField("M_H2", "Molar mass, hydrogen", "kg/mol"),
            ParamField("M_N2", "Molar mass, nitrogen", "kg/mol"),
            ParamField("M_O2", "Molar mass, oxygen", "kg/mol"),
            ParamField("T_0", "Zero degrees Celsius", "K"),
            ParamField("R", "Universal gas constant", "J/(mol K)"),
            ParamField("F", "Faraday constant", "C/mol"),
            ParamField("P_ref", "Reference pressure", "Pa"),
        )),
)

#: Names of the five layers, in the order ``Params.L`` stores them.
LAYER_NAMES = ("AGDL", "ACL", "PEM", "CCL", "CGDL")


def catalogued_names() -> set[str]:
    """Every scalar field the catalogue above covers."""
    return {entry.name for group in PARAM_GROUPS for entry in group.entries}


def editable_names() -> list[str]:
    """Every constructor argument of ``Params``, in declaration order."""
    return [f.name for f in fields(Params) if f.init]


def uncatalogued_fields() -> list[str]:
    """Constructor arguments the catalogue does not mention.

    Handled separately: ``L`` and ``U_list`` have their own editors. Anything
    else returned here is a field added to ``Params`` since this catalogue was
    written, and the editor appends it to an "Other parameters" group so it is
    still reachable.
    """
    special = {THICKNESS_FIELD, SWEEP_FIELD}
    known = catalogued_names() | special
    return [name for name in editable_names() if name not in known]


def iter_scalar_fields() -> Iterator[ParamField]:
    """Every catalogued scalar, group by group."""
    for group in PARAM_GROUPS:
        yield from group.entries
