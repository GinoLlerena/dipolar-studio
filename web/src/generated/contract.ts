// GENERATED FILE: do not edit. Regenerate with `uv run python tools/codegen/ts_contract.py`.
// Source: packages/dipolar-app/registry.snapshot.json (sha256 cfee1f8b443d66c2e2fd8ff620f5aaae85fe10e5a31b568bb9f5eeaa78c1d4cf).
// CI fails if this file is stale (tests/test_ts_contract.py).
//
// Value constraints that TypeScript cannot express (bounds, lengths, patterns) appear as doc
// comments; the server enforces them.
/* eslint-disable */

export const CONTRACT_VERSION = "0.5.0";

/** Any JSON value. */
export type JsonValue =
  null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

// ---------------------------------------------------------------- definitions

export type Angstrom = {
  unit: "Å";
  /** exclusiveMinimum 0 */
  value: number;
};

export type AtomOut = {
  element: string;
  /** integer */
  index: number;
  x: number;
  y: number;
  z: number;
};

export type BasinOut = {
  chi2: number;
  delta_chi2: number;
  theta: NamedValue[];
};

export type CameraIn = {
  far: Angstrom;
  fov: Degrees;
  near: Angstrom;
  position: Vector;
  target: Vector;
  up: Direction;
};

export type CouplingOut = {
  equivalent_pairs: string[];
  /** pattern "^cpl_[0-9]{6}$" */
  id: string;
  label: string;
  /** integer */
  multiplicity: number;
  observable: string;
  sigma: Hertz;
  sigma_source: string;
  source_labels: [string, string] | null;
  /** pattern "^spn_[0-9]{6}$" */
  spin_a: string;
  /** pattern "^spn_[0-9]{6}$" */
  spin_b: string;
  value: Hertz;
};

export type Degrees = {
  unit: "deg";
  value: number;
};

export type Direction = {
  /** minItems 3, maxItems 3 */
  xyz: [number, number, number];
};

export type DryRunReport = {
  proposals_changed: string[];
  science: ScienceChanges | null;
  selection_after: string[] | null;
  would_revisions: WouldRevisions;
};

export type ErrorBody = {
  code: ErrorCode;
  details: { [key: string]: JsonValue };
  hint: string | null;
  message: string;
  offending_field: string | null;
};

export type ErrorCode = "INVALID_ARGUMENT" | "UNKNOWN_OPERATION" | "UNAUTHENTICATED" | "CAPABILITY_DENIED" | "PROPOSAL_REQUIRED" | "REVISION_CONFLICT" | "NO_PROJECT" | "ID_NOT_FOUND" | "OUT_OF_DOMAIN" | "PROJECT_NOT_READY" | "PAYLOAD_TOO_LARGE" | "IDEMPOTENCY_KEY_REUSED" | "PROPOSAL_STALE" | "PROPOSAL_CLOSED" | "NOTHING_TO_UNDO" | "QUOTA_EXCEEDED" | "JOURNAL_FAILED" | "INTERNAL";

export type FitRunOut = {
  adequate: boolean | null;
  basins: BasinOut[];
  chi2: number;
  couplings: FittedCoupling[];
  estimand: string;
  fit_version: string;
  frame: string;
  intervals: IntervalOut[];
  intervals_policy: string;
  model: ModelOut;
  /** integer */
  n_obs: number;
  notes: string[];
  nu: number | null;
  numerical_context: { [key: string]: string | number };
  order: NamedValue[];
  /** integer */
  p_free: number;
  p_value: number | null;
  rms_residual: Hertz;
  science_hash: string;
  /** integer */
  science_revision: number;
  statement: string;
  stderr: NamedValue[] | null;
  theta: NamedValue[];
  unidentified: NamedValue[][];
  validity: FitValidity;
};

export type FitSummary = {
  adequate: boolean | null;
  at_bound: string[];
  converged: boolean;
  notes: string[];
  p_value: number | null;
  physically_admissible: boolean | null;
  regular: boolean;
};

