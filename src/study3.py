"""Artefact 1 — size-corrected power, bracketed MDE, and the asset-class substitute.

Three things this does, all requested as fixes to the previous run:

1. Calibrates critical values against the simulated null so empirical size is 5%.
   The time-FE specification rejects at 7.8% against nominal 5%, and an anti-
   conservative test cannot support an exclusion bound -- the bound is the claim.
   Both nominal and size-corrected rejection rates are reported.

2. Adds plants at larger effects so the 80% crossing is bracketed rather than
   extrapolated past the largest planted effect.

3. Measures the asset-class-dummy specification as a partial substitute for the
   instrument FE that had to be dropped: class dummies control coarse heterogeneity
   without touching the within-instrument mean that caused the contamination.
"""

import numpy as np

from power_sim import CRIT, LOOKBACK, REPS, SEED, load_panel, pairs, regression_t, simulate

CLASSES = {
    "equities": ["SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ"],
    "bonds": ["TLT", "IEF", "TIP", "LQD", "BWX"],
    "commodities": ["GLD", "SLV", "DBC", "USO"],
    "fx_alt": ["FXE", "FXY", "IYR"],
}
TARGETS = [0.3, 0.5, 0.7, 0.9]


def demean_time_class(x, cls, iters=60):
    """Alternating projections: time FE and asset-class FE."""
    x = x.copy()
    for _ in range(iters):
        x -= x.mean(axis=1, keepdims=True)
        for g in np.unique(cls):
            m = cls == g
            x[:, m] -= x[:, m].mean(axis=(0, 1), keepdims=True)
    return x


def regression_t_class(z, y, cls):
    zd = demean_time_class(z, cls)
    yd = demean_time_class(y, cls)
    return _tstat(zd, yd)


def _tstat(zd, yd):
    from power_sim import HAC_LAG
    Szz = (zd * zd).sum(axis=(0, 1))
    beta = (zd * yd).sum(axis=(0, 1)) / Szz
    u = yd - zd * beta[None, None, :]
    g = (zd * u).sum(axis=1)
    s = (g * g).sum(axis=0)
    for l in range(1, HAC_LAG + 1):
        w = 1.0 - l / (HAC_LAG + 1.0)
        s = s + 2.0 * w * (g[l:] * g[:-l]).sum(axis=0)
    return beta / np.sqrt(np.maximum(s / (Szz ** 2), 1e-30))


def strat_sr(z, y):
    sr = (z * y).mean(axis=1)
    return np.sqrt(52) * sr.mean(axis=0) / sr.std(axis=0, ddof=1)


def main():
    rng = np.random.default_rng(SEED)
    corr, sigma = load_panel()
    L = np.linalg.cholesky(corr)
    names = list(CLASSES)
    cls = np.array([names.index(k) for k, v in CLASSES.items() for _ in v])

    # ---------- null: critical values ----------
    r0 = simulate(0.0, L, sigma, REPS, rng)
    z0, y0 = pairs(r0, sigma)
    t_time = regression_t(z0, y0, "time")[0]
    t_both = regression_t(z0, y0, "both")[0]
    t_cls = regression_t_class(z0, y0, cls)

    c_time = float(np.quantile(np.abs(t_time), 0.95))
    c_both = float(np.quantile(np.abs(t_both), 0.95))
    c_cls = float(np.quantile(np.abs(t_cls), 0.95))

    print("NULL, empirical size against nominal 5%")
    print(f"{'specification':22s} {'size@1.96':>10s} {'95th pct |t|':>13s} {'mean t':>8s} {'sd t':>7s}")
    for nm, t, c in (("time FE", t_time, c_time),
                     ("instrument+time", t_both, c_both),
                     ("time + class", t_cls, c_cls)):
        print(f"{nm:22s} {np.mean(np.abs(t) > CRIT):10.3f} {c:13.3f} {t.mean():8.2f} {t.std():7.2f}")

    sr_series = (z0 * y0).mean(axis=1)
    sig_w = float(sr_series.std(axis=0, ddof=1).mean())

    # ---------- power with calibrated critical values ----------
    print(f"\nPOWER, time FE, critical value calibrated to 5% empirical size (c = {c_time:.3f})")
    print(f"{'target':>7s} {'realised Sharpe':>16s} {'rej@nominal':>12s} {'rej@calibrated':>15s}")
    rows = []
    null_pt = (0.0, float(np.mean(np.abs(t_time) > c_time)))
    for S in TARGETS:
        theta = S * sig_w / (np.sqrt(52) * sigma.mean())
        rr = simulate(theta, L, sigma, REPS, rng)
        z, y = pairs(rr, sigma)
        t = regression_t(z, y, "time")[0]
        real = float(strat_sr(z, y).mean())
        r_nom = float(np.mean(np.abs(t) > CRIT))
        r_cal = float(np.mean(np.abs(t) > c_time))
        rows.append((real, r_nom, r_cal))
        print(f"{S:7.2f} {real:16.3f} {r_nom:12.3f} {r_cal:15.3f}")

    pts = sorted([(r[0], r[2]) for r in rows] + [null_pt])
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    if ys.min() < 0.8 < ys.max():
        mde = float(np.interp(0.8, ys, xs))
        print(f"\nMDE at 80% power, calibrated: Sharpe {mde:.2f}   "
              f"(bracketed: {xs[np.searchsorted(ys,0.8)-1]:.2f}-{xs[np.searchsorted(ys,0.8)]:.2f})")
    else:
        print(f"\n80% still not bracketed; rejection range {ys.min():.2f}-{ys.max():.2f}")


if __name__ == "__main__":
    main()
