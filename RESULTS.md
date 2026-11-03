# Results — first run

**Status:** first result, 2026-11-01. This file is **post-registration**. The pre-registration
(`w86xt`, DOI 10.17605/OSF.IO/W86XT) is unchanged and remains the frozen design.

## Headline

**The pre-registered exclusion bound is not supported, and is withdrawn.**

## What was run

`src/backtest.py` against the frozen snapshot `20261101T130536Z-44dced9f`, with the panel
SHA-256 verified before load, under the specification in `prereg/PREREGISTRATION.md` §3:
52-week trailing signal, inverse-volatility sizing (`sign(r)/σ`, 52-week rolling σ), weekly
W-FRI rebalance, **time fixed effects only**, time-clustered standard errors.

## Numbers

| Quantity | Value |
|---|---|
| Realised Sharpe | **+0.526** |
| 95% interval (bootstrap) | **[0.038, 1.054]** |
| 95% interval (Lo 2002) | [−0.001, 1.053] |
| P(Sharpe > 0.77) | 0.179 |
| Regression t | **2.079** |
| Size-corrected critical value | **2.152** → fail to reject |
| Nominal 1.96 | would have "rejected" |
| Random subsets of 12 (1,000 draws, seed 20261101) | all positive; p5 **+0.341**; full-universe percentile **58.8** |
| Excluding QQQ | +0.455 [−0.033, 0.977], t 1.685 |

The two interval constructions agree closely in width and centre. They differ at the lower
bound, where the bootstrap excludes zero at 0.04 and Lo (2002) marginally includes it
at −0.001.

## Why the bound is withdrawn

§1.2 states: *"A null result excludes a live effect above 0.77."* **That is false on its own
terms.** 80% power at 0.77 means the test misses an effect of 0.77 one time in five, so a
non-rejection cannot exclude it. An exclusion requires the **interval's upper bound** to sit
below the threshold, and here the upper bound is **1.05** — which fails to exclude 0.77. The
interval spans 0.04 to 1.05 under the bootstrap and −0.001 to 1.05 under Lo (2002); it excludes
neither a negligible effect nor an effect at the pre-registered bound.

The design is not at fault. The sentence describing what a null would establish was.

## What this does and does not establish

**It does not establish that time-series momentum is absent.** The point estimate is positive,
material at roughly 0.5 Sharpe, and robust to composition — every one of 1,000 subsets is
positive and the full universe sits at the 58.8th percentile of that distribution, so the
result is not an artefact of which eighteen instruments were chosen.

**It establishes that this design cannot resolve an effect of that size with confidence.** The
interval runs from the boundary of zero to 1.05, so it is compatible both with a negligible
effect and with one at the pre-registered 0.77 bound. The estimate falls in the 55.5%-power
bracket of the study's own power analysis — a range §4.3 predicted would be unresolvable, and
which the study therefore should have expected to encounter.

## Disclosed implementation mismatches

Not patched, disclosed. Both are recorded in `prereg/DEVIATIONS.md`.

1. **σ is estimated here, fixed in the calibration.** The power study fixes σ at its
   full-sample value; the backtest estimates it on a rolling window. The MDE is therefore
   approximate for the estimator actually run.
2. **The MDE's Sharpe is a different portfolio's Sharpe.** The power study's "realised Sharpe"
   is signal-weighted (0.545); §3.2's sign/σ portfolio realises 0.526. The 0.77 figure is
   expressed in the former's units, so it cannot be quoted against the latter without saying
   so.

Under-specification resolved before running — the Sharpe interval's construction, the SE
definition, the regressor's units, the definition of "best instrument", and the decision rule —
is recorded as entries 2–6, each with its measured cost.

## What follows

This is an **empirical** argument for the futures-based design that §4.3 declined as branch
(d) on cost. A panel with four decades of history and genuine cross-asset breadth could resolve
what this design cannot. That is a second study with its own pre-registration, not a
re-specification of this one — which stays frozen.
