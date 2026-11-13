// The only module that talks to the backend (04 D13: "no private UI API").
// Every domain call is a registry operation through the single dispatcher. Two other calls exist:
// authentication (04 §8.5: exchanging the single-use launch code for this tab's token) and the
// change feed (D14), which only announces revisions, so the page re-reads through operations. A
// CI test scans web/src for any other network access.
//
// The types come from ./generated/contract.ts, which tools/codegen/ts_contract.py generates from
// the registry snapshot; CI fails if it is stale. `callOperation` is typed by operation name, so
// the arguments and the result always match the registry (M2 step 1b).

import type {
  Envelope,
  ErrorBody,
  Exact,
  OperationInput,
  OperationName,
  RequestEnvelope,
  SingleName,
} from "./generated/contract";

export type * from "./generated/contract";

export type TabSession = { ok: true; token: string; actor: string } | { ok: false; error: ErrorBody };

/** The request options (M2 step 2): an idempotency key for a command, or a dry run. */
export type RequestOptions = Pick<RequestEnvelope, "request_id" | "dry_run">;

// One operation per call (`SingleName`), with exactly its arguments (`Exact`): a union of names, or
// a variable carrying keys the schema forbids, does not compile (validation round 29).
export async function callOperation<N extends OperationName, A extends OperationInput<N>>(
  name: N & SingleName<N>,
  args: A & Exact<OperationInput<N>, A>,
  token: string,
  options: RequestOptions = {},
): Promise<Envelope<N>> {
  const body: RequestEnvelope = { args, ...options };
  const response = await fetch(`/api/v1/ops/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
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

/** Why an event stream ended. `refused` carries the server's error (UNAUTHENTICATED: the tab
 * needs a new launch link; QUOTA_EXCEEDED: too many streams are open). */
export type StreamEnd =
  | { reason: "closed" }
  | { reason: "aborted" }
  | { reason: "network" }
  | { reason: "refused"; status: number; error: ErrorBody | null };

// The change feed (D14; D10 note: an authenticated fetch stream, because the browser's built-in
// server-sent-events client cannot send the bearer token). `onText` receives decoded text in
// arbitrary pieces; feed.ts splits the lines. Resolves when the stream ends, and never rejects.
export async function streamEvents(
  token: string,
  after: number | null,
  onText: (text: string) => void,
  signal: AbortSignal,
): Promise<StreamEnd> {
  let response: Response;
  try {
    response = await fetch(after === null ? "/api/v1/events" : `/api/v1/events?after=${after}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      credentials: "omit",
      signal,
    });
  } catch {
    return signal.aborted ? { reason: "aborted" } : { reason: "network" };
  }
  if (!response.ok || !response.body) {
    let error: ErrorBody | null = null;
    try {
      error = ((await response.json()) as { error?: ErrorBody }).error ?? null;
    } catch {
      // not JSON: the status says enough
    }
    return { reason: "refused", status: response.status, error };
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return { reason: "closed" };
      onText(value);
    }
  } catch {
    return signal.aborted ? { reason: "aborted" } : { reason: "network" };
  } finally {
    reader.releaseLock();
  }
}
