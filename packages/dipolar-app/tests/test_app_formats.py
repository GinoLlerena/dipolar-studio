"""M1 step 4: XYZ and couplings-CSV import, D5 reconciliation, and *.dipolar.json v1."""

from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest
from dipolar_app import formats
from dipolar_app.formats import (
    FormatError,
    apply_import,
    dumps_project,
    loads_project,
    parse_couplings_csv,
    parse_xyz,
    project_from_xyz,
    reconcile,
)
from dipolar_app.project import ModelSpec, load_example, science_hash
from dipolar_app.science import check_project, problem_for
from dipolar_core.biphenyl import BiphenylGeometry, proton_positions
from dipolar_core.fit import fit

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_CSV = (ROOT / "datasets" / "biphenyl-synthetic" / "couplings.csv").read_text()
EXAMPLE = load_example("biphenyl-synthetic")


def biphenyl_xyz(phi_deg: float = 37.0) -> str:
    g = BiphenylGeometry()
    half = math.radians(phi_deg) / 2
    lines = []
    for side in (-1.0, 1.0):
        in_plane = np.array([math.cos(half), -side * math.sin(half), 0.0])
        centre = side * (g.r_inter / 2 + g.r_cc) * np.array([0.0, 0.0, 1.0])
        to_c1 = -side * np.array([0.0, 0.0, 1.0])
        for k in range(6):
            a = math.radians(60.0 * k)
            lines.append(("C", centre + g.r_cc * (math.cos(a) * to_c1 + math.sin(a) * in_plane)))
    lines += [("H", p) for p in proton_positions(phi_deg)]
    body = "\n".join(f"{e} {p[0]:.12f} {p[1]:.12f} {p[2]:.12f}" for e, p in lines)
    return f"{len(lines)}\nbiphenyl, template geometry at phi = {phi_deg}\n{body}\n"


# --------------------------------------------------------------------------- XYZ
def test_parse_xyz() -> None:
    molecule = parse_xyz(biphenyl_xyz())
    assert molecule.elements == ("C",) * 12 + ("H",) * 10 and len(molecule.positions) == 22


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("x\ncomment\n", "atom count must be an integer"),
        ("2\ncomment\nH 0 0 0\n", "declares 2 atoms but has 1"),
        ("1\ncomment\nXx 0 0 0\n", "line 3: unsupported element"),
        ("1\ncomment\nH 0 0\n", "line 3: expected 'element x y z'"),
        ("1\ncomment\nH 0 nan 0\n", "line 3: coordinates must be finite"),
        ("1\ncomment\nH 0 a 0\n", "line 3: coordinates must be numbers"),
        ("0\ncomment\n", "between 1 and"),
    ],
)
def test_bad_xyz_is_refused_with_its_line(text: str, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        parse_xyz(text)


# --------------------------------------------------------------------------- couplings CSV
def test_parse_the_synthetic_couplings() -> None:
    table = parse_couplings_csv(SYNTHETIC_CSV)
    assert len(table.rows) == 14
    assert table.ignored_columns == ("r_A", "D_true_Hz")  # reported, never used
    first = table.rows[0]
    assert (first.spin_a, first.spin_b, first.value_hz, first.sigma_hz, first.multiplicity) == (
        "H2",
        "H2'",
        -1124.726,
        0.5,
        2,
    )
    assert first.equivalent_pairs == ("H2-H2'", "H6-H6'")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("spin_a,spin_b,D_obs_Hz\nH2,H3,1\n", "missing required column"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H2,1,0.5\n", "row 1: a spin cannot couple to itself"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,x,0.5\n", "row 1: D_obs_Hz must be a number"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,1,0\n", "row 1: sigma_Hz must be positive"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,1,inf\n", "row 1: sigma_Hz must be finite"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz,observable\nH2,H3,1,0.5,T\n", "observable D"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz,unit\nH2,H3,1,0.5,kHz\n", "must be in Hz"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz,multiplicity\nH2,H3,1,0.5,0\n", "multiplicity must be a positive"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,1\n", "number of fields"),
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz\n", "no coupling rows"),
        ("spin_a,spin_a,D_obs_Hz,sigma_Hz\nH2,H3,1,1\n", "duplicate column"),
    ],
)
def test_bad_csv_is_refused_with_its_row(text: str, message: str) -> None:
    with pytest.raises(FormatError, match=message):
        parse_couplings_csv(text)


