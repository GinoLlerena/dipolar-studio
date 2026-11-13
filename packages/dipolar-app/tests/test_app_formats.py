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
from dipolar_app.science import problem_for, validate_project
from dipolar_core.biphenyl import BiphenylGeometry, proton_positions
from dipolar_core.fit import fit

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_CSV = (ROOT / "datasets" / "biphenyl-synthetic" / "couplings.csv").read_text(encoding="utf-8")
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
        ("spin_a,spin_b,D_obs_Hz,sigma_Hz,multiplicity\nH2,H3,1,0.5,0\n", "multiplicity must be an integer from 1"),
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
        (lambda d: d.update(schema_version=3), "reads up to 2"),
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
    current = dumps_project(EXAMPLE)
    monkeypatch.setattr(formats, "PROJECT_SCHEMA_VERSION", 3)
    with pytest.raises(FormatError, match="no migration from schema 2"):
        loads_project(current)


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
        validate_project(jump_c1)
    molecule = parse_xyz(biphenyl_xyz())
    imported = project_from_xyz(molecule, name="x", source="x", torsion=(1, 0, 6, 7))
    no_torsion = imported.model_copy(
        update={
            "molecule": imported.molecule.model_copy(
                update={"geometry": imported.molecule.geometry.model_copy(update={"torsion": None})}
            )
        }
    )
    validate_project(no_torsion)  # a draft without a torsion is a valid project…
    with pytest.raises(ValueError, match="needs a declared torsion"):
        problem_for(no_torsion)  # …that is not yet ready to fit
    on_carbon = imported.molecule.spins[0].model_copy(update={"atom": 0})
    bad_spin = imported.model_copy(
        update={"molecule": imported.molecule.model_copy(update={"spins": (on_carbon, *imported.molecule.spins[1:])})}
    )
    with pytest.raises(ValueError, match="must name a hydrogen"):
        validate_project(bad_spin)
    with pytest.raises(FormatError, match="not hydrogens"):
        project_from_xyz(molecule, name="x", source="x", torsion=(1, 0, 6, 7), spin_labels={0: "C1"})


# --------------------------------------------------------------------------- round 22 counterexamples
V1_JOURNAL = Path(__file__).parent / "data" / "schema-v1.events.jsonl"


def test_a_schema_v1_journal_still_replays(tmp_path: Path) -> None:
    """Round 22, finding 1. This journal was written by the pre-step-4 code (order
    "diagonal-bisector", no new fields). Its hash is checked against the payload as stored, then
    the project is migrated. A new command after it, and a second reopen, both work."""
    from dipolar_app.journal import Journal
    from dipolar_app.session import Session

    copy = tmp_path / "events.jsonl"
    copy.write_bytes(V1_JOURNAL.read_bytes())
    session = Session(Journal(copy), contract_version="0.1.0")
    project = session.state.project
    assert project is not None and project.schema_version == 2
    assert project.model.order == "bisector-diagonal" and project.next_coupling_id == 15
    assert Session(Journal(copy), contract_version="0.1.0").state.science_hash == session.state.science_hash


def test_a_tampered_v1_journal_is_still_refused(tmp_path: Path) -> None:
    from dipolar_app.journal import Journal, JournalCorrupt
    from dipolar_app.session import Session

    record = json.loads(V1_JOURNAL.read_text(encoding="utf-8").splitlines()[0])
    record["events"][0]["project"]["name"] = "tampered"
    del record["checksum"]
    copy = tmp_path / "events.jsonl"
    Journal(copy).append(record)
    with pytest.raises(JournalCorrupt, match="does not reproduce"):
        Session(Journal(copy), contract_version="0.1.0")


def test_a_v1_project_file_is_migrated() -> None:
    record = json.loads(V1_JOURNAL.read_text(encoding="utf-8").splitlines()[0])
    document = {"format": "dipolar-studio-project", "schema_version": 1, "project": record["events"][0]["project"]}
    project = loads_project(json.dumps(document))
    assert project.schema_version == 2 and project.model.order == "bisector-diagonal"


def test_deleted_coupling_ids_are_never_reused() -> None:
    """Round 22, finding 2: keep one coupling, then add a new pair; it must not get cpl_000002."""
    spin = {s.label: s.id for s in EXAMPLE.molecule.spins}
    keep = parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H2',1,1\n")
    reduced = apply_import(EXAMPLE, keep, {"H2": spin["H2"], "H2'": spin["H2'"]})
    assert [c.id for c in reduced.couplings] == ["cpl_000001"] and reduced.next_coupling_id == 15
    added = apply_import(
        reduced,
        parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz\nH3,H5,1,1\n"),
        {"H3": spin["H3"], "H5": spin["H5"]},
    )
    assert added.couplings[0].id == "cpl_000015" and added.next_coupling_id == 16


