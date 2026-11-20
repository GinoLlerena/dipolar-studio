"""The scientific project (D6, D14): science only, no view state. Canonical hash per D11."""

from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import threading
from collections.abc import Callable, Collection, Iterator
from importlib import resources
from typing import Annotated, Any, Literal

from dipolar_core.context import numerical_context
from pydantic import Field, StrictInt

from dipolar_app.schemas import Angstrom, CouplingId, ExampleName, Hertz, SpinId, Wire

#: v2 (M1 step 4): the order model "diagonal-bisector" was renamed "bisector-diagonal"; imported
#: geometry, spin atoms, source labels, the model's kind/frame, and ``next_coupling_id`` were
#: added. ``migrate_project`` upgrades v1 documents.
#: v3 (Phase 2 V1.3): an atom's mass number, the molecule's declared symmetry, and the model kind
#: "fixed" (order "point-group", frame "symmetry", no torsion domain). Every v2 document is a v3
#: document with the version changed. Only export files are migrated: a 0.1 project directory is
#: never opened (D-1), so no journal record or snapshot is ever migrated.
PROJECT_SCHEMA_VERSION = 3

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


def _absent(value: object) -> bool:
    return value is None


class Atom(Wire):
    element: Annotated[str, Field(min_length=1, max_length=2)]
    x: Coordinate  # Å, in the input frame (the frame of the order tensor)
    y: Coordinate
    z: Coordinate
    #: The isotope (D-6): absent for the element's default; one spelling per identity, so a default
    #: written out is refused on load (``dipolar_core.symmetry.ISOTOPES``). Strict integers only.
    mass_number: Annotated[StrictInt, Field(ge=1, le=999)] | None = Field(default=None, exclude_if=_absent)


class ImportedGeometry(Wire):
    """Coordinates from a file (XYZ). ``torsion`` names four atoms (a, i, j, b) whose IUPAC
    dihedral is the fitted angle (``dipolar_core.torsion``)."""

    source_format: Literal["xyz"]
    atoms: Annotated[tuple[Atom, ...], Field(min_length=1, max_length=MAX_ATOMS)]
    torsion: tuple[int, int, int, int] | None = None


Axis = tuple[float, float, float]


class SymmetrySpec(Wire):
    """A declared point group (D-4), validated against the geometry by ``dipolar_core.symmetry``.

    The point group and medium are kept as written, so an unsupported one is refused with its own
    code (``POINT_GROUP_NOT_SUPPORTED``, ``MEDIUM_NOT_SUPPORTED``), never as a malformed field.
    """

    point_group: Annotated[str, Field(min_length=1, max_length=16)]
    axes: tuple[Axis, Axis, Axis]  # rows x, y, z of the symmetry frame, in input coordinates
    tolerance: Angstrom
    medium: Annotated[str, Field(min_length=1, max_length=64)]


class Molecule(Wire):
    geometry: BiphenylTemplate | ImportedGeometry
    spins: Annotated[tuple[Spin, ...], Field(max_length=MAX_ATOMS)]
    #: Imported geometry without a torsion only (D-3); required by the fixed-geometry model.
    symmetry: SymmetrySpec | None = Field(default=None, exclude_if=_absent)


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
    """The fitted model (``dipolar_core.biphenyl``, ``dipolar_core.torsion``, ``dipolar_core.fixed``).

    - ``kind``: "rigid" (one conformer), "jump4" (the symmetric four-site jump, template only) or
      "fixed" (imported geometry with no torsion: the order tensor alone, D-3).
    - ``order``: "bisector-diagonal" (legacy "D4"; template only), "c2z" (legacy "D2"), "c1", or
      "point-group" (fixed: the declared symmetry restricts the tensor).
    - ``frame``: "bisector" or "ring-a" for the template; "input" for imported coordinates;
      "symmetry" (fixed: the declared symmetry frame).
    - ``phi_domain_deg``: the fitted torsion interval; absent for "fixed", required otherwise.
    """

    kind: Literal["rigid", "jump4", "fixed"]
    order: Literal["bisector-diagonal", "c2z", "c1", "point-group"]
    frame: Literal["bisector", "ring-a", "input", "symmetry"] = "bisector"
    phi_domain_deg: tuple[float, float] | None = Field(default=None, exclude_if=_absent)


