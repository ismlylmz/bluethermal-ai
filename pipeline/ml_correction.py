"""ML error model: predict the Copernicus model error at Keri from model fields only, so it can run
where no station exists. Trained on one winter, tested on the other. Writes data/ml_summary.csv."""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
import config

k = pd.read_csv(config.path('keri_table.csv'), parse_dates=['date'])
s = pd.read_csv(config.path('site_table.csv'), parse_dates=['date'])


def features(t):
    w = t.pivot_table(index='date', columns='depth', values=['model', 'model_sal'])
    w.columns = [f'{a}_{b}' for a, b in w.columns]
    X = pd.DataFrame(index=w.index)
    for z in config.DEPTHS:
        X[f't{z}'] = w[f'model_{z}']
        X[f's{z}'] = w[f'model_sal_{z}']
    X['grad_40_60'] = X.t40 - X.t60
    X['grad_60_70'] = X.t60 - X.t70
    X['halocline'] = X.s70 - X.s20
    for z in (60, 70):
        X[f'trend7_{z}'] = X[f't{z}'].diff(7)
        X[f'mean30_{z}'] = X[f't{z}'].rolling(30, min_periods=10).mean()
    doy = X.index.dayofyear
    X['season_sin'] = np.sin(2 * np.pi * doy / 365.25)
    X['season_cos'] = np.cos(2 * np.pi * doy / 365.25)
    return X


def model():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=3, min_samples_leaf=20, random_state=0)


XK, XS = features(k), features(s)
rmse = lambda e: round(float(np.sqrt((e ** 2).mean())), 2)
rows, site_ml = [], {}
for z in (40, 60, 70):
    kz = k[k.depth == z].set_index('date')
    y = (kz.model - kz.obs).dropna()
    d = XK.loc[y.index].assign(y=y, winter=[config.winter_of(g) or -1 for g in y.index])
    winters = sorted(w for w in d.winter.unique() if w > 0)
    for test in winters:
        tr, te = d[d.winter != test], d[d.winter == test]
        m = model().fit(tr.drop(columns=['y', 'winter']), tr.y)
        p = m.predict(te.drop(columns=['y', 'winter']))
        o, r, bias = kz.obs.loc[te.index], kz.model.loc[te.index], tr.y.mean()
        rows.append(dict(depth=z, test_winter=f'{test}-{test + 1}', days=len(te),
                         rmse_raw=rmse(r - o), rmse_bias=rmse(r - bias - o), rmse_ml=rmse(r - p - o),
                         cold_obs=int((o < config.COLD_LIMIT).sum()), cold_raw=int((r < config.COLD_LIMIT).sum()),
                         cold_ml=int((r - p < config.COLD_LIMIT).sum())))
    m = model().fit(d.drop(columns=['y', 'winter']), d.y)
    xs = XS.dropna()
    site_ml[z] = pd.Series(XS.loc[xs.index, f't{z}'] - m.predict(xs), index=xs.index)

out = pd.DataFrame(rows)
out.to_csv(config.path('ml_summary.csv'), index=False)
pd.DataFrame(site_ml).rename(columns=lambda c: f'ml_{c}').rename_axis('date').to_csv(config.path('site_ml.csv'))
pd.set_option('display.width', 200)
print('Train on one winter, test on the other (Keri, Dec-Apr):')
print(out.to_string(index=False))
