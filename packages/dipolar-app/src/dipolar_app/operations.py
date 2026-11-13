"""The operation registry: the M0 slice operations and the M2 science operations.

``project.open_example``, ``view.select`` and ``render.describe_view`` are defined here. The
science operations (projects, the model, couplings and fitting) are in ``dipolar_app.science_ops``.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from dipolar_app import history_ops as H
from dipolar_app import job_ops as J
from dipolar_app import proposal_ops as P
from dipolar_app import science_ops as S
from dipolar_app import view_ops as V
from dipolar_app.errors import ErrorCode, OperationError
from dipolar_app.policy import Capability
from dipolar_app.project import load_example, science_hash
from dipolar_app.registry import Context, Operation, Registry
from dipolar_app.schemas import ExampleName, ObjectId, Revision, Wire
from dipolar_app.session import WORKSPACE, Event, SessionState

MAX_SELECTION = 1000

_require_project = S.require_project


# --------------------------------------------------------------------------- project.open_example
class OpenExampleIn(Wire):
    name: ExampleName
    expected_science_revision: Revision


class OpenExampleOut(Wire):
    science_revision: int
    science_hash: str
    n_spins: int
    n_couplings: int


def open_example(ctx: Context, p: OpenExampleIn) -> OpenExampleOut:
    project = load_example(p.name)

    def plan(state: SessionState) -> tuple[list[Event], OpenExampleOut]:
        S.check_revision(p.expected_science_revision, state)
        # IDs of the old project never stay selected, even where an ID also exists in the example
        # (round 27): always clear, never prune.
        opened = S.keep_allocator(state, project)
        events = S.replace_project(state, opened, same_project=False)
        return events, OpenExampleOut(
            science_revision=state.science_revision + 1,
            science_hash=science_hash(opened),
            n_spins=len(project.molecule.spins),
            n_couplings=len(project.couplings),
        )

    return ctx.commit("project.open_example", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- view.select
class SelectIn(Wire):
    ids: Annotated[tuple[ObjectId, ...], Field(max_length=MAX_SELECTION)]


class SelectOut(Wire):
    workspace_revision: int
    selection: tuple[V.SelectedObject, ...]


def view_select(ctx: Context, p: SelectIn) -> SelectOut:
    ids = tuple(dict.fromkeys(p.ids))  # de-duplicate, keep order

    def plan(state: SessionState) -> tuple[list[Event], SelectOut]:
        project = _require_project(state)
        for position, object_id in enumerate(ids):
            if project.label_of(object_id) is None:
                raise OperationError(
                    ErrorCode.ID_NOT_FOUND,
                    f"{object_id} is not a spin or coupling of the current project",
                    offending_field=f"ids[{position}]",
                    hint="read IDs from project.describe or fit.preview",
                )
        out = SelectOut(
            workspace_revision=state.workspace_revision + (ids != state.view.selection),
            selection=V.selected(project, ids),
        )
        if ids == state.view.selection:
            return [], out  # nothing changes: no event, no revision
        event: Event = {
            "type": "view.selection_set",
            "domain": WORKSPACE,
            "selection": list(ids),
            "previous": list(state.view.selection),
        }
        return [event], out

    return ctx.commit("view.select", p.model_dump(mode="json"), plan)


# --------------------------------------------------------------------------- registry
def build_registry() -> Registry:
    registry = Registry()
    registry.register(
        Operation(
            name="project.open_example",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Replace the session's project with a bundled example dataset.",
            input_model=OpenExampleIn,
            output_model=OpenExampleOut,
            handler=open_example,
            revision_check="expected_science_revision (required)",
            proposable=True,
            examples=({"name": "biphenyl-synthetic", "expected_science_revision": 0},),
        )
    )
    registry.register(
        Operation(
            name="project.describe",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="Describe the project: geometry, spins, couplings, model, estimand and readiness to fit, with IDs.",
            input_model=S.DescribeProjectIn,
            output_model=S.DescribeProjectOut,
            handler=S.describe_project,
            idempotent=True,
            examples=({},),
        )
    )
    registry.register(
        Operation(
            name="fit.preview",
            kind="query",
            effect="none",
            capability=Capability.PREVIEW,
            summary="Preview the fit at a fixed torsion: order parameters re-solved, predictions and residuals.",
            input_model=S.PreviewIn,
            output_model=S.PreviewOut,
            handler=S.fit_preview,
            idempotent=True,
            examples=({"phi": {"value": 37.0, "unit": "deg"}},),
        )
    )
    registry.register(
        Operation(
            name="view.select",
            kind="command",
            effect="view",
            capability=Capability.VIEW_WRITE,
            summary="Set the shared selection to the given spin or coupling IDs (replaces it).",
            input_model=SelectIn,
            output_model=SelectOut,
            handler=view_select,
            idempotent=True,
            revision_check="none: an absolute set; IDs are validated atomically and never reused",
            examples=({"ids": ["cpl_000002"]},),
        )
    )
    _register_science(registry)
    _register_history(registry)
    _register_proposals(registry)
    _register_jobs(registry)
    _register_view(registry)
    return registry


def _register_science(registry: Registry) -> None:
    """The M2 step 1 science operations (``dipolar_app.science_ops``)."""
    revision = "expected_science_revision (required)"
    for op in (
        Operation(
            name="model.set",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Set the model: kind (rigid, jump4), order model, frame and torsion domain.",
            input_model=S.ModelSetIn,
            output_model=S.ModelSetOut,
            handler=S.model_set,
            revision_check=revision,
            proposable=True,
            examples=(
                {
                    "kind": "jump4",
                    "order": "bisector-diagonal",
                    "frame": "bisector",
                    "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
                    "expected_science_revision": 1,
                },
            ),
        ),
        Operation(
            name="project.import_xyz",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Replace the project with one on imported XYZ coordinates (one spin per hydrogen, no couplings).",
            input_model=S.ImportXyzIn,
            output_model=S.ImportXyzOut,
            handler=S.import_xyz,
            revision_check=revision,
            proposable=True,
            examples=(
                {
                    "xyz": S.ETHANE_XYZ,
                    "name": "ethane",
                    "torsion": [2, 0, 1, 5],
                    "expected_science_revision": 0,
                },
            ),
        ),
        Operation(
            name="molecule.set_torsion",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Declare the fitted torsion of imported geometry: four atom indices (a, i, j, b), i–j a bond.",
            input_model=S.SetTorsionIn,
            output_model=S.SetTorsionOut,
            handler=S.set_torsion,
            revision_check=revision,
            proposable=True,
            examples=({"torsion": [3, 0, 1, 6], "expected_science_revision": 1},),
        ),
        Operation(
            name="couplings.reconcile",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="Read a couplings CSV against the project: the proposed label mapping and the diff (no change).",
            input_model=S.ReconcileIn,
            output_model=S.ReconcileOut,
            handler=S.couplings_reconcile,
            idempotent=True,
            examples=({"csv": "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n"},),
        ),
        Operation(
            name="couplings.import",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Replace the couplings with a CSV's, under a label mapping the caller confirmed (stable IDs kept).",
            input_model=S.ImportCouplingsIn,
            output_model=S.ImportCouplingsOut,
            handler=S.couplings_import,
            revision_check=revision,
            proposable=True,
            examples=(
                {
                    "csv": "spin_a,spin_b,D_obs_Hz,sigma_Hz\nH2,H3,-1124.6,0.5\n",
                    "confirmed_mapping": {"H2": "spn_000001", "H3": "spn_000002"},
                    "expected_science_revision": 1,
                },
            ),
        ),
        Operation(
            name="project.load",
            kind="command",
            effect="model",
            capability=Capability.SCIENCE_MUTATION,
            summary="Replace the project with a *.dipolar.json document (validated and migrated).",
            input_model=S.LoadIn,
            output_model=S.LoadOut,
            handler=S.project_load,
            revision_check=revision,
            proposable=True,
            max_request_bytes=S.LOAD_REQUEST_BYTES,
            examples=({"text": S.ethane_document(), "expected_science_revision": 0},),
        ),
        Operation(
            name="project.export",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The project as *.dipolar.json text, with a suggested file name.",
            input_model=S.ExportIn,
            output_model=S.ExportOut,
            handler=S.project_export,
            idempotent=True,
            examples=({},),
        ),
    ):
        registry.register(op)


def _register_history(registry: Registry) -> None:
    """Global chronological undo and redo (M2 step 2, ``dipolar_app.history_ops``)."""
    for name, handler, in_, out, summary in (
        (
            "history.undo",
            H.history_undo,
            H.UndoIn,
            H.UndoOut,
            "Undo the latest science change (a new, journaled command).",
        ),
        (
            "history.redo",
            H.history_redo,
            H.RedoIn,
            H.RedoOut,
            "Redo the latest undone science change (a new, journaled command).",
        ),
    ):
        registry.register(
            Operation(
                name=name,
                kind="command",
                effect="model",
                capability=Capability.SCIENCE_MUTATION,
                summary=summary,
                input_model=in_,
                output_model=out,
                handler=handler,
                revision_check="expected_science_revision (required)",
                proposable=True,
                examples=({"expected_science_revision": 2},),
            )
        )
    registry.register(
        Operation(
            name="history.log",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The science changes that can be undone and redone, the next first.",
            input_model=H.LogIn,
            output_model=H.LogOut,
            handler=H.history_log,
            idempotent=True,
            examples=({},),
        )
    )


def _register_proposals(registry: Registry) -> None:
    """Proposals that a human approves (M2 step 2, ``dipolar_app.proposal_ops``)."""
    registry.register(
        Operation(
            name="proposal.create",
            kind="command",
            effect="proposal",
            capability=Capability.PROPOSE,
            summary="Submit proposable commands as one change set for a human to accept; validated against "
            "the current state, nothing is applied.",
            input_model=P.CreateIn,
            output_model=P.CreateOut,
            handler=P.proposal_create,
            revision_check="each step's own expected_science_revision: step i expects base + i",
            max_request_bytes=P.MAX_PROPOSAL_BYTES + (1 << 20),
            examples=(
                {
                    "steps": [
                        {
                            "operation": "model.set",
                            "args": {
                                "kind": "jump4",
                                "order": "bisector-diagonal",
                                "frame": "bisector",
                                "phi_domain": [{"value": 0.0, "unit": "deg"}, {"value": 90.0, "unit": "deg"}],
                                "expected_science_revision": 1,
                            },
                        }
                    ],
                    "note": "try the four-site jump model",
                },
            ),
        )
    )
    registry.register(
        Operation(
            name="proposal.list",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The session's proposals (pending, and the latest decided), without their arguments.",
            input_model=P.ListIn,
            output_model=P.ListOut,
            handler=P.proposal_list,
            idempotent=True,
            examples=({}, {"status": "pending"}),
        )
    )
    registry.register(
        Operation(
            name="proposal.get",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="One proposal with every step's arguments.",
            input_model=P.GetIn,
            output_model=P.ProposalDetailOut,
            handler=P.proposal_get,
            idempotent=True,
            examples=({"proposal_id": "prp_000001"},),
        )
    )
    registry.register(
        Operation(
            name="proposal.accept",
            kind="command",
            effect="model",
            capability=Capability.APPROVE,
            summary="Accept a pending proposal (human only): all steps, or a dependency-closed subset, applied "
            "atomically as one transaction.",
            input_model=P.AcceptIn,
            output_model=P.AcceptOut,
            handler=P.proposal_accept,
            revision_check="the proposal's base science revision must be current (else PROPOSAL_STALE)",
            examples=({"proposal_id": "prp_000001"}, {"proposal_id": "prp_000001", "steps": [0]}),
        )
    )
    registry.register(
        Operation(
            name="proposal.reject",
            kind="command",
            effect="proposal",
            capability=Capability.APPROVE,
            summary="Reject a pending proposal (human only), with an optional reason.",
            input_model=P.RejectIn,
            output_model=P.RejectOut,
            handler=P.proposal_reject,
            examples=({"proposal_id": "prp_000001", "reason": "keep the bisector-diagonal model"},),
        )
    )


def _register_jobs(registry: Registry) -> None:
    """Jobs and runs (M2 step 3, ``dipolar_app.job_ops``; the runner is ``dipolar_app.jobs``)."""
    registry.register(
        Operation(
            name="fit.run",
            kind="command",
            effect="compute",
            capability=Capability.COMPUTE_JOB,
            summary="Submit the D3 fit of the current project as a job (estimates, validity, adequacy, and "
            "optional profile intervals under the reporting policy). Returns the job at once; read the run "
            "with job.wait and run.get.",
            input_model=J.FitRunIn,
            output_model=J.FitRunSubmitted,
            handler=J.fit_run,
            cost="job",
            revision_check="expected_science_revision (required): the job computes from that state",
            proposable=True,
            examples=({"expected_science_revision": 1}, {"intervals": True, "expected_science_revision": 1}),
        )
    )
    for op in (
        Operation(
            name="job.status",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="One job: its status, input identity, run or error, and whether its input is stale.",
            input_model=J.JobStatusIn,
            output_model=J.JobStatusOut,
            handler=J.job_status,
            idempotent=True,
            examples=({"job_id": "job_000001"},),
        ),
        Operation(
            name="job.wait",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary=f"Wait until a job finishes, at most timeout_s (≤ {J.MAX_WAIT_S:.0f} s); call again if it has not.",
            input_model=J.JobWaitIn,
            output_model=J.JobWaitOut,
            handler=J.job_wait,
            idempotent=True,
            examples=({"job_id": "job_000001", "timeout_s": 5.0},),
        ),
        Operation(
            name="job.list",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The session's jobs (unfinished, and the latest finished).",
            input_model=J.JobListIn,
            output_model=J.JobListOut,
            handler=J.job_list,
            idempotent=True,
            examples=({}, {"status": "unfinished"}),
        ),
        Operation(
            name="job.cancel",
            kind="command",
            effect="compute",
            capability=Capability.JOB_CANCEL,
            summary="Cancel an unfinished job (a propose-tier caller: its own jobs only). A finished job is left "
            "as it is.",
            input_model=J.JobCancelIn,
            output_model=J.JobCancelOut,
            handler=J.job_cancel,
            idempotent=True,
            examples=({"job_id": "job_000001"},),
        ),
        Operation(
            name="run.get",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="A run's result (the fit), verified against its stored hash, and whether it is stale.",
            input_model=J.RunGetIn,
            output_model=J.RunGetOut,
            handler=J.run_get,
            idempotent=True,
            examples=({"run_id": "run_000001"},),
        ),
        Operation(
            name="run.list",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The session's runs, newest first, each with its input identity and staleness.",
            input_model=J.RunListIn,
            output_model=J.RunListOut,
            handler=J.run_list,
            idempotent=True,
            examples=({},),
        ),
    ):
        registry.register(op)


def _register_view(registry: Registry) -> None:
    """View commands and perception (M2 step 4, ``dipolar_app.view_ops``; ``dipolar_app.scene``)."""
    absolute = "none: an absolute set of view state; never touches the science"
    for op in (
        Operation(
            name="view.set_camera",
            kind="command",
            effect="view",
            capability=Capability.VIEW_WRITE,
            summary="Set the shared camera (a perspective camera in Å) and viewport; camera null fits the "
            "molecule automatically.",
            input_model=V.SetCameraIn,
            output_model=V.SetCameraOut,
            handler=V.view_set_camera,
            idempotent=True,
            revision_check="optional expected_workspace_revision: a delayed gesture never overwrites a newer camera; "
            "otherwise an absolute set of view state",
            examples=(
                {"camera": None, "viewport": {"width": 800, "height": 600}},
                {
                    "camera": {
                        "position": {"xyz": [0.0, 0.0, 20.0], "unit": "Å"},
                        "target": {"xyz": [0.0, 0.0, 0.0], "unit": "Å"},
                        "up": {"xyz": [0.0, 1.0, 0.0]},
                        "fov": {"value": 45.0, "unit": "deg"},
                        "near": {"value": 1.0, "unit": "Å"},
                        "far": {"value": 100.0, "unit": "Å"},
                    },
                    "viewport": {"width": 640, "height": 480},
                },
            ),
        ),
        Operation(
            name="view.highlight",
            kind="command",
            effect="view",
            capability=Capability.VIEW_WRITE,
            summary="Set the shared highlights to the given spin or coupling IDs (replaces them).",
            input_model=V.HighlightIn,
            output_model=V.HighlightOut,
            handler=V.view_highlight,
            idempotent=True,
            revision_check=absolute,
            examples=({"ids": ["cpl_000001", "spn_000002"]},),
        ),
        Operation(
            name="view.set_layers",
            kind="command",
            effect="view",
            capability=Capability.VIEW_WRITE,
            summary="Show or hide the labels, bonds and coupling lines of the shared view.",
            input_model=V.LayersIn,
            output_model=V.LayersOut,
            handler=V.view_set_layers,
            idempotent=True,
            revision_check=absolute,
            examples=({"labels": True, "bonds": True, "couplings": False},),
        ),
        Operation(
            name="render.scene",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The scene description (04 §8.4): atoms with coordinates and projected screen positions, "
            "bonds, couplings with residuals, camera, layers, selection and highlights.",
            input_model=V.SceneIn,
            output_model=V.SceneOut,
            handler=V.render_scene,
            idempotent=True,
            examples=({},),
        ),
        Operation(
            name="render.view_svg",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="The shared view as an SVG, rendered on the server from the scene description.",
            input_model=V.SvgIn,
            output_model=V.SvgOut,
            handler=V.render_view_svg,
            idempotent=True,
            examples=({},),
        ),
        Operation(
            name="render.describe_view",
            kind="query",
            effect="none",
            capability=Capability.QUERY,
            summary="Describe the shared view: revisions, the run it reflects and whether it is stale, visible "
            "objects, selection, highlights, the largest residuals and warnings.",
            input_model=V.DescribeViewIn,
            output_model=V.DescribeViewOut,
            handler=V.describe_view,
            idempotent=True,
            examples=({},),
        ),
    ):
        registry.register(op)
