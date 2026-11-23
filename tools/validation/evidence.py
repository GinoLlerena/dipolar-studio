"""Owner-local evidence for the V1.5 report (round 83, A4 and A5).

Two records, both kept on the owner's machine and read by ``verification.run_report``:

- **The method-evidence record** (A4) says which of the four inputs of a reproduction claim the
  source documents (V0.3 §6: geometry, objective, weights, corrections), gives each documented
  one, and names where it is documented. It sets the authors'-analysis track's mode
  (``prereg_labels.reproduction_mode``) and the fit that track uses. This runner expresses the
  authors' geometry as the protocol's shape (a planar regular hexagon with radial C–H) with the
  authors' two radii, the objective as least squares, the weights as 1/σ² or uniform, and only
  an empty list of corrections. A record outside that is refused, not approximated.
- **Review references** (A5). A disagreeing cell counts as reviewed only through a reference (path
  and SHA-256) to an existing local annex entry, and to an existing local review receipt that
  links the reviewed public entry by path, SHA-256 and heading. Each file binds the dataset,
  track, cell and protocol revision. A missing, stale, unbound, linked or misplaced file leaves
  the failure unresolved.

Every problem is value-free: it names the cell and what is wrong, never a number or a file's
content.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import prereg_labels as pl

LOCAL = "datasets-local"

# ------------------------------------------------------------------ the method record (A4)
METHOD_FIELDS = frozenset(
    {"dataset", "protocol_sha256", "documented", "geometry", "objective", "weights", "corrections", "sources"}
)
GEOMETRY_FIELDS = frozenset({"r_cc_angstrom", "r_ch_angstrom"})
#: What the fixed-linear fitter implements: least squares, with weights 1/σ² or uniform.
OBJECTIVES = ("least squares",)
WEIGHTS = ("1/sigma^2", "uniform")
FALLBACK_WEIGHTS = "1/sigma^2"


@dataclass(frozen=True)
class Method:
    """The authors'-analysis track's mode and the fit it uses (None for a pending track)."""

    mode: pl.ReproductionMode = "pending"
    documented: tuple[str, ...] = ()
    geometry: Mapping[str, float] | None = None
    weights: str | None = None  # the weights applied: the documented ones, or 1/σ² in the fallback
    sources: Mapping[str, str] = field(default_factory=dict)


def _distance(x: object) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def method(record: object, *, dataset: str, protocol: str) -> tuple[Method, list[str]]:
    """The method record's track mode and fit, or value-free problems. No record: pending."""
    if record is None:
        return Method(), []
    if not isinstance(record, Mapping) or set(record) != METHOD_FIELDS:
        return Method(), ["the method record does not have exactly the fields " + ", ".join(sorted(METHOD_FIELDS))]
    if record["dataset"] != dataset or record["protocol_sha256"] != protocol:
        return Method(), ["the method record is not for this dataset at this protocol revision"]
    documented = record["documented"]
    if (
        not isinstance(documented, list)
        or not all(isinstance(x, str) for x in documented)
        or len(set(documented)) != len(documented)
        or not set(documented) <= set(pl.REPRODUCTION_REQUIREMENTS)
    ):
        return Method(), [
            "the method record's documented inputs are not distinct names among "
            + ", ".join(pl.REPRODUCTION_REQUIREMENTS)
        ]
    problems = []
    for name in pl.REPRODUCTION_REQUIREMENTS:
        if (record[name] is not None) != (name in documented):
            problems.append(f"the method record gives the {name} if and only if it is documented: it does not")
    geometry = record["geometry"]
    if geometry is not None and (
        not isinstance(geometry, Mapping)
        or set(geometry) != GEOMETRY_FIELDS
        or not all(_distance(geometry[k]) for k in GEOMETRY_FIELDS)
    ):
        problems.append(
            "the method record's geometry is not two positive radii (" + ", ".join(sorted(GEOMETRY_FIELDS)) + ")"
        )
    if record["objective"] is not None and record["objective"] not in OBJECTIVES:
        problems.append("the method record's objective is not one the fixed-linear fitter implements")
    if record["weights"] is not None and record["weights"] not in WEIGHTS:
        problems.append("the method record's weights are not ones the fixed-linear fitter implements")
    if record["corrections"] is not None and record["corrections"] != []:
        problems.append("the method record documents a correction this runner cannot apply")
    sources = record["sources"]
    if (
        not isinstance(sources, Mapping)
        or set(sources) != set(documented)
        or not all(isinstance(s, str) and s.strip() for s in sources.values())
    ):
        problems.append("the method record does not name a source for exactly each documented input")
    if problems:
        return Method(), problems
    mode = pl.reproduction_mode(documented)
    if mode == "pending":
        return Method(documented=tuple(documented), sources=dict(sources)), []
    weights = record["weights"] if mode == "reproduction" else FALLBACK_WEIGHTS
    radii = {k: float(geometry[k]) for k in sorted(GEOMETRY_FIELDS)}
    return Method(mode, tuple(documented), radii, weights, dict(sources)), []


