"""File formats and import reconciliation (plan D5, D6; ADR-0005, ADR-0006; M1 step 4).

- **XYZ** (``parse_xyz``): an atom count, a comment line, then one line per atom with
  "element x y z" in Å. The parser is strict: every problem is an error with its line number,
  and nothing is guessed.
- **Couplings CSV** (``parse_couplings_csv``):
  - required columns: spin_a, spin_b, D_obs_Hz, sigma_Hz;
  - optional columns: sigma_source, multiplicity, equivalent_pairs (space-separated),
    observable (only "D"), unit (only "Hz");
  - an absent column or an empty cell is *omitted*, kept distinct from "1" (D-5);
  - unknown columns are reported, not silently used.
- **Rows keyed by pair orbit** (fixed-geometry fits, D-5): with an ``OrbitOf`` function,
  reconciliation matches rows by pair orbit, so another member of an observed orbit updates that
  row; two rows in one orbit are refused; an omitted multiplicity or class is filled in from the
  orbit, and an explicit one must match it (as sets) or the import is refused with the difference.
- **Reconciliation (D5)** (``reconcile``):
  - imported labels are only proposed against the project's spins; the mapping applies only
    after the caller confirms it;
  - the original labels are kept on each coupling (``source_labels``);
  - the reviewable diff lists additions, removals and changes against the current couplings, by
    spin pair;
  - a matching label is never shown as a "validated assignment".
- **Project files** (``dumps_project``, ``loads_project``): ``*.dipolar.json``, schema-versioned.
  Loading validates strictly, and an older file is upgraded through ``MIGRATIONS`` one version at
  a time. A newer file is refused rather than guessed at.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from dipolar_core.symmetry import ISOTOPES

from dipolar_app.errors import ErrorCode
from dipolar_app.project import (
    MAX_ATOMS,
    MAX_CLASS_SIZE,
    MAX_COUPLINGS,
    PROJECT_SCHEMA_VERSION,
    Coupling,
    Project,
    canonical_json,
    migrate_project,
    split_pair_label,
)
from dipolar_app.schemas import Hertz, wire_problem

PROJECT_FORMAT: Final = "dipolar-studio-project"
MAX_PROJECT_BYTES: Final = 64 * 2**20
REQUIRED_COLUMNS: Final = ("spin_a", "spin_b", "D_obs_Hz", "sigma_Hz")
OPTIONAL_COLUMNS: Final = ("sigma_source", "multiplicity", "equivalent_pairs", "observable", "unit")
#: The XYZ elements: the core's isotope table (D-6; round 76: B and Si were missing).
ELEMENTS: Final = frozenset(ISOTOPES)

Members = frozenset[frozenset[str]]


@dataclass(frozen=True)
class Orbits:
    """The pair orbits of a fixed-geometry project, prepared once per reconciliation (D-5).

    ``of(a, b)`` gives (key, members) of a pair of spins: the key is the smallest sorted spin-ID
    pair. ``class_of(members)`` gives the class that stands for an omitted ``equivalent_pairs``
    (empty for a single pair); it raises ValueError when the labels cannot express it unambiguously.
    """

    of: Callable[[str, str], tuple[tuple[str, str], Members]]
    class_of: Callable[[Members], tuple[str, ...]]


OrbitOf = Orbits

# A plain decimal number in ASCII (M3 step 2): float() alone also accepts "1_000", Unicode digits,
# "inf" and "nan". A decimal comma ("1,5") is never guessed: in this comma-separated format it
# splits the field, and the row is refused.
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


class FormatError(ValueError):
    """A file that does not follow its format; the message names the line or row. ``code`` and
    ``details`` carry a refusal's own envelope code when it has one (``science.refusal``)."""

    def __init__(self, message: str, code: ErrorCode | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.details = details or {}


# --------------------------------------------------------------------------- XYZ
@dataclass(frozen=True)
class XyzMolecule:
    elements: tuple[str, ...]
    positions: tuple[tuple[float, float, float], ...]  # Å
    comment: str


def parse_xyz(text: str) -> XyzMolecule:
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) < 2:
        raise FormatError("line 1: an XYZ file needs an atom count and a comment line")
    count = lines[0].strip()
    if not re.fullmatch(r"[0-9]{1,9}", count):
        raise FormatError(f"line 1: the atom count must be an integer, got {count!r}")
    n = int(count)
    if not 1 <= n <= MAX_ATOMS:
        raise FormatError(f"line 1: the atom count must be between 1 and {MAX_ATOMS}, got {n}")
    if len(lines) != n + 2:
        raise FormatError(f"the file declares {n} atoms but has {len(lines) - 2} atom lines")
    elements, positions = [], []
    for number, line in enumerate(lines[2:], start=3):
        fields = line.split()
        if len(fields) != 4:
            raise FormatError(f"line {number}: expected 'element x y z', got {line.strip()!r}")
        element = fields[0]
        if element not in ELEMENTS:
            raise FormatError(f"line {number}: unsupported element {element!r}; supported: {sorted(ELEMENTS)}")
        if not all(_DECIMAL.fullmatch(v) for v in fields[1:]):
            raise FormatError(f"line {number}: coordinates must be plain decimal numbers, got {fields[1:]}")
        xyz = tuple(float(v) for v in fields[1:])
        if not all(math.isfinite(v) for v in xyz):
            raise FormatError(f"line {number}: coordinates must be finite")
        elements.append(element)
        positions.append((xyz[0], xyz[1], xyz[2]))
    return XyzMolecule(tuple(elements), tuple(positions), lines[1])


