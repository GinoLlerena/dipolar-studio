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
  const out: Record<string, string> = {};
  for (const [label, spin] of Object.entries({ ...proposed, ...choices })) if (spin !== "") out[label] = spin;
  return out;
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
  if (labels.some((label) => !(label in mapping))) return "unmapped";
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
