import { type MouseEvent, useMemo, useState } from "react";
import type { FittedCoupling, LandscapeOut } from "../api";
import { extent, fixed } from "../format";
import { landscapePath, logRange, lowest, nearest } from "../preview";
import { misfitStep } from "../scene/view";
import { strings } from "../strings";

// Results charts (ui-design §4). Colour comes from CSS classes (the misfit ramp m0–m5), so both
// themes and forced-colours mode style them; every chart has a table with the same numbers.

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
  const range = extent(couplings.flatMap((c) => [c.observed.value, c.calculated.value]));
  if (range === null) return null;
  let [lo, hi] = range;
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

const LAND_W = 520;
const LAND_H = 200;
const LAND_PAD = { left: 52, right: 12, top: 10, bottom: 34 };
const LAND_INNER = { w: LAND_W - LAND_PAD.left - LAND_PAD.right, h: LAND_H - LAND_PAD.top - LAND_PAD.bottom };
const SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹";

/** 10 to an integer power, as "10³" or "10⁻²". */
function decade(k: number): string {
  const digits = [...String(Math.abs(k))].map((d) => SUPERSCRIPT[Number(d)]).join("");
  return `10${k < 0 ? "⁻" : ""}${digits}`;
}

/** The χ²(φ) landscape (fit.landscape) on a log axis, with the previewed φ (solid line) and the
 * current fit's φ (dashed). Torsions where the order matrix is not physically admissible are
 * marked under the axis. A click moves the preview there; the slider is the keyboard control,
 * and the table under the chart lists every sample. */
export function LandscapePlot({
  landscape,
  phi,
  fitted,
  stale,
  onPick,
}: {
  landscape: LandscapeOut;
  phi: number | null;
  fitted: number | null;
  stale: boolean;
  onPick: (phi: number) => void;
}) {
  const { phi: xs, chi2 } = landscape;
  const [tableOpen, setTableOpen] = useState(false);
  // Everything that depends only on the landscape is computed once per landscape: the slider
  // re-renders this chart at every step, and only the cursor moves (M3 step 3).
  const scale = useMemo(() => {
    const range = logRange(chi2);
    const lo = xs[0] ?? 0;
    const hi = xs[xs.length - 1] ?? 1;
    if (range === null || !(hi > lo)) return null;
    const floor = 10 ** range.lo;
    const x = (v: number) => LAND_PAD.left + ((v - lo) / (hi - lo)) * LAND_INNER.w;
    const y = (c: number) =>
      LAND_PAD.top + (1 - (Math.log10(Math.max(c, floor)) - range.lo) / (range.hi - range.lo)) * LAND_INNER.h;
    return {
      lo,
      hi,
      x,
      y,
      path: landscapePath(xs, chi2, x, y),
      best: lowest(xs, chi2),
      decades: Array.from({ length: range.hi - range.lo + 1 }, (_, i) => range.lo + i),
    };
  }, [xs, chi2]);
  if (scale === null) return <p className="muted">{strings.landscapeEmpty}</p>;
  const { lo, hi, x, y, path, best, decades } = scale;
  const inner = LAND_INNER;
  const pick = (e: MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * LAND_W;
    onPick(lo + ((px - LAND_PAD.left) / inner.w) * (hi - lo));
  };
  const at = phi === null ? null : chi2[nearest(xs, phi)];
  return (
    <figure className={stale ? "plot landscape stale" : "plot landscape"}>
      <svg
        viewBox={`0 0 ${LAND_W} ${LAND_H}`}
        width="100%"
        style={{ maxWidth: LAND_W }}
        role="img"
        aria-label={strings.landscapeLabel(
          xs.length,
          best ? fixed(best.phi, 1) : "–",
          best ? fixed(best.chi2, 2) : "–",
          phi === null ? null : fixed(phi, 1),
        )}
        onClick={pick}
      >
        {niceTicks(lo, hi, 6).map((t) => (
          <g key={`x${t}`} className="plot-tick">
            <line x1={x(t)} x2={x(t)} y1={LAND_PAD.top} y2={LAND_PAD.top + inner.h} />
            <text x={x(t)} y={LAND_H - LAND_PAD.bottom + 14} textAnchor="middle">
              {fixed(t, 0)}
            </text>
          </g>
        ))}
        {decades.map((k) => (
          <g key={`y${k}`} className="plot-tick">
            <line x1={LAND_PAD.left} x2={LAND_PAD.left + inner.w} y1={y(10 ** k)} y2={y(10 ** k)} />
            <text x={LAND_PAD.left - 4} y={y(10 ** k) + 3} textAnchor="end">
              {decade(k)}
            </text>
          </g>
        ))}
        <rect className="plot-frame" x={LAND_PAD.left} y={LAND_PAD.top} width={inner.w} height={inner.h} />
        {landscape.physically_admissible.map((ok, i) =>
          ok === false ? (
            <line
              key={`na${i}`}
              className="plot-inadmissible"
              x1={x(xs[i] ?? 0)}
              x2={x(xs[i] ?? 0)}
              y1={LAND_PAD.top + inner.h}
              y2={LAND_PAD.top + inner.h + 5}
            />
          ) : null,
        )}
        <path className="plot-line" d={path} />
        {fitted !== null && fitted >= lo && fitted <= hi && (
          <line className="plot-fit" x1={x(fitted)} x2={x(fitted)} y1={LAND_PAD.top} y2={LAND_PAD.top + inner.h} />
        )}
        {phi !== null && (
          <g className="plot-cursor">
            <line x1={x(phi)} x2={x(phi)} y1={LAND_PAD.top} y2={LAND_PAD.top + inner.h} />
            {at !== null && at !== undefined && <circle cx={x(phi)} cy={y(at)} r={4} />}
          </g>
        )}
        <text className="plot-axis" x={LAND_PAD.left + inner.w / 2} y={LAND_H - 4} textAnchor="middle">
          {strings.landscapeX}
        </text>
        <text className="plot-axis" transform={`translate(11 ${LAND_PAD.top + inner.h / 2}) rotate(-90)`} textAnchor="middle">
          {strings.landscapeY}
        </text>
      </svg>
      <figcaption className="help">
        {strings.landscapeCaption}
        {landscape.physically_admissible.some((ok) => ok === false) && ` ${strings.landscapeInadmissible}`}
      </figcaption>
      <details onToggle={(e) => setTableOpen(e.currentTarget.open)}>
        <summary>{strings.landscapeTable(xs.length)}</summary>
        {tableOpen && <div className="scroll short">
          <table className="grid compact">
            <thead>
              <tr>
                <th className="num">φ (°)</th>
                <th className="num">χ²</th>
                <th>{strings.colAdmissible}</th>
              </tr>
            </thead>
            <tbody>
              {xs.map((v, i) => (
                <tr key={v}>
                  <td className="num">{fixed(v, 2)}</td>
                  <td className="num">{chi2[i] === null ? strings.notEvaluable : fixed(chi2[i] ?? 0, 2)}</td>
                  <td>
                    {landscape.physically_admissible[i] === null
                      ? "–"
                      : landscape.physically_admissible[i]
                        ? strings.yes
                        : strings.no}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>}
      </details>
    </figure>
  );
}