# --------------------------------------------------------------------------- couplings CSV
@dataclass(frozen=True)
class CouplingRow:
    row: int  # 1-based data row, for messages
    spin_a: str
    spin_b: str
    value_hz: float
    sigma_hz: float
    sigma_source: str
    multiplicity: int | None  # None: omitted (an absent column or an empty cell), never "1"
    equivalent_pairs: tuple[str, ...] | None  # None: omitted

    @property
    def class_entries(self) -> tuple[str, ...]:
        return self.equivalent_pairs or ()

    @property
    def multiplicity_or_one(self) -> int:
        return 1 if self.multiplicity is None else self.multiplicity


@dataclass(frozen=True)
class CouplingTable:
    rows: tuple[CouplingRow, ...]
    ignored_columns: tuple[str, ...]


def _number(text: str, what: str, row: int) -> float:
    stripped = text.strip(" \t")
    if not _DECIMAL.fullmatch(stripped):
        raise FormatError(f"row {row}: {what} must be a plain decimal number (digits and a point), got {text!r}")
    value = float(stripped)
    if not math.isfinite(value):
        raise FormatError(f"row {row}: {what} must be finite")
    return value


def parse_couplings_csv(text: str, *, default_sigma_source: str = "not stated") -> CouplingTable:
    """Parse a couplings table. The contract:
    - one leading byte-order mark is removed (spreadsheet exports write one); CRLF line ends work;
    - quoting is strict: a malformed or unterminated quoted field is an error, never repaired;
    - labels are kept verbatim (no trimming), so they match spin labels exactly (D5);
    - numbers may have surrounding spaces.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    try:
        return _parse_couplings(text, default_sigma_source)
    except csv.Error as exc:
        raise FormatError(f"malformed CSV (line {exc.args[0] if exc.args else '?'}): {exc}") from None


def _parse_couplings(text: str, default_sigma_source: str) -> CouplingTable:
    reader = csv.DictReader(io.StringIO(text), strict=True)
    header = tuple(reader.fieldnames or ())
    if len(set(header)) != len(header):
        raise FormatError("header: duplicate column names")
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise FormatError(f"header: missing required column(s) {missing}")
    ignored = tuple(c for c in header if c not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    rows = []
    for number, raw in enumerate(reader, start=1):
        if number > MAX_COUPLINGS:
            raise FormatError(f"more than {MAX_COUPLINGS} rows")
        if None in raw or any(v is None for v in raw.values()):
            raise FormatError(f"row {number}: the number of fields does not match the header")
        a, b = raw["spin_a"], raw["spin_b"]
        if not a.strip() or not b.strip():
            raise FormatError(f"row {number}: spin labels must not be empty")
        if a == b:
            raise FormatError(f"row {number}: a spin cannot couple to itself ({a!r})")
        if raw.get("observable", "D").strip() not in ("", "D"):
            raise FormatError(f"row {number}: only signed dipolar couplings (observable D) are supported")
        if raw.get("unit", "Hz").strip() not in ("", "Hz"):
            raise FormatError(f"row {number}: values must be in Hz")
        sigma = _number(raw["sigma_Hz"], "sigma_Hz", number)
        if sigma <= 0:
            raise FormatError(f"row {number}: sigma_Hz must be positive")
        multiplicity_text = raw.get("multiplicity", "").strip()
        # ASCII digits only, bounded before int() (round 27): no Unicode digits, no huge numbers.
        if multiplicity_text and (
            not re.fullmatch(r"[0-9]{1,7}", multiplicity_text) or not 1 <= int(multiplicity_text) <= MAX_CLASS_SIZE
        ):
            raise FormatError(f"row {number}: multiplicity must be an integer from 1 to {MAX_CLASS_SIZE}")
        equivalent = tuple(raw.get("equivalent_pairs", "").split())
        if len(equivalent) > MAX_CLASS_SIZE:
            raise FormatError(f"row {number}: more than {MAX_CLASS_SIZE} equivalent pairs")
        rows.append(
            CouplingRow(
                row=number,
                spin_a=a,
                spin_b=b,
                value_hz=_number(raw["D_obs_Hz"], "D_obs_Hz", number),
                sigma_hz=sigma,
                sigma_source=raw.get("sigma_source", "").strip() or default_sigma_source,
                multiplicity=int(multiplicity_text) if multiplicity_text else None,
                equivalent_pairs=equivalent or None,
            )
        )
    if not rows:
        raise FormatError("the file has no coupling rows")
    return CouplingTable(tuple(rows), ignored)


# --------------------------------------------------------------------------- reconciliation (D5)
@dataclass(frozen=True)
class ImportDiff:
    """What applying the import would change. Nothing changes until ``apply`` is called with a
    mapping the user confirmed."""

    proposed_mapping: dict[str, str]  # imported label → spin ID; only exact label matches
    unmatched_labels: tuple[str, ...]  # need a user decision
    unresolved_pairs: tuple[str, ...] = ()  # equivalent-pair entries that name no two known labels
    added: tuple[tuple[str, str], ...] = ()  # spin-ID pairs new to the project
    removed: tuple[tuple[str, str], ...] = ()  # pairs present now and absent from the import
    changed: tuple[tuple[str, str], ...] = ()  # pairs whose value, σ or source differs
    unchanged: tuple[tuple[str, str], ...] = ()
    # The imported row of each incoming pair (added, changed and unchanged), so a preview can show
    # what the import would set next to what the project has (M3 step 2).
    incoming: Mapping[tuple[str, str], CouplingRow] = field(default_factory=dict, repr=False)
    table: CouplingTable | None = field(default=None, repr=False)
    # The project's couplings by the same keys (pairs, or pair-orbit keys for a fixed model).
    current: Mapping[tuple[str, str], Coupling] = field(default_factory=dict, repr=False)


def _pair_key(a: str, b: str) -> tuple[str, str]:
    """D is symmetric in its two spins, so a reversed pair is the same observation."""
    return (a, b) if a <= b else (b, a)


def _class_labels(row: CouplingRow, labels: Collection[str]) -> list[tuple[str, str]]:
    """The row's equivalent pairs split into imported labels (``split_pair_label``)."""
    return [split_pair_label(entry, labels) for entry in row.class_entries]


