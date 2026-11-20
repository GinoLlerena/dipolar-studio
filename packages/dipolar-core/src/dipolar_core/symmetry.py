"""Symmetry as a validated group action (Phase 2 V1.2; docs/phase2/v1.0-design.md D-4 to D-6).

**The declaration** (``Declaration``) gives a supported point group, its symmetry axes as rows in
input coordinates, a matching tolerance, and the medium (achiral, uniaxial only).

**Validation** (``validate``):
1. the limits and the declaration are checked before any work;
2. every atom's isotope identity is normalized (``normalize_isotope``, D-6);
3. the coordinates are centred on the unweighted centroid and turned into the symmetry frame
   (x′ = Q x, with Q the polar factor of the declared axes);
4. each operation g of the group must map every atom onto the unique atom of the same isotope
   within the tolerance (inclusive, on the computed distance: a match exactly at the cutoff can
   depend on the input frame by rounding), giving a permutation π_g; the permutations must compose like the group
   table (π_gh = π_g ∘ π_h), so they are a group action;
5. the averaged geometry x*_i = |G|⁻¹ Σ_g g⁻¹ x_{π_g(i)} is exactly symmetric, and is what the
   fit uses; the largest |x*_i − x_i| is reported.

**Orbits.** Site orbits are symmetry-enforced chemical equivalence. A pair's orbit is the set of
sorted pairs (π_g(a), π_g(b)); its key is the smallest. Magnetic equivalence is never used to merge
observations. ``fixed_rows`` gives one design row per observed pair orbit, from its key on the
averaged geometry, and refuses a second observation of the same orbit (D-5): a symmetry copy is not
a new observation, so it changes neither N nor ν.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from dipolar_core import fixed
from dipolar_core.forward import design_rows

Array = NDArray[np.float64]

SUPPORTED_GROUPS: Final = ("C1", "Cs", "C2v", "D2h", "D3h", "D6h")
MEDIUM: Final = "achiral-uniaxial"
TOLERANCE_MIN_A: Final = 0.001
TOLERANCE_MAX_A: Final = 0.1
TOLERANCE_DEFAULT_A: Final = 0.01
AXES_ATOL: Final = 1e-9
MAX_ATOMS: Final = 1000
MAX_OPERATIONS: Final = 24

#: The isotope table (D-6): element → (default mass number, allowed mass numbers). D is the only
#: spelling of deuterium; other elements have their most abundant isotope only.
ISOTOPES: Final[dict[str, tuple[int, frozenset[int]]]] = {
    "H": (1, frozenset({1})),
    "D": (2, frozenset({2})),
    "B": (11, frozenset({11})),
    "C": (12, frozenset({12, 13})),
    "N": (14, frozenset({14, 15})),
    "O": (16, frozenset({16})),
    "F": (19, frozenset({19})),
    "Si": (28, frozenset({28})),
    "P": (31, frozenset({31})),
    "S": (32, frozenset({32})),
    "Cl": (35, frozenset({35})),
    "Br": (79, frozenset({79})),
    "I": (127, frozenset({127})),
}
PROTON: Final = ("H", None)

Key = tuple[str, int | None]


class SymmetryError(ValueError):
    """A refusal with a stable code (the application maps it to its error envelope)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class Declaration:
    point_group: str
    axes: Array  # rows x, y, z of the symmetry frame, in input coordinates
    tolerance_a: float = TOLERANCE_DEFAULT_A
    medium: str = MEDIUM


def normalize_isotope(element: str, mass_number: int | None) -> Key:
    """One spelling per isotope identity: a default mass is absent; deuterium is ``D``."""
    if element not in ISOTOPES:
        raise SymmetryError("ISOTOPE_NOT_SUPPORTED", f"element {element!r} is not in the isotope table")
    default, allowed = ISOTOPES[element]
    if mass_number is None or mass_number == default:
        return (element, None)
    if element == "H" and mass_number == 2:
        raise SymmetryError("ISOTOPE_NOT_SUPPORTED", "deuterium is the element D, not H with mass number 2")
    if mass_number not in allowed:
        raise SymmetryError("ISOTOPE_NOT_SUPPORTED", f"{element}-{mass_number} is not supported")
    return (element, int(mass_number))


def _rot_z(angle: float) -> Array:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _generators(group: str) -> list[Array]:
    c2z, c2x, c2y = np.diag([-1.0, -1.0, 1.0]), np.diag([1.0, -1.0, -1.0]), np.diag([-1.0, 1.0, -1.0])
    sigma_h, sigma_xz = np.diag([1.0, 1.0, -1.0]), np.diag([1.0, -1.0, 1.0])
    return {
        "C1": [],
        "Cs": [sigma_h],  # z normal to the mirror
        "C2v": [c2z, sigma_xz],  # z on C2; mirrors xz and yz
        "D2h": [c2z, c2y, -np.eye(3)],  # C2 along x, y, z
        "D3h": [_rot_z(2 * np.pi / 3), c2x, sigma_h],  # z on C3; x on a C2'
        "D6h": [_rot_z(np.pi / 3), c2x, sigma_h],  # z on C6; x on a C2'
    }[group]


