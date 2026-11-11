"""From a project to a D3 problem (M1 step 4): the one place that maps the saved science onto
``dipolar_core``.

- ``validate_project`` states the invariants every project must satisfy, draft or not. Project
  files are checked on load.
- ``problem_for`` adds what fitting needs: couplings, a declared torsion for imported geometry,
  and a supported domain.
"""

from __future__ import annotations

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
from dipolar_core.torsion import TorsionGeometry, imported_problem

from dipolar_app.project import BiphenylTemplate, Coupling, ImportedGeometry, Project

#: Torsions at which a declared equivalence class must give identical design rows.
_PROBE_FRACTIONS = (0.137, 0.5, 0.861)
_ROW_RTOL = 1e-9


def _resolve_pair(entry: str, by_label: dict[str, str]) -> frozenset[str] | None:
    """An ``equivalent_pairs`` entry "A-B" as a pair of spin IDs, splitting at any hyphen that
    leaves two known labels (labels may themselves contain hyphens)."""
    for k, ch in enumerate(entry):
        if ch == "-" and entry[:k] in by_label and entry[k + 1 :] in by_label:
            return frozenset((by_label[entry[:k]], by_label[entry[k + 1 :]]))
    return None


def validate_project(project: Project) -> None:
    """Raise ValueError naming the first broken invariant, or return None."""
    g, m = project.molecule.geometry, project.model
    spins = project.molecule.spins
    if len({s.id for s in spins}) != len(spins):
        raise ValueError("spin IDs must be unique")
    if len({s.label for s in spins}) != len(spins):
        raise ValueError("spin labels must be unique (they identify spins during import)")
    if len({c.id for c in project.couplings}) != len(project.couplings):
        raise ValueError("coupling IDs must be unique")
    numbers = [int(c.id[4:]) for c in project.couplings]
    if numbers and max(numbers) >= project.next_coupling_id:
        raise ValueError("next_coupling_id must exceed every coupling number (IDs are never reused)")
    known = {s.id for s in spins}
    for c in project.couplings:
        if c.spin_a not in known or c.spin_b not in known or c.spin_a == c.spin_b:
            raise ValueError(f"coupling {c.id} must join two different spins of the project")
        if not c.sigma.value > 0:
            raise ValueError(f"coupling {c.id}: sigma must be positive")
    lo, hi = m.phi_domain_deg
    if not lo < hi:
        raise ValueError("the torsion domain must have lower < upper")
    if isinstance(g, BiphenylTemplate):
        if m.frame == "input":
            raise ValueError("the template uses the 'bisector' or 'ring-a' frame")
        if len(spins) != len(PROTON_LABELS) or any(s.atom is not None for s in spins):
            raise ValueError("the biphenyl template has its ten protons, in template order, without atom indices")
        if m.kind == "jump4" and (m.order != "bisector-diagonal" or m.frame != "bisector"):
            raise ValueError("the jump model uses the bisector-diagonal order model in the bisector frame")
        if not (0.0 <= lo and hi <= (90.0 if m.kind == "jump4" else 180.0)):
            raise ValueError("the template's torsion domain lies within [0, 90] (jump) or [0, 180] (rigid)")
    else:
        if m.kind != "rigid" or m.order == "bisector-diagonal" or m.frame != "input":
            raise ValueError("imported geometry uses the rigid model, order 'c1' or 'c2z', in the 'input' frame")
        n = len(g.atoms)
        for s in spins:
            if s.atom is None or not s.atom < n or g.atoms[s.atom].element != "H":
                raise ValueError(f"spin {s.id} must name a hydrogen atom of the imported geometry")
        if len({s.atom for s in spins}) != len(spins):
            raise ValueError("two spins name the same atom")
        if g.torsion is not None and not all(0 <= k < n for k in g.torsion):
            raise ValueError("the torsion atoms must exist")
        if hi - lo > 360.0:
            raise ValueError("the torsion domain may span at most 360 deg")
    _validate_observation_classes(project)


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
            resolved = [_resolve_pair(e, by_label) for e in c.equivalent_pairs]
            if any(r is None for r in resolved):
                raise ValueError(f"coupling {c.id}: an equivalent pair names an unknown spin label")
            members = [r for r in resolved if r is not None]
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
    lo, hi = m.phi_domain_deg
    for fraction in _PROBE_FRACTIONS:
        phi = lo + fraction * (hi - lo)
        for c, members in classes:
            pairs = tuple(tuple(index[s] for s in sorted(pair)) for pair in members)
            rows = _design(project, pairs, phi)  # type: ignore[arg-type]
            scale = max(1.0, float(np.abs(rows).max()))
            if not np.allclose(rows, rows[0], rtol=0, atol=_ROW_RTOL * scale):
                raise ValueError(
                    f"coupling {c.id}: its equivalent pairs are not equivalent under the {m.kind}/{m.order} "
                    f"model (they predict different couplings at phi = {phi:.4g}); re-group the observations"
                )


