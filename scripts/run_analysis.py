"""Run the full capacity-adequacy analysis and write results/ + figures/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from adequacy import data, fleet, lole, link, margin  # noqa: E402
from adequacy.paths import FIGURES, RESULTS  # noqa: E402

PERIODS = ["2025", "2026-H1", "2026-H2"]
COLORS = {"2025": "#4c72b0", "2026-H1": "#55a868", "2026-H2": "#c44e52"}
ATTR = "Data: Energy-Charts.info / SMARD.de (CC BY 4.0); derating ASSUMED"


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    panel = data.load_panel()
    inst = data.load_installed()
    s2 = data.load_step2()
    df = panel.join(s2, how="left")
    df["period"] = data.period_label(df.index)
    df["year"] = df.index.year

    # --- available dispatchable capacity, two bases -------------------------
    avail_rows, avail_by_period = [], {}
    for per in PERIODS:
        year = int(per[:4])
        sub = df[df["period"] == per]
        der = fleet.derated_mw(inst, year)
        dem = fleet.demonstrated_mw(sub)
        ins = fleet.installed_mw(inst, year)
        for t in fleet.FLEET:
            avail_rows.append({"period": per, "tech": t.name, "installed_mw": ins[t.name],
                               "derating_ASSUMED": t.derating, "derated_mw": der[t.name],
                               "demonstrated_q995_mw": dem[t.name]})
        avail_by_period[per] = {"installed": ins, "derated": sum(der.values()), "demonstrated": sum(dem.values())}
    avail = pd.DataFrame(avail_rows)
    avail.to_csv(RESULTS / "available_capacity.csv", index=False, float_format="%.0f")

    df["available_mw"] = df["period"].map({p: v["derated"] for p, v in avail_by_period.items()})
    df["margin_mw"] = margin.margin(df["available_mw"], df["residual_load_mw"])
    df["demo_available_mw"] = df["period"].map({p: v["demonstrated"] for p, v in avail_by_period.items()})
    df["demo_margin_mw"] = df["demo_available_mw"] - df["residual_load_mw"]

    # --- period summaries ---------------------------------------------------
    rows = []
    for per in PERIODS:
        sub = df[df["period"] == per]
        r = {"period": per, **margin.summarise_period(sub, n_top=100)}
        r["available_derated_mw"] = avail_by_period[per]["derated"]
        r["available_demonstrated_mw"] = avail_by_period[per]["demonstrated"]
        r["hours_demo_margin_lt0"] = int((sub["demo_margin_mw"] < 0).sum())
        r["m0_bias"] = float((sub["M0_stack"] - sub["da_price_eur_mwh"]).mean())
        thermal = sub[["lignite_mw", "hard_coal_mw", "gas_mw", "oil_mw"]].sum(axis=1)
        r["thermal_out_mean_mw"] = float(thermal.mean())
        r["thermal_out_q995_mw"] = float(thermal.quantile(0.995))
        rows.append(r)
    ps = pd.DataFrame(rows)
    ps.to_csv(RESULTS / "period_summary.csv", index=False, float_format="%.3f")

    # --- top-100 scarcity hours ---------------------------------------------
    top = []
    for per in PERIODS:
        sub = df[df["period"] == per].nlargest(100, "residual_load_mw")
        top.append(sub.assign(period=per)[["period", "residual_load_mw", "load_mw", "da_price_eur_mwh",
                                           "M0_stack", "margin_mw", "net_trade_mw"]])
    pd.concat(top).to_csv(RESULTS / "top100_residual_load_hours.csv", float_format="%.2f")

    # --- monthly -----------------------------------------------------------
    df["month"] = df.index.strftime("%Y-%m")
    mon = df.groupby("month").agg(
        da_mean=("da_price_eur_mwh", "mean"), m0_mean=("M0_stack", "mean"),
        rl_mean_mw=("residual_load_mw", "mean"), rl_max_mw=("residual_load_mw", "max"),
        margin_mean_mw=("margin_mw", "mean"), margin_min_mw=("margin_mw", "min"),
        net_import_mean_mw=("net_trade_mw", "mean"))
    mon["m0_bias"] = mon["m0_mean"] - mon["da_mean"]
    mon.to_csv(RESULTS / "monthly.csv", float_format="%.2f")
    rho_month = float(mon["margin_min_mw"].corr(mon["m0_bias"], method="spearman"))
    rho_month_mean = float(mon["margin_mean_mw"].corr(mon["m0_bias"], method="spearman"))

    # --- LOLE screen --------------------------------------------------------
    lrows = []
    for per in PERIODS:
        sub = df[df["period"] == per]
        ins = avail_by_period[per]["installed"]
        for scale in (1.0, 0.9, 0.8, 0.7):
            draws = lole.sample_capacity(ins, n_draws=20000, seed=42, derating_scale=scale)
            for imp in (0.0, 5000.0, 10000.0):
                r = lole.screen(draws, sub["residual_load_mw"], imports_mw=imp)
                lrows.append({"period": per, "hours": len(sub), "derating_scale": scale,
                              "imports_mw": imp, **r})
    lt = pd.DataFrame(lrows)
    lt.to_csv(RESULTS / "lole_screen.csv", index=False, float_format="%.4f")

    # --- link to H2 underpricing --------------------------------------------
    bins = np.arange(0, 85, 10)
    bm = link.bias_by_margin_decile(df[df["year"] == 2026], bins)
    bm.to_csv(RESULTS / "m0_bias_by_margin.csv", index=False, float_format="%.2f")
    reg = link.h2_gap_regression(df)
    # bias within the loosest half of 2026-H2 hours (above the 2026-H1 median margin)
    h1m = df.loc[df["period"] == "2026-H1", "margin_mw"].median()
    h2 = df[df["period"] == "2026-H2"]
    loose = h2[h2["margin_mw"] > h1m]
    reg["h1_median_margin_mw"] = float(h1m)
    reg["h2_hours_looser_than_h1_median"] = int(len(loose))
    reg["h2_bias_in_those_hours"] = float((loose["M0_stack"] - loose["da_price_eur_mwh"]).mean())
    reg["spearman_month_min_margin_vs_m0_bias"] = rho_month
    reg["spearman_month_mean_margin_vs_m0_bias"] = rho_month_mean

    # seasonally matched: Jun-Oct 2025 vs Jun-Oct 2026
    jo = df[df.index.month.isin([6, 7, 8, 9, 10])]
    seas = {}
    for y in (2025, 2026):
        sub = jo[jo["year"] == y]
        seas[str(y)] = {
            "hours": int(len(sub)),
            "da_mean": float(sub["da_price_eur_mwh"].mean()),
            "rl_mean_mw": float(sub["residual_load_mw"].mean()),
            "margin_mean_mw": float(sub["margin_mw"].mean()),
            "margin_p01_mw": float(sub["margin_mw"].quantile(0.01)),
            "hours_margin_lt_30gw": int((sub["margin_mw"] < 30000).sum()),
            "m0_bias": float((sub["M0_stack"] - sub["da_price_eur_mwh"]).mean()),
            "net_import_mean_mw": float(sub["net_trade_mw"].mean()),
        }
    reg["jun_oct_matched"] = seas
    pd.DataFrame(seas).T.to_csv(RESULTS / "jun_oct_2025_vs_2026.csv", float_format="%.2f")

    summary = {
        "window": [str(df.index.min()), str(df.index.max())],
        "hours": int(len(df)),
        "periods": ps.set_index("period").to_dict(orient="index"),
        "lole_main": lt[(lt.derating_scale == 1.0)].set_index(["period", "imports_mw"])["lole_h"].unstack().to_dict(),
        "h2_link": reg,
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=float))

    # --- figures ------------------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for per in PERIODS:
        sub = df[df["period"] == per]
        dc = margin.duration_curve(sub["residual_load_mw"] / 1000)
        ax[0].plot(dc["exceedance"] * 100, dc["value"], label=f"{per} ({len(sub):,} h)", color=COLORS[per])
        ax[0].axhline(avail_by_period[per]["derated"] / 1000, color=COLORS[per], ls="--", lw=0.8)
        top = sub.nlargest(500, "residual_load_mw")
        ax[1].scatter(top["residual_load_mw"] / 1000, top["da_price_eur_mwh"], s=6, alpha=0.6,
                      color=COLORS[per], label=per)
    ax[0].set(xlabel="% of hours exceeded", ylabel="Residual load (GW)",
              title="Residual-load duration curves (dashed: derated dispatchable, ASSUMED)")
    ax[0].axhline(0, color="k", lw=0.5)
    ax[0].legend()
    ax[1].set(xlabel="Residual load (GW)", ylabel="DA price (€/MWh)", title="Top-500 residual-load hours vs DA price")
    ax[1].legend()
    fig.text(0.01, 0.005, ATTR, fontsize=7, color="grey")
    fig.tight_layout()
    fig.savefig(FIGURES / "01_residual_load_duration.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for per in ["2026-H1", "2026-H2"]:
        b = bm[bm["period"] == per]
        mids = [iv.mid for iv in b["margin_bin"]]
        ax[0].plot(mids, b["m0_bias"], "o-", color=COLORS[per], label=per)
    ax[0].axhline(0, color="k", lw=0.5)
    ax[0].set(xlabel="Capacity margin bin (GW, derated, ASSUMED)", ylabel="M0 bias (€/MWh)",
              title="Step-2 stack bias by capacity margin, 2026")
    ax[0].legend()
    m = mon.copy()
    sc = ax[1].scatter(m["margin_mean_mw"] / 1000, m["m0_bias"], c=np.arange(len(m)), cmap="viridis")
    for k, r in m.iterrows():
        if k >= "2026-05":
            ax[1].annotate(k[2:], (r["margin_mean_mw"] / 1000, r["m0_bias"]), fontsize=7)
    ax[1].axhline(0, color="k", lw=0.5)
    ax[1].set(xlabel="Monthly mean margin (GW)", ylabel="Monthly M0 bias (€/MWh)",
              title="Monthly margin vs stack bias (2025-01 → 2026-10)")
    fig.text(0.01, 0.005, ATTR + "; M0 from epm-merit-order-model", fontsize=7, color="grey")
    fig.tight_layout()
    fig.savefig(FIGURES / "02_margin_vs_m0_bias.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for per in PERIODS:
        s = lt[(lt.period == per) & (lt.imports_mw == 0)]
        ax.semilogy(s["derating_scale"], s["lole_h"].clip(lower=1e-3), "o-", color=COLORS[per], label=per)
    ax.set(xlabel="Derating scale on ASSUMED factors (1 = base)", ylabel="LOLE screen, h per period (floor 1e-3)",
           title="Isolated-zone LOLE screen, no imports")
    ax.invert_xaxis()
    ax.legend()
    fig.text(0.01, 0.005, ATTR, fontsize=7, color="grey")
    fig.tight_layout()
    fig.savefig(FIGURES / "03_lole_screen.png", dpi=130)
    plt.close(fig)

    print(ps.T.to_string())
    print(lt.to_string())
    print(bm.to_string())
    print(json.dumps(reg, indent=2))
    print(avail[avail.period != "2025"].to_string())


if __name__ == "__main__":
    main()
