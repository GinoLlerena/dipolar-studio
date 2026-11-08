// UI strings are externalised from the start (plan §4), so translation needs no code changes.
export const strings = {
  title: "Dipolar Studio",
  tagline: "Molecular conformation and liquid-crystal order from NMR dipolar couplings",
  status: "Milestone M0 vertical slice: a thin client of the operation registry.",
  credits:
    "A new implementation of the 1998 graduation thesis by Gino Llerena and Marco Idrogo (advisor: Dr. Jaime Avalos).",
  tokenLabel: "Session token",
  tokenHelp:
    "Copy the user token from the ready file that dipolar serve wrote (provisional until the M0 D10 spike decides the browser hand-off).",
  connect: "Connect",
  openExample: "Open the synthetic biphenyl example",
  phiLabel: "Torsion φ (deg)",
  preview: "Preview",
  noProject: "No project is open.",
  revisions: (science: number, workspace: number) => `science revision ${science} · workspace revision ${workspace}`,
  selection: "Selection",
  nothingSelected: "nothing selected",
  colCoupling: "Coupling",
  colObserved: "Observed (Hz)",
  colCalculated: "Calculated (Hz)",
  colResidual: "Residual (Hz)",
  colNormalized: "Residual / σ",
  admissible: (ok: boolean) => (ok ? "physically admissible" : "NOT physically admissible"),
  rank: (rank: number, params: number) => `inner rank ${rank} of ${params}`,
  condition: (value: number | null) => (value === null ? "condition number: not finite" : `condition ${value.toFixed(3)}`),
  selectHint: "Click a row to select that coupling in the shared view.",
} as const;
