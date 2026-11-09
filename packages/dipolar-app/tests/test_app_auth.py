"""Launch codes and tab tokens (plan D10, M0 spike 3), with a fake clock."""

from __future__ import annotations

import pytest
from conftest import ROBOT, USER
from dipolar_app.auth import LAUNCH_CODE_TTL_S, MAX_PENDING_CODES, MAX_TAB_SESSIONS, Credentials
from dipolar_app.errors import ErrorCode, OperationError


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def credentials() -> tuple[Credentials, Clock]:
    clock = Clock()
    return Credentials({"launch-user": USER, "launch-robot": ROBOT}, clock=clock), clock


def test_launch_tokens_authenticate() -> None:
    creds, _ = credentials()
    assert creds.authenticate("launch-user") is USER
    assert creds.authenticate("launch-robot") is ROBOT
    assert creds.authenticate("launch-user ") is None
    assert creds.authenticate("") is None


def test_a_code_is_single_use_and_yields_a_new_tab_token() -> None:
    creds, _ = credentials()
    code = creds.issue_launch_code("launch-user")
    token, principal = creds.redeem(code)
    assert principal is USER and token not in {"launch-user", "launch-robot"}
    assert creds.authenticate(token) is USER
    with pytest.raises(OperationError) as err:
        creds.redeem(code)
    assert err.value.code is ErrorCode.UNAUTHENTICATED


def test_a_code_expires() -> None:
    creds, clock = credentials()
    code = creds.issue_launch_code("launch-user")
    clock.now += LAUNCH_CODE_TTL_S  # expiry is exclusive: at exactly the TTL the code is gone
    with pytest.raises(OperationError) as err:
        creds.redeem(code)
    assert err.value.code is ErrorCode.UNAUTHENTICATED
    fresh = creds.issue_launch_code("launch-user")
    clock.now += LAUNCH_CODE_TTL_S - 1
    assert creds.redeem(fresh)[1] is USER


def test_only_the_human_launch_token_mints_codes() -> None:
    """Round 10, finding 3: a robot token and a *tab* token (which acts as the user) cannot mint."""
    creds, _ = credentials()
    tab, principal = creds.redeem(creds.issue_launch_code("launch-user"))
    assert principal is USER
    for token, code in (("launch-robot", ErrorCode.CAPABILITY_DENIED), (tab, ErrorCode.CAPABILITY_DENIED)):
        with pytest.raises(OperationError) as err:
            creds.issue_launch_code(token)
        assert err.value.code is code
    with pytest.raises(OperationError) as err:
        creds.issue_launch_code("unknown")
    assert err.value.code is ErrorCode.UNAUTHENTICATED


@pytest.mark.parametrize("code", ["", "\ud800", "x" * 65, "has space", "é"])
def test_malformed_codes_are_refused_cleanly(code: str) -> None:
    creds, _ = credentials()
    with pytest.raises(OperationError) as err:
        creds.redeem(code)
    assert err.value.code is ErrorCode.UNAUTHENTICATED


def test_pending_codes_are_bounded_and_expire() -> None:
    creds, clock = credentials()
    for _ in range(MAX_PENDING_CODES):
        creds.issue_launch_code("launch-user")
    with pytest.raises(OperationError):
        creds.issue_launch_code("launch-user")
    clock.now += LAUNCH_CODE_TTL_S
    creds.issue_launch_code("launch-user")  # the expired ones no longer count


def test_tab_sessions_are_bounded() -> None:
    creds, _ = credentials()
    for _ in range(MAX_TAB_SESSIONS):
        creds.redeem(creds.issue_launch_code("launch-user"))
    code = creds.issue_launch_code("launch-user")
    with pytest.raises(OperationError) as err:
        creds.redeem(code)
    assert err.value.code is ErrorCode.CAPABILITY_DENIED
