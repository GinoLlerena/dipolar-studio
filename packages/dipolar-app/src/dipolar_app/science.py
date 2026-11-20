"""From a project to a D3 problem (M1 step 4): the one place that maps the saved science onto
``dipolar_core``.

- ``validate_project`` states the invariants every project must satisfy, draft or not. Project
  files are checked on load, and every edit, dry run and proposal acceptance runs it too.
- ``problem_for`` adds what fitting needs: couplings, a declared torsion for imported geometry,
  and a supported domain.
- ``fixed_problem_for`` does the same for a fixed-geometry fit (Phase 2 V1.3): the declared
  symmetry validated against the geometry, and one design row per observed pair orbit.

**The model states (D-3).** A template fit, a torsion fit and a draft are as in 0.1. A
fixed-geometry fit (``kind = "fixed"``) has imported geometry, no torsion, a declared symmetry,
order "point-group", frame "symmetry" and no torsion domain; every H atom is a spin, and each
coupling's class is exactly its pair orbit (D-5). A symmetry may be declared on a draft, never on
the template or with a torsion (not in V1).

**Refusals.** Core refusals keep their code (``SymmetryError.code``) and application refusals carry
one (``ScienceError``); ``refusal`` maps both onto the error envelope, through the explicit table
``CORE_ERROR_CODES`` (round 76). Every other ``ValueError`` is an invalid argument.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from dipolar_core.biphenyl import (
    PROTON_LABELS,
    BiphenylGeometry,
    jump_design,
    jump_problem,
    rigid_design,
    rigid_problem,
)
from dipolar_core.problem import Problem
from dipolar_core.symmetry import (
    ISOTOPES,
    MAX_FIT_ROWS,
    Declaration,
    FixedRows,
    SymmetryError,
    Validated,
    normalize_isotope,
)
from dipolar_core.torsion import TorsionGeometry, imported_problem

from dipolar_app.errors import ErrorCode
from dipolar_app.project import (
    BiphenylTemplate,
    ByIdentity,
    Coupling,
    ImportedGeometry,
    Molecule,
    Project,
    split_pair_label,
)

#: Every refusal code of ``dipolar_core.symmetry`` and its error envelope (round 76). Codes the
#: application cannot reach (it passes only valid spin atoms) map to INVALID_ARGUMENT; the
#: envelope's ``details.core_code`` always names the core code.
CORE_ERROR_CODES: dict[str, ErrorCode] = {
    "TOO_MANY_ATOMS": ErrorCode.INVALID_ARGUMENT,
    "MEDIUM_NOT_SUPPORTED": ErrorCode.MEDIUM_NOT_SUPPORTED,
    "POINT_GROUP_NOT_SUPPORTED": ErrorCode.POINT_GROUP_NOT_SUPPORTED,
    "TOLERANCE_OUT_OF_RANGE": ErrorCode.OUT_OF_DOMAIN,
    "AXES_INVALID": ErrorCode.INVALID_ARGUMENT,
    "GEOMETRY_INVALID": ErrorCode.INVALID_ARGUMENT,
    "ISOTOPE_NOT_SUPPORTED": ErrorCode.ISOTOPE_NOT_SUPPORTED,
    "SYMMETRY_NOT_SATISFIED": ErrorCode.SYMMETRY_NOT_SATISFIED,
    "SYMMETRY_AMBIGUOUS": ErrorCode.SYMMETRY_NOT_SATISFIED,  # a guard: impossible in a valid project
    "SYMMETRY_NOT_AN_ACTION": ErrorCode.SYMMETRY_NOT_SATISFIED,  # a guard: impossible in a valid project
    "OBSERVATION_INVALID_INDEX": ErrorCode.INVALID_ARGUMENT,
    "OBSERVATION_NOT_PROTON": ErrorCode.INVALID_ARGUMENT,
    "PAIR_ORBIT_REPEATED": ErrorCode.OBSERVATIONS_CONFLICT,
    "FIT_TOO_LARGE": ErrorCode.FIT_TOO_LARGE,
}


class ScienceError(ValueError):
    """An application refusal with its own envelope code and details (for example the coupling IDs
    of an ``OBSERVATIONS_CONFLICT``)."""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def refusal(exc: ValueError) -> tuple[ErrorCode, dict[str, Any]]:
    """The envelope code and details of a refusal raised while validating or fitting."""
    if isinstance(exc, ScienceError):
        return exc.code, dict(exc.details)
    if isinstance(exc, SymmetryError):
        return CORE_ERROR_CODES[exc.code], {"core_code": exc.code}
    code = getattr(exc, "code", None)  # a FormatError that wraps one of the above
    if isinstance(code, ErrorCode):
        return code, dict(getattr(exc, "details", {}) or {})
    return ErrorCode.INVALID_ARGUMENT, {}


DRAFT_REASON = "declare a torsion, or declare the molecule's symmetry and choose a fixed-geometry fit"

#: Torsions at which a declared equivalence class must give identical design rows.
_PROBE_FRACTIONS = (0.137, 0.5, 0.861)
_ROW_RTOL = 1e-9
#: Imported atoms closer than this are refused: coincident spins have no dipolar coupling.
MIN_ATOM_DISTANCE_A = 0.5


def _resolve_pair(entry: str, by_label: dict[str, str]) -> frozenset[str]:
    """An ``equivalent_pairs`` entry "A-B" as a pair of spin IDs (``split_pair_label``: exactly
    one split must name two known labels)."""
    a, b = split_pair_label(entry, by_label.keys())
    return frozenset((by_label[a], by_label[b]))


#: The template's bond lengths are a few Å; the bound keeps its geometry numerically safe (round 36).
MAX_BOND_A = 10.0


_VALID = ByIdentity(size=8)


def validate_project(project: Project) -> None:
    """Raise ValueError naming the first broken invariant, or return None. A ``SymmetryError`` or a
    ``ScienceError`` carries its own code (``refusal``). A project is immutable, so a validated
    one is remembered by identity (a fit validates the project it was just given)."""
    _VALID.get(project, lambda: _validate_project(project))


def _validate_project(project: Project) -> bool:
    g, m = project.molecule.geometry, project.model
    spins = project.molecule.spins
    if len({s.id for s in spins}) != len(spins):
        raise ValueError("spin IDs must be unique")
    if len({s.label for s in spins}) != len(spins):
        raise ValueError("spin labels must be unique (they identify spins during import)")
    if len({c.id for c in project.couplings}) != len(project.couplings):
        raise ValueError("coupling IDs must be unique")
    if isinstance(g, BiphenylTemplate) and max(g.r_cc.value, g.r_ch.value, g.r_inter.value) > MAX_BOND_A:
        raise ValueError(f"the template's bond lengths must not exceed {MAX_BOND_A:g} Å (round 36)")
    numbers = [int(c.id[4:]) for c in project.couplings]
    if numbers and max(numbers) >= project.next_coupling_id:
        raise ValueError("next_coupling_id must exceed every coupling number (IDs are never reused)")
    known = {s.id for s in spins}
    for c in project.couplings:
        if c.spin_a not in known or c.spin_b not in known or c.spin_a == c.spin_b:
            raise ValueError(f"coupling {c.id} must join two different spins of the project")
        if not c.sigma.value > 0:
            raise ValueError(f"coupling {c.id}: sigma must be positive")
    fixed = m.kind == "fixed"
    if fixed:
        if m.order != "point-group" or m.frame != "symmetry" or m.phi_domain_deg is not None:
            raise ValueError(
                "the fixed-geometry model uses order 'point-group' in the 'symmetry' frame, with no torsion domain"
            )
    else:
        if m.order == "point-group" or m.frame == "symmetry":
            raise ValueError("order 'point-group' and frame 'symmetry' belong to the fixed-geometry model")
        if m.phi_domain_deg is None:
            raise ValueError("the model needs a torsion domain (only the fixed-geometry model has none)")
        lo, hi = m.phi_domain_deg
        if not lo < hi:
            raise ValueError("the torsion domain must have lower < upper")
    if isinstance(g, BiphenylTemplate):
        if fixed or project.molecule.symmetry is not None:
            raise ValueError(
                "the biphenyl template has a torsion: it takes no symmetry declaration or fixed-geometry fit"
            )
        if m.frame == "input":
            raise ValueError("the template uses the 'bisector' or 'ring-a' frame")
        if len(spins) != len(PROTON_LABELS) or any(s.atom is not None for s in spins):
            raise ValueError("the biphenyl template has its ten protons, in template order, without atom indices")
        if m.kind == "jump4" and (m.order != "bisector-diagonal" or m.frame != "bisector"):
            raise ValueError("the jump model uses the bisector-diagonal order model in the bisector frame")
        if not (0.0 <= lo and hi <= (90.0 if m.kind == "jump4" else 180.0)):
            raise ValueError("the template's torsion domain lies within [0, 90] (jump) or [0, 180] (rigid)")
    else:
        if fixed:
            if g.torsion is not None:
                raise ValueError(
                    "a fixed-geometry fit has no torsion: clear it, or fit the torsion with the rigid model"
                )
            if project.molecule.symmetry is None:
                raise ValueError("a fixed-geometry fit needs the molecule's declared symmetry (molecule.set_symmetry)")
        elif m.kind != "rigid" or m.order == "bisector-diagonal" or m.frame != "input":
            raise ValueError("imported geometry uses the rigid model, order 'c1' or 'c2z', in the 'input' frame")
        n = len(g.atoms)
        for k, atom in enumerate(g.atoms):
            if atom.element not in ISOTOPES:
                raise ValueError(f"atom {k}: the element {atom.element!r} is not supported ({', '.join(ISOTOPES)})")
        for s in spins:
            if s.atom is None or not s.atom < n or g.atoms[s.atom].element != "H":
                raise ValueError(f"spin {s.id} must name a hydrogen atom of the imported geometry")
            if g.atoms[s.atom].mass_number is not None:
                raise ValueError(f"spin {s.id}: a ¹H spin's atom has no mass number (deuterium is the element D)")
        if len({s.atom for s in spins}) != len(spins):
            raise ValueError("two spins name the same atom")
        for k, atom in enumerate(g.atoms):
            if normalize_isotope(atom.element, atom.mass_number) != (atom.element, atom.mass_number):
                raise ValueError(
                    f"atom {k}: {atom.element}-{atom.mass_number} is the default isotope, written without a mass number"
                )
        if fixed and len(spins) != sum(atom.element == "H" for atom in g.atoms):
            raise ValueError("in a fixed-geometry fit every H atom is a spin, so the pair orbits are complete (D-5)")
        positions = np.array([[atom.x, atom.y, atom.z] for atom in g.atoms])
        if n > 1:
            gaps = np.linalg.norm(positions[:, None, :] - positions[None, :, :], axis=2)
            np.fill_diagonal(gaps, np.inf)
            k = int(np.argmin(gaps))
            if gaps.flat[k] < MIN_ATOM_DISTANCE_A:  # coincident or overlapping atoms (round 27)
                i, j = divmod(k, n)
                raise ValueError(
                    f"atoms {i} and {j} are {gaps.flat[k]:.3g} Å apart; atoms closer than "
                    f"{MIN_ATOM_DISTANCE_A} Å are not a molecule"
                )
        if g.torsion is not None:
            if project.molecule.symmetry is not None:
                raise ValueError("a symmetry is not declared together with a torsion in this version (D-3)")
            if not all(0 <= k < n for k in g.torsion):
                raise ValueError("the torsion atoms must exist")
            # A declared torsion must be a real one: distinct atoms, a bonded, non-ring central bond,
            # a on the fixed side and b on the moving side (round 24). A missing torsion is a draft.
            _torsion_geometry(g)
        if not fixed and hi - lo > 360.0:
            raise ValueError("the torsion domain may span at most 360 deg")
        if project.molecule.symmetry is not None:
            validated_symmetry(project)  # the declaration holds for this geometry (D-4)
    if fixed:
        _validate_fixed_classes(project)
    else:
        _validate_observation_classes(project)
    return True


def _validate_observation_classes(project: Project) -> None:
    """Each observation is one class of pairs (round 22).

    - A class lists its own pair, and the multiplicity counts the class.
    - No pair belongs to two couplings, so N counts independent observations (D3.3).
    - Every pair of a class must have the representative's design row under the selected model
      at several torsions. Otherwise the class is not an equivalence of that model. For example,
      the fixture's D2 classes are not equivalences of c2z or c1.
    """
    by_label = {s.label: s.id for s in project.molecule.spins}
    owner: dict[frozenset[str], str] = {}
    classes: list[tuple[Coupling, list[frozenset[str]]]] = []
    for c in project.couplings:
        own = frozenset((c.spin_a, c.spin_b))
        members = [own]
        if c.equivalent_pairs:
            try:
                members = [_resolve_pair(e, by_label) for e in c.equivalent_pairs]
            except ValueError as exc:
                raise ValueError(f"coupling {c.id}: {exc}") from None
            if own not in members:
                raise ValueError(f"coupling {c.id}: its equivalent pairs must include its own pair")
            if len(set(members)) != len(members) or c.multiplicity != len(members):
                raise ValueError(f"coupling {c.id}: multiplicity must equal the number of distinct equivalent pairs")
        elif c.multiplicity != 1:
            raise ValueError(f"coupling {c.id}: a multiplicity above 1 needs its equivalent pairs")
        for pair in members:
            if pair in owner:
                raise ValueError(f"coupling {c.id} repeats an observation already in coupling {owner[pair]}")
            owner[pair] = c.id
        if len(members) > 1:
            classes.append((c, members))
    if classes:
        _check_class_rows(project, classes)


def _check_class_rows(project: Project, classes: list[tuple[Coupling, list[frozenset[str]]]]) -> None:
    m = project.model
    index = {s.id: i for i, s in enumerate(project.molecule.spins)}
    assert m.phi_domain_deg is not None  # a non-fixed model (validate_project checked it)
    lo, hi = m.phi_domain_deg
    design = _design_function(project)  # the geometry is built once per validation (round 24)
    for fraction in _PROBE_FRACTIONS:
        phi = lo + fraction * (hi - lo)
        for c, members in classes:
            pairs = tuple(tuple(index[s] for s in sorted(pair)) for pair in members)
            rows = design(pairs, phi)  # type: ignore[arg-type]
            scale = max(1.0, float(np.abs(rows).max()))
            if not np.allclose(rows, rows[0], rtol=0, atol=_ROW_RTOL * scale):
                raise ValueError(
                    f"coupling {c.id}: its equivalent pairs are not equivalent under the {m.kind}/{m.order} "
                    f"model (they predict different couplings at phi = {phi:.4g}); re-group the observations"
                )


def _torsion_geometry(g: ImportedGeometry) -> TorsionGeometry:
    assert g.torsion is not None
    positions = np.array([[a.x, a.y, a.z] for a in g.atoms])
    return TorsionGeometry.from_atoms([a.element for a in g.atoms], positions, g.torsion)


def _design_function(project: Project) -> Callable[[tuple[tuple[int, int], ...], float], np.ndarray]:
    """design(spin-index pairs, φ) for the project's model, with the geometry built once."""
    g, m = project.molecule.geometry, project.model
    if isinstance(g, BiphenylTemplate):
        geometry = BiphenylGeometry(r_cc=g.r_cc.value, r_ch=g.r_ch.value, r_inter=g.r_inter.value)
        if m.kind == "jump4":
            return lambda pairs, phi: jump_design(phi, pairs, geometry)
        return lambda pairs, phi: rigid_design(phi, pairs, geometry, order=m.order, frame=m.frame)  # type: ignore[arg-type]
    assert isinstance(g, ImportedGeometry)
    from dipolar_core.forward import constraint_c1, constraint_c2z, design_rows

    atom_of = [s.atom for s in project.molecule.spins]
    c = constraint_c1() if m.order == "c1" else constraint_c2z()
    fixed = np.array([[a.x, a.y, a.z] for a in g.atoms])
    torsion = _torsion_geometry(g) if g.torsion is not None else None

    def design(pairs: tuple[tuple[int, int], ...], phi: float) -> np.ndarray:
        atom_pairs = tuple((int(atom_of[a]), int(atom_of[b])) for a, b in pairs)  # type: ignore[arg-type]
        positions = fixed if torsion is None else torsion.positions(phi)
        out: np.ndarray = design_rows(positions, atom_pairs, 1.0) @ c
        return out

    return design


