"""Credentials of one ``dipolar serve`` instance and the browser hand-off (plan D10, M0 spike 3).

Launch-time tokens are written only to the private ready file. A browser never sees them. Instead:

1. ``dipolar open`` (or ``serve --open``) asks the server for a **launch code**: single use, valid
   for ``LAUNCH_CODE_TTL_S`` seconds, minted only for a human launch credential;
2. the browser is opened at ``/#launch=<code>``. The fragment is never sent to the server;
3. the page removes the fragment from the address bar and exchanges the code once, from an allowed
   Origin, for a **tab token** that it keeps in ``sessionStorage`` (scoped to this origin and tab).

A code left in browser history or a process list is therefore useless after first use or a minute.
A failed exchange by the real page (the code was stolen and used first) is visible to the user.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable, Mapping

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Principal

LAUNCH_CODE_TTL_S = 60.0
MAX_PENDING_CODES = 8
MAX_TAB_SESSIONS = 32


def _digest(secret: str) -> bytes:
    return hashlib.sha256(secret.encode()).digest()


class Credentials:
    """The token table (launch tokens plus tab tokens) and the pending launch codes."""

    def __init__(self, launch_tokens: Mapping[str, Principal], *, clock: Callable[[], float] = time.monotonic) -> None:
        self._tokens: dict[str, Principal] = dict(launch_tokens)
        self._codes: dict[bytes, tuple[float, Principal]] = {}  # sha256(code) -> (expiry, principal)
        self._tab_sessions = 0
        self._clock = clock
        self._lock = threading.Lock()

    def authenticate(self, token: str) -> Principal | None:
        """Constant-time comparison against every known token."""
        found: Principal | None = None
        with self._lock:
            known = list(self._tokens.items())
        for candidate, principal in known:
            if hmac.compare_digest(candidate.encode(), token.encode()):
                found = principal
        return found

    def _purge(self, now: float) -> None:
        for digest in [d for d, (expiry, _) in self._codes.items() if expiry <= now]:
            del self._codes[digest]

    def issue_launch_code(self, principal: Principal) -> str:
        if not principal.human:
            raise OperationError(
                ErrorCode.CAPABILITY_DENIED,
                "launch codes are issued only to the human launch credential",
                hint="scripts use their own token from the ready file",
            )
        with self._lock:
            now = self._clock()
            self._purge(now)
            if len(self._codes) >= MAX_PENDING_CODES:
                raise OperationError(
                    ErrorCode.CAPABILITY_DENIED,
                    f"{MAX_PENDING_CODES} launch codes are already pending",
                    hint=f"use one, or wait {LAUNCH_CODE_TTL_S:.0f} s for them to expire",
                )
            code = secrets.token_urlsafe(24)
            self._codes[_digest(code)] = (now + LAUNCH_CODE_TTL_S, principal)
        return code

    def redeem(self, code: str) -> tuple[str, Principal]:
        """Exchange a launch code (once) for a new tab token with the code's principal."""
        with self._lock:
            now = self._clock()
            self._purge(now)
            entry = self._codes.pop(_digest(code), None)
            if entry is None:
                raise OperationError(
                    ErrorCode.UNAUTHENTICATED,
                    "the launch code is invalid, expired or already used",
                    hint="run `dipolar open` for a new one; if this page never used it, someone else may have",
                )
            if self._tab_sessions >= MAX_TAB_SESSIONS:
                raise OperationError(
                    ErrorCode.CAPABILITY_DENIED,
                    f"this instance already has {MAX_TAB_SESSIONS} browser sessions",
                    hint="restart dipolar serve to revoke them",
                )
            token = secrets.token_urlsafe(32)
            self._tokens[token] = entry[1]
            self._tab_sessions += 1
            return token, entry[1]
