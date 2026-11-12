"""The web client's TypeScript contract is generated from the registry snapshot (M2 step 1b, D13).

The committed files must equal the generator's output (CI fails if they are stale), and the
generator must fail closed on any schema feature it cannot represent exactly. The TypeScript side
(web/src/contract.typetest.ts) checks with `tsc` that the generated types reject what the schema
rejects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "codegen"))

import ts_contract  # noqa: E402
from ts_contract import Unsupported, generate, generate_conformance  # noqa: E402

SNAPSHOT = json.loads(ts_contract.SNAPSHOT.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- the committed files
def test_committed_contract_is_current() -> None:
    assert ts_contract.OUTPUT.read_text(encoding="utf-8") == generate(SNAPSHOT), (
        "web/src/generated/contract.ts is stale; run: uv run python tools/codegen/ts_contract.py"
    )
    assert ts_contract.CONFORMANCE.read_text(encoding="utf-8") == generate_conformance(SNAPSHOT), (
        "web/src/generated/conformance.ts is stale; run: uv run python tools/codegen/ts_contract.py"
    )


def test_contract_follows_the_live_registry() -> None:
    """The chain registry → snapshot → TypeScript, end to end (the snapshot test covers step one)."""
    from dipolar_app.operations import build_registry

    live = json.loads(json.dumps(build_registry().snapshot()))
    assert generate(live) == ts_contract.OUTPUT.read_text(encoding="utf-8")


def test_every_operation_and_definition_is_emitted() -> None:
    text = generate(SNAPSHOT)
    assert f'export const CONTRACT_VERSION = "{SNAPSHOT["contract_version"]}";' in text
    for op in SNAPSHOT["operations"]:
        name, inp, out = op["name"], op["input_schema"]["title"], op["output_schema"]["title"]
        assert f'  "{name}": {{ input: {inp}; output: {out} }};' in text
        assert f"export type {inp} = " in text and f"export type {out} = " in text
        assert f'  "{name}": {{ kind: "{op["kind"]}", ' in text
        assert f"max_request_bytes: {op['max_request_bytes']} }}," in text
        for definition in op["input_schema"].get("$defs", {}) | op["output_schema"].get("$defs", {}):
            assert f"export type {definition} = " in text or definition == "JsonValue"
    codes = SNAPSHOT["envelopes"]["error"]["$defs"]["ErrorCode"]["enum"]
    assert "export type ErrorCode = " + " | ".join(json.dumps(c) for c in codes) + ";" in text


def test_every_example_is_type_checked() -> None:
    text = generate_conformance(SNAPSHOT)
    n = sum(len(op["examples"]) for op in SNAPSHOT["operations"])
    assert n > 0 and text.count(" satisfies OperationInput<") == n


def test_generation_is_deterministic_and_does_not_mutate_the_snapshot() -> None:
    before = json.dumps(SNAPSHOT, sort_keys=True)
    assert generate(SNAPSHOT) == generate(json.loads(before))
    assert json.dumps(SNAPSHOT, sort_keys=True) == before


def test_check_mode_reports_stale_files(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(SNAPSHOT), encoding="utf-8")
    out = tmp_path / "generated" / "contract.ts"
    args = ["--snapshot", str(snapshot), "--output", str(out)]
    assert ts_contract.main([*args, "--check"]) == 1  # missing
    assert ts_contract.main(args) == 0
    assert ts_contract.main([*args, "--check"]) == 0
    (tmp_path / "generated" / "conformance.ts").write_text("// edited\n", encoding="utf-8")
    assert ts_contract.main([*args, "--check"]) == 1  # either file stale fails


# --------------------------------------------------------------------------- the renderer
def _snapshot(input_schema: dict[str, Any], output_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """A minimal snapshot: the real envelopes and one operation with the given schemas."""
    return {
        "contract_version": "9.9.9",
        "envelopes": SNAPSHOT["envelopes"],
        "operations": [
            {
                "name": "probe.op",
                "kind": "query",
                "effect": "none",
                "capability": "query",
                "summary": "A probe.",
                "cost": "instant",
                "idempotent": True,
                "revision_check": "none",
                "max_request_bytes": 1024,
                "examples": [],
                "input_schema": {"title": "ProbeIn", **input_schema},
                "output_schema": output_schema
                or {"title": "ProbeOut", "type": "object", "additionalProperties": False},
            }
        ],
    }


def _render(input_schema: dict[str, Any]) -> str:
    text = generate(_snapshot(input_schema))
    start = text.index("export type ProbeIn = ")
    return text[start : text.index(";\n\n", start) + 1]


def _obj(props: dict[str, Any], required: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or list(props), **extra}


def test_required_and_optional_properties() -> None:
    out = _render(_obj({"a": {"type": "integer"}, "b": {"type": "string", "default": "x"}}, ["a"]))
    assert "  /** integer */\n  a: number;" in out
    assert '  /** default "x" */\n  b?: string;' in out
    assert "[key: string]" not in out.replace("[key: string]: JsonValue", "")  # open object below


def test_closed_and_open_objects() -> None:
    assert _render({"type": "object", "additionalProperties": False}) == (
        "export type ProbeIn = { [key: string]: never };"
    )
    # An open object (no additionalProperties) keeps any JSON value under other keys.
    assert "  [key: string]: JsonValue;" in _render(_obj({"a": {"type": "string"}}))
    record = _render({"type": "object", "additionalProperties": {"type": "number"}})
    assert record == "export type ProbeIn = { [key: string]: number };"
    # Named properties beside a typed index signature cannot be expressed exactly (round 29,
    # finding 1): the signature would have to admit the named types under every other key.
    with pytest.raises(Unsupported, match="typed additionalProperties beside named properties"):
        _render(_obj({"a": {"type": "string"}}, additionalProperties={"type": "number"}))


def test_literals_unions_and_arrays() -> None:
    out = _render(
        _obj(
            {
                "c": {"const": "deg"},
                "e": {"enum": ["x", "y", 3, None]},
                "n": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "t": {"type": ["string", "null"]},
                "l": {"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "number"}]}},
                "p": {
                    "type": "array",
                    "prefixItems": [{"type": "integer"}, {"type": "string"}],
                    "minItems": 2,
                    "maxItems": 2,
                },
                "j": {},
            },
            additionalProperties=False,
        )
    )
    assert '  c: "deg";' in out
    assert '  e: "x" | "y" | 3 | null;' in out
    assert "  n: string | null;" in out and "  t: string | null;" in out
    assert "  l: (string | number)[];" in out
    assert "  p: [number, string];" in out
    assert "  j: JsonValue;" in out


def test_const_and_enum_keep_a_matching_type() -> None:
    out = _render(
        _obj(
            {"c": {"const": "deg", "type": "string"}, "i": {"enum": [1, 2.0], "type": "integer"}},
            additionalProperties=False,
        )
    )
    assert '  c: "deg";' in out and "  i: 1 | 2;" in out


def test_unions_of_closed_objects_are_exclusive() -> None:
    """Round 29, finding 2: each closed branch forbids the other branches' keys."""
    left = _obj({"kind": {"const": "l"}, "a": {"type": "integer"}}, additionalProperties=False)
    right = _obj({"kind": {"const": "r"}, "b": {"type": "string"}}, additionalProperties=False)
    out = _render(_obj({"u": {"anyOf": [left, right, {"type": "null"}]}}, additionalProperties=False))
    assert "& { b?: never })" in out and "& { a?: never })" in out and out.rstrip(";").endswith("| null;\n}")
    # Through references too, and a branch accepting any JSON value makes the union JsonValue.
    via_refs = _snapshot(
        {**_obj({"u": {"anyOf": [{"$ref": "#/$defs/L"}, {"$ref": "#/$defs/R"}]}}), "$defs": {"L": left, "R": right}}
    )
    assert "u: (L & { b?: never }) | (R & { a?: never });" in generate(via_refs)
    assert "  u: JsonValue;" in _render(_obj({"u": {"anyOf": [left, {}]}}))


