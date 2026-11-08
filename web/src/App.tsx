import { useCallback, useEffect, useRef, useState } from "react";
import {
  callOperation,
  type DescribeView,
  type Envelope,
  type OpenExample,
  type OperationError,
  type Preview,
  type Select,
} from "./api";
import { strings } from "./strings";

// The token may arrive in the URL fragment (never sent to the server). It is read once, removed
// from the address bar, and kept only in memory.
function tokenFromFragment(): string {
  const match = /(?:^|&)token=([^&]+)/.exec(window.location.hash.slice(1));
  if (match?.[1]) {
    history.replaceState(null, "", window.location.pathname + window.location.search);
    return decodeURIComponent(match[1]);
  }
  return "";
}

const fmt = (value: number, digits = 3) => value.toFixed(digits);

// Revisions never decrease (04 §8.1), so a view response older than the one shown is a late
// response and is discarded (D11).
function isNotOlder(next: DescribeView, shown: DescribeView | null): boolean {
  return (
    shown === null ||
    (next.science_revision >= shown.science_revision && next.workspace_revision >= shown.workspace_revision)
  );
}

export function App() {
  const [token, setToken] = useState(tokenFromFragment);
  const [connected, setConnected] = useState(false);
  const [view, setView] = useState<DescribeView | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [phi, setPhi] = useState("37");
  const [error, setError] = useState<OperationError | null>(null);
  const previewRequest = useRef(0); // only the latest preview request may update the page

  // isCurrent lets a caller drop a superseded response entirely: neither its result nor its
  // error may reach the page (D11 late-response rule).
  const run = useCallback(
    async <T,>(name: string, args: object, isCurrent: () => boolean = () => true): Promise<T | null> => {
      const envelope: Envelope<T> = await callOperation<T>(name, args, token);
      if (!isCurrent()) return null;
      if (!envelope.ok) {
        setError(envelope.error);
        return null;
      }
      setError(null);
      return envelope.result;
    },
    [token],
  );

  const refreshView = useCallback(async () => {
    const result = await run<DescribeView>("render.describe_view", {});
    if (result) {
      setView((shown) => (isNotOlder(result, shown) ? result : shown));
      setConnected(true);
    }
    return result;
  }, [run]);

  // The beta has one shared view (D15). Until the M2 event stream exists, poll it so that
  // changes made by other clients (the robot, a script) appear here.
  useEffect(() => {
    if (!connected) return;
    const timer = window.setInterval(() => void refreshView(), 2000);
    return () => window.clearInterval(timer);
  }, [connected, refreshView]);

  const openExample = async () => {
    const current = await refreshView();
    if (!current) return;
    const opened = await run<OpenExample>("project.open_example", {
      name: "biphenyl-synthetic",
      expected_science_revision: current.science_revision,
    });
    if (opened) {
      previewRequest.current++; // a preview still in flight belongs to the replaced project
      setPreview(null);
      await refreshView();
    }
  };

  const runPreview = async () => {
    const request = ++previewRequest.current;
    const isCurrent = () => request === previewRequest.current;
    const result = await run<Preview>("fit.preview", { phi: { value: Number(phi), unit: "deg" } }, isCurrent);
    if (result) setPreview(result);
  };

  const select = async (id: string) => {
    const result = await run<Select>("view.select", { ids: [id] });
    if (result) await refreshView();
  };

  const selected = new Set(view?.selection.map((s) => s.id) ?? []);
  const stale = preview !== null && view !== null && preview.science_revision !== view.science_revision;

  return (
    <main>
      <header>
        <h1>{strings.title}</h1>
        <p className="tagline">{strings.tagline}</p>
        <p className="status">{strings.status}</p>
      </header>

      <section className="panel">
        <label htmlFor="token">{strings.tokenLabel}</label>
        <div className="row">
          <input
            id="token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value.trim())}
          />
          <button type="button" disabled={!token} onClick={() => void refreshView()}>
            {strings.connect}
          </button>
        </div>
        <p className="help">{strings.tokenHelp}</p>
      </section>

      {error && (
        <section className="error" role="alert">
          <strong>{error.code}</strong>: {error.message}
          {error.offending_field && <code> ({error.offending_field})</code>}
          {error.hint && <div className="help">{error.hint}</div>}
        </section>
      )}

      {connected && view && (
        <section className="panel">
          <p className="meta">
            {view.project_open ? view.project_name : strings.noProject} ·{" "}
            {strings.revisions(view.science_revision, view.workspace_revision)}
          </p>
          <p className="meta">
            {strings.selection}:{" "}
            {view.selection.length ? view.selection.map((s) => s.label).join(", ") : strings.nothingSelected}
          </p>
          <div className="row">
            <button type="button" onClick={() => void openExample()}>
              {strings.openExample}
            </button>
          </div>
          {view.project_open && (
            <div className="row">
              <label htmlFor="phi">{strings.phiLabel}</label>
              <input id="phi" type="number" min="0" max="90" step="0.1" value={phi} onChange={(e) => setPhi(e.target.value)} />
              <button type="button" onClick={() => void runPreview()}>
                {strings.preview}
              </button>
            </div>
          )}
        </section>
      )}

      {preview && (
        <section className={stale ? "panel stale" : "panel"}>
          <p className="meta">
            φ = {fmt(preview.phi.value, 4)}° · S<sub>zz</sub> = {fmt(preview.order.Szz, 5)} · Δ ={" "}
            {fmt(preview.order.Delta, 5)} · χ² = {fmt(preview.chi2, 3)} (N = {preview.n_obs}) · RMS ={" "}
            {fmt(preview.rms_residual.value, 3)} Hz
          </p>
          <p className="meta">
            {strings.rank(preview.validity.inner_rank, preview.validity.inner_parameters)} ·{" "}
            {strings.condition(preview.validity.inner_condition_number)} ·{" "}
            {strings.admissible(preview.validity.physically_admissible)}
          </p>
          <p className="help">{preview.statement}</p>
          <p className="help">{strings.selectHint}</p>
          <table>
            <thead>
              <tr>
                <th>{strings.colCoupling}</th>
                <th>{strings.colObserved}</th>
                <th>{strings.colCalculated}</th>
                <th>{strings.colResidual}</th>
                <th>{strings.colNormalized}</th>
              </tr>
            </thead>
            <tbody>
              {preview.couplings.map((c) => (
                <tr
                  key={c.id}
                  className={selected.has(c.id) ? "selected" : undefined}
                  aria-selected={selected.has(c.id)}
                  tabIndex={0}
                  onClick={() => void select(c.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") void select(c.id);
                  }}
                >
                  <td>{c.label}</td>
                  <td>{fmt(c.observed.value)}</td>
                  <td>{fmt(c.calculated.value)}</td>
                  <td>{fmt(c.residual.value)}</td>
                  <td>{fmt(c.normalized_residual, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <footer>{strings.credits}</footer>
    </main>
  );
}
