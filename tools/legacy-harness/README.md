# Legacy numerical harness

Compiles the *unmodified* 1998 solvers (`Matriz.cpp`, `SistEcuac.cpp`) outside MFC
with a 10-line `stdafx.h` stub, and compares them against NumPy.

```bash
LEGACY=/path/to/NMRApllication tools/legacy-harness/run.sh            # compare with the frozen goldens
LEGACY=/path/to/NMRApllication tools/legacy-harness/run.sh --freeze   # rewrite expected-output.txt
```

`run.sh` copies the four legacy files (converted from Latin-1), compiles them with clang++, and
diffs the output against `expected-output.txt` (the "golden failures"). CI runs it on macOS
against the pinned legacy commit `34a0bff`.

Observed output (2026-11-07):

```
diagonal (D4-like)  -> Sxx= -0.10000 Syy= -0.20000 Szz=  0.30000   OK
D2: only Sxy!=0     -> Sxx= -0.22071 Syy= -0.07929 Szz= 99.00000   BUG (expected 0.30000)
only Sxz!=0         -> Sxx= -0.10615 Syy= -0.20615 Szz=  0.30615   BUG (expected -0.20000, -0.10616, 0.30616)
only Syz!=0         -> Sxx=      nan Syy=      nan Szz=      nan   BUG (division by zero)
general             -> Sxx= -0.22133 Syy= -0.08162 Szz=  0.30311   ~1.6e-4 error vs NumPy
SistEcuac partial-path solve, expected (1,2,3): got (1, 2, 14)    BUG
SistEcuac full Gauss solve,   expected (1,2,3): got (1, 2, 3)     OK
```

These cases are frozen in `expected-output.txt` as the "golden failures": the new engine must get every one of them right, and `legacy_exact` mode (V6) must reproduce them.
