"""Generate the web client's TypeScript contract from the committed registry snapshot (D13, M2 step 1b).

    uv run python tools/codegen/ts_contract.py           # write web/src/generated/{contract,conformance}.ts
    uv run python tools/codegen/ts_contract.py --check   # exit 1 if a committed file is stale

The snapshot (packages/dipolar-app/registry.snapshot.json) is the contract; this module turns it
into types, so the page cannot drift from the operations it calls. It emits:

- one type per schema definition and per operation input and output;
- ``Operations``, the map from operation name to its input and output types, so
  ``callOperation("fit.preview", args)`` checks ``args`` and types the result;
- the envelopes (the success envelope is specialised per operation), the error codes and
  ``CONTRACT_VERSION``;
- ``OPERATIONS``, each operation's metadata (kind, effect, capability, cost, request limit);
- conformance.ts, a type-only check that every registry example satisfies its operation's input
  type.

It fails closed. A keyword it cannot represent exactly (``allOf``, ``oneOf``, ``not``, an object
``const``, a non-local ``$ref``, …) raises ``Unsupported``, and so does a definition name used
with two different schemas, so a type is never silently looser than the schema. Validation-only
keywords (bounds, lengths, patterns) cannot be expressed in TypeScript; they are kept as doc
comments, and the server still enforces them.

Standard library only: it runs in CI before anything is installed for the web.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "packages/dipolar-app/registry.snapshot.json"
OUTPUT = ROOT / "web/src/generated/contract.ts"
CONFORMANCE = OUTPUT.with_name("conformance.ts")

#: Keywords turned into types.
STRUCTURAL = frozenset(
    {"type", "properties", "required", "additionalProperties", "items", "prefixItems", "anyOf", "enum", "const", "$ref"}
)
#: Keywords that only constrain values. TypeScript cannot express them; they become doc comments.
DOCUMENTED = (
    "minimum",
    "exclusiveMinimum",
    "maximum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "propertyNames",
    "default",
)
#: Keywords with no effect on the type or the value set.
IGNORED = frozenset({"title", "description", "examples", "$defs"})
KNOWN = STRUCTURAL | frozenset(DOCUMENTED) | IGNORED

JSON_VALUE = "JsonValue"
IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
PRIMITIVES = {"string": "string", "number": "number", "integer": "number", "boolean": "boolean", "null": "null"}
SUCCESS_FIELDS = {"ok", "operation", "result", "revisions"}
METADATA = ("kind", "effect", "capability", "cost", "idempotent", "revision_check", "max_request_bytes")


class Unsupported(ValueError):
    """The snapshot uses a schema feature this generator cannot represent exactly."""


# --------------------------------------------------------------------------- helpers
def _key(name: str) -> str:
    return name if IDENTIFIER.match(name) else json.dumps(name, ensure_ascii=False)


def _literal(value: Any, where: str) -> str:
    if value is None or isinstance(value, bool | int | float | str):
        return json.dumps(value, ensure_ascii=False)
    raise Unsupported(f"{where}: only primitive const/enum values are supported, not {value!r}")


def _doc(text: str, indent: str) -> str:
    safe = text.replace("*/", "*\\/")
    return f"{indent}/** {safe} */\n"


def _union(parts: Iterable[str]) -> str:
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return " | ".join(seen)  # unions flatten; array element unions are parenthesised in _array


def _constraints(schema: Mapping[str, Any]) -> str:
    notes = ["integer"] if schema.get("type") == "integer" else []
    for keyword in DOCUMENTED:
        if keyword in schema:
            value = schema[keyword]
            if keyword == "propertyNames":
                notes.append(f"keys {_constraints(value) or 'any string'}")
            else:
                notes.append(f"{keyword} {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    return ", ".join(notes)


class _Renderer:
    """Renders JSON Schema (the subset Pydantic emits) to TypeScript type expressions."""

    def render(self, schema: Any, where: str, indent: str = "") -> str:
        if schema is True or schema == {}:
            return JSON_VALUE
        if not isinstance(schema, Mapping):
            raise Unsupported(f"{where}: schema must be an object, not {schema!r}")
        unknown = sorted(set(schema) - KNOWN)
        if unknown:
            raise Unsupported(f"{where}: unsupported keyword(s) {unknown}")
        if "propertyNames" in schema:
            self._check_property_names(schema["propertyNames"], f"{where}.propertyNames")

        if "$ref" in schema:
            extra = set(schema) - {"$ref"} - IGNORED - set(DOCUMENTED)
            if extra:
                raise Unsupported(f"{where}: $ref alongside {sorted(extra)}")
            return self._ref(schema["$ref"], where)
        if "const" in schema:
            return _literal(schema["const"], where)
        if "enum" in schema:
            values = schema["enum"]
            if not isinstance(values, list) or not values:
                raise Unsupported(f"{where}: enum must be a non-empty list")
            return _union(_literal(v, where) for v in values)
        if "anyOf" in schema:
            if set(schema) & {"type", "properties", "items", "prefixItems"}:
                raise Unsupported(f"{where}: anyOf alongside structural keywords")
            branches = schema["anyOf"]
            if not isinstance(branches, list) or not branches:
                raise Unsupported(f"{where}: anyOf must be a non-empty list")
            return _union(self.render(b, f"{where}.anyOf[{i}]", indent) for i, b in enumerate(branches))

        kind = schema.get("type")
        if kind is None:
            if set(schema) & {"properties", "additionalProperties", "items", "prefixItems", "required"}:
                raise Unsupported(f"{where}: structural keywords without a type")
            return JSON_VALUE  # only annotations: any JSON value
        if isinstance(kind, list):
            if not kind or len(set(kind)) != len(kind):
                raise Unsupported(f"{where}: type list must be non-empty and unique")
            if any(k in ("object", "array") for k in kind) and len(kind) > 1:
                raise Unsupported(f"{where}: a type list with object or array")
            return _union(self._typed(schema, k, where, indent) for k in kind)
        return self._typed(schema, kind, where, indent)

    def _check_property_names(self, schema: Any, where: str) -> None:
        if not isinstance(schema, Mapping) or (set(schema) - set(DOCUMENTED) - IGNORED - {"type"}):
            raise Unsupported(f"{where}: only string constraints are supported for keys")
        if schema.get("type", "string") != "string":
            raise Unsupported(f"{where}: keys are strings")

    def _ref(self, ref: Any, where: str) -> str:
        if not isinstance(ref, str) or not ref.startswith("#/$defs/") or "/" in ref[len("#/$defs/") :]:
            raise Unsupported(f"{where}: only local '#/$defs/<Name>' references are supported, not {ref!r}")
        name = ref[len("#/$defs/") :]
        if not IDENTIFIER.match(name):
            raise Unsupported(f"{where}: definition name {name!r} is not a TypeScript identifier")
        return name

    def _typed(self, schema: Mapping[str, Any], kind: Any, where: str, indent: str) -> str:
        if kind in PRIMITIVES:
            stray = set(schema) & {"properties", "additionalProperties", "items", "prefixItems", "required"}
            if stray:
                raise Unsupported(f"{where}: {sorted(stray)} on a {kind}")
            return PRIMITIVES[kind]
        if kind == "array":
            return self._array(schema, where, indent)
        if kind == "object":
            return self._object(schema, where, indent)
        raise Unsupported(f"{where}: unknown type {kind!r}")

    def _array(self, schema: Mapping[str, Any], where: str, indent: str) -> str:
        if set(schema) & {"properties", "additionalProperties", "required"}:
            raise Unsupported(f"{where}: object keywords on an array")
        if "prefixItems" in schema:
            prefix = schema["prefixItems"]
            n = len(prefix) if isinstance(prefix, list) else -1
            # A tuple only when the length is fixed: exactly the prefix, nothing after it.
            fixed = schema.get("minItems") == n and schema.get("maxItems") == n and schema.get("items", False) is False
            if n < 1 or not fixed:
                raise Unsupported(f"{where}: prefixItems is supported only as a fixed-length tuple")
            parts = [self.render(p, f"{where}.prefixItems[{i}]", indent) for i, p in enumerate(prefix)]
            return f"[{', '.join(parts)}]"
        item = self.render(schema.get("items", True), f"{where}.items", indent)
        return f"({item})[]" if " | " in item else f"{item}[]"

    def _object(self, schema: Mapping[str, Any], where: str, indent: str) -> str:
        if set(schema) & {"items", "prefixItems"}:
            raise Unsupported(f"{where}: array keywords on an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            raise Unsupported(f"{where}: properties must be an object and required a list")
        missing = sorted(set(required) - set(properties))
        if missing:
            raise Unsupported(f"{where}: required names {missing} have no property schema")
        extra = schema.get("additionalProperties", True)
        inner = indent + "  "
        lines: list[str] = []
        types: list[str] = []
        for name, child in properties.items():
            text = self.render(child, f"{where}.{name}", inner)
            types.append(text)
            note = _constraints(child) if isinstance(child, Mapping) else ""
            if note:
                lines.append(_doc(note, inner))
            optional = "" if name in required else "?"
            lines.append(f"{inner}{_key(name)}{optional}: {text};\n")
        if extra is False:
            if not properties:
                return "{ [key: string]: never }"  # exactly the empty object; `{}` would accept anything
        else:
            value = self.render(extra, f"{where}.additionalProperties", inner)
            if properties:  # every named property must also fit the index signature
                value = _union([value, *types]) if value != JSON_VALUE else JSON_VALUE
            note = _constraints(extra) if isinstance(extra, Mapping) else ""
            if note:
                lines.append(_doc(note, inner))
            elif not properties:
                return f"{{ [key: string]: {value} }}"
            lines.append(f"{inner}[key: string]: {value};\n")
        return "{\n" + "".join(lines) + indent + "}"


# --------------------------------------------------------------------------- definitions
class _Definitions:
    """Every named type, collected across all schemas. One name means one schema."""

    def __init__(self) -> None:
        self.schemas: dict[str, Any] = {}
        self.origin: dict[str, str] = {}

    def add(self, name: str, schema: Any, where: str) -> None:
        if not IDENTIFIER.match(name):
            raise Unsupported(f"{where}: definition name {name!r} is not a TypeScript identifier")
        if name == JSON_VALUE:
            if schema != {}:
                raise Unsupported(f"{where}: {JSON_VALUE} is reserved for any JSON value")
            return
        if name in self.schemas and self.schemas[name] != schema:
            raise Unsupported(f"{where}: {name!r} names two different schemas (also in {self.origin[name]})")
        self.schemas.setdefault(name, schema)
        self.origin.setdefault(name, where)

    def collect(self, schema: Mapping[str, Any], where: str) -> None:
        for name, definition in schema.get("$defs", {}).items():
            self.add(name, definition, f"{where}.$defs.{name}")

    def check_refs(self, schema: Any, where: str) -> None:
        """Every reference must resolve to a collected definition."""
        if isinstance(schema, Mapping):
            ref = schema.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref[len("#/$defs/") :]
                if name not in self.schemas and name != JSON_VALUE:
                    raise Unsupported(f"{where}: dangling reference {ref!r}")
            for key, child in schema.items():
                if key in ("const", "enum", "default", "examples"):
                    continue
                self.check_refs(child, f"{where}.{key}")
        elif isinstance(schema, list):
            for i, child in enumerate(schema):
                self.check_refs(child, f"{where}[{i}]")


def _top_level(schema: Mapping[str, Any], where: str) -> tuple[str, dict[str, Any]]:
    """An operation schema's own type: its title names it, the $defs are hoisted."""
    title = schema.get("title")
    if not isinstance(title, str) or not IDENTIFIER.match(title):
        raise Unsupported(f"{where}: needs a title that is a TypeScript identifier, not {title!r}")
    return title, {k: v for k, v in schema.items() if k != "$defs"}


