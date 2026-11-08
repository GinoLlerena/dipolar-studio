"""``dipolar serve``: one local session over HTTP on a loopback, OS-assigned port (plan D10).

Credentials are generated per launch and written, with the port, to a ready file readable only by
the owner (mode 0600). They never appear on the command line, in URLs or in logs. The ready file is
removed on exit.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import signal
import socket
import sys
from pathlib import Path

import uvicorn

from dipolar_app.http import create_app
from dipolar_app.journal import Journal
from dipolar_app.operations import build_registry
from dipolar_app.policy import Principal, Tier
from dipolar_app.registry import CONTRACT_VERSION
from dipolar_app.session import Session

#: Principals issued at launch: name in the ready file -> principal.
PRINCIPALS = {
    "user": Principal(actor="user", tier=Tier.APPLY, human=True),
    "robot": Principal(actor="script:robot", tier=Tier.APPLY, human=False),
    "viewer": Principal(actor="script:viewer", tier=Tier.READ, human=False),
}


def _write_private(path: Path, data: dict[str, object]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with contextlib.suppress(FileNotFoundError):
        tmp.unlink()
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _exit_on_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(128 + signum)


def serve(project_dir: Path, ready_file: Path, static_dir: Path | None) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    registry = build_registry()
    session = Session(Journal(project_dir / "project.events.jsonl"), contract_version=CONTRACT_VERSION)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)  # listening before the ready file exists, so a reader never sees "refused"
    port = sock.getsockname()[1]
    by_name = {name: secrets.token_urlsafe(32) for name in PRINCIPALS}
    tokens = {token: PRINCIPALS[name] for name, token in by_name.items()}

    app = create_app(registry, session, tokens, port=port, static_dir=static_dir)
    config = uvicorn.Config(app, log_level="warning", access_log=False, lifespan="off")
    server = uvicorn.Server(config)

    # uvicorn shuts down gracefully, then re-raises SIGTERM; turn it into SystemExit so that the
    # ready file is still removed below.
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    print(f"Dipolar Studio: http://127.0.0.1:{port}/  (credentials: {ready_file})", flush=True)
    # Publishing the ready file is the last start-up step: a reader that sees it may rely on
    # everything above (listening socket, signal handling, the printed banner).
    _write_private(
        ready_file,
        {
            "pid": os.getpid(),
            "base_url": f"http://127.0.0.1:{port}",
            "contract_version": CONTRACT_VERSION,
            "tokens": by_name,
        },
    )
    try:
        server.run(sockets=[sock])
    finally:
        with contextlib.suppress(FileNotFoundError):
            ready_file.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dipolar")
    sub = parser.add_subparsers(dest="command", required=True)
    p_serve = sub.add_parser("serve", help="serve one local session over HTTP on 127.0.0.1")
    p_serve.add_argument("--project-dir", type=Path, required=True, help="directory for the journal")
    p_serve.add_argument("--ready-file", type=Path, help="where to write port and credentials (mode 0600)")
    p_serve.add_argument("--static-dir", type=Path, help="built browser page to serve at / (web/dist)")
    ns = parser.parse_args(argv)
    if ns.command == "serve":
        if ns.static_dir is not None and not (ns.static_dir / "index.html").is_file():
            parser.error(f"--static-dir {ns.static_dir} has no index.html (run: cd web && pnpm build)")
        serve(ns.project_dir, ns.ready_file or ns.project_dir / "serve.ready.json", ns.static_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
