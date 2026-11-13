import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { type ErrorBody, startTabSession, type TabSession } from "./api";
import { strings } from "./strings";
import { Studio } from "./studio";
import { StatusBar, TitleBar, type Workspace } from "./ui/Chrome";
import { DataWorkspace } from "./ui/DataWorkspace";
import { FitWorkspace } from "./ui/FitWorkspace";
import { StructureWorkspace } from "./ui/StructureWorkspace";

// Browser hand-off (D10, M0 spike 3). `dipolar open` opens /#launch=<code>. The fragment never
// reaches the server; it is removed from the address bar before anything else happens, and the
// single-use code is exchanged once per page load for this tab's token. The token lives in
// sessionStorage: scoped to this origin and tab, kept across reloads, gone when the tab closes.
const TOKEN_KEY = "dipolar.tab-token";

function takeLaunchCode(): string | null {
  const match = /(?:^|&)launch=([^&]+)/.exec(window.location.hash.slice(1));
  if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
  if (!match?.[1]) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return ""; // a malformed link: the exchange is refused and the page explains what to do
  }
}

const launchCode = takeLaunchCode();
// Once per load. startTabSession never rejects, so the page always leaves the "connecting" state.
const exchange: Promise<TabSession> | null = launchCode !== null ? startTabSession(launchCode) : null;

export function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? "");
  const [pending, setPending] = useState(exchange !== null);
  const [error, setError] = useState<ErrorBody | null>(null);

  useEffect(() => {
    if (exchange === null) return;
    let live = true;
    void exchange.then((session) => {
      if (!live) return;
      setPending(false);
      if (session.ok) {
        sessionStorage.setItem(TOKEN_KEY, session.token);
        setToken(session.token);
        setError(null);
      } else {
        setError(session.error);
      }
    });
    return () => {
      live = false;
    };
  }, []);

  if (pending) return <p className="launch muted">{strings.connecting}</p>;
  if (!token) {
    return (
      <main className="launch">
        <h1>{strings.title}</h1>
        <p className="muted">{strings.tagline}</p>
        {error && <ErrorBanner error={error} />}
        <p>{strings.needLaunch}</p>
        <pre>
          <code>{strings.launchCommand}</code>
        </pre>
        <p className="help">{strings.launchHelp}</p>
        <footer className="credits">{strings.credits}</footer>
      </main>
    );
  }
  return (
    <Workbench
      token={token}
      onLostSession={(lost) => {
        // The server restarted or the token was revoked: this tab needs a new launch link.
        sessionStorage.removeItem(TOKEN_KEY);
        setError(lost);
        setToken("");
      }}
    />
  );
}

function ErrorBanner({ error, onDismiss }: { error: ErrorBody; onDismiss?: () => void }) {
  return (
    <div className="error" role="alert">
      <div>
        <strong>{error.code}</strong>: {error.message}
        {error.offending_field && <code> ({error.offending_field})</code>}
        {error.hint && <div className="help">{error.hint}</div>}
      </div>
      {onDismiss && (
        <button type="button" className="quiet" onClick={onDismiss} aria-label={strings.dismiss}>
          ✕
        </button>
      )}
    </div>
  );
}

function Workbench({ token, onLostSession }: { token: string; onLostSession: (error: ErrorBody) => void }) {
  // One store per token; it calls the latest onLostSession, so the store never has to be rebuilt.
  const onLostSessionRef = useLatest(onLostSession);
  const studio = useMemo(() => new Studio(token, (e) => onLostSessionRef.current(e)), [token, onLostSessionRef]);
  useEffect(() => {
    studio.start();
    return () => studio.stop();
  }, [studio]);
  const state = useSyncExternalStore(studio.subscribe, studio.getSnapshot);
  const [workspace, setWorkspace] = useState<Workspace>("data");
  const runId = state.view?.run?.run_id;
  useEffect(() => {
    if (runId) void studio.loadResult(runId); // the status bar shows the current run's χ²
  }, [studio, runId]);

  return (
    <div className="shell">
      <TitleBar studio={studio} state={state} workspace={workspace} onWorkspace={setWorkspace} />
      {state.error && <ErrorBanner error={state.error} onDismiss={() => studio.dismissError()} />}
      <div className="content">
        {workspace === "structure" ? (
          <StructureWorkspace studio={studio} state={state} />
        ) : workspace === "data" ? (
          <DataWorkspace studio={studio} state={state} />
        ) : (
          <FitWorkspace studio={studio} state={state} />
        )}
        <footer className="credits">{strings.credits}</footer>
      </div>
      <StatusBar state={state} />
    </div>
  );
}

/** A ref that always holds the latest value (for callbacks read later, outside render). */
function useLatest<T>(value: T): { readonly current: T } {
  const [ref] = useState(() => ({ current: value }));
  ref.current = value;
  return ref;
}
