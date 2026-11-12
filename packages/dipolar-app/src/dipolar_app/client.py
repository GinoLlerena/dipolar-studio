"""Python adapter: an in-process client over the same dispatcher the HTTP adapter uses."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from dipolar_app.policy import Principal
from dipolar_app.registry import Registry, dispatch
from dipolar_app.session import Session


class LocalClient:
    def __init__(self, registry: Registry, session: Session, principal: Principal) -> None:
        self._registry = registry
        self._session = session
        self._principal = principal

    def call(
        self, name: str, args: Mapping[str, Any] | None = None, *, request_id: str | None = None, dry_run: bool = False
    ) -> dict[str, Any]:
        """Return the same JSON envelope as ``POST /api/v1/ops/{name}``.

        The dispatcher validates the arguments as strict JSON, so the Python path accepts exactly
        what the HTTP path accepts (no Python-only types, no NaN or infinity).
        """
        envelope = dispatch(
            self._registry, self._session, self._principal, name, args, request_id=request_id, dry_run=dry_run
        )
        return json.loads(json.dumps(envelope, allow_nan=False))  # type: ignore[no-any-return]
