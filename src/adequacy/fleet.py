"""Dispatchable fleet for the adequacy screen.

Installed GW are observed (Energy-Charts yearly stock). Derating factors,
unit sizes and forced-outage rates are ASSUMED engineering screening values
(register in docs/assumptions.md, IDs A-C*). Thermal deratings match step 2.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Tech:
    name: str
    installed_key: str      # column in installed_gw.csv
    derating: float         # ASSUMED expected share of nameplate firm at peak (incl. forced outages)
    unit_mw: float          # ASSUMED representative unit size for the outage Monte Carlo
    forced_outage: float    # ASSUMED forced-outage rate
    output_cols: tuple = () # panel columns with observed output of this tech


FLEET = (
    Tech("lignite", "fossil_brown_coal_lignite", 0.85, 600, 0.08, ("lignite_mw",)),
    Tech("hard_coal", "fossil_hard_coal", 0.65, 500, 0.08, ("hard_coal_mw", "coal_gas_mw")),
    Tech("gas", "fossil_gas", 0.85, 200, 0.05, ("gas_mw",)),
    Tech("oil", "fossil_oil", 0.50, 100, 0.10, ("oil_mw",)),
    Tech("other_non_renewable", "other_non_renewable", 0.50, 50, 0.10, ("waste_mw", "others_mw")),
    Tech("biomass", "biomass", 0.75, 10, 0.10, ("biomass_mw",)),
    Tech("hydro", "hydro", 0.40, 20, 0.05, ("hydro_ror_mw", "hydro_res_mw")),
    Tech("pumped_storage", "hydro_pumped_storage", 0.85, 300, 0.05, ("ps_gen_mw",)),
    Tech("battery", "battery_storage_power", 0.20, 5, 0.02, ()),
)


def installed_mw(installed: pd.DataFrame, year: int) -> dict[str, float]:
    row = installed.loc[year]
    out = {}
    for t in FLEET:
        v = row.get(t.installed_key)
        out[t.name] = 0.0 if pd.isna(v) else float(v) * 1000.0
    return out


def derated_mw(installed: pd.DataFrame, year: int, scale: float = 1.0) -> dict[str, float]:
    inst = installed_mw(installed, year)
    return {t.name: inst[t.name] * min(1.0, t.derating * scale) for t in FLEET}


def demonstrated_mw(panel: pd.DataFrame, q: float = 0.995) -> dict[str, float]:
    """Observed q-quantile of hourly output per tech in `panel` (data-derived).

    This is a lower bound on deliverable capacity: plants only show output
    when the market calls them, so it is censored by demand and imports.
    """
    out = {}
    for t in FLEET:
        if not t.output_cols:
            out[t.name] = 0.0
            continue
        s = panel[list(t.output_cols)].clip(lower=0).sum(axis=1, min_count=1)
        out[t.name] = float(s.quantile(q)) if s.notna().any() else 0.0
    return out
