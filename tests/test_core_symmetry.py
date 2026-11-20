"""Phase 2 V1.2: symmetry and permutation classes (dipolar_core.symmetry), gated as frozen in
docs/phase2/v1.0-design.md §3 and docs/phase2-proposal.md (V1.2).

Every expected answer is computed independently of the module under test: couplings come from
the raw input geometry and the true tensor rotated into the input frame (forward.design_rows,
forward.order_matrix), never from the symmetry module's averaged geometry, operations or orbits.
The fixtures are synthetic.
"""

from __future__ import annotations

import math
import time
import tracemalloc

import numpy as np
import pytest
from dipolar_core import fixed
from dipolar_core import symmetry as sym
from dipolar_core.forward import design_rows, order_matrix, order_vector
from dipolar_core.nuclides import dipolar_constant_hz_a3

K = dipolar_constant_hz_a3("1H", "1H")
R_CC, R_CH, R_CCL = 1.3914, 1.0802, 1.74


# ---- Fixtures: (elements, masses, coordinates in the symmetry frame) ---------------------------------


def _ring(subst: dict[int, tuple[str, float]] | None = None, carbon13: int | None = None, start_deg: float = 0.0):
    """A planar six-ring in the xy plane, ring atom k at angle start + 60k. ``subst`` replaces the
    hydrogen on carbon k by (element, bond length)."""
    subst = subst or {}
    elements, masses, xyz = [], [], []
    for k in range(6):
        a = math.radians(start_deg + 60.0 * k)
        u = np.array([math.cos(a), math.sin(a), 0.0])
        elements.append("C")
        masses.append(13 if carbon13 == k else None)
        xyz.append(R_CC * u)
    for k in range(6):
        a = math.radians(start_deg + 60.0 * k)
        u = np.array([math.cos(a), math.sin(a), 0.0])
        element, bond = subst.get(k, ("H", R_CH))
        elements.append(element)
        masses.append(None)
        xyz.append((R_CC + bond) * u)
    return elements, masses, np.array(xyz)


def benzene():
    return _ring()  # D6h frame: z normal, x through C0–H6


def dcb14():
    """1,4-dichlorobenzene in its D2h frame: Cl on carbons 0 and 3 (along x), z normal."""
    return _ring({0: ("Cl", R_CCL), 3: ("Cl", R_CCL)})


def odcb_c2v():
    """o-dichlorobenzene in its C2v frame (z on C2, in-plane; x the ring normal; y in-plane):
    built in the plane, Cl on carbons 0 and 1, then the axes are permuted."""
    elements, masses, xyz = _ring({0: ("Cl", R_CCL), 1: ("Cl", R_CCL)}, start_deg=-120.0)
    # in-plane C2 axis bisects carbons 0 and 1, at angle -90°: map it to +z
    c2 = np.array([0.0, -1.0, 0.0])
    normal = np.array([0.0, 0.0, 1.0])
    axes = np.array([normal, np.cross(c2, normal), c2])
    return elements, masses, xyz @ axes.T


def tcb135():
    """1,3,5-trichlorobenzene, D3h: z normal, x along C0–Cl."""
    return _ring({0: ("Cl", R_CCL), 2: ("Cl", R_CCL), 4: ("Cl", R_CCL)})


def prism_d3h():
    """Six protons on a triangular prism (D3h, nonplanar) around a carbon."""
    xyz = [np.zeros(3)]
    for z in (1.0, -1.0):
        for k in range(3):
            a = math.radians(120.0 * k)
            xyz.append(np.array([1.5 * math.cos(a), 1.5 * math.sin(a), z]))
    return ["C"] + ["H"] * 6, [None] * 7, np.array(xyz)


def cs_fixture():
    """Cs (mirror z = 0): in-plane protons and one mirrored pair."""
    xyz = np.array(
        [[0.0, 0.0, 0.0], [2.4, 0.3, 0.0], [1.1, 2.2, 0.0], [-1.3, 1.6, 1.2], [-1.3, 1.6, -1.2], [0.6, -1.4, 0.0]]
    )
    return ["C", "H", "H", "H", "H", "H"], [None] * 6, xyz


def c1_fixture():
    xyz = np.array(
        [[0.0, 0.0, 0.0], [2.4, 0.3, 0.1], [1.1, 2.2, -0.4], [-1.3, 1.6, 1.2], [0.4, -1.9, 1.7], [2.9, -1.1, -1.5]]
    )
    return ["H"] * 6, [None] * 6, xyz


