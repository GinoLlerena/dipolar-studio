// Couplings CSV reconciliation, client side (D5; M3 step 2). The server proposes a mapping from
// the file's labels to the project's spins (exact label matches only) and the diff the import
// would make; the user confirms or changes every label's spin before anything is imported. Pure
// functions with type-only imports: tests/reconcile.test.ts runs them under Node.

import type { ReconcileOut } from "./generated/contract";

/** The file's labels in a stable order: the matched ones and the ones that need a choice. */
export function labelsOf(diff: Pick<ReconcileOut, "proposed_mapping" | "unmatched_labels">): string[] {
  return [...new Set([...Object.keys(diff.proposed_mapping), ...diff.unmatched_labels])].sort((a, b) =>
    a < b ? -1 : a > b ? 1 : 0,
  );
}

/** The mapping the user is looking at: the proposal, overridden by the user's choices. An empty
 * choice ("") removes a label from the mapping, so it must be chosen again. */
export function effectiveMapping(
  proposed: Readonly<Record<string, string>>,
  choices: Readonly<Record<string, string>>,
): Record<string, string> {
  // Built with a Map and Object.fromEntries, which define own properties: assigning to a plain
  // object would turn a label like "__proto__" into a prototype change (round 41).
  const merged = new Map(Object.entries(proposed));
  for (const [label, spin] of Object.entries(choices)) merged.set(label, spin);
  return Object.fromEntries([...merged].filter(([, spin]) => spin !== ""));
}

/** The spin chosen for `label`, or "" (own properties only: labels are arbitrary text). */
export function spinOf(mapping: Readonly<Record<string, string>>, label: string): string {
  return Object.hasOwn(mapping, label) ? (mapping[label] ?? "") : "";
}

/** The spins chosen for more than one label, each with its labels: the mapping must be
 * one-to-one, and the page says so before asking the server. */
export function collisions(mapping: Readonly<Record<string, string>>): Map<string, string[]> {
  const bySpin = new Map<string, string[]>();
  for (const [label, spin] of Object.entries(mapping)) bySpin.set(spin, [...(bySpin.get(spin) ?? []), label]);
  for (const [spin, labels] of bySpin) if (labels.length < 2) bySpin.delete(spin);
  return bySpin;
}

/** Why the import cannot run yet, or null when it can. The diff must be for this exact mapping
 * and the current science revision, complete, and with nothing left to choose. */
export function blocker(
  diff: ReconcileOut | null,
  checkedMapping: Readonly<Record<string, string>> | null,
  mapping: Readonly<Record<string, string>>,
  labels: readonly string[],
  scienceRevision: number,
): "no-file" | "unmapped" | "collision" | "unresolved" | "outdated" | null {
  if (diff === null || checkedMapping === null) return "no-file";
  if (labels.some((label) => !Object.hasOwn(mapping, label))) return "unmapped";
  if (collisions(mapping).size > 0) return "collision";
  if (diff.unresolved_pairs.length > 0) return "unresolved";
  if (!sameMapping(checkedMapping, mapping) || diff.science_revision !== scienceRevision || !diff.complete) {
    return "outdated";
  }
  return null;
}

export function sameMapping(a: Readonly<Record<string, string>>, b: Readonly<Record<string, string>>): boolean {
  const ka = Object.keys(a);
  return ka.length === Object.keys(b).length && ka.every((k) => Object.hasOwn(b, k) && a[k] === b[k]);
}

type Values = { value: { value: number }; sigma: { value: number } } | null;
type Pair = { label: string; spin_a: string; spin_b: string; before: Values; after: Values };

/** The whole diff as CSV, for inspection outside the page: every pair, the values at full
 * precision (round 41: the page shows the first rows of each kind). Text cells are quoted, and
 * any text cell that does not start with a letter or a digit is prefixed with an apostrophe, so a
 * spreadsheet reads it as text: formula characters, but also a leading space, tab, CR or LF before
 * one (round 42; OWASP CSV injection guidance). */
export function diffCsv(diff: Record<"added" | "changed" | "removed" | "unchanged", readonly Pair[]>): string {
  const cell = (text: string) => {
    const safe = text === "" || /^[\p{L}\p{N}]/u.test(text) ? text : `'${text}`;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const num = (v: number | undefined) => (v === undefined ? "" : String(v));
  const rows = ["kind,pair,spin_a,spin_b,D_now_Hz,sigma_now_Hz,D_after_Hz,sigma_after_Hz"];
  for (const kind of ["changed", "added", "removed", "unchanged"] as const) {
    for (const p of diff[kind]) {
      rows.push(
        [
          kind,
          cell(p.label),
          p.spin_a,
          p.spin_b,
          num(p.before?.value.value),
          num(p.before?.sigma.value),
          num(p.after?.value.value),
          num(p.after?.sigma.value),
        ].join(","),
      );
    }
  }
  return `${rows.join("\n")}\n`;
}
