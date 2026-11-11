"""From a project to a D3 problem (M1 step 4): the one place that maps the saved science onto
``dipolar_core``. ``check_project`` states the rules a project must satisfy to be fitted."""

from __future__ import annotations

import numpy as np
from dipolar_core.biphenyl import PROTON_LABELS, BiphenylGeometry, jump_problem, rigid_problem
from dipolar_core.problem import Problem
from dipolar_core.torsion import TorsionGeometry, imported_problem

from dipolar_app.project import BiphenylTemplate, ImportedGeometry, Project


def check_project(project: Project) -> None:
    """Raise ValueError naming the first inconsistency, or return None."""
    g, m = project.molecule.geometry, project.model
    spins = project.molecule.spins
    if len({s.id for s in spins}) != len(spins):
        raise ValueError("spin IDs must be unique")
    if len({c.id for c in project.couplings}) != len(project.couplings):
        raise ValueError("coupling IDs must be unique")
    known = {s.id for s in spins}
    for c in project.couplings:
        if c.spin_a not in known or c.spin_b not in known or c.spin_a == c.spin_b:
            raise ValueError(f"coupling {c.id} must join two different spins of the project")
        if not c.sigma.value > 0:
            raise ValueError(f"coupling {c.id}: sigma must be positive")
    pairs = [frozenset((c.spin_a, c.spin_b)) for c in project.couplings]
    if len(set(pairs)) != len(pairs):
        raise ValueError("each spin pair may appear once (merge symmetry copies into one coupling)")
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
        if g.torsion is None:
            raise ValueError("imported geometry needs a declared torsion (a, i, j, b) to be fitted")
        n = len(g.atoms)
        for s in spins:
            if s.atom is None or not s.atom < n or g.atoms[s.atom].element != "H":
                raise ValueError(f"spin {s.id} must name a hydrogen atom of the imported geometry")
        if len({s.atom for s in spins}) != len(spins):
            raise ValueError("two spins name the same atom")
        if not all(0 <= k < n for k in g.torsion):
            raise ValueError("the torsion atoms must exist")
        if hi - lo > 360.0:
            raise ValueError("the torsion domain may span at most 360 deg")


def problem_for(project: Project) -> Problem:
    """The D3 problem of a consistent project (``check_project`` first)."""
    check_project(project)
    g, m = project.molecule.geometry, project.model
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
    assert isinstance(g, ImportedGeometry) and g.torsion is not None
    atom_of = {s.id: s.atom for s in project.molecule.spins}
    pairs = tuple((int(atom_of[c.spin_a]), int(atom_of[c.spin_b])) for c in project.couplings)  # type: ignore[arg-type]
    isotopes = tuple(("1H", "1H") for _ in project.couplings)
    torsion = TorsionGeometry.from_atoms(
        [a.element for a in g.atoms], np.array([[a.x, a.y, a.z] for a in g.atoms]), g.torsion
    )
    return imported_problem(torsion, pairs, isotopes, y, sigma, order=m.order, domain_deg=m.phi_domain_deg)
