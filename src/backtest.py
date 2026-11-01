"""Artefact 1 — the pre-registered backtest, run once against the frozen snapshot.

This script implements `prereg/PREREGISTRATION.md` §3 and §6 and nothing else. It is
deliberately not a research harness: there is no grid, no search, and no option that
changes the specification. The only arguments select an output path.

What it computes
----------------
1. Weekly closes (W-FRI, last observation) from the frozen Tiingo panel; total return is
   the ratio of consecutive `adjClose` (§2.3, §2.4). No absolute adjusted level is used
   anywhere.
2. A 52-week trailing total-return signal (§3.1), long if positive, short if negative,
   no deadband.
3. Inverse-volatility sizing `sign(signal) / sigma`, sigma the rolling 52-week standard
   deviation of weekly returns, annualised (§3.2). No portfolio-level volatility target.
4. The realised annualised Sharpe of the resulting weekly portfolio, with a confidence
   interval, tested against the pre-registered exclusion bound of 0.77 (§1.2, §5.1).
5. The pooled panel regression with **time fixed effects only** and time-clustered
   standard errors (§3.3), judged against the size-corrected critical value 2.152 (§5.2).
6. The two pre-committed composition checks: exclude the single best instrument, and
   1,000 random 12-of-18 subsets with seed 20261101, reporting p5 and the full-universe
   percentile (§6.1).

What it refuses to do
---------------------
- It refuses to run if the panel's SHA-256 is not the registered one (§12). The design
  names a snapshot; a backtest on another snapshot is a different study.
- It does not regenerate, re-pull or repair data.

Where the pre-registration is silent, or wrong
----------------------------------------------
Five choices are not fixed by the frozen document, and two of its claims do not survive
contact with the build. None is resolved silently here: each is written up with its cost
in `prereg/DEVIATIONS.md` entries 2–8, dated before this file was first run.

  (a) the regressor's units — raw 52-week return, or divided by sigma as in the power
      simulation. The simulation decides it: the 0.77 MDE and 2.152 were calibrated on
      the sigma-standardised regressor, so that is the primary and the raw form is
      reported as a variant. [entry 4]
  (b) the standard-error estimator — §3.3 says "time-clustered"; the simulation that
      produced 2.152 used Newey-West with a Bartlett kernel at lag 52. That estimator is
      used so the critical value applies. [entry 3]
  (c) the Sharpe interval's construction — §3 never names one. Stationary block bootstrap
      is primary (mean block 13 weeks, 20,000 draws, seed 20261101); the Lo (2002)
      asymptotic interval is reported alongside, and if the two disagree the claim is not
      made. [entry 2]
  (d) whether "the claim holds" is read through the regression test or through the Sharpe
      interval's upper bound. The registration never says, and the two turn out to
      disagree, so both are reported. [entry 6]
  (e) "the best instrument" for the exclusion check — defined here as the highest
      standalone annualised Sharpe. [entry 5]

Two further problems, logged rather than patched:

  (f) the calibration fixes sigma at its full-sample value; a backtest has to estimate it
      on a rolling window, so the 2.152 critical value describes a slightly different
      estimator. [entry 7]
  (g) the Sharpe the MDE is expressed in is a signal-magnitude-weighted portfolio; §3.2
      runs a sign/inverse-vol portfolio. The units are not interchangeable. [entry 8]

Nothing else in this file is a choice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SNAPSHOTS = REPO / "data" / "snapshots"
RESULTS = REPO / "results"

# ------------------------------------------------------------------ frozen constants
# Every number in this block is copied from the pre-registration, not chosen here.
TICKERS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ",
    "TLT", "IEF", "TIP", "LQD", "BWX",
    "GLD", "SLV", "DBC", "USO",
    "FXE", "FXY", "IYR",
]
START = "2011-01-01"
LOOKBACK = 52
HAC_LAG = 52
CRIT_NOMINAL = 1.959964
CRIT_CORRECTED = 2.152        # §5.2, calibrated to 5% empirical size
MDE_SHARPE = 0.77             # §5.1, 80% power
EXCLUSION_BOUND = 0.77        # §1.2, the number the claim quotes
SEED = 20261101               # §6.1
SUBSET_SIZE = 12              # §6.1
SUBSET_DRAWS = 1000           # §6.1
WEEKS_EXPECTED = 826          # §2.3
SIGNAL_OBS_EXPECTED = 774     # §2.3
B_RETURNS_EXPECTED = 4.687    # §4.2
B_SIGNAL_EXPECTED = 4.0412    # §4.2
B_DESIGN = 4.04
B_TOLERANCE = 0.40            # §4.4

# Snapshot identity (§2, §12). Both must match or the run is void.
SNAPSHOT_ID = "20261101T130536Z-44dced9f"
PANEL_SHA256 = "44dced9f55ace2997ad17bbbec5202d472810d342fd14e583ba5af48d8c603c1"

# (c) Sharpe interval: choices logged in DEVIATIONS entry 2, fixed before the first run.
BOOT_REPS = 20000
BOOT_MEAN_BLOCK = 13.0        # weeks; one quarter
CI_LEVEL = 0.95


# ------------------------------------------------------------------------ provenance
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_snapshot(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        return p if p.is_dir() else p.parent
    found = sorted(SNAPSHOTS.glob("*/panel.csv"))
    if not found:
        raise SystemExit(
            f"no frozen snapshot under {SNAPSHOTS}\n"
            "the backtest runs on the registered snapshot only; run scripts/fetch_data.py "
            "or point --snapshot at a snapshot directory."
        )
    return found[-1].parent


# -------------------------------------------------------------------------- loading
def load_weekly(snapshot: Path) -> pd.DataFrame:
    """Wide weekly closes, W-FRI last observation, on the registered window.

    Mirrors scripts/design_inputs.py::load_panel so that the breadth reconciliation in
    `reconcile_design_inputs` is computed on exactly the frame the design inputs were.
    """
    df = pd.read_csv(snapshot / "panel.csv", parse_dates=["date"])
    wide = df.pivot(index="date", columns="ticker", values="adjClose")
    cols = [c for c in TICKERS if c in wide.columns]
    if len(cols) != len(TICKERS):
        raise SystemExit(f"panel is missing instruments: {set(TICKERS) - set(cols)}")
    wide = wide[cols].sort_index()
    wk = wide.resample("W-FRI").last()
    wk = wk[wk.index >= START]
    wk = wk.dropna(how="any")
    if wk.shape[1] != 18:
        raise SystemExit(f"expected 18 instruments, found {wk.shape[1]}")
    return wk


def build_series(wk: pd.DataFrame):
    """Returns, signal, rolling sigma, and the forward return the position earns.

    Alignment, in weeks: the signal and sigma at week t use data through t's close; the
    position is held over week t+1; the return it earns is `fwd`. One week of gap, no
    overlap, no same-week information.
    """
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    sig = (wk / wk.shift(LOOKBACK) - 1.0).dropna(how="any")
    sigma = rets.rolling(LOOKBACK, min_periods=LOOKBACK).std(ddof=1).dropna(how="any")
    sigma_ann = sigma * math.sqrt(52.0)

    common = sig.index.intersection(sigma.index)
    sig, sigma_ann = sig.loc[common], sigma_ann.loc[common]

    fwd = rets.shift(-1)
    fwd = fwd.loc[common].dropna(how="any")
    sig, sigma_ann = sig.loc[fwd.index], sigma_ann.loc[fwd.index]

    if (sigma_ann <= 0).to_numpy().any():
        raise SystemExit("non-positive volatility in a sizing window")

    weights = np.sign(sig) / sigma_ann          # §3.2: sign(signal) / sigma
    return rets, sig, sigma_ann, weights, fwd


# ------------------------------------------------------------------------ statistics
def sharpe_annual(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    return float(math.sqrt(52.0) * r.mean() / sd) if sd > 0 else float("nan")


def stationary_bootstrap_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano stationary bootstrap: geometric block lengths, wrapped indices."""
    p = 1.0 / mean_block
    out = np.empty(n, dtype=np.int64)
    pos = 0
    while pos < n:
        start = int(rng.integers(0, n))
        length = int(rng.geometric(p))
        end = min(pos + length, n)
        out[pos:end] = (start + np.arange(end - pos)) % n
        pos = end
    return out