def test_labels_are_matched_and_kept_verbatim() -> None:
    """Round 22, finding 3: a quoted " H2" is not the label "H2", and is kept as written."""
    table = parse_couplings_csv('spin_a,spin_b,D_obs_Hz,sigma_Hz\n" H2",H3,1,1\n')
    assert table.rows[0].spin_a == " H2"
    assert reconcile(table, EXAMPLE).unmatched_labels == (" H2",)


def test_the_diff_covers_every_replaced_field() -> None:
    """Round 22, finding 4: a change of multiplicity or equivalent pairs alone is a change."""
    lines = SYNTHETIC_CSV.splitlines()
    edited = lines[1].replace(",H2-H2' H6-H6',2,", ",H2-H2' H6-H6',3,")
    assert edited != lines[1]
    text = "\n".join([lines[0], edited, *lines[2:]]) + "\n"
    diff = reconcile(parse_couplings_csv(text, default_sigma_source=EXAMPLE.couplings[0].sigma_source), EXAMPLE)
    assert len(diff.changed) == 1 and len(diff.unchanged) == 13


def test_a_duplicated_observation_is_refused() -> None:
    """Round 22, finding 5a: H5–H6 already belongs to the H2–H3 observation class."""
    spin = {s.label: s.id for s in EXAMPLE.molecule.spins}
    extra = EXAMPLE.couplings[0].model_copy(
        update={
            "id": "cpl_000015",
            "spin_a": spin["H5"],
            "spin_b": spin["H6"],
            "multiplicity": 1,
            "equivalent_pairs": (),
        }
    )
    with pytest.raises(ValueError, match="repeats an observation"):
        validate_project(EXAMPLE.model_copy(update={"couplings": (*EXAMPLE.couplings, extra), "next_coupling_id": 16}))


