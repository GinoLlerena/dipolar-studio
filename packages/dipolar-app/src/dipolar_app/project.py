"""The scientific project (D6, D14): science only, no view state. Canonical hash per D11."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection
from importlib import resources
from typing import Annotated, Any, Literal

from dipolar_core.context import numerical_context
from pydantic import Field

from dipolar_app.schemas import Angstrom, CouplingId, ExampleName, Hertz, SpinId, Wire

#: v2 (M1 step 4): the order model "diagonal-bisector" was renamed "bisector-diagonal"; imported
#: geometry, spin atoms, source labels, the model's kind/frame, and ``next_coupling_id`` were
#: added. ``migrate_project`` upgrades v1 documents, including those stored in journals.
PROJECT_SCHEMA_VERSION = 2

#: Size caps, enforced by the schema on every path (round 24). Bond perception is quadratic in the
#: atom count, so this cap bounds memory (about 24 MB at 1000 atoms).
MAX_ATOMS = 1_000
MAX_COUPLINGS = 100_000
MAX_CLASS_SIZE = 1_000


def split_pair_label(entry: str, labels: Collection[str]) -> tuple[str, str]:
    """Split an "A-B" pair label into two known labels; labels may contain hyphens themselves.

    Exactly one split must name two known labels: none, or more than one, is an error, never a
    guess (round 24). With labels a, b-c, a-b and c, "a-b-c" is ambiguous.
    """
    splits = [
        (entry[:k], entry[k + 1 :])
        for k, ch in enumerate(entry)
        if ch == "-" and entry[:k] in labels and entry[k + 1 :] in labels
    ]
    if not splits:
        raise ValueError(f"the pair label {entry!r} does not name two known spin labels")
    if len(splits) > 1:
        raise ValueError(f"the pair label {entry!r} is ambiguous: it splits as {splits}")
    return splits[0]


class Spin(Wire):
    id: SpinId
    label: str  # display only (D5)
    isotope: Literal["1H"]
    atom: Annotated[int, Field(ge=0)] | None = None  # index into imported atoms; None for the template


class BiphenylTemplate(Wire):
    template: Literal["biphenyl"]
    r_cc: Angstrom
    r_ch: Angstrom
    r_inter: Angstrom


#: Imported coordinates lie within ±MAX_COORD_A Å of the origin (round 36): molecules are a few Å
#: across, and the bound keeps every projection and auto-fitted camera numerically safe.
MAX_COORD_A = 1e4
Coordinate = Annotated[float, Field(ge=-MAX_COORD_A, le=MAX_COORD_A)]

#: Display labels in outputs are cut to this many characters (rounds 35–36): a label joined into
#: many outputs (a coupling's "A–B") never multiplies a long label's length.
MAX_LABEL_OUT = 64


def short(label: str) -> str:
    return label if len(label) <= MAX_LABEL_OUT else label[: MAX_LABEL_OUT - 1] + "…"


class Atom(Wire):
    element: Annotated[str, Field(min_length=1, max_length=2)]
    x: Coordinate  # Å, in the input frame (the frame of the order tensor)
    y: Coordinate
    z: Coordinate


class ImportedGeometry(Wire):
    """Coordinates from a file (XYZ). ``torsion`` names four atoms (a, i, j, b) whose IUPAC
    dihedral is the fitted angle (``dipolar_core.torsion``)."""

    source_format: Literal["xyz"]
    atoms: Annotated[tuple[Atom, ...], Field(min_length=1, max_length=MAX_ATOMS)]
    torsion: tuple[int, int, int, int] | None = None


class Molecule(Wire):
    geometry: BiphenylTemplate | ImportedGeometry
    spins: Annotated[tuple[Spin, ...], Field(max_length=MAX_ATOMS)]


class Coupling(Wire):
    id: CouplingId
    spin_a: SpinId
    spin_b: SpinId
    observable: Literal["D"]  # signed dipolar coupling (D7 beta scope)
    value: Hertz
    sigma: Hertz
    sigma_source: str
    multiplicity: Annotated[int, Field(ge=1)]  # symmetry copies; never inflates N (D3.3)
    #: The observation class, as "A-B" pairs of the project's spin labels (``split_pair_label``).
    equivalent_pairs: Annotated[tuple[str, ...], Field(max_length=MAX_CLASS_SIZE)]
    source_labels: tuple[str, str] | None = None  # the labels as imported, kept verbatim (D5)
    #: The class as imported, verbatim, when it was translated through a confirmed mapping.
    source_equivalent_pairs: Annotated[tuple[str, ...], Field(max_length=MAX_CLASS_SIZE)] | None = None


class ModelSpec(Wire):
    """The fitted model (``dipolar_core.biphenyl`` and ``dipolar_core.torsion``).

    - ``kind``: "rigid" (one conformer) or "jump4" (the symmetric four-site jump, template only).
    - ``order``: "bisector-diagonal" (legacy "D4"; template only), "c2z" (legacy "D2") or "c1".
    - ``frame``: "bisector" or "ring-a" for the template; "input" for imported coordinates.
    - ``phi_domain_deg``: the fitted torsion interval.
    """

    kind: Literal["rigid", "jump4"]
    order: Literal["bisector-diagonal", "c2z", "c1"]
    frame: Literal["bisector", "ring-a", "input"] = "bisector"
    phi_domain_deg: tuple[float, float]


class Project(Wire):
    schema_version: Literal[2]
    name: str
    source: str
    molecule: Molecule
    couplings: Annotated[tuple[Coupling, ...], Field(max_length=MAX_COUPLINGS)]
    model: ModelSpec
    #: The next coupling number to assign. It only grows, so a deleted coupling's ID is never
    #: given to a different observation (D5, round 22).
    next_coupling_id: Annotated[int, Field(ge=1)] = 1

    def spin(self, spin_id: str) -> Spin | None:
        return next((s for s in self.molecule.spins if s.id == spin_id), None)

    def coupling(self, coupling_id: str) -> Coupling | None:
        return next((c for c in self.couplings if c.id == coupling_id), None)

    def label_of(self, object_id: str) -> tuple[str, str] | None:
        """Return (kind, display label) for a spin or coupling ID, or None if absent."""
        if (s := self.spin(object_id)) is not None:
            return "spin", short(s.label)
        if (c := self.coupling(object_id)) is not None:
            return "coupling", self.coupling_label(c)
        return None

    def coupling_label(self, c: Coupling) -> str:
        a, b = self.spin(c.spin_a), self.spin(c.spin_b)
        return f"{short(a.label) if a else c.spin_a}–{short(b.label) if b else c.spin_b}"


def canonical_json(data: Any) -> str:
    """Canonical JSON used for hashes and checksums (sorted keys, no whitespace, exact floats)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def science_hash(project: Project | None) -> str:
    """Canonical science identity: the project plus the core's numerical context (D11)."""
    return payload_hash(None if project is None else project.model_dump(mode="json"))


