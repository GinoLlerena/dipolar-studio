import { useEffect, useRef, useState } from "react";
import { callOperation, type DescribeProjectOut, type PairOut, type ReconcileOut } from "../api";
import { comparable } from "../format";
import { blocker, collisions, diffCsv, effectiveMapping, labelsOf, sameMapping, spinOf } from "../reconcile";
import { strings } from "../strings";
import type { Studio, StudioState } from "../studio";
import { download, FileButton, Panel } from "./common";

// Importing a couplings CSV (D5; M3 step 2). Nothing changes until the user imports:
// couplings.reconcile is a query that proposes exact label matches and reports the diff, and the
// user confirms or changes every label's spin from the keyboard (one native select per label).
// The import sends exactly the mapping the last diff was computed for, at that diff's science
// revision, so a concurrent edit makes it fail with a conflict instead of importing blind.

type Props = { studio: Studio; state: StudioState; project: DescribeProjectOut };

/** Rows of each diff list shown; the counts are always complete. */
const SHOWN_ROWS = 200;

type Checked = { diff: ReconcileOut; mapping: Record<string, string> };

export function ImportCouplings({ studio, state, project }: Props) {
  const [file, setFile] = useState<{ name: string; csv: string } | null>(null);
  const [proposal, setProposal] = useState<ReconcileOut | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState<Checked | null>(null);
  const [checking, setChecking] = useState(false);
  const request = useRef(0);
  const revision = state.view?.science_revision ?? 0;

  const reset = () => {
    request.current += 1;
    setFile(null);
    setProposal(null);
    setChoices({});
    setChecked(null);
    setChecking(false);
  };

  /** Asks for the proposal, then for the diff under the user's mapping when it differs. Only the
   * latest request's answers are applied (a slower, older answer is dropped). */
  const check = async (csv: string, picks: Record<string, string>) => {
    const mine = ++request.current;
    setChecking(true);
    try {
      const base = await studio.run((t) => callOperation("couplings.reconcile", { csv }, t));
      if (mine !== request.current) return;
      if (!base) {
        setProposal(null);
        setChecked(null);
        return;
      }
      setProposal(base);
      const mapping = effectiveMapping(base.proposed_mapping, picks);
      if (sameMapping(mapping, base.proposed_mapping)) {
        setChecked({ diff: base, mapping });
        return;
      }
      const labels = labelsOf(base);
      if (labels.some((l) => !Object.hasOwn(mapping, l)) || collisions(mapping).size > 0) {
        setChecked(null); // the page says what is missing; nothing to ask the server yet
        return;
      }
      const diff = await studio.run((t) => callOperation("couplings.reconcile", { csv, mapping }, t));
      if (mine !== request.current) return;
      setChecked(diff ? { diff, mapping } : null);
    } finally {
      if (mine === request.current) setChecking(false);
    }
  };

  // Another client's edit changes what the import would do: check again at the new revision.
  const picksRef = useRef(choices);
  picksRef.current = choices;
  useEffect(() => {
    if (file) void check(file.csv, picksRef.current);
    // Only the revision triggers this; the file and choices are read when it fires.
  }, [revision]);

  const choose = (label: string, spin: string) => {
    const next = { ...choices, [label]: spin };
    setChoices(next);
    if (file) void check(file.csv, next);
  };

  const labels = proposal ? labelsOf(proposal) : [];
  const mapping = proposal ? effectiveMapping(proposal.proposed_mapping, choices) : {};
  const clash = collisions(mapping);
  const why = file ? blocker(checked?.diff ?? null, checked?.mapping ?? null, mapping, labels, revision) : "no-file";
  const diff = checked?.diff ?? null;
  const incoming = diff ? diff.added.length + diff.changed.length + diff.unchanged.length : 0;
  const spins = project.spins;

  return (
    <Panel title={strings.importCouplings} id="pane-import-couplings">
      <p className="help">{strings.csvHelp}</p>
      <div className="row">
        <FileButton
          label={strings.chooseCsv}
          accept=".csv,text/csv,text/plain"
          disabled={state.busy !== null}
          onText={(csv, name) => {
            setFile({ name, csv });
            setChoices({});
            setChecked(null);
            void check(csv, {});
          }}
        />
        {file && <span className="muted">{file.name}</span>}
        {checking && <span className="muted">{strings.checking}</span>}
      </div>

      {proposal && proposal.ignored_columns.length > 0 && (
        <p className="warn-text">{strings.ignoredColumns(proposal.ignored_columns.join(", "))}</p>
      )}
      {proposal && proposal.unresolved_pairs.length > 0 && (
        <p className="warn-text" role="alert">
          {strings.unresolvedPairs(proposal.unresolved_pairs.join(", "))}
        </p>
      )}

      {proposal && (
        <>
          <h3>{strings.mapping}</h3>
          <p className="help">{strings.mappingHelp}</p>
          <div className="scroll short">
            <table className="grid compact">
              <thead>
                <tr>
                  <th>{strings.colFileLabel}</th>
                  <th>{strings.colSpin}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {labels.map((label) => {
                  const spin = spinOf(mapping, label);
                  const others = (clash.get(spin) ?? []).filter((l) => l !== label);
                  const isProposed = spin !== "" && spinOf(proposal.proposed_mapping, label) === spin;
                  const id = `map-${label}`;
                  return (
                    <tr key={label}>
                      <td>
                        <label htmlFor={id}>{label}</label>
                      </td>
                      <td>
                        <select id={id} value={spin} onChange={(e) => choose(label, e.target.value)}>
                          <option value="">{strings.chooseSpin}</option>
                          {spins.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.label} ({s.id})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        {spin === "" ? (
                          <span className="warn-text">{strings.needsChoice}</span>
                        ) : others.length > 0 ? (
                          <span className="warn-text">{strings.collision(others.join(", "))}</span>
                        ) : isProposed ? (
                          <span className="muted">{strings.proposed}</span>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {diff && why === null && (
        <>
          <h3>{strings.diff}</h3>
          <p>{strings.diffCounts(diff.added.length, diff.changed.length, diff.removed.length, diff.unchanged.length)}</p>
          {(["changed", "added", "removed"] as const).map((kind) =>
            diff[kind].length === 0 ? null : <DiffTable key={kind} kind={kind} pairs={diff[kind]} />,
          )}
          {diff.removed.length > 0 && <p className="warn-text">{strings.removesWarning(diff.removed.length)}</p>}
          <button
            type="button"
            className="quiet"
            onClick={() => download(`${file?.name ?? "couplings"}.diff.csv`, diffCsv(diff), "text/csv")}
          >
            {strings.downloadDiff}
          </button>
        </>
      )}

      {file && (
        <div className="row">
          <button
            type="button"
            disabled={why !== null || state.busy !== null || checking}
            onClick={async () => {
              if (!checked) return;
              const done = await studio.command("couplings.import", (t) =>
                callOperation(
                  "couplings.import",
                  {
                    csv: file.csv,
                    confirmed_mapping: checked.mapping,
                    expected_science_revision: checked.diff.science_revision,
                  },
                  t,
                ),
              );
              if (done) reset();
            }}
          >
            {why === null ? strings.importNow(incoming) : strings.importCouplingsShort}
          </button>
          <button type="button" className="quiet" onClick={reset}>
            {strings.cancelImport}
          </button>
          {why !== null && <span className="muted">{strings.blocked[why]}</span>}
        </div>
      )}
    </Panel>
  );
}

/** A changed pair whose value and σ are the same: what changed is its provenance (the file's
 * labels, the σ source, the multiplicity or the equivalent pairs). */
function sameValues(p: PairOut): boolean {
  return (
    p.before !== null &&
    p.after !== null &&
    p.before.value.value === p.after.value.value &&
    p.before.sigma.value === p.after.sigma.value
  );
}

function DiffTable({ kind, pairs }: { kind: "added" | "changed" | "removed"; pairs: readonly PairOut[] }) {
  const pair = (v: PairOut["before"]) => (v ? { value: v.value.value, sigma: v.sigma.value } : null);
  return (
    <details open={kind === "changed"}>
      <summary>
        {strings.diffKind[kind]} ({pairs.length})
      </summary>
      <table className="grid compact">
        <thead>
          <tr>
            <th>{strings.colCoupling}</th>
            <th className="num">{strings.colBefore}</th>
            <th className="num">{strings.colAfter}</th>
          </tr>
        </thead>
        <tbody>
          {pairs.slice(0, SHOWN_ROWS).map((p) => {
            const [now, after] = comparable([pair(p.before), pair(p.after)]);
            return (
            <tr key={`${p.spin_a}-${p.spin_b}`}>
              <td>{p.label}</td>
              <td className="num">{now}</td>
              <td className="num">
                {after}
                {kind === "changed" && sameValues(p) && <div className="help">{strings.provenanceOnly}</div>}
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
      {pairs.length > SHOWN_ROWS && <p className="muted">{strings.moreRows(pairs.length - SHOWN_ROWS)}</p>}
    </details>
  );
}
