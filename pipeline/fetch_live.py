"""Fetch today's inputs: Copernicus forecast (archived), latest Keri measurements,
Estonian day-ahead prices (Elering) and Tallinn air temperature (Open-Meteo). Writes data/live.json."""
import os, json, datetime as dt
import pandas as pd, xarray as xr, requests, copernicusmarine as cm
import config

today = dt.date.today()
out = {'created': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
os.makedirs(config.ARCHIVE, exist_ok=True)

# 1) Copernicus Marine Baltic forecast, archived once per day
name = f'forecast_{today}.nc'
if not os.path.exists(os.path.join(config.ARCHIVE, name)):
    cm.subset(dataset_id=config.MODEL_DATASET, variables=['thetao', 'so'], minimum_depth=0, maximum_depth=100,
              start_datetime=str(today - dt.timedelta(days=2)), end_datetime=str(today + dt.timedelta(days=10)),
              output_directory=config.ARCHIVE, output_filename=name, **config.ARCHIVE_BOX)
ds = xr.open_dataset(os.path.join(config.ARCHIVE, name))
fc = {'issued': str(today), 'dates': [str(t)[:10] for t in ds.time.values]}
for place, sel in config.SEL.items():
    for z in config.DEPTHS:
        s = ds.sel(depth=z, method='nearest').sel(**sel).mean(['latitude', 'longitude'])
        fc[f'{place}_{z}_t'] = [round(float(v), 3) for v in s.thetao.values]
        fc[f'{place}_{z}_s'] = [round(float(v), 3) for v in s.so.values]
out['forecast'] = fc

# 2) Keri station, last 10 days
cm.subset(dataset_id=config.INSITU_DATASET, dataset_part='latest', variables=['TEMP'],
          start_datetime=str(today - dt.timedelta(days=10)), end_datetime=str(today + dt.timedelta(days=1)),
          file_format='csv', output_directory=config.DATA, output_filename='keri_last10.csv', overwrite=True,
          **config.KERI_BOX)
d = pd.read_csv(config.path('keri_last10.csv'))
d = d[(d.platform_id == config.KERI_PLATFORM) & (d.value_qc == 1)]
d['date'] = d.time.str[:10]
out['keri_obs'] = {str(z): d[d.depth.between(z - 2, z + 2)].groupby('date').value.mean().round(3).to_dict()
                   for z in config.DEPTHS}

# 3) Elering day-ahead prices, last 14 days + published days ahead (EUR/MWh, hourly mean)
r = requests.get('https://dashboard.elering.ee/api/nps/price', timeout=30,
                 params={'start': f'{today - dt.timedelta(days=14)}T00:00:00Z', 'end': f'{today + dt.timedelta(days=2)}T00:00:00Z'}).json()
p = pd.DataFrame(r['data']['ee'])
p['time'] = pd.to_datetime(p.timestamp, unit='s', utc=True)
h = p.set_index('time').price.resample('h').mean().dropna().round(2)
out['prices'] = {'time': [t.strftime('%Y-%m-%dT%H:00Z') for t in h.index], 'eur_mwh': h.tolist()}

# 4) Tallinn air temperature forecast
w = requests.get('https://api.open-meteo.com/v1/forecast', timeout=30,
                 params={'latitude': 59.44, 'longitude': 24.75, 'hourly': 'temperature_2m',
                         'forecast_days': 10, 'past_days': 1, 'timezone': 'UTC'}).json()
out['weather'] = {'time': [t + 'Z' for t in w['hourly']['time']], 'temp': w['hourly']['temperature_2m']}

json.dump(out, open(config.path('live.json'), 'w'))
print('forecast', fc['dates'][0], '->', fc['dates'][-1], '| site 70 m', fc['site_70_t'][:3])
print('Keri 70 m', list(out['keri_obs']['70'].items())[-2:])
print('prices to', out['prices']['time'][-1])
