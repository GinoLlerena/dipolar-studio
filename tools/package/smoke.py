"""The user's path, checked against the installed wheels (Beta step B1; CI "packaged" job).

Run with the Python of a clean environment where only the two wheels are installed:

    python -I tools/package/smoke.py --guide docs/user/getting-started.md

It checks what the user guide tells a user to do:
1. `dipolar --version` names both packages and the contract;
2. the guide's Python example (the code block under "Using Python"), run as written;
3. `dipolar serve` on a fresh project directory serves the bundled page, and `Studio.connect`
   drives that session: the example opened, a fit run, the result read back.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def the_guides_python_example(guide: Path) -> str:
    text = guide.read_text(encoding="utf-8")
    section = text.split("## Using Python", 1)[1]
    found = re.search(r"```python\n(.*?)```", section, re.S)
    if not found:
        raise SystemExit("the guide's 'Using Python' section has no python code block")
    return found.group(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guide", type=Path, required=True)
    ns = parser.parse_args()
    dipolar = shutil.which("dipolar", path=str(Path(sys.executable).parent)) or shutil.which("dipolar")
    if dipolar is None:
        raise SystemExit("no dipolar command next to this Python")

    # 1. The version line.
    version = subprocess.run([dipolar, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    assert re.fullmatch(r"dipolar \S+ \(dipolar-core \S+, contract \d+\.\d+\.\d+\)", version), version
    print(f"ok  {version}")

    # 2. The guide's example, as written, in a fresh interpreter of this environment.
    example = the_guides_python_example(ns.guide)
    out = subprocess.run([sys.executable, "-I", "-c", example], capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr
    print("ok  the guide's Python example ran")

    # 3. dipolar serve, the bundled page, and a script driving the same session.
    from dipolar_app.api import Studio

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "project"
        ready = Path(tmp) / "ready.json"
        server = subprocess.Popen(
            [dipolar, "serve", "--project-dir", str(project), "--ready-file", str(ready)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while not ready.exists():
                assert server.poll() is None, "dipolar serve stopped"
                assert time.monotonic() < deadline, "dipolar serve did not start"
                time.sleep(0.1)
            base = json.loads(ready.read_text(encoding="utf-8"))["base_url"]
            with urllib.request.urlopen(base + "/", timeout=30) as page:
                assert page.status == 200 and b'<div id="root"' in page.read(), "the bundled page is not served"
            print("ok  dipolar serve serves the bundled page")
            with Studio.connect(ready) as studio:
                studio.call("project.open_example", name="biphenyl-synthetic", expected_science_revision=0)
                run = studio.fit()
                phi = {t["name"]: t["value"] for t in run["theta"]}["phi_deg"]
                assert abs(phi - 37.0) < 0.5, phi
            print(f"ok  Studio.connect fitted through dipolar serve: phi = {phi:.3f} deg")
        finally:
            server.terminate()
            try:
                server.wait(timeout=20)
            except subprocess.TimeoutExpired:
                server.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
