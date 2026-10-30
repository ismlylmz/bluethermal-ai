# BlueThermal

Intake depth planning and daily operation for seawater heat pumps, built on Copernicus Marine Service data.
Pilot: Tallinn Bay, planned intake at about 70 m.

**Dashboard:** `docs/index.html`, published with GitHub Pages and rebuilt every day.

## What it does

- **Intake depth.** Corrects the Copernicus Marine Baltic model at the site with the error measured at the Keri station (TalTech) the same day, and turns winter intake temperature into cold-water days, plant capacity and backup heat by depth.
- **Operations.** Today's forecast at the intake, checked against Keri, and a cost-optimised hourly plan for heat pump, heat storage and electric boiler against Estonian day-ahead prices. Hours after the published prices use our ML price forecast. Any past week since 2023 can be replayed.
- **Evidence.** Model against Keri over two winters, archived real forecasts against measurements, and two ML models tested on unseen data.

## Daily pipeline (`pipeline/run_daily.py`, GitHub Actions at 12:15 UTC)

| Step | Script | Output |
|---|---|---|
| Live inputs | `fetch_live.py` | today's forecast in `data/forecast_archive`, `data/live.json` |
| History tables | `update_tables.py` | `data/keri_table.csv`, `data/site_table.csv` |
| Price forecast (ML) | `price_forecast.py` | `data/price_forecast.json` |
| Correction | `validate.py` | `data/site_corrected.csv`, `data/winter_summary.csv` |
| Cold week | `cold_week.py` | `data/cold_week.json` |
| Forecast test | `forecast_test.py` | `data/forecast_test.csv` |
| Sea temperature error model (ML) | `ml_correction.py` | `data/ml_summary.csv` |
| Dashboard | `build_static.py`, `build_dashboard.py` | `docs/index.html` |

`capacity.py` holds the plant model and can be run on its own for a capacity summary.

## Run locally

```
pip install -r requirements.txt
copernicusmarine login
python pipeline/run_daily.py
```

## Data sources

- Copernicus Marine Service: BALTICSEA_ANALYSISFORECAST_PHY_003_006; INSITU_BAL_PHYBGCWAV_DISCRETE_MYNRT_013_032 (Keri station, TalTech)
- Elering / Nord Pool day-ahead prices for Estonia
- Open-Meteo weather archive and forecast

Plant values are illustrative, based on published figures from Esbjerg and Stockholm.
