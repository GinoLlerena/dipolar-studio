#!/usr/bin/env bash
# Build the installable artefacts (plan D10 packaged spike): the browser page is bundled inside the
# dipolar-app wheel, so `pip install` + `dipolar serve` needs no Node and no source checkout.
#
#   tools/package/build.sh            -> dist/packages/*.whl
set -euo pipefail
cd "$(dirname "$0")/../.."

(cd web && pnpm install --frozen-lockfile && pnpm build)

static=packages/dipolar-app/src/dipolar_app/static
rm -rf "$static"
cp -R web/dist "$static"

rm -rf dist/packages
uv build --package dipolar-core --wheel --out-dir dist/packages
uv build --package dipolar-app --wheel --out-dir dist/packages
rm -rf "$static"  # the source tree stays free of build products

python3 - <<'PY'
import pathlib, zipfile
licence = pathlib.Path("LICENSE").read_bytes()
for wheel in sorted(pathlib.Path("dist/packages").glob("*.whl")):
    archive = zipfile.ZipFile(wheel)
    shipped = [n for n in archive.namelist() if n.endswith(".dist-info/licenses/LICENSE")]
    assert len(shipped) == 1 and archive.read(shipped[0]) == licence, f"{wheel.name}: the licence is not shipped"
    print(f"{wheel.name}: licence shipped ({shipped[0]})")
wheel = next(pathlib.Path("dist/packages").glob("dipolar_app-*.whl"))
names = zipfile.ZipFile(wheel).namelist()
assert "dipolar_app/static/index.html" in names, "the page is not bundled"
print(f"{wheel.name}: page bundled ({sum(n.startswith('dipolar_app/static/') for n in names)} files)")
PY
