"""What a command would change, for dry runs (04 D17, §8.3; M2 step 2).

A dry run plans the command against the current state and applies its events in memory only.
This module compares the state before and after and reports the change in bounded form: which
parts of the project changed, and the IDs of the spins and couplings added, removed or changed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import Field

from dipolar_app.project import Project
from dipolar_app.schemas import ObjectId, ProposalId, Revision, Wire
from dipolar_app.session import SessionState

#: IDs listed per change kind; beyond this the list is cut and ``truncated`` is set.
MAX_LISTED_IDS = 100


class IdChanges(Wire):
    added: Annotated[tuple[ObjectId, ...], Field(max_length=MAX_LISTED_IDS)]
    removed: Annotated[tuple[ObjectId, ...], Field(max_length=MAX_LISTED_IDS)]
    changed: Annotated[tuple[ObjectId, ...], Field(max_length=MAX_LISTED_IDS)]
    n_added: int
    n_removed: int
    n_changed: int
    truncated: bool


class ScienceChanges(Wire):
    science_hash_before: str
    science_hash_after: str
    project_opened: bool  # there was no project before
    name_changed: bool
    geometry_changed: bool
    model_changed: bool
    spins: IdChanges
    couplings: IdChanges


class WouldRevisions(Wire):
    science: Revision
    workspace: Revision


class DryRunReport(Wire):
    """The outcome of a dry run: nothing was changed, journaled or recorded."""

    would_revisions: WouldRevisions
    science: ScienceChanges | None  # None when the science would not change
    selection_after: tuple[ObjectId, ...] | None  # None when the selection would not change
    proposals_changed: tuple[ProposalId, ...]  # proposals that would be created or decided


def _id_changes(before: Mapping[str, object], after: Mapping[str, object]) -> IdChanges:
    added = [i for i in after if i not in before]
    removed = [i for i in before if i not in after]
    changed = [i for i in after if i in before and before[i] != after[i]]
    cut = MAX_LISTED_IDS
    return IdChanges(
        added=tuple(added[:cut]),
        removed=tuple(removed[:cut]),
        changed=tuple(changed[:cut]),
        n_added=len(added),
        n_removed=len(removed),
        n_changed=len(changed),
        truncated=max(len(added), len(removed), len(changed)) > cut,
    )


def _parts(project: Project | None) -> tuple[dict[str, object], dict[str, object]]:
    if project is None:
        return {}, {}
    return {s.id: s for s in project.molecule.spins}, {c.id: c for c in project.couplings}


def science_changes(before: SessionState, after: SessionState) -> ScienceChanges | None:
    if after.science_revision == before.science_revision:
        return None
    old, new = before.project, after.project
    spins_before, couplings_before = _parts(old)
    spins_after, couplings_after = _parts(new)
    return ScienceChanges(
        science_hash_before=before.science_hash,
        science_hash_after=after.science_hash,
        project_opened=old is None,
        name_changed=old is None or new is None or old.name != new.name,
        geometry_changed=old is None or new is None or old.molecule.geometry != new.molecule.geometry,
        model_changed=old is None or new is None or old.model != new.model,
        spins=_id_changes(spins_before, spins_after),
        couplings=_id_changes(couplings_before, couplings_after),
    )


def dry_run_report(before: SessionState, after: SessionState) -> DryRunReport:
    old = {p.id: p for p in before.proposals}
    touched = tuple(p.id for p in after.proposals if old.get(p.id) != p)
    return DryRunReport(
        would_revisions=WouldRevisions(science=after.science_revision, workspace=after.workspace_revision),
        science=science_changes(before, after),
        selection_after=after.view.selection if after.view.selection != before.view.selection else None,
        proposals_changed=touched,
    )
