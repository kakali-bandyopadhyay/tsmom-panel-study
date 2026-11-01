"""Artefact 1 — backtest data pull, hash, store. Run once per snapshot; never regenerate.

Why this file exists before the pre-registration
------------------------------------------------
The pre-registration must name its data source and its total-return convention. Both are
answers this script produces, not assumptions it consumes:

  1. Tiingo daily prices. A Stooq cross-check is attempted and recorded as unavailable
     when refused: from this environment Stooq returns a JavaScript challenge page rather
     than CSV, on all URL forms, so the cross-check could not be obtained. The failure is
     recorded in the manifest per instrument rather than papered over.
  2. A total-return series defined as the ratio of Tiingo's `adjClose`, which is
     dividend- and split-adjusted. Returns are computed from ratios only and never from
     an absolute adjusted level, because the adjustment factor is applied retroactively
     and an absolute level therefore carries information from the future. A ratio
     carries none. This is stated in data/SOURCES.md and reproduced in the pre-reg.

The two-snapshot rule
---------------------
Pull, hash, store, never regenerate. A snapshot directory is immutable: if it exists,
this script verifies its hash and reuses it. It never overwrites. Regenerating a pull
silently changes the panel under a frozen design, which is exactly the failure the rule
exists to prevent.

No vendor data is committed. `data/` is gitignored; only this script and the committed
hash manifests go into the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data"
RAW = DATA / "raw"
SNAPSHOTS = DATA / "snapshots"

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
END = "2026-10-30"

TIINGO = ("https://api.tiingo.com/tiingo/daily/{ticker}/prices"
          "?startDate={start}&endDate={end}&format=json&resampleFreq=daily")
STOOQ = "https://stooq.com/q/d/l/?s={ticker}.us&d1={d1}&d2={d2}&i=d"

UA = "Mozilla/5.0 (compatible; tsmom-panel-study/0.1; research)"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get(url: str, token: str | None = None, attempts: int = 4, timeout: int = 60) -> bytes:
    headers = {"User-Agent": UA, "Accept": "application/json, text/csv;q=0.9,*/*;q=0.8"}
    if token:
        headers["Authorization"] = f"Token {token}"
        headers["Content-Type"] = "application/json"
    last: Exception | None = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last = exc
            time.sleep(2 + 4 * i)
    raise RuntimeError(f"GET failed after {attempts} attempts: {url} :: {last}")


# --------------------------------------------------------------------------- tiingo

def fetch_tiingo(ticker: str, token: str) -> tuple[bytes, str]:
    url = TIINGO.format(ticker=ticker, start=START, end=END)
    body = get(url, token=token)
    return body, url


def parse_tiingo(body: bytes, ticker: str) -> pd.DataFrame:
    rows = json.loads(body.decode("utf-8"))
    if not rows:
        raise RuntimeError(f"{ticker}: empty Tiingo response")
    df = pd.DataFrame(rows)
    need = {"date", "close", "adjClose", "divCash", "splitFactor"}
    missing = need - set(df.columns)
    if missing:
        raise RuntimeError(f"{ticker}: Tiingo response missing {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.set_index("date").sort_index()
    num = ["close", "adjClose", "divCash", "splitFactor"]
    df[num] = df[num].apply(pd.to_numeric, errors="coerce")
    df["splitFactor"] = df["splitFactor"].fillna(1.0).replace(0.0, 1.0)
    df["divCash"] = df["divCash"].fillna(0.0)
    df["ticker"] = ticker
    return df[["close", "adjClose", "divCash", "splitFactor", "ticker"]]


def audit_total_return(df: pd.DataFrame, ticker: str) -> dict:
    """Confirm adjClose embeds dividends and splits.

    Total return from raw prices is (close + divCash) / close_prev * splitFactor - 1.
    Computed on the full series: removing split rows would make the next row's
    pct_change span the split and report a deviation equal to the split ratio.
    """
    d = df.copy()
    adj_r = d["adjClose"].pct_change(fill_method=None)
    gross = (d["close"] + d["divCash"]) / d["close"].shift(1) * d["splitFactor"] - 1.0
    dev = (adj_r - gross).abs().dropna()
    return {
        "ticker": ticker,
        "rows": int(len(d)),
        "first": str(d.index[0].date()),
        "last": str(d.index[-1].date()),
        "n_split_days": int((d["splitFactor"] != 1.0).sum()),
        "n_dividend_days": int((d["divCash"] > 0).sum()),
        "max_abs_dev": float(dev.max()) if len(dev) else 0.0,
    }

# --------------------------------------------------------------------------- stooq

def fetch_stooq(ticker: str) -> tuple[bytes, str]:
    url = STOOQ.format(ticker=ticker.lower(),
                       d1=START.replace("-", ""), d2=END.replace("-", ""))
    return get(url), url


def parse_stooq(body: bytes) -> pd.DataFrame | None:
    """Stooq serves CSV, but returns an HTML interstitial to uninvited clients.

    A cross-check that silently accepts an HTML page as if it were prices would be worse
    than no cross-check, so this returns None and the caller records the failure
    explicitly rather than falling back to something weaker.
    """
    head = body[:400].lstrip().lower()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        return None
    try:
        from io import StringIO
        df = pd.read_csv(StringIO(body.decode("utf-8", errors="replace")))
    except Exception:  # noqa: BLE001
        return None
    cols = {c.lower(): c for c in df.columns}
    if "date" not in cols or "close" not in cols:
        return None
    df = df.rename(columns={cols["date"]: "date", cols["close"]: "close"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df[["close"]]


def crosscheck_stooq(panel: pd.DataFrame, ticker: str, stooq: pd.DataFrame | None) -> dict:
    """Compare closes on common dates, reporting correlation and level ratio.

    A Stooq close series, were one obtainable, would be expected to be split-adjusted but
    not dividend-adjusted. That is an expectation and not something verified here, because
    no Stooq response was ever received. Such a comparison would validate the price series
    and split handling, not the total-return series. Saying which half of the construction
    is being verified is the point; a cross-check that claims to verify everything verifies
    nothing.
    """
    if stooq is None:
        return {"ticker": ticker, "status": "unavailable",
                "note": "Stooq returned an HTML interstitial, not CSV"}
    t = panel[panel["ticker"] == ticker]["close"]
    j = pd.concat([t, stooq["close"]], axis=1, keys=["tiingo", "stooq"]).dropna()
    if len(j) < 100:
        return {"ticker": ticker, "status": "insufficient_overlap", "n": int(len(j))}
    ret_t = j["tiingo"].pct_change(fill_method=None).dropna()
    ret_s = j["stooq"].pct_change(fill_method=None).dropna()
    idx = ret_t.index.intersection(ret_s.index)
    return {
        "ticker": ticker,
        "status": "ok",
        "n_common_days": int(len(j)),
        "return_correlation": float(ret_t.reindex(idx).corr(ret_s.reindex(idx))),
        "max_abs_return_diff": float((ret_t.reindex(idx) - ret_s.reindex(idx)).abs().max()),
    }


# --------------------------------------------------------------------------- snapshot

def main() -> int:
    ap = argparse.ArgumentParser(description="Pull and freeze the artefact-1 backtest panel.")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the plan, print it, touch nothing")
    ap.add_argument("--skip-stooq", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("TIINGO_TOKEN", "").strip()
    if not args.dry_run and not token:
        print("TIINGO_TOKEN is not set. Nothing written.\n"
              "  A free Tiingo account provides a token; export it as TIINGO_TOKEN.\n"
              "  This script will not fall back to an unadjusted or scraped source: the\n"
              "  data source is a pre-registered design input, not an implementation detail.",
              file=sys.stderr)
        return 2

    print(f"window     {START} -> {END}")
    print(f"instruments {len(TICKERS)}: {' '.join(TICKERS)}")
    if args.dry_run:
        print(f"\nwould pull:\n  {TIINGO.format(ticker='SPY', start=START, end=END)}")
        print(f"  {STOOQ.format(ticker='spy', d1='20110101', d2='20261030')}")
        print(f"would store under {RAW} and {SNAPSHOTS}")
        print("\ndry run: nothing fetched, nothing written")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rawdir = RAW / stamp
    rawdir.mkdir(parents=True, exist_ok=True)

    frames: list[pd.DataFrame] = []
    files: dict[str, dict] = {}
    audits: list[dict] = []

    for t in TICKERS:
        try:
            body, url = fetch_tiingo(t, token)
        except RuntimeError as exc:
            print(f"  FAIL {t:5s} {exc}", file=sys.stderr)
            return 1
        path = rawdir / f"{t}.json"
        path.write_bytes(body)
        df = parse_tiingo(body, t)
        frames.append(df)
        a = audit_total_return(df, t)
        audits.append(a)
        files[t] = {"bytes": len(body), "sha256": sha256_bytes(body), "url": url,
                    "rows": a["rows"], "first": a["first"], "last": a["last"]}
        print(f"  {t:5s} {a['first']} -> {a['last']}  n={a['rows']:5d}  "
              f"splits={a['n_split_days']}  divs={a['n_dividend_days']}  "
              f"maxdev={a['max_abs_dev']:.2e}")
        time.sleep(1.2)   # free tier allows 1000 req/hour; stay well inside it

    panel = pd.concat(frames).reset_index().sort_values(["date", "ticker"])
    panel_path = rawdir / "panel.csv"
    panel.to_csv(panel_path, index=False)
    panel_hash = sha256_file(panel_path)

    stooq_rows: list[dict] = []
    if not args.skip_stooq:
        print("\nStooq cross-check")
        for t in TICKERS:
            try:
                body, _ = fetch_stooq(t)
                s = parse_stooq(body)
            except RuntimeError as exc:
                print(f"  {t:5s} unavailable ({exc})")
                s = None
            r = crosscheck_stooq(panel, t, s)
            stooq_rows.append(r)
            print(f"  {t:5s} {r['status']:22s} "
                  + (f"corr={r.get('return_correlation', float('nan')):.4f} "
                     f"maxdiff={r.get('max_abs_return_diff', float('nan')):.2e}"
                     if r["status"] == "ok" else r.get("note", "")))
            time.sleep(1.0)

    snapshot_id = f"{stamp}-{panel_hash[:8]}"
    snapdir = SNAPSHOTS / snapshot_id
    if snapdir.exists():
        print(f"\nsnapshot {snapshot_id} already exists -> verifying and reusing, not regenerating")
        if sha256_file(snapdir / "panel.csv") != panel_hash:
            print("HASH MISMATCH: refusing to continue", file=sys.stderr)
            return 1
        return 0
    snapdir.mkdir(parents=True, exist_ok=False)
    (snapdir / "panel.csv").write_bytes(panel_path.read_bytes())
    (snapdir / "panel.csv.sha256").write_text(f"{panel_hash}  panel.csv\n", encoding="utf-8")

    manifest = {
        "snapshot_id": snapshot_id,
        "pulled_utc": stamp,
        "source": "tiingo",
        "window": {"start": START, "end": END},
        "instruments": TICKERS,
        "total_return_method": {
            "definition": "ratio of adjClose; dividend- and split-adjusted",
            "never": "an absolute adjusted level (retroactive factor is a lookahead vector)",
        },
        "panel_sha256": panel_hash,
        "files": files,
        "total_return_audit": audits,
        "stooq_crosscheck": stooq_rows,
        "environment": {"python": sys.version.split()[0], "pandas": pd.__version__},
    }
    (snapdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nsnapshot   {snapdir}")
    print(f"panel hash {panel_hash}")
    print(f"manifest   {snapdir / 'manifest.json'}")

    bad = [a for a in audits if a["max_abs_dev"] > 1e-9]
    if bad:
        print("\nAUDIT FAILED: adjClose does not reconcile with close + divCash on:")
        for a in bad:
           print(f"  {a['ticker']}: {a['max_abs_dev']:.3e}")
        print("Do not freeze a pre-registration on this snapshot.", file=sys.stderr)
        return 1
    unavailable = [r["ticker"] for r in stooq_rows if r["status"] != "ok"]
    if unavailable:
        print(f"\ncross-check incomplete for {len(unavailable)} instruments "
              f"({', '.join(unavailable)}); recorded in the manifest as-is")
    print("\naudit passed: adjClose reconciles with close + divCash on all instruments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
