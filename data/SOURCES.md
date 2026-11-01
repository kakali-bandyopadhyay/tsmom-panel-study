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

## 3. Why the audit exists

`scripts/fetch_data.py` does not take `adjClose` on trust. For every instrument it checks,
on non-split days only, that

    adjClose_t / adjClose_{t-1}  ==  (close_t / close_{t-1}) * (1 + divCash_t / close_{t-1})

which is what "dividends reinvested, splits absorbed" must mean in price space. Split days
are excluded from that identity because the `close` ratio is not a return across a split;
on those days the check is instead that `adjClose` has **no jump**, i.e. the split was
absorbed. A tolerance of 1e-6 is enforced, and the pull aborts rather than freezing a
snapshot whose total-return series does not reconcile.

This is a correctness gate on the data, in the same spirit as the 1e-5 gate on artefact 2's
native evaluator: the claim rests on it, so it is tested rather than assumed.

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
