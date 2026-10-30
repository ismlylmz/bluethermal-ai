"""Find the week in winter 2023-24 with the largest sea-driven heat shortfall at 70 m and export it.

Shortfall per day = min(demand, capacity from raw model) - capacity from corrected temperature.
Writes data/cold_week.json with daily sea temperatures and hourly prices and air temperature."""
import json
import pandas as pd
import config
from capacity import capacity

m = pd.read_csv(config.path('site_corrected.csv'), parse_dates=['date'])
z70 = m[m.depth == 70].set_index('date').sort_index().loc['2023-12-01':'2024-04-30']
air_d = pd.read_csv(config.path('weather_archive.csv'), index_col=0, parse_dates=[0]).tallinn_temperature_2m
air_d.index = air_d.index.tz_localize(None) if air_d.index.tz is not None else air_d.index
air_d = air_d.resample('D').mean()
demand = 70 * (0.35 + 0.75 * ((17 - air_d.reindex(z70.index)) / 32).clip(0, 1))
loss = pd.Series([max(0.0, min(d, capacity(r, s)[0]) - capacity(c, s)[0]) if pd.notna(c) else float('nan')
                  for r, c, s, d in zip(z70.model, z70.corrected, z70.model_sal, demand)], index=z70.index)
complete = loss.notna().rolling(7).sum() == 7
end = loss.rolling(7).sum()[complete].idxmax()
days = pd.date_range(end - pd.Timedelta(days=6), end, freq='D')

out = {'dates': [d.strftime('%Y-%m-%d') for d in days]}
for z in config.DEPTHS:
    t = m[m.depth == z].set_index('date').reindex(days)
    out[str(z)] = {'raw': t.model.round(3).tolist(), 'cor': t.corrected.round(3).tolist(), 'sal': t.model_sal.round(3).tolist()}
hours = pd.date_range(days[0], days[-1] + pd.Timedelta(hours=23), freq='h', tz='UTC')
price = pd.read_csv(config.path('elering_hourly.csv'), index_col=0).price
price.index = pd.to_datetime(price.index, utc=True)
air = pd.read_csv(config.path('weather_archive.csv'), index_col=0, parse_dates=[0]).tallinn_temperature_2m
air.index = air.index.tz_localize('UTC') if air.index.tz is None else air.index
out['hours'] = [t.strftime('%Y-%m-%dT%H:00Z') for t in hours]
out['price'] = price.reindex(hours).interpolate().round(2).tolist()
out['air'] = air.reindex(hours).interpolate().round(1).tolist()
json.dump(out, open(config.path('cold_week.json'), 'w'))
print('Cold week', out['dates'][0], '->', out['dates'][-1], '| 70 m raw', out['70']['raw'], '| corrected', out['70']['cor'])
