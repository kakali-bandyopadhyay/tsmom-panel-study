"""Artefact 1 — evidence for the sqrt(N/T) scaling of the instrument-FE contamination.

The claim is that instrument fixed effects contaminate the estimate because the
signal is constructed from the dependent variable's own history: instrument-demeaning
subtracts a scaled copy of the mean return from both regressor and outcome. If that
mechanism is right, the induced bias in t units should scale as sqrt(N/T) -- growing
with breadth, shrinking with sample length.

This varies N and T independently under the null and checks whether mean t divided by
sqrt(N/T) is roughly constant across the grid. If it is, the mechanism is supported;
if not, the claim needs restating.

Composition is a confound when subsetting instruments, so subsets are drawn at random
rather than taken as the first N columns, and averaged over draws.
"""

import os

import numpy as np

from power_sim import LOOKBACK, SEED, load_panel, regression_t

N_GRID = [6, 12, 18]
T_GRID = [260, 520, 826]
DRAWS = 5
REPS = 100


def simulate(theta, L, sigma, reps, rng, T_WEEKS):
    T = LOOKBACK + T_WEEKS
    N = L.shape[0]
    Z = rng.standard_normal((T, N, reps))
    e = np.einsum("ij,tjr->tir", L, Z, optimize=True) * sigma[None, :, None]
    r = np.empty((T, N, reps))
    r[:LOOKBACK] = e[:LOOKBACK]
    scale = sigma * np.sqrt(LOOKBACK)
    for t in range(LOOKBACK, T):
        z = r[t - LOOKBACK:t].sum(axis=0) / scale[:, None]
        r[t] = theta * sigma[:, None] * z + e[t]
    return r[LOOKBACK:]


def pairs(r, sigma):
    T = r.shape[0]
    cs = np.cumsum(r, axis=0)
    scale = sigma[:, None] * np.sqrt(LOOKBACK)
    idx = np.arange(LOOKBACK + 1, T)
    return (cs[idx - 1] - cs[idx - LOOKBACK - 1]) / scale[None, :, :], r[idx]


def main():
    rng = np.random.default_rng(SEED)
    corr, sigma = load_panel()
    N_ALL = corr.shape[0]

    print(f"{'N':>3s} {'T':>5s} {'mean t':>8s} {'sd t':>7s} {'sqrt(N/T)':>10s} {'mean t / sqrt(N/T)':>20s}")
    rows = []
    for N in N_GRID:
        for T in T_GRID:
            ts = []
            for _ in range(DRAWS):
                idx = np.sort(rng.choice(N_ALL, size=N, replace=False))
                sub = corr[np.ix_(idx, idx)]
                Ls = np.linalg.cholesky(sub)
                rr = simulate(0.0, Ls, sigma[idx], REPS, rng, T)
                z, y = pairs(rr, sigma[idx])
                t = regression_t(z, y, "instrument")[0]
                ts.append(t)
            t = np.concatenate(ts)
            s = np.sqrt(N / T)
            rows.append((N, T, t.mean(), t.std(), s, t.mean() / s))
            print(f"{N:3d} {T:5d} {t.mean():8.3f} {t.std():7.2f} {s:10.4f} {t.mean()/s:20.3f}")

    vals = np.array([r[5] for r in rows])
    print(f"\nmean t / sqrt(N/T): mean {vals.mean():.3f}  sd {vals.std():.3f}  "
          f"range {vals.min():.3f} to {vals.max():.3f}")
    print("A near-constant ratio supports the sqrt(N/T) claim; a strong trend across the")
    print("grid would mean the bias scales with something else.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 4))
        for N in N_GRID:
            pts = [(r[4], -r[2]) for r in rows if r[0] == N]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ax.plot(xs, ys, "o-", label=f"N={N}")
        allx = np.array([r[4] for r in rows])
        ally = np.array([-r[2] for r in rows])
        k = float((allx * ally).sum() / (allx ** 2).sum())
        xx = np.linspace(0, allx.max() * 1.05, 50)
        ax.plot(xx, k * xx, "k--", lw=1, label=f"slope {k:.2f}")
        ax.set_xlabel("sqrt(N/T)")
        ax.set_ylabel("-mean t (bias)")
        ax.set_title("Instrument-FE bias against sqrt(N/T)")
        ax.legend()
        fig.tight_layout()
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scaling.png")
        fig.savefig(out, dpi=140)
        print(f"\nfigure: {out}")
    except Exception as exc:  # noqa: BLE001
        print(f"\nplot skipped: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
