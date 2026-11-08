"""Nuclide table and the dipolar coupling constant (plan D7).

``K = −(μ0/4π)·γi·γj·ħ/(2π)`` with angular γ in rad s⁻¹ T⁻¹. The SI value is in Hz·m³; it is
multiplied by 10³⁰ to give Hz·Å³ for distances in Å. Couplings are in Hz.
"""

from __future__ import annotations

import math
from typing import Final

TABLE_VERSION: Final = "codata2018-iupac.1"

MU0_OVER_4PI: Final = 1e-7  # T² m³ J⁻¹
HBAR: Final = 1.054571817e-34  # J s (CODATA 2018, exact since the SI redefinition)

#: Angular gyromagnetic ratios, rad s⁻¹ T⁻¹ (CODATA 2018 for ¹H). Only ¹H is in the beta scope.
GAMMA: Final[dict[str, float]] = {
    "1H": 2.6752218744e8,
}


def dipolar_constant_hz_a3(isotope_a: str, isotope_b: str) -> float:
    """Return K in Hz·Å³ for a pair of isotopes (negative for two protons)."""
    try:
        gamma_a = GAMMA[isotope_a]
        gamma_b = GAMMA[isotope_b]
    except KeyError as exc:
        raise ValueError(f"isotope not in nuclide table {TABLE_VERSION}: {exc.args[0]}") from None
    return -MU0_OVER_4PI * gamma_a * gamma_b * HBAR / (2 * math.pi) * 1e30