export type FitValidity = {
  at_bound: string[];
  converged: boolean;
  derivatives_resolved: boolean;
  inner_condition_number: number | null;
  /** integer */
  inner_parameters: number;
  /** integer */
  inner_rank: number;
  /** integer */
  joint_parameters: number;
  /** integer */
  joint_rank: number;
  physically_admissible: boolean | null;
  regular: boolean;
  search_resolved: boolean;
};

export type FittedCoupling = {
  calculated: Hertz;
  /** pattern "^cpl_[0-9]{6}$" */
  id: string;
  label: string;
  normalized_residual: number;
  observed: Hertz;
  residual: Hertz;
  sigma: Hertz;
};

export type Hertz = {
  unit: "Hz";
  value: number;
};

export type HistoryEntryOut = {
  actor: string;
  operation: string;
  /** integer */
  science_revision: number;
};

export type IdChanges = {
  /** maxItems 100 */
  added: string[];
  /** maxItems 100 */
  changed: string[];
  /** integer */
  n_added: number;
  /** integer */
  n_changed: number;
  /** integer */
  n_removed: number;
  /** maxItems 100 */
  removed: string[];
  truncated: boolean;
};

export type ImportedOut = {
  atoms: AtomOut[];
  kind: "imported";
  source_format: string;
  torsion: [number, number, number, number] | null;
};

export type IntervalOut = {
  estimate: number;
  kind: "profile";
  label: string;
  lower: number | null;
  note: string;
  parameter: string;
  supported: boolean;
  upper: number | null;
};

export type JobError = {
  code: string;
  message: string;
};

export type JobOut = {
  error: JobError | null;
  finished_at: string | null;
  /** pattern "^job_[0-9]{6}$" */
  id: string;
  input_hash: string;
  kind: "fit";
  options: { [key: string]: boolean };
  owner: string;
  proposed_by: string | null;
  run_id: string | null;
  science_hash: string;
  /** integer */
  science_revision: number;
  stale: boolean;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "interrupted";
  submitted_at: string;
};

export type ModelOut = {
  frame: "bisector" | "ring-a" | "input";
  kind: "rigid" | "jump4";
  order: "bisector-diagonal" | "c2z" | "c1";
  /** minItems 2, maxItems 2 */
  phi_domain: [Degrees, Degrees];
};

export type NamedValue = {
  name: string;
  value: number;
};

export type PairOut = {
  label: string;
  /** pattern "^spn_[0-9]{6}$" */
  spin_a: string;
  /** pattern "^spn_[0-9]{6}$" */
  spin_b: string;
};

export type PreviewValidity = {
  inner_condition_number: number | null;
  /** integer */
  inner_parameters: number;
  /** integer */
  inner_rank: number;
  physically_admissible: boolean | null;
};

export type ProposalOut = {
  accepted_steps: number[];
  /** integer */
  base_science_revision: number;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  expires_at: string;
  /** pattern "^prp_[0-9]{6}$" */
  id: string;
  note: string;
  proposer: string;
  reason: string;
  stale: boolean;
  status: "pending" | "accepted" | "rejected" | "expired";
  steps: StepOut[];
};

export type ResidualOut = {
  /** pattern "^(spn|cpl)_[0-9]{6}$" */
  id: string;
  label: string;
  residual: Hertz;
};

export type Revisions = {
  /** integer, minimum 0, maximum 9007199254740991 */
  science: number;
  /** integer, minimum 0, maximum 9007199254740991 */
  workspace: number;
};

export type RunOut = {
  created_at: string;
  /** pattern "^run_[0-9]{6}$" */
  id: string;
  input_hash: string;
  /** pattern "^job_[0-9]{6}$" */
  job_id: string;
  kind: "fit";
  owner: string;
  result_sha256: string;
  science_hash: string;
  /** integer */
  science_revision: number;
  stale: boolean;
};

export type SceneAtom = {
  element: string;
  id: string;
  label: string;
  position: Vector;
  screen: Screen;
};

export type SceneBond = {
  a: string;
  b: string;
};

export type SceneCamera = {
  automatic: boolean;
  far: Angstrom;
  fov: Degrees;
  near: Angstrom;
  position: Vector;
  target: Vector;
  /** minItems 3, maxItems 3 */
  up: [number, number, number];
};

