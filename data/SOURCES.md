# Data sources and the total-return convention

This file records the data decisions that the pre-registration depends on. It is written
before the pull, so that the pull cannot be chosen to suit a result.

## 1. Source

| role | source | status |
|------|--------|--------|
| backtest panel | **Tiingo** daily prices, `adjClose`, `divCash`, `splitFactor` | chosen |
| cross-check | **Stooq** daily closes | attempt, may fail — see §4 |
| breadth only | Yahoo `adjclose` | **confined to the breadth calculation**, never the backtest |

Yahoo is used for the breadth pull that produced the design inputs (B = 4.04, MDE = 0.77).
It is not used for the backtest: its adjusted series has undocumented revision behaviour and
no stable reproducibility guarantee. The breadth figure is a design input, not a result, and
its provenance is recorded here rather than presented as if it were the backtest data.

## 2. Total-return convention

**Definition: total return is the ratio of consecutive `adjClose` values.**

`adjClose` is adjusted for both dividends and splits, so a ratio of two `adjClose` values is
the total return over that interval with dividends reinvested. Cumulative products of those
ratios form a total-return index.

**Never used as an absolute level.** The adjustment factor is applied retroactively across
the whole history, so any absolute adjusted price embeds every subsequent corporate action.
That is a lookahead vector: a threshold, a notional, or a stop expressed in adjusted-price
units would be conditioned on the future. Ratios are invariant to the factor and therefore
safe; levels are not. All signals are built from ratios.

## 3. Why the audit exists, and what its first version got wrong

`scripts/audit_snapshot.py` does not take `adjClose` on trust. For every instrument it checks,
on the **full series including split days**, that

    adjClose_t / adjClose_{t-1} - 1  ==  (close_t + divCash_t) / close_{t-1} * splitFactor_t - 1

Tolerance **1e-9**. Worst observed deviation across the eighteen instruments: **9.44e-12**.
The pull refuses to freeze a snapshot that does not reconcile.

**The first version of this audit was wrong in three ways and failed fifteen of eighteen
instruments as a result.**

1. It removed split rows before computing the return, so the row following a split computed its
   return against the row *before* the split — spanning it. USO (1:8), EWJ (4:1) and BWX (2:1)
   reported deviations equal to their split ratios, which is what identified the cause.
2. It formed the implied return as `price_return × (1 + divCash/close_prev)`, which leaves a
   residual of roughly the dividend yield, instead of `(close + divCash)/close_prev ×
   splitFactor − 1`.
3. It enforced a tolerance of 1e-6 on a daily return, which no instrument carrying distributions
   could satisfy at any data quality.

Those were defects in the audit, not in the data. **No data was re-pulled**, and the panel
SHA-256 is unchanged (`44dced9f…c603c1`). The correction is recorded in `prereg/DEVIATIONS.md`
entry 1; the authoritative audit output is `data/audit.json`; and `data/snapshot_manifest.json`
carries an `audit_correction` block naming the superseded v1 numbers.

This is a correctness gate on the data, in the same spirit as the 1e-5 gate on artefact 2's
native evaluator: the claim rests on it, so it is tested rather than assumed — and when the gate
itself proved faulty, the gate was corrected and the correction published.

## 4. The cross-check, and what it can and cannot verify

Stooq publishes split-adjusted closes **without** dividend adjustment. So the cross-check
verifies **the price series and split handling**, not the total-return series. The dividend
component is verified internally by the audit in §3. Stating which half each check covers is
the point — a cross-check that claims to verify everything verifies nothing.

**Known obstacle:** Stooq serves an HTML interstitial to uninvited clients instead of CSV.
A live probe from this machine on 1 November 2026 returned HTTP 200 with
`<!DOCTYPE html>…<noscript>` rather than a CSV body. `parse_stooq` therefore returns `None`
and the failure is recorded in the manifest as `"status": "unavailable"` rather than being
silently tolerated. If the cross-check cannot be obtained, the pre-registration will say so
and the price series will rest on the audit in §3 and on Tiingo's documented adjustment,
rather than on a comparison that was never completed.

## 5. The two-snapshot rule

Pull, hash, store, never regenerate.

- A pull is stored under `data/snapshots/<timestamp>-<hash8>/` and is **immutable**.
- `scripts/fetch_data.py` verifies an existing snapshot's hash and reuses it; it never
  overwrites. Re-pulling silently changes the panel under a frozen design, which is the
  exact failure this rule exists to prevent.
- Each snapshot carries `manifest.json`: per-file SHA-256, row counts, first and last date,
  the exact request URLs, the total-return audit, the cross-check results, and the Python
  and pandas versions.
- `data/` is gitignored. The script and the hash manifests are committed; **vendor data is
  never committed**.

## 6. Confirming the design inputs

`scripts/design_inputs.py` recomputes B on the frozen backtest snapshot and applies a rule
fixed in advance:

- `|B_new - 4.04| <= 0.40` → carry MDE = 0.77 forward, record the recomputation.
- `|B_new - 4.04| > 0.40` → rerun the power simulation before §1.1 is frozen.

The gate fires at B < 8 and B is 4.04, so branch (b) is robust to a change of provider. What
is not automatically robust is the MDE, because it is derived from the correlation
structure — hence the rule, and hence the threshold being declared before the number is seen.
