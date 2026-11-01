"""Artefact 1 — effective breadth (B) calculation, pre-backtest.

Question: how many independent bets does an 18-instrument cross-asset ETF panel
actually contain, and does the design clear its own B >= 8 gate?

Method: participation ratio of the eigenvalues of the weekly correlation matrix,
computed twice -- once on returns, once on the momentum signal -- because
positions co-move more than returns do in trending markets, which makes the
return-based figure an upper bound on breadth for a momentum test.

Provenance: adjusted closes from Yahoo (cheap source, breadth only -- NOT the
backtest source). Snapshot stored to CSV with a recorded hash and pull date.
"""

import hashlib
import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd

TICKERS = [
    # equities
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ",
    # bonds
    "TLT", "IEF", "TIP", "LQD", "BWX",
    # commodities
    "GLD", "SLV", "DBC", "USO",
    # fx / alternatives
    "FXE", "FXY", "IYR",
]

START = "2011-01-01"
OUTDIR = "artefact1"
SNAPSHOT = os.path.join(OUTDIR, "breadth_snapshot.csv")

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"


def fetch(ticker, p1=1293840000, p2=1793577600, attempts=3):
    url = BASE.format(t=ticker, p1=p1, p2=p2)
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode())
            res = payload["chart"]["result"][0]
            ts = res["timestamp"]
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            s = pd.Series(adj, index=pd.to_datetime(ts, unit="s").normalize(), name=ticker)
            return s.dropna()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 3 * i)
    raise RuntimeError(f"{ticker}: {last}")


def participation_ratio(corr):
    """B = (sum lambda)^2 / sum lambda^2, on the correlation matrix eigenvalues."""
    lam = np.linalg.eigvalsh(corr.values)
    lam = np.clip(lam, 0, None)
    return float((lam.sum() ** 2) / (lam ** 2).sum()), np.sort(lam)[::-1]


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    series = {}
    for t in TICKERS:
        s = fetch(t)
        series[t] = s
        print(f"  {t:5s} {s.index[0].date()} -> {s.index[-1].date()}  n={len(s)}")
        time.sleep(0.7)

    daily = pd.DataFrame(series).sort_index()
    daily.index.name = "date"
    daily.to_csv(SNAPSHOT)
    with open(SNAPSHOT, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    # Weekly, Friday close
    wk = daily.resample("W-FRI").last()
    wk = wk[wk.index >= START].dropna(how="any")
    rets = wk.pct_change(fill_method=None).dropna(how="any")

    # Momentum signal: 52-week trailing return, same convention
    sig = (wk / wk.shift(52) - 1).dropna(how="any")

    print(f"\nsnapshot      : {SNAPSHOT}")
    print(f"sha256        : {digest}")
    print(f"pull date     : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"weekly obs    : {len(wk)}   (signal obs: {len(sig)})")
    print(f"window        : {wk.index[0].date()} -> {wk.index[-1].date()}")

    for label, frame in (("returns", rets), ("momentum signal", sig)):
        corr = frame.corr()
        B, lam = participation_ratio(corr)
        share1 = lam[0] / lam.sum()
        print(f"\n--- {label} ---")
        print(f"B (participation ratio) : {B:.2f}")
        print(f"first factor share      : {share1:.1%}")
        print(f"top 5 eigenvalues       : {np.round(lam[:5], 2)}")
        print(f"mean |off-diag corr|    : {np.abs(corr.values[np.triu_indices_from(corr, 1)]).mean():.2f}")

    # The number that goes into the power paragraph: lower of the two
    B_ret, _ = participation_ratio(rets.corr())
    B_sig, _ = participation_ratio(sig.corr())
    B_use = min(B_ret, B_sig)
    print(f"\nB used in power calc (lower of two) : {B_use:.2f}")
    print(f"gate B >= 8 : {'PASS' if B_use >= 8 else 'FAIL -> branch decision required'}")

    rets.to_csv(os.path.join(OUTDIR, "weekly_returns_breadth.csv"))


if __name__ == "__main__":
    main()
