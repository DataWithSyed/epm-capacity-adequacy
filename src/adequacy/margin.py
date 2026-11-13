"""Residual-load duration curves, scarcity hours and capacity margins."""
from __future__ import annotations

import numpy as np
import pandas as pd


def duration_curve(x: pd.Series) -> pd.DataFrame:
    """Sorted descending values against exceedance share (0..1]."""
    v = np.sort(x.dropna().to_numpy())[::-1]
    n = len(v)
    return pd.DataFrame({"exceedance": np.arange(1, n + 1) / n, "value": v})


def top_n(df: pd.DataFrame, col: str, n: int) -> pd.DataFrame:
    return df.nlargest(n, col)


def margin(available_mw: float | pd.Series, residual_load_mw: pd.Series) -> pd.Series:
    """Capacity margin (MW): available dispatchable minus residual load (isolated zone)."""
    return available_mw - residual_load_mw


def summarise_period(df: pd.DataFrame, n_top: int = 100) -> dict:
    rl = df["residual_load_mw"]
    p = df["da_price_eur_mwh"]
    top_rl = df.nlargest(n_top, "residual_load_mw")
    top_p = df.nlargest(n_top, "da_price_eur_mwh")
    overlap = len(top_rl.index.intersection(top_p.index))
    return {
        "hours": int(len(df)),
        "rl_mean_mw": float(rl.mean()),
        "rl_p99_mw": float(rl.quantile(0.99)),
        "rl_max_mw": float(rl.max()),
        "load_mean_mw": float(df["load_mw"].mean()),
        "price_mean": float(p.mean()),
        "price_top_rl_hours": float(top_rl["da_price_eur_mwh"].mean()),
        "rl_top_price_hours_mw": float(top_p["residual_load_mw"].mean()),
        "top_overlap_share": overlap / n_top,
        "spearman_rl_price": float(rl.corr(p, method="spearman")),
        "net_import_mean_mw": float(df["net_trade_mw"].mean()),
        "net_import_in_top_rl_mw": float(top_rl["net_trade_mw"].mean()),
        "margin_mean_mw": float(df["margin_mw"].mean()) if "margin_mw" in df else np.nan,
        "margin_min_mw": float(df["margin_mw"].min()) if "margin_mw" in df else np.nan,
        "margin_p01_mw": float(df["margin_mw"].quantile(0.01)) if "margin_mw" in df else np.nan,
    }