def _translated_class(row: CouplingRow, mapping: Mapping[str, str], label_of: Mapping[str, str]) -> tuple[str, ...]:
    """The row's class in the project's own labels, through the confirmed mapping (round 24)."""
    try:
        pairs = _class_labels(row, mapping.keys())
    except ValueError as exc:
        raise FormatError(f"row {row.row}: {exc}") from None
    return tuple(f"{label_of[mapping[a]]}-{label_of[mapping[b]]}" for a, b in pairs)


def _labels_in_order(row: CouplingRow, mapping: Mapping[str, str], c: Coupling) -> tuple[str, str]:
    """The row's labels in the order of the existing coupling's spins."""
    return (row.spin_a, row.spin_b) if mapping[row.spin_a] == c.spin_a else (row.spin_b, row.spin_a)


def _check_orbit_fields(
    row: CouplingRow,
    members: frozenset[frozenset[str]],
    mapping: Mapping[str, str],
    label_of: Mapping[str, str],
) -> None:
    """D-5: an explicit multiplicity or class must match the row's pair orbit (as unordered sets);
    an omitted one is filled in from it."""
    if row.multiplicity is not None and row.multiplicity != len(members):
        raise FormatError(
            f"row {row.row}: multiplicity {row.multiplicity}, but the pair orbit of {row.spin_a}–{row.spin_b} has "
            f"{len(members)} pairs under the declared symmetry (leave it empty to fill it in)",
            ErrorCode.OBSERVATIONS_CONFLICT,
        )
    if row.equivalent_pairs is None:
        return
    try:
        given = {frozenset((mapping[a], mapping[b])) for a, b in _class_labels(row, mapping.keys())}
    except ValueError as exc:
        raise FormatError(f"row {row.row}: {exc}") from None
    if given != members or len(given) != len(row.equivalent_pairs):

        def names(pairs: set[frozenset[str]]) -> list[str]:
            return sorted("-".join(label_of[x] for x in sorted(p)) for p in pairs)

        repeated = "; a pair is repeated" if len(given) != len(row.equivalent_pairs) else ""
        raise FormatError(
            f"row {row.row}: equivalent_pairs must be the pair orbit of {row.spin_a}–{row.spin_b} under the declared "
            f"symmetry (compared as sets); missing {names(set(members - given))}, not in the orbit "
            f"{names(given - set(members))}{repeated}",
            ErrorCode.OBSERVATIONS_CONFLICT,
        )


