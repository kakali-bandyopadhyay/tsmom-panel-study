# Pre-registration — `tsmom-panel-study`

**Frozen:** 2026-11-01
**Snapshot:** `20261101T130536Z-44dced9f`
**Panel SHA-256:** `44dced9f55ace2997ad17bbbec5202d472810d342fd14e583ba5af48d8c603c1`
**Status:** written and committed **before any strategy return has been computed.**

---

## 0. Scope

This document fixes the design of a single test before that test is run. Anything not
stated here may not be added after the fact without a dated entry in `DEVIATIONS.md`
recording what changed and what it cost the claim.

Three limits are declared up front:

1. **This is not a replication of Moskowitz, Ooi & Pedersen (2012).** MOP tested time-series
   momentum on a broad futures panel with forty years of history. MOP's return includes a
   roll yield that an ETF construction does not have. What is tested here is time-series
   momentum **in spot / total-return ETF prices** — a related but strictly narrower effect.
   §1.3 states the difference and what it removes.

2. **The design cannot resolve decay.** A live effect and an effect that has decayed by more
   than approximately 0.77 Sharpe are distinguishable. An effect that has decayed into the
   0.2–0.5 band is not distinguishable from zero at this sample size. §5 pre-commits to
   reporting this as a bound rather than an absence.

3. **The universe is survivor-selected.** All eighteen instruments existed on 2026-11-01 and
   the sample begins in 2011. Funds that closed are absent by construction. The bias is
   declared, its direction is known, and it **cannot be bounded** without delisted-fund data
   that is not available at zero cost. §10 states this as a non-claim.

---

## 1. Question and claim

### 1.1 The question

Has time-series momentum, as measured on a cross-asset ETF panel over 2011–2026, fallen to a
magnitude at or below zero?

### 1.2 The claim, and its shape before results

The claim is **an exclusion bound, not an absence**.

If TSMOM were still live at its historical magnitude, this design would detect it. The
primary test is therefore reported as:

> At this breadth, horizon and estimator, the minimum detectable effect at 80% power is a
> realised Sharpe of **0.77**. A null result excludes a live effect above 0.77. It does not
> establish that the effect is zero, and it does not resolve the 0.2–0.5 band.

A null is a **finding about the design's resolution**, not evidence against the strategy. This
sentence is repeated in §3.4 so that the two cannot drift apart in the write-up.

### 1.3 What the ETF construction removes

MOP's effect is measured on futures and includes roll yield in the return. ETFs hold the
underlying (or a swap on it); there is no roll yield. Most of this basket is therefore
roll-free, and the commodity sleeve (DBC, USO) differs again in that it holds futures.
The tested object is the **spot momentum component**, and the literature cited as the
prior is index and spot momentum, not MOP.

Declaring this as a variant rather than a deviation is deliberate: it is a design choice
made before the data, not a shortfall to be conceded afterwards.

---

## 2. Data

### 2.1 Source

**Tiingo** daily prices, EOD, adjusted. Single source. No fallback.

A Stooq cross-check was attempted and refused: Stooq returns a JavaScript challenge page
rather than CSV on every URL form tried, so the cross-check is recorded in the manifest as
`unavailable` for all eighteen instruments. **No weaker substitute was used**, because a
cross-check that silently accepts an unverified page is worse than none.

### 2.2 Universe — eighteen instruments, fixed

| Asset class | Tickors |
|---|---|
| Equities | SPY, QQQ, IWM, EFA, EEM, EWJ |
| Bonds | TLT, IEF, TIP, LQD, BWX |
| Commodities | GLD, SLV, DBC, USO |
| FX / alternatives | FXE, FXY, IYR |

The universe was fixed on 2026-11-01 and is **not** re-selected. No eligibility rule is applied
as-of-date, because a rule reconstructed from incomplete historical data would introduce an
undeclared bias larger than the one it claims to remove. The survivor selection is declared in
§10 and answered only by the composition checks in §6.

### 2.3 Window and frequency

- Daily closes pulled 2011-01-01 → 2026-10-30.
- Resampled to **weekly, W-FRI**, taking the last observation in each week.
- 3,981 daily rows per instrument; **826 weeks**; **774 signal observations** after the
  52-week lookback.

### 2.4 Total-return convention

Total return is the **ratio of `adjClose`**. It is never an absolute adjusted level: the
adjustment factor is applied retroactively, so an absolute level carries information from
the future while a ratio does not.

### 2.5 Total-return audit

`adjClose` is required to reconcile with `(close + divCash) / close_prev * splitFactor − 1`
on every day. Tolerance **1e-9**.

**Result: worst deviation 9.44e-12 across all eighteen instruments.** Three instruments carry
splits (BWX 2:1, EWJ 4:1, USO 1:8 reverse); all reconcile. Audit output: `data/audit.json`.

An earlier version of this audit failed on fifteen of eighteen. The failure was traced to two
formula defects in the audit itself, not to the data; the history is in `DEVIATIONS.md` entry 1.

---

## 3. Design