export type SceneCoupling = {
  /** pattern "^(spn|cpl)_[0-9]{6}$" */
  id: string;
  length: Angstrom;
  residual: Hertz | null;
  /** pattern "^(spn|cpl)_[0-9]{6}$" */
  spin_a: string;
  /** pattern "^(spn|cpl)_[0-9]{6}$" */
  spin_b: string;
};

export type SceneLayers = {
  bonds: boolean;
  couplings: boolean;
  labels: boolean;
};

export type SceneRun = {
  available: boolean;
  /** pattern "^run_[0-9]{6}$" */
  run_id: string;
  stale: boolean;
};

export type SceneViewport = {
  /** integer */
  height: number;
  /** integer */
  width: number;
};

export type ScienceChanges = {
  couplings: IdChanges;
  geometry_changed: boolean;
  model_changed: boolean;
  name_changed: boolean;
  project_opened: boolean;
  science_hash_after: string;
  science_hash_before: string;
  spins: IdChanges;
};

export type Screen = {
  depth: number;
  visible: boolean;
  x: number;
  y: number;
};

export type SelectedObject = {
  /** pattern "^(spn|cpl)_[0-9]{6}$" */
  id: string;
  kind: "spin" | "coupling";
  label: string;
};

export type SpinOut = {
  atom: number | null;
  /** pattern "^spn_[0-9]{6}$" */
  id: string;
  isotope: string;
  label: string;
};

export type StepDetail = {
  args: { [key: string]: JsonValue };
  depends_on: number[];
  /** integer */
  index: number;
  operation: string;
};

export type StepIn = {
  args: { [key: string]: JsonValue };
  /** minLength 1, maxLength 100 */
  operation: string;
};

export type StepOut = {
  depends_on: number[];
  /** integer */
  index: number;
  operation: string;
};

export type StepResult = {
  /** integer */
  index: number;
  operation: string;
  result: { [key: string]: JsonValue };
};

export type TemplateOut = {
  kind: "template";
  r_cc: Angstrom;
  r_ch: Angstrom;
  r_inter: Angstrom;
  template: string;
};

export type Vector = {
  unit: "Å";
  /** minItems 3, maxItems 3 */
  xyz: [number, number, number];
};

export type Viewport = {
  /** integer, minimum 16, maximum 8192 */
  height: number;
  /** integer, minimum 16, maximum 8192 */
  width: number;
};

export type WouldRevisions = {
  /** integer, minimum 0, maximum 9007199254740991 */
  science: number;
  /** integer, minimum 0, maximum 9007199254740991 */
  workspace: number;
};

// ---------------------------------------------------------------- envelopes

export type ErrorEnvelope = {
  error: ErrorBody;
  ok: false;
  operation: string | null;
};

/** The body of every call: `args` plus the request options. */
export type RequestEnvelope = {
  args?: { [key: string]: JsonValue };
  /** default false */
  dry_run?: boolean;
  /** default null */
  request_id?: string | null;
};

/** A successful call of operation `N`; `result` has that operation's output type. It
 * distributes over a union of names, so `operation` and `result` always belong together. */
export type SuccessEnvelope<N extends OperationName = OperationName> = N extends OperationName
  ? {
      ok: true;
      operation: N;
      result: OperationOutput<N>;
      revisions: Revisions;
      replayed: boolean;
      dry_run: DryRunReport | null;
    }
  : never;

export type Envelope<N extends OperationName = OperationName> = SuccessEnvelope<N> | ErrorEnvelope;

// ---------------------------------------------------------------- operations

/** `couplings.import` input. */
export type ImportCouplingsIn = {
  /** maxProperties 1000, keys maxLength 200 */
  confirmed_mapping: {
    /** pattern "^spn_[0-9]{6}$" */
    [key: string]: string;
  };
  /** maxLength 1048576 */
  csv: string;
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
};

/** `couplings.import` output. */
export type ImportCouplingsOut = {
  /** integer */
  added: number;
  /** integer */
  changed: number;
  /** integer */
  n_couplings: number;
  not_ready_reason: string | null;
  ready_to_fit: boolean;
  /** integer */
  removed: number;
  science_hash: string;
  /** integer */
  science_revision: number;
  /** integer */
  unchanged: number;
};

