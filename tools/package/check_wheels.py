"""The wheels carry no third-party or local data (plan, V1.5c: "Check all archive and wheel
manifests for excluded data").

    python3 tools/package/check_wheels.py dist/packages/*.whl

Each wheel's manifest is read, not unpacked. A wheel may carry the packages' code, the bundled
page, the synthetic example and its metadata. Refused: any path under ``datasets/`` or
``datasets-local``, any name from the third-party corpus (8CB, benzene, ortho-dichlorobenzene,
the SI file), and compiled caches. Exit status 1 lists every refused name.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

#: Case-insensitive fragments that no wheel path may contain. They are long enough not to occur
#: by chance in the page's hashed asset names.
EXCLUDED = re.compile(
    r"(^|/)datasets(/|-local)|biphenyl-8cb|dipietro|taggar|benzene-zli1132|jp052592j|chandrakumar|odcb-"
    r"|__pycache__|\.pyc$",
    re.IGNORECASE,
)


def problems(names: list[str]) -> list[str]:
    """The manifest's refused names, each with why."""
    return [f"{name}: excluded data" for name in names if EXCLUDED.search(name)]


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_wheels.py WHEEL...", file=sys.stderr)
        return 2
    failed = False
    for wheel in argv:
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        found = problems(names)
        for problem in found:
            print(f"{Path(wheel).name}: {problem}", file=sys.stderr)
        failed |= bool(found)
        if not found:
            print(f"{Path(wheel).name}: no excluded data ({len(names)} entries)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
