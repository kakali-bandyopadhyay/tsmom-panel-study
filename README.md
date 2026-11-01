# tsmom-panel-study

A pre-registered test of time-series momentum across a cross-asset panel of eighteen liquid
ETFs, 2011–2026, asking whether the effect has decayed below detectability.

## Identifiers

- **OSF pre-registration:** [10.17605/OSF.IO/W86XT](https://doi.org/10.17605/OSF.IO/W86XT)
- **ORCID:** https://orcid.org/0000-0002-6130-9816
- **Git tag:** `v0.1-prereg` (commit `2d3ab67`)

The design was frozen and registered before any strategy return was computed. Two independent
timestamps exist — the Git tag and the OSF registration — neither of which can be altered
after the fact.

This is not a replication of Moskowitz, Ooi & Pedersen (2012). MOP tested a broad futures
panel across four decades and their return includes a roll yield that an ETF construction
does not have. What is tested here is time-series momentum in spot / total-return ETF prices —
a narrower, related effect, declared as such in `prereg/PREREGISTRATION.md` §1.3.

## What makes it worth reading

The design was measured before it was run. Effective breadth came out at **B = 4.04** — the
eighteen instruments contain about four independent bets, not eighteen — so a breadth gate of
B ≥ 8 failed and the study was narrowed rather than overclaimed.

**The pre-run expectation, recorded before the result, was this:**

> A null excludes a live effect above 0.77. It does not establish that the effect is zero, and
> it does not resolve the 0.2–0.5 band.

**That expectation did not survive the run — and its second sentence was wrong when it was
written.** A design with 80% power at 0.77 misses 0.77 one time in five, so a non-rejection
cannot exclude it. The bound was withdrawn. See **Status** below and [`RESULTS.md`](RESULTS.md).

What survives is the part that was right: a portfolio-level test at this breadth cannot answer
the decay question. The study now says so with a measured interval instead of an assumed bound.

## Contents

| Path | What it is |
|---|---|
| `prereg/PREREGISTRATION.md` | The frozen design, committed before any strategy return was computed |
| `prereg/DEVIATIONS.md` | Dated departures from it, with the cost to the claim |
| `RESULTS.md` | The first result, post-registration: numbers, the withdrawn bound, and why |
| `src/backtest.py` | The registered specification, executed against the frozen panel |
| `scripts/fetch_data.py` | Pull, audit, hash and freeze the data snapshot |
| `scripts/design_inputs.py` | Recompute breadth on the frozen snapshot; apply the pre-declared rule |
| `scripts/audit_snapshot.py` | Standalone total-return audit against a frozen snapshot |
| `src/` | The breadth and power work that produced the numbers in §4 and §5 |
| `data/audit.json` | Total-return audit result |
| `data/snapshot_manifest.json` | Source hashes, so a fresh clone can verify rather than re-derive |

No vendor data is committed. `data/raw/` and `data/snapshots/` are gitignored; the committed
manifest carries the hashes.

## Status

Pre-registration frozen and tagged `v0.1-prereg`; registered on OSF (DOI above).

**First result, 2026-11-01: the pre-registered exclusion bound is not supported, and is withdrawn.**

Realised Sharpe **+0.526**, 95% interval **[0.038, 1.054]**. Regression t = 2.079 against the
size-corrected critical value of 2.152 — fail to reject, and it would have "rejected" at the
nominal 1.96. All 1,000 random subsets are positive (p5 +0.341), so the result is not
composition-driven.

The estimate is positive and material at roughly half the pre-decay magnitude, but this design
cannot separate it from zero: its minimum detectable effect was 0.77, and the interval's upper
bound of 1.05 excludes neither 0.77 nor the historical value.

The pre-registration's §1.2 stated that a null would exclude a live effect above 0.77. That is
false at 80% power — the test misses 0.77 one time in five — and the sentence is withdrawn in
`RESULTS.md`, which also explains why the design was not at fault, only the claim made for it.

## Licence

Code: MIT — see `LICENSE`.

Documents and pre-registration text: CC-BY 4.0 (see the OSF registration).
