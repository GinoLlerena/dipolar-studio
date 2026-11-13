import type { FittedCoupling } from "../api";
import { fixed } from "../format";
import { strings } from "../strings";

// Results charts (ui-design §4). Colour comes from CSS classes (the misfit ramp m0–m5), so both
// themes and forced-colours mode style them; every chart has a table with the same numbers.

/** The misfit step (0–5) for |residual|/σ: the same ramp as the arcs in the structure view. */
export function misfitStep(normalized: number): number {
  const z = Math.abs(normalized);
  if (!Number.isFinite(z)) return 5;
  return z < 0.5 ? 0 : z < 1 ? 1 : z < 1.5 ? 2 : z < 2 ? 3 : z < 3 ? 4 : 5;
}

const BAR_W = 96;
const BAR_H = 12;
const PER_SIGMA = BAR_W / 6; // ±3σ fills the width

/** A diverging bar for residual/σ on a fixed ±3σ scale, with a shaded ±1σ band. Beyond ±3σ the
 * bar stops at the edge and ends in an arrow. */
export function ResidualBar({ normalized }: { normalized: number }) {
  const mid = BAR_W / 2;
  const clipped = Math.max(-3, Math.min(3, Number.isFinite(normalized) ? normalized : 3));
  const end = mid + clipped * PER_SIGMA;
  const over = Math.abs(normalized) > 3;
  const x = Math.min(mid, end);
  const width = Math.abs(end - mid);
  return (
    <svg className="resbar" width={BAR_W} height={BAR_H} viewBox={`0 0 ${BAR_W} ${BAR_H}`} aria-hidden="true">
      <rect className="resbar-band" x={mid - PER_SIGMA} y={0} width={2 * PER_SIGMA} height={BAR_H} />
      <rect className={`resbar-bar m${misfitStep(normalized)}`} x={x} y={2} width={width} height={BAR_H - 4} />
      {over && (
        <path
          className={`resbar-bar m${misfitStep(normalized)}`}
          d={normalized > 0 ? `M${BAR_W - 4},1 L${BAR_W},${BAR_H / 2} L${BAR_W - 4},${BAR_H - 1}Z` : `M4,1 L0,${BAR_H / 2} L4,${BAR_H - 1}Z`}
        />
      )}
      <line className="resbar-zero" x1={mid} x2={mid} y1={0} y2={BAR_H} />
    </svg>
  );
}

/** About `count` round tick values covering [lo, hi]. */
export function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 5, 10].find((m) => m * power >= raw) ?? 10) * power;
  const ticks: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) ticks.push(Math.abs(t) < step * 1e-9 ? 0 : t);
  return ticks;
}

const SIZE = 248;
const PAD = { left: 52, right: 10, top: 10, bottom: 34 };

/** Observed against calculated couplings with the 1:1 line. The selected couplings are rings. */
export function ObsCalcPlot({
  couplings,
  selected,
  rms,
  onPick,
}: {
  couplings: readonly FittedCoupling[];
  selected: ReadonlySet<string>;
  rms: number;
  onPick: (id: string) => void;
}) {
  if (couplings.length === 0) return null;
  const values = couplings.flatMap((c) => [c.observed.value, c.calculated.value]);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const pad = (hi - lo || Math.abs(hi) || 1) * 0.06;
  lo -= pad;
  hi += pad;
  const inner = SIZE - PAD.left - PAD.right;
  const sx = (v: number) => PAD.left + ((v - lo) / (hi - lo)) * inner;
  const sy = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * inner;
  const ticks = niceTicks(lo, hi);
  const digits = Math.max(0, -Math.floor(Math.log10(Math.max((ticks[1] ?? 1) - (ticks[0] ?? 0), 1e-12))));
  return (
    <figure className="plot">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width={SIZE}
        height={SIZE}
        role="img"
        aria-label={strings.obsCalcLabel(couplings.length, fixed(rms, 2))}
      >
        {ticks.map((t) => (
          <g key={t} className="plot-tick">
            <line x1={sx(t)} x2={sx(t)} y1={PAD.top} y2={PAD.top + inner} />
            <line x1={PAD.left} x2={PAD.left + inner} y1={sy(t)} y2={sy(t)} />
            <text x={sx(t)} y={SIZE - PAD.bottom + 14} textAnchor="middle">
              {fixed(t, digits)}
            </text>
            <text x={PAD.left - 4} y={sy(t) + 3} textAnchor="end">
              {fixed(t, digits)}
            </text>
          </g>
        ))}
        <rect className="plot-frame" x={PAD.left} y={PAD.top} width={inner} height={inner} />
        <line className="plot-identity" x1={sx(lo)} y1={sy(lo)} x2={sx(hi)} y2={sy(hi)} />
        {couplings.map((c) => (
          <circle
            key={c.id}
            className={`plot-point m${misfitStep(c.normalized_residual)}`}
            cx={sx(c.calculated.value)}
            cy={sy(c.observed.value)}
            r={3.5}
            onClick={() => onPick(c.id)}
          >
            <title>{c.label}</title>
          </circle>
        ))}
        {couplings
          .filter((c) => selected.has(c.id))
          .map((c) => (
            <circle key={`ring-${c.id}`} className="plot-ring" cx={sx(c.calculated.value)} cy={sy(c.observed.value)} r={7} />
          ))}
        <text className="plot-axis" x={PAD.left + inner / 2} y={SIZE - 4} textAnchor="middle">
          {strings.colCalculated}
        </text>
        <text className="plot-axis" transform={`translate(11 ${PAD.top + inner / 2}) rotate(-90)`} textAnchor="middle">
          {strings.colObserved}
        </text>
      </svg>
    </figure>
  );
}
