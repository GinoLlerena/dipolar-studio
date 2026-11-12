"""Global chronological undo and redo of the science history (04 D14, §8.2; M2 step 2).

Every transaction that changes the science pushes one undo entry: the project before it (the
session builds the stacks from journaled events, so replay rebuilds them). ``history.undo`` and
``history.redo`` are new commands, journaled and audited like any other: revisions never decrease,
and they need ``expected_science_revision``, so an undo never silently reverts a change its caller
has not seen, such as another actor's (the §8.6 cross-actor check).

The view has no undo stack yet: the selection is its only state, and undoing a science change
prunes it to the IDs that still exist. Runs and exports are not undone (there are no stored runs
before M2 step 3).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.project import science_hash
from dipolar_app.registry import Context
from dipolar_app.schemas import Revision, Wire
from dipolar_app.science_ops import Science, check_revision, replace_project
from dipolar_app.session import MAX_UNDO, Event, HistoryEntry, SessionState


class HistoryEntryOut(Wire):
    operation: str
    actor: str
    science_revision: int  # the revision the change produced


def _entry(e: HistoryEntry) -> HistoryEntryOut:
    return HistoryEntryOut(operation=e.operation, actor=e.actor, science_revision=e.science_revision)


class UndoIn(Wire):
    expected_science_revision: Revision


class RedoIn(UndoIn):
    pass


class UndoOut(Science):
    undone: HistoryEntryOut


class RedoOut(Science):
    redone: HistoryEntryOut


def _move(state: SessionState, kind: str, entry: HistoryEntry) -> list[Event]:
    events = replace_project(state, entry.project)
    for event in events:
        if event["type"] == "project.replaced":
            event["history"] = kind
    return events


def history_undo(ctx: Context, p: UndoIn) -> UndoOut:
    def plan(state: SessionState) -> tuple[list[Event], UndoOut]:
        check_revision(p.expected_science_revision, state)
        if not state.undo:
            raise OperationError(
                ErrorCode.NOTHING_TO_UNDO,
                "there is no science change to undo",
                hint="history.log lists what can be undone and redone",
            )
        entry = state.undo[-1]
        return _move(state, "undo", entry), UndoOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(entry.project),
            undone=_entry(entry),
        )

    return ctx.commit("history.undo", p.model_dump(mode="json"), plan)


def history_redo(ctx: Context, p: RedoIn) -> RedoOut:
    def plan(state: SessionState) -> tuple[list[Event], RedoOut]:
        check_revision(p.expected_science_revision, state)
        if not state.redo:
            raise OperationError(
                ErrorCode.NOTHING_TO_UNDO,
                "there is no undone change to redo (a new change clears the redo history)",
                hint="history.log lists what can be undone and redone",
            )
        entry = state.redo[-1]
        return _move(state, "redo", entry), RedoOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(entry.project),
            redone=_entry(entry),
        )

    return ctx.commit("history.redo", p.model_dump(mode="json"), plan)


class LogIn(Wire):
    pass


class LogOut(Science):
    undo: Annotated[tuple[HistoryEntryOut, ...], Field(max_length=MAX_UNDO)]  # the next undo first
    redo: Annotated[tuple[HistoryEntryOut, ...], Field(max_length=MAX_UNDO)]  # the next redo first
    max_undo: int


def history_log(ctx: Context, _: LogIn) -> LogOut:
    state = ctx.read()
    return LogOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        undo=tuple(_entry(e) for e in reversed(state.undo)),
        redo=tuple(_entry(e) for e in reversed(state.redo)),
        max_undo=MAX_UNDO,
    )
