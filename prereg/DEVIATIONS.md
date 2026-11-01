# Deviations log — `tsmom-panel-study`

Every departure from `PREREGISTRATION.md`, dated, with what it cost the claim.

A deviation log that stays empty is more likely to indicate under-reporting than a clean run.
Deviations recorded before the pre-registration was frozen are listed separately from those
made after, because only the latter can affect a claim.

---

## Before freeze (2026-11-01)

These are design corrections made while the design was still open. They are recorded here for
the audit trail rather than as deviations from a frozen document.

### Entry 1 — total-return audit, v1 → v2

**What happened.** The first audit run failed on 15 of 18 instruments and instructed that no
pre-registration be frozen on the snapshot.

| Instrument | Reported deviation |
|---|---|
| USO | 7.854 |
| EWJ | 3.018 |
| BWX | 0.4976 |
| DBC | 5.32e-02 |
| EFA | 2.456e-02 |
| EEM | 2.118e-02 |
| IYR | 1.419e-02 |
| TIP | 1.288e-02 |
| IWM | 8.637e-03 |
| SPY | 7.154e-03 |
| QQQ | 5.622e-03 |
| LQD | 4.312e-03 |
| TLT | 4.273e-03 |
| IEF | 3.605e-03 |
| FXE | 2.000e-03 |
| GLD, SLV, FXY | 0 (no distributions, no splits) |

**Diagnosis.** Two defects in the audit, not in the data.

*Defect 1 — split gap.* The audit removed rows where `splitFactor ≠ 1` and then called
`pct_change()`. The row following a split therefore computed its return against the row
*before* the split, spanning it. USO (1:8 reverse), EWJ (4:1) and BWX (2:1) reported
deviations equal to their split ratios — which is what identified the cause.

*Defect 2 — multiplicative dividend factor.* The audit formed the implied return as
`price_return × (1 + div/close_prev)`. The correct total return is
`(close + divCash)/close_prev × splitFactor − 1`. The two differ by a residual of roughly the
dividend yield on any day with a large price move, which is why the remaining twelve showed
deviations scaling with their distribution counts (IEF, TLT and LQD each carry 189
distributions and sit mid-range).

*Defect 3 — tolerance.* The failure threshold was `1e-6` on a daily return. Vendor prices are
rounded, so no instrument with distributions could pass that threshold regardless of data
quality.

**Correction.** The formula and the tolerance were both fixed, giving
`max_abs_dev` with a tolerance of `1e-9` — floating-point noise, chosen because the corrected
formula reproduces the series to ~1e-12 and not because it admits the observed values.

**Result after correction:** worst deviation **9.44e-12** across all 18 instruments; zero days
exceeding 1e-3. Audit output committed as `data/audit.json`.

**Cost to the claim: none.** No data was re-pulled. The panel hash
`44dced9f55ace2997ad17bbbec5202d472810d342fd14e583ba5af48d8c603c1` is unchanged from the
original pull, so the audit correction verified the same snapshot rather than a new one.

**Why this is recorded rather than quietly fixed.** The audit's job is to catch a data fault
before it becomes an unfixable result. Here it caught its own fault, which is the better
failure. A reader can check both formulas against the committed snapshot; the point of
writing it down is that they should not have to take the correction on trust.

---

## After freeze

Entries 2–8 were written on 2026-11-01, the day the backtest was first run. The choices they
record were fixed in `src/backtest.py` before that run; the write-up followed immediately
after it, with the numbers in hand. That is stated plainly because it is the weaker
position: a choice fixed before the run can be checked against the result, but a choice
described after it cannot be distinguished from one made to suit it. Where an entry claims
a choice did not matter, the claim is a measurement taken from the run, not a prediction.

None of them changes the data, the universe, the window or the estimator that was run.
Entries 6–8 affect what can be claimed from it.

### Entry 2 — the Sharpe interval was never specified

**What the document says.** §5.1 quotes an MDE in Sharpe units and §1.2 quotes an exclusion
bound of 0.77. Neither names an interval, and the claim as written is a threshold on one.

**Decision.** Primary: stationary block bootstrap on the weekly portfolio returns, mean
block 13 weeks, 20,000 resamples, seed 20261101, 95% percentile interval. Secondary: the
Lo (2002) interval with skew and kurtosis correction, reported alongside.

**Why the block.** The signal is a 52-week trailing sum, so the sign of the position
persists across long runs and weekly returns are not iid. An iid bootstrap would narrow the
interval, and a narrower interval makes the exclusion bound easier to claim — the one
direction this choice must not flatter.

**Cost.** The interval is the claim. The two constructions agree to 0.001 (upper bounds
1.054 and 1.053), so the choice is immaterial to the decision. That was checked after the
fact, not assumed.

