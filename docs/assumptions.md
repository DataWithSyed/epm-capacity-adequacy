# Assumptions register: capacity adequacy (step 4)

IDs continue the umbrella register. **ASSUMED** = screening judgement, not an observation. Edit `src/adequacy/fleet.py`.

| ID | Parameter | Value | Basis |
|---|---|---|---|
| A-C1 | Installed capacity | Energy-Charts yearly stock (2025 for 2025 hours, 2026 for 2026 hours) | Observed |
| A-C2 | Derating, lignite / hard coal / gas / oil | 0.85 / 0.65 / 0.85 / 0.50 | ASSUMED, same as step 2 (A-M7); hard coal is lower for reserve / out-of-market units |
| A-C3 | Derating, other non-renewable / biomass / hydro / pumped storage | 0.50 / 0.75 / 0.40 / 0.85 | ASSUMED; hydro is low because run-of-river is flow-limited |
| A-C4 | Battery capacity credit | 0.20 of Energy-Charts battery power | ASSUMED; mostly home storage, short duration, not market-dispatched |
| A-C5 | Unit sizes for the outage MC | lignite 600, hard coal 500, gas 200, oil 100, other 50, biomass 10, hydro 20, pumped storage 300, battery 5 MW | ASSUMED representative sizes |
| A-C6 | Unit availability in the MC | each unit available with p = derating (independent) | ASSUMED; the derating bundles planned and forced unavailability |
| A-C7 | Forced-outage rates in `fleet.py` | 0.02–0.10 | Documentation only, already inside the derating; not used separately |
| A-C8 | Imports | 0, 5, 10 GW flat allowance | ASSUMED sensitivities (isolated zone otherwise) |
| A-C9 | Demonstrated capacity | 99.5 % quantile of observed hourly output per tech and period | Data-derived lower bound (censored by demand) |
| A-C10 | Period split | 2026-H1 = Jan–May, 2026-H2 = Jun–Oct | Design choice, follows steps 2–3 |
