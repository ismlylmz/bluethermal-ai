"""Build the dashboard: template + static.json + live.json (+ price_forecast.json) -> docs/index.html."""
import os, json
import config

html = open(config.TEMPLATE, encoding='utf-8').read()
static = open(config.path('static.json'), encoding='utf-8').read()
live = json.load(open(config.path('live.json'), encoding='utf-8'))
if os.path.exists(config.path('price_forecast.json')):
    live['price_ml'] = json.load(open(config.path('price_forecast.json'), encoding='utf-8'))
json.loads(static)
html = html.replace('/*STATIC*/null', static).replace('/*LIVE*/null', json.dumps(live))
if not html.lstrip().lower().startswith('<!doctype'):
    html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>\n'
            + html + '\n</html>\n')
os.makedirs(os.path.dirname(config.OUTPUT), exist_ok=True)
open(config.OUTPUT, 'w', encoding='utf-8').write(html)
print('Dashboard written:', config.OUTPUT, round(len(html) / 1e3), 'kB')