def test_real_pydantic_models() -> None:
    """The reviewer's round-29 models, from Pydantic itself rather than hand-written schemas."""
    from typing import Annotated, Literal

    from pydantic import BaseModel, ConfigDict, Field

    class TypedExtra(BaseModel):
        model_config = ConfigDict(extra="allow")
        label: str
        __pydantic_extra__: dict[str, int] = Field(init=False)

    with pytest.raises(Unsupported, match="typed additionalProperties"):
        generate(_snapshot(TypedExtra.model_json_schema()))

    class Left(BaseModel):
        model_config = ConfigDict(extra="forbid")
        a: int

    class Right(BaseModel):
        model_config = ConfigDict(extra="forbid")
        b: str

    class UnionIn(BaseModel):
        model_config = ConfigDict(extra="forbid")
        choice: Left | Right

    assert "choice: (Left & { b?: never }) | (Right & { a?: never });" in generate(
        _snapshot(UnionIn.model_json_schema())
    )

    class Cat(BaseModel):
        kind: Literal["cat"]

    class Dog(BaseModel):
        kind: Literal["dog"]

    class Discriminated(BaseModel):
        pet: Annotated[Cat | Dog, Field(discriminator="kind")]

    with pytest.raises(Unsupported, match="unsupported keyword"):
        generate(_snapshot(Discriminated.model_json_schema()))

    class Optional(BaseModel):
        model_config = ConfigDict(extra="forbid")
        optional: str | None = None
        required_nullable: str | None
        pair: tuple[int, str]
        mapping: dict[str, str | int]

    out = generate(_snapshot(Optional.model_json_schema()))
    for line in ("optional?: string | null;", "required_nullable: string | null;", "pair: [number, string];"):
        assert line in out
    assert "mapping: { [key: string]: string | number };" in out