### Entry 3 — "time-clustered" standard errors were never defined

**What the document says.** §3.3 requires time-clustered standard errors. It does not name
a kernel, a bandwidth or a cluster estimator.

**Decision.** Newey–West with a Bartlett kernel at lag 52 — the estimator used by the power
study that produced 2.152 (`src/power_sim.py::regression_t`). Any other estimator would be
compared to a critical value calibrated for this one, which would make the correction
meaningless.

**Cost.** Measured on the same panel: t = 2.079 at lag 52, 1.656 at lag 5 (the bandwidth
§10 quotes for T = 260), 1.641 for a CR1 time-cluster sandwich. The distance from 2.152 is
therefore a property of the bandwidth, not of the market. §10 of the pre-registration
already flags lag 52 against T = 260 as a likely confound; this confirms it matters. The
alternate-lag numbers are **not** valid substitutes — their null distributions have not
been calibrated — so only the lag-52 figure is compared to 2.152.

### Entry 4 — the regressor's units were never fixed

**What the document says.** §3.1 defines the signal as the 52-week trailing total return;
§3.3 says what to regress it on but not in what units.

**Decision.** Primary: the signal divided by its own rolling annualised σ, because that is
what the simulation used (`src/power_sim.py::pairs`), and 0.77 and 2.152 were calibrated on
it. Variant: the raw 52-week return, reported alongside.

**Cost.** t = 2.079 standardised, 1.766 raw. Neither rejects at 2.152. The 0.31 gap is
larger than the 0.07 margin the primary clears the threshold by, so the variant is reported
rather than dropped.

### Entry 5 — "the best instrument" was never defined

**What the document says.** §6.1 requires excluding "the best instrument" and names the
cross-sectional axis, without saying what makes one instrument best.

**Decision.** Highest standalone annualised Sharpe on that instrument's own sign/σ strategy
over the same window; the check recomputes both the interval and the regression on the
remaining 17.

**Cost.** None to the decision. QQQ is best (standalone Sharpe 0.756); removing it moves the
portfolio to 0.455, which does not change either reading. Recorded because the check's
meaning depends on the definition, and the definition was chosen after seeing the data.

### Entry 6 — the decision rule is not stated, and the one the document implies is wrong

**What the document says.** §1.2 and §5.1: the MDE at 80% power is 0.77, therefore "a null
result excludes a live effect above 0.77". §9 then reads a null as "Effect excluded above
0.77".

**Why that does not follow.** A test with 80% power at 0.77 misses an effect of exactly 0.77
one time in five. Failing to reject therefore does not exclude 0.77; it fails to detect it.
Exclusion comes from an interval on the effect, not from the power figure. The document's
phrasing turns a statement about the design's resolution into a statement about the effect,
which is the error §0.2 and §3.4 were written to prevent — in the opposite direction.

The document also never says which statistic carries the claim: the regression's failure to
reject, or an interval on the realised Sharpe.

**Decision.** Both are computed and reported. The interval governs the exclusion bound,
because a bound is a statement about effect size. Where the two disagree, the bound is not
claimed.

**Cost.** This is the claim. With a realised Sharpe of +0.53 and a 95% interval of
[0.04, 1.05], the upper bound is 1.05: **the pre-registered exclusion bound of 0.77 is not
established.** The regression fails to reject at 2.152, which under §1.2's prose would have
licensed reporting "excluded above 0.77". Reporting that sentence would have been wrong, and
the two statistics disagreeing is the evidence that it is wrong.

§9's outcome table has no row for this result either. It offers "null", "positive inside the
published range" and "positive above it", but not "positive and not distinguishable from zero
at the corrected threshold", which is the row that applies: an estimate of +0.53 with a
corrected t of 2.079 is a positive point estimate that the registered test cannot separate
from zero, and it is not a null.

### Entry 7 — σ is estimated here and was fixed in the calibration

**What happened.** The power study standardised the signal by each instrument's full-sample
σ — a constant. A backtest cannot do that: a full-sample σ is a look-ahead, so §3.2's
rolling 52-week σ is estimated inside the sample. The calibration's 0.77 and 2.152
therefore describe a regressor with less estimation noise than the one that was run, and
the true size of the adopted test is not known to be 5%.

**Not resolved.** Resolving it means rerunning the power simulation with a rolling σ, which
is a post-freeze change to the design inputs and would need its own entry and its own cost.
It is left recorded rather than quietly patched.

**Cost.** None to the headline, which fails on the interval regardless. It does mean the
secondary claim "the regression is correctly sized at 2.152" is unverified.

### Entry 8 — the Sharpe the MDE is measured on is not the Sharpe §3.2 runs

