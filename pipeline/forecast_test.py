"""Check archived daily Copernicus forecasts against Keri measurements.

Compares three methods by lead time: the forecast as issued, the last measurement kept constant,
and the forecast shifted by the last known model error. Writes data/forecast_test.csv."""
import glob, os, re
import pandas as pd, xarray as xr
import config

k = pd.read_csv(config.path('keri_table.csv'), parse_dates=['date']).dropna(subset=['obs'])
obs = {z: k[k.depth == z].set_index('date').obs for z in config.DEPTHS}
if os.path.exists(config.path('keri_last10.csv')):
    d = pd.read_csv(config.path('keri_last10.csv'))
    d = d[(d.platform_id == config.KERI_PLATFORM) & (d.value_qc == 1)]
    d['date'] = pd.to_datetime(d.time.str[:10])
    for z in config.DEPTHS:
        new = d[d.depth.between(z - 2, z + 2)].groupby('date').value.mean()
        obs[z] = pd.concat([obs[z], new[~new.index.isin(obs[z].index)]]).sort_index()

rows = []
for f in sorted(glob.glob(os.path.join(config.ARCHIVE, 'forecast_*.nc'))):
    issued = pd.Timestamp(re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(f)).group(1))
    ds = xr.open_dataset(f)
    for z in config.DEPTHS:
        s = ds.thetao.sel(depth=z, method='nearest').sel(**config.SEL['keri']).mean(['latitude', 'longitude']).to_series()
        s.index = pd.to_datetime(s.index).normalize()
        o = obs[z]
        before = o[o.index < issued]
        if len(before) == 0:
            continue
        t0, o0 = before.index[-1], before.iloc[-1]
        err0 = s.get(t0) - o0 if t0 in s.index else float('nan')
        for t, v in s.items():
            lead = (t - issued).days
            if lead < 1 or t not in o.index:
                continue
            rows.append(dict(issued=issued, target=t, lead=lead, depth=z, obs=o[t], model=v, persistence=o0, corrected=v - err0))

d = pd.DataFrame(rows).sort_values(['depth', 'target', 'issued'])
d['jump'] = d.groupby(['depth', 'target']).model.diff().abs()
d.to_csv(config.path('forecast_test.csv'), index=False)
d['group'] = pd.cut(d.lead, [0, 2, 5, 8], labels=['1-2 days', '3-5 days', '6-8 days'])
for c in ('model', 'persistence', 'corrected'):
    d[f'err_{c}'] = (d[c] - d.obs).abs()
t = d.groupby(['depth', 'group'], observed=True).agg(pairs=('err_model', 'size'), copernicus=('err_model', 'mean'),
                                                     persistence=('err_persistence', 'mean'), corrected=('err_corrected', 'mean')).round(2)
print('Mean absolute error (C) at Keri\n', t.to_string(), sep='')
print('Forecast files:', d.issued.nunique(), '| last measurement:', d.target.max().date())
