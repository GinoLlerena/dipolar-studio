"""The summary report of a run (plan §4 "a deterministic HTML/CSV summary"; beta step B2).

`render_html` and `render_csv` turn one stored run (its record and its fit result) into a
self-contained HTML page and a CSV of the per-coupling table. They read nothing else: not the
current project, not the clock. So **the same run gives the same bytes** with the same software
(the report names the software's version, so another version may word it differently).

The HTML has no script, no external resource and no form; every string from the project or the
run (labels, sources, notes) is escaped. The CSV keeps full precision (each number as Python's
shortest round-trip representation) and guards text cells against spreadsheet formula injection.
"""

from __future__ import annotations

import csv
import html
import io
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

from dipolar_app.reporting import ADEQUATE_P_MIN

#: The report's own format, named in both outputs; bumped when their content changes.
REPORT_FORMAT: Final = "dipolar-report.1"

CSV_COLUMNS: Final = (
    "coupling_id",
    "label",
    "observed_Hz",
    "sigma_Hz",
    "calculated_Hz",
    "residual_Hz",
    "normalized_residual",
)

_STYLE = "\n".join(
    (
        'body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1d232b;',
        "margin:2rem auto;max-width:60rem;padding:0 1rem}",
        "h1{font-size:1.5rem;margin:0 0 .25rem}",
        "h2{font-size:1.1rem;margin:1.75rem 0 .5rem;border-bottom:1px solid #d5dae1;padding-bottom:.25rem}",
        "table{border-collapse:collapse;width:100%;margin:.25rem 0}",
        "th,td{text-align:left;padding:.2rem .5rem;border-bottom:1px solid #eceff3;vertical-align:top}",
        "th{font-weight:600;background:#f5f7fa}",
        "td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}",
        "dl{display:grid;grid-template-columns:max-content 1fr;gap:.15rem 1rem;margin:.25rem 0}",
        "dt{font-weight:600}dd{margin:0}",
        ".muted{color:#5b6573}.flag-no{color:#9a2b2b;font-weight:600}.flag-yes{color:#1f6b3a}",
        "code{font-size:.92em}",
    )
)


def _text(value: object) -> str:
    return html.escape(str(value), quote=True)


