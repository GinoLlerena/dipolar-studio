"""The restricted-value scan (round 74, A4) on synthetic text: every numeric form of a value is
found, exceptions are single verified lines, and reports never print the value. The values here
are synthetic and match no dataset."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "datasets"))

import restricted_scan as rs  # noqa: E402

VALUES = frozenset({Decimal("0.48731"), Decimal("917.64")})
TIERS = [rs.Tier(VALUES, min_sig=4, prefixes=None), rs.Tier(frozenset({Decimal("0.613")}), 3, ("docs/phase2/",))]


def _hits(
    path: str, text: str, encoding: str = "utf-8", allowed: frozenset[tuple[str, str]] = frozenset()
) -> list[str]:
    return rs.scan([(path, text.encode(encoding))], TIERS, allowed)


def test_every_numeric_form_is_found() -> None:
    for form in ("0.48731", "-0.48731", "0.487310", ".48731", "4.8731e-1", "48.731E-2", "−0.48731", "917.64",
                 "-917:64", "917.640"):  # fmt: skip
        assert _hits("notes.md", f"a value {form} here") == ["notes.md:1"], form


def test_other_numbers_are_not_flagged() -> None:
    for form in ("0.4873", "917.6", "1.0.48731", "v0.48731x", "48731", "0.48732"):
        assert _hits("notes.md", f"x {form} y") == [], form


def test_encodings_are_decoded() -> None:
    for encoding in ("utf-16", "utf-16-le", "utf-16-be", "utf-32"):
        assert _hits("data.txt", "first\nthe 0.48731 cell\n", encoding) == ["data.txt:2"], encoding


def test_the_short_tier_applies_only_under_its_prefix() -> None:
    assert _hits("docs/phase2/x.md", "about 0.613") == ["docs/phase2/x.md:1"]
    assert _hits("src/x.py", "about 0.613") == []


def test_an_exception_covers_one_line_only() -> None:
    line = "the mockup shows 917.64 Hz"
    allowed = frozenset({("mock.html", rs.line_hash(line))})
    assert _hits("mock.html", f"{line}\nlater 917.64 again\n", allowed=allowed) == ["mock.html:2"]
    assert _hits("other.html", f"{line}\n", allowed=allowed) == ["other.html:1"]


def test_only_lock_upload_timestamps_are_exempt() -> None:
    lock = 'upload-time = "2026-01-01T00:00:917.64Z"\nsize = 917.64\n'
    assert _hits("uv.lock", lock) == ["uv.lock:2"]


def test_reports_name_the_place_not_the_value() -> None:
    hits = _hits("notes.md", "0.48731 and 917.64")
    assert hits == ["notes.md:1"] and not any("487" in h or "917" in h for h in hits)
