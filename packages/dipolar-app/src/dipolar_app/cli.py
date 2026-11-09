"""``dipolar serve`` and ``dipolar open`` (plan D10, decided in M0 spike 3).

``serve`` runs one local session over HTTP on a loopback, OS-assigned port. It first takes an
exclusive lock on the project directory, so a second instance can never write the same journal; the
operating system releases the lock when the process dies, even on SIGKILL. Credentials are generated
per launch and written, with the port and a public instance ID, to a ready file readable only by the
owner (mode 0600). They never appear on the command line, in URLs or in logs. The ready file is
removed on exit.

``open`` reads the ready file, checks the instance handshake, asks for a single-use launch code and
opens the browser at ``/#launch=<code>`` (see ``dipolar_app.auth``). The code never appears on a
command line: browser launchers pass their URL as an argument, which other local users can read with
``ps``. So the URL goes into a private redirect page (mode 0600) in ``browser-launch/`` beside the
ready file (a verified, user-owned, mode-0700 directory, never a symlink), and the browser is given
only that file's path (validation rounds 10 and 11). Graceful shutdown removes the instance's pages;
after a SIGKILL, expired pages are removed by the next ``dipolar open``.
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import secrets
import signal
import socket
import stat
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import uvicorn

from dipolar_app.auth import LAUNCH_CODE_TTL_S, Credentials
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


BUNDLED_STATIC = Path(__file__).resolve().parent / "static"  # filled by tools/package/build.sh
EXIT_INSTANCE_RUNNING = 3
EXIT_STALE = 4


class InstanceRunning(Exception):
    pass


LAUNCH_DIR_NAME = "browser-launch"


class UnsafeLaunchDir(Exception):
    pass


def verified_launch_dir(base: Path, *, create: bool) -> Path | None:
    """``<base>/browser-launch`` (base = the ready file's directory), only if it is a real
    directory owned by this user, never a symlink (validation round 11). Mode is forced to 0700.
    Returns None if it does not exist and ``create`` is false.

    The checks are path-based, so they assume that untrusted users cannot replace ``base`` or its
    parents (they are the user's own directories; same-user processes are trusted, ADR-0010).
    Validated on POSIX; on Windows ``chmod`` cannot repair a shared directory's ACL."""
    path = base.resolve() / LAUNCH_DIR_NAME
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not create:
            return None
        with contextlib.suppress(FileExistsError):  # a concurrent `dipolar open` may win (round 12)
            os.mkdir(path, 0o700)
        info = os.lstat(path)  # whoever created it, the checks below decide
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise UnsafeLaunchDir(f"{path} is not a plain directory (a symlink?); refusing to use it")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise UnsafeLaunchDir(f"{path} belongs to another user; refusing to use it")
    if stat.S_IMODE(info.st_mode) != 0o700:
        if os.chmod in os.supports_follow_symlinks:
            os.chmod(path, 0o700, follow_symlinks=False)
        else:
            os.chmod(path, 0o700)  # lstat above showed a real directory we own
    return path


def remove_pages(directory: Path, pattern: str, *, older_than_s: float | None = None) -> None:
    """Delete matching *regular files* in a verified launch directory (never follow links)."""
    now = time.time()
    for page in directory.glob(pattern):
        with contextlib.suppress(OSError):
            info = os.lstat(page)
            if not stat.S_ISREG(info.st_mode):
                continue
            if older_than_s is not None and now - info.st_mtime <= older_than_s:
                continue
            page.unlink()


def write_redirect_page(url: str, directory: Path, instance_id: str) -> Path:
    """A private page (0600) that sends the browser to ``url``; expired pages are removed first."""
    remove_pages(directory, "open-*.html", older_than_s=LAUNCH_CODE_TTL_S)
    target = html.escape(url, quote=True)
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={target}"><title>Dipolar Studio</title></head>'
        f'<body><p><a href="{target}">Open Dipolar Studio</a></p></body></html>\n'
    )
    path = directory / f"open-{instance_id}-{secrets.token_hex(8)}.html"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(page)
    return path


def open_in_browser(url: str, ready_file: Path, instance_id: str) -> bool:
    """Open ``url`` without putting it on any command line (validation round 10, finding 1)."""
    directory = verified_launch_dir(ready_file.parent, create=True)
    assert directory is not None
    return webbrowser.open(write_redirect_page(url, directory, instance_id).resolve().as_uri())


def remove_instance_pages(ready_file: Path, instance_id: str) -> None:
    """At shutdown: this instance's redirect pages, whose codes die with it."""
    try:
        directory = verified_launch_dir(ready_file.parent, create=False)
    except (UnsafeLaunchDir, OSError):
        return
    if directory is not None:
        remove_pages(directory, f"open-{instance_id}-*.html")


def lock_project(project_dir: Path) -> int:
    """Take the project's exclusive instance lock; the returned descriptor is held for life."""
    fd = os.open(project_dir / "serve.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise InstanceRunning(f"another dipolar serve is already using {project_dir}") from None
    return fd


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


def serve(project_dir: Path, ready_file: Path, static_dir: Path | None, *, open_browser: bool = False) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    lock_fd = lock_project(project_dir)  # before anything that touches the journal or the ready file
    # Holding the lock proves no live instance owns an existing ready file: it is stale (a crash).
    ready_file.unlink(missing_ok=True)
    registry = build_registry()
    session = Session(Journal(project_dir / "project.events.jsonl"), contract_version=CONTRACT_VERSION)
    if session.recovery is not None:
        r = session.recovery
        print(
            f"Recovered the journal: discarded {r.discarded_bytes} bytes of an unacknowledged record cut short "
            f"by a crash (kept {r.kept_records} records; the bytes are in {r.quarantine.name}).",
            flush=True,
        )

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)  # listening before the ready file exists, so a reader never sees "refused"
    port = sock.getsockname()[1]
    by_name = {name: secrets.token_urlsafe(32) for name in PRINCIPALS}
    credentials = Credentials({token: PRINCIPALS[name] for name, token in by_name.items()})
    instance_id = "ins_" + secrets.token_hex(8)  # public: names this run, proves nothing by itself

    app = create_app(
        registry, session, credentials, port=port, instance_id=instance_id, pid=os.getpid(), static_dir=static_dir
    )
    config = uvicorn.Config(app, log_level="warning", access_log=False, lifespan="off")
    server = uvicorn.Server(config)

    # uvicorn shuts down gracefully, then re-raises SIGTERM; turn it into SystemExit so that the
    # ready file is still removed below.
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    print(f"Dipolar Studio: http://127.0.0.1:{port}/  (credentials: {ready_file})", flush=True)
    if static_dir is not None and not open_browser:
        print(f"Open the page with: dipolar open --ready-file {ready_file}", flush=True)
    # Publishing the ready file is the last start-up step: a reader that sees it may rely on
    # everything above (listening socket, signal handling, the printed banner).
    _write_private(
        ready_file,
        {
            "pid": os.getpid(),
            "instance_id": instance_id,
            "base_url": f"http://127.0.0.1:{port}",
            "contract_version": CONTRACT_VERSION,
            "tokens": by_name,
        },
    )
    try:
        if open_browser and static_dir is not None:
            # The socket is already listening, so the browser's request waits for uvicorn to accept it.
            code = credentials.issue_launch_code(by_name["user"])
            try:
                open_in_browser(f"http://127.0.0.1:{port}/#launch={code}", ready_file, instance_id)
            except UnsafeLaunchDir as exc:
                print(f"dipolar serve: {exc}; not opening a browser", file=sys.stderr, flush=True)
        server.run(sockets=[sock])
    finally:
        with contextlib.suppress(FileNotFoundError):
            ready_file.unlink()
        remove_instance_pages(ready_file, instance_id)
        os.close(lock_fd)


class StaleReadyFile(Exception):
    pass


def _get_json(url: str, token: str, method: str = "GET") -> tuple[int, Any]:
    request = urllib.request.Request(url, method=method, data=b"{}" if method == "POST" else None)
    request.add_header("Authorization", f"Bearer {token}")
    if method == "POST":
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, OSError, ValueError):
        return 0, None