def _resolved(
    table: CouplingTable, mapping: Mapping[str, str], project: Project, orbit_of: OrbitOf | None = None
) -> dict[tuple[str, str], CouplingRow]:
    """The rows by key (their pair, or under a fixed-geometry model their pair-orbit key), with the
    mapping, repeats and the orbit fields checked; the same checks for reconciliation and import."""
    label_of = {s.id: s.label for s in project.molecule.spins}
    targets = list(mapping.values())
    if len(set(targets)) != len(targets):
        raise FormatError("the mapping must be one-to-one: two labels map to the same spin")
    spin_ids = {s.id for s in project.molecule.spins}
    # Every target, including labels that appear only in equivalent pairs (round 27).
    for label, target in mapping.items():
        if target not in spin_ids:
            raise FormatError(f"the label {label!r} maps to {target!r}, which is not a spin of the project")
    out: dict[tuple[str, str], CouplingRow] = {}
    for row in table.rows:
        ids = []
        for label in (row.spin_a, row.spin_b):
            if label not in mapping:
                raise FormatError(f"row {row.row}: the label {label!r} has no confirmed mapping")
            if mapping[label] not in spin_ids:
                raise FormatError(
                    f"row {row.row}: {label!r} maps to {mapping[label]!r}, which is not a spin of the project"
                )
            ids.append(mapping[label])
        if ids[0] == ids[1]:
            raise FormatError(f"row {row.row}: both labels map to the same spin {ids[0]}")
        if orbit_of is None:
            key = _pair_key(ids[0], ids[1])
            if key in out:
                raise FormatError(
                    f"row {row.row}: the pair {row.spin_a}–{row.spin_b} repeats row {out[key].row} "
                    "(merge symmetry copies into one row with a multiplicity)"
                )
        else:
            key, members = orbit_of.of(ids[0], ids[1])
            if key in out:
                raise FormatError(
                    f"row {row.row}: the pair {row.spin_a}–{row.spin_b} is in the pair orbit of row {out[key].row}: "
                    "repeat measurements of one pair orbit are not accepted in this release",
                    ErrorCode.OBSERVATIONS_CONFLICT,
                )
            _check_orbit_fields(row, members, mapping, label_of)
            try:
                orbit_of.class_of(members)  # the class an import stores must parse back (rounds 77–78)
            except ValueError as exc:
                raise FormatError(f"row {row.row}: {exc}") from None
        out[key] = row
    return out


