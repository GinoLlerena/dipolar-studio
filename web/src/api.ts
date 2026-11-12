// The only module that talks to the backend (04 D13: "no private UI API").
// Every domain call is a registry operation through the single dispatcher. The one exception is
// authentication (04 §8.5): exchanging the single-use launch code for this tab's token. A CI test
// scans web/src for any other network access.
//
// The types come from ./generated/contract.ts, which tools/codegen/ts_contract.py generates from
// the registry snapshot; CI fails if it is stale. `callOperation` is typed by operation name, so
// the arguments and the result always match the registry (M2 step 1b).

import type { Envelope, ErrorBody, Exact, OperationInput, OperationName, SingleName } from "./generated/contract";

export type * from "./generated/contract";

export type TabSession = { ok: true; token: string; actor: string } | { ok: false; error: ErrorBody };

// One operation per call (`SingleName`), with exactly its arguments (`Exact`): a union of names, or
// a variable carrying keys the schema forbids, does not compile (validation round 29).
export async function callOperation<N extends OperationName, A extends OperationInput<N>>(
  name: N & SingleName<N>,
  args: A & Exact<OperationInput<N>, A>,
  token: string,
): Promise<Envelope<N>> {
  const response = await fetch(`/api/v1/ops/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ args }),
    cache: "no-store",
    credentials: "omit",
  });
  return (await response.json()) as Envelope<N>;
}

// Exchange the launch code from the URL fragment for this tab's token (D10). The code is single
// use, so this runs at most once per page load.
// It never rejects: a network failure or a non-JSON reply becomes an error the page can show.
export async function startTabSession(code: string): Promise<TabSession> {
  const failure = (message: string): TabSession => ({
    ok: false,
    error: {
      code: "UNAUTHENTICATED",
      message,
      offending_field: null,
      hint: "run `dipolar open` for a new link",
      details: {},
    },
  });
  try {
    const response = await fetch("/api/v1/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
      cache: "no-store",
      credentials: "omit",
    });
    const body = (await response.json()) as { token?: string; actor?: string; error?: ErrorBody };
    if (response.ok && body.token && body.actor) return { ok: true, token: body.token, actor: body.actor };
    return body.error ? { ok: false, error: body.error } : failure(`the server answered HTTP ${response.status}`);
  } catch {
    return failure("could not reach dipolar serve to start this tab's session");
  }
}