def _check_success_envelope(schema: Mapping[str, Any]) -> None:
    """The success envelope is specialised per operation by hand-written template text below; it
    must therefore have exactly the shape that text assumes."""
    props = schema.get("properties", {})
    ok = (
        set(props) == SUCCESS_FIELDS
        and set(schema.get("required", [])) == SUCCESS_FIELDS
        and schema.get("additionalProperties") is False
        and props["ok"].get("const") is True
        and props["operation"].get("type") == "string"
        and props["revisions"].get("$ref") == "#/$defs/Revisions"
    )
    if not ok:
        raise Unsupported("envelopes.success: shape changed; update the SuccessEnvelope template")


# --------------------------------------------------------------------------- generation
def generate(snapshot: Mapping[str, Any], *, source: str = "packages/dipolar-app/registry.snapshot.json") -> str:
    """The TypeScript module for one snapshot. Deterministic: the same snapshot gives the same text."""
    # Canonical key order, exactly as the committed snapshot is written: the live registry and the
    # file give the same text, and the digest is the committed file's sha256. Lists keep their order.
    raw = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    snapshot = json.loads(raw)
    version = snapshot.get("contract_version")
    if not isinstance(version, str):
        raise Unsupported("contract_version must be a string")
    envelopes = snapshot.get("envelopes", {})
    operations = snapshot.get("operations", [])
    if set(envelopes) != {"success", "error"} or not isinstance(operations, list):
        raise Unsupported("the snapshot needs envelopes.success, envelopes.error and an operations list")

    renderer = _Renderer()
    defs = _Definitions()
    tops: list[tuple[str, dict[str, Any], str]] = []  # (name, schema, where)

    _check_success_envelope(envelopes["success"])
    defs.collect(envelopes["success"], "envelopes.success")
    defs.collect(envelopes["error"], "envelopes.error")
    error_name, error_schema = _top_level(envelopes["error"], "envelopes.error")
    tops.append((error_name, error_schema, "envelopes.error"))

    names: list[str] = []
    for op in operations:
        name = op.get("name")
        if not isinstance(name, str) or not name:
            raise Unsupported(f"operation without a name: {op!r}")
        if name in names:
            raise Unsupported(f"duplicate operation {name!r}")
        names.append(name)
        for io in ("input_schema", "output_schema"):
            where = f"{name}.{io}"
            defs.collect(op[io], where)
            tops.append((*_top_level(op[io], where), where))

    top_names = [t[0] for t in tops]
    for top, _, where in tops:
        if top_names.count(top) > 1:
            raise Unsupported(f"{where}: the type name {top!r} is used twice")
        if top in defs.schemas or top == JSON_VALUE:
            raise Unsupported(f"{where}: the type name {top!r} is also a definition")
    for name, schema in defs.schemas.items():
        defs.check_refs(schema, defs.origin[name])
    for _, schema, where in tops:
        defs.check_refs(schema, where)

    out: list[str] = [
        "// GENERATED FILE: do not edit. Regenerate with `uv run python tools/codegen/ts_contract.py`.\n",
        f"// Source: {source} (sha256 {digest}).\n",
        "// CI fails if this file is stale (tests/test_ts_contract.py).\n",
        "//\n",
        "// Value constraints that TypeScript cannot express (bounds, lengths, patterns) appear as doc\n",
        "// comments; the server enforces them.\n",
        "/* eslint-disable */\n\n",
        f"export const CONTRACT_VERSION = {json.dumps(version)};\n\n",
        "/** Any JSON value. */\n",
        f"export type {JSON_VALUE} =\n"
        f"  null | boolean | number | string | {JSON_VALUE}[] | {{ [key: string]: {JSON_VALUE} }};\n",
        "\n// ---------------------------------------------------------------- definitions\n\n",
    ]
    for name in sorted(defs.schemas):
        schema = defs.schemas[name]
        note = _constraints(schema) if isinstance(schema, Mapping) else ""
        if note:
            out.append(_doc(note, ""))
        out.append(f"export type {name} = {renderer.render(schema, defs.origin[name])};\n\n")

    out.append("// ---------------------------------------------------------------- envelopes\n\n")
    out.append(f"export type {error_name} = {renderer.render(error_schema, 'envelopes.error')};\n\n")
    out.append(
        "/** A successful call of operation `N`; `result` has that operation's output type. */\n"
        "export type SuccessEnvelope<N extends OperationName = OperationName> = {\n"
        "  ok: true;\n"
        "  operation: N;\n"
        "  result: OperationOutput<N>;\n"
        "  revisions: Revisions;\n"
        "};\n\n"
        f"export type Envelope<N extends OperationName = OperationName> = SuccessEnvelope<N> | {error_name};\n\n"
    )

    out.append("// ---------------------------------------------------------------- operations\n\n")
    for op in operations:
        for io in ("input_schema", "output_schema"):
            top, schema = _top_level(op[io], f"{op['name']}.{io}")
            out.append(f"/** `{op['name']}` {'input' if io == 'input_schema' else 'output'}. */\n")
            out.append(f"export type {top} = {renderer.render(schema, op['name'] + '.' + io)};\n\n")

    out.append("/** Every registry operation, by name: its input (`args`) and output (`result`) types. */\n")
    out.append("export interface Operations {\n")
    for op in operations:
        summary = op.get("summary")
        if isinstance(summary, str) and summary:
            out.append(_doc(summary, "  "))
        out.append(
            f"  {json.dumps(op['name'])}: {{ input: {op['input_schema']['title']}; "
            f"output: {op['output_schema']['title']} }};\n"
        )
    out.append("}\n\n")
    out.append(
        "export type OperationName = keyof Operations;\n"
        'export type OperationInput<N extends OperationName> = Operations[N]["input"];\n'
        'export type OperationOutput<N extends OperationName> = Operations[N]["output"];\n\n'
    )

    out.append("/** Each operation's metadata from the registry. */\n")
    out.append("export const OPERATIONS = {\n")
    for op in operations:
        fields = []
        for key in METADATA:
            if key not in op:
                raise Unsupported(f"{op['name']}: metadata {key!r} missing")
            fields.append(f"{key}: {_literal(op[key], op['name'] + '.' + key)}")
        out.append(f"  {json.dumps(op['name'])}: {{ {', '.join(fields)} }},\n")
    out.append("} as const satisfies Record<OperationName, unknown>;\n\n")

    return "".join(out)