def _current(project: Project, orbit_of: OrbitOf | None) -> dict[tuple[str, str], Coupling]:
    if orbit_of is None:
        return {_pair_key(c.spin_a, c.spin_b): c for c in project.couplings}
    return {orbit_of.of(c.spin_a, c.spin_b)[0]: c for c in project.couplings}


def _incoming_class(
    row: CouplingRow,
    mapping: Mapping[str, str],
    label_of: Mapping[str, str],
    orbit_of: OrbitOf | None,
) -> tuple[int, tuple[str, ...]]:
    """(multiplicity, class in the project's labels) that applying ``row`` stores."""
    if orbit_of is None:
        return row.multiplicity_or_one, _translated_class(row, mapping, label_of)
    _, members = orbit_of.of(mapping[row.spin_a], mapping[row.spin_b])
    # An explicit class has matched the orbit as sets; it is stored as the orbit in the project's
    # labels (one spelling, always parseable), and kept verbatim in source_equivalent_pairs (round 78).
    return len(members), orbit_of.class_of(members)


def reconcile(
    table: CouplingTable,
    project: Project,
    mapping: Mapping[str, str] | None = None,
    orbit_of: OrbitOf | None = None,
) -> ImportDiff:
    """Propose a mapping (exact label matches only) and, if every label is mapped, the diff. With
    ``orbit_of`` (a fixed-geometry model), rows are keyed by pair orbit (D-5)."""
    own = {label for row in table.rows for label in (row.spin_a, row.spin_b)}
    universe = own | {s.label for s in project.molecule.spins} | set(mapping or ())
    found, unresolved = set(own), []
    for row in table.rows:
        for entry in row.class_entries:
            try:
                found.update(split_pair_label(entry, universe))
            except ValueError:
                unresolved.append(entry)
    labels = sorted(found)
    by_label: dict[str, list[str]] = {}
    for s in project.molecule.spins:
        by_label.setdefault(s.label, []).append(s.id)
    proposed = {label: by_label[label][0] for label in labels if len(by_label.get(label, ())) == 1}
    effective = dict(mapping) if mapping is not None else proposed
    unmatched = tuple(label for label in labels if label not in effective)
    if unmatched or unresolved:
        return ImportDiff(proposed, unmatched, tuple(unresolved), table=table)
    label_of = {s.id: s.label for s in project.molecule.spins}
    incoming = _resolved(table, effective, project, orbit_of)
    current = _current(project, orbit_of)
    changed: list[tuple[str, str]] = []
    unchanged: list[tuple[str, str]] = []
    for key in sorted(incoming.keys() & current.keys()):
        row, c = incoming[key], current[key]
        # Every field that apply_import replaces (round 22): science and provenance alike.
        multiplicity, members = _incoming_class(row, effective, label_of, orbit_of)
        new = (row.value_hz, row.sigma_hz, row.sigma_source, multiplicity, members)
        old = (c.value.value, c.sigma.value, c.sigma_source, c.multiplicity, c.equivalent_pairs)
        same_pair = {effective[row.spin_a], effective[row.spin_b]} == {c.spin_a, c.spin_b}
        # Provenance counts too, except its first population (None → labels), documented (round 24).
        same = (
            new == old
            and same_pair  # another member of the orbit replaces the row's pair (D-5)
            and c.source_labels in (None, _labels_in_order(row, effective, c))
            and c.source_equivalent_pairs in (None, row.equivalent_pairs or None)
        )
        (unchanged if same else changed).append(key)
    return ImportDiff(
        proposed_mapping=proposed,
        unmatched_labels=(),
        added=tuple(sorted(incoming.keys() - current.keys())),
        removed=tuple(sorted(current.keys() - incoming.keys())),
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        table=table,
        incoming=incoming,
        current=current,
    )


