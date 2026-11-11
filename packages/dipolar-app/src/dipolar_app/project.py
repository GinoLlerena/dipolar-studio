"""The scientific project (D6, D14): science only, no view state. Canonical hash per D11."""

from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Annotated, Any, Literal

from dipolar_core.context import numerical_context
from pydantic import Field

from dipolar_app.schemas import Angstrom, CouplingId, ExampleName, Hertz, SpinId, Wire

PROJECT_SCHEMA_VERSION = 1


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


class Atom(Wire):
    element: Annotated[str, Field(min_length=1, max_length=2)]
    x: float  # Å, in the input frame (the frame of the order tensor)
    y: float
    z: float


class ImportedGeometry(Wire):
    """Coordinates from a file (XYZ). ``torsion`` names four atoms (a, i, j, b) whose IUPAC
    dihedral is the fitted angle (``dipolar_core.torsion``)."""

    source_format: Literal["xyz"]
    atoms: tuple[Atom, ...]
    torsion: tuple[int, int, int, int] | None = None


class Molecule(Wire):
    geometry: BiphenylTemplate | ImportedGeometry
    spins: tuple[Spin, ...]


class Coupling(Wire):
    id: CouplingId
    spin_a: SpinId
    spin_b: SpinId
    observable: Literal["D"]  # signed dipolar coupling (D7 beta scope)
    value: Hertz
    sigma: Hertz
    sigma_source: str
    multiplicity: Annotated[int, Field(ge=1)]  # symmetry copies; never inflates N (D3.3)
    equivalent_pairs: tuple[str, ...]  # display labels, data only
    source_labels: tuple[str, str] | None = None  # the labels as imported, kept verbatim (D5)


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
    schema_version: Literal[1]
    name: str
    source: str
    molecule: Molecule
    couplings: tuple[Coupling, ...]
    model: ModelSpec

    def spin(self, spin_id: str) -> Spin | None:
        return next((s for s in self.molecule.spins if s.id == spin_id), None)

    def coupling(self, coupling_id: str) -> Coupling | None:
        return next((c for c in self.couplings if c.id == coupling_id), None)

    def label_of(self, object_id: str) -> tuple[str, str] | None:
        """Return (kind, display label) for a spin or coupling ID, or None if absent."""
        if (s := self.spin(object_id)) is not None:
            return "spin", s.label
        if (c := self.coupling(object_id)) is not None:
            return "coupling", self.coupling_label(c)
        return None

    def coupling_label(self, c: Coupling) -> str:
        a, b = self.spin(c.spin_a), self.spin(c.spin_b)
        return f"{a.label if a else c.spin_a}–{b.label if b else c.spin_b}"


def canonical_json(data: Any) -> str:
    """Canonical JSON used for hashes and checksums (sorted keys, no whitespace, exact floats)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def science_hash(project: Project | None) -> str:
    """Canonical science identity: the project plus the core's numerical context (D11)."""
    payload = {
        "numerical_context": numerical_context(),
        "project": None if project is None else project.model_dump(mode="json"),
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def load_example(name: ExampleName) -> Project:
    """Build a project from a bundled example. IDs are assigned here, in file order."""
    raw = json.loads(resources.files("dipolar_app.examples").joinpath(f"{name}.json").read_text("utf-8"))
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
        schema_version=1,
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
