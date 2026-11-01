"""Artefact 1 — simulation-based power study, with a size diagnostic first.

The first run produced a null rejection rate of 0.62 at a nominal 5%, with mean
t = -1.54. An estimator that rejects 62% of the time under the null cannot be used
to report a p-value, let alone a power figure. So this version diagnoses the
mis-sizing by specification before doing anything else.

Candidate cause: the signal is a trailing 52-week sum of the dependent variable, so
each instrument's time-mean of the signal is almost exactly a scaled version of its
time-mean of the return. Two-way within transformation then removes, from both
regressor and outcome, quantities that are mechanically related -- and because a
52-week-trend regressor is nearly collinear with the time dummies, the surviving
variation is small enough that the induced covariance dominates.
"""

import os
import time

import numpy as np
import pandas as pd

from breadth import OUTDIR, TICKERS

SEED = 20261101
REPS = 1000
T_WEEKS = 826
LOOKBACK = 52
HAC_LAG = 52
TARGETS = [0.2, 0.3, 0.5]
CRIT = 1.959964


def load_panel():
    df = pd.read_csv(os.path.join(OUTDIR, "breadth_snapshot_2005.csv"), index_col=0, parse_dates=True)
    cols = [c for c in TICKERS if c in df.columns]
    wk = df[cols].resample("W-FRI").last()
    wk = wk[wk.index >= "2011-01-01"].dropna(how="any")
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    return rets.corr().values, rets.std().values


def simulate(theta, L, sigma, reps, rng):
    T = LOOKBACK + T_WEEKS
    N = L.shape[0]
    Z = rng.standard_normal((T, N, reps))
    # L is the Cholesky of the correlation matrix; scale by sigma so the synthetic
    # returns carry the panel's actual volatilities, not unit variance
    e = np.einsum("ij,tjr->tir", L, Z, optimize=True) * sigma[None, :, None]
    r = np.empty((T, N, reps))
    r[:LOOKBACK] = e[:LOOKBACK]
    scale = sigma * np.sqrt(LOOKBACK)
    for t in range(LOOKBACK, T):
        z = r[t - LOOKBACK:t].sum(axis=0) / scale[:, None]
        # theta is in units of each instrument's own weekly volatility. Applying a
        # uniform theta instead makes the low-volatility names run into the feedback
        # stability bound first, which produces explosive paths rather than planted
        # effects at larger sizes.
        r[t] = theta * sigma[:, None] * z + e[t]
    return r[LOOKBACK:]


def pairs(r, sigma):
    """Signal at t-1 against return at t."""
    T = r.shape[0]
    cs = np.cumsum(r, axis=0)
    scale = sigma[:, None] * np.sqrt(LOOKBACK)
    t_idx = np.arange(LOOKBACK + 1, T)
    z = (cs[t_idx - 1] - cs[t_idx - LOOKBACK - 1]) / scale[None, :, :]
    y = r[t_idx]
    return z, y


def demean(x, both):
    if both == "none":
        return x
    if both == "instrument":
        return x - x.mean(axis=0, keepdims=True)
    if both == "time":
        return x - x.mean(axis=1, keepdims=True)
    return x - x.mean(axis=0, keepdims=True) - x.mean(axis=1, keepdims=True) + x.mean()


def regression_t(z, y, both="both"):
    zd = demean(z, both)
    yd = demean(y, both)
    Szz = (zd * zd).sum(axis=(0, 1))
    beta = (zd * yd).sum(axis=(0, 1)) / Szz
    u = yd - zd * beta[None, None, :]
    g = (zd * u).sum(axis=1)
    s = (g * g).sum(axis=0)
    for l in range(1, HAC_LAG + 1):
        w = 1.0 - l / (HAC_LAG + 1.0)
        s = s + 2.0 * w * (g[l:] * g[:-l]).sum(axis=0)
    var = s / (Szz ** 2)
    return beta / np.sqrt(np.maximum(var, 1e-30)), beta, Szz


def main():
    rng = np.random.default_rng(SEED)
    corr, sigma = load_panel()
    eig = np.linalg.eigvalsh(corr)
    L = np.linalg.cholesky(corr)
    print(f"panel N={corr.shape[0]} T={T_WEEKS} lookback={LOOKBACK} HAC={HAC_LAG} seed={SEED}")
    print(f"first factor share {eig.max()/eig.sum():.1%}\n")

    t0 = time.time()
    r = simulate(0.0, L, sigma, 400, rng)
    z, y = pairs(r, sigma)
    print(f"observations per replication: {z.shape[0]} weeks x {z.shape[1]} instruments\n")

    print("SIZE UNDER THE NULL (theta = 0), 400 reps")
    print(f"{'specification':28s} {'rejection@5%':>13s} {'mean t':>8s} {'sd t':>7s} {'mean Szz/NT':>12s}")
    for spec in ("none", "instrument", "time", "both"):
        t, beta, Szz = regression_t(z, y, spec)
        print(f"{spec:28s} {np.mean(np.abs(t) > CRIT):13.3f} {t.mean():8.2f} "
              f"{t.std():7.2f} {Szz.mean()/(z.shape[0]*z.shape[1]):12.4f}")

    print(f"\nelapsed {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