class Project(Wire):
    schema_version: Literal[3]
    name: str
    source: str
    molecule: Molecule
    couplings: Annotated[tuple[Coupling, ...], Field(max_length=MAX_COUPLINGS)]
    model: ModelSpec
    #: The next coupling number to assign. It only grows, so a deleted coupling's ID is never
    #: given to a different observation (D5, round 22).
    next_coupling_id: Annotated[int, Field(ge=1)] = 1

    def spin(self, spin_id: str) -> Spin | None:
        """By ID, through an index kept per project object (round 78: no scan of the spins per row)."""
        index: dict[str, Spin] = _SPIN_INDEX.get(self, lambda: {s.id: s for s in self.molecule.spins})
        return index.get(spin_id)

    def coupling(self, coupling_id: str) -> Coupling | None:
        index: dict[str, Coupling] = _COUPLING_INDEX.get(self, lambda: {c.id: c for c in self.couplings})
        return index.get(coupling_id)

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


class ByIdentity:
    """A small cache keyed by object identity, for values derived from an immutable object (a
    frozen project). It holds the objects it has seen, so their ids are never reused while cached.
    Large projects pay for these values on every call otherwise (M3 step 4b: 0.6 s for the hash
    and 0.85 s for validation at 45 000 couplings, per call). ``tag`` is anything else the value
    depends on, compared by equality (the hashes cover the numerical context too)."""

    def __init__(self, size: int = 4) -> None:
        self._size = size
        self._entries: list[tuple[object, object, Any]] = []
        self._lock = threading.Lock()

    def get(self, key: object, compute: Callable[[], Any], tag: object = None) -> Any:
        with self._lock:
            for seen, seen_tag, value in self._entries:
                if seen is key and seen_tag == tag:
                    return value
        value = compute()  # outside the lock; a race only computes the same value twice
        with self._lock:
            self._entries.insert(0, (key, tag, value))
            del self._entries[self._size :]
        return value


_SCIENCE_HASHES = ByIdentity()
_SPIN_INDEX = ByIdentity()
_COUPLING_INDEX = ByIdentity()
_CONTENT_HASHES = ByIdentity()


def science_hash(project: Project | None) -> str:
    """Canonical science identity: the project plus the core's numerical context (D11)."""
    if project is None:
        return payload_hash(None)
    value: str = _SCIENCE_HASHES.get(
        project, lambda: payload_hash(project.model_dump(mode="json")), tag=numerical_context()
    )
    return value


def content_hash(project: Project | None) -> str:
    """The science content alone, for staleness: ``science_hash`` without the coupling-ID
    allocator. The allocator is bookkeeping that never reaches a fit, and undo deliberately keeps
    it advanced (a coupling ID is never handed out twice), so an undo that restores a run's exact
    input restores this hash, though not ``science_hash`` (M3 step 2, the owner's decision)."""
    if project is None:
        return payload_hash(None)

    def compute() -> str:
        payload = project.model_dump(mode="json")
        payload.pop("next_coupling_id", None)
        return payload_hash(payload)

    value: str = _CONTENT_HASHES.get(project, compute, tag=numerical_context())
    return value


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
        data["schema_version"] = version = 2
    if version == 2:
        data["schema_version"] = 3  # v3 only adds optional fields and the model kind "fixed"
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
        schema_version=3,
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


_GC_LOCK = threading.Lock()
_GC_PAUSES = 0
_GC_WAS_ENABLED = False


@contextlib.contextmanager
def paused_gc() -> Iterator[None]:
    """Pause the cyclic garbage collector during a bounded computation over many small objects (a
    20 000-row fixed fit or import: the collector took about 40 % of the time; round 77). Reference
    counting still frees memory; the collector resumes, and runs, when the last pause ends. Pauses
    nest across threads: the collector's state is restored only by the last one."""
    global _GC_PAUSES, _GC_WAS_ENABLED
    with _GC_LOCK:
        if _GC_PAUSES == 0:
            _GC_WAS_ENABLED = gc.isenabled()
        gc.disable()  # also when an outside call re-enabled it during an enclosing pause
        _GC_PAUSES += 1
    try:
        yield
    finally:
        with _GC_LOCK:
            _GC_PAUSES -= 1
            if _GC_PAUSES == 0:  # the outermost pause restores the state it recorded (round 78)
                (gc.enable if _GC_WAS_ENABLED else gc.disable)()