def bootstrap_sharpe_ci(x: np.ndarray, reps: int, mean_block: float, seed: int,
                        level: float) -> dict:
    """Percentile interval for the annualised Sharpe under a stationary block bootstrap.

    Blocks are needed because the strategy's weekly returns are not iid: the signal is a
    52-week trailing sum, so the sign persists across long runs. An iid bootstrap would
    understate the interval and make the exclusion bound easier to claim.
    """
    rng = np.random.default_rng(seed)
    n = len(x)
    draws = np.empty(reps, dtype=float)
    for b in range(reps):
        draws[b] = sharpe_annual(x[stationary_bootstrap_indices(n, mean_block, rng)])
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(draws, [a, 1.0 - a])
    return {"method": f"stationary block bootstrap, mean block {mean_block:g}w",
            "reps": reps, "seed": seed, "level": level,
            "lo": float(lo), "hi": float(hi),
            "median": float(np.median(draws)),
            "p_gt_bound": float(np.mean(draws > EXCLUSION_BOUND))}


Z_95 = 1.959964


def lo2002_ci(returns: np.ndarray, level: float) -> dict:
    """Lo (2002)/Mertens (2002) asymptotic interval, skew- and kurtosis-adjusted.

    Reported as a cross-check on the bootstrap, not as the primary interval: it assumes
    stationarity and asymptotic normality of the Sharpe estimator, both of which the
    52-week overlapping signal makes doubtful.
    """
    if level != 0.95:
        raise SystemExit("only the 95% interval is implemented; the level is a logged choice")
    r = np.asarray(returns, dtype=float)
    n = len(r)
    sr_p = r.mean() / r.std(ddof=1)
    c = r - r.mean()
    m2 = (c ** 2).mean()
    skew = (c ** 3).mean() / m2 ** 1.5
    kurt = (c ** 4).mean() / m2 ** 2.0            # raw kurtosis, normal = 3
    var_p = (1.0 - skew * sr_p + (kurt - 1.0) / 4.0 * sr_p ** 2) / (n - 1)
    se_ann = math.sqrt(52.0) * math.sqrt(max(var_p, 0.0))
    sr = math.sqrt(52.0) * sr_p
    return {"method": "Lo (2002) asymptotic, skew/kurtosis adjusted",
            "lo": float(sr - Z_95 * se_ann), "hi": float(sr + Z_95 * se_ann),
            "se": float(se_ann), "skew": float(skew), "kurtosis": float(kurt)}


