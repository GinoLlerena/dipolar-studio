// The only module that talks to the backend (04 D13: "no private UI API").
// Every domain call is a registry operation through the single dispatcher. The one exception is
// authentication (04 §8.5): exchanging the single-use launch code for this tab's token. A CI test
// scans web/src for any other network access. The types below are hand-written for M0; M2
// generates them from the registry snapshot.

export type Quantity<U extends string> = { value: number; unit: U };

export type OperationError = {
  code: string;
  message: string;
  offending_field: string | null;
  hint: string | null;
};

export type TabSession = { ok: true; token: string; actor: string } | { ok: false; error: OperationError };

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

// Exchange the launch code from the URL fragment for this tab's token (D10). The code is single
// use, so this runs at most once per page load.
// It never rejects: a network failure or a non-JSON reply becomes an error the page can show.
export async function startTabSession(code: string): Promise<TabSession> {
  const failure = (message: string): TabSession => ({
    ok: false,
    error: { code: "UNAUTHENTICATED", message, offending_field: null, hint: "run `dipolar open` for a new link" },
  });
  try {
    const response = await fetch("/api/v1/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
      cache: "no-store",
      credentials: "omit",
    });
    const body = (await response.json()) as { token?: string; actor?: string; error?: OperationError };
    if (response.ok && body.token && body.actor) return { ok: true, token: body.token, actor: body.actor };
    return body.error ? { ok: false, error: body.error } : failure(`the server answered HTTP ${response.status}`);
  } catch {
    return failure("could not reach dipolar serve to start this tab's session");
  }
}
