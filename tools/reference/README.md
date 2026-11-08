# Independent reference implementation

`biphenyl_reference.py` computes the **frozen expected answers** in `datasets/*/expected/`. It
uses only NumPy and SciPy and is deliberately **independent of `dipolar-core`**: the engine is
tested against these numbers, so it must never be used to produce them.

```bash
uv run python -I tools/reference/make_expected.py               # re-freeze, incl. 1000-seed coverage (~2 min)
uv run python -I tools/reference/make_expected.py --no-coverage # keep the existing coverage file
```

**Re-freezing is a deliberate act.** `MANIFEST.sha256` in each `expected/` directory detects
hand edits. `tests/test_expected_fixtures.py` re-runs this reference and fails if the frozen
numbers drift. Record every re-freeze, with its reason, in the changelog of
[ADR-0003](../../docs/adr/0003-scientific-inference-contract.md).

What it checks at freeze time:

- the reference passes the gates it imposes, so no gate can fail on its own fixture:
  - noiseless recovery to 1e-8;
  - coverage inside the 64.5–72.1% band;
  - sanity bounds against the rounded prototype results;
- the explicit four-conformer average equals the ring-B relabelling shortcut (to 1e-9 Hz);
- its vectorised geometry equals `datasets/biphenyl-synthetic/generate.py`.
