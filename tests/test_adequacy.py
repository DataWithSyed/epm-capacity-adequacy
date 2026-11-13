import numpy as np
import pandas as pd
import pytest

from adequacy import data, fleet, link, lole, margin


@pytest.fixture(scope="module")
def panel():
    return data.load_panel()


@pytest.fixture(scope="module")
def installed():
    return data.load_installed()


def test_panel_sanity(panel):
    assert len(panel) == 16056
    assert panel.index.is_monotonic_increasing
    assert str(panel.index.tz) == "Europe/Berlin"
    rl = panel["load_mw"] - panel["wind_onshore_mw"] - panel["wind_offshore_mw"] - panel["solar_mw"]
    assert (panel["residual_load_mw"] - rl).abs().max() < 1.0  # Energy-Charts residual load = load - wind - solar


def test_period_labels(panel):
    lab = data.period_label(panel.index)
    counts = lab.value_counts()
    assert counts["2025"] == 8760
    assert counts["2026-H1"] + counts["2026-H2"] == 16056 - 8760
    assert (lab[panel.index.month == 6] != "2026-H1").all()


def test_step2_join(panel):
    s2 = data.load_step2()
    j = panel.join(s2, how="left")
    assert j["M0_stack"].notna().mean() > 0.999


def test_duration_curve_monotone():
    s = pd.Series([3.0, 1.0, 2.0, np.nan, 5.0])
    dc = margin.duration_curve(s)
    assert list(dc["value"]) == [5.0, 3.0, 2.0, 1.0]
    assert dc["exceedance"].iloc[-1] == 1.0


def test_margin_and_summary():
    idx = pd.date_range("2026-01-01", periods=4, freq="h", tz="Europe/Berlin")
    df = pd.DataFrame({"residual_load_mw": [10.0, 40.0, 20.0, 30.0], "da_price_eur_mwh": [1.0, 4.0, 2.0, 3.0],
                       "load_mw": 50.0, "net_trade_mw": [0.0, 5.0, 0.0, 1.0]}, index=idx)
    df["margin_mw"] = margin.margin(50.0, df["residual_load_mw"])
    s = margin.summarise_period(df, n_top=1)
    assert s["margin_min_mw"] == 10.0
    assert s["price_top_rl_hours"] == 4.0
    assert s["top_overlap_share"] == 1.0
    assert s["spearman_rl_price"] == pytest.approx(1.0)


def test_derated_below_installed(installed):
    ins = fleet.installed_mw(installed, 2026)
    der = fleet.derated_mw(installed, 2026)
    for k in ins:
        assert 0 <= der[k] <= ins[k]
    assert ins["lignite"] == pytest.approx(14776.0)
    assert fleet.derated_mw(installed, 2026, scale=10)["gas"] == pytest.approx(ins["gas"])  # capped at nameplate


def test_demonstrated_is_quantile(panel):
    d = fleet.demonstrated_mw(panel, q=1.0)
    assert d["lignite"] == pytest.approx(panel["lignite_mw"].max())
    assert d["battery"] == 0.0


def test_mc_matches_exact_convolution():
    ins = {"lignite": 6000.0, "gas": 4000.0, "oil": 1000.0}
    draws = lole.sample_capacity(ins, n_draws=200000, seed=1)
    grid, pmf = lole.exact_capacity_cdf(ins, step_mw=100.0)
    mean_exact = float((grid * pmf).sum())
    expected = 6000 * 0.85 + 4000 * 0.85 + 1000 * 0.5
    assert mean_exact == pytest.approx(expected, rel=1e-3)
    assert draws.mean() == pytest.approx(expected, rel=2e-3)
    for thr in (7000.0, 8000.0, 9000.0):
        p_exact = float(pmf[grid < thr].sum())
        assert (draws < thr).mean() == pytest.approx(p_exact, abs=0.01)


def test_lole_monotone_in_load_and_imports():
    draws = lole.sample_capacity({"gas": 10000.0}, n_draws=5000, seed=3)
    rl = pd.Series([7000.0, 8500.0, 9000.0])
    base = lole.screen(draws, rl)
    more = lole.screen(draws, rl + 500)
    imp = lole.screen(draws, rl, imports_mw=1000)
    assert more["lole_h"] >= base["lole_h"] >= imp["lole_h"]
    assert more["eue_gwh"] >= base["eue_gwh"] >= imp["eue_gwh"] >= 0


def test_eue_formula_matches_bruteforce():
    rng = np.random.default_rng(0)
    draws = rng.uniform(0, 100, 1000)
    rl = pd.Series([20.0, 50.0, 90.0])
    r = lole.screen(draws, rl)
    brute = sum(np.maximum(0, x - draws).mean() for x in rl) / 1000.0
    assert r["eue_gwh"] == pytest.approx(brute)
    assert r["lole_h"] == pytest.approx(sum((draws < x).mean() for x in rl))


def test_h2_regression_recovers_level_shift():
    rng = np.random.default_rng(5)
    idx = pd.date_range("2026-01-01", "2026-10-31 23:00", freq="h", tz="Europe/Berlin")
    n = len(idx)
    per = np.where(idx.month >= 6, "2026-H2", "2026-H1")
    m = rng.uniform(10_000, 80_000, n)
    m0 = rng.uniform(50, 150, n)
    da = m0 + 30 * (per == "2026-H2") - 0.5 * m / 1000 + rng.normal(0, 5, n)
    df = pd.DataFrame({"period": per, "margin_mw": m, "M0_stack": m0, "da_price_eur_mwh": da}, index=idx)
    r = link.h2_gap_regression(df, n_boot=30)
    assert r["h2_gap_with_margin"] == pytest.approx(30, abs=1.0)
    assert r["margin_slope_eur_per_gw"] == pytest.approx(-0.5, abs=0.05)