def apply_import(
    project: Project,
    table: CouplingTable,
    confirmed_mapping: Mapping[str, str],
    orbit_of: OrbitOf | None = None,
) -> Project:
    """Replace the project's couplings with the imported ones, under a mapping the user confirmed.

    A pair already in the project keeps its coupling ID (a stable reference, D5). A new pair gets
    the next free ID. The imported labels are kept verbatim in ``source_labels``. With ``orbit_of``
    (a fixed-geometry model), a row of an observed pair orbit keeps that row's ID and takes the
    imported pair, and its class is the orbit (D-5).
    """
    _resolved(table, confirmed_mapping, project, orbit_of)  # validates the mapping and rejects duplicates
    current = _current(project, orbit_of)
    label_of = {s.id: s.label for s in project.molecule.spins}
    used = [int(c.id[4:]) for c in project.couplings]
    next_id = max(project.next_coupling_id, max(used, default=0) + 1)  # never reuse a number
    couplings = []
    for row in table.rows:  # file order
        a, b = confirmed_mapping[row.spin_a], confirmed_mapping[row.spin_b]
        source = (row.spin_a, row.spin_b)
        key = _pair_key(a, b) if orbit_of is None else orbit_of.of(a, b)[0]
        if key in current:
            cid = current[key].id
            if (current[key].spin_a, current[key].spin_b) == (b, a):  # keep the stored orientation
                a, b, source = b, a, (row.spin_b, row.spin_a)
        else:
            cid, next_id = f"cpl_{next_id:06d}", next_id + 1
        multiplicity, members = _incoming_class(row, confirmed_mapping, label_of, orbit_of)
        couplings.append(
            Coupling(
                id=cid,
                spin_a=a,
                spin_b=b,
                observable="D",
                value=Hertz(value=row.value_hz, unit="Hz"),
                sigma=Hertz(value=row.sigma_hz, unit="Hz"),
                sigma_source=row.sigma_source,
                multiplicity=multiplicity,
                equivalent_pairs=members,
                source_labels=source,
                source_equivalent_pairs=row.equivalent_pairs or None,
            )
        )
    return project.model_copy(update={"couplings": tuple(couplings), "next_coupling_id": next_id})


# --------------------------------------------------------------------------- project files (D6)
#: Upgrade steps: MIGRATIONS[v] turns a version-v document into version v + 1.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: lambda document: {**document, "project": _project_to(2, document["project"])},
    2: lambda document: {**document, "project": migrate_project(document["project"])},
}


def _project_to(version: int, project: Any) -> Any:
    """One step of ``migrate_project``: the v1 payload as v2 (the file migrates one version at a
    time, and its project with it)."""
    if not isinstance(project, dict):
        raise ValueError("the project must be a JSON object")
    upgraded = migrate_project(project)
    upgraded["schema_version"] = version
    return upgraded


def _json_depth_exceeds(text: str, limit: int) -> bool:
    """True if brackets nest deeper than ``limit`` outside strings: a bounded scan run before
    decoding, so a hostile file cannot exhaust the decoder's recursion (round 22)."""
    depth, in_string, escaped = 0, False, False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                return True
        elif ch in "]}":
            depth -= 1
    return False


