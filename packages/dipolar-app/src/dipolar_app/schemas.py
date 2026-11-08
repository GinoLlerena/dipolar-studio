"""Shared wire types: units are explicit, IDs are typed, unknown fields are rejected (04 D13, §8.5)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Wire(BaseModel):
    """Base for every input and output model: strict shape, immutable, finite floats only."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Degrees(Wire):
    value: float
    unit: Literal["deg"]


class Hertz(Wire):
    value: float
    unit: Literal["Hz"]


class Angstrom(Wire):
    value: Annotated[float, Field(gt=0)]
    unit: Literal["Å"]


def deg(value: float) -> Degrees:
    return Degrees(value=value, unit="deg")


def hz(value: float) -> Hertz:
    return Hertz(value=value, unit="Hz")


#: Stable IDs (plan D5). Labels are for display only and never used as references.
SpinId = Annotated[str, StringConstraints(pattern=r"^spn_[0-9]{6}$")]
CouplingId = Annotated[str, StringConstraints(pattern=r"^cpl_[0-9]{6}$")]
ObjectId = Annotated[str, StringConstraints(pattern=r"^(spn|cpl)_[0-9]{6}$")]

ExampleName = Literal["biphenyl-synthetic"]

#: Integers on the wire stay within ±(2⁵³ − 1), so a JavaScript client reads them exactly.
MAX_SAFE_INTEGER = 2**53 - 1
Revision = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
