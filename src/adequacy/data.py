"""Load the lab panel (shipped from step 2, epm-merit-order-model).

Sources: Energy-Charts.info (Fraunhofer ISE) public net generation / load /
residual load / cross-border trade and yearly installed capacity; DE-LU
day-ahead price from Bundesnetzagentur | SMARD.de. All CC BY 4.0.
`step2_model_prices.csv.gz` holds the step-2 merit-order back-cast (M0, C3).
"""
from __future__ import annotations

import pandas as pd

from .paths import PROCESSED

TZ = "Europe/Berlin"


def load_panel(path=None) -> pd.DataFrame:
    p = path or PROCESSED / "hourly_panel.csv"
    d = pd.read_csv(p)
    d["timestamp"] = pd.to_datetime(d["timestamp"], utc=True).dt.tz_convert(TZ)
    d = d.set_index("timestamp").sort_index()
    if d.index.has_duplicates:
        raise ValueError("duplicate timestamps in panel")
    return d


def load_installed(path=None) -> pd.DataFrame:
    p = path or PROCESSED / "installed_gw.csv"
    return pd.read_csv(p).set_index("year")


def load_step2(path=None) -> pd.DataFrame:
    p = path or PROCESSED / "step2_model_prices.csv.gz"
    m = pd.read_csv(p)
    m["timestamp"] = pd.to_datetime(m["timestamp"], utc=True).dt.tz_convert(TZ)
    return m.set_index("timestamp").sort_index()


def period_label(idx: pd.DatetimeIndex) -> pd.Series:
    """'2025', '2026-H1' (Jan-May) and '2026-H2' (Jun-Oct).

    The 2026 split at June follows steps 2-3, where the merit-order
    underpricing starts in June 2026.
    """
    y = idx.year
    lab = pd.Series(y.astype(str), index=idx)
    lab[(y == 2026) & (idx.month < 6)] = "2026-H1"
    lab[(y == 2026) & (idx.month >= 6)] = "2026-H2"
    return lab
