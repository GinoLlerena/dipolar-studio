"""File formats and import reconciliation (plan D5, D6; ADR-0005, ADR-0006; M1 step 4).

- **XYZ** (``parse_xyz``): an atom count, a comment line, then one line per atom with
  "element x y z" in Å. The parser is strict: every problem is an error with its line number,
  and nothing is guessed.
- **Couplings CSV** (``parse_couplings_csv``):
  - required columns: spin_a, spin_b, D_obs_Hz, sigma_Hz;
  - optional columns: sigma_source, multiplicity, equivalent_pairs (space-separated),
    observable (only "D"), unit (only "Hz");
  - unknown columns are reported, not silently used.
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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from dipolar_app.project import PROJECT_SCHEMA_VERSION, Coupling, Project, canonical_json
from dipolar_app.schemas import Hertz, wire_problem

PROJECT_FORMAT: Final = "dipolar-studio-project"
MAX_ATOMS: Final = 10_000
MAX_COUPLINGS: Final = 100_000
REQUIRED_COLUMNS: Final = ("spin_a", "spin_b", "D_obs_Hz", "sigma_Hz")
OPTIONAL_COLUMNS: Final = ("sigma_source", "multiplicity", "equivalent_pairs", "observable", "unit")
ELEMENTS: Final = frozenset({"H", "D", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"})


class FormatError(ValueError):
    """A file that does not follow its format; the message names the line or row."""


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
    try:
        n = int(lines[0].strip())
    except ValueError:
        raise FormatError(f"line 1: the atom count must be an integer, got {lines[0].strip()!r}") from None
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
        try:
            xyz = tuple(float(v) for v in fields[1:])
        except ValueError:
            raise FormatError(f"line {number}: coordinates must be numbers, got {fields[1:]}") from None
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
    multiplicity: int
    equivalent_pairs: tuple[str, ...]


@dataclass(frozen=True)
class CouplingTable:
    rows: tuple[CouplingRow, ...]
    ignored_columns: tuple[str, ...]


def _number(text: str, what: str, row: int) -> float:
    try:
        value = float(text)
    except ValueError:
        raise FormatError(f"row {row}: {what} must be a number, got {text!r}") from None
    if not math.isfinite(value):
        raise FormatError(f"row {row}: {what} must be finite")
    return value


def parse_couplings_csv(text: str, *, default_sigma_source: str = "not stated") -> CouplingTable:
    reader = csv.DictReader(io.StringIO(text))
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
        a, b = raw["spin_a"].strip(), raw["spin_b"].strip()
        if not a or not b:
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
        multiplicity_text = raw.get("multiplicity", "").strip() or "1"
        if not multiplicity_text.isdigit() or int(multiplicity_text) < 1:
            raise FormatError(f"row {number}: multiplicity must be a positive integer")
        rows.append(
            CouplingRow(
                row=number,
                spin_a=a,
                spin_b=b,
                value_hz=_number(raw["D_obs_Hz"], "D_obs_Hz", number),
                sigma_hz=sigma,
                sigma_source=raw.get("sigma_source", "").strip() or default_sigma_source,
                multiplicity=int(multiplicity_text),
                equivalent_pairs=tuple(raw.get("equivalent_pairs", "").split()),
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
    added: tuple[tuple[str, str], ...] = ()  # spin-ID pairs new to the project
    removed: tuple[tuple[str, str], ...] = ()  # pairs present now and absent from the import
    changed: tuple[tuple[str, str], ...] = ()  # pairs whose value, σ or source differs
    unchanged: tuple[tuple[str, str], ...] = ()
    table: CouplingTable | None = field(default=None, repr=False)


def _pair_key(a: str, b: str) -> tuple[str, str]:
    """D is symmetric in its two spins, so a reversed pair is the same observation."""
    return (a, b) if a <= b else (b, a)


def _resolved(table: CouplingTable, mapping: Mapping[str, str], project: Project) -> dict[tuple[str, str], CouplingRow]:
    spin_ids = {s.id for s in project.molecule.spins}
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
        key = _pair_key(ids[0], ids[1])
        if key in out:
            raise FormatError(
                f"row {row.row}: the pair {row.spin_a}–{row.spin_b} repeats row {out[key].row} "
                "(merge symmetry copies into one row with a multiplicity)"
            )
        out[key] = row
    return out


def reconcile(table: CouplingTable, project: Project, mapping: Mapping[str, str] | None = None) -> ImportDiff:
    """Propose a mapping (exact label matches only) and, if every label is mapped, the diff."""
    labels = sorted({label for row in table.rows for label in (row.spin_a, row.spin_b)})
    by_label: dict[str, list[str]] = {}
    for s in project.molecule.spins:
        by_label.setdefault(s.label, []).append(s.id)
    proposed = {label: by_label[label][0] for label in labels if len(by_label.get(label, ())) == 1}
    effective = dict(mapping) if mapping is not None else proposed
    unmatched = tuple(label for label in labels if label not in effective)
    if unmatched:
        return ImportDiff(proposed, unmatched, table=table)
    incoming = _resolved(table, effective, project)
    current = {_pair_key(c.spin_a, c.spin_b): c for c in project.couplings}
    changed: list[tuple[str, str]] = []
    unchanged: list[tuple[str, str]] = []
    for key in sorted(incoming.keys() & current.keys()):
        row, c = incoming[key], current[key]
        same = (row.value_hz, row.sigma_hz, row.sigma_source) == (c.value.value, c.sigma.value, c.sigma_source)
        (unchanged if same else changed).append(key)
    return ImportDiff(
        proposed_mapping=proposed,
        unmatched_labels=(),
        added=tuple(sorted(incoming.keys() - current.keys())),
        removed=tuple(sorted(current.keys() - incoming.keys())),
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        table=table,
    )


def apply_import(project: Project, table: CouplingTable, confirmed_mapping: Mapping[str, str]) -> Project:
    """Replace the project's couplings with the imported ones, under a mapping the user confirmed.

    A pair already in the project keeps its coupling ID (a stable reference, D5). A new pair gets
    the next free ID. The imported labels are kept verbatim in ``source_labels``.
    """
    _resolved(table, confirmed_mapping, project)  # validates the mapping and rejects duplicates
    current = {_pair_key(c.spin_a, c.spin_b): c.id for c in project.couplings}
    used = [int(c.id[4:]) for c in project.couplings]
    next_id = max(used, default=0) + 1
    couplings = []
    for row in table.rows:  # file order
        a, b = confirmed_mapping[row.spin_a], confirmed_mapping[row.spin_b]
        key = _pair_key(a, b)
        if key in current:
            cid = current[key]
        else:
            cid, next_id = f"cpl_{next_id:06d}", next_id + 1
        couplings.append(
            Coupling(
                id=cid,
                spin_a=a,
                spin_b=b,
                observable="D",
                value=Hertz(value=row.value_hz, unit="Hz"),
                sigma=Hertz(value=row.sigma_hz, unit="Hz"),
                sigma_source=row.sigma_source,
                multiplicity=row.multiplicity,
                equivalent_pairs=row.equivalent_pairs,
                source_labels=(row.spin_a, row.spin_b),
            )
        )
    return project.model_copy(update={"couplings": tuple(couplings)})


# --------------------------------------------------------------------------- project files (D6)
#: Upgrade steps: MIGRATIONS[v] turns a version-v document into version v + 1.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def dumps_project(project: Project) -> str:
    """The ``*.dipolar.json`` text: a format tag, the schema version and the project."""
    document = {
        "format": PROJECT_FORMAT,
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project": project.model_dump(mode="json"),
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def loads_project(text: str) -> Project:
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
        document = MIGRATIONS[version](document)
        version += 1
        document["schema_version"] = version
    project_data = document["project"]
    if not isinstance(project_data, dict) or project_data.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise FormatError("the project's own schema_version must match the file's")
    return Project.model_validate_json(canonical_json(project_data), strict=True)


def project_from_xyz(
    molecule: XyzMolecule,
    *,
    name: str,
    source: str,
    torsion: tuple[int, int, int, int],
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
        schema_version=1,
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