/** `couplings.reconcile` input. */
export type ReconcileIn = {
  /** maxLength 1048576 */
  csv: string;
  /** default null */
  mapping?: {
    /** pattern "^spn_[0-9]{6}$" */
    [key: string]: string;
  } | null;
};

/** `couplings.reconcile` output. */
export type ReconcileOut = {
  added: PairOut[];
  changed: PairOut[];
  complete: boolean;
  ignored_columns: string[];
  proposed_mapping: {
    /** pattern "^spn_[0-9]{6}$" */
    [key: string]: string;
  };
  removed: PairOut[];
  science_hash: string;
  /** integer */
  science_revision: number;
  unchanged: PairOut[];
  unmatched_labels: string[];
  unresolved_pairs: string[];
};

/** `fit.preview` input. */
export type PreviewIn = {
  phi: Degrees;
};

/** `fit.preview` output. */
export type PreviewOut = {
  chi2: number;
  couplings: FittedCoupling[];
  estimand: string;
  frame: string;
  model: ModelOut;
  /** integer */
  n_obs: number;
  numerical_context: { [key: string]: string | number };
  order: NamedValue[];
  phi: Degrees;
  rms_residual: Hertz;
  science_hash: string;
  /** integer */
  science_revision: number;
  statement: string;
  validity: PreviewValidity;
};

/** `fit.run` input. */
export type FitRunIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
  /** default false */
  intervals?: boolean;
};

/** `fit.run` output. */
export type FitRunSubmitted = {
  job: JobOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `history.log` input. */
export type LogIn = { [key: string]: never };

/** `history.log` output. */
export type LogOut = {
  /** integer */
  max_undo: number;
  /** maxItems 100 */
  redo: HistoryEntryOut[];
  science_hash: string;
  /** integer */
  science_revision: number;
  /** maxItems 100 */
  undo: HistoryEntryOut[];
};

/** `history.redo` input. */
export type RedoIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
};

/** `history.redo` output. */
export type RedoOut = {
  redone: HistoryEntryOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `history.undo` input. */
export type UndoIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
};

/** `history.undo` output. */
export type UndoOut = {
  science_hash: string;
  /** integer */
  science_revision: number;
  undone: HistoryEntryOut;
};

/** `job.cancel` input. */
export type JobCancelIn = {
  /** pattern "^job_[0-9]{6}$" */
  job_id: string;
};