def operations(point_group: str) -> list[Array]:
    """The group's operations in its symmetry frame, closed from its generators; identity first."""
    if point_group not in SUPPORTED_GROUPS:
        raise SymmetryError("POINT_GROUP_NOT_SUPPORTED", f"{point_group!r} is not supported")
    ops: list[Array] = [np.eye(3)]
    frontier = list(ops)
    gens = _generators(point_group)
    while frontier:
        nxt = []
        for g in frontier:
            for h in gens:
                p = h @ g
                p[np.abs(p) < 1e-14] = 0.0
                if all(np.max(np.abs(p - k)) > 1e-9 for k in ops):
                    ops.append(p)
                    nxt.append(p)
        frontier = nxt
        if len(ops) > MAX_OPERATIONS:
            raise SymmetryError("POINT_GROUP_NOT_SUPPORTED", "the group is larger than the operation limit")
    return ops


def multiplication_table(ops: Sequence[Array]) -> NDArray[np.intp]:
    """table[i, j] is the index of ops[i] @ ops[j]."""
    n = len(ops)
    table = np.empty((n, n), dtype=np.intp)
    for i, g in enumerate(ops):
        for j, h in enumerate(ops):
            p = g @ h
            table[i, j] = int(np.argmin([np.max(np.abs(p - k)) for k in ops]))
    return table


def match_operation(points: Array, keys: Sequence[Key], mapped: Array, tolerance_a: float) -> NDArray[np.intp]:
    """π with mapped[i] ≈ points[π(i)], matching only atoms of the same isotope. A missing match
    refuses the symmetry; two candidates within the tolerance are an ambiguity (a guard: impossible
    when atoms are ≥ 0.5 Å apart and the tolerance ≤ 0.1 Å)."""
    from scipy.spatial import cKDTree

    n = len(points)
    perm = np.full(n, -1, dtype=np.intp)
    classes: dict[Key, list[int]] = {}
    for i, key in enumerate(keys):
        classes.setdefault(key, []).append(i)
    for key, members in classes.items():
        idx = np.array(members, dtype=np.intp)
        tree = cKDTree(points[idx])
        k = min(2, len(idx))
        dist, near = tree.query(mapped[idx], k=k)
        dist = np.asarray(dist).reshape(len(idx), k)
        near = np.asarray(near).reshape(len(idx), k)
        bad = np.flatnonzero(dist[:, 0] > tolerance_a)  # the cutoff is inclusive
        if bad.size:
            i = int(idx[bad[0]])
            raise SymmetryError(
                "SYMMETRY_NOT_SATISFIED",
                f"atom {i} ({key[0]}) has no partner within {tolerance_a!r} Å "
                f"(nearest {float(dist[bad[0], 0]):.15g} Å)",
            )
        if k == 2 and np.any(dist[:, 1] <= tolerance_a):
            i = int(idx[np.flatnonzero(dist[:, 1] <= tolerance_a)[0]])
            raise SymmetryError("SYMMETRY_AMBIGUOUS", f"atom {i}: two atoms lie within the tolerance of its image")
        perm[idx] = idx[near[:, 0]]
    return perm


def check_action(perms: NDArray[np.intp], table: NDArray[np.intp]) -> None:
    """Each π_g is a permutation, and π_gh = π_g ∘ π_h for the whole table."""
    n = perms.shape[1]
    for g, perm in enumerate(perms):
        if not np.array_equal(np.sort(perm), np.arange(n)):
            raise SymmetryError("SYMMETRY_NOT_AN_ACTION", f"operation {g} does not permute the atoms")
    for g in range(len(perms)):
        for h in range(len(perms)):
            if not np.array_equal(perms[table[g, h]], perms[g][perms[h]]):
                raise SymmetryError("SYMMETRY_NOT_AN_ACTION", f"operations {g} and {h} do not compose")


@dataclass(frozen=True)
class Validated:
    point_group: str
    rotation: Array  # Q: x_sym = Q (x − centroid)
    centroid: Array
    operations: tuple[Array, ...]
    permutations: NDArray[np.intp]  # |G| × n
    averaged: Array  # x*, in the symmetry frame, centred
    max_displacement_a: float
    site_orbit: NDArray[np.intp]  # the smallest atom index of each atom's site orbit
    keys: tuple[Key, ...]

    def endpoints(self, a: object, b: object) -> tuple[int, int]:
        """Two distinct atom indices in [0, n): integers only (bool, floats and strings are
        refused, never truncated or wrapped)."""
        n = len(self.keys)
        out = []
        for x in (a, b):
            if isinstance(x, bool) or not isinstance(x, int | np.integer) or not 0 <= int(x) < n:
                raise SymmetryError("OBSERVATION_INVALID_INDEX", f"{x!r} is not an atom index in [0, {n})")
            out.append(int(x))
        if out[0] == out[1]:
            raise SymmetryError("OBSERVATION_INVALID_INDEX", "a coupling needs two distinct atoms")
        return out[0], out[1]

    def pair_orbit(self, a: int, b: int) -> tuple[tuple[int, int], frozenset[tuple[int, int]]]:
        """(key, members) of the unordered pair's orbit: both endpoints move together."""
        a, b = self.endpoints(a, b)
        members = frozenset((int(min(p[a], p[b])), int(max(p[a], p[b]))) for p in self.permutations)
        return min(members), members


