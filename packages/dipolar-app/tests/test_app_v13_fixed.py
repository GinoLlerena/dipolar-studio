"""V1.3, the application: fixed-geometry fits of imported molecules (docs/phase2/v1.0-design.md,
D-1, D-3, D-5, D-6 and D-10; the §3 V1.3 gates; the round-76 contract items).

These gate tests were frozen before the implementation. Their targets come from the raw input
geometry and a known tensor, through ``dipolar_core.forward.design_rows`` (V1.1/V1.2 verified the
core path; here the application must reach it unchanged).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import AGENT, USER, Server, client, new_session, run_fit
from dipolar_core.forward import design_rows
from dipolar_core.nuclides import dipolar_constant_hz_a3

DATA = Path(__file__).parent / "data"
PHASE1 = DATA / "phase1"
K = dipolar_constant_hz_a3("1H", "1H")
R_CC, R_CH = 1.3914, 1.0802  # Gauss & Stanton (2000) r_e, Å
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
#: C2v for benzene with the C2 axis along input x (through carbon 0): z_sym = x, x_sym = y, y_sym = z.
C2V_AXES = [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]]
DRAFT_REASON = "declare a torsion, or declare the molecule's symmetry and choose a fixed-geometry fit"


# --------------------------------------------------------------------------- fixtures
def ring(elements: list[str] | None = None, *, wobble: float = 0.0) -> tuple[list[str], np.ndarray]:
    """Benzene in its D6h frame (z normal, x through carbon 0): six C, then six H/D/Cl.
    ``wobble`` moves hydrogen 0 by that many Å along y (within a tolerance it stays symmetric)."""
    subst = elements or ["H"] * 6
    els, xyz = [], []
    for k in range(6):
        a = math.radians(60 * k)
        els.append("C")
        xyz.append((R_CC * math.cos(a), R_CC * math.sin(a), 0.0))
    for k, e in enumerate(subst):
        a = math.radians(60 * k)
        r = R_CC + (1.75 if e == "Cl" else R_CH)
        xyz.append((r * math.cos(a), r * math.sin(a), 0.0))
    out = np.array(xyz)
    out[6, 1] += wobble
    return els + subst, out


def xyz_text(elements: list[str], xyz: np.ndarray, comment: str = "fixture") -> str:
    lines = [str(len(elements)), comment]
    lines += [f"{e} {x!r} {y!r} {z!r}" for e, (x, y, z) in zip(elements, xyz.tolist(), strict=True)]
    return "\n".join(lines) + "\n"


def couplings(xyz: np.ndarray, pairs: list[tuple[int, int]], s5: list[float]) -> np.ndarray:
    return design_rows(xyz, pairs, K) @ np.array(s5)


def ok(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"], envelope
    result: dict[str, Any] = envelope["result"]
    return result


def refused(envelope: dict[str, Any], code: str) -> dict[str, Any]:
    assert not envelope["ok"], envelope
    assert envelope["error"]["code"] == code, envelope["error"]
    error: dict[str, Any] = envelope["error"]
    return error


def rev(c: Any) -> int:
    envelope = c.call("render.describe_view")
    ok(envelope)
    return int(envelope["revisions"]["science"])


def csv_of(rows: list[tuple[str, str, float]], sigma: float = 0.5, extra: dict[str, list[str]] | None = None) -> str:
    extra = extra or {}
    header = ["spin_a", "spin_b", "D_obs_Hz", "sigma_Hz", *extra]
    lines = [",".join(header)]
    for k, (a, b, d) in enumerate(rows):
        lines.append(",".join([a, b, repr(float(d)), repr(sigma), *(extra[name][k] for name in extra)]))
    return "\n".join(lines) + "\n"


def import_csv(c: Any, csv: str) -> dict[str, Any]:
    mapping = ok(c.call("couplings.reconcile", {"csv": csv}))["proposed_mapping"]
    return c.call("couplings.import", {"csv": csv, "confirmed_mapping": mapping, "expected_science_revision": rev(c)})


def symmetry(group: str, axes: list[list[float]] | None = None, **kw: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"point_group": group, "axes": axes or IDENTITY}
    out.update(kw)
    return out


def set_symmetry(c: Any, sym: dict[str, Any] | None) -> dict[str, Any]:
    return c.call("molecule.set_symmetry", {"symmetry": sym, "expected_science_revision": rev(c)})


FIXED = {"kind": "fixed", "order": "point-group", "frame": "symmetry"}
DRAFT = {
    "kind": "rigid",
    "order": "c1",
    "frame": "input",
    "phi_domain": [{"value": -180.0, "unit": "deg"}, {"value": 180.0, "unit": "deg"}],
}


def set_model(c: Any, model: dict[str, Any]) -> dict[str, Any]:
    return c.call("model.set", {**model, "expected_science_revision": rev(c)})


def keys(value: Any) -> set[str]:
    """Every key in a JSON value, at any depth."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()


#: Benzene's three pair orbits by their H labels (atoms 6–11 are labelled H7–H12).
ORTHO, META, PARA = ("H7", "H8"), ("H7", "H9"), ("H7", "H10")
S_ZZ = 0.1


def benzene_rows(xyz: np.ndarray) -> list[tuple[str, str, float]]:
    d = couplings(xyz, [(6, 7), (6, 8), (6, 9)], [S_ZZ, 0, 0, 0, 0])
    return [(*ORTHO, d[0]), (*META, d[1]), (*PARA, d[2])]


def benzene_draft(c: Any, elements: list[str] | None = None, *, wobble: float = 0.0) -> np.ndarray:
    els, xyz = ring(elements, wobble=wobble)
    ok(
        c.call(
            "project.import_xyz", {"xyz": xyz_text(els, xyz), "name": "benzene", "expected_science_revision": rev(c)}
        )
    )
    return xyz


