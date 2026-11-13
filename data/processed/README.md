# Processed panels (derived, attributed)

- `hourly_panel.csv`, `installed_gw.csv`: copied unchanged from step 2 ([epm-merit-order-model](https://github.com/DataWithSyed/epm-merit-order-model) `data/processed/`). Hourly means of 15-min Energy-Charts v2 data, 2025-01-01 → 2026-10-31 (timestamps in UTC; analysis in Europe/Berlin). Sources: Energy-Charts.info (Fraunhofer ISE), DE-LU day-ahead price from Bundesnetzagentur | SMARD.de. **CC BY 4.0.** `net_trade_mw` > 0 = net import.
- `step2_model_prices.csv.gz`: step-2 hourly model prices `M0_stack` (uncalibrated stack) and `C3_rolling90_linear` (MIT, derived).
