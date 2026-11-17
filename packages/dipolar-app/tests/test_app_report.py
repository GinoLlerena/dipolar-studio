"""The run's summary report (run.report, beta step B2): the same run gives the same bytes; it says
what the run says, nothing from the current project; user strings are escaped in the HTML and
cannot run as spreadsheet formulas in the CSV."""

from __future__ import annotations

import csv
import html
import io
import json
import math
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


# --------------------------------------------------------------------------- round 57
def section(page: str, title: str) -> str:
    """A section's text, tags removed."""
    part = page.split(f"<h2>{title}</h2>", 1)[1].split("<h2>", 1)[0]
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", part))).strip()


def shown(text: str) -> float:
    return float(text.replace("−", "-"))


def tight(studio: Studio) -> tuple[str, dict[str, Any]]:
    """The example with its observations replaced by a fit's own predictions and σ = 1e-5 Hz: a
    supported interval only a few 1e-7 degrees wide (the reviewer's case)."""
    studio.call("project.open_example", OPEN)
    first = studio.fit()
    exported = json.loads(studio.call("project.export")["text"])
    calc = {c["id"]: c["calculated"]["value"] for c in first["couplings"]}
    for c in exported["project"]["couplings"]:
        c["value"]["value"], c["sigma"]["value"] = calc[c["id"]], 1e-5
    studio.call("project.load", text=json.dumps(exported), expected_science_revision=studio.science_revision)
    return fitted(studio)


def test_values_are_shown_to_the_precision_of_their_uncertainty() -> None:
    with Studio.local() as studio:
        run_id, run = tight(studio)
        page = studio.call("run.report", run_id=run_id)["html"]
    rows = re.findall(
        r"<tr><td>(phi_deg|Szz|Delta)</td><td class=num>([^<]+)</td><td class=num>([^<]+)</td>"
        r"<td class=num>([^<]+)</td><td>",
        page,
    )
    assert len(rows) == 3, rows
    for name, estimate, lower, upper in rows:
        interval = next(i for i in run["intervals"] if i["parameter"] == name)
        assert interval["supported"]
        assert len({estimate, lower, upper}) == 3, (name, estimate, lower, upper)  # told apart
        places = len(estimate.split(".")[1])
        for text, value in ((estimate, interval["estimate"]), (lower, interval["lower"]), (upper, interval["upper"])):
            assert abs(shown(text) - value) <= 0.5 * 10**-places, (name, text, value)
    se = {s["name"]: s["value"] for s in run["stderr"]}
    phi_row = re.search(r"<tr><td>phi_deg</td><td class=num>([^<]+)</td><td class=num>([^<]+)</td></tr>", page)
    assert phi_row is not None
    assert len(phi_row.group(1).split(".")[1]) >= -math.floor(math.log10(se["phi_deg"]))  # not coarser than σ


def test_the_validity_wording_says_what_the_flags_mean() -> None:
    with Studio.local() as studio:
        studio.call("project.open_example", OPEN)
        run_id, run = fitted(studio)
        page = studio.call("run.report", run_id=run_id)["html"]
    result, validity, intervals = section(page, "Result"), section(page, "Validity"), section(page, "Intervals")
    assert "explains the data" not in page  # adequacy is the p-value policy, nothing stronger
    assert "Adequate (p ≥ 0.001 under the stated σ) yes" in result
    assert "Regular optimum (converged, resolved, interior, full rank) yes" in validity
    assert "identifiable" not in validity.split("Standard errors")[0].lower()  # regularity is not identifiability
    for flag in (
        "Converged yes",
        "Search resolved yes",
        "Derivatives resolved yes",
        "Inner rank 2 of 2",
        "Joint rank 3 of 3",
        "At a bound none",
    ):
        assert flag in validity, flag
    assert run["intervals_policy"] in intervals
    for i in run["intervals"]:
        assert re.search(rf"{i['parameter']} [0-9.−]+ [0-9.−]+ [0-9.−]+ yes", intervals), i["parameter"]


def test_a_singular_inner_problem_is_shown_as_such() -> None:
    with Studio.local() as studio:
        studio.call("project.open_example", OPEN)
        exported = json.loads(studio.call("project.export")["text"])
        exported["project"]["couplings"] = exported["project"]["couplings"][:1]
        studio.call("project.load", text=json.dumps(exported), expected_science_revision=studio.science_revision)
        run_id, run = fitted(studio)
        page = studio.call("run.report", run_id=run_id)["html"]
    assert run["validity"]["inner_condition_number"] is None and run["validity"]["inner_rank"] == 1
    assert "Inner condition number ∞ (singular)" in section(page, "Validity")


