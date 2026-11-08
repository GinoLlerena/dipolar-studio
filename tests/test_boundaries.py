"""Architecture boundaries (plan D1/D8, 04 §6): dipolar-core stays pure.

dipolar-core may import only the standard library's pure modules, NumPy, SciPy and itself. It
must not import the application layer, web frameworks or I/O modules, and must not call open().
"""

from __future__ import annotations

import ast
import re
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


# --------------------------------------------------------------------------- frontend (04 §8.5)
WEB_SRC = ROOT / "web" / "src"
NETWORK_APIS = ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "import(")
# Registry operations, plus the one authentication exception (04 §8.5): the launch-code exchange.
ALLOWED_PATHS = ("/api/v1/ops/", "/api/v1/auth/session")
WEB_FILES = sorted(p for p in WEB_SRC.rglob("*") if p.suffix in {".ts", ".tsx"})


@pytest.mark.parametrize("path", WEB_FILES, ids=[str(p.relative_to(WEB_SRC)) for p in WEB_FILES])
def test_frontend_has_no_private_api(path: Path) -> None:
    """Only web/src/api.ts may touch the network, and only registry operation URLs (D13)."""
    text = path.read_text()
    used = [api for api in NETWORK_APIS if api in text]
    if path.name != "api.ts":
        assert not used, f"{path.name} uses {used}; all backend access goes through api.ts"
        return
    assert used == ["fetch("], used
    assert text.count("fetch(") == 2, "api.ts makes exactly two kinds of call: operations and the code exchange"
    urls = re.findall(r"`(/[^`$]*)", text) + re.findall(r"[\"'](/api[^\"']*)", text)
    assert urls and all(u.startswith(ALLOWED_PATHS) for u in urls), urls


def test_frontend_imports_no_domain_logic() -> None:
    """The frontend may not reimplement fitting, reconciliation or selection logic (04 §8.5)."""
    for path in WEB_FILES:
        for spec in re.findall(r"from\s+[\"']([^\"']+)[\"']", path.read_text()):
            assert spec.startswith(".") or spec.split("/")[0] in {"react", "react-dom"}, (path.name, spec)