def test_recursive_definitions_are_refused() -> None:
    """Round 30, finding 2: Exact walks the argument type, so a recursive definition is refused
    (JsonValue, built in, is the one recursive type and ends the walk)."""
    from pydantic import BaseModel, ConfigDict

    type JsonTree = str | list[JsonTree]

    class TreeIn(BaseModel):
        model_config = ConfigDict(extra="forbid")
        tree: JsonTree

    with pytest.raises(Unsupported, match=r"recursive definition \(JsonTree -> JsonTree\)"):
        generate(_snapshot(TreeIn.model_json_schema()))

    class Node(BaseModel):
        model_config = ConfigDict(extra="forbid")
        children: list[Node]

    class NodeIn(BaseModel):
        model_config = ConfigDict(extra="forbid")
        root: Node

    with pytest.raises(Unsupported, match="recursive definition"):
        generate(_snapshot(NodeIn.model_json_schema()))

    # Indirect cycles too, and an acyclic chain is fine.
    a = {"type": "object", "properties": {"b": {"$ref": "#/$defs/B"}}, "required": ["b"], "additionalProperties": False}
    b = {"type": "object", "properties": {"a": {"$ref": "#/$defs/A"}}, "required": ["a"], "additionalProperties": False}
    with pytest.raises(Unsupported, match="recursive definition"):
        generate(_snapshot({**_obj({"x": {"$ref": "#/$defs/A"}}), "$defs": {"A": a, "B": b}}))
    leaf = {"type": "object", "properties": {"v": {"type": "number"}}, "required": ["v"], "additionalProperties": False}
    chain = {"A": {**a, "properties": {"b": {"$ref": "#/$defs/B"}}}, "B": leaf}
    assert "export type A = " in generate(_snapshot({**_obj({"x": {"$ref": "#/$defs/A"}}), "$defs": chain}))
    # Any JSON value is allowed: it is the built-in recursive type.

    class AnyIn(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: Any

    assert "value: JsonValue;" in generate(_snapshot(AnyIn.model_json_schema()))


def test_call_helpers_are_emitted() -> None:
    text = generate(SNAPSHOT)
    assert "export type SingleName<N extends OperationName>" in text
    assert "export type Exact<T, A> = false extends ExactOK<T, A> ? never : unknown;" in text
    assert "export type ExactOK<T, A> = [JsonValue] extends [T]" in text  # JsonValue ends the walk
    assert "export type SuccessEnvelope<N extends OperationName = OperationName> = N extends OperationName" in text


def test_keys_and_doc_comments_are_escaped() -> None:
    out = _render(_obj({"needs-quote": {"type": "string", "pattern": "a*/b"}}, additionalProperties=False))
    assert '  "needs-quote": string;' in out
    assert '/** pattern "a*\\/b" */' in out  # a pattern cannot close the comment early


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        ({"allOf": [{"type": "string"}]}, "unsupported keyword"),
        ({"oneOf": [{"type": "string"}]}, "unsupported keyword"),
        ({"not": {"type": "string"}}, "unsupported keyword"),
        ({"if": {"type": "string"}, "then": {}}, "unsupported keyword"),
        ({"type": "object", "patternProperties": {"^a": {}}}, "unsupported keyword"),
        ({"const": {"a": 1}}, "primitive const"),
        ({"enum": []}, "non-empty"),
        ({"$ref": "https://example.com/x"}, "local"),
        ({"$ref": "#/$defs/Missing"}, "dangling"),
        ({"$ref": "#/$defs/Revisions", "type": "string"}, "alongside"),
        ({"type": "array", "prefixItems": [{"type": "string"}]}, "fixed-length"),
        ({"type": "array", "prefixItems": [{"type": "string"}], "minItems": 1, "maxItems": 3}, "fixed-length"),
        ({"type": ["object", "null"]}, "object or array"),
        ({"type": "tuple"}, "unknown type"),
        ({"properties": {"a": {}}}, "without a type"),
        ({"type": "object", "required": ["a"]}, "no property schema"),
        ({"type": "string", "properties": {}}, "on a string"),
        ({"anyOf": [{"type": "string"}], "type": "string"}, "alongside"),
        ({"type": "object", "propertyNames": {"enum": ["a"]}}, "keys"),
        # Round 29, finding 3: structural siblings of anyOf/const/enum are refused, not dropped.
        ({"anyOf": [_obj({"a": {"type": "string"}}, [], additionalProperties=False)], "required": ["a"]}, "alongside"),
        ({"anyOf": [{"type": "object"}], "additionalProperties": False}, "alongside"),
        ({"anyOf": [{"type": "string"}], "properties": {}}, "alongside"),
        ({"anyOf": [{"type": "string"}], "const": "x"}, "alongside"),
        ({"const": "x", "type": "number"}, "declared type"),
        ({"enum": ["x", 1], "type": "string"}, "declared type"),
        ({"enum": [1.5], "type": "integer"}, "declared type"),
        ({"const": "x", "enum": ["x"]}, "const alongside enum"),
        ({"const": "x", "properties": {}}, "alongside"),
        ({"$ref": "#/$defs/Revisions", "anyOf": [{"type": "string"}]}, "alongside"),
        # Unions that TypeScript cannot make exact.
        (
            {"anyOf": [_obj({"a": {"type": "string"}}, additionalProperties=False), {"type": "object"}]},
            "not all closed",
        ),
        (
            {
                "anyOf": [
                    _obj({"a": {"type": "string"}}, additionalProperties=False),
                    {"type": "object", "additionalProperties": {"type": "string"}},
                ]
            },
            "not all closed",
        ),
        (
            {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "array", "items": {"type": "number"}}]},
            "several array",
        ),
    ],
)
def test_unrepresentable_schemas_fail_closed(schema: dict[str, Any], message: str) -> None:
    with pytest.raises(Unsupported, match=message):
        generate(_snapshot(_obj({"x": schema}, additionalProperties=False)))


