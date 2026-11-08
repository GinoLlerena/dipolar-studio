# Legacy numerical harness

Compiles the *unmodified* 1998 solvers (`Matriz.cpp`, `SistEcuac.cpp`) outside MFC
with a 10-line `stdafx.h` stub, and compares them against NumPy.

```bash
LEGACY=../../../NMRApllication   # a clone of https://github.com/GinoLlerena/NMRApllication
for f in Matriz.cpp Matriz.h SistEcuac.cpp SistEcuac.h; do
  iconv -f latin1 -t utf-8 "$LEGACY/$f" | tr -d '\r' > src/$f
done
clang++ -std=c++17 -w -Isrc test.cpp src/Matriz.cpp src/SistEcuac.cpp -o t && ./t
```

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

These cases become the first regression tests ("golden failures") of the new engine.