def fixed_benzene(c: Any, *, rows_first: bool = True, wobble: float = 0.0) -> np.ndarray:
    """Benzene declared D6h with its three orbit rows, as a fixed-geometry fit."""
    xyz = benzene_draft(c, wobble=wobble)
    ok(set_symmetry(c, symmetry("D6h")))
    if rows_first:
        ok(import_csv(c, csv_of(benzene_rows(ring()[1]))))
        ok(set_model(c, FIXED))
    else:
        ok(set_model(c, FIXED))
        ok(import_csv(c, csv_of(benzene_rows(ring()[1]))))
    return xyz


def by_label(c: Any) -> dict[str, str]:
    return {s["label"]: s["id"] for s in ok(c.call("project.describe"))["spins"]}


def pairs_as_ids(entries: list[str], labels: dict[str, str]) -> set[frozenset[str]]:
    out = set()
    for e in entries:
        a, b = e.split("-")
        out.add(frozenset((labels[a], labels[b])))
    return out


def benzene_orbit(kind: str) -> set[frozenset[str]]:
    """The orbit of the ortho, meta or para pair as label pairs (hard-coded: H7..H12 in ring order)."""
    hs = [f"H{k}" for k in range(7, 13)]
    step = {"ortho": 1, "meta": 2, "para": 3}[kind]
    return {frozenset((hs[k], hs[(k + step) % 6])) for k in range(6)}