### 3.1 Signal

52-week trailing total return, computed from adjusted price ratios. Long if positive, short if
negative.

**No deadband.** A plain sign rule, as in MOP's construction. A no-trade threshold would add
a parameter that is absent from the power simulation in §5, and the resulting MDE would no
longer describe the design actually run.

### 3.2 Portfolio construction

**Inverse-volatility sizing.** Position size ∝ sign(r) / σ, where σ is the rolling 52-week
standard deviation of weekly returns, annualised.

Three reasons for this and not equal-weight:

- It matches MOP's construction, so the variant differs from MOP by the absent roll yield
  and nothing else — which is exactly what §1.3 claims.
- A 52-week volatility window adds no new parameter, because the signal already uses 52 weeks.
- **No portfolio-level volatility targeting is applied.** The test statistic is a Sharpe
  ratio, in which any such scaling cancels exactly. Adding one would be an unjustified extra
  choice with no effect on the result.

### 3.3 Estimator — the pre-registered specification

**Time fixed effects only. Time-clustered standard errors. No instrument fixed effects, no
asset-class fixed effects.**

Instrument fixed effects are **contaminated** in this setting: the signal is constructed from
the dependent variable's own history, so within-instrument demeaning subtracts a
mechanically related quantity from both sides. Measured size under the null is 13.3% at a
nominal 5%, and mean t is −0.44. This is a design defect, not a small-sample artefact.

Asset-class fixed effects are rejected for a different and stronger reason: **they change the
estimand.** Class demeaning removes the class-level trend, and class-level trend is a
substantial part of what TSMOM measures. §7 carries the measured cost.

### 3.4 The claim, restated at the specification

> A null excludes a live effect above ≈0.77 realised Sharpe. It does not establish zero and
> does not resolve the 0.2–0.5 band.

---

## 4. Breadth — the gate, and why the scope narrowed

### 4.1 Measurement

Effective number of independent bets, by participation ratio of the correlation matrix
eigenvalues:

    B = (Σλᵢ)² / Σλᵢ²

### 4.2 Result on the backtest snapshot

| | value |
|---|---|
| B (signal) | **4.04** |
| B (returns) | 4.69 |
| First factor share (signal) | 38.6% |
| First factor share (returns) | 36.9% |
| Design value | 4.04 |
| Δ against design | **0.00** |

The signal-based figure being lower than the return-based one is the expected direction —
positions co-move more than returns — which confirms the estimator behaved as intended.

### 4.3 The gate failed, and this was known before the test

Gate: B ≥ 8. B = 4.04. **FAIL.** The panel is one and a half factors deep, not eighteen
independent bets.

Four branches were evaluated and recorded:

| Branch | Outcome |
|---|---|
| (a) add instruments | **Dead.** Five genuinely different additions (EM debt, high yield, REITs, agriculture, dollar index) moved B from 4.04 to 4.26 — +0.044 per addition, extrapolating to ~90 more instruments. Liquid ETFs do not contain eight independent bets. |
| (b) narrow the claim | **Chosen.** Accept that the design cannot resolve decay; report an exclusion bound. |
| (c) extend history to 2007 | **Rejected.** Gains 3.2 years but B falls to 3.66, and it pulls 2008 — the best trend-following year on record — into the sample, handing a critic an easy objection. |
| (d) long-history futures | **Declined on scope and cost.** Would resolve decay properly. Requires paid data and a defensible roll construction. Recorded as declined, not overlooked. |

### 4.4 Design value vs recomputation

B = 4.04 was computed on the breadth pull (Yahoo), which is unfit for backtesting and confined
to the breadth calculation. The pre-declared rule, fixed before the recomputation:

    |B_new − 4.04| ≤ 0.40  → carry MDE 0.77 forward
    |B_new − 4.04| >  0.40  → rerun the power simulation before §5 freezes

Recomputed on the Tiingo snapshot: **4.04. Δ = 0.00.** Rule applied: 0.77 carried forward.

---

## 5. Power

### 5.1 The number

**Minimum detectable effect at 80% power: 0.77 realised Sharpe**, bracketed between 0.53
(55.5% rejection) and 0.83 (85.8%).

Simulated, not analytic. An earlier analytic panel estimate of 0.27 was **withdrawn** — it was
wrong by a factor of 2.4 because it treated breadth as though it multiplied independent
observations of this coefficient. The simulation is authoritative.

### 5.2 Size correction

Time fixed effects alone reject at **7.8%** against a nominal 5%. The critical value is
therefore raised to **2.152**, restoring empirical size to 5%. Both the nominal and the
corrected rejection rates are reported throughout; §5.1's figures use the corrected value.

### 5.3 Analytic comparison

The portfolio-Sharpe route gives an analytic MDE of 0.70 against the simulation's 0.77 — two
independent routes agreeing within 10%. This is corroboration, not the headline.

---

## 6. Robustness — pre-committed

### 6.1 Composition checks (not bounds)

Two checks, both fixed before the result:

