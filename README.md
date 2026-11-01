# tsmom-panel-study

A pre-registered test of time-series momentum across a cross-asset panel of eighteen liquid
ETFs, 2011–2026, asking whether the effect has decayed to a magnitude at or below zero.

This is not a replication of Moskowitz, Ooi & Pedersen (2012). MOP tested a broad futures
panel across four decades and their return includes a roll yield that an ETF construction
does not have. What is tested here is time-series momentum in spot / total-return ETF prices —
a narrower, related effect, declared as such in `prereg/PREREGISTRATION.md` §1.3.

## What makes it worth reading

The design was measured before it was run. Effective breadth came out at **B = 4.04** — the
eighteen instruments contain about four independent bets, not eighteen — so a breadth gate
of B ≥ 8 failed and the study was narrowed rather than overclaimed. A simulation puts the
minimum detectable effect at **0.77 realised Sharpe**, which means the result will be a bound,
not a verdict:

> A null excludes a live effect above 0.77. It does not establish that the effect is zero, and
> it does not resolve the 0.2–0.5 band.

A portfolio-level test at this breadth simply cannot answer the decay question. Saying so in
advance is the point.

## Contents

| Path | What it is |
|---|---|
| `prereg/PREREGISTRATION.md` | The frozen design, committed before any strategy return was computed |
| `prereg/DEVIATIONS.md` | Dated departures from it, with the cost to the claim |
| `scripts/fetch_data.py` | Pull, audit, hash and freeze the data snapshot |
| `scripts/design_inputs.py` | Recompute breadth on the frozen snapshot; apply the pre-declared rule |
| `scripts/audit_snapshot.py` | Standalone total-return audit against a frozen snapshot |
| `src/` | The breadth and power work that produced the numbers in §4 and §5 |
| `data/audit.json` | Total-return audit result |
| `data/snapshot_manifest.json` | Source hashes, so a fresh clone can verify rather than re-derive |

No vendor data is committed. `data/raw/` and `data/snapshots/` are gitignored; the committed
manifest carries the hashes.

## Status

Pre-registration frozen and tagged `v0.1-prereg`. No strategy returns computed at the time
of this commit.

## Licence

MIT — see `LICENSE`.
