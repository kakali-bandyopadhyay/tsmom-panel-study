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

Nothing yet. The pre-registration was committed and tagged before any strategy return was
computed.