def _axes(declaration: Declaration) -> Array:
    axes = np.asarray(declaration.axes, dtype=np.float64)
    if axes.shape != (3, 3) or not np.all(np.isfinite(axes)):
        raise SymmetryError("AXES_INVALID", "the axes must be a finite 3 × 3 matrix (rows x, y, z)")
    if np.max(np.abs(axes @ axes.T - np.eye(3))) > AXES_ATOL or np.linalg.det(axes) <= 0:
        raise SymmetryError("AXES_INVALID", f"the axes must be orthonormal and right-handed within {AXES_ATOL}")
    u, _, vt = np.linalg.svd(axes)
    q: Array = u @ vt  # the polar factor: exactly orthogonal
    return q


def validate(
    coordinates: Array, elements: Sequence[str], mass_numbers: Sequence[int | None], declaration: Declaration
) -> Validated:
    """Validate a declared symmetry against a geometry (see the module docstring)."""
    if len(elements) > MAX_ATOMS:
        raise SymmetryError("TOO_MANY_ATOMS", f"symmetry validation supports at most {MAX_ATOMS} atoms")
    if declaration.medium != MEDIUM:
        raise SymmetryError("MEDIUM_NOT_SUPPORTED", f"only the {MEDIUM} medium is supported")
    if declaration.point_group not in SUPPORTED_GROUPS:
        raise SymmetryError(
            "POINT_GROUP_NOT_SUPPORTED", f"{declaration.point_group!r}: supported are {', '.join(SUPPORTED_GROUPS)}"
        )
    if not TOLERANCE_MIN_A <= declaration.tolerance_a <= TOLERANCE_MAX_A:
        raise SymmetryError(
            "TOLERANCE_OUT_OF_RANGE", f"the tolerance must be within {TOLERANCE_MIN_A}–{TOLERANCE_MAX_A} Å"
        )
    q = _axes(declaration)
    xyz = np.asarray(coordinates, dtype=np.float64)
    n = len(elements)
    if xyz.shape != (n, 3) or len(mass_numbers) != n or n == 0 or not np.all(np.isfinite(xyz)):
        raise SymmetryError("AXES_INVALID", "the coordinates must be a finite N × 3 array matching the atoms")
    keys = tuple(normalize_isotope(e, m) for e, m in zip(elements, mass_numbers, strict=True))

    centroid = xyz.mean(axis=0)
    y = (xyz - centroid) @ q.T
    ops = operations(declaration.point_group)
    perms = np.array([match_operation(y, keys, y @ g.T, declaration.tolerance_a) for g in ops], dtype=np.intp)
    check_action(perms, multiplication_table(ops))

    averaged = np.zeros_like(y)
    for g, perm in zip(ops, perms, strict=True):
        averaged += y[perm] @ g  # g⁻¹ = gᵀ applied to row vectors
    averaged /= len(ops)
    return Validated(
        point_group=declaration.point_group,
        rotation=q,
        centroid=centroid,
        operations=tuple(ops),
        permutations=perms,
        averaged=averaged,
        max_displacement_a=float(np.max(np.linalg.norm(averaged - y, axis=1))),
        site_orbit=perms.min(axis=0),
        keys=keys,
    )


@dataclass(frozen=True)
class FixedRows:
    design_s5: Array  # N × 5, one row per observed pair orbit, in the symmetry frame
    subspace: Array  # the group's symmetry subspace of b (fixed.SUBSPACES)
    keys: tuple[tuple[int, int], ...]  # each row's pair-orbit key
    multiplicities: tuple[int, ...]  # the number of pairs in each orbit (information only)


def fixed_rows(validated: Validated, pairs: Sequence[tuple[int, int]], k_hz_a3: float) -> FixedRows:
    """One design row per observed ¹H–¹H pair orbit (D-5), from the orbit's key on the averaged
    geometry. A second observation of an orbit is refused: it is a symmetry copy, not new data."""
    keys: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()  # duplicate detection in O(1) per row (round 75)
    sizes: list[int] = []
    for pair in pairs:
        a, b = validated.endpoints(*pair)
        if validated.keys[a] != PROTON or validated.keys[b] != PROTON:
            raise SymmetryError("OBSERVATION_NOT_PROTON", f"pair ({a}, {b}): only ¹H–¹H couplings are observations")
        key, members = validated.pair_orbit(a, b)
        if key in seen:
            raise SymmetryError(
                "PAIR_ORBIT_REPEATED",
                f"pair ({a}, {b}) is in the orbit of {key}, already observed: repeat measurements of one "
                "pair orbit are not accepted in this release",
            )
        seen.add(key)
        keys.append(key)
        sizes.append(len(members))
    design = design_rows(validated.averaged, keys, k_hz_a3)
    return FixedRows(design, fixed.SUBSPACES[validated.point_group], tuple(keys), tuple(sizes))
