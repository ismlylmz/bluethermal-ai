"""Compare the Copernicus model with Keri measurements and correct the site series.

Correction: the model error measured at Keri on a given day is subtracted from the site model that day.
Writes data/site_corrected.csv and data/winter_summary.csv."""
import pandas as pd
import config

k = pd.read_csv(config.path('keri_table.csv'), parse_dates=['date'])
s = pd.read_csv(config.path('site_table.csv'), parse_dates=['date'])
k['error'] = k.model - k.obs
k['winter'] = k.date.map(config.winter_of)
rows = []
for (z, w), g in k[k.winter.notna()].dropna(subset=['obs']).groupby(['depth', 'winter']):
    rows.append(dict(place='Keri', depth=z, winter=f'{int(w)}-{int(w) + 1}', days=len(g),
                     cold_obs=int((g.obs < config.COLD_LIMIT).sum()), cold_model=int((g.model < config.COLD_LIMIT).sum()),
                     min_obs=round(g.obs.min(), 2), min_model=round(g.model.min(), 2),
                     bias=round(g.error.mean(), 2), rmse=round((g.error ** 2).mean() ** 0.5, 2)))

m = s.merge(k[['date', 'depth', 'error']], on=['date', 'depth'], how='left')
m['corrected'] = m.model - m.error
m['winter'] = m.date.map(config.winter_of)
for (z, w), g in m[m.winter.notna()].dropna(subset=['corrected']).groupby(['depth', 'winter']):
    rows.append(dict(place='Site', depth=z, winter=f'{int(w)}-{int(w) + 1}', days=len(g),
                     cold_corrected=int((g.corrected < config.COLD_LIMIT).sum()), cold_model=int((g.model < config.COLD_LIMIT).sum()),
                     min_corrected=round(g.corrected.min(), 2), min_model=round(g.model.min(), 2)))

summary = pd.DataFrame(rows)
summary.to_csv(config.path('winter_summary.csv'), index=False)
m.drop(columns='winter').to_csv(config.path('site_corrected.csv'), index=False)
pd.set_option('display.width', 200)
print(summary.fillna('').to_string(index=False))
