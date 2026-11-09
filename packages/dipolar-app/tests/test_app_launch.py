"""The private redirect directory of the browser hand-off (plan D10; validation rounds 11-12)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from dipolar_app import cli


def test_a_concurrent_creator_is_tolerated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two first opens race at mkdir: the loser must accept the winner's directory, after the checks."""
    real_mkdir = os.mkdir

    def lose_the_race(path: str | os.PathLike[str], mode: int = 0o777) -> None:
        real_mkdir(path, 0o755)  # the other process got there first
        raise FileExistsError(path)

    monkeypatch.setattr(cli.os, "mkdir", lose_the_race)
    directory = cli.verified_launch_dir(tmp_path, create=True)
    assert directory == (tmp_path / "browser-launch").resolve()
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


@pytest.mark.parametrize("kind", ["symlink", "file"])
def test_anything_but_a_plain_directory_is_refused(tmp_path: Path, kind: str) -> None:
    target = tmp_path / "browser-launch"
    if kind == "symlink":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir(mode=0o755)
        target.symlink_to(elsewhere, target_is_directory=True)
    else:
        target.write_text("not a directory")
    with pytest.raises(cli.UnsafeLaunchDir):
        cli.verified_launch_dir(tmp_path, create=True)
    if kind == "symlink":
        assert stat.S_IMODE((tmp_path / "elsewhere").stat().st_mode) == 0o755


def test_missing_directory_without_create(tmp_path: Path) -> None:
    assert cli.verified_launch_dir(tmp_path, create=False) is None
