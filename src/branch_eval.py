"""Artefact 1 — branch evaluation after the breadth gate failed.

B = 4.04 (signal) / 4.69 (returns) on the 18-instrument panel, 2011-2026.
Gate was B >= 8. Three branches were enumerated before the measurement:

  (a) widen the universe to raise breadth
  (b) keep the universe, proceed as underpowered-by-design methodology test
  (c) trade breadth for time

This script measures (a) and (c) so the branch choice rests on numbers.
No strategy returns are computed -- that would be peeking before pre-registration.
Only signals and return correlations are used, which are result-free inputs.

Note: the earlier run hardcoded a 2011 window, which silently truncated the
2007-start test. This version pulls from 2005 and subsets.
"""

import hashlib
import os
import time

import numpy as np
import pandas as pd

from breadth import TICKERS, OUTDIR, fetch, participation_ratio

EXTRA = ["EMB", "HYG", "VNQ", "DBA", "UUP"]  # all pre-2011, added for branch (a)
P1_2005 = 1104537600  # 2005-01-01
Z = 1.959964 + 0.8416212  # 5% two-sided, 80% power


def build():
    series = {}
    for t in TICKERS + EXTRA:
        try:
            s = fetch(t, p1=P1_2005)
            series[t] = s
            print(f"  {t:5s} {s.index[0].date()} -> {s.index[-1].date()}  n={len(s)}")
            time.sleep(0.7)
        except Exception as e:  # noqa: BLE001
            print(f"  SKIP {t}: {e}")

    df = pd.DataFrame(series).sort_index()
    path = os.path.join(OUTDIR, "breadth_snapshot_2005.csv")
    df.to_csv(path)
    with open(path, "rb") as fh:
        print(f"\nsnapshot {path}\nsha256  {hashlib.sha256(fh.read()).hexdigest()}")
    return df


def evaluate(name, df, start):
    wk = df.resample("W-FRI").last()
    wk = wk[wk.index >= start].dropna(how="any")
    if len(wk) < 60:
        return None
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    sig = (wk / wk.shift(52) - 1).dropna(how="any")
    B_ret, _ = participation_ratio(rets.corr())
    B_sig, _ = participation_ratio(sig.corr())
    B = min(B_ret, B_sig)
    T = len(wk) / 52.0
    return dict(name=name, n=wk.shape[1], start=wk.index[0].date(), weeks=len(wk), T=T,
                B_ret=B_ret, B_sig=B_sig, B=B, TB=T * B, mde=Z / np.sqrt(T * B))


def main():
    df = build()
    base = [c for c in TICKERS if c in df.columns]
    wide = [c for c in base + EXTRA if c in df.columns]

    rows = [
        evaluate("18 instr, 2011 start  (as planned)", df[base], "2011-01-01"),
        evaluate("18 instr, 2007 start  (branch c: +time, same breadth)", df[base], "2007-02-01"),
        evaluate("23 instr, 2011 start  (branch a: +breadth)", df[wide], "2011-01-01"),
        evaluate("23 instr, 2008 start  (branch a+c combined)", df[wide], "2008-01-01"),
    ]
    rows = [r for r in rows if r]

    print("\n"
          f"{'design':58s} {'n':>3s} {'start':>10s} {'wk':>5s} {'T':>6s} {'B':>5s} {'T*B':>6s} {'MDE':>6s}")
    for r in rows:
        print(f"{r['name']:58s} {r['n']:3d} {str(r['start']):>10s} {r['weeks']:5d} "
              f"{r['T']:6.1f} {r['B']:5.2f} {r['TB']:6.1f} {r['mde']:6.2f}")

    print("\nMDE = minimum detectable annualised Sharpe, 80% power, 5% two-sided.")
    print("Pre-decay diversified TSMOM Sharpe ~0.8-1.0; post-2010 decayed estimates ~0.2-0.5.")

    # How many instruments would branch (a) actually need?
    r18, r23 = rows[2], rows[2]
    d_breadth = rows[2]["B"] - rows[0]["B"]
    d_n = rows[2]["n"] - rows[0]["n"]
    if d_n > 0:
        per = d_breadth / d_n
        print(f"\nB gain per added diverse instrument: {per:+.3f}  "
              f"(from {d_n} additions: {rows[0]['B']:.2f} -> {rows[2]['B']:.2f})")
        if per > 0:
            print(f"instruments needed to reach B=8 at that rate: {(8 - rows[0]['B']) / per:.0f} more")


if __name__ == "__main__":
    main()