**Exclude the best instrument** — the **cross-sectional** axis, named explicitly. (Survivorship
is a cross-sectional problem; a best-*year* exclusion would test something else.)

**1,000-draw random-subset stability**, seed **20261101**. Subsets of 12 drawn from 18.
The pass/fail statistic is **p5 of the subset distribution** — the conservative bound.
The **full-universe percentile within that distribution** is reported alongside as a
descriptive diagnostic, because it is what detects composition dependence: a full-universe
effect at the 95th percentile means the chosen eighteen are unusually favourable.

### 6.2 What these checks do not do

**They do not bound survivorship.** They bound *sensitivity to universe composition*. True
survivorship bias cannot be quantified without delisted-fund data. §10 states this as a
non-claim, and §12 repeats it so the two cannot slide together.

---

## 7. Specification exclusions, with the measured cost

Asset-class fixed effects were rejected. All three reasons are recorded because the third
was found only after the first two:

**Cost.** MDE rises from 0.77 to **0.95** — a loss of 0.18, not the 0.05 assumed before
measurement. Rejection at realised Sharpe 0.53 falls from 55.5% to **38.7%**: a third of the
power, not a tenth.

**Estimand.** Class demeaning subtracts the class-level mean trend. Class-level trend is where
time-series momentum lives — bonds all trending together *is* the signal. What survives is
within-class dispersion, a cross-sectional question, not the one the literature asks.

**Size.** Class FE reject at **9.7%** nominal against time FE's 7.8%, so its MDE is only
comparable after its own calibration (critical value 2.365 vs 2.152). A specification that is
both less powerful and more mis-sized is not a control, it is a different study.

**And 0.95 is disqualifying on its own**: at or above the top of the pre-decay historical
range, a bound of 0.95 excludes nothing the study exists to test.

A bias-corrected instrument-FE estimator (half-panel jackknife, Dhaene–Jochmans) is noted as a
**possible extension, explicitly not attempted**.

---

## 8. Deviations

Every departure from this document is logged in `DEVIATIONS.md` with a date and the cost to
the claim. Entry 1 records the audit correction.

Deviations are expected. A deviation log that stays empty is more likely to indicate
under-reporting than a clean run.

---

## 9. Pre-committed readings

| Outcome | Reading |
|---|---|
| Null, both composition checks pass | Effect excluded above 0.77. The pipeline is validated. Decay band unresolved. |
| Null, exclude-best fails | Result is driven by one instrument. Reported as such; the bound is not claimed. |
| Null, p5 ≤ 0 | Subset distribution crosses zero. Composition-dependent. Bound not claimed. |
| Positive, inside pre-2011 published range | Effect live. Report magnitude, all cost assumptions, and the roll-yield gap. |
| Positive, above the published range | Suspect the pipeline before the market. Investigate before reporting. |
| Positive, driven by a single asset class | Report the class decomposition; do not headline the aggregate. |
| Any outcome, full-universe percentile ≥ 95 | Composition dependence flagged prominently regardless of the headline. |

---

## 10. Deliberate non-claims

1. **No survivorship bound.** Declared, direction positive, not quantifiable.
2. **No law relating contamination to N and T.** Measured exponents are approximately N^0.27
   and T^−0.72 against a predicted N^0.5/T^−0.5. §2A of the write-up states the mechanism,
   the measured exponents, and **explicitly declines to claim a law**. The likely confound is a
   HAC lag of 52 against T = 260 (the standard Newey–West rule gives ≈5); disentangling them
   is a separate design.
3. **No claim about futures-based TSMOM.** Different construction, different return.
4. **No causal claim.** This is a measurement, not an identification.

---

## 11. Threats to validity, stated before results

- **Survivor-selected universe** — §2.2, §6.2, §10.
- **Single vendor, no independent cross-check** — Stooq unobtainable; recorded per instrument.
- **Weekly resampling** discards intraweek information; the last observation of each week is
  used, which is a convention not a measurement.
- **ETF tracking error and expense** are inside the price series and are not separated out.
- **Roll-free construction** — §1.3.
- **One effect, one specification, one sample.** No multiple-testing correction is needed
  because only one hypothesis is tested, but this also means one result is one result.

---

## 12. Repository integrity

- Pre-registration committed and tagged **`v0.1-prereg`** before any strategy return is
  computed. The tag is **never** moved, amended or force-pushed.
- Pre-registration also registered on **OSF** for an independent DOI and timestamp.
- **Two snapshots, two hashes, never regenerated.** `data/raw/` and `data/snapshots/` are
  gitignored; `data/snapshot_manifest.json` and `data/audit.json` are committed so a fresh
  clone can re-pull and verify rather than re-derive.
- No vendor data is committed.
- Code committed with the pre-registration: `scripts/fetch_data.py`, `scripts/design_inputs.py`,
  `scripts/audit_snapshot.py`, and `src/` (the breadth and power work that produced §4 and §5).

---

## 13. Sign-off

Design frozen: 2026-11-01.
No strategy return has been computed at the time of writing.
