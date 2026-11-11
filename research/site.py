"""Build the static public site (site/dist) from the committed data snapshots.

site/page.html is the page body; this script wraps it in a document and writes
data.json and analyses.json next to it. Nothing here needs a key or a server.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = ROOT / 'site' / 'dist'
SNAP = ['assets', 'currentAssets', 'noncurrentAssets', 'currentLiabilities', 'noncurrentLiabilities', 'equity', 'parentEquity',
        'deposits', 'revenue', 'operating', 'pretax', 'netIncome', 'groupNetIncome', 'netInterest', 'netFees']
HEAD = ('<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style></head><body>')


def load(name):
    return json.loads((DATA / name).read_text())


def companies():
    uni, hist, market = load('kap-universe.json'), load('history.json'), load('market-2026-11-09.json')
    sources = (('KAP tam rapor', load('research-2026-09.json')), ('KAP özeti', load('kap-summary-2026-09.json')),
               ('İş Yatırım şirket kartı', load('broker-summary-2026-09.json')))
    quotes = {q['code']: q for q in market['companies']}
    scorecard = load('scorecard.json') if (DATA / 'scorecard.json').exists() else {'companies': {}}
    risk = load('risk-flags.json') if (DATA / 'risk-flags.json').exists() else {'flags': {}}
    rows = []
    for issuer in uni['companies']:
        codes = issuer['codes']
        code = max(codes, key=lambda c: quotes.get(c, {}).get('marketCap') or -1)
        q = quotes.get(code, {})
        row = {'c': code, 'n': issuer['name'], 'sn': q.get('name'), 's': q.get('sector'), 'seg': issuer['segments'],
               'kap': issuer['kapProfile'], 'px': q.get('price'), 'mc': q.get('marketCap'), 'pe': q.get('pe'),
               'pb': q.get('pb'), 'ytd': q.get('ytdReturn')}
        if len(codes) > 1:
            row['alt'] = [c for c in codes if c != code]
        for label, src in sources:
            rec = next((src[f'{c}:2026/9'] for c in codes if f'{c}:2026/9' in src), None)
            if rec:
                row['snap'] = {'prov': label, 'basis': rec.get('basis'), 'src': rec.get('source'),
                               'v': {k: rec[k] for k in SNAP if isinstance(rec.get(k), (int, float))},
                               'prev': {k: v for k, v in (rec.get('previous') or {}).items() if k in SNAP and isinstance(v, (int, float))}}
                break
        h = next((hist['companies'][c] for c in codes if c in hist['companies']), None)
        if h:
            row['h'] = {'g': h['group'], 'basis': h['basis'], 'src': h['source'], 'p': h['periods'], 'v': h['values']}
            if h.get('warnings'):
                row['h']['w'] = h['warnings']
        card = next((scorecard['companies'][c] for c in codes if c in scorecard['companies']), None)
        if card:
            row['sc'] = card
        flags = [f for c in codes for f in risk['flags'].get(c, [])]
        if flags:
            row['risk'] = flags
        rows.append(row)
    meta = {'priceDate': market['date'], 'priceSource': market['source'], 'historySource': hist['source'],
            'collectedAt': hist['collectedAt'], 'note': hist['note'],
            'risk': {k: risk.get(k) for k in ('asOf', 'topic', 'note', 'levels', 'sources')}, 'universeDate': uni['date'], 'universeSource': uni['source']}
    return {'meta': meta, 'companies': rows}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    compact = dict(ensure_ascii=False, separators=(',', ':'))
    data = companies()
    (OUT / 'data.json').write_text(json.dumps(data, **compact))
    analyses = DATA / 'ai-analyses.json'
    (OUT / 'analyses.json').write_text(analyses.read_text() if analyses.exists() else '{}')
    (OUT / 'index.html').write_text(HEAD + (ROOT / 'site' / 'page.html').read_text() + '</body></html>')
    (OUT / '.nojekyll').write_text('')
    print(f"{len(data['companies'])} şirket · site/dist yazıldı")


if __name__ == '__main__':
    main()