def payload_hash(project_payload: dict[str, Any] | None) -> str:
    """``science_hash`` of a stored project payload as it was written, at any schema version."""
    payload = {"numerical_context": numerical_context(), "project": project_payload}
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def migrate_project(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a stored project payload to ``PROJECT_SCHEMA_VERSION``, one version at a time.

    A newer version is refused. The input is not modified.
    """
    if not isinstance(data, dict):
        raise ValueError("the project must be a JSON object")
    data = json.loads(json.dumps(data))
    version = data.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= PROJECT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported project schema_version {version!r} (this version reads 1–{PROJECT_SCHEMA_VERSION})"
        )
    if version == 1:
        # Shapes are checked before they are used: a malformed old document is a clear error, never
        # an internal one (round 28). Full validation follows the migration.
        if not isinstance(data.get("couplings", []), list):
            raise ValueError("couplings must be a list")
        if not isinstance(data.get("model", {}), dict):
            raise ValueError("model must be a JSON object")
        model = data.get("model")
        if isinstance(model, dict) and model.get("order") == "diagonal-bisector":
            model["order"] = "bisector-diagonal"
        numbers = [
            int(c["id"][4:])
            for c in data.get("couplings", ())
            if isinstance(c, dict) and str(c.get("id", "")).startswith("cpl_")
        ]
        data["next_coupling_id"] = max(numbers, default=0) + 1
        data["schema_version"] = 2
    return data


def load_example(name: ExampleName) -> Project:
    """Build a project from a bundled example. IDs are assigned here, in file order."""
    raw = json.loads(resources.files("dipolar_app.examples").joinpath(f"{name}.json").read_text(encoding="utf-8"))
    labels = raw["spins"]
    spin_ids = {label: f"spn_{i + 1:06d}" for i, label in enumerate(labels)}
    geometry = raw["geometry_A"]
    couplings = tuple(
        Coupling(
            id=f"cpl_{i + 1:06d}",
            spin_a=spin_ids[row["spin_a"]],
            spin_b=spin_ids[row["spin_b"]],
            observable="D",
            value=Hertz(value=row["D_obs_Hz"], unit="Hz"),
            sigma=Hertz(value=row["sigma_Hz"], unit="Hz"),
            sigma_source=raw["sigma_source"],
            multiplicity=row["multiplicity"],
            equivalent_pairs=tuple(row["equivalent_pairs"]),
        )
        for i, row in enumerate(raw["couplings"])
    )
    return Project(
        schema_version=2,
        next_coupling_id=len(couplings) + 1,
        name=raw["name"],
        source=raw["source"],
        molecule=Molecule(
            geometry=BiphenylTemplate(
                template="biphenyl",
                r_cc=Angstrom(value=geometry["r_cc"], unit="Å"),
                r_ch=Angstrom(value=geometry["r_ch"], unit="Å"),
                r_inter=Angstrom(value=geometry["r_inter"], unit="Å"),
            ),
            spins=tuple(Spin(id=spin_ids[label], label=label, isotope="1H") for label in labels),
        ),
        couplings=couplings,
        model=ModelSpec(kind="rigid", order="bisector-diagonal", phi_domain_deg=(0.0, 90.0)),
    )
