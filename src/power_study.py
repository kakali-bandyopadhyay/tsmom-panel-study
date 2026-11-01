"""Artefact 1 — simulation-based power study.

Findings so far, in order:

1. The analytic MDE (0.28-0.32) was a placeholder; this replaces it with a measured one.
2. Size diagnostic under the null showed the estimator is mis-sized, and located the cause:
   instrument fixed effects reject 17.7% of the time at a nominal 5%, while time fixed
   effects alone reject 8.7%.

   Why: the signal is a trailing 52-week sum of the dependent variable, so each
   instrument's time-mean of the signal is almost exactly a scaled copy of its time-mean
   of the return. Within-instrument demeaning therefore subtracts mechanically related
   quantities from regressor and outcome alike, inducing a negative covariance -- mean t
   of -0.74 under the null, with no true effect present. The bias scales roughly as
   sqrt(N/T), so it grows with breadth and shrinks with sample length; at N=18, T=773 it
   is material.

   This is a property of the data structure, not of the simulation: the same mechanical
   relation holds in the real panel.

3. Consequence: the planned specification (instrument AND time FE) is not usable as
   stated. Power is computed here for time FE alone, which absorbs the common factor --
   the reason the panel was attractive in the first place -- without the instrument-mean
   contamination.

Scope held to what was agreed: three planted effects, 1,000 replications, no sweeps.
"""

import time

import numpy as np

from power_sim import (CRIT, HAC_LAG, LOOKBACK, REPS, SEED, TARGETS, T_WEEKS,
                       load_panel, pairs, regression_t, simulate)


def strategy_sharpe(z, y):
    sr = (z * y).mean(axis=1)               # per-rep weekly portfolio return series
    mu = sr.mean(axis=0)
    sd = sr.std(axis=0, ddof=1)
    return np.sqrt(52) * mu / sd


def main():
    rng = np.random.default_rng(SEED)
    corr, sigma = load_panel()
    L = np.linalg.cholesky(corr)

    t0 = time.time()
    # null: strategy volatility for calibration, and size for both candidate specs
    r0 = simulate(0.0, L, sigma, REPS, rng)
    z0, y0 = pairs(r0, sigma)
    sr0 = strategy_sharpe(z0, y0)
    # time-series volatility of the portfolio return, averaged over replications --
    # not the dispersion of the mean across replications
    sr_series = (z0 * y0).mean(axis=1)          # (T, R)
    sig_w = float(sr_series.std(axis=0, ddof=1).mean())
    print(f"null size, time FE only   : {np.mean(np.abs(regression_t(z0, y0, 'time')[0]) > CRIT):.3f}")
    print(f"null size, instrument+time: {np.mean(np.abs(regression_t(z0, y0, 'both')[0]) > CRIT):.3f}")
    print(f"null realised Sharpe      : {sr0.mean():+.3f}")
    print(f"strategy weekly vol (null): {sig_w:.5f}\n")

    results = {}
    for spec in ("time", "both"):
        print(f"--- specification: {spec} FE ---")
        print(f"{'target':>7s} {'theta':>10s} {'realised Sharpe':>16s} {'rejection':>10s}")
        rows = []
        for S in TARGETS:
            theta = S * sig_w / np.sqrt(52)
            rr = simulate(theta, L, sigma, REPS, rng)
            z, y = pairs(rr, sigma)
            t, _, _ = regression_t(z, y, spec)
            rej = float((np.abs(t) > CRIT).mean())
            real = float(strategy_sharpe(z, y).mean())
            rows.append((real, rej))
            print(f"{S:7.2f} {theta:10.6f} {real:16.3f} {rej:10.3f}")
        xs = np.array([r[0] for r in rows])
        ys = np.array([r[1] for r in rows])
        o = np.argsort(xs)
        xs, ys = xs[o], ys[o]
        if ys.min() < 0.8 < ys.max():
            mde = float(np.interp(0.8, ys, xs))
            print(f"MDE at 80% power: Sharpe {mde:.2f}\n")
        else:
            mde = None
            print(f"80% not bracketed (rejection {ys.min():.2f}-{ys.max():.2f})\n")
        results[spec] = (rows, mde)

    print(f"elapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
