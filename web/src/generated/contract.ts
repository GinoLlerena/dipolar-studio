// GENERATED FILE: do not edit. Regenerate with `uv run python tools/codegen/ts_contract.py`.
// Source: packages/dipolar-app/registry.snapshot.json (sha256 0d181234562eda5e1db208e7f3121f11e6711845f9fbd29de96d1fd4e1aaec02).
// CI fails if this file is stale (tests/test_ts_contract.py).
//
// Value constraints that TypeScript cannot express (bounds, lengths, patterns) appear as doc
// comments; the server enforces them.
/* eslint-disable */

export const CONTRACT_VERSION = "0.2.0";

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

export type ErrorBody = {
  code: ErrorCode;
  details: { [key: string]: JsonValue };
  hint: string | null;
  message: string;
  offending_field: string | null;
};

export type ErrorCode = "INVALID_ARGUMENT" | "UNKNOWN_OPERATION" | "UNAUTHENTICATED" | "CAPABILITY_DENIED" | "PROPOSAL_REQUIRED" | "REVISION_CONFLICT" | "NO_PROJECT" | "ID_NOT_FOUND" | "OUT_OF_DOMAIN" | "PROJECT_NOT_READY" | "PAYLOAD_TOO_LARGE" | "JOURNAL_FAILED" | "INTERNAL";

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

export type Revisions = {
  /** integer, minimum 0, maximum 9007199254740991 */
  science: number;
  /** integer, minimum 0, maximum 9007199254740991 */
  workspace: number;
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

export type TemplateOut = {
  kind: "template";
  r_cc: Angstrom;
  r_ch: Angstrom;
  r_inter: Angstrom;
  template: string;
};

// ---------------------------------------------------------------- envelopes

export type ErrorEnvelope = {
  error: ErrorBody;
  ok: false;
  operation: string | null;
};

/** A successful call of operation `N`; `result` has that operation's output type. */
export type SuccessEnvelope<N extends OperationName = OperationName> = {
  ok: true;
  operation: N;
  result: OperationOutput<N>;
  revisions: Revisions;
};

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
  /** default false */
  intervals?: boolean;
};

/** `fit.run` output. */
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
  geometry: TemplateOut | ImportedOut;
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

/** `render.describe_view` input. */
export type DescribeViewIn = { [key: string]: never };

/** `render.describe_view` output. */
export type DescribeViewOut = {
  project_name: string | null;
  project_open: boolean;
  /** integer */
  science_revision: number;
  selection: SelectedObject[];
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

/** Every registry operation, by name: its input (`args`) and output (`result`) types. */
export interface Operations {
  /** Replace the couplings with a CSV's, under a label mapping the caller confirmed (stable IDs kept). */
  "couplings.import": { input: ImportCouplingsIn; output: ImportCouplingsOut };
  /** Read a couplings CSV against the project: the proposed label mapping and the diff (no change). */
  "couplings.reconcile": { input: ReconcileIn; output: ReconcileOut };
  /** Preview the fit at a fixed torsion: order parameters re-solved, predictions and residuals. */
  "fit.preview": { input: PreviewIn; output: PreviewOut };
  /** Fit the project's model (D3): estimates, validity, adequacy, and optional profile intervals under the reporting policy. */
  "fit.run": { input: FitRunIn; output: FitRunOut };
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
  /** Describe the shared view: revisions and the current selection, with labels. */
  "render.describe_view": { input: DescribeViewIn; output: DescribeViewOut };
  /** Set the shared selection to the given spin or coupling IDs (replaces it). */
  "view.select": { input: SelectIn; output: SelectOut };
}

export type OperationName = keyof Operations;
export type OperationInput<N extends OperationName> = Operations[N]["input"];
export type OperationOutput<N extends OperationName> = Operations[N]["output"];

/** Each operation's metadata from the registry. */
export const OPERATIONS = {
  "couplings.import": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576 },
  "couplings.reconcile": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576 },
  "fit.preview": { kind: "query", effect: "none", capability: "preview", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576 },
  "fit.run": { kind: "query", effect: "none", capability: "compute_job", cost: "seconds", idempotent: true, revision_check: "none", max_request_bytes: 1048576 },
  "model.set": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576 },
  "molecule.set_torsion": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576 },
  "project.describe": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576 },
  "project.export": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576 },
  "project.import_xyz": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576 },
  "project.load": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 34603008 },
  "project.open_example": { kind: "command", effect: "model", capability: "science_mutation", cost: "instant", idempotent: false, revision_check: "expected_science_revision (required)", max_request_bytes: 1048576 },
  "render.describe_view": { kind: "query", effect: "none", capability: "query", cost: "instant", idempotent: true, revision_check: "none", max_request_bytes: 1048576 },
  "view.select": { kind: "command", effect: "view", capability: "view_write", cost: "instant", idempotent: true, revision_check: "none: an absolute set; IDs are validated atomically and never reused", max_request_bytes: 1048576 },
} as const satisfies Record<OperationName, unknown>;

