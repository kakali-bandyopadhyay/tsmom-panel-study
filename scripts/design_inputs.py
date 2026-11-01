"""Artefact 1 — recompute the design inputs on the frozen backtest snapshot.

B = 4.04 was computed on the breadth pull (Yahoo), which the pre-registration declares
unfit for backtesting and confines to the breadth calculation. That B is a design input,
not a result, and the pre-registered step is to **recompute it on the backtest snapshot as
a confirmation** rather than carry it forward unexamined.

The margin is wide: the breadth gate fires at B < 8 and B sits at 4.04. A different
provider's correlation matrix will not move it to 8, so the branch decision (b) is robust.
What could move is the MDE, because it is derived from the correlation structure — so this
script applies a pre-declared rule for when the power simulation must be rerun.

Pre-declared rule (fixed before the recomputation, not after):

    |B_new - 4.04| <= 0.40  -> carry MDE = 0.77 forward, record the recomputation
    |B_new - 4.04| >  0.40  -> rerun the power simulation before §1.1 is frozen

0.40 is roughly a 10% move in B. MDE scales as 1/sqrt(B) locally, so a 10% move in B is a
~5% move in MDE — 0.77 -> 0.73 or 0.81, which changes the number the claim actually
quotes ("we can exclude a live effect above ≈0.77 Sharpe"). Below that, the quoted bound
is unchanged and rerunning would be churn.

This script computes the design inputs only. It computes no strategy returns: that would
be peeking before the pre-registration is filed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SNAPSHOTS = REPO / "data" / "snapshots"

TICKERS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ",
    "TLT", "IEF", "TIP", "LQD", "BWX",
    "GLD", "SLV", "DBC", "USO",
    "FXE", "FXY", "IYR",
]
START = "2011-01-01"
LOOKBACK = 52

B_DESIGN = 4.04          # from the breadth pull; the design input being confirmed
B_GATE = 8.0             # pre-registered breadth gate
B_TOLERANCE = 0.40       # pre-declared rule above
MDE_DESIGN = 0.77


def participation_ratio(corr: pd.DataFrame) -> tuple[float, np.ndarray]:
    lam = np.sort(np.linalg.eigvalsh(corr.values))[::-1]
    lam = np.clip(lam, 0.0, None)
    return float(lam.sum() ** 2 / (lam ** 2).sum()), lam


def load_panel(snapshot: Path) -> pd.DataFrame:
    df = pd.read_csv(snapshot / "panel.csv", parse_dates=["date"])
    wide = df.pivot(index="date", columns="ticker", values="adjClose")
    cols = [c for c in TICKERS if c in wide.columns]
    wide = wide[cols].sort_index()
    wk = wide.resample("W-FRI").last()
    wk = wk[wk.index >= START]
    return wk.dropna(how="any")


def build_inputs(wk: pd.DataFrame) -> dict:
    rets = wk.pct_change(fill_method=None).dropna(how="any")
    sig = (wk / wk.shift(LOOKBACK) - 1).dropna(how="any")

    B_ret, lam_ret = participation_ratio(rets.corr())
    B_sig, lam_sig = participation_ratio(sig.corr())
    B = min(B_ret, B_sig)

    # persistence of a representative signal, used only for the analytic cross-check
    rho = np.nan_to_num(np.array([sig.iloc[:, 0].autocorr(lag=k) for k in range(1, LOOKBACK + 1)],
                                 dtype=float))
    blocks = len(wk) / max(1.0 + 2 * rho.sum(), 1.0)
    T = len(wk) / 52.0
    z80 = 1.959964 + 0.8416212

    return {
        "instruments": list(wk.columns),
        "n_instruments": int(wk.shape[1]),
        "weeks": int(len(wk)),
        "signal_obs": int(len(sig)),
        "window_start": str(wk.index[0].date()),
        "window_end": str(wk.index[-1].date()),
        "B_returns": round(B_ret, 4),
        "B_signal": round(B_sig, 4),
        "B": round(B, 4),
        "first_factor_share_returns": round(float(lam_ret[0] / lam_ret.sum()), 4),
        "first_factor_share_signal": round(float(lam_sig[0] / lam_sig.sum()), 4),
        "mean_abs_offdiag_returns": round(
            float(np.abs(rets.corr().values[np.triu_indices_from(rets.corr(), 1)]).mean()), 4),
        "persistence_factor": round(float(max(1.0 + 2 * rho.sum(), 1.0)), 2),
        "independent_blocks": round(float(blocks), 2),
        "analytic_mde_portfolio": round(z80 / np.sqrt(T), 3),
    }


def reconcile(inputs: dict) -> dict:
    delta = inputs["B"] - B_DESIGN
    gate = inputs["B"] >= B_GATE
    rerun = abs(delta) > B_TOLERANCE
    return {
        "B_design": B_DESIGN,
        "B_recomputed": inputs["B"],
        "delta": round(delta, 4),
        "tolerance": B_TOLERANCE,
        "gate_B_ge_8": bool(gate),
        "branch_b_holds": not gate,
        "power_sim_rerun_required": bool(rerun),
        "rule": ("|B_new - 4.04| <= 0.40 -> carry MDE 0.77 forward; "
                 "> 0.40 -> rerun the power simulation before §1.1 is frozen"),
        "mde_carried_forward": None if rerun else MDE_DESIGN,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        found = sorted(SNAPSHOTS.glob("*/panel.csv")) if SNAPSHOTS.exists() else []
        if not found:
            print(f"no frozen snapshot under {SNAPSHOTS}\n"
                  "run scripts/fetch_data.py first: the design inputs are confirmed on the\n"
                  "backtest snapshot, not on the breadth pull.", file=sys.stderr)
            return 2
        snapshot = found[-1].parent
    else:
        snapshot = Path(argv[0])

    wk = load_panel(snapshot)
    inputs = build_inputs(wk)

    panel_hash = hashlib.sha256((snapshot / "panel.csv").read_bytes()).hexdigest()
    out = {
        "snapshot_id": snapshot.name,
        "panel_sha256": panel_hash,
        "design_inputs": inputs,
        "reconciliation": reconcile(inputs),
    }
    path = snapshot / "design_inputs.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    r = out["reconciliation"]
    print(f"snapshot        {snapshot.name}")
    print(f"panel sha256    {panel_hash}")
    print(f"instruments     {inputs['n_instruments']}  weeks {inputs['weeks']}  "
          f"signal obs {inputs['signal_obs']}")
    print(f"window          {inputs['window_start']} -> {inputs['window_end']}")
    print(f"B (returns)     {inputs['B_returns']:.2f}   first factor "
          f"{inputs['first_factor_share_returns']:.1%}")
    print(f"B (signal)      {inputs['B_signal']:.2f}   first factor "
          f"{inputs['first_factor_share_signal']:.1%}")
    print(f"B used          {inputs['B']:.2f}   (design value {B_DESIGN:.2f}, "
          f"delta {r['delta']:+.2f})")
    print(f"breadth gate    B >= {B_GATE:.0f}: {'PASS' if r['gate_B_ge_8'] else 'FAIL'}")
    print(f"branch (b)      {'holds' if r['branch_b_holds'] else 'DOES NOT HOLD — revisit scope'}")
    print(f"power rerun     {'REQUIRED before §1.1 freezes' if r['power_sim_rerun_required'] else 'not required; MDE 0.77 carried forward'}")
    print(f"written         {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