# --------------------------------------------------------------------------- reconciliation (D5)
def test_reconciling_the_same_data_changes_nothing() -> None:
    table = parse_couplings_csv(SYNTHETIC_CSV, default_sigma_source=EXAMPLE.couplings[0].sigma_source)
    diff = reconcile(table, EXAMPLE)
    assert diff.unmatched_labels == () and len(diff.proposed_mapping) == 10
    assert (diff.added, diff.removed, diff.changed) == ((), (), ()) and len(diff.unchanged) == 14


def test_the_diff_shows_changes_removals_and_treats_reversed_pairs_as_the_same() -> None:
    lines = SYNTHETIC_CSV.splitlines()
    header, rows = lines[0], lines[1:]
    reversed_first = rows[0].replace("H2,H2',", "H2',H2,", 1)
    changed_second = rows[1].replace("-1966.69", "-1960.00")
    text = "\n".join([header, reversed_first, changed_second, *rows[2:-1]]) + "\n"  # last row dropped
    source = EXAMPLE.couplings[0].sigma_source
    diff = reconcile(parse_couplings_csv(text, default_sigma_source=source), EXAMPLE)
    assert len(diff.changed) == 1 and len(diff.removed) == 1 and diff.added == ()
    assert len(diff.unchanged) == 12  # the reversed pair is the same observation


def test_unmatched_labels_need_a_confirmed_mapping() -> None:
    text = "spin_a,spin_b,D_obs_Hz,sigma_Hz\northo-A,meta-A,-1966.69,0.5\n"
    table = parse_couplings_csv(text)
    diff = reconcile(table, EXAMPLE)
    assert diff.unmatched_labels == ("meta-A", "ortho-A") and diff.added == ()
    with pytest.raises(FormatError, match="no confirmed mapping"):
        apply_import(EXAMPLE, table, diff.proposed_mapping)
    spin = {s.label: s.id for s in EXAMPLE.molecule.spins}
    mapping = {"ortho-A": spin["H2"], "meta-A": spin["H3"]}
    project = apply_import(EXAMPLE, table, mapping)
    (c,) = project.couplings
    assert c.source_labels == ("ortho-A", "meta-A")  # the original labels are kept verbatim
    original = next(x for x in EXAMPLE.couplings if {x.spin_a, x.spin_b} == {spin["H2"], spin["H3"]})
    assert c.id == original.id  # an existing pair keeps its stable ID


def test_a_new_pair_gets_the_next_free_id_and_duplicates_are_refused() -> None:
    spin = {s.label: s.id for s in EXAMPLE.molecule.spins}
    table = parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH3,H5,10,1\n")  # not in the example
    project = apply_import(EXAMPLE, table, {"H3": spin["H3"], "H5": spin["H5"]})
    assert project.couplings[0].id == "cpl_000015"
    twice = parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,1,1\nH3,H2,1,1\n")
    with pytest.raises(FormatError, match="repeats row 1"):
        reconcile(twice, EXAMPLE)
    same_spin = parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz\nA,B,1,1\n")
    with pytest.raises(FormatError, match="map to the same spin"):
        apply_import(EXAMPLE, same_spin, {"A": spin["H2"], "B": spin["H2"]})
    with pytest.raises(FormatError, match="not a spin of the project"):
        apply_import(EXAMPLE, same_spin, {"A": spin["H2"], "B": "spn_999999"})