def _design(project: Project, pairs: tuple[tuple[int, int], ...], phi: float) -> np.ndarray:
    g, m = project.molecule.geometry, project.model
    if isinstance(g, BiphenylTemplate):
        geometry = BiphenylGeometry(r_cc=g.r_cc.value, r_ch=g.r_ch.value, r_inter=g.r_inter.value)
        if m.kind == "jump4":
            return jump_design(phi, pairs, geometry)
        return rigid_design(phi, pairs, geometry, order=m.order, frame=m.frame)  # type: ignore[arg-type]
    assert isinstance(g, ImportedGeometry)
    atom_of = [s.atom for s in project.molecule.spins]
    atom_pairs = tuple((int(atom_of[a]), int(atom_of[b])) for a, b in pairs)  # type: ignore[arg-type]
    elements = [a.element for a in g.atoms]
    positions = np.array([[a.x, a.y, a.z] for a in g.atoms])
    if g.torsion is None:
        from dipolar_core.forward import constraint_c1, constraint_c2z, design_rows

        c = constraint_c1() if m.order == "c1" else constraint_c2z()
        return design_rows(positions, atom_pairs, 1.0) @ c
    torsion = TorsionGeometry.from_atoms(elements, positions, g.torsion)
    zeros = np.zeros(len(atom_pairs))
    problem = imported_problem(torsion, atom_pairs, [("1H", "1H")] * len(atom_pairs), zeros, zeros + 1, order=m.order)
    return problem.design(np.array([phi]))


def problem_for(project: Project) -> Problem:
    """The D3 problem of a project that is ready to fit; ValueError says what is missing."""
    validate_project(project)
    g, m = project.molecule.geometry, project.model
    if isinstance(g, ImportedGeometry) and g.torsion is None:
        raise ValueError("imported geometry needs a declared torsion (a, i, j, b) to be fitted")
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
        lo, hi = m.phi_domain_deg
        if (float(problem.lower[0]), float(problem.upper[0])) != (lo, hi):
            raise ValueError(f"the template supports the domains [0, 90] and [0, 180], not [{lo}, {hi}]")
        return problem
    assert isinstance(g, ImportedGeometry)
    if g.torsion is None:
        raise ValueError("imported geometry needs a declared torsion (a, i, j, b) to be fitted")
    atom_of = {s.id: s.atom for s in project.molecule.spins}
    pairs = tuple((int(atom_of[c.spin_a]), int(atom_of[c.spin_b])) for c in project.couplings)  # type: ignore[arg-type]
    isotopes = tuple(("1H", "1H") for _ in project.couplings)
    torsion = TorsionGeometry.from_atoms(
        [a.element for a in g.atoms], np.array([[a.x, a.y, a.z] for a in g.atoms]), g.torsion
    )
    return imported_problem(torsion, pairs, isotopes, y, sigma, order=m.order, domain_deg=m.phi_domain_deg)
