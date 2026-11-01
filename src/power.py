"""Artefact 1 — corrected power calculation.

Correction to the earlier figure. The earlier arithmetic used
    SE(Sharpe) = sqrt(1 / (T_years * B))
which mixes units. B breadth does not multiply the number of independent
observations of a *portfolio* Sharpe: breadth lowers portfolio volatility, and
the Sharpe is already expressed in units of that volatility, so the sampling
error of a portfolio Sharpe is ~1/sqrt(T_years) regardless of B.

Two distinct tests, two distinct MDEs:

  portfolio Sharpe   : SE ~ 1/sqrt(T_years)          -> breadth buys level, not precision
  panel coefficient  : SE ~ 1/sqrt(B_eff * T_blocks) -> breadth does buy precision,
                       where T_blocks is the number of effectively independent time
                       blocks after the 52-week lookback's persistence is absorbed

For a 52-week overlapping signal on weekly data, the persistence factor
1 + 2*sum(rho_k) is roughly 52, so T_blocks ~ T_weeks/52 ~ T_years. That is why the
panel figure lands near the number quoted earlier -- but it is a per-asset effect
size, not a portfolio Sharpe, and the two are not interchangeable.
"""

import os

import numpy as np
import pandas as pd

from breadth import TICKERS, OUTDIR, participation_ratio

Z = 1.959964 + 0.8416212  # 80% power, 5% two-sided
SNAP = os.path.join(OUTDIR, "breadth_snapshot_2005.csv")

DESIGNS = {
    "18 instr, 2011 start (planned)": "2011-01-01",
    "18 instr, 2007 start (branch c)": "2007-02-01",
    "8 instr, 2004 start (long history)": "2004-01-01",
    "12 instr, 2004 start (long history)": "2004-01-01",
}

LONG8 = ["SPY", "EFA", "EEM", "EWJ", "TLT", "IEF", "GLD", "IYR"]
LONG12 = LONG8 + ["QQQ", "IWM", "TIP", "LQD"]


def persistence_blocks(series):
    """Approximate independent blocks from the signal's own autocorrelation."""
    sig = series.dropna()
    if len(sig) < 80:
        return None
    rho = [sig.autocorr(lag=k) for k in range(1, 53)]
    rho = np.nan_to_num(np.array(rho, dtype=float))
    factor = 1 + 2 * rho.sum()
    return max(factor, 1.0)


def evaluate(df, start):
    wk = df.resample("W-FRI").last()
    wk = wk[wk.index >= start].dropna(how="any")
    if len(wk) < 100:
        return None
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    sig = (wk / wk.shift(52) - 1).dropna(how="any")
    B_ret, _ = participation_ratio(rets.corr())
    B_sig, _ = participation_ratio(sig.corr())
    B = min(B_ret, B_sig)

    T = len(wk) / 52.0
    # persistence of a representative signal, averaged across instruments
    factors = [persistence_blocks(sig[c]) for c in sig.columns]
    factors = [f for f in factors if f]
    pf = float(np.mean(factors)) if factors else 1.0
    blocks = len(wk) / pf

    mde_port = Z / np.sqrt(T)
    mde_panel = Z / np.sqrt(B * blocks)
    return dict(n=wk.shape[1], start=wk.index[0].date(), weeks=len(wk), T=T, B=B,
                persist=pf, blocks=blocks, mde_port=mde_port, mde_panel=mde_panel)


def main():
    df = pd.read_csv(SNAP, index_col=0, parse_dates=True)
    print(f"{'design':36s} {'n':>3s} {'start':>10s} {'weeks':>5s} {'T':>5s} {'B':>5s} "
          f"{'persist':>7s} {'blocks':>6s} {'MDE_pf':>7s} {'MDE_pnl':>7s}")
    for name, start in DESIGNS.items():
        if name.startswith("8 "):
            cols = [c for c in LONG8 if c in df.columns]
        elif name.startswith("12 "):
            cols = [c for c in LONG12 if c in df.columns]
        else:
            cols = [c for c in TICKERS if c in df.columns]
        r = evaluate(df[cols], start)
        if not r:
            print(f"{name:36s} insufficient data for {cols}")
            continue
        print(f"{name:36s} {r['n']:3d} {str(r['start']):>10s} {r['weeks']:5d} {r['T']:5.1f} "
              f"{r['B']:5.2f} {r['persist']:7.1f} {r['blocks']:6.1f} {r['mde_port']:7.2f} {r['mde_panel']:7.2f}")

    print("\nMDE_pf  = portfolio-Sharpe test, annualised units, 80% power")
    print("MDE_pnl = panel coefficient expressed as a per-asset annualised edge")
    print("Reference points: diversified portfolio TSMOM Sharpe pre-decay ~0.8-1.0,")
    print("post-2010 decayed estimates ~0.2-0.5; per-asset edge is naturally lower.")


if __name__ == "__main__":
    main()
