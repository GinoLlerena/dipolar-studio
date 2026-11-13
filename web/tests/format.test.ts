// The display formatter (ui-design §5). Run with `pnpm test` (Node's test runner, types stripped).
import assert from "node:assert/strict";
import { test } from "node:test";
import { atPlace, compact, decimalsFor, extent, fixed, MINUS, pValue, scientific, signed, withUncertainty } from "../src/format.ts";

const N = " "; // the thousands separator

test("fixed uses the true minus sign, groups thousands and never shows −0", () => {
  assert.equal(fixed(-2407.3, 1), `${MINUS}2${N}407.3`);
  assert.equal(fixed(1124.726, 1), `1${N}124.7`);
  assert.equal(fixed(999.94, 1), "999.9");
  assert.equal(fixed(1234567, 0), `1${N}234${N}567`);
  assert.equal(fixed(-0.0004, 2), "0.00");
  assert.equal(fixed(1234, -1), `1${N}230`);
  assert.equal(fixed(Number.NaN, 2), "—");
  assert.equal(fixed(Number.NEGATIVE_INFINITY, 2), `${MINUS}∞`);
});

test("signed residuals", () => {
  assert.equal(signed(0.214, 2), "+0.21");
  assert.equal(signed(-0.214, 2), `${MINUS}0.21`);
  assert.equal(signed(0.001, 2), "0.00");
  assert.equal(signed(-0.001, 2), "0.00");
});

test("an uncertainty keeps one or two significant figures", () => {
  const cases: [number, number][] = [
    [0.03, 2], // 1 figure: leading 3
    [0.0296, 2], // rounds to 0.030, leading 3: one figure, 0.03
    [0.12, 2], // two figures: leading 1
    [0.196, 2], // rounds to 0.20, leading 2: two figures
    [0.0996, 2], // carries to 0.10: two figures, not 0.100
    [0.0096, 2], // one figure carries to 0.01
    [0.005, 3],
    [0.0003, 4],
    [6.228e-5, 5],
    [0.0082, 3],
    [35, -1], // tens
    [1.5, 1],
  ];
  for (const [sigma, decimals] of cases) assert.equal(decimalsFor(sigma), decimals, `sigma ${sigma}`);
  for (const bad of [0, -1, Number.NaN, Number.POSITIVE_INFINITY]) assert.equal(decimalsFor(bad), null);
});

test("value ± uncertainty, rounded to the same place", () => {
  assert.equal(withUncertainty(39.6012, 0.03, 2), "39.60 ± 0.03");
  assert.equal(withUncertainty(1.48213, 0.005, 3), "1.482 ± 0.005");
  assert.equal(withUncertainty(36.98502906869832, 0.008197701460040127, 2), "36.985 ± 0.008");
  assert.equal(withUncertainty(0.2500377728761341, 6.228182813569459e-5, 4), "0.25004 ± 0.00006");
  assert.equal(withUncertainty(-12.34, 0.12, 2), `${MINUS}12.34 ± 0.12`);
  assert.equal(withUncertainty(1234, 35, 0), `1${N}230 ± 40`);
  assert.equal(withUncertainty(39.6, null, 2), "39.60");
  assert.equal(withUncertainty(39.6, 0, 2), "39.60");
});

test("compact uncertainty in the last digits", () => {
  assert.equal(compact(0.30204, 0.0003, 4), "0.3020(3)");
  assert.equal(compact(0.2500377728761341, 6.228182813569459e-5, 4), "0.25004(6)");
  assert.equal(compact(1234, 35, 0), `1${N}230 ± 40`); // no decimal place to attach it to
});

test("scientific notation outside [10⁻³, 10⁵)", () => {
  assert.equal(scientific(3.3153491978522327), "3.3");
  assert.equal(scientific(2643485.636662991, 3), "2.64 × 10⁶");
  assert.equal(scientific(1.2e-7), "1.2 × 10⁻⁷");
  assert.equal(scientific(-45000), `${MINUS}45${N}000`);
  assert.equal(scientific(0), "0");
});

test("p-values", () => {
  assert.equal(pValue(0.3321762482554919), "0.332");
  assert.equal(pValue(0.0004), "< 0.001");
  assert.equal(pValue(null), "—");
});

test("extent copes with the 100 000-coupling limit and skips non-finite values (round 39)", () => {
  const many = Array.from({ length: 200_000 }, (_, k) => k - 50_000);
  assert.deepEqual(extent(many), [-50_000, 149_999]);
  assert.deepEqual(extent([3, Number.NaN, -2, Number.POSITIVE_INFINITY]), [-2, 3]);
  assert.equal(extent([]), null);
});

test("a tiny but valid uncertainty never crashes and stays nonzero (round 40)", () => {
  const sigma = 1.6395402920085017e-102; // σ = 1e-100 Hz on every coupling: a regular fit
  assert.equal(decimalsFor(sigma), 103);
  assert.equal(withUncertainty(36.98502906869832, sigma, 2), "36.98502906869832 ± 1.6 × 10⁻¹⁰²");
  assert.equal(compact(36.98502906869832, sigma, 2), "36.98502906869832 ± 1.6 × 10⁻¹⁰²");
  assert.equal(atPlace(36.98502906869832, 103), "36.98502906869832"); // an interval endpoint
  assert.equal(atPlace(0.25, 103), "0.2500000000000000");
  assert.equal(atPlace(1.5e-90, 103), "1.5000000000000 × 10⁻⁹⁰");
  assert.equal(atPlace(39.6, 2), "39.60");
  assert.doesNotThrow(() => fixed(1, 400));
  assert.equal(withUncertainty(1, 1e-300, 2).endsWith("× 10⁻³⁰⁰"), true);
});