def test_a_definition_name_means_one_schema() -> None:
    a = {"type": "object", "properties": {"v": {"type": "number"}}, "required": ["v"], "additionalProperties": False}
    b = {**a, "properties": {"v": {"type": "string"}}}
    same = _snapshot(
        {**_obj({"x": {"$ref": "#/$defs/A"}}), "$defs": {"A": a}},
        {"title": "ProbeOut", **_obj({"y": {"$ref": "#/$defs/A"}}), "$defs": {"A": a}},
    )
    assert generate(same).count("export type A = ") == 1
    clash = _snapshot(
        {**_obj({"x": {"$ref": "#/$defs/A"}}), "$defs": {"A": a}},
        {"title": "ProbeOut", **_obj({"y": {"$ref": "#/$defs/A"}}), "$defs": {"A": b}},
    )
    with pytest.raises(Unsupported, match="two different schemas"):
        generate(clash)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda s: s["operations"][0]["input_schema"].update(title="ProbeOut"), "used twice"),
        (lambda s: s["operations"][0]["input_schema"].update(title="Revisions"), "also a definition"),
        (lambda s: s["operations"][0]["input_schema"].update(title="not an identifier"), "title"),
        (lambda s: s["operations"].append(dict(s["operations"][0])), "duplicate operation"),
        (lambda s: s["operations"][0].pop("max_request_bytes"), "metadata"),
        (lambda s: s["operations"][0]["input_schema"].update({"$defs": {"JsonValue": {"type": "string"}}}), "reserved"),
        (lambda s: s.update(contract_version=2), "contract_version"),
    ],
)
def test_snapshot_level_problems_fail_closed(mutate: Any, message: str) -> None:
    snapshot = json.loads(json.dumps(_snapshot({"type": "object", "additionalProperties": False})))
    mutate(snapshot)
    with pytest.raises(Unsupported, match=message):
        generate(snapshot)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e["properties"].update(extra={"type": "string"}),
        lambda e: e["required"].remove("revisions"),
        lambda e: e.update(additionalProperties=True),
        lambda e: e["properties"]["ok"].update(const=False),
        lambda e: e["properties"]["revisions"].update({"$ref": "#/$defs/Other"}),
        # Round 29, finding 4: every keyword counts, `result` included.
        lambda e: e["properties"].update(result={"type": "array", "items": {"type": "string"}}),
        lambda e: e["properties"]["operation"].update(enum=["fit.run"]),
        lambda e: e["properties"]["revisions"].update({"not": {}}),
        lambda e: e.update({"not": {}}),
        lambda e: e.update(unevaluatedProperties=False),
        lambda e: e["$defs"].update(Extra={"type": "string"}),
        lambda e: e["required"].append("ok"),
    ],
)
def test_success_envelope_template_tracks_the_schema(mutate: Any) -> None:
    """SuccessEnvelope<N> is template text; a change to the published envelope must break the build."""
    snapshot = json.loads(json.dumps(_snapshot({"type": "object", "additionalProperties": False})))
    mutate(snapshot["envelopes"]["success"])
    with pytest.raises(Unsupported, match=r"envelopes\.success"):
        generate(snapshot)