**What happened.** The power study's realised Sharpe is `mean(z·y)/std(z·y)` with z the
standardised signal (`src/study3.py::strat_sr`) — a portfolio weighted by signal magnitude.
§3.2 runs `sign(signal)/σ` — a portfolio weighted by sign and inverse volatility. These are
different portfolios, so 0.77 is expressed in the units of one and the result in the units
of the other.

**Measured on the frozen panel.** Signal-weighted +0.545; inverse-vol sign/σ as run +0.526;
equal-weight sign +0.449. The first two are within 4% of each other on this sample, so for
the portfolio that was actually run the translation is mild — 0.77 in the simulation's units
is roughly 0.74 in its units. The equal-weight sign portfolio sits 18% below the
signal-weighted one, so a sentence that says only "0.77 realised Sharpe" could mean anything
from about 0.64 to 0.77 depending on which portfolio it is read against.

**Not resolved**, because resolving it means re-deriving the MDE on the portfolio that is
run, which is a rerun of §5 after freeze.

**Cost.** It does not change the decision: the interval's upper bound (1.05) is above 0.77
and above every translated bound in that range, so no exclusion is supportable either way.
It does mean the sentence "the minimum detectable effect is 0.77 realised Sharpe" cannot be
carried into the write-up without saying which portfolio the MDE is measured on — and the
pre-registration does not say.

---

## Run record

**2026-11-01.** `src/backtest.py` first run. Snapshot `20261101T130536Z-44dced9f`, panel
SHA-256 verified `44dced9f…c603c1` before load; 826 weekly closes, 774 signal observations,
773 portfolio weeks; B recomputed 4.04 (signal) against the registered 4.04. No data was
re-pulled, regenerated or amended. Output `results/backtest.json`.

Result: realised Sharpe **+0.526**, 95% interval [0.038, 1.054]; regression t = **+2.079**
against the corrected critical value 2.152; exclude-QQQ +0.455; 1,000 subsets of 12, p5
+0.341, full-universe percentile 58.8. No exclusion claimed.

---

## Repository defects found during the build

Not deviations from the pre-registration; defects in the artefacts the pre-registration
points at. Recorded so they are fixed deliberately rather than discovered by a reader.

1. **`data/snapshot_manifest.json` carries the superseded audit.** Its `total_return_audit`
   block has the v1 schema and the v1 numbers — USO 7.854, EWJ 3.018, BWX 0.4976 — which are
   the failures DEVIATIONS entry 1 identifies and corrects. `data/audit.json` (v2) and
   §2.5 disagree with it. Cause: `fetch_data.py` wrote the manifest before aborting on the
   v1 audit, and it short-circuits on an existing snapshot, so the manifest was never
   regenerated after the correction. A reader who trusts the manifest concludes the panel
   failed its own audit.
2. **`data/snapshot_manifest.json` has an empty `stooq_crosscheck`.** §2.1 says the failure
   is recorded per instrument as `unavailable` for all eighteen; the manifest records
   nothing.
3. **`data/SOURCES.md` §3 describes the v1 audit as the method** — non-split days only,
   tolerance 1e-6 — which entry 1 calls a defect on three counts.
4. **`v0.1-prereg` is not on the remote.** The annotated tag exists locally (2d3ab67,
   2026-11-01 18:57 +0530, before the OSF registration at 14:15Z) but `git ls-remote --tags`
   returns nothing, so the repository publishes one timestamp, not the two that README and
   §12 claim. Fix is a tag push; it must not be re-created or moved.
5. **`src/` cannot be run from a fresh clone.** `src/power_sim.py` reads
   `artefact1/breadth_snapshot_2005.csv` and imports `breadth`, whose `OUTDIR` is
   `artefact1`; neither exists in the repository. §12 claims the code producing §4 and §5 is
   committed, which is true, but it does not run without an uncommitted scratch directory.

---

### Entry 9 — §9's outcome table has no row for the observed outcome

**What happened.** §9 pre-commits a reading to each possible outcome. The observed outcome —
a positive, composition-robust estimate that this design cannot distinguish from zero — is not
among them. The table anticipated a null, a composition failure, and a positive result inside
or above the published range. It did not anticipate *positive but unresolvable*, which is what
a design whose MDE (0.77) exceeds the effect it is measuring (≈0.5) will produce whenever the
effect is real.

**Handling.** The reading is stated in `RESULTS.md` and is flagged there as **post hoc**. The
gap is recorded here rather than patched into the frozen pre-registration.

**Cost to the claim.** The numbers are unaffected. What is affected is interpretive
discipline: the reading was not pre-committed, so a reader cannot verify it was not chosen
after seeing the data. That is the whole reason §9 exists, and this is the one place in the
study where it failed.

---

### Entry 10 — §2.1 states a per-instrument cross-check record that the run never produced