def time_fe_nw_t(x: pd.DataFrame, y: pd.DataFrame, lag: int) -> tuple[float, float]:
    """Pooled slope with time fixed effects only, Newey-West (Bartlett) standard errors.

    `x` and `y` are T x N frames sharing an index. Time demeaning is applied to both
    sides; the constant is absorbed. This is the estimator the power simulation used
    (`src/power_sim.py::regression_t(..., "time")`), which is why the calibrated critical
    value applies to it. See DEVIATIONS entry 3(b).
    """
    xd = x.to_numpy(dtype=float)
    yd = y.to_numpy(dtype=float)
    xd = xd - xd.mean(axis=1, keepdims=True)
    yd = yd - yd.mean(axis=1, keepdims=True)

    sxx = float((xd * xd).sum())
    beta = float((xd * yd).sum() / sxx)
    u = yd - xd * beta
    g = (xd * u).sum(axis=1)
    s = float((g * g).sum())
    for k in range(1, lag + 1):
        w = 1.0 - k / (lag + 1.0)
        s += 2.0 * w * float((g[k:] * g[:-k]).sum())
    var = s / (sxx ** 2)
    return float(beta / math.sqrt(max(var, 1e-30))), beta


def evaluate(weights: pd.DataFrame, fwd: pd.DataFrame, sig: pd.DataFrame,
             sigma_ann: pd.DataFrame) -> dict:
    """One pass of the registered pipeline on a given instrument set."""
    port = (weights * fwd).mean(axis=1).to_numpy()
    sr = sharpe_annual(port)
    ci = bootstrap_sharpe_ci(port, BOOT_REPS, BOOT_MEAN_BLOCK, SEED, CI_LEVEL)
    t, beta = time_fe_nw_t(sig.loc[weights.index, weights.columns] / sigma_ann.loc[weights.index, weights.columns],
                           fwd[weights.columns], HAC_LAG)
    return {"sharpe": sr, "ci_bootstrap": ci, "t": t, "beta": beta,
            "n_weeks": int(len(port)),
            "ci_upper_below_bound": bool(ci["hi"] < EXCLUSION_BOUND),
            "regression_null": bool(abs(t) <= CRIT_CORRECTED),
            "n_instruments": int(weights.shape[1])}


