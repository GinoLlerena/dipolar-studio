"""The run's summary report (run.report, beta step B2): the same run gives the same bytes; it says
what the run says, nothing from the current project; user strings are escaped in the HTML and
cannot run as spreadsheet formulas in the CSV."""

from __future__ import annotations

import csv
import html
import io
import json
import re
from pathlib import Path
from typing import Any

import dipolar_app
import pytest
from conftest import ROOT
from dipolar_app.api import OperationFailed, Studio
from dipolar_app.report import CSV_COLUMNS, REPORT_FORMAT

OPEN = {"name": "biphenyl-synthetic", "expected_science_revision": 0}
DATA = ROOT / "datasets" / "biphenyl-synthetic"
TUTORIAL_LABELS = ["H2", "H3", "H4", "H5", "H6", "H2'", "H3'", "H4'", "H5'", "H6'"]
DOMAIN = [{"value": -90, "unit": "deg"}, {"value": 0, "unit": "deg"}]


def fitted(studio: Studio) -> tuple[str, dict[str, Any]]:
    run = studio.fit(intervals=True)
    run_id = studio.call("render.describe_view")["run"]["run_id"]
    return run_id, run


def test_the_same_run_gives_the_same_report_even_after_reopening(tmp_path: Path) -> None:
    project = tmp_path / "project"
    with Studio.local(project) as studio:
        studio.call("project.open_example", OPEN)
        run_id, _ = fitted(studio)
        first = studio.call("run.report", run_id=run_id)
        assert studio.call("run.report", run_id=run_id) == first
        # The report describes the run, not the current project: an edit makes the run stale, and
        # the report is unchanged.
        jump = {"kind": "jump4", "order": "bisector-diagonal", "frame": "bisector"}
        studio.call(
            "model.set",
            **jump,
            phi_domain=[{"value": 0, "unit": "deg"}, {"value": 90, "unit": "deg"}],
            expected_science_revision=1,
        )
        assert studio.call("run.get", run_id=run_id)["run"]["stale"] is True
        later = studio.call("run.report", run_id=run_id)
        assert (later["html"], later["csv"]) == (first["html"], first["csv"])
    with Studio.local(project) as reopened:  # replayed from the journal and the stored result
        again = reopened.call("run.report", run_id=run_id)
        assert (again["html"], again["csv"]) == (first["html"], first["csv"])
    assert first["format"] == REPORT_FORMAT and first["filename"] == f"dipolar-report-{run_id}"


def test_the_report_says_what_the_run_says() -> None:
    with Studio.local() as studio:
        studio.call("project.open_example", OPEN)
        run_id, run = fitted(studio)
        report = studio.call("run.report", run_id=run_id)
        stored = studio.call("run.get", run_id=run_id)["run"]
    page = report["html"]
    assert page.startswith("<!doctype html>") and "<script" not in page.lower()
    assert not re.search(r"""(?:src|href)\s*=\s*["']?(?:https?:|//)""", page)  # self-contained
    for text in (
        run_id,
        stored["job_id"],
        stored["input_hash"],
        stored["science_hash"],
        stored["result_sha256"],
        run["fit_version"],
        run["estimand"],
        REPORT_FORMAT,
        html.escape(run["statement"], quote=True),
    ):
        assert text in page, text
    assert f"dipolar {dipolar_app.__version__} (dipolar-core {dipolar_app.__version__}, contract" in page
    phi = {t["name"]: t["value"] for t in run["theta"]}["phi_deg"]
    assert format(phi, ".6g").replace("-", "−") in page
    for c in run["couplings"]:
        assert html.escape(c["label"], quote=True) in page
    # The CSV: every coupling, at full precision, exactly the stored values.
    rows = list(csv.DictReader(io.StringIO(report["csv"])))
    assert tuple(rows[0]) == CSV_COLUMNS and len(rows) == len(run["couplings"])
    for row, c in zip(rows, run["couplings"], strict=True):
        assert row["coupling_id"] == c["id"] and row["label"] == c["label"]
        assert float(row["calculated_Hz"]) == c["calculated"]["value"]
        assert float(row["residual_Hz"]) == c["residual"]["value"]
        assert float(row["normalized_residual"]) == c["normalized_residual"]
        assert float(row["observed_Hz"]) == c["observed"]["value"] and float(row["sigma_Hz"]) == c["sigma"]["value"]


def test_user_strings_are_escaped_and_cannot_run_as_formulas() -> None:
    """Spin labels are the user's (an imported project can name them anything): a label with markup
    is shown as text, and one that starts with "=" cannot run as a spreadsheet formula."""
    xyz = (DATA / "biphenyl.xyz").read_text(encoding="utf-8")
    couplings = (DATA / "tutorial-couplings.csv").read_text(encoding="utf-8")
    names = xyz.split("\n")[1].split("atoms:")[1].split()
    with Studio.local() as studio:
        studio.call("project.import_xyz", xyz=xyz, name="hostile", expected_science_revision=0)
        spins = {s["atom"]: s["id"] for s in studio.call("project.describe")["spins"]}
        mapping = {label: spins[names.index(label)] for label in TUTORIAL_LABELS}
        studio.call("couplings.import", csv=couplings, confirmed_mapping=mapping, expected_science_revision=1)
        exported = json.loads(studio.call("project.export")["text"])
        labels = exported["project"]["molecule"]["spins"]
        labels[0]["label"], labels[1]["label"] = "<img src=x onerror=alert(1)>", "=HYPERLINK(1)"
        studio.call("project.load", text=json.dumps(exported), expected_science_revision=studio.science_revision)
        studio.call("molecule.set_torsion", torsion=[1, 0, 6, 7], expected_science_revision=studio.science_revision)
        studio.call(
            "model.set",
            kind="rigid",
            order="c2z",
            frame="input",
            phi_domain=DOMAIN,
            expected_science_revision=studio.science_revision,
        )
        run_id, run = fitted(studio)
        report = studio.call("run.report", run_id=run_id)
    assert any(c["label"].startswith("<img") for c in run["couplings"])
    assert "<img" not in report["html"] and "&lt;img src=x onerror=alert(1)&gt;" in report["html"]
    rows = list(csv.DictReader(io.StringIO(report["csv"])))
    formulas = [r["label"] for r in rows if r["label"].lstrip("'").startswith("=")]
    assert formulas and all(label.startswith("'=") for label in formulas)  # quoted, not a formula


def test_an_unknown_or_damaged_run_is_refused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    with Studio.local(project) as studio:
        with pytest.raises(OperationFailed) as unknown:
            studio.call("run.report", run_id="run_000009")
        assert unknown.value.code == "ID_NOT_FOUND"
        studio.call("project.open_example", OPEN)
        run_id, _ = fitted(studio)
        digest = studio.call("run.get", run_id=run_id)["run"]["result_sha256"]
        (project / "runs" / f"{digest}.json").write_text("{}", encoding="utf-8")  # damaged
        with pytest.raises(OperationFailed) as damaged:
            studio.call("run.report", run_id=run_id)
        assert damaged.value.code == "INTERNAL"