def test_the_report_does_not_depend_on_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rendered twice with the clock moved by a year: the same bytes."""
    import datetime as dt
    import time

    from dipolar_app import report as report_module

    with Studio.local() as studio:
        studio.call("project.open_example", OPEN)
        run_id, _ = fitted(studio)
        stored = studio.call("run.get", run_id=run_id)
    record = {k: v for k, v in stored["run"].items() if k != "stale"}
    real_time = time.time

    def move_clock(shift: float) -> None:
        class Moved(dt.datetime):
            @classmethod
            def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:  # type: ignore[override]
                return dt.datetime.fromtimestamp(real_time() + shift, tz)

        class MovedDate(dt.date):
            @classmethod
            def today(cls) -> dt.date:  # type: ignore[override]
                return dt.date.fromtimestamp(real_time() + shift)

        monkeypatch.setattr(time, "time", lambda: real_time() + shift)
        monkeypatch.setattr(dt, "datetime", Moved)
        monkeypatch.setattr(dt, "date", MovedDate)

    renders = []
    for shift in (0.0, 365 * 86400.0):
        move_clock(shift)
        html_text = report_module.render_html(record, stored["result"], software="s")
        renders.append((html_text, report_module.render_csv(record, stored["result"])))
        monkeypatch.undo()
    assert renders[0] == renders[1]


# --------------------------------------------------------------------------- round 58
def test_a_tiny_but_supported_interval_is_still_told_apart() -> None:
    """Round 58: predictions scaled by 1e-7 and σ = 1e-12 Hz put S near 2.5e-8 with a standard
    error of 1e-16; a 15-decimal cap showed estimate and endpoints equal. Scientific notation at
    the uncertainty's resolution tells them apart."""
    with Studio.local() as studio:
        studio.call("project.open_example", OPEN)
        first = studio.fit()
        exported = json.loads(studio.call("project.export")["text"])
        calc = {c["id"]: c["calculated"]["value"] for c in first["couplings"]}
        for c in exported["project"]["couplings"]:
            c["value"]["value"], c["sigma"]["value"] = calc[c["id"]] * 1e-7, 1e-12
        studio.call("project.load", text=json.dumps(exported), expected_science_revision=studio.science_revision)
        run_id, run = fitted(studio)
        page = studio.call("run.report", run_id=run_id)["html"]
    assert run["validity"]["regular"]
    rows = dict(
        (name, (e, lo, hi))
        for name, e, lo, hi in re.findall(
            r"<tr><td>(phi_deg|Szz|Delta)</td><td class=num>([^<]+)</td><td class=num>([^<]+)</td>"
            r"<td class=num>([^<]+)</td><td>",
            page,
        )
    )
    for i in run["intervals"]:
        if not i["supported"]:
            continue
        estimate, lower, upper = rows[i["parameter"]]
        assert len({estimate, lower, upper}) == 3, (i["parameter"], estimate, lower, upper)
        assert shown(lower) < shown(estimate) < shown(upper)
        for text, value in ((estimate, i["estimate"]), (lower, i["lower"]), (upper, i["upper"])):
            assert abs(shown(text) - value) <= 0.6 * abs(i["upper"] - i["lower"]), (text, value)


def test_rank_is_described_as_local_and_rival_basins_are_flagged() -> None:
    """Round 58: imported geometry, rigid C1 on [−90°, 90°]: full ranks and two basins near ±36.7°
    with Δχ² ≈ 3e-13. The report must not say the data determine every parameter outright."""
    xyz = (DATA / "biphenyl.xyz").read_text(encoding="utf-8")
    couplings = (DATA / "tutorial-couplings.csv").read_text(encoding="utf-8")
    names = xyz.split("\n")[1].split("atoms:")[1].split()
    with Studio.local() as studio:
        studio.call("project.import_xyz", xyz=xyz, name="two basins", expected_science_revision=0)
        spins = {s["atom"]: s["id"] for s in studio.call("project.describe")["spins"]}
        mapping = {label: spins[names.index(label)] for label in TUTORIAL_LABELS}
        studio.call("couplings.import", csv=couplings, confirmed_mapping=mapping, expected_science_revision=1)
        studio.call("molecule.set_torsion", torsion=[1, 0, 6, 7], expected_science_revision=studio.science_revision)
        studio.call(
            "model.set",
            kind="rigid",
            order="c1",
            frame="input",
            phi_domain=[{"value": -90, "unit": "deg"}, {"value": 90, "unit": "deg"}],
            expected_science_revision=studio.science_revision,
        )
        run_id, run = fitted(studio)
        page = studio.call("run.report", run_id=run_id)["html"]
    assert len(run["basins"]) >= 2 and run["basins"][1]["delta_chi2"] < 1.0
    validity = section(page, "Validity")
    assert "local diagnostic" in validity and "not that no other torsion fits as well" in validity
    assert "determine every parameter, even" not in page
    assert "Another basin fits about as well" in section(page, "Basins")