# ------------------------------------------------------------------- review references (A5)
KEY_FIELDS = ("dataset", "track", "condition", "component", "protocol_sha256")
REF_FIELDS = frozenset({*KEY_FIELDS, "path", "sha256"})
ANNEX_FIELDS = frozenset({*KEY_FIELDS, "kind", "entry"})
RECEIPT_FIELDS = frozenset({*KEY_FIELDS, "kind", "reviewer", "public_entry"})
PUBLIC_FIELDS = frozenset({"path", "sha256", "heading"})


def key(entry: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(entry[f]) for f in KEY_FIELDS)


def _file(root: Path, rel: object, *, local: bool) -> Path | None:
    """The regular file at a checkout-relative POSIX path, under datasets-local/ or outside it as
    asked, reached through no link and leaving the checkout nowhere; else None."""
    if not isinstance(rel, str) or not rel or "\\" in rel:
        return None
    pure = PurePosixPath(rel)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        return None
    if (pure.parts[0] == LOCAL) != local:
        return None
    here = root
    for part in pure.parts:
        here = here / part
        if here.is_symlink():
            return None
    return here if here.is_file() else None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(root: Path, ref: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    path = _file(root, ref["path"], local=True)
    if path is None:
        return None, "is not an existing local file under datasets-local/, reached through no link"
    if _sha(path) != ref["sha256"]:
        return None, "is stale: its SHA-256 is not the referenced one"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, "is not a JSON record"
    if not isinstance(record, dict):
        return None, "is not a JSON record"
    if any(f not in record or str(record[f]) != str(ref[f]) for f in KEY_FIELDS):
        return None, "is bound to another dataset, track, cell or protocol revision"
    return record, None


def _text(x: object) -> bool:
    return isinstance(x, str) and bool(x.strip())


def check_annex(root: Path, ref: Mapping[str, Any]) -> str | None:
    record, problem = _record(root, ref)
    if record is None:
        return problem
    if set(record) != ANNEX_FIELDS or record["kind"] != "annex":
        return "is not an annex entry (fields " + ", ".join(sorted(ANNEX_FIELDS)) + ", kind 'annex')"
    if not _text(record["entry"]):
        return "is empty"
    return None


def check_receipt(root: Path, ref: Mapping[str, Any]) -> str | None:
    record, problem = _record(root, ref)
    if record is None:
        return problem
    if set(record) != RECEIPT_FIELDS or record["kind"] != "review receipt":
        return "is not a review receipt (fields " + ", ".join(sorted(RECEIPT_FIELDS)) + ", kind 'review receipt')"
    if not _text(record["reviewer"]):
        return "names no reviewer"
    public = record["public_entry"]
    if not isinstance(public, dict) or set(public) != PUBLIC_FIELDS or not _text(public["heading"]):
        return "does not link a public entry by " + ", ".join(sorted(PUBLIC_FIELDS))
    path = _file(root, public["path"], local=False)
    if path is None:
        return "links no existing public file outside datasets-local/, reached through no link"
    if _sha(path) != public["sha256"]:
        return "links a public entry that changed after its review"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return "links a public file that is not text"
    if public["heading"] not in lines:
        return "links a public file without the reviewed entry's heading"
    return None


def review_coverage(
    disagreeing: Iterable[Mapping[str, Any]],
    annex: Iterable[object],
    receipts: Iterable[object],
    *,
    root: Path,
) -> list[str]:
    """Exact one-to-one coverage of the disagreeing keys by annex references and by receipt
    references, each reaching an existing, current file bound to its key: missing, duplicate,
    stale, unrelated or unbound evidence, and references with other fields, are problems."""
    want = {key(k) for k in disagreeing}
    problems = []
    checks: tuple[tuple[str, list[object], Callable[[Path, Mapping[str, Any]], str | None]], ...] = (
        ("annex", list(annex), check_annex),
        ("receipts", list(receipts), check_receipt),
    )
    for name, refs, check in checks:
        if any(not isinstance(e, Mapping) or set(e) != REF_FIELDS for e in refs):
            problems.append(f"{name}: a reference without exactly the fields {sorted(REF_FIELDS)}")
            continue
        good: list[Mapping[str, Any]] = [e for e in refs if isinstance(e, Mapping)]
        counts = Counter(key(e) for e in good)
        problems += [f"{name}: {k[2]} {k[3]} ({k[1]}) is listed twice" for k, n in counts.items() if n > 1]
        problems += [f"{name}: no entry for {k[2]} {k[3]} ({k[1]})" for k in sorted(want - set(counts))]
        problems += [
            f"{name}: {k[2]} {k[3]} ({k[1]}) is stale or not a disagreement" for k in sorted(set(counts) - want)
        ]
        for e in good:
            k = key(e)
            if k in want and (problem := check(root, e)):
                problems.append(f"{name}: the evidence for {k[2]} {k[3]} ({k[1]}) {problem}")
    return problems