# ------------------------------------------------------------------- design check
def participation_ratio(corr: np.ndarray) -> float:
    lam = np.sort(np.linalg.eigvalsh(corr))[::-1]
    lam = np.clip(lam, 0.0, None)
    return float(lam.sum() ** 2 / (lam ** 2).sum())


def reconcile_design_inputs(wk: pd.DataFrame) -> dict:
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    sig = (wk / wk.shift(LOOKBACK) - 1.0).dropna(how="any")
    b_ret = participation_ratio(rets.corr().to_numpy())
    b_sig = participation_ratio(sig.corr().to_numpy())
    checks = {
        "weeks": (len(wk), WEEKS_EXPECTED),
        "signal_obs": (len(sig), SIGNAL_OBS_EXPECTED),
        "B_signal": (b_sig, B_SIGNAL_EXPECTED),
        "B_returns": (b_ret, B_RETURNS_EXPECTED),
    }
    out = {}
    ok = True
    for k, (got, want) in checks.items():
        if k.startswith("B_"):
            good = abs(got - want) <= 0.005
            out[k] = {"computed": round(got, 4), "registered": want, "match": bool(good)}
        else:
            good = int(got) == int(want)
            out[k] = {"computed": int(got), "registered": int(want), "match": bool(good)}
        ok &= good
    out["all_match"] = bool(ok)
    out["Delta_B"] = round(b_sig - B_DESIGN, 4)
    out["tolerance"] = B_TOLERANCE
    return out


# ---------------------------------------------------------------------- the backtest
def exclude_best(weights: pd.DataFrame, fwd: pd.DataFrame, sig: pd.DataFrame,
                 sigma_ann: pd.DataFrame, dropped: str, full_bound_held: bool) -> dict:
    keep = [c for c in weights.columns if c != dropped]
    res = evaluate(weights[keep], fwd[keep], sig[keep], sigma_ann[keep])
    res["excluded"] = dropped
    res["survives"] = bool(res["ci_upper_below_bound"] and res["regression_null"])
    # §9 reads a failure here as "the result is driven by one instrument". That reading is
    # only available if the full-sample bound held in the first place.
    res["diagnostic_only"] = bool(not full_bound_held)
    return res