# --------------------------------------------------------------------------- fixed geometry (V1.3)
_SYMMETRIES = ByIdentity(size=8)


def validated_symmetry(project: Project) -> Validated:
    """The declared symmetry validated against the geometry (``dipolar_core.symmetry.validate``),
    computed once per molecule object: edits that keep the molecule reuse it."""
    molecule = project.molecule
    value: Validated = _SYMMETRIES.get(molecule, lambda: _validate_symmetry(molecule))
    return value


def _validate_symmetry(molecule: Molecule) -> Validated:
    from dipolar_core.symmetry import validate

    g, declared = molecule.geometry, molecule.symmetry
    if not isinstance(g, ImportedGeometry) or declared is None:
        raise ValueError("only imported geometry declares a symmetry")
    declaration = Declaration(
        point_group=declared.point_group,
        axes=np.array(declared.axes, dtype=np.float64),
        tolerance_a=declared.tolerance.value,
        medium=declared.medium,
    )
    xyz = np.array([[a.x, a.y, a.z] for a in g.atoms])
    return validate(xyz, [a.element for a in g.atoms], [a.mass_number for a in g.atoms], declaration)


Orbit = frozenset[frozenset[str]]


class OrbitIndex:
    """The pair orbits of a molecule's spins under its declaration, prepared once per molecule
    (round 77: per-pair work is O(|G|), never O(spins)).

    Spins are ranked by spin ID, so a pair's integer code ``min(r) · n + max(r)`` orders pairs as
    their sorted spin-ID pairs do: the smallest code of an orbit is its D-5 key. Without a
    declaration, a pair's orbit is the pair itself."""

    def __init__(self, project: Project) -> None:
        spins = project.molecule.spins
        self.ids = sorted(s.id for s in spins)
        self.n = len(self.ids)
        self.rank = {spin_id: k for k, spin_id in enumerate(self.ids)}
        self.label = [""] * self.n
        for s in spins:
            self.label[self.rank[s.id]] = s.label
        self.rank_of_label = {label: k for k, label in enumerate(self.label)}
        self._orbits: dict[int, tuple[tuple[str, str], Orbit]] = {}
        if project.molecule.symmetry is None:
            self.images = np.arange(self.n, dtype=np.int64)[None, :]  # the identity only
            self.complete = True
            self.columns = [(k,) for k in range(self.n)]
            return
        validated = validated_symmetry(project)
        rank_of_atom = np.full(len(validated.keys), -1, dtype=np.int64)
        for s in spins:
            rank_of_atom[int(s.atom)] = self.rank[s.id]  # type: ignore[arg-type]
        atoms = np.empty(self.n, dtype=np.intp)
        for s in spins:
            atoms[self.rank[s.id]] = int(s.atom)  # type: ignore[arg-type]
        self.images = rank_of_atom[validated.permutations[:, atoms]]  # |G| × spins: the image's rank
        self.complete = bool(np.all(self.images >= 0))
        self.columns = [tuple(column) for column in self.images.T.tolist()]  # each spin's images

    def codes(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """|G| × N codes of the images of the pairs (ranks a, b)."""
        if not self.complete:
            raise ValueError("every H atom must be a spin for the pair orbits to be complete")
        ia, ib = self.images[:, a], self.images[:, b]
        out: np.ndarray = np.minimum(ia, ib) * self.n + np.maximum(ia, ib)
        return out

    def code(self, a: str, b: str) -> int:
        ra, rb = self.rank[a], self.rank[b]
        return min(ra, rb) * self.n + max(ra, rb)

    def pair(self, code: int) -> tuple[str, str]:
        return self.ids[code // self.n], self.ids[code % self.n]

    def members(self, codes: Any) -> tuple[int, ...]:
        """A column of codes as its sorted distinct members."""
        return tuple(sorted(set(codes.tolist())))

    def orbit(self, a: str, b: str) -> tuple[tuple[str, str], Orbit]:
        """(key, members as spin-ID pairs) of one pair: |G| lookups in plain Python (round 77: a
        reconciliation asks for one pair at a time), remembered per pair."""
        if not self.complete:
            raise ValueError("every H atom must be a spin for the pair orbits to be complete")
        ra, rb, n = self.rank[a], self.rank[b], self.n
        codes = {x * n + y if x < y else y * n + x for x, y in zip(self.columns[ra], self.columns[rb], strict=True)}
        key = min(codes)
        found = self._orbits.get(key)  # one entry per orbit, whichever member asked (round 78)
        if found is None:
            if len(self._orbits) >= MAX_ORBIT_MEMO:
                self._orbits.clear()  # a bound: a later request recomputes in O(|G|)
            found = self.pair(key), frozenset(frozenset(self.pair(c)) for c in sorted(codes))
            self._orbits[key] = found
        return found

    def entry_code(self, entry: str) -> int | None:
        """An "A-B" class entry as a pair code, or None if it does not name exactly one pair of
        distinct spins (``split_pair_label``; a single hyphen is the fast path)."""
        if entry.count("-") == 1:
            a, _, b = entry.partition("-")
            if a not in self.rank_of_label or b not in self.rank_of_label:
                return None
        else:
            try:
                a, b = split_pair_label(entry, self.rank_of_label)
            except ValueError:
                return None
        ra, rb = self.rank_of_label[a], self.rank_of_label[b]
        if ra == rb:
            return None
        return min(ra, rb) * self.n + max(ra, rb)

    def class_entries(self, members: tuple[int, ...]) -> tuple[str, ...]:
        """An orbit as an ``equivalent_pairs`` class, ordered by spin-ID pair: empty for a single
        pair (the row's own pair), and refused when an entry would not parse back to its pair
        under the project's labels (round 77: labels may contain hyphens)."""
        if len(members) == 1:
            return ()
        out = []
        for code in members:
            a, b = code // self.n, code % self.n
            # Either endpoint order names the pair: the first that parses back to it (round 78).
            entry = next(
                (
                    e
                    for e in (f"{self.label[a]}-{self.label[b]}", f"{self.label[b]}-{self.label[a]}")
                    if self.entry_code(e) == code
                ),
                None,
            )
            if entry is None:
                raise ValueError(
                    f"the pair {self.label[a]}–{self.label[b]} of the pair orbit cannot be written as an "
                    "unambiguous class entry with these spin labels; rename the spins so that no 'A-B' entry "
                    "splits two ways"
                )
            out.append(entry)
        return tuple(out)


_ORBIT_INDEXES = ByIdentity(size=8)
#: The per-molecule orbit memo holds at most this many orbits (round 78).
MAX_ORBIT_MEMO = 100_000


def orbit_index(project: Project) -> OrbitIndex:
    """The orbit index of the project's molecule, computed once per molecule object."""
    value: OrbitIndex = _ORBIT_INDEXES.get(project.molecule, lambda: OrbitIndex(project))
    return value


_CODES = ByIdentity(size=4)


def coupling_codes(project: Project) -> tuple[OrbitIndex, list[tuple[int, ...]]]:
    """Each coupling's orbit as its sorted member codes (the first is its key), computed once per
    project object (validation and the fit share it)."""
    value: tuple[OrbitIndex, list[tuple[int, ...]]] = _CODES.get(project, lambda: _coupling_codes(project))
    return value


def _coupling_codes(project: Project) -> tuple[OrbitIndex, list[tuple[int, ...]]]:
    index = orbit_index(project)
    if not project.couplings:
        return index, []
    rank = index.rank
    a = np.array([rank[c.spin_a] for c in project.couplings], dtype=np.intp)
    b = np.array([rank[c.spin_b] for c in project.couplings], dtype=np.intp)
    codes = np.sort(index.codes(a, b), axis=0)  # each column sorted: duplicates are adjacent
    if codes.shape[0] == 1:
        return index, [(int(x),) for x in codes[0].tolist()]
    fresh = np.vstack([np.ones((1, codes.shape[1]), dtype=bool), np.diff(codes, axis=0) != 0])
    columns, keep = codes.T.tolist(), fresh.T.tolist()
    return index, [
        tuple(x for x, k in zip(col, flags, strict=True) if k) for col, flags in zip(columns, keep, strict=True)
    ]


def coupling_keys(project: Project) -> tuple[tuple[str, str], ...]:
    """Each coupling's D-5 key alone (the fit needs no memberships; round 78)."""
    index = orbit_index(project)
    if not project.couplings:
        return ()
    rank = index.rank
    a = np.array([rank[c.spin_a] for c in project.couplings], dtype=np.intp)
    b = np.array([rank[c.spin_b] for c in project.couplings], dtype=np.intp)
    return tuple(index.pair(int(code)) for code in index.codes(a, b).min(axis=0).tolist())


def coupling_orbits(project: Project) -> list[tuple[tuple[str, str], Orbit]]:
    """Each coupling's pair orbit: its D-5 key (the smallest sorted pair of spin IDs) and its
    members as spin-ID pairs."""
    index, orbits = coupling_codes(project)
    return [(index.pair(m[0]), frozenset(frozenset(index.pair(c)) for c in m)) for m in orbits]


def pair_orbit(project: Project, spin_a: str, spin_b: str) -> tuple[tuple[str, str], Orbit]:
    """(key, members) of the orbit of the pair of spins (D-5): the core's orbit (both endpoints
    permuted together) mapped to spin IDs, each pair sorted, and the key the smallest (round 76)."""
    return orbit_index(project).orbit(spin_a, spin_b)


def orbit_key(project: Project, spin_a: str, spin_b: str) -> tuple[str, str]:
    return pair_orbit(project, spin_a, spin_b)[0]


def orbit_class(project: Project, members: Orbit) -> tuple[str, ...]:
    """An orbit as an ``equivalent_pairs`` class (``OrbitIndex.class_entries``)."""
    index = orbit_index(project)
    return index.class_entries(tuple(sorted(index.code(*sorted(p)) for p in members)))


def _class_codes(index: OrbitIndex, c: Coupling) -> list[int] | None:
    """A coupling's stored class as pair codes (its own pair when empty), or None if an entry is
    malformed. The common entry (one hyphen, two known labels) is parsed inline: a fixed project
    can hold about 480 000 entries (round 77)."""
    if not c.equivalent_pairs:
        return [index.code(c.spin_a, c.spin_b)]
    ranks, n = index.rank_of_label, index.n
    out = []
    for entry in c.equivalent_pairs:
        a, sep, b = entry.partition("-")
        ra, rb = ranks.get(a), ranks.get(b)
        if sep and ra is not None and rb is not None and ra != rb and "-" not in b:
            out.append(ra * n + rb if ra < rb else rb * n + ra)
            continue
        code = index.entry_code(entry)
        if code is None:
            return None
        out.append(code)
    return out


def _conflict(ids: list[str], repeated: bool, reason: str) -> ScienceError:
    ids = sorted(set(ids))
    if repeated:
        reason = "repeat measurements of one pair orbit are not accepted in this release; " + reason
    return ScienceError(ErrorCode.OBSERVATIONS_CONFLICT, f"couplings {', '.join(ids)}: {reason}", {"coupling_ids": ids})


def _validate_fixed_classes(project: Project) -> None:
    """D-5: one row per pair orbit, and each row's class is exactly its orbit (unordered pairs,
    each once), with the orbit's size as multiplicity. Every conflicting row is listed, malformed
    classes included (round 77)."""
    index, orbits = coupling_codes(project)
    seen: dict[int, str] = {}
    conflicts: list[str] = []
    repeated = False
    for c, members in zip(project.couplings, orbits, strict=True):
        if members[0] in seen:
            conflicts += [seen[members[0]], c.id]
            repeated = True
        seen.setdefault(members[0], c.id)
        codes = _class_codes(index, c)
        if (
            codes is None
            or len(set(codes)) != len(codes)
            or tuple(sorted(codes)) != members
            or c.multiplicity != len(members)
        ):
            conflicts.append(c.id)
    if conflicts:
        raise _conflict(
            conflicts, repeated, "each row's equivalent pairs must be exactly its pair orbit, each pair once"
        )


def canonicalize_for_fixed(project: Project) -> Project:
    """Entering the fixed-geometry model (D-3): each row's class becomes its pair orbit, keeping
    the coupling ID, value, σ and provenance. Refused (listing the rows) when two rows fall in one
    orbit, or a row's class is neither its orbit (as sets) nor its own single pair."""
    index, orbits = coupling_codes(project)
    seen: dict[int, str] = {}
    conflicts: list[str] = []
    repeated = False
    out = []
    for c, members in zip(project.couplings, orbits, strict=True):
        if members[0] in seen:
            conflicts += [seen[members[0]], c.id]
            repeated = True
        seen.setdefault(members[0], c.id)
        codes = _class_codes(index, c)
        if codes is not None and len(set(codes)) == len(codes) and tuple(sorted(codes)) == members:
            out.append(c.model_copy(update={"multiplicity": len(members)}))
        elif codes is not None and len(codes) == 1:
            entries = index.class_entries(members)
            out.append(c.model_copy(update={"equivalent_pairs": entries, "multiplicity": len(members)}))
        else:
            conflicts.append(c.id)
    if conflicts:
        raise _conflict(
            conflicts,
            repeated,
            "a row's equivalent pairs must be its pair orbit or its own single pair; remove the rows "
            "(couplings.remove) or re-import them",
        )
    return project.model_copy(update={"couplings": tuple(out)})


def _atom_orbits(project: Project) -> list[tuple[int, ...]]:
    """Each coupling's full pair orbit in atom indices (sorted pair codes). Without a declaration a
    pair's orbit is the pair itself. Atom indices, not spins: a draft may leave an H atom without a
    spin, and an orbit through it is still compared (round 78)."""
    g = project.molecule.geometry
    if not isinstance(g, ImportedGeometry) or not project.couplings:
        return [() for _ in project.couplings]
    n = len(g.atoms)
    atom_of = {s.id: int(s.atom) for s in project.molecule.spins if s.atom is not None}
    a = np.array([atom_of[c.spin_a] for c in project.couplings], dtype=np.int64)
    b = np.array([atom_of[c.spin_b] for c in project.couplings], dtype=np.int64)
    if project.molecule.symmetry is None:
        perms = np.arange(n, dtype=np.int64)[None, :]
    else:
        perms = validated_symmetry(project).permutations.astype(np.int64)
    pa, pb = perms[:, a], perms[:, b]
    codes = np.sort(np.minimum(pa, pb) * n + np.maximum(pa, pb), axis=0)
    return [tuple(sorted(set(column))) for column in codes.T.tolist()]


def orbit_changes(before: Project, after: Project) -> list[str]:
    """The rows whose full pair-orbit membership differs between two projects (a merge, a split or
    an expansion: D-3 declaration and isotope edits), compared in atom indices."""
    if not before.couplings:
        return []
    old, new = _atom_orbits(before), _atom_orbits(after)
    return [c.id for c, x, y in zip(after.couplings, old, new, strict=True) if x != y]


def invalid_classes(project: Project) -> list[str]:
    """The rows whose class is not an equivalence of the project's (non-fixed) model: leaving the
    fixed-geometry model keeps a class only where it stays valid (D-3)."""
    out = []
    for c in project.couplings:
        if c.multiplicity == 1 and len(c.equivalent_pairs) <= 1:
            continue
        single = project.model_copy(update={"couplings": (c,)})
        try:
            _validate_observation_classes(single)
        except ValueError:
            out.append(c.id)
    return out


@dataclass(frozen=True, slots=True)
class FixedProblem:
    """What a fixed-geometry fit needs: the validated symmetry, the rows, the data, and each row's
    orbit key in spin IDs."""

    validated: Validated
    rows: FixedRows
    y: np.ndarray
    sigma: np.ndarray
    keys: tuple[tuple[str, str], ...]


_FIXED = ByIdentity()


def fixed_problem_for(project: Project) -> FixedProblem:
    """The fixed-geometry problem of a project ready to fit; ValueError (or ``SymmetryError``
    ``FIT_TOO_LARGE``, checked before any row is built) says what is missing."""
    value: FixedProblem = _FIXED.get(project, lambda: _fixed_problem_for(project))
    return value


@dataclass(frozen=True, slots=True)
class FixedColumns:
    """A fixed-geometry project's observations as plain columns: what the fit reads of them."""

    ids: list[str]
    spin_a: list[str]
    spin_b: list[str]
    values: list[float]
    sigmas: list[float]

    @staticmethod
    def of(project: Project) -> FixedColumns:
        cs = project.couplings
        return FixedColumns(
            [c.id for c in cs],
            [c.spin_a for c in cs],
            [c.spin_b for c in cs],
            [c.value.value for c in cs],
            [c.sigma.value for c in cs],
        )


def _fixed_problem_for(project: Project, *, check: bool = True) -> FixedProblem:
    if check and len(project.couplings) <= MAX_FIT_ROWS:
        validate_project(project)
    return fixed_problem_from(project, FixedColumns.of(project))


def fixed_problem_from(project: Project, columns: FixedColumns) -> FixedProblem:
    """The fixed-geometry problem from a project's molecule and model and its observation columns.
    The job worker calls it with its committed input (``jobs.job_input``: the session's state,
    validated on commit, sent as columns; rounds 77–78); everything else validates first
    (``fixed_problem_for``). The declared symmetry, the rows and their keys are computed here, and
    the core still refuses bad endpoints, non-proton pairs and repeated orbits."""
    from dipolar_core.nuclides import dipolar_constant_hz_a3
    from dipolar_core.symmetry import fixed_rows

    if project.model.kind != "fixed":
        raise ValueError("the project's model is not a fixed-geometry fit")
    n = len(columns.ids)
    if n > MAX_FIT_ROWS:  # D-11, before any work (also checked by the core)
        raise SymmetryError("FIT_TOO_LARGE", f"{n} observations: at most {MAX_FIT_ROWS} rows are fitted")
    if project.molecule.symmetry is None:
        raise ValueError("a fixed-geometry fit needs the molecule's declared symmetry")
    if not n:
        raise ValueError("the project has no couplings to fit")
    validated = validated_symmetry(project)
    atom_of = {s.id: s.atom for s in project.molecule.spins}
    pairs = [(int(atom_of[a]), int(atom_of[b])) for a, b in zip(columns.spin_a, columns.spin_b, strict=True)]  # type: ignore[arg-type]
    rows = fixed_rows(validated, pairs, dipolar_constant_hz_a3("1H", "1H"))
    index = orbit_index(project)
    ra = np.array([index.rank[x] for x in columns.spin_a], dtype=np.intp)
    rb = np.array([index.rank[x] for x in columns.spin_b], dtype=np.intp)
    keys = tuple(index.pair(int(code)) for code in index.codes(ra, rb).min(axis=0).tolist())
    return FixedProblem(validated, rows, np.array(columns.values), np.array(columns.sigmas), keys)


_PROBLEMS = ByIdentity()


def problem_for(project: Project) -> Problem:
    """The D3 problem of a project that is ready to fit; ValueError says what is missing. A project
    is immutable, so its problem is built (and the project validated) once while it is current
    (M3 step 4b); a failure is not cached."""
    problem: Problem = _PROBLEMS.get(project, lambda: _problem_for(project))
    return problem


def _problem_for(project: Project) -> Problem:
    validate_project(project)
    g, m = project.molecule.geometry, project.model
    if m.kind == "fixed":
        raise ValueError("the fixed-geometry model has no torsion (fixed_problem_for)")
    if isinstance(g, ImportedGeometry) and g.torsion is None:
        raise ValueError(DRAFT_REASON)
    if not project.couplings:
        raise ValueError("the project has no couplings to fit")
    y = np.array([c.value.value for c in project.couplings])
    sigma = np.array([c.sigma.value for c in project.couplings])
    if isinstance(g, BiphenylTemplate):
        index = {s.id: i for i, s in enumerate(project.molecule.spins)}
        pairs = tuple((index[c.spin_a], index[c.spin_b]) for c in project.couplings)
        geometry = BiphenylGeometry(r_cc=g.r_cc.value, r_ch=g.r_ch.value, r_inter=g.r_inter.value)
        if m.kind == "jump4":
            problem = jump_problem(pairs, y, sigma, geometry)
        else:
            domain = "acute" if m.phi_domain_deg == (0.0, 90.0) else "fixed-labels"
            problem = rigid_problem(pairs, y, sigma, geometry, order=m.order, frame=m.frame, domain=domain)  # type: ignore[arg-type]
        assert m.phi_domain_deg is not None
        lo, hi = m.phi_domain_deg
        if (float(problem.lower[0]), float(problem.upper[0])) != (lo, hi):
            raise ValueError(f"the template supports the domains [0, 90] and [0, 180], not [{lo}, {hi}]")
        return problem
    assert isinstance(g, ImportedGeometry)
    if g.torsion is None:
        raise ValueError(DRAFT_REASON)
    assert m.phi_domain_deg is not None
    atom_of = {s.id: s.atom for s in project.molecule.spins}
    pairs = tuple((int(atom_of[c.spin_a]), int(atom_of[c.spin_b])) for c in project.couplings)  # type: ignore[arg-type]
    isotopes = tuple(("1H", "1H") for _ in project.couplings)
    return imported_problem(_torsion_geometry(g), pairs, isotopes, y, sigma, order=m.order, domain_deg=m.phi_domain_deg)
