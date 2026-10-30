"""Collect history, validation and test results into data/static.json for the dashboard."""
import os, json
import pandas as pd
import config

m = pd.read_csv(config.path('site_corrected.csv'), parse_dates=['date'])
k = pd.read_csv(config.path('keri_table.csv'), parse_dates=['date'])
m['winter'] = m.date.map(config.winter_of)
k['winter'] = k.date.map(config.winter_of)
r = lambda v: None if pd.isna(v) else round(float(v), 2)
out = {'winters': {}}
for w in sorted(m.winter.dropna().unique()):
    w = int(w)
    g = m[m.winter == w]
    days = sorted(g.date.unique())
    W = {'days': [pd.Timestamp(d).strftime('%Y-%m-%d') for d in days]}
    for z in config.DEPTHS:
        h = g[g.depth == z].set_index('date').reindex(days)
        kk = k[(k.winter == w) & (k.depth == z)].set_index('date').reindex(days)
        W[str(z)] = {'raw': [r(v) for v in h.model], 'sal': [r(v) for v in h.model_sal], 'cor': [r(v) for v in h.corrected],
                     'keri_obs': [r(v) for v in kk.obs], 'keri_mod': [r(v) for v in kk.model]}
    W['has_obs'] = bool(k[k.winter == w].obs.notna().sum() > 0)
    out['winters'][f'{w}-{str(w + 1)[2:]}'] = W

if os.path.exists(config.path('forecast_test.csv')):
    t = pd.read_csv(config.path('forecast_test.csv'), parse_dates=['issued', 'target'])
    ft = {}
    for z in config.DEPTHS:
        g = t[t.depth == z].assign(e_m=lambda x: (x.model - x.obs).abs(), e_p=lambda x: (x.persistence - x.obs).abs(),
                                   e_c=lambda x: (x.corrected - x.obs).abs()).groupby('lead')
        a = g.agg(n=('e_m', 'size'), copernicus=('e_m', 'mean'), persistence=('e_p', 'mean'), corrected=('e_c', 'mean'))
        ft[str(z)] = {'lead': a.index.tolist(), 'n': a.n.tolist(), **{c: [round(v, 3) for v in a[c]] for c in ('copernicus', 'persistence', 'corrected')}}
    out['forecast_test'] = ft
    out['forecast_test_meta'] = {'files': int(t.issued.nunique()), 'first': str(t.issued.min().date()), 'last_obs': str(t.target.max().date())}

if os.path.exists(config.path('ml_summary.csv')):
    out['ml'] = pd.read_csv(config.path('ml_summary.csv')).to_dict(orient='records')
if os.path.exists(config.path('cold_week.json')):
    out['cold_week'] = json.load(open(config.path('cold_week.json')))

# Look-back data: every day at 60/70 m and hourly prices and air temperature since 2023
if os.path.exists(config.path('elering_hourly.csv')) and os.path.exists(config.path('weather_archive.csv')):
    p = pd.read_csv(config.path('elering_hourly.csv'), index_col=0).price
    p.index = pd.to_datetime(p.index, utc=True)
    a = pd.read_csv(config.path('weather_archive.csv'), index_col=0, parse_dates=[0]).tallinn_temperature_2m
    a.index = a.index.tz_localize('UTC') if a.index.tz is None else a.index
    idx = pd.date_range(p.index.min().floor('D'), p.index.max(), freq='h')
    out['hourly'] = {'start': idx[0].strftime('%Y-%m-%dT%H:00Z'),
                     'price': [None if pd.isna(v) else round(float(v), 1) for v in p.reindex(idx).values],
                     'air': [None if pd.isna(v) else round(float(v), 1) for v in a.reindex(idx).interpolate(limit=6).values]}
    days = pd.date_range(m.date.min(), m.date.max(), freq='D')
    out['daily'] = {'start': str(days[0].date())}
    for z in (60, 70):
        h = m[m.depth == z].set_index('date').reindex(days)
        out['daily'][str(z)] = {'raw': [r(v) for v in h.model], 'cor': [r(v) for v in h.corrected], 'sal': [r(v) for v in h.model_sal]}

json.dump(out, open(config.path('static.json'), 'w'))
print('static.json', round(os.path.getsize(config.path('static.json')) / 1e3), 'kB | winters', list(out['winters']))