**What §2.1 says.** "A Stooq cross-check was attempted and refused: Stooq returns a JavaScript
challenge page rather than CSV on every URL form tried, so the cross-check is recorded in the
manifest as `unavailable` for all eighteen instruments."

**What the artifacts show.** The pull was run with `--skip-stooq`. `fetch_data.py` initialises
`stooq_rows = []` and fills it only inside `if not args.skip_stooq:`, so an empty list in the
manifest is the signature of a loop that never ran — had it run, it would have written eighteen
rows whatever their status. No request was made for any instrument and no response was
received. The HTML challenge was seen by a separate probe in the same session, which is
presumably where the sentence came from, but that probe was not the pull and recorded nothing
per instrument.

**What was wrong for one commit.** The defect-2 fix wrote eighteen `"unavailable"` records
into the manifest, reasoning from the code's failure branch and from that probe. The provenance
block disclosed the reconstruction, but the records themselves still asserted a per-instrument
response — and disclosing an invented record does not make it a record. Reverted the same day;
`stooq_crosscheck` is empty again.

**Cost to the claim.** None to the numbers: the cross-check never entered the inference, and
§11 already lists "single vendor, no independent cross-check" as a threat. The cost is to
§2.1's accuracy, and to any reader who treats the manifest as a log of requests made. The gap
is now visible; before, §2.1 said the record existed, so nobody had reason to look for it.

**Why recorded rather than repaired.** A genuine per-instrument record requires running the
cross-check against the frozen snapshot. That has not been done, and writing the records
without doing it is the error this entry documents.

---

## Corrections to the repository defect list

**Defect 1 — FIXED 2026-11-01.** `data/snapshot_manifest.json` now carries the v2 audit
(worst deviation 9.44e-12, `passed: true`) plus an `audit_correction` block recording the
superseded v1 numbers (USO 7.854, EWJ 3.018, BWX 0.4976), naming the three v1 defects, and
pointing at `data/audit.json` and entry 1. The panel SHA-256 is unchanged — only the
verification record was corrected, not the data.

**Defect 4 — WITHDRAWN, false positive.** `v0.1-prereg` **is** on the remote.
`git ls-remote --tags origin` returns both `refs/tags/v0.1-prereg` (`8723e0a9`, the annotated
tag object) and `refs/tags/v0.1-prereg^{}` (`2d3ab67`, the commit). The original report was
inferred from an `ls-remote` that failed with `SEC_E_NO_CREDENTIALS` — a credential failure,
not a missing ref. **A failed network call is not evidence of absence.** Both timestamps are
public and the claim in README and §12 stands.

**Defect 2 — NOT FIXED; recorded as a gap.** A first attempt wrote eighteen `"unavailable"`
records into `stooq_crosscheck`. That was wrong and has been reverted: the pull ran with
`--skip-stooq`, so no per-instrument request was made and no response was received, and the
records asserted an event that did not happen. `stooq_crosscheck` is empty again — the true
state — and `stooq_crosscheck_provenance` in the manifest records what happened, why it
matters, and that it was not backfilled. The misstatement in §2.1 is entry 10.

**Defect 3 — FIXED 2026-11-01** (by the author). `data/SOURCES.md` §3 now documents the v2
audit as the method — full series including split days, split factor applied, tolerance 1e-9,
worst deviation 9.44e-12 — and lists the three v1 defects as defects.

**Defect 5 — FIXED 2026-11-01.** `src/power_sim.py` no longer reads an uncommitted `artefact1/`
directory. The simulation consumes exactly two objects, the correlation matrix and the vector
of weekly sigmas, so those are committed as `data/breadth_inputs.json` with the source
snapshot's SHA-256 (`e4b78952…`), and `scripts/build_breadth_inputs.py` regenerates the file
from a local copy of the pull. `python src/study3.py` runs from a fresh clone and reproduces
§5 exactly: 7.8% size at time FE with critical value **2.152**, instrument + time 13.3% and
mean t −0.44, class FE 9.7% with critical value 2.365, 55.5% rejection at realised Sharpe 0.53,
85.8% at 0.83, MDE 0.77 bracketed 0.53–0.83.

What defect 5 did **not** cover, and what is still true: `src/breadth.py`, `src/power.py`,
`src/branch_eval.py` and `src/residual_breadth.py` still require a local copy of the Yahoo
breadth pull at `artefact1/breadth_snapshot_2005.csv`. That file is not committed, and no
committed script regenerates that exact pull — `src/breadth.py` fetches a different,
2011-onward snapshot. The §4 breadth numbers are therefore checkable against a local pull but
not reproducible from a bare clone. Recorded rather than papered over, because committing the
return series would be committing the vendor data the licence terms forbid.

