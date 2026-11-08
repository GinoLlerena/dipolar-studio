// The only module that talks to the backend (04 D13: "no private UI API").
// Every call is a registry operation through the single dispatcher. A CI test scans web/src for
// any other network access. The types below are hand-written for M0; M2 generates them from the
// registry snapshot.

export type Quantity<U extends string> = { value: number; unit: U };

export type OperationError = {
  code: string;
  message: string;
  offending_field: string | null;
  hint: string | null;
};

export type Envelope<T> =
  | { ok: true; operation: string; result: T; revisions: { science: number; workspace: number } }
  | { ok: false; operation: string | null; error: OperationError };

export type SelectedObject = { id: string; kind: "spin" | "coupling"; label: string };

export type DescribeView = {
  science_revision: number;
  workspace_revision: number;
  project_open: boolean;
  project_name: string | null;
  selection: SelectedObject[];
};

export type PreviewCoupling = {
  id: string;
  label: string;
  observed: Quantity<"Hz">;
  sigma: Quantity<"Hz">;
  calculated: Quantity<"Hz">;
  residual: Quantity<"Hz">;
  normalized_residual: number;
};

export type Preview = {
  science_revision: number;
  estimand: string;
  phi: Quantity<"deg">;
  order: { Szz: number; Delta: number };
  couplings: PreviewCoupling[];
  chi2: number;
  n_obs: number;
  rms_residual: Quantity<"Hz">;
  validity: {
    inner_rank: number;
    inner_parameters: number;
    inner_condition_number: number | null;
    physically_admissible: boolean;
  };
  statement: string;
};

export type OpenExample = { science_revision: number; science_hash: string; n_spins: number; n_couplings: number };
export type Select = { workspace_revision: number; selection: SelectedObject[] };

export async function callOperation<T>(name: string, args: object, token: string): Promise<Envelope<T>> {
  const response = await fetch(`/api/v1/ops/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ args }),
    cache: "no-store",
    credentials: "omit",
  });
  return (await response.json()) as Envelope<T>;
}