def launch_url(ready_file: Path) -> tuple[str, str]:
    """Check the instance handshake, then return a page URL carrying a fresh single-use code."""
    try:
        ready = json.loads(ready_file.read_text("utf-8"))
        base, token, expected = ready["base_url"], ready["tokens"]["user"], ready["instance_id"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StaleReadyFile(f"cannot read {ready_file}: {exc}") from None
    status, instance = _get_json(f"{base}/api/v1/instance", token)
    if status != 200 or not isinstance(instance, dict) or instance.get("instance_id") != expected:
        raise StaleReadyFile(
            f"{ready_file} does not describe the server on {base}: the server has stopped, or another "
            "process now uses the port. Start dipolar serve again."
        )
    status, issued = _get_json(f"{base}/api/v1/auth/launch-code", token, method="POST")
    if status != 200 or not isinstance(issued, dict) or not isinstance(issued.get("code"), str):
        raise StaleReadyFile(f"the server on {base} refused a launch code (HTTP {status})")
    return f"{base}/#launch={issued['code']}", expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dipolar")
    sub = parser.add_subparsers(dest="command", required=True)
    p_serve = sub.add_parser("serve", help="serve one local session over HTTP on 127.0.0.1")
    p_serve.add_argument("--project-dir", type=Path, required=True, help="directory for the journal")
    p_serve.add_argument("--ready-file", type=Path, help="where to write port and credentials (mode 0600)")
    p_serve.add_argument("--static-dir", type=Path, help="browser page to serve at / (default: the bundled one)")
    p_serve.add_argument("--open", action="store_true", help="open the page in the default browser")
    p_open = sub.add_parser("open", help="open the page of a running dipolar serve in the browser")
    where = p_open.add_mutually_exclusive_group(required=True)
    where.add_argument("--project-dir", type=Path, help="the project directory given to serve")
    where.add_argument("--ready-file", type=Path, help="the ready file written by serve")
    p_open.add_argument(
        "--print-url", action="store_true", help="print the single-use URL instead of opening a browser"
    )
    ns = parser.parse_args(argv)
    if ns.command == "serve":
        static_dir = ns.static_dir
        if static_dir is None and (BUNDLED_STATIC / "index.html").is_file():
            static_dir = BUNDLED_STATIC
        if static_dir is not None and not (static_dir / "index.html").is_file():
            parser.error(f"--static-dir {static_dir} has no index.html (run: cd web && pnpm build)")
        try:
            serve(
                ns.project_dir, ns.ready_file or ns.project_dir / "serve.ready.json", static_dir, open_browser=ns.open
            )
        except InstanceRunning as exc:
            print(f"dipolar serve: {exc}; use `dipolar open --project-dir {ns.project_dir}`", file=sys.stderr)
            return EXIT_INSTANCE_RUNNING
    elif ns.command == "open":
        ready_file = ns.ready_file or ns.project_dir / "serve.ready.json"
        try:
            url, instance_id = launch_url(ready_file)
        except StaleReadyFile as exc:
            print(f"dipolar open: {exc}", file=sys.stderr)
            return EXIT_STALE
        if ns.print_url:
            print(url, flush=True)  # single use, valid for one minute; shown only to this terminal
            return 0
        try:
            opened = open_in_browser(url, ready_file, instance_id)
        except UnsafeLaunchDir as exc:
            print(f"dipolar open: {exc}", file=sys.stderr)
            return 1
        if not opened:
            print("dipolar open: no browser available; rerun with --print-url", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
