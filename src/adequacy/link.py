"""Does capacity tightness explain the step-2 H2-2026 merit-order underpricing?

M0 error e_t = M0_t - DA_t (negative = model underprices). We compare the
error across margin deciles in each period and fit
    DA_t - M0_t = a + b * margin_GW_t + c * 1[2026-H2] + hour-of-day FE
on 2026 hours with HAC-free OLS (point estimates only; standard errors from
a block bootstrap by day). If tightness explained the underpricing, the H2
dummy c would shrink towards zero once the margin is controlled for, and
the bias would be concentrated in the tightest hours.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def bias_by_margin_decile(df: pd.DataFrame, bins: np.ndarray) -> pd.DataFrame:
    d = df.dropna(subset=["M0_stack", "margin_mw"]).copy()
    d["err"] = d["M0_stack"] - d["da_price_eur_mwh"]
    d["margin_bin"] = pd.cut(d["margin_mw"] / 1000.0, bins, include_lowest=True)
    g = d.groupby(["period", "margin_bin"], observed=True)
    return g.agg(hours=("err", "size"), da_mean=("da_price_eur_mwh", "mean"),
                 m0_mean=("M0_stack", "mean"), m0_bias=("err", "mean")).reset_index()


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def design(d: pd.DataFrame, with_margin: bool = True) -> np.ndarray:
    hours = d.index.hour.to_numpy()
    fe = (hours[:, None] == np.arange(1, 24)[None, :]).astype(float)
    cols = [np.ones(len(d)), (d["period"] == "2026-H2").to_numpy(float)]
    if with_margin:
        cols.append(d["margin_mw"].to_numpy() / 1000.0)
    return np.column_stack(cols + [fe])


def h2_gap_regression(df: pd.DataFrame, n_boot: int = 300, seed: int = 0) -> dict:
    d = df[df["period"].isin(["2026-H1", "2026-H2"])].dropna(subset=["M0_stack", "margin_mw"])
    y = (d["da_price_eur_mwh"] - d["M0_stack"]).to_numpy()
    X0, X1 = design(d, False), design(d, True)
    b0, b1 = _ols(X0, y), _ols(X1, y)
    days = d.index.normalize()
    ud = np.unique(days)
    pos = {k: np.flatnonzero(days == k) for k in ud}
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        idx = np.concatenate([pos[k] for k in rng.choice(ud, len(ud), replace=True)])
        bs.append(_ols(X1[idx], y[idx])[[1, 2]])
    bs = np.array(bs)
    return {
        "hours": int(len(d)),
        "h2_gap_no_margin": float(b0[1]),
        "h2_gap_with_margin": float(b1[1]),
        "h2_gap_with_margin_ci95": [float(np.quantile(bs[:, 0], 0.025)), float(np.quantile(bs[:, 0], 0.975))],
        "margin_slope_eur_per_gw": float(b1[2]),
        "margin_slope_ci95": [float(np.quantile(bs[:, 1], 0.025)), float(np.quantile(bs[:, 1], 0.975))],
        "share_of_gap_explained_by_margin": float(1 - b1[1] / b0[1]) if b0[1] != 0 else np.nan,
    }
