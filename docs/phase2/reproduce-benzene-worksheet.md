# Benzene reproduction: evidence worksheet (blank)

The worksheet of the [benzene reproduction guide](reproduce-benzene.md). Copy this file, fill it
in on your own computer, and send it to the owner through the private channel (decision 9). Do
not post it publicly.

Write no name, handle, e-mail address or other contact detail here. The owner keeps those
separately and knows you only by your opaque participant ID.

The owner builds a sanitized record (`verification.check_participant`) from this worksheet. Its
fields are listed under [The owner's record](#the-owners-record), at the end. The other keys stay
in this private worksheet.

| Field | Key | Value |
|---|---|---|
| Participant ID (`P-` and three digits, from the owner) | `participant` |  |
| Eligible under decision 8 (yes or no) | `eligible` |  |
| Success claimed: all four steps done (yes or no) | `success_claimed` |  |

## Source

| Field | Key | Value |
|---|---|---|
| Where the file came from (the page and the link you used) | `si_origin` |  |
| SHA-256 printed by your check | `si_sha256` |  |
| It equals the guide's value (yes or no) | `si_sha256_matches` |  |

## Release

| Field | Key | Value |
|---|---|---|
| Release tag | `release_tag` |  |
| Its commit (from the release page) | `commit` |  |
| `dipolar --version`, as printed | `version_line` |  |
| Protocol revision (from the benzene verification page) | `protocol_sha256` |  |
| Operating system and Python version | `platform` |  |

## Geometry

| Field | Key | Value |
|---|---|---|
| Computed by you, not copied (yes or no) | `geometry_computed` |  |
| How: the tool or program, and the formula | `geometry_method` |  |
| Decimal places of the coordinates | `decimals` |  |
| Axes of your XYZ frame | `xyz_axes` |  |

## Symmetry

| Field | Key | Value |
|---|---|---|
| Point group declared | `point_group` |  |
| Axes declared (x′, y′, z′ as rows) | `declared_axes` |  |

## Observables and σ

| Field | Key | Value |
|---|---|---|
| Signs and digits kept as printed (yes or no) | `kept_as_printed` |  |
| How σ was read from each token | `sigma_reading` |  |
| The pairs used for D12, D13 and D14 | `pairs` |  |

## Conditions

One row per condition. The other columns are your notes, and they stay in this worksheet. The
last column is the owner's: `numerical_match`, from the owner's local check of your saved run.

In the record, `conditions` has one entry per row, keyed `<run>/<sample>` (for example `1/1.31`).
Each entry holds only `numerical_match`.

| Run | Sample | CSV made from the checked file | S_zz estimated, rank verified | Saved run file | `numerical_match` (owner) |
|---|---|---|---|---|---|
| 1 | `1.31` |  |  |  |  |
| 1 | `3.00` |  |  |  |  |
| 1 | `4.48` |  |  |  |  |
| 1 | `5.14` |  |  |  |  |
| 1 | `6.71` |  |  |  |  |
| 1 | `8.32` |  |  |  |  |
| 1 | `mix1` |  |  |  |  |
| 2 | `0.55` |  |  |  |  |
| 2 | `1.101` |  |  |  |  |
| 2 | `2.321` |  |  |  |  |
| 2 | `2.921` |  |  |  |  |
| 2 | `4.969` |  |  |  |  |
| 2 | `mix2.1` |  |  |  |  |
| 2 | `mix2.2` |  |  |  |  |
| 2 | `mix2.3` |  |  |  |  |

## Numerical match

Filled in by the owner, in a local session, under the guide's precision rule (1e-8 absolute at
12 or more decimal places, plus the owner's allowance at 8 to 11).

| Field | Key | Value |
|---|---|---|
| Conditions checked | `checked` |  |
| Conditions matching | `matching` |  |

## Comparison counts

Step 4, after the owner publishes the counts. Record your own counts and the published ones.
The record's `counts` is your four counts, which carry no value from the paper.

| Field | Key | Value |
|---|---|---|
| Compared (yours) | `compared` |  |
| Agreeing (yours) | `agreeing` |  |
| Disagreeing (yours) | `disagreeing` |  |
| Pending (yours) | `pending` |  |
| Compared (published) | `published_compared` |  |
| Agreeing (published) | `published_agreeing` |  |
| Disagreeing (published) | `published_disagreeing` |  |
| Pending (published) | `published_pending` |  |
| Yours equal the published counts (yes or no) | `counts_equal_published` |  |
| Adequacy, recorded separately (your notes) | `adequacy_notes` |  |

## The owner's record

The owner fills in this table from the worksheet. It is the whole sanitized record: nothing
else is kept in the repository's receipt.

| Field | Key | Taken from | Value |
|---|---|---|---|
| Participant ID | `participant` | the first table |  |
| Eligible under decision 8 | `eligible` | the first table, checked by the owner |  |
| Release tag | `release_tag` | Release |  |
| Its commit | `commit` | Release |  |
| Protocol revision | `protocol_sha256` | Release |  |
| The SI hash matches | `si_sha256_matches` | Source |  |
| The geometry was computed | `geometry_computed` | Geometry |  |
| `numerical_match` per `<run>/<sample>` | `conditions` | Conditions (the owner's column) |  |
| Your four counts | `counts` | Comparison counts (yours) |  |
| Success claimed | `success_claimed` | the first table |  |
