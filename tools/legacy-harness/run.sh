#!/usr/bin/env bash
# Compile the unmodified 1998 solvers and compare their output with the frozen goldens.
#   LEGACY=/path/to/NMRApllication ./run.sh            # check (exit 1 on any difference)
#   LEGACY=/path/to/NMRApllication ./run.sh --freeze   # rewrite expected-output.txt
set -euo pipefail
cd "$(dirname "$0")"
: "${LEGACY:=../../../NMRApllication}"
CXX="${CXX:-clang++}"
for f in Matriz.cpp Matriz.h SistEcuac.cpp SistEcuac.h; do
  iconv -f latin1 -t utf-8 "$LEGACY/$f" | tr -d '\r' > "src/$f"
done
"$CXX" -std=c++17 -w -O0 -Isrc test.cpp src/Matriz.cpp src/SistEcuac.cpp -o t
# Normalise the platform-dependent spelling of NaN (macOS prints nan, glibc may print -nan).
./t | sed -E 's/-?nan/nan/g' > actual-output.txt
if [[ "${1:-}" == "--freeze" ]]; then
  mv actual-output.txt expected-output.txt
  echo "froze expected-output.txt"
else
  diff -u expected-output.txt actual-output.txt && echo "legacy goldens: OK (1998 bugs reproduce exactly)"
  rm -f actual-output.txt
fi