def random_subsets(weights: pd.DataFrame, fwd: pd.DataFrame, full_sharpe: float) -> dict:
    rng = np.random.default_rng(SEED)
    cols = list(weights.columns)
    n = len(cols)
    sharpes = np.empty(SUBSET_DRAWS, dtype=float)
    for d in range(SUBSET_DRAWS):
        pick = rng.choice(n, size=SUBSET_SIZE, replace=False)
        c = [cols[i] for i in pick]
        port = (weights[c] * fwd[c]).mean(axis=1).to_numpy()
        sharpes[d] = sharpe_annual(port)
    p5 = float(np.quantile(sharpes, 0.05))
    pct = float(100.0 * np.mean(sharpes <= full_sharpe))
    return {"draws": SUBSET_DRAWS, "subset_size": SUBSET_SIZE, "seed": SEED,
            "p5": p5, "p50": float(np.quantile(sharpes, 0.50)),
            "p95": float(np.quantile(sharpes, 0.95)),
            "full_universe_percentile": pct,
            "frac_negative": float(np.mean(sharpes < 0.0)),
            "pass": bool(p5 > 0.0)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Artefact 1 — pre-registered backtest.")
    ap.add_argument("--snapshot", help="snapshot directory (default: latest under data/snapshots)")
    ap.add_argument("--out", default=str(RESULTS / "backtest.json"))
    args = ap.parse_args(argv)

    snapshot = resolve_snapshot(args.snapshot)
    panel = snapshot / "panel.csv"
    digest = sha256_file(panel)
    if digest != PANEL_SHA256:
        print(f"FROZEN SNAPSHOT MISMATCH\n  panel      {panel}\n  sha256     {digest}\n"
              f"  registered {PANEL_SHA256}\n"
              "Refusing to run: a backtest on a different panel is a different study.",
              file=sys.stderr)
        return 3

    wk = load_weekly(snapshot)
    recon = reconcile_design_inputs(wk)
    rets, sig, sigma_ann, weights, fwd = build_series(wk)
    full = evaluate(weights, fwd, sig, sigma_ann)
    port = (weights * fwd).mean(axis=1).to_numpy()
    sr = full["sharpe"]
    t_std, beta_std = full["t"], full["beta"]
    ci_boot, ci_lo = full["ci_bootstrap"], lo2002_ci(port, CI_LEVEL)

    # (a) variant: the raw 52-week signal as the regressor, no sigma standardisation.
    t_raw, beta_raw = time_fe_nw_t(sig, fwd, HAC_LAG)

    # Standalone Sharpe per instrument, for the exclusion check's definition of "best".
    solo = {c: sharpe_annual((weights[c] * fwd[c]).to_numpy()) for c in weights.columns}
    best = max(solo, key=lambda k: solo[k])
    excl = exclude_best(weights, fwd, sig, sigma_ann, best, bool(full["ci_upper_below_bound"]))

    out = {
        "snapshot": {"id": SNAPSHOT_ID, "dir": snapshot.name, "panel_sha256": digest,
                     "verified": True},
        "design_reconciliation": recon,
        "sample": {"weeks_closes": int(len(wk)),
                   "signal_obs": int(recon["signal_obs"]["computed"]),
                   "regression_pairs": int(len(fwd)),
                   "portfolio_weeks": int(len(port)),
                   "first": str(wk.index[0].date()), "last": str(wk.index[-1].date())},
        "portfolio": {
            "ann_return_arith": float(52.0 * port.mean()),
            "ann_vol": float(math.sqrt(52.0) * port.std(ddof=1)),
            "weekly_mean": float(port.mean()),
            "weekly_vol": float(port.std(ddof=1)),
            "sharpe": float(sr),
            "ci_bootstrap": ci_boot,
            "ci_lo2002": ci_lo,
            "worst_week": float(port.min()), "best_week": float(port.max()),
        },
        "regression": {
            "spec": "pooled OLS, time FE only, Newey-West Bartlett lag 52",
            "n_obs": int(len(fwd) * len(weights.columns)),
            "n_weeks": int(len(fwd)), "n_instruments": int(len(weights.columns)),
            "primary_standardised": {"t": t_std, "beta": beta_std},
            "variant_raw_signal": {"t": t_raw, "beta": beta_raw},
            "crit_nominal": CRIT_NOMINAL, "crit_corrected": CRIT_CORRECTED,
            "reject_null_nominal": bool(abs(t_std) > CRIT_NOMINAL),
            "reject_null_corrected": bool(abs(t_std) > CRIT_CORRECTED),
        },
        "robustness": {"best_instrument": best, "solo_sharpe": {k: float(v) for k, v in solo.items()},
                       "exclude_best": excl,
                       "subsets": random_subsets(weights, fwd, sr)},
    }

    # (d) the two readings of the claim, both computed, neither assumed.
    bound_ci = bool(ci_boot["hi"] < EXCLUSION_BOUND)
    null_t = not out["regression"]["reject_null_corrected"]
    out["claim"] = {
        "exclusion_bound_sharpe": EXCLUSION_BOUND,
        "ci_upper": float(ci_boot["hi"]),
        "ci_upper_below_bound": bound_ci,
        "ci_upper_below_bound_lo2002": bool(ci_lo["hi"] < EXCLUSION_BOUND),
        "regression_null_at_corrected_crit": bool(null_t),
        "readings_agree": bool(bound_ci == null_t),
        "exclude_best_survives": bool(excl["survives"]),
        "subsets_pass": out["robustness"]["subsets"]["pass"],
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------------- receipt
    print(f"snapshot      {SNAPSHOT_ID}  ({digest[:16]}…)")
    print(f"panel         {len(wk)} weekly closes x {wk.shape[1]} instruments, "
          f"{wk.index[0].date()} -> {wk.index[-1].date()}")
    print(f"reconciliation weeks {recon['weeks']['computed']}/{recon['weeks']['registered']}  "
          f"signal {recon['signal_obs']['computed']}/{recon['signal_obs']['registered']}  "
          f"B_sig {recon['B_signal']['computed']:.2f}  "
          f"{'PASS' if recon['all_match'] else 'FAIL'}")
    print()
    print(f"portfolio     {len(port)} weeks, arithmetic annual return {52*port.mean():+.3f}, "
          f"annual vol {math.sqrt(52)*port.std(ddof=1):.3f}")
    print(f"Sharpe        {sr:+.3f}   (claim quotes the exclusion bound {EXCLUSION_BOUND:.2f})")
    print(f"  bootstrap   {ci_boot['lo']:+.3f} .. {ci_boot['hi']:+.3f}   "
          f"{ci_boot['method']}, {BOOT_REPS} draws")
    print(f"  Lo (2002)   {ci_lo['lo']:+.3f} .. {ci_lo['hi']:+.3f}   "
          f"se {ci_lo['se']:.3f}, skew {ci_lo['skew']:+.2f}, kurt {ci_lo['kurtosis']:.2f}")
    print(f"  P(Sharpe > {EXCLUSION_BOUND:.2f}) {ci_boot['p_gt_bound']:.3f}")
    print()
    print(f"regression    t = {t_std:+.3f}  (beta {beta_std:+.5f})  "
          f"[raw-signal variant t = {t_raw:+.3f}]")
    print(f"  critical    2.152 corrected -> {'REJECT null' if out['regression']['reject_null_corrected'] else 'fail to reject'}"
          f";  1.96 nominal -> {'reject' if out['regression']['reject_null_nominal'] else 'fail to reject'}")
    print()
    print(f"exclude best  {best} (solo Sharpe {solo[best]:+.3f}) -> portfolio Sharpe "
          f"{excl['sharpe']:+.3f}, CI upper {excl['ci_bootstrap']['hi']:+.3f}, t {excl['t']:+.3f}")
    if excl["diagnostic_only"]:
        print("              descriptive only: the full-sample bound did not hold, so a "
              "failure after exclusion does not identify a single instrument")
    sub = out["robustness"]["subsets"]
    print(f"subsets       1000 draws of {SUBSET_SIZE}/18: p5 {sub['p5']:+.3f}, "
          f"median {sub['p50']:+.3f}, p95 {sub['p95']:+.3f}")
    print(f"  full-universe percentile {sub['full_universe_percentile']:.1f}  "
          f"({sub['frac_negative']:.1%} of subsets negative)")
    print()
    print("CLAIM          " + ("CI upper bound below 0.77" if bound_ci else "CI upper bound NOT below 0.77")
          + ";  regression " + ("null" if null_t else "significant")
          + f"  -> readings {'AGREE' if out['claim']['readings_agree'] else 'DISAGREE'}")
    print(f"written       {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
