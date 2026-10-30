"""Daily update: run every pipeline step in order and stop if live data or the dashboard build fails."""
import os, sys, subprocess, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = ['fetch_live.py', 'update_tables.py', 'price_forecast.py', 'validate.py', 'cold_week.py',
         'forecast_test.py', 'ml_correction.py', 'build_static.py', 'build_dashboard.py']
CRITICAL = {'fetch_live.py', 'build_dashboard.py'}

print('=' * 60)
print(dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'update started')
failed = False
for step in STEPS:
    r = subprocess.run([sys.executable, os.path.join(HERE, step)], capture_output=True, text=True)
    print(f'{step:20s} {"ok" if r.returncode == 0 else "FAILED"}')
    if r.returncode != 0:
        print(r.stderr[-2000:])
        failed = True
        if step in CRITICAL:
            sys.exit(1)
print('done' + (' with warnings' if failed else ''))