@pytest.mark.parametrize("order", ["c2z", "c1"])
def test_classes_must_be_equivalences_of_the_selected_model(order: str) -> None:
    """Round 22, finding 5b: the fixture's D2 classes are not equivalences of c2z or c1."""
    model = EXAMPLE.model.model_copy(update={"order": order})
    with pytest.raises(ValueError, match="not equivalent under the rigid/" + order):
        validate_project(EXAMPLE.model_copy(update={"model": model}))
    validate_project(EXAMPLE)  # they are equivalences of the bisector-diagonal model


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p["molecule"]["spins"][1].update(id="spn_000001"), "spin IDs must be unique"),
        (lambda p: p["couplings"][0]["sigma"].update(value=-0.5), "sigma must be positive"),
        (lambda p: p["model"].update(frame="input"), "'bisector' or 'ring-a' frame"),
        (lambda p: p.update(next_coupling_id=3), "next_coupling_id must exceed"),
    ],
)
def test_project_files_are_checked_for_consistency(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    """Round 22, finding 6: structure alone is not enough on load."""
    document = json.loads(dumps_project(EXAMPLE))
    mutate(document["project"])
    with pytest.raises(FormatError, match=message):
        loads_project(json.dumps(document))


@pytest.mark.parametrize("field", ['"0.5', '"0".5'])
def test_malformed_csv_quoting_is_refused(field: str) -> None:
    """Round 22, finding 8: never repair a malformed field into a number."""
    with pytest.raises(FormatError, match="malformed CSV"):
        parse_couplings_csv(f"spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,1,{field}\n")


def test_deeply_nested_json_is_refused_without_recursion() -> None:
    """Round 22, finding 9: 20,000 nested arrays once raised RecursionError."""
    with pytest.raises(FormatError, match="nested deeper"):
        loads_project("[" * 20_000 + "]" * 20_000)
    assert formats._json_depth_exceeds('{"a": "[[[[[["}', 3) is False  # brackets inside strings do not count


def test_import_contracts_bom_and_one_to_one_mappings() -> None:
    """Round 22 (B): a leading BOM is removed; a mapping must be one-to-one."""
    table = parse_couplings_csv("\ufeffspin_a,spin_b,D_obs_Hz,sigma_Hz\r\nH2,H3,1,1\r\n")
    assert table.rows[0].spin_a == "H2"
    spin = {s.label: s.id for s in EXAMPLE.molecule.spins}
    two = parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz\nA,H3,1,1\nB,H4,1,1\n")
    with pytest.raises(FormatError, match="one-to-one"):
        apply_import(EXAMPLE, two, {"A": spin["H2"], "B": spin["H2"], "H3": spin["H3"], "H4": spin["H4"]})


# --------------------------------------------------------------------------- round 24 counterexamples
def _journal_with(tmp_path: Path, mutate) -> Path:  # type: ignore[no-untyped-def]
    from dipolar_app.journal import Journal

    record = json.loads(V1_JOURNAL.read_text(encoding="utf-8").splitlines()[0])
    del record["checksum"]
    mutate(record)
    path = tmp_path / "events.jsonl"
    Journal(path).append(record)
    return path


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda r: r.update(project_schema=2), "does not match project_schema 2"),
        (lambda r: r.update(project_schema=3), "unsupported project_schema 3"),
        (lambda r: r.update(project_schema="1"), "unsupported project_schema '1'"),
        (lambda r: r.pop("project_schema"), "unsupported project_schema None"),
        (lambda r: r["events"][0]["project"].update(schema_version=2), "does not match project_schema 1"),
    ],
)
def test_journal_schema_metadata_cannot_choose_the_hash_rule(tmp_path: Path, mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    """Round 24, finding 1: the record's schema must be a supported integer that matches every
    payload in it. A v1 payload tagged 2 (or untagged) once replayed under the migrated hash."""
    from dipolar_app.journal import Journal, JournalCorrupt
    from dipolar_app.session import Session

    with pytest.raises(JournalCorrupt, match=message):
        Session(Journal(_journal_with(tmp_path, mutate)), contract_version="0.1.0")


def test_imported_classes_are_translated_through_the_confirmed_mapping() -> None:
    """Round 24, finding 2: a class written in the file's own labels is resolved through the
    mapping, stored in project labels, and kept verbatim as provenance."""
    table = parse_couplings_csv("spin_a,spin_b,D_obs_Hz,sigma_Hz,multiplicity,equivalent_pairs\nA,B,1,1,2,A-B C-D\n")
    unconfirmed = reconcile(table, EXAMPLE)
    assert unconfirmed.unresolved_pairs == ("C-D",)  # C and D are unknown until mapped
    spin = {s.label: s.id for s in EXAMPLE.molecule.spins}
    mapping = {"A": spin["H2"], "B": spin["H3"], "C": spin["H5"], "D": spin["H6"]}
    diff = reconcile(table, EXAMPLE, mapping)
    assert diff.unmatched_labels == () and diff.unresolved_pairs == ()
    project = apply_import(EXAMPLE, table, mapping)
    (c,) = project.couplings
    assert c.equivalent_pairs == ("H2-H3", "H5-H6") and c.source_equivalent_pairs == ("A-B", "C-D")
    validate_project(project)
    assert loads_project(dumps_project(project)) == project


def test_ambiguous_pair_labels_are_refused() -> None:
    """Round 24 (B): with labels a, b-c, a-b and c, "a-b-c" names two different pairs."""
    from dipolar_app.project import split_pair_label

    with pytest.raises(ValueError, match="ambiguous"):
        split_pair_label("a-b-c", {"a", "b-c", "a-b", "c"})
    assert split_pair_label("H2-H3'", {"H2", "H3'"}) == ("H2", "H3'")


@pytest.mark.parametrize(
    ("torsion", "message"),
    [((0, 0, 6, 7), "four distinct"), ((2, 0, 1, 3), "in a ring"), ((1, 0, 7, 8), "not bonded")],
)
def test_an_invalid_declared_torsion_is_refused_on_load(torsion: tuple[int, int, int, int], message: str) -> None:
    """Round 24, finding 3: a declared torsion is validated even with no equivalence classes."""
    project = project_from_xyz(parse_xyz(biphenyl_xyz()), name="x", source="x", torsion=(1, 0, 6, 7))
    document = json.loads(dumps_project(project))
    document["project"]["molecule"]["geometry"]["torsion"] = list(torsion)
    with pytest.raises(FormatError, match=message):
        loads_project(json.dumps(document))


def test_project_files_respect_the_atom_cap() -> None:
    """Round 24, finding 4: the cap is in the schema, so every load path enforces it."""
    project = project_from_xyz(parse_xyz(biphenyl_xyz()), name="x", source="x", torsion=(1, 0, 6, 7))
    document = json.loads(dumps_project(project))
    atoms = document["project"]["molecule"]["geometry"]["atoms"]
    document["project"]["molecule"]["geometry"]["atoms"] = (
        atoms + [{"element": "C", "x": 9.0, "y": 9.0, "z": 9.0}] * 980
    )
    with pytest.raises(ValueError, match="at most 1000"):
        loads_project(json.dumps(document))


def test_class_validation_builds_the_geometry_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Round 24, finding 4: the design function used by the class check builds the torsion
    geometry (and its quadratic bond graph) once, however many classes and probes it serves."""
    from dipolar_app import science
    from dipolar_core import torsion as core_torsion

    project = project_from_xyz(parse_xyz(biphenyl_xyz()), name="x", source="x", torsion=(1, 0, 6, 7))
    calls = []
    original = core_torsion.TorsionGeometry.from_atoms.__func__  # type: ignore[attr-defined]

    def counting(cls, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(1)
        return original(cls, *args, **kwargs)

    monkeypatch.setattr(core_torsion.TorsionGeometry, "from_atoms", classmethod(counting))
    design = science._design_function(project)
    for phi in (-150.0, -37.0, 0.0, 60.0):
        for _ in range(25):
            design(((0, 1), (2, 3)), phi)
    assert len(calls) == 1
