"""Build, execute and check the user notebooks (beta step B3).

    uv run python tools/notebooks/run.py --write   # rebuild docs/notebooks/*.ipynb with outputs
    uv run python tools/notebooks/run.py --check   # CI: the committed notebooks are current and run

The notebooks' cells are defined in `build.py`. `--write` executes each one (in docs/notebooks/,
where its relative paths point) and saves it with its outputs, so a reader sees the results.
`--check` fails if a committed notebook's cells differ from `build.py`'s, or if one raises.

The 8CB notebook reads the user's transcription of Di Pietro (2013), Table 3.1. Here it is given
one made from the repository's validation copy (`datasets/biphenyl-8CB-dipietro2013/`); when
that third-party dataset is absent (it is removable on request), the 8CB notebook is skipped.
Its reference values are also checked against the frozen expected fits.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "notebooks"
DIPIETRO = ROOT / "datasets" / "biphenyl-8CB-dipietro2013"
TIMEOUT_S = 900

sys.path.insert(0, str(HERE))
from build import NOTEBOOKS  # noqa: E402


def transcription(directory: Path) -> Path | None:
    """What a user would transcribe from Table 3.1 at T_red = 0.930, from the validation copy."""
    source = DIPIETRO / "couplings.csv"
    if not source.exists():
        return None
    with source.open(encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["T_red"] == "0.930"]
    path = directory / "my-8cb-T0.930.csv"
    lines = ["spin_a,spin_b,D_obs_Hz,sigma_Hz"]
    lines += [f"{r['spin_a']},{r['spin_b']},{r['D_obs_Hz']},{r['sigma_Hz']}" for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def check_reference() -> None:
    """The 8CB notebook's typed reference values equal the frozen expected fits (to their printed
    digits)."""
    expected = json.loads((DIPIETRO / "expected" / "T0.930.json").read_text(encoding="utf-8"))["expected"]
    source = "\n".join(c["source"] for c in NOTEBOOKS["03-reproduce-8cb.ipynb"].cells if c["cell_type"] == "code")
    reference = next(
        ast.literal_eval(node.value)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REFERENCE" for t in node.targets)
    )
    assert isinstance(reference, dict)
    for configuration, values in reference.items():
        for key, value in values.items():
            frozen = expected[configuration][key]
            assert abs(value - frozen) <= 1e-6, (configuration, key, value, frozen)


def execute(name: str, nb: nbformat.NotebookNode, env: dict[str, str]) -> nbformat.NotebookNode:
    nb = nbformat.reads(nbformat.writes(nb), as_version=4)  # a copy
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        client = NotebookClient(
            nb,
            timeout=TIMEOUT_S,
            kernel_name="python3",
            record_timing=False,  # no execution timestamps: a rewrite changes nothing (round 59)
            resources={"metadata": {"path": str(OUT)}},
        )
        client.execute()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print(f"ok  {name} ran")
    return nb


def code_of(nb: nbformat.NotebookNode) -> list[tuple[str, str]]:
    return [(c["cell_type"], c["source"]) for c in nb.cells]


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    ns = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        csv_8cb = transcription(Path(tmp))
        if csv_8cb is not None:
            check_reference()
        for name, nb in NOTEBOOKS.items():
            target = OUT / name
            if ns.check:
                assert target.exists(), f"{target} is missing: run tools/notebooks/run.py --write"
                committed = nbformat.read(target, as_version=4)
                assert code_of(committed) == code_of(nb), f"{name} differs from build.py: run --write"
                executed = all(c.get("outputs") for c in committed.cells if c["cell_type"] == "code")
                assert executed, f"{name}: committed without its outputs: run --write"
            if name.startswith("03-") and csv_8cb is None:
                print(f"--  {name} skipped: the third-party 8CB dataset is not present")
                continue
            env = {"DIPOLAR_8CB_CSV": str(csv_8cb)} if csv_8cb is not None else {}
            done = execute(name, nb, env)
            if ns.write:
                if name.startswith("03-"):  # do not leave the temporary path in the saved notebook
                    for cell in done.cells:
                        for output in cell.get("outputs", []):
                            if "text" in output:
                                output["text"] = output["text"].replace(str(csv_8cb.parent), ".")
                nbformat.write(done, target)
                print(f"    wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
