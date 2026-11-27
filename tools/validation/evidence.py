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
  the failure unresolved. Round 84 (A5): the annex entry holds the plan's fields (procedure 6:
  frame and observable convention, geometry, vibrational corrections, solvent and sample
  context, numerical comparison, and the likely cause or its limits), each a non-empty text, not
  all one text, and not the same as another cell's. Each receipt links its own Markdown heading,
  which the public file holds once, with a body. These checks are structural: the owner's
  attestation remains the check of substance.

Every problem is value-free: it names the cell and what is wrong, never a number or a file's
content.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import unicodedata
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
#: The plan's fields of an annex entry (procedure 6), beside the key's condition and estimand.
ANNEX_TEXT_FIELDS = (
    "frame_and_convention",
    "geometry",
    "vibrational_corrections",
    "sample_context",
    "numerical_comparison",
    "cause",
)
ANNEX_FIELDS = frozenset({*KEY_FIELDS, "kind", *ANNEX_TEXT_FIELDS})
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
    if str(pure) != rel:  # round 86: one file, one spelling (no "./", "//" or trailing "/")
        return None
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        return None
    if (pure.parts[0].casefold() == LOCAL) != local:  # round 87: in any letter case
        return None
    here = root
    try:  # round 92 (A1): a path that cannot be stat'ed is no file, never an exception
        for part in pure.parts:
            here = here / part
            if here.is_symlink():
                return None
        return here if here.is_file() else None
    except OSError:
        return None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(root: Path, ref: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    path = _file(root, ref["path"], local=True)
    if path is None:
        return None, "is not an existing local file under datasets-local/, reached through no link"
    try:
        stale = _sha(path) != ref["sha256"]
        record = None if stale else json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None, "cannot be read"
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None, "is not a JSON record"
    if stale:
        return None, "is stale: its SHA-256 is not the referenced one"
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
    texts = [record[f] for f in ANNEX_TEXT_FIELDS]
    if not all(_text(t) for t in texts):
        return "has an empty field, or a field that is not text"
    if len({t.strip() for t in texts}) == 1:
        return "gives one text in every field"
    return None


def _annex_texts(root: Path, ref: Mapping[str, Any]) -> tuple[str, ...] | None:
    record, _ = _record(root, ref)
    return None if record is None else tuple(str(record[f]).strip() for f in ANNEX_TEXT_FIELDS)


_HEADING = re.compile(r"(#{1,6}) \S.*")


_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


#: Round 91 (B4): further text that does not render: an element marked hidden, a link-reference
#: definition, and zero-width or soft-hyphen characters.
#: Round 92: the hidden attribute itself (not a class name containing "hidden"), or display:none.
_HIDE = r"(?=[^>]*(?:\shidden(?=[\s=>/])|\sstyle\s*=\s*[\"'][^\"']*display\s*:\s*none))"
_HIDDEN = re.compile(rf"<(\w+)\b{_HIDE}[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE)
_HIDDEN_UNCLOSED = re.compile(rf"<\w+\b{_HIDE}[^>]*>.*\Z", re.DOTALL | re.IGNORECASE)
#: Letters that render as blank (Hangul fillers), removed before looking for a word.
_FILLERS = re.compile("[\u115f\u1160\u3164\uffa0]")
#: A visible word: two letters in a row (round 92, B4: a positive rule, not a list of cases).
_WORD = re.compile(r"[^\W\d_]{2,}")
_LINK_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*\S.*$", re.MULTILINE)
_INVISIBLE = re.compile("[\u00ad\u200b-\u200f\u2060\ufeff]")


def _rendered(text: str) -> str:
    """The text without what does not render: HTML comments, an unclosed one included (round
    87), hidden elements, link-reference definitions and invisible characters (round 91)."""
    text = re.sub(r"<!--.*\Z", "", _COMMENT.sub("", text), flags=re.DOTALL)
    text = _HIDDEN_UNCLOSED.sub("", _HIDDEN.sub("", text))
    return _INVISIBLE.sub("", _LINK_DEFINITION.sub("", text))


def _visible(line: str) -> bool:
    """Whether a rendered line shows a word (round 92, B4): entities decoded, blank fillers
    removed, tags and link targets stripped."""
    # Format and combining characters are not word characters, so they never make a word.
    text = unicodedata.normalize("NFC", html.unescape(line))
    text = re.sub(r"\]\([^)]*\)", "]", re.sub(r"<[^>]*>", "", _FILLERS.sub("", text)))
    return _WORD.search(text) is not None


def _section_has_body(lines: list[str], heading: str) -> bool:
    """Whether the heading's own text (up to its next heading of any level: round 91) holds a
    line that renders. ``lines`` are the rendered text's, without HTML
    comments (``_rendered``; rounds 86 and 87: a comment does not render, so it is not a body)."""
    at = lines.index(heading)
    for line in lines[at + 1 :]:
        if _HEADING.fullmatch(line):  # round 91 (B4): a body comes before the first subheading
            return False
        if _visible(line):  # a visible word, not a bare tag, an entity or a blank filler
            return True
    return False


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
    try:
        if _sha(path) != public["sha256"]:
            return "links a public entry that changed after its review"
        lines = _rendered(path.read_text(encoding="utf-8")).splitlines()
    except OSError:
        return "links a public file that cannot be read"
    except UnicodeDecodeError:
        return "links a public file that is not text"
    heading = public["heading"]
    if heading not in lines:
        return "links a public file without the reviewed entry's heading"
    if not _HEADING.fullmatch(heading):
        return "links a heading that is not a Markdown heading"
    if lines.count(heading) != 1:
        return "links a heading that the public file holds more than once"
    if not _section_has_body(lines, heading):
        return "links a heading without a body"
    return None


def _public_heading(root: Path, ref: Mapping[str, Any]) -> tuple[str, str] | None:
    record, _ = _record(root, ref)
    if record is None or not isinstance(record.get("public_entry"), Mapping):
        return None
    path = _file(root, record["public_entry"].get("path"), local=False)
    if path is None:
        return None
    stat = path.stat()  # round 87: the file itself, whatever spelling or letter case names it
    return f"{stat.st_dev}:{stat.st_ino}", str(record["public_entry"].get("heading"))


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
        passed = []
        for e in good:
            k = key(e)
            if k in want and (problem := check(root, e)):
                problems.append(f"{name}: the evidence for {k[2]} {k[3]} ({k[1]}) {problem}")
            elif k in want:
                passed.append(e)
        # Round 84 (A5): one cell's evidence does not stand in for another's.
        shared = _annex_texts if name == "annex" else _public_heading
        seen: dict[object, tuple[str, ...]] = {}
        for e in passed:
            k, what = key(e), shared(root, e)
            if what is not None and what in seen and seen[what] != k:
                other = seen[what]
                problems.append(
                    f"{name}: the evidence for {k[2]} {k[3]} ({k[1]}) is the same as for "
                    f"{other[2]} {other[3]} ({other[1]})"
                )
            elif what is not None:
                seen[what] = k
    return problems