# --------------------------------------------------------------------------- D-1: Phase 1 directories
def tree(path: Path) -> dict[str, str]:
    return {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("fixture", ["journal-only", "snapshot-journal"])
@pytest.mark.parametrize("with_lock", [False, True])
def test_a_phase1_directory_is_refused_unchanged_by_the_python_api(
    tmp_path: Path, fixture: str, with_lock: bool
) -> None:
    from dipolar_app.api import Studio
    from dipolar_app.directory import DirectoryRefused

    project = tmp_path / fixture
    shutil.copytree(PHASE1 / fixture, project)
    if with_lock:
        (project / "serve.lock").write_bytes(b"")  # 0.1 leaves its (empty) lock file behind
    before = tree(project)
    with pytest.raises(DirectoryRefused) as caught:
        Studio.local(project)
    message = str(caught.value)
    assert "written by Dipolar Studio 0.1" in message
    assert "project.export" in message and "not changed" in message
    assert tree(project) == before  # byte for byte; no lock file is left behind


@pytest.mark.parametrize("fixture", ["journal-only", "snapshot-journal"])
def test_a_phase1_directory_is_refused_unchanged_by_serve(tmp_path: Path, fixture: str) -> None:
    project = tmp_path / fixture
    shutil.copytree(PHASE1 / fixture, project)
    before = tree(project)
    ready = tmp_path / "ready.json"
    done = subprocess.run(
        [sys.executable, "-m", "dipolar_app.cli", "serve", "--project-dir", str(project), "--ready-file", str(ready)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode != 0
    assert "written by Dipolar Studio 0.1" in done.stdout + done.stderr
    assert not ready.exists()
    assert tree(project) == before


def test_a_new_directory_still_opens_and_replays(tmp_path: Path) -> None:
    from dipolar_app.api import Studio

    with Studio.local(tmp_path / "p") as studio:
        studio.call("project.open_example", name="biphenyl-synthetic", expected_science_revision=0)
        first = studio.call("project.describe")
    with Studio.local(tmp_path / "p") as studio:
        assert studio.call("project.describe") == first


def test_v1_and_v2_export_files_load_to_one_v3_identity_by_both_paths() -> None:
    from dipolar_app.formats import loads_project
    from dipolar_app.project import PROJECT_SCHEMA_VERSION, science_hash

    assert PROJECT_SCHEMA_VERSION == 3
    v1 = (PHASE1 / "export-v1.dipolar.json").read_text(encoding="utf-8")
    v2 = (PHASE1 / "export-v2.dipolar.json").read_text(encoding="utf-8")
    a, b = loads_project(v1), loads_project(v2)
    assert a == b and a.schema_version == 3
    identity = science_hash(a)
    for text in (v1, v2):
        c = client(new_session())
        loaded = ok(c.call("project.load", {"text": text, "expected_science_revision": 0}))
        assert loaded["science_hash"] == identity
        assert ok(c.call("render.describe_view"))["science_hash"] == identity
        exported = ok(c.call("project.export"))["text"]
        assert json.loads(exported)["schema_version"] == 3
        assert science_hash(loads_project(exported)) == identity


def test_an_old_journal_is_refused_on_replay() -> None:
    """The bundled schema-1 journal was written under the 0.1 numerical context: it is never
    replayed (D-1, D-2: no V1 code reads a record written under another context)."""
    from dipolar_app.journal import Journal, JournalCorrupt
    from dipolar_app.session import replay

    with pytest.raises(JournalCorrupt, match="numerical context"):
        replay(Journal(DATA / "schema-v1.events.jsonl"))


# --------------------------------------------------------------------------- the numerical context
def test_the_numerical_context_names_the_v1_choices() -> None:
    from dipolar_core.context import numerical_context

    context = numerical_context()
    for key in ("fixed_fit", "rank_policy", "symmetry_check", "tensor_basis", "feasibility_certificate"):
        assert isinstance(context[key], str) and context[key], key


# --------------------------------------------------------------------------- D-3: model states
def test_an_imported_draft_says_how_to_become_fittable() -> None:
    c = client(new_session())
    benzene_draft(c)
    described = ok(c.call("project.describe"))
    assert described["ready_to_fit"] is False
    assert described["not_ready_reason"] == DRAFT_REASON
    assert described["model"]["phi_domain"] == [{"value": -180.0, "unit": "deg"}, {"value": 180.0, "unit": "deg"}]


def test_entering_fixed_canonicalizes_the_rows_losslessly() -> None:
    c = client(new_session())
    benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    ok(import_csv(c, csv_of(benzene_rows(ring()[1]))))
    before = ok(c.call("project.describe"))["couplings"]
    assert [x["multiplicity"] for x in before] == [1, 1, 1]
    out = ok(set_model(c, FIXED))
    assert out["model"] == FIXED and out["ready_to_fit"] is True
    described = ok(c.call("project.describe"))
    assert described["model"] == FIXED  # no phi_domain key at all
    after = described["couplings"]
    for old, new, kind in zip(before, after, ("ortho", "meta", "para"), strict=True):
        for key in ("id", "spin_a", "spin_b", "value", "sigma", "sigma_source", "source_labels"):
            assert new[key] == old[key], key
        members = {frozenset(e.split("-")) for e in new["equivalent_pairs"]}
        assert members == benzene_orbit(kind)
        assert new["multiplicity"] == len(benzene_orbit(kind))
    assert described["symmetry"]["point_group"] == "D6h"


def test_entering_fixed_is_refused_without_a_symmetry_or_with_a_torsion() -> None:
    c = client(new_session())
    benzene_draft(c)
    r = rev(c)
    error = refused(set_model(c, FIXED), "INVALID_ARGUMENT")
    assert "symmetry" in error["message"]
    from dipolar_app.science_ops import ETHANE_XYZ

    ok(
        c.call(
            "project.import_xyz",
            {"xyz": ETHANE_XYZ, "name": "e", "torsion": [2, 0, 1, 5], "expected_science_revision": rev(c)},
        )
    )
    refused(set_model(c, FIXED), "INVALID_ARGUMENT")
    ok(c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": rev(c)}))
    refused(set_model(c, FIXED), "OUT_OF_DOMAIN")
    assert rev(c) == r + 2  # the two imports only


def test_the_phi_domain_is_absent_for_fixed_and_required_otherwise() -> None:
    c = client(new_session())
    benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    error = refused(set_model(c, {**FIXED, "phi_domain": DRAFT["phi_domain"]}), "INVALID_ARGUMENT")
    assert error["offending_field"] == "phi_domain"
    error = refused(set_model(c, {k: v for k, v in DRAFT.items() if k != "phi_domain"}), "INVALID_ARGUMENT")
    assert error["offending_field"] == "phi_domain"
    refused(set_model(c, {**DRAFT, "kind": "fixed"}), "INVALID_ARGUMENT")  # fixed needs point-group/symmetry


def test_entering_fixed_refuses_two_rows_in_one_orbit_listing_them() -> None:
    c = client(new_session())
    xyz = benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    d = couplings(xyz, [(6, 7), (7, 8)], [S_ZZ, 0, 0, 0, 0])
    ok(import_csv(c, csv_of([("H7", "H8", d[0]), ("H8", "H9", d[1])])))
    r = rev(c)
    error = refused(set_model(c, FIXED), "OBSERVATIONS_CONFLICT")
    assert error["details"]["coupling_ids"] == ["cpl_000001", "cpl_000002"]
    assert rev(c) == r


def test_entering_fixed_refuses_a_class_that_is_neither_its_orbit_nor_one_pair() -> None:
    c = client(new_session())
    xyz = benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    d = couplings(xyz, [(6, 7)], [S_ZZ, 0, 0, 0, 0])[0]
    csv = csv_of([("H7", "H8", d)], extra={"equivalent_pairs": ["H7-H8 H10-H11"], "multiplicity": ["2"]})
    ok(import_csv(c, csv))  # valid in the draft: the two pairs have identical rows
    error = refused(set_model(c, FIXED), "OBSERVATIONS_CONFLICT")
    assert error["details"]["coupling_ids"] == ["cpl_000001"]


def test_leaving_fixed_keeps_valid_classes_and_refuses_the_others() -> None:
    c = client(new_session())
    fixed_benzene(c)
    out = ok(set_model(c, DRAFT))
    assert out["ready_to_fit"] is False and out["not_ready_reason"] == DRAFT_REASON
    assert [x["multiplicity"] for x in ok(c.call("project.describe"))["couplings"]] == [6, 6, 3]

    c = client(new_session())
    fixed_benzene(c, wobble=0.004)  # symmetric within the 0.01 Å tolerance, not exactly
    r = rev(c)
    error = refused(set_model(c, DRAFT), "OBSERVATIONS_CONFLICT")
    assert set(error["details"]["coupling_ids"]) <= {"cpl_000001", "cpl_000002", "cpl_000003"}
    assert error["details"]["coupling_ids"]
    assert rev(c) == r


def test_symmetry_edits_and_their_refusals() -> None:
    c = client(new_session())
    fixed_benzene(c)
    r = rev(c)
    refused(set_symmetry(c, None), "INVALID_ARGUMENT")  # cleared while fixed
    # D2h (C2 along x, y, z) is a subgroup: it splits the ortho and meta orbits.
    error = refused(set_symmetry(c, symmetry("D2h")), "OBSERVATIONS_CONFLICT")
    assert "cpl_000001" in error["details"]["coupling_ids"]
    refused(set_symmetry(c, symmetry("D6h", medium="chiral")), "MEDIUM_NOT_SUPPORTED")
    refused(set_symmetry(c, symmetry("C3v")), "POINT_GROUP_NOT_SUPPORTED")
    refused(set_symmetry(c, symmetry("D6h", tolerance={"value": 0.5, "unit": "Å"})), "OUT_OF_DOMAIN")
    assert rev(c) == r
    # The same D6h with a larger tolerance: the orbits do not change, so it is accepted.
    out = ok(set_symmetry(c, symmetry("D6h", tolerance={"value": 0.05, "unit": "Å"})))
    assert out["symmetry"]["tolerance"] == {"value": 0.05, "unit": "Å"}


def test_a_symmetry_the_geometry_lacks_is_refused() -> None:
    c = client(new_session())
    benzene_draft(c, wobble=0.2)
    error = refused(set_symmetry(c, symmetry("D6h")), "SYMMETRY_NOT_SATISFIED")
    assert error["details"]["core_code"] == "SYMMETRY_NOT_SATISFIED"
    ok(set_symmetry(c, symmetry("Cs")))  # the plane is still a mirror


def test_symmetry_and_torsion_exclude_each_other_in_v1() -> None:
    from dipolar_app.science_ops import ETHANE_XYZ

    c = client(new_session())
    ok(
        c.call(
            "project.import_xyz",
            {"xyz": ETHANE_XYZ, "name": "e", "torsion": [2, 0, 1, 5], "expected_science_revision": 0},
        )
    )
    refused(set_symmetry(c, symmetry("C1")), "INVALID_ARGUMENT")
    c = client(new_session())
    ok(c.call("project.import_xyz", {"xyz": ETHANE_XYZ, "name": "e", "expected_science_revision": 0}))
    ok(set_symmetry(c, symmetry("C1")))
    refused(
        c.call("molecule.set_torsion", {"torsion": [2, 0, 1, 5], "expected_science_revision": rev(c)}),
        "INVALID_ARGUMENT",
    )
    c = client(new_session())
    ok(c.call("project.open_example", {"name": "biphenyl-synthetic", "expected_science_revision": 0}))
    refused(set_symmetry(c, symmetry("C1")), "OUT_OF_DOMAIN")


def test_the_same_validation_on_dry_run_and_proposals() -> None:
    session = new_session()
    c, agent = client(session), client(session, AGENT)
    xyz = benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    d = couplings(xyz, [(6, 7), (7, 8)], [S_ZZ, 0, 0, 0, 0])
    ok(import_csv(c, csv_of([("H7", "H8", d[0]), ("H8", "H9", d[1])])))
    args = {**FIXED, "expected_science_revision": rev(c)}
    refused(c.call("model.set", args, dry_run=True), "OBSERVATIONS_CONFLICT")
    refused(
        agent.call("proposal.create", {"steps": [{"operation": "model.set", "args": args}]}), "OBSERVATIONS_CONFLICT"
    )
    ok(c.call("couplings.remove", {"coupling_ids": ["cpl_000002"], "expected_science_revision": rev(c)}))
    args = {**FIXED, "expected_science_revision": rev(c)}
    dry = ok(c.call("model.set", args, dry_run=True))
    created = ok(agent.call("proposal.create", {"steps": [{"operation": "model.set", "args": args}]}))
    accepted = ok(c.call("proposal.accept", {"proposal_id": created["proposal"]["id"]}))
    assert accepted["science_hash"] == dry["science_hash"]
    assert ok(c.call("project.describe"))["couplings"][0]["multiplicity"] == 6


def test_couplings_remove() -> None:
    c = client(new_session())
    fixed_benzene(c)
    r = rev(c)
    refused(
        c.call("couplings.remove", {"coupling_ids": ["cpl_000009"], "expected_science_revision": r}), "ID_NOT_FOUND"
    )
    out = ok(c.call("couplings.remove", {"coupling_ids": ["cpl_000003", "cpl_000001"], "expected_science_revision": r}))
    assert out["removed"] == 2 and out["n_couplings"] == 1
    assert [x["id"] for x in ok(c.call("project.describe"))["couplings"]] == ["cpl_000002"]
    ok(c.call("history.undo", {"expected_science_revision": r + 1}))
    assert len(ok(c.call("project.describe"))["couplings"]) == 3


def test_a_loaded_fixed_project_is_validated_with_the_same_codes() -> None:
    c = client(new_session())
    fixed_benzene(c)
    document = json.loads(ok(c.call("project.export"))["text"])
    assert document["schema_version"] == 3
    broken = json.loads(json.dumps(document))
    broken["project"]["couplings"][0]["equivalent_pairs"] = ["H7-H8"]
    broken["project"]["couplings"][0]["multiplicity"] = 1
    refused(
        c.call("project.load", {"text": json.dumps(broken), "expected_science_revision": rev(c)}),
        "OBSERVATIONS_CONFLICT",
    )
    moved = json.loads(json.dumps(document))
    moved["project"]["molecule"]["geometry"]["atoms"][6]["y"] += 0.2
    refused(
        c.call("project.load", {"text": json.dumps(moved), "expected_science_revision": rev(c)}),
        "SYMMETRY_NOT_SATISFIED",
    )
    ok(c.call("project.load", {"text": json.dumps(document), "expected_science_revision": rev(c)}))


# --------------------------------------------------------------------------- D-5: rows keyed by orbit
def test_another_orbit_member_updates_the_same_row() -> None:
    c = client(new_session())
    xyz = fixed_benzene(c, rows_first=False)
    d = couplings(xyz, [(8, 9)], [S_ZZ, 0, 0, 0, 0])[0] + 1.0  # H9–H10 is ortho too
    csv = csv_of(
        [
            ("H9", "H10", d),
            (*META, couplings(xyz, [(6, 8)], [S_ZZ, 0, 0, 0, 0])[0]),
            (*PARA, couplings(xyz, [(6, 9)], [S_ZZ, 0, 0, 0, 0])[0]),
        ]
    )
    diff = ok(c.call("couplings.reconcile", {"csv": csv}))
    assert (len(diff["added"]), len(diff["removed"]), len(diff["changed"]), len(diff["unchanged"])) == (0, 0, 1, 2)
    ok(import_csv(c, csv))
    rows = ok(c.call("project.describe"))["couplings"]
    assert [x["id"] for x in rows] == ["cpl_000001", "cpl_000002", "cpl_000003"]
    labels = by_label(c)
    assert {rows[0]["spin_a"], rows[0]["spin_b"]} == {labels["H9"], labels["H10"]}
    assert rows[0]["value"]["value"] == pytest.approx(d, abs=0)
    assert {frozenset(e.split("-")) for e in rows[0]["equivalent_pairs"]} == benzene_orbit("ortho")


def test_two_rows_in_one_orbit_are_refused_in_an_import() -> None:
    c = client(new_session())
    xyz = fixed_benzene(c, rows_first=False)
    d = couplings(xyz, [(6, 7), (7, 8)], [S_ZZ, 0, 0, 0, 0])
    csv = csv_of([("H7", "H8", d[0]), ("H8", "H9", d[1])])
    labels = by_label(c)
    for envelope in (
        c.call("couplings.reconcile", {"csv": csv}),
        c.call("couplings.import", {"csv": csv, "confirmed_mapping": labels, "expected_science_revision": rev(c)}),
    ):
        error = refused(envelope, "OBSERVATIONS_CONFLICT")
        assert "repeat measurements of one pair orbit are not accepted" in error["message"]


def test_omitted_and_explicit_orbit_fields() -> None:
    c = client(new_session())
    xyz = fixed_benzene(c, rows_first=False)
    d = couplings(xyz, [(6, 7)], [S_ZZ, 0, 0, 0, 0])[0]
    labels = by_label(c)

    def attempt(extra: dict[str, list[str]]) -> dict[str, Any]:
        return c.call(
            "couplings.import",
            {
                "csv": csv_of([("H7", "H8", d)], extra=extra),
                "confirmed_mapping": labels,
                "expected_science_revision": rev(c),
            },
        )

    ok(attempt({"multiplicity": [""]}))  # omitted: filled in from the orbit
    assert ok(c.call("project.describe"))["couplings"][0]["multiplicity"] == 6
    ok(attempt({"multiplicity": ["6"]}))
    error = refused(attempt({"multiplicity": ["1"]}), "OBSERVATIONS_CONFLICT")  # "1" is not "omitted"
    assert "6" in error["message"]
    orbit = " ".join(f"{a}-{b}" for a, b in sorted(tuple(sorted(p)) for p in benzene_orbit("ortho")))
    ok(attempt({"equivalent_pairs": [" ".join(reversed(orbit.split()))]}))  # any order: compared as sets
    error = refused(attempt({"equivalent_pairs": ["H7-H8 H8-H9"]}), "OBSERVATIONS_CONFLICT")
    assert "H10-H11" in error["message"] or "H11-H10" in error["message"]  # the difference is named


# --------------------------------------------------------------------------- D-6: isotopes
def test_the_xyz_import_uses_the_core_isotope_table() -> None:
    c = client(new_session())
    bh3 = ["B", "H", "H", "H"]
    xyz = np.array(
        [[0, 0, 0]] + [[1.19 * math.cos(a), 1.19 * math.sin(a), 0] for a in (0, 2 * math.pi / 3, 4 * math.pi / 3)]
    )
    ok(c.call("project.import_xyz", {"xyz": xyz_text(bh3, xyz), "name": "BH3", "expected_science_revision": 0}))
    ok(set_symmetry(c, symmetry("D3h")))
    si = xyz_text(["Si", "H"], np.array([[0, 0, 0], [0, 0, 1.48]]))
    ok(c.call("project.import_xyz", {"xyz": si, "name": "SiH", "expected_science_revision": rev(c)}))
    for bad in ("He", "X", "Xe"):
        refused(
            c.call(
                "project.import_xyz",
                {
                    "xyz": xyz_text([bad, "H"], np.array([[0, 0, 0], [0, 0, 1.0]])),
                    "name": "x",
                    "expected_science_revision": rev(c),
                },
            ),
            "INVALID_ARGUMENT",
        )


def test_set_isotope_on_every_path() -> None:
    session = new_session()
    c, agent = client(session), client(session, AGENT)
    benzene_draft(c)
    ok(set_symmetry(c, symmetry("D6h")))
    error = refused(
        c.call("molecule.set_isotope", {"atom": 0, "mass_number": 13, "expected_science_revision": rev(c)}),
        "SYMMETRY_NOT_SATISFIED",
    )
    assert error["details"]["core_code"] == "SYMMETRY_NOT_SATISFIED"
    ok(set_symmetry(c, symmetry("C2v", C2V_AXES)))
    args = {"atom": 0, "mass_number": 13, "expected_science_revision": rev(c)}
    ok(c.call("molecule.set_isotope", args, dry_run=True))
    created = ok(agent.call("proposal.create", {"steps": [{"operation": "molecule.set_isotope", "args": args}]}))
    ok(c.call("proposal.accept", {"proposal_id": created["proposal"]["id"]}))
    atoms = ok(c.call("project.describe"))["geometry"]["atoms"]
    assert atoms[0]["mass_number"] == 13 and "mass_number" not in atoms[1]
    out = ok(c.call("molecule.set_isotope", {"atom": 0, "mass_number": 12, "expected_science_revision": rev(c)}))
    assert out["mass_number"] is None  # the default spelled out is normalized to absent
    assert "mass_number" not in ok(c.call("project.describe"))["geometry"]["atoms"][0]
    ok(
        c.call("molecule.set_isotope", {"atom": 0, "mass_number": 13.0, "expected_science_revision": rev(c)})
    )  # JSON integer
    r = rev(c)
    refused(
        c.call("molecule.set_isotope", {"atom": 6, "mass_number": 2, "expected_science_revision": r}),
        "INVALID_ARGUMENT",
    )
    refused(
        c.call("molecule.set_isotope", {"atom": 1, "mass_number": 14, "expected_science_revision": r}),
        "ISOTOPE_NOT_SUPPORTED",
    )
    refused(
        c.call("molecule.set_isotope", {"atom": 1, "mass_number": 13.5, "expected_science_revision": r}),
        "INVALID_ARGUMENT",
    )
    refused(
        c.call("molecule.set_isotope", {"atom": 1, "mass_number": True, "expected_science_revision": r}),
        "INVALID_ARGUMENT",
    )
    refused(
        c.call("molecule.set_isotope", {"atom": 99, "mass_number": 13, "expected_science_revision": r}), "ID_NOT_FOUND"
    )
    refused(
        c.call("molecule.set_isotope", {"atom": 1, "mass_number": 14, "expected_science_revision": r}, dry_run=True),
        "ISOTOPE_NOT_SUPPORTED",
    )
    assert rev(c) == r


def test_isotopes_on_load() -> None:
    c = client(new_session())
    benzene_draft(c)
    document = json.loads(ok(c.call("project.export"))["text"])
    for mutate, code in (
        (lambda atoms: atoms[0].update(mass_number=12), "INVALID_ARGUMENT"),  # not the one spelling
        (lambda atoms: atoms[6].update(mass_number=2), "INVALID_ARGUMENT"),  # H-2 is spelled D
        (lambda atoms: atoms[0].update(mass_number=14), "ISOTOPE_NOT_SUPPORTED"),
        (lambda atoms: atoms[0].update(element="He"), "INVALID_ARGUMENT"),
    ):
        copy = json.loads(json.dumps(document))
        mutate(copy["project"]["molecule"]["geometry"]["atoms"])
        refused(c.call("project.load", {"text": json.dumps(copy), "expected_science_revision": rev(c)}), code)
    copy = json.loads(json.dumps(document))
    copy["project"]["molecule"]["geometry"]["atoms"][0]["mass_number"] = 13
    ok(c.call("project.load", {"text": json.dumps(copy), "expected_science_revision": rev(c)}))


def test_benzene_d1_is_refused_as_d6h_and_accepted_as_c2v() -> None:
    c = client(new_session())
    benzene_draft(c, ["D", "H", "H", "H", "H", "H"])
    assert len(ok(c.call("project.describe"))["spins"]) == 5  # D is an atom, not a ¹H spin
    refused(set_symmetry(c, symmetry("D6h")), "SYMMETRY_NOT_SATISFIED")
    ok(set_symmetry(c, symmetry("C2v", C2V_AXES)))


# --------------------------------------------------------------------------- D-10: the result and contract
def test_a_fixed_run_recovers_benzene_and_has_no_phi() -> None:
    c = client(new_session())
    fixed_benzene(c)
    fit = ok(run_fit(c))
    assert fit["model"] == FIXED
    assert not {k for k in keys(fit) if "phi" in k or "theta" in k or "torsion" in k}
    assert fit["rank"]["required"] == 1 and fit["rank"]["verified"] is True
    by_name = {x["name"]: x for x in fit["components"]}
    assert by_name["Szz"]["status"] == "estimated"
    assert by_name["Szz"]["estimate"] == pytest.approx(S_ZZ, rel=1e-12, abs=0)
    assert by_name["Szz"]["interval_support"] == "supported"
    assert {x["level"] for x in by_name["Szz"]["intervals"]} == {"68.3", "95"}
    for name in ("Sxx-Syy", "Sxy", "Sxz", "Syz"):
        assert by_name[name]["status"] == "fixed-by-symmetry" and by_name[name]["estimate"] == 0.0
    assert fit["adequacy"]["nu"] == 2 and fit["n_obs"] == 3  # N counts rows, never multiplicity
    assert fit["adequacy"]["status"] == "given"
    assert fit["admissibility"]["status"] == "admissible"
    assert fit["symmetry"]["point_group"] == "D6h" and fit["symmetry"]["max_displacement"]["unit"] == "Å"
    assert [r["coupling_id"] for r in fit["rows"]] == ["cpl_000001", "cpl_000002", "cpl_000003"]
    for row in fit["rows"]:
        assert row["residual"]["value"] == pytest.approx(0.0, abs=1e-9)
    assert fit["provenance"]["fit_version"] == "fixed-linear.1"
    assert fit["provenance"]["numerical_context"]["fixed_fit"] == "fixed-linear.1"
    assert fit["assumptions"] and fit["estimand"]


def test_a_d2h_fixture_recovers_two_free_coordinates() -> None:
    c = client(new_session())
    els, xyz = ring(["Cl", "H", "H", "Cl", "H", "H"])  # 1,4-dichlorobenzene, Cl along x
    ok(c.call("project.import_xyz", {"xyz": xyz_text(els, xyz), "name": "pdcb", "expected_science_revision": 0}))
    ok(set_symmetry(c, symmetry("D2h")))
    ok(set_model(c, FIXED))
    # H on carbons 1, 2, 4, 5 are atoms 7, 8, 10, 11 (labels H8, H9, H11, H12).
    truth = [0.08, 0.03, 0, 0, 0]
    pairs = [(7, 8), (7, 11), (7, 10)]  # ortho (C1–C2), across C0 (C1–C5), para (C1–C4)
    d = couplings(xyz, pairs, truth)
    labels = {7: "H8", 8: "H9", 10: "H11", 11: "H12"}
    ok(import_csv(c, csv_of([(labels[a], labels[b], v) for (a, b), v in zip(pairs, d, strict=True)])))
    fit = ok(run_fit(c))
    by_name = {x["name"]: x for x in fit["components"]}
    assert by_name["Szz"]["estimate"] == pytest.approx(0.08, rel=1e-10, abs=0)
    assert by_name["Sxx-Syy"]["estimate"] == pytest.approx(0.03, rel=1e-10, abs=0)
    assert fit["rank"]["required"] == 2 and fit["adequacy"]["nu"] == 1
    assert [r["multiplicity"] for r in fit["rows"]] == [2, 2, 2]


def test_preview_and_landscape_refuse_a_fixed_model() -> None:
    c = client(new_session())
    fixed_benzene(c)
    refused(c.call("fit.preview", {"phi": {"value": 0.0, "unit": "deg"}}), "NO_TORSION")
    refused(c.call("fit.landscape", {}), "NO_TORSION")


def test_the_fixed_report_states_the_estimable_combinations_without_phi() -> None:
    from dipolar_app.report import CSV_COLUMNS

    c = client(new_session())
    fixed_benzene(c)
    ok(run_fit(c))
    report = ok(c.call("run.report", {"run_id": "run_000001"}))
    page = report["html"]
    assert "torsion" not in page.lower() and "φ" not in page
    assert "estimable" in page.lower() and "fixed by symmetry" in page.lower()
    for words in ("fixed geometry", "Gaussian", "stated σ"):
        assert words in page
    lines = report["csv"].splitlines()
    assert tuple(lines[0].split(",")) == CSV_COLUMNS and len(lines) == 4
    assert report["format"] != "dipolar-report.1"


def test_the_scene_and_view_of_a_fixed_run() -> None:
    c = client(new_session())
    fixed_benzene(c)
    ok(run_fit(c))
    scene = ok(c.call("render.scene"))
    assert scene["fit"] is not None and scene["fit"]["regular"] is True
    assert all(x["residual"] is not None for x in scene["couplings"])
    view = ok(c.call("render.describe_view"))
    assert not any("torsion" in w for w in view["warnings"])


def test_the_contract_moves_to_0_11_0_as_breaking() -> None:
    from dipolar_app.operations import build_registry
    from dipolar_app.registry import CONTRACT_VERSION

    assert CONTRACT_VERSION == "0.11.0"
    snapshot = build_registry().snapshot()
    entry = next(x for x in snapshot["changelog"] if x["version"] == "0.11.0")
    assert entry["breaking"] is True
    text = " ".join(entry["changes"])
    assert "run.get" in text and "project.describe" in text
    for name in ("molecule.set_symmetry", "molecule.set_isotope", "couplings.remove"):
        op = next(o for o in snapshot["operations"] if o["name"] == name)
        assert op["proposable"] is True and op["revision_check"].startswith("expected_science_revision")
    committed = json.loads((Path(__file__).parents[1] / "registry.snapshot.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(snapshot))


def _validate(instance: Any, schema: dict[str, Any]) -> None:
    import jsonschema

    jsonschema.Draft202012Validator(schema).validate(instance)


def test_non_fixed_responses_keep_the_0_10_0_contract() -> None:
    """Old clients keep working on projects without a fixed model: every response of the biphenyl
    and imported-torsion paths validates against the 0.10.0 snapshot's output schemas (from which
    the 0.10.0 TypeScript types were generated), which forbid extra fields."""
    old = json.loads((DATA / "contract-0.10.0.json").read_text(encoding="utf-8"))
    assert old["contract_version"] == "0.10.0"
    schemas = {o["name"]: o["output_schema"] for o in old["operations"]}
    from dipolar_app.science_ops import ETHANE_XYZ

    c = client(new_session())
    steps: list[tuple[str, Any]] = [
        ("project.open_example", lambda: {"name": "biphenyl-synthetic", "expected_science_revision": rev(c)}),
        ("project.describe", lambda: {}),
        ("fit.preview", lambda: {"phi": {"value": 37.0, "unit": "deg"}}),
        ("fit.landscape", lambda: {"points": 7}),
        ("fit.run", lambda: {"expected_science_revision": rev(c)}),
        ("job.wait", lambda: {"job_id": "job_000001", "timeout_s": 30}),
        ("run.get", lambda: {"run_id": "run_000001"}),
        ("run.report", lambda: {"run_id": "run_000001"}),
        ("render.scene", lambda: {}),
        ("render.describe_view", lambda: {}),
        (
            "model.set",
            lambda: {
                "kind": "jump4",
                "order": "bisector-diagonal",
                "frame": "bisector",
                "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
                "expected_science_revision": rev(c),
            },
        ),
        (
            "project.import_xyz",
            lambda: {"xyz": ETHANE_XYZ, "name": "e", "torsion": [2, 0, 1, 5], "expected_science_revision": rev(c)},
        ),
        ("project.describe", lambda: {}),
        ("project.export", lambda: {}),
        ("render.scene", lambda: {}),
    ]
    for name, make in steps:
        _validate(ok(c.call(name, make())), schemas[name])


def test_new_operations_have_python_http_parity(server: Server) -> None:
    py = client(new_session(), USER)
    els, xyz = ring()
    rows = benzene_rows(xyz)
    labels = {f"H{k}": f"spn_{k - 6:06d}" for k in range(7, 13)}
    csv = csv_of(rows)
    sequence: list[tuple[str, dict[str, Any]]] = [
        ("project.import_xyz", {"xyz": xyz_text(els, xyz), "name": "benzene", "expected_science_revision": 0}),
        ("molecule.set_symmetry", {"symmetry": symmetry("D6h"), "expected_science_revision": 1}),
        ("molecule.set_isotope", {"atom": 0, "mass_number": 13, "expected_science_revision": 2}),  # refused
        ("model.set", {**FIXED, "expected_science_revision": 2}),
        ("couplings.import", {"csv": csv, "confirmed_mapping": labels, "expected_science_revision": 3}),
        ("couplings.remove", {"coupling_ids": ["cpl_000003"], "expected_science_revision": 4}),
        ("project.describe", {}),
        ("fit.preview", {"phi": {"value": 0.0, "unit": "deg"}}),  # refused: NO_TORSION
    ]
    for name, args in sequence:
        assert server.call(name, args, token="user") == py.call(name, args), name


# --------------------------------------------------------------------------- the round-76 contract items
def test_every_core_symmetry_code_has_an_explicit_envelope() -> None:
    import dipolar_core.symmetry as core
    from dipolar_app.errors import ErrorCode
    from dipolar_app.science import CORE_ERROR_CODES

    source = Path(core.__file__).read_text(encoding="utf-8")
    codes = set(re.findall(r'SymmetryError\(\s*"([A-Z_]+)"', source))
    assert codes and set(CORE_ERROR_CODES) == codes
    assert all(isinstance(v, ErrorCode) for v in CORE_ERROR_CODES.values())


def test_the_orbit_key_is_the_smallest_sorted_pair_of_spin_ids() -> None:
    """D-5: the key comes from spin IDs, not atom indices. Spin IDs here run against the atom order,
    so the two keys differ."""
    from dipolar_app.formats import loads_project
    from dipolar_app.science import orbit_key

    c = client(new_session())
    fixed_benzene(c)
    document = json.loads(ok(c.call("project.export"))["text"])
    spins = document["project"]["molecule"]["spins"]
    for s, n in zip(spins, range(6, 0, -1), strict=True):  # H7 -> spn_000006, ..., H12 -> spn_000001
        s["id"] = f"spn_{n:06d}"
    document["project"]["couplings"] = []
    project = loads_project(json.dumps(document))
    ids = {s.label: s.id for s in project.molecule.spins}
    assert orbit_key(project, ids["H7"], ids["H8"]) == ("spn_000001", "spn_000002")  # the H11–H12 / H12–H7 pairs
    assert orbit_key(project, ids["H7"], ids["H10"]) == ("spn_000001", "spn_000004")


def test_fit_too_large_is_refused_on_every_path(tmp_path: Path) -> None:
    from dipolar_app.errors import OperationError
    from dipolar_app.jobs import compute
    from dipolar_core.symmetry import MAX_FIT_ROWS

    text = big_c1_document(MAX_FIT_ROWS + 1)
    session = new_session()
    c, agent = client(session), client(session, AGENT)
    ok(c.call("project.load", {"text": text, "expected_science_revision": 0}))
    args = {"expected_science_revision": 1}
    refused(c.call("fit.run", args), "FIT_TOO_LARGE")
    refused(c.call("fit.run", args, dry_run=True), "FIT_TOO_LARGE")
    refused(agent.call("proposal.create", {"steps": [{"operation": "fit.run", "args": args}]}), "FIT_TOO_LARGE")
    project = session.state.project
    assert project is not None
    with pytest.raises(OperationError) as caught:
        compute("fit", project.model_dump_json(), {}, 1, session.state.science_hash)
    assert caught.value.code.value == "FIT_TOO_LARGE"


@pytest.mark.slow
def test_the_admission_limit_through_the_process_worker(tmp_path: Path) -> None:
    """D-11: 20 000 rows are admitted, and their result stays under the worker's 16 MiB cap, with
    long non-ASCII spin labels (the worst case for the outcome file)."""
    from dipolar_app.jobs import MAX_OUTCOME_BYTES, JobRunner
    from dipolar_app.registry import CONTRACT_VERSION
    from dipolar_app.session import Session
    from dipolar_core.symmetry import MAX_FIT_ROWS

    text = big_c1_document(MAX_FIT_ROWS, long_labels=True)

    session = Session(None, contract_version=CONTRACT_VERSION)
    runner = JobRunner(session, mode="process")
    try:
        c = client(session)
        ok(c.call("project.load", {"text": text, "expected_science_revision": 0}))
        job = ok(c.call("fit.run", {"expected_science_revision": 1}))["job"]
        while not ok(c.call("job.wait", {"job_id": job["id"], "timeout_s": 30}))["finished"]:
            pass
        done = ok(c.call("job.status", {"job_id": job["id"]}))["job"]
        assert done["status"] == "succeeded", done
        result = ok(c.call("run.get", {"run_id": done["run_id"]}))["result"]
        assert result["n_obs"] == MAX_FIT_ROWS
        size = len(json.dumps(result).encode())
        assert size < MAX_OUTCOME_BYTES // 2, size
    finally:
        runner.close()


def big_c1_document(n_rows: int, *, long_labels: bool = False) -> str:
    """A fixed C1 project with ``n_rows`` distinct ¹H–¹H pairs (201 protons on a 1 Å grid)."""
    from dipolar_app.formats import dumps_project
    from dipolar_app.project import Atom, Coupling, ImportedGeometry, ModelSpec, Molecule, Project, Spin, SymmetrySpec
    from dipolar_app.schemas import Angstrom, Hertz

    points = [(float(x), float(y), float(z)) for x in range(6) for y in range(6) for z in range(6)][:201]
    atoms = tuple(Atom(element="H", x=x, y=y, z=z) for x, y, z in points)
    label = (lambda k: ("\U0001d4d7" * 60) + f"{k:03d}") if long_labels else (lambda k: f"H{k + 1}")
    spins = tuple(Spin(id=f"spn_{k + 1:06d}", label=label(k), isotope="1H", atom=k) for k in range(201))
    pairs = [(a, b) for a in range(201) for b in range(a + 1, 201)][:n_rows]
    rng = np.random.default_rng(7)
    rows = tuple(
        Coupling(
            id=f"cpl_{k + 1:06d}",
            spin_a=spins[a].id,
            spin_b=spins[b].id,
            observable="D",
            value=Hertz(value=float(rng.normal(-100.0, 50.0)), unit="Hz"),
            sigma=Hertz(value=1.0, unit="Hz"),
            sigma_source="synthetic",
            multiplicity=1,
            equivalent_pairs=(f"{spins[a].label}-{spins[b].label}",),
        )
        for k, (a, b) in enumerate(pairs)
    )
    project = Project(
        schema_version=3,
        name="grid",
        source="synthetic",
        molecule=Molecule(
            geometry=ImportedGeometry(source_format="xyz", atoms=atoms),
            spins=spins,
            symmetry=SymmetrySpec(
                point_group="C1",
                axes=tuple(tuple(r) for r in IDENTITY),
                tolerance=Angstrom(value=0.01, unit="Å"),
                medium="achiral-uniaxial",
            ),
        ),
        couplings=rows,
        model=ModelSpec(kind="fixed", order="point-group", frame="symmetry"),
        next_coupling_id=len(rows) + 1,
    )
    return dumps_project(project)


# --------------------------------------------------------------------------- journal replay
def test_a_fixed_project_replays_and_compacts(tmp_path: Path) -> None:
    from dipolar_app.api import Studio

    project = tmp_path / "p"
    with Studio.local(project) as studio:
        c = _StudioClient(studio)
        fixed_benzene(c)
        result = studio.fit()
        described = studio.call("project.describe")
    with Studio.local(project) as studio:
        assert studio.call("project.describe") == described
        assert studio.call("run.get", run_id="run_000001")["result"] == result
        studio._transport._session.compact()  # type: ignore[attr-defined]
    with Studio.local(project) as studio:
        assert studio.call("project.describe") == described
        assert studio.call("run.get", run_id="run_000001")["result"] == result


class _StudioClient:
    """A ``LocalClient``-shaped wrapper over ``Studio`` (envelopes, dry_run unsupported)."""

    def __init__(self, studio: Any) -> None:
        self._studio = studio

    def call(self, name: str, args: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        envelope: dict[str, Any] = self._studio.envelope(name, args or {})
        return envelope