def generate_conformance(snapshot: Mapping[str, Any]) -> str:
    """A type-only module: every registry example must satisfy its operation's input type.

    Nothing imports it, so it never reaches the bundle; ``tsc`` checks it because it is under
    web/src. An object literal under ``satisfies`` also fails on unknown properties.
    """
    snapshot = json.loads(json.dumps(snapshot, sort_keys=True))
    out = [
        "// GENERATED FILE: do not edit. Regenerate with `uv run python tools/codegen/ts_contract.py`.\n",
        "// Type-level conformance: each registry example satisfies its operation's input type.\n",
        "// Checked by `tsc`; nothing imports this file, so it is not bundled.\n\n",
        'import type { OperationInput } from "./contract";\n\n',
    ]
    for op in snapshot.get("operations", []):
        for i, example in enumerate(op.get("examples", [])):
            text = json.dumps(example, ensure_ascii=False, sort_keys=True)
            out.append(f"void ({text} satisfies OperationInput<{json.dumps(op['name'])}>); // example {i}\n")
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the committed file is stale")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    files = {args.output: generate(snapshot), args.output.with_name(CONFORMANCE.name): generate_conformance(snapshot)}
    if args.check:
        stale = [path for path, text in files.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"{path} is stale; run: uv run python tools/codegen/ts_contract.py", file=sys.stderr)
        return 1 if stale else 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for path, text in files.items():
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
