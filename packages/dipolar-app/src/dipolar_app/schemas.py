"""Shared wire types: units are explicit, IDs are typed, unknown fields are rejected (04 D13, §8.5)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

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

#: Deepest JSON nesting accepted from any adapter (the contract itself needs fewer than ten levels).
MAX_JSON_DEPTH = 64


def _valid_unicode(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:  # an unpaired surrogate, e.g. from the JSON escape "\\ud800"
        return False
    return True


def wire_problem(value: Any) -> str | None:
    """Why ``value`` cannot travel as contract JSON (too deep, or invalid Unicode), or None.

    Iterative, so a hostile document cannot exhaust the stack; the depth bound also stops cycles.
    """
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            return f"nested deeper than {MAX_JSON_DEPTH} levels"
        if isinstance(item, str):
            if not _valid_unicode(item):
                return "a string is not valid Unicode (unpaired surrogate)"
        elif isinstance(item, dict):
            for key, child in item.items():
                if isinstance(key, str) and not _valid_unicode(key):
                    return "a key is not valid Unicode (unpaired surrogate)"
                stack.append((child, depth + 1))
        elif isinstance(item, list | tuple):
            stack.extend((child, depth + 1) for child in item)
    return None
