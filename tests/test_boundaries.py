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
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def calls_open(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
# Registry operations, the one authentication exception (04 §8.5: the launch-code exchange) and
# the change feed (D14; M3 step 1), a read with no arguments that only announces revisions.
ALLOWED_PATHS = ("/api/v1/ops/", "/api/v1/auth/session", "/api/v1/events")
WEB_FILES = sorted(p for p in WEB_SRC.rglob("*") if p.suffix in {".ts", ".tsx"})


@pytest.mark.parametrize("path", WEB_FILES, ids=[str(p.relative_to(WEB_SRC)) for p in WEB_FILES])
def test_frontend_has_no_private_api(path: Path) -> None:
    """Only web/src/api.ts may touch the network, and only registry operation URLs (D13)."""
    text = path.read_text(encoding="utf-8")
    used = [api for api in NETWORK_APIS if api in text]
    if path.name != "api.ts":
        assert not used, f"{path.name} uses {used}; all backend access goes through api.ts"
        return
    assert used == ["fetch("], used
    assert text.count("fetch(") == 3, "api.ts makes three kinds of call: operations, the code exchange, events"
    urls = re.findall(r"`(/[^`$]*)", text) + re.findall(r"[\"'](/api[^\"']*)", text)
    assert urls and all(u.startswith(ALLOWED_PATHS) for u in urls), urls


def test_frontend_imports_no_domain_logic() -> None:
    """The frontend may not reimplement fitting, reconciliation or selection logic (04 §8.5)."""
    for path in WEB_FILES:
        for spec in re.findall(r"from\s+[\"']([^\"']+)[\"']", path.read_text(encoding="utf-8")):
            assert spec.startswith(".") or spec.split("/")[0] in {"react", "react-dom"}, (path.name, spec)


def test_the_app_starts_without_the_optimizer() -> None:
    """Building a problem, the registry and the HTTP app must not import scipy.optimize or
    scipy.stats (1.5 s per process start); only fitting does. M1 step 1 moved Problem out of
    dipolar_core.fit for this."""
    import subprocess
    import sys

    probe = "\n".join(
        [
            "import sys, numpy as np",
            "import dipolar_app.cli",
            "from dipolar_app.auth import Credentials",
            "from dipolar_app.http import create_app",
            "from dipolar_app.operations import build_registry",
            "from dipolar_app.session import Session",
            "from dipolar_core.biphenyl import rigid_problem",
            "rigid_problem(((0, 5),), np.array([-1000.0]), np.array([0.5]))",  # build a problem
            "create_app(build_registry(), Session(None, contract_version='0'), Credentials({}), port=1)",
            "print(sorted(m for m in ('scipy.optimize', 'scipy.stats') if m in sys.modules))",
        ]
    )
    loaded = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True).stdout.strip()
    assert loaded == "[]", loaded


#: Third-party data used for validation only, removable on request (datasets/README.md).
THIRD_PARTY_DATA = ("biphenyl-8CB-dipietro2013", "dipietro")


def test_shipped_code_never_depends_on_third_party_data() -> None:
    """Removing a third-party dataset must not affect the product: no shipped source mentions it.

    Shipped means the packages' sources, the web page and the packaging script. The tests, the
    reference tools and the docs may refer to it; they skip or document its absence.
    """
    root = Path(__file__).resolve().parents[1]
    shipped = [*root.glob("packages/*/src/**/*.py"), *root.glob("web/src/**/*.ts*"), root / "tools/package/build.sh"]
    assert shipped
    for path in shipped:
        text = path.read_text(encoding="utf-8").lower()
        for name in THIRD_PARTY_DATA:
            assert name.lower() not in text, f"{path.relative_to(root)} refers to third-party data {name!r}"


def test_each_package_ships_the_repository_licence() -> None:
    """The wheels carry the licence (D9 checklist, spike 3): each package's LICENSE, declared in
    its license-files, is the repository LICENSE byte for byte."""
    import tomllib

    licence = (ROOT / "LICENSE").read_bytes()
    for package in ("dipolar-core", "dipolar-app"):
        directory = ROOT / "packages" / package
        assert (directory / "LICENSE").read_bytes() == licence, package
        project = tomllib.loads((directory / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        assert project["license"] == "BSD-3-Clause" and project["license-files"] == ["LICENSE"], package


#: Owners whose ``open`` is not file text I/O.
_NOT_TEXT_IO = {"os", "webbrowser", "urllib", "request", "tarfile", "zipfile", "gzip", "io", "codecs", "subprocess"}


def _unencoded_text_io(source: str) -> list[int]:
    """Lines with a text-mode read_text/write_text/open call that names no encoding."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text"):
            if f.attr == "read_text" and node.args:  # read_text("utf-8"): the encoding, positionally
                continue
            lines.append(node.lineno)
        elif (isinstance(f, ast.Attribute) and f.attr == "open") or (isinstance(f, ast.Name) and f.id == "open"):
            owner = f.value if isinstance(f, ast.Attribute) else None
            if isinstance(owner, ast.Name) and owner.id in _NOT_TEXT_IO:
                continue
            if isinstance(owner, ast.Attribute) and owner.attr in _NOT_TEXT_IO:
                continue
            position = 0 if isinstance(f, ast.Attribute) else 1
            mode = node.args[position] if len(node.args) > position else None
            mode = next((k.value for k in node.keywords if k.arg == "mode"), mode)
            if mode is not None and not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
                continue
            if isinstance(mode, ast.Constant) and "b" in mode.value:
                continue
            lines.append(node.lineno)
    return lines


def test_text_io_always_names_its_encoding() -> None:
    """Every text read or write names UTF-8. Without it Python uses the locale's encoding
    (cp1252 on Windows), which corrupts "Å" and the non-ASCII sources (small batch, Windows CI)."""
    import subprocess

    tracked = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    found = {}
    for name in tracked.stdout.split():
        lines = _unencoded_text_io((ROOT / name).read_text(encoding="utf-8"))
        if lines:
            found[name] = lines
    assert not found, found
