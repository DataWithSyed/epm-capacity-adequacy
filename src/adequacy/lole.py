"""LOLE-style screening by Monte Carlo of forced outages.

Each tech is a set of identical units (ASSUMED size). Each unit is
independently available with probability equal to its ASSUMED derating
factor (the derating bundles planned/structural unavailability and forced
outages), so the expected available capacity equals the deterministic
derated capacity and the Monte Carlo adds only the spread from discrete
unit outages. Available capacity is sampled once
(N draws, time-invariant, i.e. no seasonal maintenance) and each historical
hour's residual load is compared with the sampled capacity plus an import
allowance. LOLP_t = P(C < RL_t - imports); LOLE = sum of LOLP_t (h / period).
This is a screening statistic on the historical residual-load path, not a
probabilistic adequacy assessment (no weather resampling, no correlation).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .fleet import FLEET


def unit_counts(installed_mw: dict[str, float]) -> dict[str, tuple[int, float, float]]:
    """name -> (n_units, unit_mw, p_available) with p_available = derating."""
    out = {}
    for t in FLEET:
        cap = installed_mw.get(t.name, 0.0)
        if cap <= 0:
            continue
        n = max(1, int(round(cap / t.unit_mw)))
        unit = cap / n
        p = min(1.0, t.derating)
        out[t.name] = (n, unit, p)
    return out


def sample_capacity(installed_mw: dict[str, float], n_draws: int = 20000, seed: int = 42,
                    derating_scale: float = 1.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = np.zeros(n_draws)
    for name, (n, unit, p) in unit_counts(installed_mw).items():
        total += rng.binomial(n, min(1.0, p * derating_scale), size=n_draws) * unit
    return total


def exact_capacity_cdf(installed_mw: dict[str, float], step_mw: float = 100.0,
                       derating_scale: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Exact convolution of binomials on a `step_mw` grid (capacity-outage table).

    Returns (grid_mw, pmf). Used to validate the Monte Carlo in tests.
    """
    from math import comb

    pmf = np.array([1.0])
    for name, (n, unit, p) in unit_counts(installed_mw).items():
        p = min(1.0, p * derating_scale)
        k = np.arange(n + 1)
        w = np.array([comb(n, int(i)) for i in k], dtype=float) * p ** k * (1 - p) ** (n - k)
        idx = np.round(k * unit / step_mw).astype(int)
        tech = np.zeros(idx.max() + 1)
        np.add.at(tech, idx, w)
        pmf = np.convolve(pmf, tech)
    grid = np.arange(len(pmf)) * step_mw
    return grid, pmf / pmf.sum()


def lolp(capacity_draws: np.ndarray, residual_load_mw: pd.Series, imports_mw: float = 0.0) -> pd.Series:
    c = np.sort(capacity_draws)
    need = residual_load_mw.to_numpy() - imports_mw
    # share of draws strictly below need
    p = np.searchsorted(c, need, side="left") / len(c)
    return pd.Series(p, index=residual_load_mw.index, name="lolp")


def screen(capacity_draws: np.ndarray, rl: pd.Series, imports_mw: float = 0.0) -> dict:
    """LOLE (h), hours with LOLP > 1 %, expected unserved energy (GWh)."""
    c = np.sort(capacity_draws)
    n = len(c)
    need = rl.to_numpy() - imports_mw
    k = np.searchsorted(c, need, side="left")
    prefix = np.concatenate([[0.0], np.cumsum(c)])
    eue_mwh = (k * need - prefix[k]) / n  # E[max(0, need - C)] per hour
    lp = k / n
    return {
        "lole_h": float(lp.sum()),
        "hours_lolp_gt_1pct": int((lp > 0.01).sum()),
        "eue_gwh": float(eue_mwh.sum()) / 1000.0,
        "cap_mean_mw": float(c.mean()),
        "cap_p01_mw": float(np.quantile(c, 0.01)),
    }