def _number(value: float | int | None, digits: int = 6) -> str:
    """A number for reading: `digits` significant digits, a typographic minus; None as an em dash."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        raise TypeError("a flag is not a number")
    if isinstance(value, int):
        text = str(value)
    elif not math.isfinite(value):
        text = "inf" if value > 0 else "-inf" if value < 0 else "nan"
    else:
        text = format(value, f".{digits}g")
    return text.replace("-", "−")


def _decimals(spread: float | None) -> int | None:
    """Decimal places that show `spread` (an uncertainty or an interval's half-width) to two
    significant digits, so a value is never shown coarser than its uncertainty (round 57); None
    when there is no usable spread."""
    if spread is None or not math.isfinite(spread) or spread <= 0:
        return None
    return max(0, min(15, 1 - math.floor(math.log10(spread))))


def _fixed(value: float | None, decimals: int | None) -> str:
    """`value` at `decimals` places (a typographic minus); `_number` when there are none."""
    if value is None or decimals is None or not math.isfinite(value):
        return _number(value)
    return f"{value:.{decimals}f}".replace("-", "\u2212")


def _interval_cells(estimate: float, lower: float | None, upper: float | None) -> tuple[str, str, str]:
    """An interval's estimate and endpoints at one precision fine enough to tell them apart: from
    the narrower half-width, refined until the three differ (round 57: a supported interval of
    width 3e-7 showed three equal numbers)."""
    sides = [
        d
        for d in (estimate - lower if lower is not None else None, upper - estimate if upper is not None else None)
        if d is not None and d > 0
    ]
    places = _decimals(min(sides)) if sides else None
    if places is None:
        return _number(estimate), _number(lower), _number(upper)
    cells = (_fixed(estimate, places), _fixed(lower, places), _fixed(upper, places))
    while places < 15 and len({c for c in cells if c != "\u2014"}) < sum(c != "\u2014" for c in cells):
        places += 1
        cells = (_fixed(estimate, places), _fixed(lower, places), _fixed(upper, places))
    return cells


def _flag(value: bool | None, yes: str = "yes", no: str = "no") -> str:
    if value is None:
        return '<span class="muted">not assessed</span>'
    return f'<span class="flag-yes">{yes}</span>' if value else f'<span class="flag-no">{no}</span>'


def _table(header: Sequence[tuple[str, bool]], rows: Iterable[Sequence[str]]) -> str:
    """`header`: (title, numeric) per column; `rows`: cells already escaped or formatted."""
    head = "".join(f'<th{" class=num" if num else ""} scope="col">{_text(t)}</th>' for t, num in header)
    body = "".join(
        "<tr>" + "".join(f"<td{' class=num' if header[i][1] else ''}>{c}</td>" for i, c in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _dl(items: Iterable[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{_text(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"


def _named(values: Sequence[Mapping[str, Any]] | None) -> dict[str, float]:
    return {str(v["name"]): float(v["value"]) for v in values or ()}


def _condition(validity: Mapping[str, Any]) -> str:
    """The inner condition number; an infinite one is sent as null (JSON has no infinity), which
    with a deficient inner rank means singular, not unknown (round 57)."""
    value = validity.get("inner_condition_number")
    if value is not None:
        return _number(value, 4)
    if validity["inner_rank"] < validity["inner_parameters"]:
        return "\u221e (singular)"
    return '<span class="muted">not computed</span>'


def render_html(run: Mapping[str, Any], result: Mapping[str, Any], *, software: str) -> str:
    """The report page of a run. `run` is the run record (`RunOut` as JSON), `result` its fit
    (`FitRunOut` as JSON), `software` the version line (`dipolar --version`)."""
    model = result["model"]
    domain = model["phi_domain"]
    stderr = _named(result.get("stderr"))
    parts: list[str] = []
    add = parts.append

    add(f"<h1>Fit report: {_text(run['id'])}</h1>")
    add(
        f'<p class="muted">Dipolar Studio: the torsion and orientational order of a biphenyl-type '
        f"molecule from its dipolar couplings. Estimand: <strong>{_text(result['estimand'])}</strong>.</p>"
    )

    if result.get("statement"):
        add(f"<p>{_text(result['statement'])}</p>")
    add("<h2>Result</h2>")
    rows = [
        (_text(name), _fixed(value, _decimals(stderr.get(name))), _number(stderr.get(name), 2))
        for name, value in [*_named(result["theta"]).items(), *_named(result["order"]).items()]
    ]
    add(_table([("Parameter", False), ("Value", True), ("Standard error", True)], rows))
    rms = result["rms_residual"]
    add(
        _dl(
            [
                ("χ²", _number(result["chi2"])),
                ("Observations N", _number(result["n_obs"])),
                ("Free parameters", _number(result["p_free"])),
                ("Degrees of freedom ν", _number(result.get("nu"))),
                ("p-value", _number(result.get("p_value"), 4)),
                (f"Adequate (p ≥ {ADEQUATE_P_MIN:g} under the stated σ)", _flag(result.get("adequate"))),
                ("RMS residual", f"{_number(rms['value'], 4)} {_text(rms['unit'])}"),
            ]
        )
    )

    add("<h2>Validity</h2>")
    v = result["validity"]
    add(
        _dl(
            [
                ("Converged", _flag(v["converged"])),
                (
                    "Regular optimum (converged, resolved, interior, full rank)",
                    _flag(v["regular"]),
                ),
                ("Physically admissible order", _flag(v.get("physically_admissible"))),
                ("Search resolved", _flag(v["search_resolved"])),
                ("Derivatives resolved", _flag(v["derivatives_resolved"])),
                ("Inner rank", f"{_number(v['inner_rank'])} of {_number(v['inner_parameters'])}"),
                ("Joint rank", f"{_number(v['joint_rank'])} of {_number(v['joint_parameters'])}"),
                ("Inner condition number", _condition(v)),
                ("At a bound", _text(", ".join(v.get("at_bound") or ())) or "none"),
            ]
        )
    )
    add(
        '<p class="muted">Standard errors, ν and intervals need a regular optimum. Identifiability is '
        "the ranks: a full rank and no undetermined direction mean the data determine every parameter, "
        "even at a bound.</p>"
    )
    unidentified = result.get("unidentified") or ()
    if unidentified:
        directions = "".join(
            "<li>" + _text(", ".join(f"{d['name']} {_number(d['value'], 4)}" for d in direction)) + "</li>"
            for direction in unidentified
        )
        add(f"<p>Directions the data do not determine:</p><ul>{directions}</ul>")

    add("<h2>Intervals</h2>")
    add(f"<p>{_text(result['intervals_policy'])}</p>")
    if result["intervals"]:
        kinds = sorted({str(i["label"]) for i in result["intervals"]})
        add(f'<p class="muted">{_text("; ".join(kinds))}</p>')
        add(
            _table(
                [
                    ("Parameter", False),
                    ("Estimate", True),
                    ("Lower", True),
                    ("Upper", True),
                    ("Supported", False),
                    ("Note", False),
                ],
                (
                    (
                        _text(i["parameter"]),
                        *_interval_cells(i["estimate"], i.get("lower"), i.get("upper")),
                        _flag(i["supported"]),
                        _text(i["note"]),
                    )
                    for i in result["intervals"]
                ),
            )
        )

    add("<h2>Model</h2>")
    notes = "".join(f"<li>{_text(n)}</li>" for n in result.get("notes") or ())
    add(
        _dl(
            [
                ("Model", _text(model["kind"])),
                ("Order model", _text(model["order"])),
                ("Frame", _text(model["frame"])),
                (
                    "Torsion domain",
                    f"[{_number(domain[0]['value'])}, {_number(domain[1]['value'])}] {_text(domain[0]['unit'])}",
                ),
            ]
        )
    )
    if notes:
        add(f"<ul>{notes}</ul>")

    if result["basins"]:
        add("<h2>Basins</h2>")
        add(
            _table(
                [("Torsion", True), ("χ²", True), ("Δχ²", True)],
                (
                    (
                        _text(", ".join(f"{t['name']} {_number(t['value'])}" for t in b["theta"])),
                        _number(b["chi2"]),
                        _number(b["delta_chi2"]),
                    )
                    for b in result["basins"]
                ),
            )
        )

    add("<h2>Couplings</h2>")
    add(
        _table(
            [
                ("Coupling", False),
                ("Observed (Hz)", True),
                ("σ (Hz)", True),
                ("Calculated (Hz)", True),
                ("Residual (Hz)", True),
                ("Residual / σ", True),
            ],
            (
                (
                    f'{_text(c["label"])} <span class="muted">{_text(c["id"])}</span>',
                    _number(c["observed"]["value"]),
                    _number(c["sigma"]["value"]),
                    _number(c["calculated"]["value"]),
                    _number(c["residual"]["value"], 4),
                    _number(c["normalized_residual"], 3),
                )
                for c in result["couplings"]
            ),
        )
    )

    add("<h2>Provenance</h2>")
    context = result.get("numerical_context") or {}
    add(
        _dl(
            [
                ("Run", f"<code>{_text(run['id'])}</code>"),
                ("Job", f"<code>{_text(run['job_id'])}</code>"),
                ("Requested by", _text(run["owner"])),
                ("Created", _text(run["created_at"])),
                ("Science revision", _number(run["science_revision"])),
                ("Science hash", f"<code>{_text(run['science_hash'])}</code>"),
                ("Input hash", f"<code>{_text(run['input_hash'])}</code>"),
                ("Result hash", f"<code>{_text(run['result_sha256'])}</code>"),
                ("Fit version", f"<code>{_text(result['fit_version'])}</code>"),
                *((f"Numerical context: {k}", f"<code>{_text(context[k])}</code>") for k in sorted(context)),
                ("Software", _text(software)),
                ("Report format", _text(REPORT_FORMAT)),
            ]
        )
    )
    add(
        '<p class="muted">The same run gives the same report with the same software (named above). The '
        "couplings, at full precision, are in the CSV that goes with it.</p>"
    )

    title = f"Dipolar Studio fit report: {run['id']}"
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_text(title)}</title>\n<style>\n{_STYLE}\n</style>\n</head>\n<body>\n"
        + "\n".join(parts)
        + "\n</body>\n</html>\n"
    )


def _cell(text: str) -> str:
    """A text cell that a spreadsheet will not run as a formula (OWASP: =, +, -, @, tab, CR)."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def render_csv(run: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    """The per-coupling table at full precision, one row per coupling, with a comment-free header
    (so any CSV reader takes it); the run and the format are in the file's name and the HTML."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for c in result["couplings"]:
        writer.writerow(
            [
                _cell(str(c["id"])),
                _cell(str(c["label"])),
                repr(float(c["observed"]["value"])),
                repr(float(c["sigma"]["value"])),
                repr(float(c["calculated"]["value"])),
                repr(float(c["residual"]["value"])),
                repr(float(c["normalized_residual"])),
            ]
        )
    return out.getvalue()
