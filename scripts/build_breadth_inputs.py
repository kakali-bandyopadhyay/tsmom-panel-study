"""Artefact 1 — regenerate `data/breadth_inputs.json` from the Yahoo breadth pull.

Why the derived file is committed and the pull is not
-----------------------------------------------------
The power simulation consumes exactly two objects: the correlation matrix of the weekly
returns and the vector of weekly standard deviations. The price snapshot behind them is
Yahoo data, and §12 of the pre-registration says no vendor data is committed. So the
snapshot stays out of the repository and these two derived objects go in, together with
the snapshot's SHA-256 — which is what lets a reader with their own copy of the pull
confirm that the committed inputs were derived from it and not adjusted afterwards.

Committing the derived objects also removes a worse failure mode: if the simulation
re-derived its inputs from a fresh pull, a re-run would silently use a different panel and
still be reported as a reproduction of §5.

Usage
-----
    python scripts/build_breadth_inputs.py path/to/breadth_snapshot_2005.csv

The input is the 23-column pull: the eighteen instruments plus the five branch-(a)
additions. `src/breadth.py::TICKERS` fixes which eighteen are read, in which order.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "data" / "breadth_inputs.json"

START = "2011-01-01"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python scripts/build_breadth_inputs.py path/to/breadth_snapshot_2005.csv",
              file=sys.stderr)
        return 2
    src = Path(argv[0])
    if not src.is_file():
        print(f"not a file: {src}", file=sys.stderr)
        return 2

    # Same ticker list and order as the simulation; one definition, in src/breadth.py.
    sys.path.insert(0, str(REPO / "src"))
    from breadth import TICKERS  # noqa: E402

    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    raw = pd.read_csv(src, index_col=0, parse_dates=True)
    missing = [c for c in TICKERS if c not in raw.columns]
    if missing:
        print(f"snapshot is missing {missing}", file=sys.stderr)
        return 2

    # The transformation is quoted in the output so the file is checkable without this
    # script: W-FRI last observation, window from 2011-01-01, complete cases only.
    wk = raw[TICKERS].resample("W-FRI").last()
    wk = wk[wk.index >= START].dropna(how="any")
    rets = wk.pct_change(fill_method=None).dropna(how="any")

    out = {
        "purpose": "design inputs for src/power_sim.py (section 5); not a backtest input",
        "source": ("Yahoo adjclose breadth pull - unfit for backtesting, confined to the "
                   "breadth and power calculations (PREREGISTRATION.md 4.4, data/SOURCES.md 1)"),
        "snapshot_file": src.name,
        "snapshot_sha256": digest,
        "columns_used": TICKERS,
        "n_instruments": len(TICKERS),
        "weekly_weeks": int(len(wk)),
        "weekly_observations": int(len(rets)),
        "window_start": str(wk.index[0].date()),
        "window_end": str(wk.index[-1].date()),
        "construction": ("W-FRI last observation of adjClose; window >= 2011-01-01; complete "
                         "cases; returns are pct_change of the resampled series; correlation "
                         "and standard deviation computed on those returns (ddof=1)"),
        "correlation": rets.corr().to_numpy().tolist(),
        "sigma_weekly": rets.std().to_numpy().tolist(),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"snapshot   {src}  ({len(raw.columns)} columns, {len(raw)} rows)")
    print(f"sha256     {digest}")
    print(f"weeks      {len(wk)}  returns {len(rets)}  "
          f"window {out['window_start']} -> {out['window_end']}")
    print(f"written    {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