# --------------------------------------------------------------------------- *.dipolar.json v1
def test_project_files_round_trip_exactly() -> None:
    text = dumps_project(EXAMPLE)
    again = loads_project(text)
    assert again == EXAMPLE and science_hash(again) == science_hash(EXAMPLE)
    assert dumps_project(again) == text


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(format="other"), "not a project file"),
        (lambda d: d.update(schema_version=2), "reads up to 1"),
        (lambda d: d.update(schema_version=True), "positive integer"),
        (lambda d: d.update(extra=1), "unexpected top-level fields"),
        (lambda d: d["project"].update(colour="red"), "Extra inputs are not permitted"),
        (lambda d: d["project"]["couplings"][0]["value"].update(value="1.0"), "valid number"),
    ],
)
def test_bad_project_files_are_refused(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    document = json.loads(dumps_project(EXAMPLE))
    mutate(document)
    with pytest.raises((FormatError, ValueError), match=message):
        loads_project(json.dumps(document))


def test_non_finite_numbers_and_an_unreachable_old_schema_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(FormatError, match="non-finite"):
        loads_project(dumps_project(EXAMPLE).replace("-1124.726", "NaN", 1))
    version_1 = dumps_project(EXAMPLE)
    monkeypatch.setattr(formats, "PROJECT_SCHEMA_VERSION", 2)
    with pytest.raises(FormatError, match="no migration from schema 1"):
        loads_project(version_1)


# --------------------------------------------------------------------------- end to end
def test_the_template_project_fits_the_frozen_fixture() -> None:
    result = fit(problem_for(loads_project(dumps_project(EXAMPLE))))
    assert result.theta[0] == pytest.approx(36.98503, abs=1e-4) and result.estimand == "rigid effective phi"


def test_xyz_plus_csv_import_fits_on_imported_coordinates() -> None:
    """Import a biphenyl XYZ, label its protons, import couplings by label, confirm, fit."""
    molecule = parse_xyz(biphenyl_xyz(37.0))
    labels = dict(zip(range(12, 22), ("H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'"), strict=True))
    project = project_from_xyz(
        molecule,
        name="biphenyl (xyz)",
        source="test",
        torsion=(1, 0, 6, 7),
        domain_deg=(-90.0, 0.0),
        spin_labels=labels,
    )
    probe = problem_for(
        apply_import(project, parse_couplings_csv(_csv(np.zeros(45))), {s.label: s.id for s in project.molecule.spins})
    )
    truth = np.array([0.25, 0.03, 0.02, -0.01, 0.015])
    y = probe.design(np.array([-48.0])) @ truth
    table = parse_couplings_csv(_csv(y))
    diff = reconcile(table, project)
    assert diff.unmatched_labels == () and len(diff.added) == 45
    fitted = fit(problem_for(apply_import(project, table, diff.proposed_mapping)))
    assert fitted.validity.regular
    assert fitted.theta[0] == pytest.approx(-48.0, abs=1e-8)
    np.testing.assert_allclose(fitted.order, truth, rtol=0, atol=1e-8)


def _csv(values: np.ndarray) -> str:
    labels = ("H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'")
    pairs = combinations(range(10), 2)
    rows = [f"{labels[a]},{labels[b]},{float(v)!r},0.5" for (a, b), v in zip(pairs, values, strict=True)]
    return "spin_a,spin_b,D_obs_Hz,sigma_Hz\n" + "\n".join(rows) + "\n"


def test_inconsistent_projects_are_refused() -> None:
    jump_c1 = EXAMPLE.model_copy(update={"model": ModelSpec(kind="jump4", order="c1", phi_domain_deg=(0.0, 90.0))})
    with pytest.raises(ValueError, match="jump model uses the bisector-diagonal"):
        check_project(jump_c1)
    molecule = parse_xyz(biphenyl_xyz())
    imported = project_from_xyz(molecule, name="x", source="x", torsion=(1, 0, 6, 7))
    no_torsion = imported.model_copy(
        update={
            "molecule": imported.molecule.model_copy(
                update={"geometry": imported.molecule.geometry.model_copy(update={"torsion": None})}
            )
        }
    )
    with pytest.raises(ValueError, match="needs a declared torsion"):
        check_project(no_torsion)
    on_carbon = imported.molecule.spins[0].model_copy(update={"atom": 0})
    bad_spin = imported.model_copy(
        update={"molecule": imported.molecule.model_copy(update={"spins": (on_carbon, *imported.molecule.spins[1:])})}
    )
    with pytest.raises(ValueError, match="must name a hydrogen"):
        check_project(bad_spin)
    with pytest.raises(FormatError, match="not hydrogens"):
        project_from_xyz(molecule, name="x", source="x", torsion=(1, 0, 6, 7), spin_labels={0: "C1"})
