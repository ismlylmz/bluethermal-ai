"""Shared paths and constants for the BlueThermal pipeline."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get('BT_DATA', os.path.join(ROOT, 'data'))
ARCHIVE = os.environ.get('BT_ARCHIVE', os.path.join(DATA, 'forecast_archive'))
TEMPLATE = os.environ.get('BT_TEMPLATE', os.path.join(ROOT, 'web', 'template.html'))
OUTPUT = os.environ.get('BT_OUTPUT', os.path.join(ROOT, 'docs', 'index.html'))

DEPTHS = (20, 40, 60, 70)
COLD_LIMIT = 3.0  # degC, intake temperature below which seawater heat pumps lose capacity

# Copernicus Marine datasets
MODEL_DATASET = 'cmems_mod_bal_phy_anfc_P1D-m'
INSITU_DATASET = 'cmems_obs-ins_bal_phybgcwav_mynrt_na_irr'
KERI_PLATFORM = 'KeriCable'

# Areas (lon/lat boxes)
KERI_BOX = dict(minimum_longitude=24.95, maximum_longitude=25.08, minimum_latitude=59.68, maximum_latitude=59.75)
SITE_BOX = dict(minimum_longitude=24.6, maximum_longitude=24.8, minimum_latitude=59.55, maximum_latitude=59.65)
ARCHIVE_BOX = dict(minimum_longitude=24.6, maximum_longitude=25.1, minimum_latitude=59.55, maximum_latitude=59.75)
SEL = {'keri': dict(latitude=slice(59.68, 59.75), longitude=slice(24.95, 25.08)),
       'site': dict(latitude=slice(59.55, 59.65), longitude=slice(24.6, 24.8))}


def path(name):
    return os.path.join(DATA, name)


def winter_of(d):
    """Winter label start year for Dec-Apr dates, else None."""
    if d.month in (12, 1, 2, 3, 4):
        return d.year if d.month == 12 else d.year - 1
    return None
