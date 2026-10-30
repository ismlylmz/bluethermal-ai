"""Append today's model values (site and Keri) and the latest Keri measurements to the history tables."""
import glob, os, datetime as dt
import pandas as pd, xarray as xr
import config

today = pd.Timestamp(dt.date.today())
files = sorted(glob.glob(os.path.join(config.ARCHIVE, 'forecast_*.nc')))
ds = xr.open_dataset(files[-1])
new = {}
for place, sel in config.SEL.items():
    parts = []
    for z in config.DEPTHS:
        s = ds.sel(depth=z, method='nearest').sel(**sel).mean(['latitude', 'longitude']).to_dataframe()[['thetao', 'so']]
        s.index = pd.to_datetime(s.index).normalize()
        s = s[s.index <= today].rename(columns={'thetao': 'model', 'so': 'model_sal'})
        parts.append(s.rename_axis('date').reset_index().assign(depth=z))
    new[place] = pd.concat(parts)

obs = pd.DataFrame({'date': pd.Series(dtype='datetime64[ns]'), 'obs': pd.Series(dtype=float), 'depth': pd.Series(dtype=int)})
if os.path.exists(config.path('keri_last10.csv')):
    d = pd.read_csv(config.path('keri_last10.csv'))
    d = d[(d.platform_id == config.KERI_PLATFORM) & (d.value_qc == 1)]
    d['date'] = pd.to_datetime(d.time.str[:10])
    obs = pd.concat([d[d.depth.between(z - 2, z + 2)].groupby('date').value.mean().rename('obs').reset_index().assign(depth=z)
                     for z in config.DEPTHS])

for fname, place in (('keri_table.csv', 'keri'), ('site_table.csv', 'site')):
    t = pd.read_csv(config.path(fname), parse_dates=['date'])
    n = new[place]
    if place == 'keri':
        known = pd.concat([t[['date', 'depth', 'obs']].dropna(), obs]).drop_duplicates(['date', 'depth'], keep='last')
        n = n.merge(known, on=['date', 'depth'], how='left')
        t = t.merge(obs.rename(columns={'obs': 'obs_new'}), on=['date', 'depth'], how='left')
        t['obs'] = t.obs.fillna(t.obs_new)
        t = t.drop(columns='obs_new')
    key = lambda x: x.set_index(['date', 'depth']).index
    t = pd.concat([t[~key(t).isin(key(n))], n]).sort_values(['depth', 'date'])
    t.to_csv(config.path(fname), index=False)
    print(fname, 'last day', t.date.max().date(), '| rows', len(t))
