"""Imported geometry with one permitted torsion (plan D4, ADR-0004; M1 step 4).

The molecule is given as coordinates in Å, for example from an XYZ file. The input frame is the
frame of the order tensor (passive frame contract of ``dipolar_core.forward``).

**The torsion** is declared by four atoms (a, i, j, b) with i–j a bond.
- The parameter φ is the signed IUPAC dihedral τ(a–i–j–b), in degrees. It is positive when, seen
  along i → j, the far bond j–b is turned clockwise from the near bond i–a, which is a
  right-handed rotation about i → j.
- Setting φ turns the *moving fragment* about the axis i → j by φ − φ₀, where φ₀ is the imported
  dihedral. The moving fragment is the side of j once the bond i–j is cut.
- The other side, which contains i and a, stays fixed. So does the input frame, and with it the
  order tensor.

**Bonds** come from covalent radii: two atoms are bonded when their distance is at most
r_a + r_b + BOND_TOLERANCE_A.
- A torsion bond inside a ring is refused, because cutting it leaves one fragment.
- A molecule whose bond graph would change as the torsion turns is the caller's responsibility;
  ``min_nonbonded_distance`` helps to check for clashes.

**The scale anchor (plan D12)** is the fixed imported geometry.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from dipolar_core.problem import Problem

Array = NDArray[np.float64]

#: Single-bond covalent radii in Å (Cordero et al., Dalton Trans. 2008, 2832), for bond perception.
COVALENT_RADII_A: Final = {
    "H": 0.31,
    "D": 0.31,
    "C": 0.76,
    "N": 0.71,
    "O": 0.66,
    "F": 0.57,
    "P": 1.07,
    "S": 1.05,
    "Cl": 1.02,
    "Br": 1.20,
    "I": 1.39,
}
BOND_TOLERANCE_A: Final = 0.45
_DEG: Final = math.pi / 180.0


def bonds_from_coordinates(elements: Sequence[str], positions: Array) -> tuple[tuple[int, int], ...]:
    """Bonds (i < j) by covalent radii; an unknown element is an error, never a guess."""
    unknown = sorted({e for e in elements if e not in COVALENT_RADII_A})
    if unknown:
        raise ValueError(f"no covalent radius for element(s) {unknown}; known: {sorted(COVALENT_RADII_A)}")
    radii = np.array([COVALENT_RADII_A[e] for e in elements])
    distance = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=2)
    limit = radii[:, None] + radii[None, :] + BOND_TOLERANCE_A
    i, j = np.nonzero(np.triu(distance <= limit, k=1))
    return tuple((int(a), int(b)) for a, b in zip(i, j, strict=True))


def moving_fragment(n_atoms: int, bonds: Sequence[tuple[int, int]], i: int, j: int) -> tuple[int, ...]:
    """Atoms on the j side of the bond i–j once it is cut (sorted). Refused if i–j is not a bond,
    or if it lies in a ring (the two sides stay connected)."""
    if (min(i, j), max(i, j)) not in {(min(a, b), max(a, b)) for a, b in bonds}:
        raise ValueError(f"atoms {i} and {j} are not bonded; a torsion needs a bond")
    neighbours: list[set[int]] = [set() for _ in range(n_atoms)]
    for a, b in bonds:
        if {a, b} != {i, j}:
            neighbours[a].add(b)
            neighbours[b].add(a)
    seen, stack = {j}, [j]
    while stack:
        for nxt in neighbours[stack.pop()] - seen:
            seen.add(nxt)
            stack.append(nxt)
    if i in seen:
        raise ValueError(f"the bond {i}–{j} is in a ring; it cannot carry a free torsion")
    return tuple(sorted(seen))


def dihedral_deg(positions: Array, a: int, i: int, j: int, b: int) -> float:
    """Signed IUPAC dihedral τ(a–i–j–b) in degrees, in (−180, 180]."""
    b1, b2, b3 = positions[i] - positions[a], positions[j] - positions[i], positions[b] - positions[j]
    y = float(np.linalg.norm(b2) * (b1 @ np.cross(b2, b3)))
    x = float(np.cross(b1, b2) @ np.cross(b2, b3))
    if x == 0.0 and y == 0.0:
        raise ValueError("the dihedral is undefined: three of its atoms are collinear")
    return math.degrees(math.atan2(y, x))


@dataclass(frozen=True)
class TorsionGeometry:
    """Imported coordinates with one torsion (a, i, j, b), turned by setting the dihedral φ."""

    positions0: Array
    torsion: tuple[int, int, int, int]
    moving: tuple[int, ...]

    @classmethod
    def from_atoms(
        cls, elements: Sequence[str], positions: Array, torsion: tuple[int, int, int, int]
    ) -> TorsionGeometry:
        positions = np.asarray(positions, dtype=np.float64)
        if positions.ndim != 2 or positions.shape != (len(elements), 3) or not np.all(np.isfinite(positions)):
            raise ValueError("positions must be a finite n × 3 array, one row per element")
        a, i, j, b = torsion
        if len({a, i, j, b}) != 4 or not all(0 <= k < len(elements) for k in torsion):
            raise ValueError("the torsion needs four distinct atom indices")
        moving = moving_fragment(len(elements), bonds_from_coordinates(elements, positions), i, j)
        if a in moving or b not in moving:
            raise ValueError("atom a must be on the fixed side of i–j and atom b on the moving side")
        dihedral_deg(positions, a, i, j, b)  # defined
        return cls(positions0=positions, torsion=torsion, moving=moving)

    @property
    def phi0_deg(self) -> float:
        """The imported dihedral."""
        return dihedral_deg(self.positions0, *self.torsion)

    def _axis(self) -> tuple[Array, Array]:
        _, i, j, _ = self.torsion
        origin = self.positions0[i]
        k = self.positions0[j] - origin
        return origin, k / np.linalg.norm(k)

    def positions(self, phi_deg: float) -> Array:
        """Coordinates with τ(a–i–j–b) = φ: the moving fragment turned right-handedly about i → j."""
        if not math.isfinite(phi_deg):
            raise ValueError("phi_deg must be finite")
        origin, k = self._axis()
        angle = math.radians(phi_deg - self.phi0_deg)
        c, s = math.cos(angle), math.sin(angle)
        out = self.positions0.copy()
        v = out[list(self.moving)] - origin
        # Rodrigues: v cos + (k × v) sin + k (k·v)(1 − cos)
        out[list(self.moving)] = origin + v * c + np.cross(k, v) * s + np.outer(v @ k, k) * (1 - c)
        return out

    def positions_derivative(self, phi_deg: float) -> Array:
        """∂positions/∂φ per degree, analytic: (π/180)·k × (p − origin) on the moving fragment."""
        origin, k = self._axis()
        out = np.zeros_like(self.positions0)
        moved = self.positions(phi_deg)[list(self.moving)]
        out[list(self.moving)] = _DEG * np.cross(k, moved - origin)
        return out

    def min_nonbonded_distance(self, phi_deg: float) -> float:
        """The closest approach between atoms of the two fragments (a clash check)."""
        pos = self.positions(phi_deg)
        _, i, j, _ = self.torsion
        moving = [m for m in self.moving if m != j]
        fixed = [f for f in range(len(pos)) if f not in self.moving and f != i]
        pairs = [(m, f) for m in self.moving for f in fixed] + [(m, i) for m in moving]
        return float(min(np.linalg.norm(pos[m] - pos[f]) for m, f in pairs))


def imported_problem(
    geometry: TorsionGeometry,
    pairs: Sequence[tuple[int, int]],
    isotopes: Sequence[tuple[str, str]],
    y: Array,
    sigma: Array,
    *,
    order: str = "c1",
    domain_deg: tuple[float, float] = (-180.0, 180.0),
    covariance: Array | None = None,
) -> Problem:
    """A rigid model on imported coordinates, with φ = τ(a–i–j–b) as the geometry parameter.

    - ``pairs`` are atom indices, and ``isotopes`` gives the nuclide pair of each coupling (K from
      the nuclide table).
    - The tensor lives in the input frame, which is fixed to the non-moving fragment. ``order`` is
      "c1" (all five components) or "c2z", which assumes the input z axis is a C2 axis of the
      tensor (the caller's declaration).
    - The domain is any interval of width at most 360°. The dihedral is periodic, so an optimum
      at either end is reported at a bound: shift the domain to move it inside.
    """
    from dipolar_core.forward import constraint_c1, constraint_c2z, design_rows, design_rows_derivative
    from dipolar_core.nuclides import dipolar_constant_hz_a3

    lo, hi = (float(v) for v in domain_deg)
    if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi <= lo + 360.0):
        raise ValueError("the torsion domain must be a finite interval no wider than 360°")
    constraints = {
        "c1": (constraint_c1(), ("Szz", "Delta", "Sxy", "Sxz", "Syz")),
        "c2z": (constraint_c2z(), ("Szz", "Delta", "Sxy")),
    }
    if order not in constraints:
        raise ValueError(f"unknown order model {order!r} for imported geometry; expected one of {tuple(constraints)}")
    if len(isotopes) != len(pairs):
        raise ValueError("one isotope pair per coupling is required")
    c, names = constraints[order]
    k = np.array([dipolar_constant_hz_a3(a, b) for a, b in isotopes])

    def design(theta: Array) -> Array:
        out: Array = (k[:, None] * design_rows(geometry.positions(float(theta[0])), pairs, 1.0)) @ c
        return out

    def derivative(theta: Array) -> Array:
        phi = float(theta[0])
        rows = design_rows_derivative(geometry.positions(phi), geometry.positions_derivative(phi)[None], pairs, 1.0)[0]
        out: Array = ((k[:, None] * rows) @ c)[None]
        return out

    return Problem(
        design=design,
        design_derivative=derivative,
        y=np.asarray(y, dtype=np.float64),
        sigma=np.asarray(sigma, dtype=np.float64),
        lower=np.array([lo]),
        upper=np.array([hi]),
        theta_names=("phi_deg",),
        order_names=names,
        s5_map=c,
        covariance=covariance,
        estimand="rigid effective dihedral",
    )
