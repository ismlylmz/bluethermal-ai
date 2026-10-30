"""Hourly electricity price forecast for Estonia, 10 days ahead.

Gradient boosting on Elering hourly prices since 2023 with weather from Open-Meteo
(Tallinn temperature and sun, 100 m wind on the Finnish west coast and the Lithuanian coast).
Back-tested on the last 60 days against a typical-day hourly profile. Writes data/price_forecast.json."""
import os, json, time, datetime as dt
import numpy as np, pandas as pd, requests
from sklearn.ensemble import HistGradientBoostingRegressor
import config

today = dt.date.today()
START = dt.date(2023, 1, 1)
PLACES = {'tallinn': (59.44, 24.75), 'pori': (61.48, 21.80), 'klaipeda': (55.90, 21.10)}
VARS = 'temperature_2m,wind_speed_100m,shortwave_radiation'


def get_json(url, params, tries=4):
    for i in range(tries):
        r = requests.get(url, params=params, timeout=180)
        if r.status_code == 200:
            return r.json()
        print('Open-Meteo returned', r.status_code, r.text[:200], '- retrying')
        time.sleep(10 * (i + 1))
    raise RuntimeError('Open-Meteo request failed')


# 1) Prices (cached)
cache = config.path('elering_hourly.csv')
old = pd.read_csv(cache, index_col=0).price if os.path.exists(cache) else pd.Series(dtype=float)
if len(old):
    old.index = pd.to_datetime(old.index, utc=True)
a = (old.index.max().date() - dt.timedelta(days=3)) if len(old) else START
parts = []
while a <= today + dt.timedelta(days=1):
    b = min(a + dt.timedelta(days=31), today + dt.timedelta(days=2))
    r = requests.get('https://dashboard.elering.ee/api/nps/price', timeout=60,
                     params={'start': f'{a}T00:00:00Z', 'end': f'{b}T00:00:00Z'}).json()
    d = pd.DataFrame(r['data']['ee'])
    if len(d):
        d['time'] = pd.to_datetime(d.timestamp, unit='s', utc=True)
        parts.append(d.set_index('time').price.resample('h').mean())
    a = b
price = pd.concat(([old] if len(old) else []) + parts)
price = price[~price.index.duplicated(keep='last')].sort_index().dropna()
price.rename('price').to_frame().to_csv(cache, index_label='time')
last_known = price.index.max()


# 2) Weather: archive (cached) + forecast
def weather():
    cache_w = config.path('weather_archive.csv')
    w = pd.read_csv(cache_w, index_col=0, parse_dates=[0]) if os.path.exists(cache_w) else None
    if w is not None and w.index.tz is not None:
        w.index = w.index.tz_localize(None)
    start = (w.index.max().date() - dt.timedelta(days=2)) if w is not None else START
    archive_end = today - dt.timedelta(days=6)
    if start < archive_end:
        cols = []
        for k, (la, lo) in PLACES.items():
            chunks, a = [], start
            while a <= archive_end:
                b = min(a + dt.timedelta(days=365), archive_end)
                j = get_json('https://archive-api.open-meteo.com/v1/archive', dict(
                    latitude=la, longitude=lo, start_date=str(a), end_date=str(b), hourly=VARS, timezone='UTC'))['hourly']
                chunks.append(pd.DataFrame({f'{k}_{v}': j[v] for v in VARS.split(',')}, index=pd.to_datetime(j['time'])))
                a = b + dt.timedelta(days=1)
                time.sleep(1)
            cols.append(pd.concat(chunks))
        fresh = pd.concat(cols, axis=1)
        w = fresh if w is None else pd.concat([w, fresh])
        w = w[~w.index.duplicated(keep='last')].sort_index()
        w.rename_axis('time').to_csv(cache_w)
    f = []
    for k, (la, lo) in PLACES.items():
        j = get_json('https://api.open-meteo.com/v1/forecast', dict(
            latitude=la, longitude=lo, hourly=VARS, past_days=10, forecast_days=11, timezone='UTC'))['hourly']
        f.append(pd.DataFrame({f'{k}_{v}': j[v] for v in VARS.split(',')}, index=pd.to_datetime(j['time'])))
    f = pd.concat(f, axis=1)
    w = pd.concat([w[w.index < f.index.min()], f]).sort_index()
    w.index = w.index.tz_localize('UTC')
    return w.dropna()


W = weather()


# 3) Features: calendar, weather and the price level known 10 days before
def features(idx):
    X = W.reindex(idx).copy()
    X['hour'], X['weekday'], X['month'] = idx.hour, idx.dayofweek, idx.month
    X['weekend'] = (idx.dayofweek >= 5).astype(int)
    daily = price.resample('D').mean()
    daily = daily.reindex(pd.date_range(daily.index.min(), idx.max().floor('D'), freq='D'))
    level = daily.rolling(7, min_periods=4).mean().shift(10)
    X['level'] = level.reindex(idx.floor('D')).values
    return X


idx = price.index[price.index >= pd.Timestamp(START, tz='UTC') + pd.Timedelta(days=20)]
X, y = features(idx), price.loc[idx]
ok = X.notna().all(axis=1)
X, y = X[ok], y[ok]
model = lambda: HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_depth=6, min_samples_leaf=40, random_state=0)

# 4) Back-test on the last 60 days
cut = pd.Timestamp(today - dt.timedelta(days=60), tz='UTC')
m = model().fit(X[X.index < cut], y[y.index < cut])
te = X.index >= cut
p_ml = pd.Series(m.predict(X[te]), index=X.index[te])
prof = []
for t in p_ml.index:
    past = price[(price.index < t.floor('D') - pd.Timedelta(days=9)) & (price.index >= t.floor('D') - pd.Timedelta(days=23))]
    prof.append(past[past.index.hour == t.hour].mean())
p_prof = pd.Series(prof, index=p_ml.index)
actual = y[te]


def cheap6(pred):
    hits = []
    for _, s in actual.groupby(actual.index.floor('D')):
        if len(s) == 24:
            hits.append(len(set(s.nsmallest(6).index) & set(pred.loc[s.index].nsmallest(6).index)) / 6)
    return round(100 * np.mean(hits))


test = dict(days=int(actual.index.floor('D').nunique()),
            mae_ml=round(float((p_ml - actual).abs().mean()), 1), mae_profile=round(float((p_prof - actual).abs().mean()), 1),
            cheap6_ml=cheap6(p_ml), cheap6_profile=cheap6(p_prof), mean_price=round(float(actual.mean()), 1))
print('Back-test, last 60 days (observed weather):', test)

# 5) Train on everything and forecast
m = model().fit(X, y)
ahead = pd.date_range(last_known + pd.Timedelta(hours=1), pd.Timestamp(today + dt.timedelta(days=10), tz='UTC') + pd.Timedelta(hours=23), freq='h')
Xa = features(ahead).dropna()
pa = pd.Series(m.predict(Xa), index=Xa.index).round(2)
out = {'time': [t.strftime('%Y-%m-%dT%H:00Z') for t in pa.index], 'eur_mwh': pa.tolist(), 'test': test,
       'created': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
json.dump(out, open(config.path('price_forecast.json'), 'w'))
print('Price forecast', out['time'][0], '->', out['time'][-1], '| mean', round(pa.mean(), 1), 'EUR/MWh')
