"""Jobs and runs as resources (04 D18, D11, §8.1; M2 step 3).

``fit.run`` no longer blocks. It commits a job submission and returns at once with the job:
- its input identity: the science revision and hash, and the D11 input hash;
- its status.

The job runner (``dipolar_app.jobs``) computes the fit from the input snapshot and publishes a
run. The other operations:
- ``job.status``, ``job.list`` and ``job.wait`` (bounded to 30 s) read jobs;
- ``job.cancel`` cancels a job: the caller's own jobs for a ``propose``-tier caller, any job for
  ``apply`` and ``admin``;
- ``run.get`` returns a run's result, verified against its blob's SHA-256, with ``stale`` set
  when the science changed since its input;
- ``run.list`` lists the runs.

A ``propose``-tier caller cannot submit a fit directly. It proposes ``fit.run`` instead, and the
job starts when a human accepts the proposal; the job records the proposer.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
from typing import Annotated, Literal

from pydantic import Field

from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Tier
from dipolar_app.project import canonical_json
from dipolar_app.registry import Context
from dipolar_app.schemas import Revision, Wire
from dipolar_app.science_ops import FitRunOut, Science, check_revision, readiness, require_project
from dipolar_app.session import JOB, TERMINAL, CurrentScience, Event, Job, Run, SessionState

#: Unfinished jobs allowed per actor, and in total (D17 budgets).
MAX_JOBS_PER_ACTOR = 2
MAX_UNFINISHED_JOBS = 8
#: ``job.wait`` never holds a request longer than this (D18).
MAX_WAIT_S = 30.0

JobId = Annotated[str, Field(pattern=r"^job_[0-9]{6}$")]
RunId = Annotated[str, Field(pattern=r"^run_[0-9]{6}$")]


class JobError(Wire):
    code: str
    message: str


PublicJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]


class JobOut(Wire):
    id: JobId
    kind: Literal["fit"]
    status: PublicJobStatus
    owner: str
    proposed_by: str | None
    submitted_at: str
    finished_at: str | None
    science_revision: int  # the input: the science state the job computes from
    science_hash: str
    input_hash: str
    options: dict[str, bool]
    run_id: RunId | None
    error: JobError | None
    stale: bool  # the science differs from the job's input (by content: an undo can restore it)


def job_out(job: Job, state: SessionState, live: str | None, current: CurrentScience | None = None) -> JobOut:
    """``current`` is passed in when listing many jobs, so the project is hashed once."""
    current = current or CurrentScience(state)
    status: PublicJobStatus = job.status if job.status in TERMINAL or live != "running" else "running"
    return JobOut(
        id=job.id,
        kind="fit",
        status=status,
        owner=job.owner,
        proposed_by=job.proposed_by,
        submitted_at=job.submitted_at,
        finished_at=job.finished_at,
        science_revision=job.science_revision,
        science_hash=job.science_hash,
        input_hash=job.input_hash,
        options=json.loads(job.options_json),
        run_id=job.run_id,
        error=JobError(code=job.error_code, message=job.error_message or "") if job.error_code else None,
        stale=current.is_stale(job),
    )


def _find_job(state: SessionState, job_id: str) -> Job:
    job = state.job(job_id)
    if job is None:
        raise OperationError(
            ErrorCode.ID_NOT_FOUND,
            f"{job_id} is not a job of this session (or it was pruned after it finished)",
            offending_field="job_id",
            hint="job.list shows the jobs",
        )
    return job


def input_hash(science_hash: str, kind: str, options: dict[str, bool], fit_version: str) -> str:
    """The D11 canonical input hash: the science, the job's options, the solver version and the
    numerical context."""
    from dipolar_core.context import numerical_context

    payload = {
        "science_hash": science_hash,
        "kind": kind,
        "options": options,
        "fit_version": fit_version,
        "numerical_context": numerical_context(),
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode()).hexdigest()


# --------------------------------------------------------------------------- fit.run
class FitRunIn(Wire):
    intervals: bool = False
    expected_science_revision: Revision


class FitRunSubmitted(Science):
    job: JobOut


def fit_run(ctx: Context, p: FitRunIn) -> FitRunSubmitted:
    # Imported here, never under the session lock: the first import loads SciPy (about 1.5 s).
    from dipolar_core.fit import FIT_VERSION

    options = {"intervals": p.intervals}
    principal = ctx.principal

    def plan(state: SessionState) -> tuple[list[Event], FitRunSubmitted]:
        check_revision(p.expected_science_revision, state)
        project = require_project(state)
        reason = readiness(project)
        if reason is not None:
            raise OperationError(
                ErrorCode.PROJECT_NOT_READY,
                f"the project cannot be fitted yet: {reason}",
                hint="project.describe reports what is missing",
            )
        unfinished = [j for j in state.jobs if j.status not in TERMINAL]
        mine = [j for j in unfinished if j.owner == principal.actor]
        if len(mine) >= MAX_JOBS_PER_ACTOR or len(unfinished) >= MAX_UNFINISHED_JOBS:
            raise OperationError(
                ErrorCode.QUOTA_EXCEEDED,
                f"{len(mine)} of your jobs and {len(unfinished)} in total are unfinished; at most "
                f"{MAX_JOBS_PER_ACTOR} per caller and {MAX_UNFINISHED_JOBS} in total",
                hint="wait for a job to finish (job.wait) or cancel one (job.cancel)",
            )
        job_id = f"job_{state.next_job:06d}"
        submitted_at = dt.datetime.now(dt.UTC).isoformat()
        digest = input_hash(state.science_hash, "fit", options, FIT_VERSION)
        data: dict[str, object] = {
            "id": job_id,
            "kind": "fit",
            "owner": principal.actor,
            "proposed_by": None,
            "submitted_at": submitted_at,
            "science_revision": state.science_revision,
            "science_hash": state.science_hash,
            "input_hash": digest,
            "options": options,
        }
        event: Event = {"type": "job.submitted", "domain": JOB, "job": data}
        job = Job(
            id=job_id,
            kind="fit",
            owner=principal.actor,
            proposed_by=None,
            submitted_at=submitted_at,
            science_revision=state.science_revision,
            science_hash=state.science_hash,
            input_hash=digest,
            options_json=canonical_json(options),
            content_hash=state.content_hash,
        )
        return [event], FitRunSubmitted(
            science_revision=state.science_revision,
            science_hash=state.science_hash,
            job=job_out(job, state, None),
        )

    return ctx.commit("fit.run", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- job.status / job.list / job.wait
class JobStatusIn(Wire):
    job_id: JobId


class JobStatusOut(Science):
    job: JobOut


def job_status(ctx: Context, p: JobStatusIn) -> JobStatusOut:
    state = ctx.read()
    job = _find_job(state, p.job_id)
    return JobStatusOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        job=job_out(job, state, ctx.session.live_status(job.id)),
    )


class JobWaitIn(Wire):
    job_id: JobId
    timeout_s: Annotated[float, Field(ge=0, le=MAX_WAIT_S)] = 10.0


class JobWaitOut(Science):
    job: JobOut
    finished: bool  # false: the wait timed out first; call again


#: Waits that may block a server thread at once. Each blocked wait holds a thread of the shared
#: pool, so the waits are capped and commands always find a thread (round 33); a wait beyond the
#: cap returns at once with the current status.
MAX_BLOCKING_WAITS = 8
_waits = threading.BoundedSemaphore(MAX_BLOCKING_WAITS)


def job_wait(ctx: Context, p: JobWaitIn) -> JobWaitOut:
    _find_job(ctx.session.state, p.job_id)

    def done(state: SessionState) -> bool:
        job = state.job(p.job_id)
        return job is None or job.status in TERMINAL

    if _waits.acquire(blocking=False):
        try:
            ctx.session.wait_for(done, p.timeout_s)
        finally:
            _waits.release()
    state = ctx.read()
    job = _find_job(state, p.job_id)
    return JobWaitOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        job=job_out(job, state, ctx.session.live_status(job.id)),
        finished=job.status in TERMINAL,
    )


class JobListIn(Wire):
    status: Literal["unfinished", "finished"] | None = None


class JobListOut(Science):
    jobs: tuple[JobOut, ...]


def job_list(ctx: Context, p: JobListIn) -> JobListOut:
    state = ctx.read()
    jobs = [j for j in state.jobs if p.status is None or (j.status in TERMINAL) == (p.status == "finished")]
    current = CurrentScience(state)
    return JobListOut(
        science_revision=state.science_revision,
        science_hash=current.science,
        jobs=tuple(job_out(j, state, ctx.session.live_status(j.id), current) for j in jobs),
    )


# --------------------------------------------------------------------------- job.cancel
class JobCancelIn(Wire):
    job_id: JobId


class JobCancelOut(Science):
    job: JobOut
    cancelled: bool  # false: the job had already finished


def job_cancel(ctx: Context, p: JobCancelIn) -> JobCancelOut:
    principal = ctx.principal

    def plan(state: SessionState) -> tuple[list[Event], JobCancelOut]:
        job = _find_job(state, p.job_id)
        if principal.tier is Tier.PROPOSE and principal.actor not in (job.owner, job.proposed_by):
            raise OperationError(
                ErrorCode.CAPABILITY_DENIED,
                f"{job.id} belongs to {job.owner}; a propose-tier caller cancels only its own jobs",
                offending_field="job_id",
            )
        if job.status in TERMINAL:
            return [], JobCancelOut(
                science_revision=state.science_revision,
                science_hash=state.science_hash,
                job=job_out(job, state, None),
                cancelled=False,
            )
        event: Event = {
            "type": "job.finished",
            "domain": JOB,
            "id": job.id,
            "status": "cancelled",
            "at": dt.datetime.now(dt.UTC).isoformat(),
            "error": None,
            "run": None,
        }
        from dipolar_app.session import apply_record

        after = apply_record(state, [[event]], operation="job.cancel", actor=principal.actor)
        cancelled = after.job(job.id)
        assert cancelled is not None
        return [event], JobCancelOut(
            science_revision=state.science_revision,
            science_hash=state.science_hash,
            job=job_out(cancelled, after, None),
            cancelled=True,
        )

    return ctx.commit("job.cancel", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- run.get / run.list
class RunOut(Wire):
    id: RunId
    job_id: JobId
    kind: Literal["fit"]
    owner: str
    created_at: str
    science_revision: int
    science_hash: str
    input_hash: str
    result_sha256: str
    stale: bool  # the science differs from the run's input (by science hash, so an undo that
    # restores the exact input makes the run current again)


def run_out(run: Run, state: SessionState, current: CurrentScience | None = None) -> RunOut:
    current = current or CurrentScience(state)
    return RunOut(
        id=run.id,
        job_id=run.job_id,
        kind="fit",
        owner=run.owner,
        created_at=run.created_at,
        science_revision=run.science_revision,
        science_hash=run.science_hash,
        input_hash=run.input_hash,
        result_sha256=run.result_sha256,
        stale=current.is_stale(run),
    )


class RunGetIn(Wire):
    run_id: RunId


class RunGetOut(Science):
    run: RunOut
    result: FitRunOut


def run_get(ctx: Context, p: RunGetIn) -> RunGetOut:
    state = ctx.read()
    run = state.run(p.run_id)
    if run is None:
        raise OperationError(
            ErrorCode.ID_NOT_FOUND,
            f"{p.run_id} is not a run of this session (or it was pruned)",
            offending_field="run_id",
            hint="run.list shows the runs",
        )
    text = ctx.session.blobs.text(run.result_sha256)
    if text is None:
        raise OperationError(ErrorCode.INTERNAL, f"the result of {run.id} is missing or damaged")
    return RunGetOut(
        science_revision=state.science_revision,
        science_hash=state.science_hash,
        run=run_out(run, state),
        result=FitRunOut.model_validate_json(text),
    )


class RunListIn(Wire):
    pass


class RunListOut(Science):
    runs: tuple[RunOut, ...]


def run_list(ctx: Context, _: RunListIn) -> RunListOut:
    state = ctx.read()
    current = CurrentScience(state)
    return RunListOut(
        science_revision=state.science_revision,
        science_hash=current.science,
        runs=tuple(run_out(r, state, current) for r in reversed(state.runs)),
    )