S_BY_GROUP = {  # true tensors in each group's symmetry subspace, ORDER_BASIS (Szz, Sxx−Syy, Sxy, Sxz, Syz)
    "C1": np.array([-0.21, 0.08, 0.03, -0.02, 0.05]),
    "Cs": np.array([-0.21, 0.08, 0.03, 0.0, 0.0]),
    "C2v": np.array([0.12, -0.20, 0.0, 0.0, 0.0]),
    "D2h": np.array([-0.18, 0.09, 0.0, 0.0, 0.0]),
    "D3h": np.array([-0.24, 0.0, 0.0, 0.0, 0.0]),
    "D6h": np.array([-0.26, 0.0, 0.0, 0.0, 0.0]),
}
FIXTURES = {
    "C1": c1_fixture,
    "Cs": cs_fixture,
    "C2v": odcb_c2v,
    "D2h": dcb14,
    "D3h": prism_d3h,
    "D6h": benzene,
}


def _rotation(seed: int) -> np.ndarray:
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q = q * np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return q


def _to_input(xyz_sym: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Place a symmetry-frame fixture in an arbitrary input frame: x_in = Qᵀ x_sym + t. The
    declaration's axes are the rows of Q (the symmetry axes in input coordinates)."""
    q = _rotation(seed)
    t = np.random.default_rng(seed + 1).normal(scale=5.0, size=3)
    return xyz_sym @ q + t, q


def _protons(elements: list[str], masses: list[int | None]) -> list[int]:
    return [i for i, (e, m) in enumerate(zip(elements, masses, strict=True)) if e == "H" and m in (None, 1)]


def _one_pair_per_orbit(v: sym.Validated, protons: list[int]) -> list[tuple[int, int]]:
    seen, pairs = set(), []
    for i, a in enumerate(protons):
        for b in protons[i + 1 :]:
            key, _ = v.pair_orbit(a, b)
            if key not in seen:
                seen.add(key)
                pairs.append((a, b))
    return pairs


def _couplings_from_input(xyz_in: np.ndarray, q: np.ndarray, s5_sym: np.ndarray, pairs) -> np.ndarray:
    """Independent target: the true tensor rotated into the input frame (S_in = Qᵀ S Q), and the
    raw input coordinates."""
    s_in = q.T @ order_matrix(s5_sym) @ q
    return design_rows(xyz_in, pairs, K) @ order_vector(s_in)


# ---- Operations and declarations ---------------------------------------------------------------------


def test_the_groups_are_closed_with_their_orders() -> None:
    for group, order in {"C1": 1, "Cs": 2, "C2v": 4, "D2h": 8, "D3h": 12, "D6h": 24}.items():
        ops = sym.operations(group)
        assert len(ops) == order
        for g in ops:
            assert np.allclose(g @ g.T, np.eye(3), atol=1e-12)
            for h in ops:
                assert min(np.max(np.abs(g @ h - k)) for k in ops) < 1e-12  # closure


def test_declarations_outside_scope_are_refused() -> None:
    ok = np.eye(3)
    cases = [
        (dict(point_group="D6h", axes=ok, medium="chiral-nematic"), "MEDIUM_NOT_SUPPORTED"),
        (dict(point_group="C3v", axes=ok), "POINT_GROUP_NOT_SUPPORTED"),
        (dict(point_group="C2", axes=ok), "POINT_GROUP_NOT_SUPPORTED"),
        (dict(point_group="C2h", axes=ok), "POINT_GROUP_NOT_SUPPORTED"),
        (dict(point_group="Oh", axes=ok), "POINT_GROUP_NOT_SUPPORTED"),
        (dict(point_group="D6h", axes=np.diag([1.0, 1.0, 1.0 + 1e-6])), "AXES_INVALID"),
        (dict(point_group="D6h", axes=np.diag([1.0, 1.0, -1.0])), "AXES_INVALID"),
        (dict(point_group="D6h", axes=ok, tolerance_a=0.2), "TOLERANCE_OUT_OF_RANGE"),
        (dict(point_group="D6h", axes=ok, tolerance_a=0.0005), "TOLERANCE_OUT_OF_RANGE"),
    ]
    elements, masses, xyz = benzene()
    for kwargs, code in cases:
        with pytest.raises(sym.SymmetryError) as err:
            sym.validate(xyz, elements, masses, sym.Declaration(**kwargs))
        assert err.value.code == code, kwargs


def test_axes_within_1e_9_are_accepted_and_reorthonormalized() -> None:
    elements, masses, xyz = benzene()
    axes = np.eye(3) + 3e-10 * np.random.default_rng(0).normal(size=(3, 3))
    v = sym.validate(xyz, elements, masses, sym.Declaration("D6h", axes))
    assert np.allclose(v.rotation @ v.rotation.T, np.eye(3), atol=1e-15)


def test_the_atom_limit_is_checked_first() -> None:
    n = sym.MAX_ATOMS + 1
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(np.zeros((n, 3)), ["H"] * n, [None] * n, sym.Declaration("C1", np.eye(3)))
    assert err.value.code == "TOO_MANY_ATOMS"


def test_the_isotope_table() -> None:
    assert sym.normalize_isotope("H", None) == ("H", None)
    assert sym.normalize_isotope("H", 1) == ("H", None)  # a default given explicitly is absent
    assert sym.normalize_isotope("D", None) == ("D", None)
    assert sym.normalize_isotope("C", 13) == ("C", 13)
    assert sym.normalize_isotope("C", 12) == ("C", None)
    assert sym.normalize_isotope("N", 15) == ("N", 15)
    assert sym.normalize_isotope("O", 16) == ("O", None)
    for element, mass in (("H", 2), ("C", 14), ("O", 17), ("N", 13), ("Xx", None)):
        with pytest.raises(sym.SymmetryError) as err:
            sym.normalize_isotope(element, mass)
        assert err.value.code == "ISOTOPE_NOT_SUPPORTED", (element, mass)


# ---- Recovery, validation and the averaged geometry ------------------------------------------------


@pytest.mark.parametrize("group", list(FIXTURES))
def test_noiseless_recovery_for_every_supported_group(group: str) -> None:
    elements, masses, xyz_sym = FIXTURES[group]()
    xyz_in, q = _to_input(xyz_sym, seed=len(group))
    v = sym.validate(xyz_in, elements, masses, sym.Declaration(group, q))
    pairs = _one_pair_per_orbit(v, _protons(elements, masses))
    rows = sym.fixed_rows(v, pairs, K)
    assert rows.subspace.shape[1] == fixed.SUBSPACES[group].shape[1]
    d = _couplings_from_input(xyz_in, q, S_BY_GROUP[group], pairs)
    res = fixed.fit_fixed(rows.design_s5, d, np.full(len(d), 0.01), rows.subspace)
    assert res.rank_verified, (group, res.rank_reason)
    assert res.s5 == pytest.approx(S_BY_GROUP[group], abs=1e-10)
    assert res.predictions == pytest.approx(d, abs=1e-8)


def test_ideal_benzene_recovers_its_single_s_zz() -> None:
    elements, masses, xyz = benzene()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    pairs = _one_pair_per_orbit(v, _protons(elements, masses))
    assert len(pairs) == 3  # ortho, meta, para
    rows = sym.fixed_rows(v, pairs, K)
    d = _couplings_from_input(xyz, np.eye(3), S_BY_GROUP["D6h"], pairs)
    res = fixed.fit_fixed(rows.design_s5, d, np.full(3, 0.01), rows.subspace)
    assert res.required_rank == 1 and res.nu == 2
    assert res.s5[0] == pytest.approx(-0.26, abs=1e-12)


def test_a_translated_and_rotated_file_validates() -> None:
    elements, masses, xyz = dcb14()
    xyz_in, q = _to_input(xyz, seed=11)
    v = sym.validate(xyz_in + 100.0, elements, masses, sym.Declaration("D2h", q))
    assert v.max_displacement_a < 1e-9


def test_the_averaged_geometry_is_exactly_symmetric_within_tolerance_noise() -> None:
    elements, masses, xyz = benzene()
    noisy = xyz + np.random.default_rng(3).uniform(-0.003, 0.003, size=xyz.shape)
    v = sym.validate(noisy, elements, masses, sym.Declaration("D6h", np.eye(3)))
    assert 0 < v.max_displacement_a <= 0.01
    for g, perm in zip(v.operations, v.permutations, strict=True):
        assert np.allclose(v.averaged @ g.T, v.averaged[perm], atol=1e-12)
    assert np.allclose(v.averaged.mean(axis=0), 0.0, atol=1e-12)


def test_a_symmetry_the_geometry_lacks_is_refused() -> None:
    elements, masses, xyz = dcb14()
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    assert err.value.code == "SYMMETRY_NOT_SATISFIED"
    tilt = np.array([[1, 0, 0], [0, math.cos(0.2), math.sin(0.2)], [0, -math.sin(0.2), math.cos(0.2)]])
    elements, masses, xyz = benzene()
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(xyz, elements, masses, sym.Declaration("D6h", tilt))
    assert err.value.code == "SYMMETRY_NOT_SATISFIED"
    moved = xyz.copy()
    moved[6, 2] += 0.05  # one proton out of the plane, beyond 0.01 Å
    with pytest.raises(sym.SymmetryError):
        sym.validate(moved, elements, masses, sym.Declaration("D6h", np.eye(3)))


# ---- Orbits, invariance, counting -------------------------------------------------------------------


def test_relabelling_and_joint_endpoint_permutation_leave_the_fit_unchanged() -> None:
    elements, masses, xyz = dcb14()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    pairs = _one_pair_per_orbit(v, _protons(elements, masses))
    d = _couplings_from_input(xyz, np.eye(3), S_BY_GROUP["D2h"], pairs)
    base = _fit(v, pairs, d)

    # joint endpoint permutation: every pair replaced by its image under some operation
    for g in range(len(v.operations)):
        perm = v.permutations[g]
        moved = [(int(perm[a]), int(perm[b])) for a, b in pairs]
        assert _fit(v, moved, d).b == pytest.approx(base.b, abs=1e-13)

    # relabelling: the atoms in another order
    order = np.random.default_rng(5).permutation(len(elements))
    inverse = np.argsort(order)
    v2 = sym.validate(xyz[order], [elements[i] for i in order], [masses[i] for i in order],
                      sym.Declaration("D2h", np.eye(3)))  # fmt: skip
    relabelled = [(int(inverse[a]), int(inverse[b])) for a, b in pairs]
    assert _fit(v2, relabelled, d).b == pytest.approx(base.b, abs=1e-13)


def _fit(v: sym.Validated, pairs, d: np.ndarray) -> fixed.FixedResult:
    rows = sym.fixed_rows(v, pairs, K)
    return fixed.fit_fixed(rows.design_s5, d, np.full(len(d), 0.01), rows.subspace)


def test_the_14_dichlorobenzene_equivalence_fixture() -> None:
    """H2 and H6 (atoms 7 and 11) share a site orbit; H2–H3 and H6–H3 are distinct pair orbits
    with distinct reduced rows, and a specified tensor predicts them differently. Site orbits are
    chemical equivalence; nothing is merged as magnetic equivalence."""
    elements, masses, xyz = dcb14()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    h2, h3, h6 = 7, 8, 11
    assert v.site_orbit[h2] == v.site_orbit[h6]
    key_23, members_23 = v.pair_orbit(h2, h3)
    key_63, members_63 = v.pair_orbit(h6, h3)
    assert key_23 != key_63 and not (members_23 & members_63)
    rows = sym.fixed_rows(v, [(h2, h3), (h6, h3)], K)
    reduced = (rows.design_s5 / fixed.ORTHO_SCALE) @ rows.subspace
    assert np.max(np.abs(reduced[0] - reduced[1])) > 1.0
    s = S_BY_GROUP["D2h"]
    d = design_rows(xyz, [(h2, h3), (h6, h3)], K) @ s
    assert abs(d[0] - d[1]) > 1.0


def test_symmetry_copies_neither_inflate_n_nor_nu() -> None:
    elements, masses, xyz = dcb14()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    pairs = _one_pair_per_orbit(v, _protons(elements, masses))
    rows = sym.fixed_rows(v, pairs, K)
    assert rows.design_s5.shape[0] == len(pairs) == 3
    _key, members = v.pair_orbit(*pairs[0])
    copy = next(m for m in sorted(members) if m != tuple(sorted(pairs[0])))
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(v, [*pairs, copy], K)
    assert err.value.code == "PAIR_ORBIT_REPEATED"
    assert rows.multiplicities[0] == len(members)
    d = design_rows(xyz, pairs, K) @ S_BY_GROUP["D2h"]
    assert fixed.fit_fixed(rows.design_s5, d, np.full(3, 0.01), rows.subspace).nu == 1


def test_only_proton_pairs_are_observations() -> None:
    elements, masses, xyz = dcb14()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(v, [(6, 7)], K)  # Cl–H
    assert err.value.code == "OBSERVATION_NOT_PROTON"


# ---- Isotopes ----------------------------------------------------------------------------------------


#: C2v axes for a ring substituted at carbon 0 (on +x): z along that in-plane C2 axis, x the ring
#: normal, y = z × x. Rows are the symmetry axes in input coordinates.
C2V_ALONG_X = np.array([[0.0, 0.0, 1.0], [0.0, -1.0, 0.0], [1.0, 0.0, 0.0]])


def test_benzene_d1_is_refused_as_d6h_and_accepted_as_c2v() -> None:
    elements, masses, xyz = benzene()
    elements[6] = "D"  # deuterium on carbon 0, along +x
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    assert err.value.code == "SYMMETRY_NOT_SATISFIED"
    v = sym.validate(xyz, elements, masses, sym.Declaration("C2v", C2V_ALONG_X))
    protons = _protons(elements, masses)
    assert 6 not in protons
    groups = {tuple(sorted(i for i in protons if v.site_orbit[i] == v.site_orbit[p])) for p in protons}
    assert groups == {(7, 11), (8, 10), (9,)}
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(v, [(6, 7)], K)  # D is not a spin
    assert err.value.code == "OBSERVATION_NOT_PROTON"


def test_carbon_13_splits_an_orbit() -> None:
    elements, masses, xyz = _ring(carbon13=0)
    with pytest.raises(sym.SymmetryError):
        sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    v = sym.validate(xyz, elements, masses, sym.Declaration("C2v", C2V_ALONG_X))
    protons = _protons(elements, masses)
    groups = {tuple(sorted(i for i in protons if v.site_orbit[i] == v.site_orbit[p])) for p in protons}
    assert groups == {(6,), (7, 11), (8, 10), (9,)}  # the proton on ¹³C stands alone


# ---- Benzene's scale degeneracy ----------------------------------------------------------------------


def test_proton_only_benzene_has_the_scale_degeneracy() -> None:
    """Scaling the whole ring by λ leaves every prediction unchanged when S_zz scales by λ³: the
    fitted S_zz from the same couplings is exactly λ³ times the original."""
    elements, masses, xyz = benzene()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    pairs = _one_pair_per_orbit(v, _protons(elements, masses))
    d = _couplings_from_input(xyz, np.eye(3), S_BY_GROUP["D6h"], pairs)
    lam = 1.03
    v2 = sym.validate(lam * xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    rows, rows2 = sym.fixed_rows(v, pairs, K), sym.fixed_rows(v2, pairs, K)
    r1 = fixed.fit_fixed(rows.design_s5, d, np.full(3, 0.01), rows.subspace)
    r2 = fixed.fit_fixed(rows2.design_s5, d, np.full(3, 0.01), rows2.subspace)
    assert r2.s5[0] == pytest.approx(lam**3 * r1.s5[0], rel=1e-12)
    assert r2.predictions == pytest.approx(r1.predictions, rel=1e-12)


# ---- Guards below the validation layer ---------------------------------------------------------------


def test_the_ambiguity_guard() -> None:
    """Two same-isotope atoms within the tolerance of one image: impossible in a valid project
    (atoms ≥ 0.5 Å apart, tolerance ≤ 0.1 Å), so tested directly."""
    points = np.array([[0.0, 0.0, 0.0], [0.05, 0.0, 0.0], [3.0, 0.0, 0.0]])
    keys = [("H", None)] * 3
    with pytest.raises(sym.SymmetryError) as err:
        sym.match_operation(points, keys, points, 0.1)
    assert err.value.code == "SYMMETRY_AMBIGUOUS"


def test_the_group_action_guard() -> None:
    """Permutations that do not compose like the group table are refused."""
    ops = sym.operations("C2v")
    table = sym.multiplication_table(ops)
    identity = int(np.argmin([np.max(np.abs(g - np.eye(3))) for g in ops]))
    perms = np.tile(np.arange(2), (4, 1))
    sym.check_action(perms, table)  # the trivial action is an action
    bad = perms.copy()
    bad[(identity + 1) % 4] = [1, 0]  # one non-identity element swaps, its products do not
    with pytest.raises(sym.SymmetryError) as err:
        sym.check_action(bad, table)
    assert err.value.code == "SYMMETRY_NOT_AN_ACTION"
    with pytest.raises(sym.SymmetryError):
        sym.check_action(np.array([[0, 0]] * 4), table)  # not a permutation


# ---- Budgets (D-11) ----------------------------------------------------------------------------------


def _large_d6h(n_max: int) -> tuple[list[str], list[None], np.ndarray]:
    ops = sym.operations("D6h")
    rng = np.random.default_rng(12)
    points: list[np.ndarray] = []
    while len(points) + len(ops) <= n_max:
        p = rng.uniform(-20.0, 20.0, size=3)
        images = np.array([g @ p for g in ops])
        gaps = np.linalg.norm(images[:, None] - images[None], axis=-1)[np.triu_indices(len(ops), 1)]
        if gaps.min() < 1.0:
            continue
        if points and np.min(np.linalg.norm(np.array(points)[:, None] - images[None], axis=-1)) < 1.0:
            continue
        points.extend(images)
    return ["H"] * len(points), [None] * len(points), np.array(points)


def test_validation_of_1000_atoms_in_d6h_stays_within_budget() -> None:
    elements, masses, xyz = _large_d6h(sym.MAX_ATOMS)
    assert len(elements) > 950
    decl = sym.Declaration("D6h", np.eye(3))
    sym.validate(xyz, elements, masses, decl)  # warm
    tracemalloc.start()
    start = time.process_time()
    sym.validate(xyz, elements, masses, decl)
    cpu = time.process_time() - start
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert cpu <= 2.0  # D-11: 1 s on the named hardware, 2× margin
    assert peak <= 200 * 2**20


def test_validation_runs_the_action_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Added after the freeze (a surviving mutant removed the call): validate must refuse matches
    that are permutations but not an action. Reached here by a patched matcher, since a valid
    geometry cannot produce them."""
    elements, masses, xyz = benzene()
    real = sym.match_operation
    calls = {"n": 0}

    def skewed(points, keys, mapped, tol):  # type: ignore[no-untyped-def]
        perm = real(points, keys, mapped, tol)
        calls["n"] += 1
        if calls["n"] == 2:  # one non-identity operation: swap two of its images
            perm = perm.copy()
            perm[[6, 7]] = perm[[7, 6]]
        return perm

    monkeypatch.setattr(sym, "match_operation", skewed)
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    assert err.value.code == "SYMMETRY_NOT_AN_ACTION"


# ---- Round 75 gates (frozen before the fixes) -------------------------------------------------------


def test_orbit_keys_and_members_are_the_hard_coded_ones() -> None:
    """1,4-dichlorobenzene (D2h): protons on carbons 1, 2, 4, 5 are atoms 7, 8, 10, 11."""
    elements, masses, xyz = dcb14()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    expected = {
        (10, 11): ((7, 8), {(7, 8), (10, 11)}),  # ortho
        (8, 10): ((7, 11), {(7, 11), (8, 10)}),  # meta, across Cl
        (11, 8): ((7, 10), {(7, 10), (8, 11)}),  # para
    }
    for pair, (key, members) in expected.items():
        assert v.pair_orbit(*pair) == (key, frozenset(members))
    rows = sym.fixed_rows(v, list(expected), K)
    assert rows.keys == ((7, 8), (7, 11), (7, 10)) and rows.multiplicities == (2, 2, 2)


def test_a_noisy_cs_geometry_is_projected_and_its_rows_use_the_projection() -> None:
    """The expected averaged geometry is the analytic projection onto Cs (mirror z = 0), computed
    here: in-plane atoms lose their z; the mirrored pair (3, 4) is averaged with its image."""
    elements, masses, xyz = cs_fixture()
    noise = np.random.default_rng(21).uniform(-0.004, 0.004, size=xyz.shape)
    noisy = xyz + noise
    y = noisy - noisy.mean(axis=0)
    mirror = np.diag([1.0, 1.0, -1.0])
    expected = y.copy()
    for i in (0, 1, 2, 5):
        expected[i] = (y[i] + y[i] @ mirror) / 2
    expected[3] = (y[3] + y[4] @ mirror) / 2
    expected[4] = expected[3] @ mirror
    v = sym.validate(noisy, elements, masses, sym.Declaration("Cs", np.eye(3)))
    assert np.allclose(v.averaged, expected, atol=1e-13)
    assert v.max_displacement_a == pytest.approx(np.max(np.linalg.norm(expected - y, axis=1)), abs=1e-13)
    pairs = [(1, 2), (1, 5), (2, 5), (1, 4), (2, 4), (4, 5), (3, 4)]
    keys = [(1, 2), (1, 5), (2, 5), (1, 3), (2, 3), (3, 5), (3, 4)]
    rows = sym.fixed_rows(v, pairs, K)
    assert list(rows.keys) == keys
    assert np.allclose(rows.design_s5, design_rows(expected, keys, K), rtol=1e-12, atol=1e-9)


@pytest.mark.parametrize("pair", [(-1, 0), (0.9, 1), (3, 0), (0, 3), (True, 1), (1, 1), ("1", 0)])
def test_invalid_endpoints_are_refused_not_reinterpreted(pair: tuple[object, object]) -> None:
    elements, masses, xyz = ["H", "H", "H"], [None] * 3, np.array([[0.0, 0, 0], [2.5, 0, 0], [0.4, 2.2, 0.3]])
    v = sym.validate(xyz, elements, masses, sym.Declaration("C1", np.eye(3)))
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(v, [pair], K)  # type: ignore[list-item]
    assert err.value.code == "OBSERVATION_INVALID_INDEX"
    with pytest.raises(sym.SymmetryError) as err:
        v.pair_orbit(*pair)  # type: ignore[arg-type]
    assert err.value.code == "OBSERVATION_INVALID_INDEX"
    assert sym.fixed_rows(v, [(np.int64(0), np.int64(2))], K).keys == ((0, 2),)


def test_row_construction_is_linear_in_the_observations() -> None:
    """D-11: up to 20 000 rows; building them must not be quadratic (round 75)."""
    rng = np.random.default_rng(31)
    xyz = rng.uniform(-60.0, 60.0, size=(201, 3))
    n = len(xyz)
    v = sym.validate(xyz, ["H"] * n, [None] * n, sym.Declaration("C1", np.eye(3)))
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)][:20_000]
    assert len(pairs) == 20_000
    start = time.process_time()
    rows = sym.fixed_rows(v, pairs, K)
    assert time.process_time() - start <= 1.0
    assert rows.design_s5.shape == (20_000, 5)


def test_the_cutoff_is_inclusive_and_explained() -> None:
    tol = 0.0625  # exactly representable
    points = np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
    keys = [("H", None)] * 2
    for d, ok in ((tol * (1 - 1e-9), True), (tol, True), (tol * (1 + 1e-9), False)):
        mapped = points + np.array([[d, 0.0, 0.0], [0.0, 0.0, 0.0]])
        if ok:
            assert list(sym.match_operation(points, keys, mapped, tol)) == [0, 1]
        else:
            with pytest.raises(sym.SymmetryError) as err:
                sym.match_operation(points, keys, mapped, tol)
            assert "0.0625000000625" in str(err.value)  # enough digits to see why


def test_the_multiplication_table_on_noncommuting_products() -> None:
    ops = sym.operations("D6h")
    table = sym.multiplication_table(ops)
    c6 = next(
        i
        for i, g in enumerate(ops)
        if np.allclose(g, [[0.5, -math.sqrt(3) / 2, 0], [math.sqrt(3) / 2, 0.5, 0], [0, 0, 1]])
    )
    c2x = next(i for i, g in enumerate(ops) if np.allclose(g, np.diag([1.0, -1.0, -1.0])))
    gh, hg = ops[c6] @ ops[c2x], ops[c2x] @ ops[c6]
    assert not np.allclose(gh, hg)
    assert np.allclose(ops[table[c6, c2x]], gh) and np.allclose(ops[table[c2x, c6]], hg)


def test_operations_have_structural_zeros() -> None:
    """The z row and column of every D6h operation are exact zeros off the diagonal."""
    for g in sym.operations("D6h"):
        assert g[0, 2] == g[1, 2] == g[2, 0] == g[2, 1] == 0.0


def test_axes_just_outside_the_tolerance_are_refused() -> None:
    elements, masses, xyz = benzene()
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.diag([1.0, 1.0, 1.0 + 2e-9])))
    assert err.value.code == "AXES_INVALID"


def test_explicit_default_masses_match_omitted_ones() -> None:
    elements, masses, xyz = benzene()
    masses = [12 if i % 2 == 0 and i < 6 else None for i in range(12)]
    masses[7] = 1
    sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))


def test_a_nitrogen_15_breaks_the_symmetry_it_should() -> None:
    elements, masses, xyz = dcb14()
    elements[0] = elements[3] = "N"  # a pyrazine-like ring: N on carbons 0 and 3
    sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    masses = list(masses)
    masses[0] = 15
    with pytest.raises(sym.SymmetryError) as err:
        sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    assert err.value.code == "SYMMETRY_NOT_SATISFIED"


def test_a_reversed_non_proton_pair_is_refused() -> None:
    elements, masses, xyz = dcb14()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D2h", np.eye(3)))
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(v, [(7, 6)], K)  # H–Cl, the proton first
    assert err.value.code == "OBSERVATION_NOT_PROTON"


def test_operations_carry_no_roundoff_residue() -> None:
    """Added after the round 75 freeze (the snapping mutant survived the frozen zero test): every
    entry of every operation is an exact zero or a real coefficient (|x| ≥ 0.5)."""
    for group in sym.SUPPORTED_GROUPS:
        for g in sym.operations(group):
            entries = np.abs(g).ravel()
            assert np.all((entries == 0.0) | (entries >= 0.5 - 1e-12)), group


# ---- Round 76 gates (frozen before the fixes) -------------------------------------------------------


def _three_protons() -> sym.Validated:
    xyz = np.array([[0.0, 0, 0], [2.5, 0, 0], [0.4, 2.2, 0.3]])
    return sym.validate(xyz, ["H"] * 3, [None] * 3, sym.Declaration("C1", np.eye(3)))


@pytest.mark.parametrize("unit", ["ns", "D"])
def test_numpy_durations_are_not_indices(unit: str) -> None:
    v = _three_protons()
    bad = np.timedelta64(1, unit)
    for call in (lambda: v.pair_orbit(bad, 0), lambda: sym.fixed_rows(v, [(bad, 0)], K)):  # type: ignore[arg-type]
        with pytest.raises(sym.SymmetryError) as err:
            call()
        assert err.value.code == "OBSERVATION_INVALID_INDEX"
    assert sym.fixed_rows(v, [(np.uint8(0), np.int32(2))], K).keys == ((0, 2),)


@pytest.mark.parametrize("pair", [(1,), (0, 1, 2), 5])
def test_malformed_pairs_are_refused(pair: object) -> None:
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(_three_protons(), [pair], K)  # type: ignore[list-item]
    assert err.value.code == "OBSERVATION_INVALID_INDEX"


def test_the_fit_admission_limit_is_enforced_before_the_rows() -> None:
    """D-11: at most 20 000 rows; 20 001 is FIT_TOO_LARGE, refused before any allocation."""
    rng = np.random.default_rng(31)
    xyz = rng.uniform(-60.0, 60.0, size=(201, 3))
    v = sym.validate(xyz, ["H"] * 201, [None] * 201, sym.Declaration("C1", np.eye(3)))
    pairs = [(i, j) for i in range(201) for j in range(i + 1, 201)][:20_001]
    assert sym.MAX_FIT_ROWS == 20_000
    with pytest.raises(sym.SymmetryError) as err:
        sym.fixed_rows(v, pairs, K)
    assert err.value.code == "FIT_TOO_LARGE"
    assert sym.fixed_rows(v, pairs[:20_000], K).design_s5.shape == (20_000, 5)


def test_bad_coordinates_have_their_own_code() -> None:
    for xyz, n in ((np.zeros((3, 2)), 3), (np.zeros((2, 3)), 3), (np.full((3, 3), np.nan), 3)):
        with pytest.raises(sym.SymmetryError) as err:
            sym.validate(xyz, ["H"] * n, [None] * n, sym.Declaration("C1", np.eye(3)))
        assert err.value.code == "GEOMETRY_INVALID"


def test_mass_numbers_are_strict_integers() -> None:
    for mass in (True, 13.0, "13"):
        with pytest.raises(sym.SymmetryError) as err:
            sym.normalize_isotope("C", mass)  # type: ignore[arg-type]
        assert err.value.code == "ISOTOPE_NOT_SUPPORTED", mass
    assert sym.normalize_isotope("C", np.int64(13)) == ("C", 13)


def test_the_polar_factor_not_another_orthogonalization() -> None:
    """Axes R·(I + εS), S symmetric, within the tolerance: the polar factor is R itself; a QR or
    Gram–Schmidt factor differs at O(ε)."""
    r = _rotation(41)
    s = np.array([[1.0, 0.4, -0.2], [0.4, -0.7, 0.3], [-0.2, 0.3, 0.5]])
    axes = r @ (np.eye(3) + 2e-10 * s)
    elements, masses, xyz = benzene()
    xyz_in = xyz @ r  # the fixture in an input frame whose symmetry axes are the rows of r
    v = sym.validate(xyz_in, elements, masses, sym.Declaration("D6h", axes))
    assert np.max(np.abs(v.rotation - r)) < 1e-15


def test_the_returned_centroid_and_site_representatives() -> None:
    elements, masses, xyz = dcb14()
    xyz_in, q = _to_input(xyz, seed=17)
    v = sym.validate(xyz_in, elements, masses, sym.Declaration("D2h", q))
    assert np.allclose(v.centroid, xyz_in.mean(axis=0), atol=1e-12)
    assert list(v.site_orbit) == [0, 1, 1, 0, 1, 1, 6, 7, 7, 6, 7, 7]  # all four protons are equivalent


def test_a_second_candidate_exactly_on_the_cutoff_is_ambiguous() -> None:
    tol = 0.0625
    points = np.array([[0.0, 0.0, 0.0], [tol, 0.0, 0.0], [5.0, 0.0, 0.0]])
    with pytest.raises(sym.SymmetryError) as err:
        sym.match_operation(points, [("H", None)] * 3, points, tol)
    assert err.value.code == "SYMMETRY_AMBIGUOUS"


def test_the_refusal_prints_the_distance_exactly() -> None:
    tol = 0.0625
    d = float(np.nextafter(tol, 1.0))
    points = np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
    mapped = points + np.array([[d, 0.0, 0.0], [0.0, 0.0, 0.0]])
    with pytest.raises(sym.SymmetryError) as err:
        sym.match_operation(points, [("H", None)] * 2, mapped, tol)
    assert repr(d) in str(err.value) and repr(tol) in str(err.value)


def test_returned_arrays_cannot_change_later_results() -> None:
    elements, masses, xyz = benzene()
    v = sym.validate(xyz, elements, masses, sym.Declaration("D6h", np.eye(3)))
    rows = sym.fixed_rows(v, [(6, 7)], K)
    before = fixed.SUBSPACES["D6h"].copy()
    try:
        rows.subspace[:] = 0.0
    except ValueError:
        pass  # read-only is fine too
    assert np.array_equal(fixed.SUBSPACES["D6h"], before)
    for array in (v.averaged, v.permutations, v.site_orbit, v.rotation, v.centroid):
        with pytest.raises(ValueError):
            array[...] = 0  # the validated result is immutable
