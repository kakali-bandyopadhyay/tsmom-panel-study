"""Artefact 1 — residual breadth for the time-FE panel specification.

B = 4.04 is the participation ratio of the raw weekly correlation matrix. That
figure governs the portfolio-Sharpe test. It does NOT govern the panel test,
because a panel with time fixed effects absorbs any common factor: identification
comes from within-period cross-sectional deviation, and the common component is
projected out before the slope is estimated.

So the panel's effective breadth is the participation ratio of the *residual*
correlation matrix after cross-sectional (week) demeaning, not B.

This matters because the two are not close, and quoting B in the panel MDE would
understate the panel's power -- while omitting time FE would collapse it back to
the portfolio figure. Both facts belong in the write-up.
"""

import os

import numpy as np
import pandas as pd

from breadth import OUTDIR, TICKERS, participation_ratio

SNAP = os.path.join(OUTDIR, "breadth_snapshot_2005.csv")


def panel(df, start):
    wk = df.resample("W-FRI").last()
    wk = wk[wk.index >= start].dropna(how="any")
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    return wk, rets


def report(name, rets, blocks):
    raw = rets.corr()
    B_raw, lam_raw = participation_ratio(raw)

    # remove the common component the way time FE would
    resid = rets.sub(rets.mean(axis=1), axis=0)
    B_res, lam_res = participation_ratio(resid.corr())

    print(f"\n{name}")
    print(f"  raw B (portfolio test)        : {B_raw:.2f}   first factor {lam_raw[0]/lam_raw.sum():.1%}")
    print(f"  residual B (panel with time FE): {B_res:.2f}   first factor {lam_res[0]/lam_res.sum():.1%}")
    print(f"  blocks (52wk persistence)      : {blocks:.1f}")
    print(f"  MDE portfolio (0.70 ref)       : {2.8/np.sqrt(len(rets)/52):.2f}")
    print(f"  MDE panel, time FE, residual B : {2.8/np.sqrt(B_res*blocks):.2f}")
    print(f"  MDE panel quoting raw B        : {2.8/np.sqrt(B_raw*blocks):.2f}   <- understates power")


def main():
    df = pd.read_csv(SNAP, index_col=0, parse_dates=True)
    cols = [c for c in TICKERS if c in df.columns]

    for start, label in (("2011-01-01", "18 instruments, 2011-2026"), ("2007-02-01", "18 instruments, 2007-2026")):
        wk, rets = panel(df[cols], start)
        sig = (wk / wk.shift(52) - 1).dropna(how="any")
        rho = np.nan_to_num(np.array([sig.iloc[:, 0].autocorr(lag=k) for k in range(1, 53)], dtype=float))
        blocks = len(wk) / (1 + 2 * rho.sum())
        report(label, rets, blocks)

    # what each asset class contributes to the residual structure
    _, rets = panel(df[cols], "2011-01-01")
    resid = rets.sub(rets.mean(axis=1), axis=0)
    print("\nresidual correlation, mean |off-diagonal| by asset class")
    groups = {
        "equities": ["SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ"],
        "bonds": ["TLT", "IEF", "TIP", "LQD", "BWX"],
        "commodities": ["GLD", "SLV", "DBC", "USO"],
        "fx/alt": ["FXE", "FXY", "IYR"],
    }
    for g, members in groups.items():
        members = [m for m in members if m in resid.columns]
        sub = resid[members].corr().values
        off = sub[np.triu_indices_from(sub, 1)]
        print(f"  {g:12s} mean {off.mean():+.2f}  max {off.max():+.2f}  n={len(members)}")


if __name__ == "__main__":
    main()
