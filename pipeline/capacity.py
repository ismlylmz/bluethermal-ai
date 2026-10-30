"""Seawater heat pump capacity from intake temperature and salinity.

Heat taken from the sea = flow x density x cp x (intake - minimum outlet temperature).
The minimum outlet temperature is the salinity-dependent freezing point plus a margin.
Delivered heat = heat from sea x COP / (COP - 1), capped at nominal output.
Defaults follow Esbjerg's published values (70 MW, 14 000 m3/h, COP 2.8 at 3.3 degC).
"""
import sys
import pandas as pd
import config

RHO, CP = 1006.0, 4.0  # kg/m3 for brackish Baltic water, kJ/kgK
PLANT = dict(flow_m3h=14000, nominal_mw=70, margin_c=1.0, max_drop_c=3.0, cop_ref=2.8, t_ref=3.3, supply_c=75.0)


def freezing_point(sal):
    """Freezing point of seawater (degC), UNESCO 1983, surface pressure."""
    return -0.0575 * sal + 1.710523e-3 * sal ** 1.5 - 2.154996e-4 * sal ** 2


def cop(t_in, p=PLANT):
    """COP scaled with the Carnot ratio so that COP(t_ref) = cop_ref."""
    carnot = lambda t: (p['supply_c'] + 5 + 273.15) / (p['supply_c'] + 5 - (t - 5))
    return p['cop_ref'] * carnot(t_in) / carnot(p['t_ref'])


def capacity(t_in, sal, p=PLANT):
    """Return (heat MW, electricity MW, COP)."""
    drop = max(0.0, min(p['max_drop_c'], t_in - (freezing_point(sal) + p['margin_c'])))
    sea_mw = p['flow_m3h'] / 3600 * RHO * CP * drop / 1000
    c = cop(t_in, p)
    heat = min(p['nominal_mw'], sea_mw * c / (c - 1))
    return heat, heat / c, c


if __name__ == '__main__':
    heat, _, c = capacity(3.3, 30, dict(PLANT, margin_c=2.0, max_drop_c=99, nominal_mw=999))
    print(f'Esbjerg check: {heat:.0f} MW, COP {c:.2f} (published: 70 MW, COP 2.8)')
    for t in (2.0, 2.5, 3.0, 4.0, 5.0):
        print(f'  intake {t:.1f} C -> {capacity(t, 8.6)[0]:5.1f} MW')
    m = pd.read_csv(config.path('site_corrected.csv'), parse_dates=['date']).dropna(subset=['corrected'])
    m = m[m.date.dt.month.isin([12, 1, 2, 3, 4]) & m.depth.isin([60, 70])]
    m['winter'] = m.date.map(lambda d: f'{config.winter_of(d)}-{config.winter_of(d) + 1}')
    for col in ('model', 'corrected'):
        m[f'mw_{col}'] = [capacity(t, s)[0] for t, s in zip(m[col], m.model_sal)]
    rows = []
    for (z, w), g in m.groupby(['depth', 'winter']):
        rows.append(dict(depth=z, winter=w, days=len(g),
                         low_days_raw=int((g.mw_model < 0.8 * PLANT['nominal_mw']).sum()),
                         low_days_corrected=int((g.mw_corrected < 0.8 * PLANT['nominal_mw']).sum()),
                         backup_mwh_raw=round((PLANT['nominal_mw'] - g.mw_model).clip(lower=0).sum() * 24),
                         backup_mwh_corrected=round((PLANT['nominal_mw'] - g.mw_corrected).clip(lower=0).sum() * 24)))
    out = pd.DataFrame(rows)
    out.to_csv(config.path('capacity_summary.csv'), index=False)
    print(out.to_string(index=False))