def dumps_project(project: Project) -> str:
    """The ``*.dipolar.json`` text: a format tag, the schema version and the project."""
    document = {
        "format": PROJECT_FORMAT,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project": project.model_dump(mode="json"),
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def loads_project(text: str) -> Project:
    """Read a project file: bounded, strictly validated, migrated, and checked for consistency
    (``dipolar_app.science.validate_project``). A draft that is not yet fittable still loads."""
    from dipolar_app.schemas import MAX_JSON_DEPTH
    from dipolar_app.science import validate_project

    if len(text) > MAX_PROJECT_BYTES:
        raise FormatError(f"the file is larger than {MAX_PROJECT_BYTES} characters")
    if _json_depth_exceeds(text, MAX_JSON_DEPTH):
        raise FormatError(f"the file is nested deeper than {MAX_JSON_DEPTH} levels")
    try:
        document = json.loads(
            text, parse_constant=lambda c: (_ for _ in ()).throw(FormatError(f"non-finite number {c}"))
        )
    except json.JSONDecodeError as exc:
        raise FormatError(f"not valid JSON: {exc}") from None
    if not isinstance(document, dict) or document.get("format") != PROJECT_FORMAT:
        raise FormatError(f"not a project file: the 'format' field must be {PROJECT_FORMAT!r}")
    if (problem := wire_problem(document)) is not None:
        raise FormatError(f"the file cannot be read: {problem}")
    version = document.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise FormatError("schema_version must be a positive integer")
    if version > PROJECT_SCHEMA_VERSION:
        raise FormatError(f"the file uses schema {version}; this version reads up to {PROJECT_SCHEMA_VERSION}")
    if set(document) != {"format", "schema_version", "project"}:
        raise FormatError(
            f"unexpected top-level fields {sorted(set(document) - {'format', 'schema_version', 'project'})}"
        )
    while version < PROJECT_SCHEMA_VERSION:
        if version not in MIGRATIONS:
            raise FormatError(f"no migration from schema {version}")
        try:
            document = MIGRATIONS[version](document)
        except ValueError as exc:  # migrate_project's shape checks (round 28)
            raise FormatError(f"cannot migrate schema {version}: {exc}") from None
        version += 1
        document["schema_version"] = version
    project_data = document["project"]
    if not isinstance(project_data, dict) or project_data.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise FormatError("the project's own schema_version must match the file's")
    _normalize_default_masses(project_data)
    project = Project.model_validate_json(canonical_json(project_data), strict=True)
    try:
        validate_project(project)
    except ValueError as exc:
        from dipolar_app.science import refusal

        code, details = refusal(exc)
        raise FormatError(f"inconsistent project: {exc}", code, details) from None
    return project


def _normalize_default_masses(project_data: dict[str, Any]) -> None:
    """D-6: a default mass number written out (C-12, H-1) is the default isotope, spelled absent, so
    both spellings load to one identity (round 77). Anything else is left for validation."""
    molecule = project_data.get("molecule")
    geometry = molecule.get("geometry") if isinstance(molecule, dict) else None
    atoms = geometry.get("atoms") if isinstance(geometry, dict) else None
    if not isinstance(atoms, list):
        return
    for atom in atoms:
        if not isinstance(atom, dict) or not isinstance(atom.get("element"), str) or atom["element"] not in ISOTOPES:
            continue  # a malformed atom is the schema's to report (round 78)
        mass = atom.get("mass_number")
        if type(mass) is int and mass == ISOTOPES[atom["element"]][0]:
            del atom["mass_number"]


def project_from_xyz(
    molecule: XyzMolecule,
    *,
    name: str,
    source: str,
    torsion: tuple[int, int, int, int] | None,
    order: str = "c1",
    domain_deg: tuple[float, float] = (-180.0, 180.0),
    spin_labels: Mapping[int, str] | None = None,
) -> Project:
    """A project on imported coordinates, with one spin per hydrogen and no couplings yet.

    The spins are labelled ``spin_labels[atom]``, or "H<atom number>" (1-based, file order). Spin
    IDs follow file order. Couplings arrive through ``reconcile`` and ``apply_import``.
    """
    from dipolar_app.project import Atom, ImportedGeometry, ModelSpec, Molecule, Spin

    labels = dict(spin_labels or {})
    hydrogens = [i for i, e in enumerate(molecule.elements) if e == "H"]
    unknown = sorted(set(labels) - set(hydrogens))
    if unknown:
        raise FormatError(f"spin labels given for atoms that are not hydrogens: {unknown}")
    spins = tuple(
        Spin(id=f"spn_{n + 1:06d}", label=labels.get(atom, f"H{atom + 1}"), isotope="1H", atom=atom)
        for n, atom in enumerate(hydrogens)
    )
    if len({s.label for s in spins}) != len(spins):
        raise FormatError("spin labels must be unique")
    return Project(
        schema_version=3,
        name=name,
        source=source,
        molecule=Molecule(
            geometry=ImportedGeometry(
                source_format="xyz",
                atoms=tuple(
                    Atom(element=e, x=p[0], y=p[1], z=p[2])
                    for e, p in zip(molecule.elements, molecule.positions, strict=True)
                ),
                torsion=torsion,
            ),
            spins=spins,
        ),
        couplings=(),
        model=ModelSpec(kind="rigid", order=order, frame="input", phi_domain_deg=domain_deg),
    )
