"""The governing equations of each MEA layer, as shown when a layer is clicked.

Every equation here is a transcription of the corresponding line of
``mmm1d.model``: ``_agdl``, ``_acl``, ``_pem``, ``_ccl`` and ``_cgdl``. The
model writes each layer as a potential/flux pair -- a constitutive law giving
the flux from the gradient of the quantity, and a balance giving the divergence
of that flux from the sources acting in the layer -- so the groups below are
laid out the same way.

Where the code departs from the published formulation the note says so rather
than showing an idealised equation, because those departures are exactly what
the thesis has to account for (see ``NOTES.md``).

Reference: R. Vetter and J. O. Schumacher, *Free open reference implementation
of a two-phase PEM fuel cell model*, Comput. Phys. Commun. 234 (2019) 223-234.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mmm1d.state import ACTIVE_REGIONS, Quantity, Region


@dataclass(frozen=True)
class Equation:
    """One line of maths, with an optional caption printed underneath it."""

    latex: str
    caption: str = ""


@dataclass(frozen=True)
class EquationGroup:
    """The equations governing one quantity inside one layer."""

    title: str
    equations: tuple[Equation, ...]
    quantity: Quantity | None = None
    note: str = ""


@dataclass(frozen=True)
class LayerDoc:
    """Everything the equation panel shows for one layer."""

    region: Region
    name: str
    subtitle: str
    description: str
    groups: tuple[EquationGroup, ...]
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def quantities(self) -> tuple[Quantity, ...]:
        """The quantities the model resolves in this layer."""
        return tuple(q for q in Quantity if self.region in ACTIVE_REGIONS[q])


# =============================================================================
# SHARED CONSTITUTIVE RELATIONS
#
# Referenced from several layers; defined once so the panel cannot show two
# different versions of the same relation.
# =============================================================================

_GAS_DENSITY_ANODE = Equation(
    r"\rho_\mathrm{gas} = \frac{M_n P_\mathrm{gas}}{R\,T}, \quad "
    r"M_n = \left(\frac{w_\mathrm{H_2O}}{M_\mathrm{H_2O}} + "
    r"\frac{1 - w_\mathrm{H_2O}}{M_\mathrm{H_2}}\right)^{-1}",
    "Ideal gas mixture of hydrogen and water vapour; the hydrogen mass "
    "fraction is the closure w_H2 = 1 - w_H2O, not a state variable.")

_GAS_DENSITY_CATHODE = Equation(
    r"\rho_\mathrm{gas} = \frac{M_n P_\mathrm{gas}}{R\,T}, \quad "
    r"M_n = \left(\frac{w_\mathrm{H_2O}}{M_\mathrm{H_2O}} + "
    r"\frac{w_\mathrm{O_2}}{M_\mathrm{O_2}} + "
    r"\frac{w_\mathrm{N_2}}{M_\mathrm{N_2}}\right)^{-1}",
    "Ternary mixture; nitrogen is the closure w_N2 = 1 - w_H2O - w_O2.")

_DIFFUSIVITY_SCALING = Equation(
    r"D = D^{\,0}\,\frac{\varepsilon_p}{\tau^2}\,(1 - s)^3\,"
    r"\left(\frac{T}{T_\mathrm{ref}}\right)^{3/2}\,"
    r"\frac{P_\mathrm{ref}}{P_\mathrm{gas}}",
    "Bruggeman-type porosity and tortuosity correction, blocked by liquid "
    "water through (1 - s)^3, with the Chapman-Enskog temperature and "
    "pressure scaling.")

_BUTLER_VOLMER = Equation(
    r"i = i_0\,a\,\left[\exp\!\left(\beta\,\frac{2F}{RT}\,\eta\right) - "
    r"\exp\!\left(-(1 - \beta)\,\frac{2F}{RT}\,\eta\right)\right]",
    "Volumetric current density [A/m^3]: the area-specific Butler-Volmer "
    "rate multiplied by the active area density a of the layer.")

_SORPTION_SOURCE = Equation(
    r"S_\mathrm{ad} = \frac{k_\mathrm{ad}(\lambda, \lambda_\mathrm{eq}, T)}"
    r"{L\,V_m}\,\left(\lambda_\mathrm{eq} - \lambda\right)",
    "Vapour absorbed into (or desorbed from) the ionomer, driving lambda "
    "towards the sorption isotherm lambda_eq(RH).")

_SORPTION_ISOTHERM = Equation(
    r"\lambda_\mathrm{eq} = 0.043 + 17.81\,a_w - 39.85\,a_w^2 + 36.0\,a_w^3, "
    r"\quad a_w = \frac{x_\mathrm{H_2O}}{x_\mathrm{sat}}",
    "Nafion vapour sorption isotherm in the water activity a_w.")

_PROTON_CONDUCTIVITY = Equation(
    r"\sigma_p = \varepsilon_i^{3/2}\,116\,"
    r"\left[\max\!\left(0,\;\frac{\lambda V_w}{V_m + \lambda V_w} - 0.06\right)"
    r"\right]^{3/2} \exp\!\left[\frac{E_a}{R}"
    r"\left(\frac{1}{T_\mathrm{ref}} - \frac{1}{T}\right)\right]",
    "Percolation form: the ionomer conducts only above a water volume "
    "fraction of 0.06.")

_DISSOLVED_WATER_FLUX = Equation(
    r"j_\lambda = -\frac{D_\lambda}{V_m}\,\frac{d\lambda}{dx} + "
    r"\frac{\xi(\lambda)}{F}\,j_p, \quad \xi(\lambda) = \frac{2.5\,\lambda}{22}",
    "Back-diffusion against electro-osmotic drag: protons carry xi water "
    "molecules each from anode to cathode.")


# =============================================================================
# LAYERS
# =============================================================================

_AGDL = LayerDoc(
    region=Region.AGDL,
    name="AGDL",
    subtitle="Anode gas diffusion layer",
    description=(
        "The porous carbon layer between the anode bipolar plate and the "
        "catalyst layer. It carries electrons to the plate, conducts the "
        "reaction heat out, and feeds humidified hydrogen inwards. No "
        "reaction happens here, so every flux is divergence-free and the "
        "layer only imposes transport losses."),
    groups=(
        EquationGroup(
            "Electron transport", quantity=Quantity.PHI_E,
            equations=(
                Equation(r"j_e = -\sigma_e^\mathrm{GDL}\,\frac{d\phi_e}{dx}",
                         "Ohm's law in the solid carbon phase."),
                Equation(r"\frac{dj_e}{dx} = 0",
                         "No charge transfer: the electron current is constant "
                         "across the layer."),
            )),
        EquationGroup(
            "Heat conduction", quantity=Quantity.T,
            equations=(
                Equation(r"j_T = -k_\mathrm{GDL}\,\frac{dT}{dx}",
                         "Fourier's law."),
                Equation(r"\frac{dj_T}{dx} = -j_e\,\frac{d\phi_e}{dx}",
                         "Ohmic (Joule) heating is the only source here."),
            )),
        EquationGroup(
            "Water vapour diffusion", quantity=Quantity.W_H2O,
            equations=(
                Equation(r"j_\mathrm{H_2O} = -\rho_\mathrm{gas}\,"
                         r"D_\mathrm{H_2O}^\mathrm{A}\,"
                         r"\frac{dw_\mathrm{H_2O}}{dx} + "
                         r"\rho_\mathrm{gas}\,w_\mathrm{H_2O}\,u_\mathrm{gas}",
                         "Fickian diffusion plus advection with the bulk gas."),
                Equation(r"\frac{dj_\mathrm{H_2O}}{dx} = 0"),
                _DIFFUSIVITY_SCALING,
                _GAS_DENSITY_ANODE,
            ),
            note="D^0 = 1.24e-4 m^2/s for water vapour in hydrogen. The "
                 "saturation s is held at zero on the anode side: the model "
                 "resolves liquid water only on the cathode."),
        EquationGroup(
            "Gas momentum (Darcy)", quantity=Quantity.P_GAS,
            equations=(
                Equation(r"u_\mathrm{gas} = -\frac{\kappa_\mathrm{GDL}}"
                         r"{\mu_\mathrm{gas}}\,\frac{dP_\mathrm{gas}}{dx}",
                         "Darcy's law through the porous medium."),
                Equation(r"\frac{d(\rho u)_\mathrm{gas}}{dx} = 0",
                         "Total gas mass is conserved: nothing is consumed or "
                         "produced in this layer."),
            )),
    ),
)

_ACL = LayerDoc(
    region=Region.ACL,
    name="ACL",
    subtitle="Anode catalyst layer",
    description=(
        "Where hydrogen is oxidised. The layer is the meeting point of three "
        "phases -- carbon carrying electrons, ionomer carrying protons and "
        "dissolved water, and pores carrying gas -- so it is the first layer "
        "in which electron current is converted into proton current, and the "
        "first in which vapour is exchanged with the ionomer."),
    groups=(
        EquationGroup(
            "Hydrogen oxidation reaction (HOR)",
            equations=(
                Equation(r"\eta_\mathrm{HOR} = \phi_e - \phi_p + "
                         r"\frac{T\,\Delta S_\mathrm{HOR}}{2F} + "
                         r"\frac{RT}{2F}\,\ln\!\frac{P_\mathrm{H_2}}"
                         r"{P_\mathrm{ref}}",
                         "Overpotential measured against the local Nernst "
                         "potential of the half reaction."),
                _BUTLER_VOLMER,
                Equation(r"i_0^\mathrm{HOR}(T) = 0.27\times10^{4}\,"
                         r"\exp\!\left[\frac{16\,\mathrm{kJ/mol}}{R}"
                         r"\left(\frac{1}{T_\mathrm{ref}} - "
                         r"\frac{1}{T}\right)\right]",
                         "Exchange current density [A/m^2], Arrhenius-corrected "
                         "from the 80 degC reference."),
                Equation(r"S_F = \frac{i}{2F}",
                         "Faradaic source [mol/(m^3 s)] shared by the mass and "
                         "heat balances."),
            ),
            note="HOR is fast: the anode overpotential stays small, which is "
                 "why the polarization curve is dominated by the cathode."),
        EquationGroup(
            "Electron transport", quantity=Quantity.PHI_E,
            equations=(
                Equation(r"j_e = -\sigma_e^\mathrm{CL}\,\frac{d\phi_e}{dx}"),
                Equation(r"\frac{dj_e}{dx} = -i",
                         "Electron current is consumed at the rate protons "
                         "are produced."),
            )),
        EquationGroup(
            "Proton transport", quantity=Quantity.PHI_P,
            equations=(
                Equation(r"j_p = -\sigma_p(\varepsilon_i^\mathrm{CL}, "
                         r"\lambda, T)\,\frac{d\phi_p}{dx}"),
                Equation(r"\frac{dj_p}{dx} = +i"),
                _PROTON_CONDUCTIVITY,
            ),
            note="The conductivity depends on lambda, which is why drying the "
                 "ionomer shows up directly as an ohmic loss."),
        EquationGroup(
            "Heat conduction", quantity=Quantity.T,
            equations=(
                Equation(r"j_T = -k_\mathrm{CL}\,\frac{dT}{dx}"),
                Equation(r"\frac{dj_T}{dx} = -j_e\,\frac{d\phi_e}{dx} - "
                         r"j_p\,\frac{d\phi_p}{dx} + i\,\eta - "
                         r"S_F\,T\,\Delta S_\mathrm{HOR} + "
                         r"H_\mathrm{ad}\,S_\mathrm{ad}",
                         "Joule heating in both conducting phases, activation "
                         "loss, reversible reaction entropy and the latent heat "
                         "of sorption."),
            )),
        EquationGroup(
            "Dissolved water transport", quantity=Quantity.LAMBDA,
            equations=(
                _DISSOLVED_WATER_FLUX,
                Equation(r"\frac{dj_\lambda}{dx} = S_\mathrm{ad}"),
                _SORPTION_SOURCE,
                _SORPTION_ISOTHERM,
            ),
            note="k_ad switches discontinuously between absorption and "
                 "desorption at lambda = lambda_eq. That switch is the single "
                 "point that carries the largest collocation residual in the "
                 "whole domain -- see the tolerance warnings in the run log."),
        EquationGroup(
            "Water vapour diffusion", quantity=Quantity.W_H2O,
            equations=(
                Equation(r"j_\mathrm{H_2O} = -\rho_\mathrm{gas}\,"
                         r"D_\mathrm{H_2O}^\mathrm{A}\,"
                         r"\frac{dw_\mathrm{H_2O}}{dx} + "
                         r"\rho_\mathrm{gas}\,w_\mathrm{H_2O}\,u_\mathrm{gas}"),
                Equation(r"\frac{dj_\mathrm{H_2O}}{dx} = "
                         r"-M_\mathrm{H_2O}\,S_\mathrm{ad}",
                         "Vapour leaves the pores exactly as fast as the "
                         "ionomer absorbs it."),
                _GAS_DENSITY_ANODE,
            )),
        EquationGroup(
            "Gas momentum (Darcy)", quantity=Quantity.P_GAS,
            equations=(
                Equation(r"u_\mathrm{gas} = -\frac{\kappa_\mathrm{CL}}"
                         r"{\mu_\mathrm{gas}}\,\frac{dP_\mathrm{gas}}{dx}"),
                Equation(r"\frac{d(\rho u)_\mathrm{gas}}{dx} = "
                         r"-M_\mathrm{H_2O}\,S_\mathrm{ad} - "
                         r"M_\mathrm{H_2}\,S_F",
                         "Gas mass is lost to sorption and to the hydrogen "
                         "consumed by the reaction."),
            )),
    ),
)

_PEM = LayerDoc(
    region=Region.PEM,
    name="PEM",
    subtitle="Polymer electrolyte membrane",
    description=(
        "The ionomer separator. It is a pure transport layer -- no reaction, "
        "no pores, no gas -- resolving only the three quantities the ionomer "
        "itself carries: protons, heat and dissolved water. Its proton "
        "resistance is the main ohmic loss of the cell, and because that "
        "resistance depends on lambda, membrane hydration couples the "
        "cathode's water production back to the cell's ohmic behaviour."),
    groups=(
        EquationGroup(
            "Proton transport", quantity=Quantity.PHI_P,
            equations=(
                Equation(r"j_p = -\sigma_p(1, \lambda, T)\,\frac{d\phi_p}{dx}",
                         "Pure ionomer, so the volume fraction is 1 rather "
                         "than the catalyst layer's eps_i."),
                Equation(r"\frac{dj_p}{dx} = 0",
                         "No charge transfer: the proton current crosses the "
                         "membrane unchanged."),
                _PROTON_CONDUCTIVITY,
            )),
        EquationGroup(
            "Heat conduction", quantity=Quantity.T,
            equations=(
                Equation(r"j_T = -k_\mathrm{PEM}\,\frac{dT}{dx}"),
                Equation(r"\frac{dj_T}{dx} = -j_p\,\frac{d\phi_p}{dx}",
                         "Joule heating from the proton current alone -- there "
                         "is no electronic phase here."),
            )),
        EquationGroup(
            "Dissolved water transport", quantity=Quantity.LAMBDA,
            equations=(
                _DISSOLVED_WATER_FLUX,
                Equation(r"\frac{dj_\lambda}{dx} = 0",
                         "Water is neither absorbed nor produced inside the "
                         "membrane; it only passes through."),
            ),
            note="The balance of electro-osmotic drag (anode to cathode) "
                 "against back-diffusion (cathode to anode) decides whether "
                 "the anode side dries out at high current."),
    ),
)

_CCL = LayerDoc(
    region=Region.CCL,
    name="CCL",
    subtitle="Cathode catalyst layer",
    description=(
        "Where oxygen is reduced and product water appears. This is the layer "
        "that limits the cell: the ORR is sluggish, so it sets the activation "
        "loss, and oxygen has to reach it through a GDL that the same reaction "
        "is filling with water. It is also the only layer carrying all eight "
        "quantities at once."),
    groups=(
        EquationGroup(
            "Oxygen reduction reaction (ORR)",
            equations=(
                Equation(r"\eta_\mathrm{ORR} = "
                         r"-\frac{\Delta H - T\,\Delta S_\mathrm{ORR}}{2F} + "
                         r"\frac{RT}{4F}\,\ln\!\frac{P_\mathrm{O_2}}"
                         r"{P_\mathrm{ref}} - (\phi_e - \phi_p)",
                         "The first term is the reversible cell potential from "
                         "the enthalpy and entropy of reaction."),
                _BUTLER_VOLMER,
                Equation(r"i_0^\mathrm{ORR}(T, P_\mathrm{O_2}) = "
                         r"2.47\times10^{-4}\,"
                         r"\left(\frac{P_\mathrm{O_2}}{P_\mathrm{ref}}\right)"
                         r"^{0.54}\exp\!\left[\frac{67\,\mathrm{kJ/mol}}{R}"
                         r"\left(\frac{1}{T_\mathrm{ref}} - "
                         r"\frac{1}{T}\right)\right]",
                         "Eight orders of magnitude below the HOR exchange "
                         "current density -- the reason the cathode dominates "
                         "the polarization curve."),
                Equation(r"S_F = \frac{i}{2F}"),
            )),
        EquationGroup(
            "Electron transport", quantity=Quantity.PHI_E,
            equations=(
                Equation(r"j_e = -\sigma_e^\mathrm{CL}\,\frac{d\phi_e}{dx}"),
                Equation(r"\frac{dj_e}{dx} = +i",
                         "Sign mirrors the anode: here electron current is "
                         "produced as proton current is consumed."),
            )),
        EquationGroup(
            "Proton transport", quantity=Quantity.PHI_P,
            equations=(
                Equation(r"j_p = -\sigma_p(\varepsilon_i^\mathrm{CL}, "
                         r"\lambda, T)\,\frac{d\phi_p}{dx}"),
                Equation(r"\frac{dj_p}{dx} = -i"),
            )),
        EquationGroup(
            "Heat conduction", quantity=Quantity.T,
            equations=(
                Equation(r"j_T = -k_\mathrm{CL}\,\frac{dT}{dx}"),
                Equation(r"\frac{dj_T}{dx} = -j_e\,\frac{d\phi_e}{dx} - "
                         r"j_p\,\frac{d\phi_p}{dx} + i\,\eta - "
                         r"S_F\,T\,\Delta S_\mathrm{ORR} + "
                         r"H_\mathrm{ad}\,S_\mathrm{ad} + "
                         r"H_\mathrm{ec}\,S_\mathrm{ec}",
                         "The dominant heat source in the cell: the ORR "
                         "entropy term alone is about -163 J/(mol K)."),
            )),
        EquationGroup(
            "Dissolved water transport", quantity=Quantity.LAMBDA,
            equations=(
                _DISSOLVED_WATER_FLUX,
                Equation(r"\frac{dj_\lambda}{dx} = S_F + S_\mathrm{ad}",
                         "Product water enters the ionomer directly, on top of "
                         "the sorption exchange with the pores."),
                _SORPTION_SOURCE,
            )),
        EquationGroup(
            "Water vapour diffusion", quantity=Quantity.W_H2O,
            equations=(
                Equation(r"j_\mathrm{H_2O} = -\rho_\mathrm{gas}\,"
                         r"D_\mathrm{H_2O}^\mathrm{C}\,"
                         r"\frac{dw_\mathrm{H_2O}}{dx} + "
                         r"\rho_\mathrm{gas}\,w_\mathrm{H_2O}\,u_\mathrm{gas}"),
                Equation(r"\frac{dj_\mathrm{H_2O}}{dx} = "
                         r"-M_\mathrm{H_2O}\,(S_\mathrm{ec} + S_\mathrm{ad})"),
                _GAS_DENSITY_CATHODE,
            ),
            note="D^0 = 0.36e-4 m^2/s for water vapour in air."),
        EquationGroup(
            "Oxygen diffusion", quantity=Quantity.W_O2,
            equations=(
                Equation(r"j_\mathrm{O_2} = -\rho_\mathrm{gas}\,"
                         r"D_\mathrm{O_2}\,\frac{dw_\mathrm{O_2}}{dx} + "
                         r"\rho_\mathrm{gas}\,w_\mathrm{O_2}\,u_\mathrm{gas}"),
                Equation(r"\frac{dj_\mathrm{O_2}}{dx} = "
                         r"-\frac{M_\mathrm{O_2}\,S_F}{2}",
                         "Half a mole of oxygen per mole of water formed."),
                _DIFFUSIVITY_SCALING,
            ),
            note="D^0 = 0.28e-4 m^2/s. This is the transport that bends the "
                 "polarization curve over at high current."),
        EquationGroup(
            "Liquid water transport", quantity=Quantity.SATURATION,
            equations=(
                Equation(r"u_\mathrm{liq} = -\frac{\kappa\,"
                         r"\kappa_\mathrm{rel}(s)}{\mu_\mathrm{liq}(T)}\,"
                         r"\frac{dP_\mathrm{liq}}{dx}",
                         "Darcy's law for the liquid phase."),
                Equation(r"\frac{d(\rho u)_\mathrm{liq}}{dx} = "
                         r"M_\mathrm{H_2O}\,S_\mathrm{ec}"),
                Equation(r"P_\mathrm{c} = P_\mathrm{liq} - P_\mathrm{gas} = "
                         r"-0.00011\,e^{-44.02(s - 0.496)} + "
                         r"278.3\,e^{8.103(s - 0.496)} - 191.8",
                         "The capillary pressure-saturation curve, inverted "
                         "numerically to get s from the state variable P_liq."),
            )),
        EquationGroup(
            "Gas momentum (Darcy)", quantity=Quantity.P_GAS,
            equations=(
                Equation(r"u_\mathrm{gas} = -\frac{\kappa}{\mu_\mathrm{gas}}\,"
                         r"\frac{dP_\mathrm{gas}}{dx}"),
                Equation(r"\frac{d(\rho u)_\mathrm{gas}}{dx} = "
                         r"-M_\mathrm{H_2O}\,(S_\mathrm{ec} + S_\mathrm{ad}) - "
                         r"\frac{M_\mathrm{O_2}\,S_F}{2}"),
            )),
    ),
    caveats=(
        "Phase change is switched off in this version: S_ec is identically "
        "zero, so the H_ec S_ec heat source and the liquid water source above "
        "both vanish and liquid water is never created or destroyed.",
        "Darcy's law in this layer uses the GDL permeability kappa_GDL "
        "(6.15e-12 m^2) rather than kappa_CL (1e-13 m^2) -- a factor of about "
        "60 -- for both the gas and the liquid pressure gradient. This follows "
        "the reference implementation and is still to be checked against the "
        "published formulation.",
    ),
)

_CGDL = LayerDoc(
    region=Region.CGDL,
    name="CGDL",
    subtitle="Cathode gas diffusion layer",
    description=(
        "The porous layer between the catalyst layer and the cathode bipolar "
        "plate. It has to do two opposite things at once: bring oxygen in and "
        "carry product water out. Both gas and liquid are resolved here, and "
        "the liquid saturation imposed at the gas channel is what sets the "
        "boundary condition for the whole cathode side."),
    groups=(
        EquationGroup(
            "Electron transport", quantity=Quantity.PHI_E,
            equations=(
                Equation(r"j_e = -\sigma_e^\mathrm{GDL}\,\frac{d\phi_e}{dx}"),
                Equation(r"\frac{dj_e}{dx} = 0",
                         "The electron current leaving this layer at the "
                         "bipolar plate is the cell current."),
            )),
        EquationGroup(
            "Heat conduction", quantity=Quantity.T,
            equations=(
                Equation(r"j_T = -k_\mathrm{GDL}\,\frac{dT}{dx}"),
                Equation(r"\frac{dj_T}{dx} = -j_e\,\frac{d\phi_e}{dx} + "
                         r"H_\mathrm{ec}\,S_\mathrm{ec}"),
            )),
        EquationGroup(
            "Water vapour diffusion", quantity=Quantity.W_H2O,
            equations=(
                Equation(r"j_\mathrm{H_2O} = -\rho_\mathrm{gas}\,"
                         r"D_\mathrm{H_2O}^\mathrm{C}\,"
                         r"\frac{dw_\mathrm{H_2O}}{dx} + "
                         r"\rho_\mathrm{gas}\,w_\mathrm{H_2O}\,u_\mathrm{gas}"),
                Equation(r"\frac{dj_\mathrm{H_2O}}{dx} = "
                         r"-M_\mathrm{H_2O}\,S_\mathrm{ec}"),
                _GAS_DENSITY_CATHODE,
            )),
        EquationGroup(
            "Oxygen diffusion", quantity=Quantity.W_O2,
            equations=(
                Equation(r"j_\mathrm{O_2} = -\rho_\mathrm{gas}\,"
                         r"D_\mathrm{O_2}\,\frac{dw_\mathrm{O_2}}{dx} + "
                         r"\rho_\mathrm{gas}\,w_\mathrm{O_2}\,u_\mathrm{gas}"),
                Equation(r"\frac{dj_\mathrm{O_2}}{dx} = 0",
                         "No reaction here, so the oxygen flux is set entirely "
                         "by what the catalyst layer consumes."),
                _DIFFUSIVITY_SCALING,
            )),
        EquationGroup(
            "Liquid water transport", quantity=Quantity.SATURATION,
            equations=(
                Equation(r"u_\mathrm{liq} = -\frac{\kappa_\mathrm{GDL}\,"
                         r"\kappa_\mathrm{rel}(s)}{\mu_\mathrm{liq}(T)}\,"
                         r"\frac{dP_\mathrm{liq}}{dx}"),
                Equation(r"\frac{d(\rho u)_\mathrm{liq}}{dx} = "
                         r"M_\mathrm{H_2O}\,S_\mathrm{ec}"),
                Equation(r"\kappa_\mathrm{rel}(s) = \max(10^{-6},\, s)",
                         "Relative permeability of the liquid phase."),
            )),
        EquationGroup(
            "Gas momentum (Darcy)", quantity=Quantity.P_GAS,
            equations=(
                Equation(r"u_\mathrm{gas} = -\frac{\kappa_\mathrm{GDL}}"
                         r"{\mu_\mathrm{gas}}\,\frac{dP_\mathrm{gas}}{dx}"),
                Equation(r"\frac{d(\rho u)_\mathrm{gas}}{dx} = "
                         r"-M_\mathrm{H_2O}\,S_\mathrm{ec}"),
            )),
    ),
    caveats=(
        "S_ec is identically zero in this version, so all three phase-change "
        "sources above vanish and the vapour, liquid and heat balances reduce "
        "to divergence-free transport.",
    ),
)

#: Every layer, keyed by region, anode to cathode.
LAYER_DOCS: dict[Region, LayerDoc] = {
    Region.AGDL: _AGDL,
    Region.ACL: _ACL,
    Region.PEM: _PEM,
    Region.CCL: _CCL,
    Region.CGDL: _CGDL,
}


# =============================================================================
# THE EIGHT COUPLED PDEs, AS LABELLED IN THE DIAGRAM
#
# The paper names eight coupled transport processes, and the interface offers
# one chip per process. They do not map one-to-one onto the eight state
# quantities the code resolves -- hydrogen is a closure rather than a state
# variable, and gas momentum is a state variable the paper's list does not name
# -- so each entry below says which quantity it corresponds to and where the
# two differ.
# =============================================================================

@dataclass(frozen=True)
class TransportDoc:
    """One of the eight coupled transport processes."""

    title: str
    quantity: Quantity
    description: str
    note: str = ""

    @property
    def regions(self) -> tuple[Region, ...]:
        """Layers on which the underlying quantity is resolved."""
        return ACTIVE_REGIONS[self.quantity]


#: In the order the paper lists them.
TRANSPORT_DOCS: tuple[TransportDoc, ...] = (
    TransportDoc(
        "Electron transport", Quantity.PHI_E,
        "Ohmic conduction of electrons through the carbon phase, from the "
        "anode catalyst layer where they are released, out to the anode "
        "plate, round the external circuit, and back in through the cathode "
        "GDL. The electron current leaving the cathode GDL is what the model "
        "reports as the cell current density."),
    TransportDoc(
        "Proton transport", Quantity.PHI_P,
        "Ohmic conduction of protons through the ionomer, from the anode "
        "catalyst layer across the membrane to the cathode catalyst layer. "
        "The conductivity depends on the local water content, so this is "
        "where hydration couples into the cell's ohmic resistance."),
    TransportDoc(
        "Heat conduction", Quantity.T,
        "Fourier conduction across all five layers, with both bipolar plates "
        "held at a fixed temperature. Sources are Joule heating in both "
        "conducting phases, the activation losses, the reversible reaction "
        "entropies, and the latent heats of sorption and phase change."),
    TransportDoc(
        "Dissolved water transport", Quantity.LAMBDA,
        "Water dissolved in the ionomer, measured as lambda -- water "
        "molecules per sulfonic acid group. It moves by diffusion down its "
        "own gradient and by electro-osmotic drag with the proton current, "
        "and is exchanged with the vapour in the pores by sorption."),
    TransportDoc(
        "Water vapour diffusion", Quantity.W_H2O,
        "Vapour in the pore space of the GDLs and catalyst layers, moving by "
        "Fickian diffusion and by advection with the bulk gas. It is the "
        "phase through which the channels humidify the ionomer and through "
        "which product water leaves the cell."),
    TransportDoc(
        "Hydrogen diffusion", Quantity.W_H2O,
        "On the anode side the gas is a binary hydrogen/water mixture, so "
        "hydrogen is not a separate state variable: its mass fraction is the "
        "closure w_H2 = 1 - w_H2O and it is resolved implicitly by the "
        "vapour equation above.",
        note="The equations shown below are therefore the anode-side vapour "
             "equations. P_H2 = x_H2 P_gas is what feeds the HOR Nernst term."),
    TransportDoc(
        "Oxygen diffusion", Quantity.W_O2,
        "Oxygen from the cathode channel through the GDL to the catalyst "
        "layer, hindered by liquid water blocking the pores through the "
        "(1 - s)^3 factor. This is the transport that limits the cell at high "
        "current density."),
    TransportDoc(
        "Liquid water transport", Quantity.SATURATION,
        "Liquid water in the cathode pores, driven by the capillary pressure "
        "gradient. The state variable is the liquid pressure P_liq; the "
        "saturation s is recovered from it by inverting the capillary "
        "pressure curve.",
        note="Two things hold this inactive in the present version: the "
             "phase-change source S_ec is zero, and the saturation inversion "
             "applies a floor at the immobile saturation s_im. Liquid water "
             "therefore neither forms nor moves."),
)


def groups_for_quantity(quantity: Quantity) -> list[tuple[LayerDoc, EquationGroup]]:
    """Every layer's treatment of one quantity, anode to cathode."""
    found = []
    for region in Region:
        doc = LAYER_DOCS[region]
        for group in doc.groups:
            if group.quantity == quantity:
                found.append((doc, group))
    return found
