"""Standalone total-return audit for a frozen snapshot.

Runs against `data/raw/<stamp>/` and writes `data/audit.json`. Does not touch the
snapshot directory, which is immutable by rule.

Why this exists separately
--------------------------
`fetch_data.py` short-circuits on an existing snapshot ("verify hash and reuse"), so it
never re-audits a snapshot already on disk. This script re-runs the audit alone, which is
what a corrected audit needs.

The two defects this replaces
-----------------------------
1. The original removed split rows and then called pct_change(), so the row after a split
   computed its return against the row before the split. USO (1:8), EWJ (4:1) and BWX
   (2:1) therefore showed deviations equal to their split ratios.

2. The original formed the implied return as price_return * (1 + div/close_prev), which
   leaves a residual of roughly the dividend yield. The correct total return is
   (close + divCash) / close_prev * splitFactor - 1.

With both corrected, adjClose reproduces to ~1e-12 on all instruments.

Tolerance is 1e-9: floating-point noise, not a calibrated convenience.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SNAPSHOTS = REPO / "data" / "snapshots"
RAW = REPO / "data" / "raw"

TOL = 1e-9
FIELDS = ["close", "adjClose", "divCash", "splitFactor"]


def audit_one(path: Path) -> dict:
    df = pd.DataFrame(json.loads(path.read_text()))
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.set_index("date").sort_index()
    for c in FIELDS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["splitFactor"] = df["splitFactor"].fillna(1.0).replace(0.0, 1.0)
    df["divCash"] = df["divCash"].fillna(0.0)

    adj_r = df["adjClose"].pct_change(fill_method=None)
    gross = (df["close"] + df["divCash"]) / df["close"].shift(1) * df["splitFactor"] - 1.0
    dev = (adj_r - gross).abs().dropna()

    return {
        "ticker": path.stem,
        "rows": int(len(df)),
        "first": str(df.index[0].date()),
        "last": str(df.index[-1].date()),
        "n_dividend_days": int((df["divCash"] > 0).sum()),
        "n_split_days": int((df["splitFactor"] != 1.0).sum()),
        "max_abs_dev": float(dev.max()) if len(dev) else 0.0,
        "p999_abs_dev": float(dev.quantile(0.999)) if len(dev) else 0.0,
    }


def main() -> int:
    if not SNAPSHOTS.exists():
        print("no snapshots directory", file=sys.stderr)
        return 1
    snap = sorted(SNAPSHOTS.iterdir())[-1]
    stamp = snap.name.split("-")[0]
    raw = RAW / stamp
    if not raw.exists():
        print(f"no raw directory for stamp {stamp} at {raw}", file=sys.stderr)
        return 1

    files = sorted(raw.glob("*.json"))
    print(f"snapshot {snap.name}")
    print(f"raw      {raw}  ({len(files)} instruments)\n")
    print(f"{'ticker':6}{'rows':>6}{'divs':>6}{'splits':>7}{'max_abs_dev':>14}{'p99.9':>12}")

    audits = []
    for f in files:
        a = audit_one(f)
        audits.append(a)
        flag = "" if a["max_abs_dev"] <= TOL else "   <-- FAIL"
        print(f"{a['ticker']:6}{a['rows']:6d}{a['n_dividend_days']:6d}"
              f"{a['n_split_days']:7d}{a['max_abs_dev']:14.2e}{a['p999_abs_dev']:12.2e}{flag}")

    bad = [a for a in audits if a["max_abs_dev"] > TOL]
    worst = max(a["max_abs_dev"] for a in audits)

    out = {
        "snapshot": snap.name,
        "raw_dir": str(raw),
        "audit_version": 2,
        "tolerance": TOL,
        "method": "(close + divCash) / close_prev * splitFactor - 1 vs adjClose pct_change",
        "worst_max_abs_dev": worst,
        "passed": not bad,
        "instruments": audits,
    }
    dest = REPO / "data" / "audit.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\nworst deviation {worst:.2e}  (tolerance {TOL:.0e})")
    if bad:
        print(f"AUDIT FAILED on {len(bad)}: {', '.join(b['ticker'] for b in bad)}", file=sys.stderr)
        print("Do not freeze a pre-registration on this snapshot.", file=sys.stderr)
        return 1
    print(f"audit passed: adjClose reconciles with close + divCash + splits on all {len(audits)} instruments")
    print(f"written {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
