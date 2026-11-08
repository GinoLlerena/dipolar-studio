"""Architecture boundaries (plan D1/D8, 04 §6): dipolar-core stays pure.

dipolar-core may import only the standard library's pure modules, NumPy, SciPy and itself. It
must not import the application layer, web frameworks or I/O modules, and must not call open().
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "packages" / "dipolar-core" / "src" / "dipolar_core"
APP = ROOT / "packages" / "dipolar-app" / "src" / "dipolar_app"

FORBIDDEN_IN_CORE = {
    "dipolar_app",
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "requests",
    "aiohttp",
    "pydantic",
    "os",
    "io",
    "pathlib",
    "shutil",
    "socket",
    "subprocess",
    "sqlite3",
    "pickle",
    "tempfile",
    "pyarrow",
    "pandas",
    "matplotlib",
}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def calls_open(path: Path) -> bool:
    tree = ast.parse(path.read_text(), filename=str(path))
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open" for n in ast.walk(tree))


CORE_FILES = sorted(CORE.rglob("*.py"))


@pytest.mark.parametrize("path", CORE_FILES, ids=[str(p.relative_to(CORE)) for p in CORE_FILES])
def test_core_is_pure(path: Path) -> None:
    bad = imported_roots(path) & FORBIDDEN_IN_CORE
    assert not bad, f"{path.name} imports {sorted(bad)}; dipolar-core must stay pure (D1/D8)"
    assert not calls_open(path), f"{path.name} calls open(); dipolar-core performs no I/O"


def test_packages_import() -> None:
    import dipolar_app
    import dipolar_core

    assert dipolar_core.__version__ and dipolar_app.__version__