/** `job.cancel` output. */
export type JobCancelOut = {
  cancelled: boolean;
  job: JobOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `job.list` input. */
export type JobListIn = {
  /** default null */
  status?: "unfinished" | "finished" | null;
};

/** `job.list` output. */
export type JobListOut = {
  jobs: JobOut[];
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `job.status` input. */
export type JobStatusIn = {
  /** pattern "^job_[0-9]{6}$" */
  job_id: string;
};

/** `job.status` output. */
export type JobStatusOut = {
  job: JobOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `job.wait` input. */
export type JobWaitIn = {
  /** pattern "^job_[0-9]{6}$" */
  job_id: string;
  /** minimum 0, maximum 30.0, default 10.0 */
  timeout_s?: number;
};

/** `job.wait` output. */
export type JobWaitOut = {
  finished: boolean;
  job: JobOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `model.set` input. */
export type ModelSetIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
  frame: "bisector" | "ring-a" | "input";
  kind: "rigid" | "jump4";
  order: "bisector-diagonal" | "c2z" | "c1";
  /** minItems 2, maxItems 2 */
  phi_domain: [Degrees, Degrees];
};

/** `model.set` output. */
export type ModelSetOut = {
  model: ModelOut;
  not_ready_reason: string | null;
  ready_to_fit: boolean;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `molecule.set_torsion` input. */
export type SetTorsionIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
  /** minItems 4, maxItems 4 */
  torsion: [number, number, number, number];
};

/** `molecule.set_torsion` output. */
export type SetTorsionOut = {
  phi0: Degrees;
  science_hash: string;
  /** integer */
  science_revision: number;
  /** minItems 4, maxItems 4 */
  torsion: [number, number, number, number];
};

/** `project.describe` input. */
export type DescribeProjectIn = { [key: string]: never };

/** `project.describe` output. */
export type DescribeProjectOut = {
  couplings: CouplingOut[];
  equivalences: string[];
  estimand: string;
  frame: string;
  geometry: (TemplateOut & { atoms?: never; source_format?: never; torsion?: never }) | (ImportedOut & { r_cc?: never; r_ch?: never; r_inter?: never; template?: never });
  model: ModelOut;
  name: string;
  not_ready_reason: string | null;
  ready_to_fit: boolean;
  science_hash: string;
  /** integer */
  science_revision: number;
  source: string;
  spins: SpinOut[];
};

/** `project.export` input. */
export type ExportIn = { [key: string]: never };

/** `project.export` output. */
export type ExportOut = {
  filename: string;
  science_hash: string;
  /** integer */
  science_revision: number;
  text: string;
};

/** `project.import_xyz` input. */
export type ImportXyzIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
  /** minLength 1, maxLength 200 */
  name: string;
  /** default "c1" */
  order?: "c2z" | "c1";
  /** maxLength 2000, default "" */
  source?: string;
  /** default null */
  torsion?: [number, number, number, number] | null;
  /** maxLength 1048576 */
  xyz: string;
};

/** `project.import_xyz` output. */
export type ImportXyzOut = {
  /** integer */
  n_atoms: number;
  /** integer */
  n_spins: number;
  not_ready_reason: string | null;
  ready_to_fit: boolean;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `project.load` input. */
export type LoadIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
  /** maxLength 33554432 */
  text: string;
};

/** `project.load` output. */
export type LoadOut = {
  /** integer */
  n_couplings: number;
  /** integer */
  n_spins: number;
  name: string;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `project.open_example` input. */
export type OpenExampleIn = {
  /** integer, minimum 0, maximum 9007199254740991 */
  expected_science_revision: number;
  name: "biphenyl-synthetic";
};

/** `project.open_example` output. */
export type OpenExampleOut = {
  /** integer */
  n_couplings: number;
  /** integer */
  n_spins: number;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `proposal.accept` input. */
export type AcceptIn = {
  /** pattern "^prp_[0-9]{6}$" */
  proposal_id: string;
  /** default null */
  steps?: number[] | null;
};

/** `proposal.accept` output. */
export type AcceptOut = {
  proposal: ProposalOut;
  results: StepResult[];
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `proposal.create` input. */
export type CreateIn = {
  /** maxLength 2000, default "" */
  note?: string;
  /** minItems 1, maxItems 20 */
  steps: StepIn[];
};

/** `proposal.create` output. */
export type CreateOut = {
  proposal: ProposalOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `proposal.get` input. */
export type GetIn = {
  /** pattern "^prp_[0-9]{6}$" */
  proposal_id: string;
};

/** `proposal.get` output. */
export type ProposalDetailOut = {
  proposal: ProposalOut;
  science_hash: string;
  /** integer */
  science_revision: number;
  steps: StepDetail[];
};

/** `proposal.list` input. */
export type ListIn = {
  /** default null */
  status?: "pending" | "accepted" | "rejected" | "expired" | null;
};

/** `proposal.list` output. */
export type ListOut = {
  proposals: ProposalOut[];
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `proposal.reject` input. */
export type RejectIn = {
  /** pattern "^prp_[0-9]{6}$" */
  proposal_id: string;
  /** maxLength 2000, default "" */
  reason?: string;
};

/** `proposal.reject` output. */
export type RejectOut = {
  proposal: ProposalOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `render.describe_view` input. */
export type DescribeViewIn = { [key: string]: never };

/** `render.describe_view` output. */
export type DescribeViewOut = {
  fit: FitSummary | null;
  /** integer */
  hidden: number;
  highlights: SelectedObject[];
  phi: Degrees | null;
  phi_source: "run" | "imported" | "default" | null;
  project_name: string | null;
  project_open: boolean;
  run: SceneRun | null;
  /** integer */
  science_revision: number;
  selection: SelectedObject[];
  /** maxItems 5 */
  top_residuals: ResidualOut[];
  visible: string[];
  warnings: string[];
  /** integer */
  workspace_revision: number;
};

/** `render.scene` input. */
export type SceneIn = { [key: string]: never };

/** `render.scene` output. */
export type SceneOut = {
  atoms: SceneAtom[];
  bonds: SceneBond[];
  camera: SceneCamera;
  couplings: SceneCoupling[];
  draw_order: string[];
  fit: FitSummary | null;
  highlights: string[];
  layers: SceneLayers;
  phi: Degrees;
  phi_source: "run" | "imported" | "default";
  run: SceneRun | null;
  /** integer */
  science_revision: number;
  selection: string[];
  viewport: SceneViewport;
  /** integer */
  workspace_revision: number;
};

/** `render.view_svg` input. */
export type SvgIn = { [key: string]: never };

/** `render.view_svg` output. */
export type SvgOut = {
  /** integer */
  height: number;
  /** integer */
  science_revision: number;
  svg: string;
  /** integer */
  width: number;
  /** integer */
  workspace_revision: number;
};

/** `run.get` input. */
export type RunGetIn = {
  /** pattern "^run_[0-9]{6}$" */
  run_id: string;
};

/** `run.get` output. */
export type RunGetOut = {
  result: FitRunOut;
  run: RunOut;
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `run.list` input. */
export type RunListIn = { [key: string]: never };

/** `run.list` output. */
export type RunListOut = {
  runs: RunOut[];
  science_hash: string;
  /** integer */
  science_revision: number;
};

/** `view.highlight` input. */
export type HighlightIn = {
  /** maxItems 1000 */
  ids: string[];
};

/** `view.highlight` output. */
export type HighlightOut = {
  highlights: string[];
  /** integer */
  workspace_revision: number;
};

/** `view.select` input. */
export type SelectIn = {
  /** maxItems 1000 */
  ids: string[];
};

/** `view.select` output. */
export type SelectOut = {
  selection: SelectedObject[];
  /** integer */
  workspace_revision: number;
};

/** `view.set_camera` input. */
export type SetCameraIn = {
  camera: CameraIn | null;
  viewport: Viewport;
};

/** `view.set_camera` output. */
export type SetCameraOut = {
  automatic: boolean;
  /** integer */
  workspace_revision: number;
};

/** `view.set_layers` input. */
export type LayersIn = {
  bonds: boolean;
  couplings: boolean;
  labels: boolean;
};

/** `view.set_layers` output. */
export type LayersOut = {
  /** integer */
  workspace_revision: number;
};

/** Every registry operation, by name: its input (`args`) and output (`result`) types. */
export interface Operations {
  /** Replace the couplings with a CSV's, under a label mapping the caller confirmed (stable IDs kept). */
  "couplings.import": { input: ImportCouplingsIn; output: ImportCouplingsOut };
  /** Read a couplings CSV against the project: the proposed label mapping and the diff (no change). */
  "couplings.reconcile": { input: ReconcileIn; output: ReconcileOut };
  /** Preview the fit at a fixed torsion: order parameters re-solved, predictions and residuals. */
  "fit.preview": { input: PreviewIn; output: PreviewOut };
  /** Submit the D3 fit of the current project as a job (estimates, validity, adequacy, and optional profile intervals under the reporting policy). Returns the job at once; read the run with job.wait and run.get. */
  "fit.run": { input: FitRunIn; output: FitRunSubmitted };
  /** The science changes that can be undone and redone, the next first. */
  "history.log": { input: LogIn; output: LogOut };
  /** Redo the latest undone science change (a new, journaled command). */
  "history.redo": { input: RedoIn; output: RedoOut };
  /** Undo the latest science change (a new, journaled command). */
  "history.undo": { input: UndoIn; output: UndoOut };
  /** Cancel an unfinished job (a propose-tier caller: its own jobs only). A finished job is left as it is. */
  "job.cancel": { input: JobCancelIn; output: JobCancelOut };
  /** The session's jobs (unfinished, and the latest finished). */
  "job.list": { input: JobListIn; output: JobListOut };
  /** One job: its status, input identity, run or error, and whether its input is stale. */
  "job.status": { input: JobStatusIn; output: JobStatusOut };
  /** Wait until a job finishes, at most timeout_s (≤ 30 s); call again if it has not. */
  "job.wait": { input: JobWaitIn; output: JobWaitOut };
  /** Set the model: kind (rigid, jump4), order model, frame and torsion domain. */
  "model.set": { input: ModelSetIn; output: ModelSetOut };
  /** Declare the fitted torsion of imported geometry: four atom indices (a, i, j, b), i–j a bond. */
  "molecule.set_torsion": { input: SetTorsionIn; output: SetTorsionOut };
  /** Describe the project: geometry, spins, couplings, model, estimand and readiness to fit, with IDs. */
  "project.describe": { input: DescribeProjectIn; output: DescribeProjectOut };
  /** The project as *.dipolar.json text, with a suggested file name. */
  "project.export": { input: ExportIn; output: ExportOut };
  /** Replace the project with one on imported XYZ coordinates (one spin per hydrogen, no couplings). */
  "project.import_xyz": { input: ImportXyzIn; output: ImportXyzOut };
  /** Replace the project with a *.dipolar.json document (validated and migrated). */
  "project.load": { input: LoadIn; output: LoadOut };
  /** Replace the session's project with a bundled example dataset. */
  "project.open_example": { input: OpenExampleIn; output: OpenExampleOut };
  /** Accept a pending proposal (human only): all steps, or a dependency-closed subset, applied atomically as one transaction. */
  "proposal.accept": { input: AcceptIn; output: AcceptOut };
  /** Submit proposable commands as one change set for a human to accept; validated against the current state, nothing is applied. */
  "proposal.create": { input: CreateIn; output: CreateOut };
  /** One proposal with every step's arguments. */
  "proposal.get": { input: GetIn; output: ProposalDetailOut };
  /** The session's proposals (pending, and the latest decided), without their arguments. */
  "proposal.list": { input: ListIn; output: ListOut };
  /** Reject a pending proposal (human only), with an optional reason. */
  "proposal.reject": { input: RejectIn; output: RejectOut };
  /** Describe the shared view: revisions, the run it reflects and whether it is stale, visible objects, selection, highlights, the largest residuals and warnings. */
  "render.describe_view": { input: DescribeViewIn; output: DescribeViewOut };
  /** The scene description (04 §8.4): atoms with coordinates and projected screen positions, bonds, couplings with residuals, camera, layers, selection and highlights. */
  "render.scene": { input: SceneIn; output: SceneOut };
  /** The shared view as an SVG, rendered on the server from the scene description. */
  "render.view_svg": { input: SvgIn; output: SvgOut };
  /** A run's result (the fit), verified against its stored hash, and whether it is stale. */
  "run.get": { input: RunGetIn; output: RunGetOut };
  /** The session's runs, newest first, each with its input identity and staleness. */
  "run.list": { input: RunListIn; output: RunListOut };
  /** Set the shared highlights to the given spin or coupling IDs (replaces them). */
  "view.highlight": { input: HighlightIn; output: HighlightOut };
  /** Set the shared selection to the given spin or coupling IDs (replaces it). */
  "view.select": { input: SelectIn; output: SelectOut };
  /** Set the shared camera (a perspective camera in Å) and viewport; camera null fits the molecule automatically. */
  "view.set_camera": { input: SetCameraIn; output: SetCameraOut };
  /** Show or hide the labels, bonds and coupling lines of the shared view. */
  "view.set_layers": { input: LayersIn; output: LayersOut };
}

export type OperationName = keyof Operations;
export type OperationInput<N extends OperationName> = Operations[N]["input"];
export type OperationOutput<N extends OperationName> = Operations[N]["output"];

/** `N` when it is a single operation name, otherwise `never`: a call names one operation, so
 * its arguments and its result can be checked against that operation's types. */
export type SingleName<N extends OperationName> = { [K in N]: [Exclude<N, K>] extends [never] ? K : never }[N];

type JsonScalar = null | boolean | number | string;
type AllTrue<B> = false extends B ? false : true; // `never` (nothing to check) counts as true

/** `true` when every member of `A` fits some branch of `T` exactly, at every depth: no key that
 * the branch does not declare. Each member of a union-typed `A` is checked on its own, so a valid
 * member cannot mask an invalid one (round 30). A target that accepts any JSON value needs no
 * check, which also ends the recursion there. */
export type ExactOK<T, A> = [JsonValue] extends [T]
  ? true
  : A extends unknown
    ? true extends FitsSomeBranch<T, A>
      ? true
      : false
    : never;
type FitsSomeBranch<T, A> = T extends unknown ? Fits<T, A> : never;
type Fits<T, A> = T extends JsonScalar | undefined
  ? [A] extends [T]
    ? true
    : false
  : T extends readonly unknown[]
    ? A extends readonly unknown[]
      ? AllTrue<{ [I in keyof A]: ExactOK<I extends keyof T ? T[I] : T[number], A[I]> }[number]>
      : false
    : A extends JsonScalar | undefined | readonly unknown[]
      ? false
      : AllTrue<
          {
            [K in keyof A]-?: [A[K]] extends [never]
              ? true // a key that can hold no value is never sent
              : K extends keyof T
              ? ExactOK<T[K], A[K]>
              : string extends keyof T
                ? ExactOK<T[string & keyof T], A[K]>
                : false;
          }[keyof A]
        >;

/** Used as `args: A & Exact<T, A>`: `unknown` when `A` is exactly `T` (see `ExactOK`), otherwise
 * `never`, so the call does not compile. */
export type Exact<T, A> = false extends ExactOK<T, A> ? never : unknown;

/** Each operation's metadata from the registry. */
export const OPERATIONS = {
  "couplings.import": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "couplings.reconcile": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "fit.preview": { kind: "query", effect: "none", capability: "preview", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "fit.run": { kind: "command", effect: "compute", capability: "compute_job", cost: "job", idempotent: false, revision_check: "expected_science_revision (required): the job computes from that state", max_request_bytes: 1048576, proposable: true },
  "history.log": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "history.redo": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "history.undo": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "job.cancel": { kind: "command", effect: "compute", capability: "job_cancel", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "job.list": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "job.status": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "job.wait": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "model.set": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "molecule.set_torsion": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "project.describe": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "project.export": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "project.import_xyz": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "project.load": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 34603008, proposable: true },
  "project.open_example": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576, proposable: true },
  "proposal.accept": { kind: "command", effect: "model", capability: "approve", cost: "instant", idempotent: false, revision_check: "the proposal's base science revision must be current (else PROPOSAL_STALE)", max_request_bytes: 1048576, proposable: false },
  "proposal.create": { kind: "command", effect: "proposal", capability: "propose", cost: "instant", idempotent: false, revision_check: "each step's own expected_science_revision: step i expects base + i", max_request_bytes: 35651584, proposable: false },
  "proposal.get": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "proposal.list": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "proposal.reject": { kind: "command", effect: "proposal", capability: "approve", cost: "instant", idempotent: false, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "render.describe_view": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "render.scene": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "render.view_svg": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "run.get": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "run.list": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576, proposable: false },
  "view.highlight": { kind: "command", effect: "view", capability: "view_write", cost: "instant", idempotent: true, revision_check: "none: an absolute set of view state; never touches the science", max_request_bytes: 1048576, proposable: false },
  "view.select": { kind: "command", effect: "view", capability: "view_write", cost: "instant", idempotent: true, revision_check: "none: an absolute set; IDs are validated atomically and never reused", max_request_bytes: 1048576, proposable: false },
  "view.set_camera": { kind: "command", effect: "view", capability: "view_write", cost: "instant", idempotent: true, revision_check: "none: an absolute set of view state; never touches the science", max_request_bytes: 1048576, proposable: false },
  "view.set_layers": { kind: "command", effect: "view", capability: "view_write", cost: "instant", idempotent: true, revision_check: "none: an absolute set of view state; never touches the science", max_request_bytes: 1048576, proposable: false },
} as const satisfies Record<OperationName, unknown>;

