"""Build the static public site (site/dist) from the committed data snapshots.

site/page.html is the page body; this script wraps it in a document and writes
data.json and analyses.json next to it. Nothing here needs a key or a server.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = ROOT / 'site' / 'dist'
SNAP = ['assets', 'currentAssets', 'noncurrentAssets', 'currentLiabilities', 'noncurrentLiabilities', 'equity', 'parentEquity',
        'deposits', 'revenue', 'operating', 'pretax', 'netIncome', 'groupNetIncome', 'netInterest', 'netFees']
HEAD = ('<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        '<link rel="manifest" href="manifest.webmanifest"><meta name="theme-color" content="#0b5c6e">'
        '<link rel="icon" href="icon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="icon-192.png">'
        '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Bilanço">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style></head><body>')


def load(name):
    return json.loads((DATA / name).read_text())


def at_or_before(series, day):
    """Close of the last bar on or before day, or None."""
    best = None
    for d, c in zip(series['d'], series['c']):
        if d > day:
            break
        best = c
    return best


def performance(series, marks):
    """One-year return in TL, in dollars and against BIST 100, from weekly closes."""
    end, start = series['d'][-1], series['d'][-1] - 364
    if series['d'][0] > start + 7:
        return None
    p0, p1 = at_or_before(series, start), series['c'][-1]
    u0, u1 = at_or_before(marks['USDTRY'], start), at_or_before(marks['USDTRY'], end)
    x0, x1 = at_or_before(marks['XU100'], start), at_or_before(marks['XU100'], end)
    if not all((p0, u0, u1, x0, x1)):
        return None
    return {'tl': round(p1 / p0 - 1, 4), 'usd': round((p1 / u1) / (p0 / u0) - 1, 4), 'rel': round((p1 / p0) / (x1 / x0) - 1, 4)}


def companies():
    # The dated snapshot belongs to the Mercek app; the public site prefers the refreshed one.
    latest = 'market-latest.json' if (DATA / 'market-latest.json').exists() else 'market-2026-11-09.json'
    uni, hist, market = load('kap-universe.json'), load('history.json'), load(latest)
    sources = (('KAP tam rapor', load('research-2026-09.json')), ('KAP özeti', load('kap-summary-2026-09.json')),
               ('İş Yatırım şirket kartı', load('broker-summary-2026-09.json')))
    quotes = {q['code']: q for q in market['companies']}
    scorecard = load('scorecard.json') if (DATA / 'scorecard.json').exists() else {'companies': {}}
    smc = load('smc-summary.json')['companies'] if (DATA / 'smc-summary.json').exists() else {}
    weekly = load('price-history.json')['companies'] if (DATA / 'price-history.json').exists() else {}
    marks = load('benchmarks.json')['series'] if (DATA / 'benchmarks.json').exists() else None
    buybacks = load('buybacks.json') if (DATA / 'buybacks.json').exists() else {'items': {}, 'since': None}
    by_code = {}
    for index, item in buybacks['items'].items():
        for c in item['codes']:
            by_code.setdefault(c, []).append({'k': item['kind'], 'd': item['date'], 's': item['summary'], 'u': item['url'], 'r': item.get('ratio'), 'cap': item.get('cap')})
    transfers = load('fund-transfers.json')['items'] if (DATA / 'fund-transfers.json').exists() else {}
    ft_by_code = {}
    for index, item in transfers.items():
        entry = {k: item.get(k) for k in ('kind', 'buyer', 'date', 'price', 'amount', 'amountCalc', 'shares', 'ratio', 'url', 'offExchange', 'targets')}
        entry['text'] = item.get('text', '')[:900]
        ft_by_code.setdefault(item['codes'][0], []).append(entry)
        for target in item.get('targets', []):
            ft_by_code.setdefault(target, []).append({**entry, 'via': item['codes'][0]})
    trades = load('insider-trades.json')['items'] if (DATA / 'insider-trades.json').exists() else {}
    ins_by_code = {}
    for index, item in trades.items():
        for row in item['rows']:
            entry = {'date': row['date'], 'buy': row['buy'], 'sell': row['sell'], 'endPct': row.get('endPct'),
                     'who': item.get('who') or '', 'role': item.get('role') or '', 'price': item.get('price'),
                     'url': item['url'], 'off': item.get('offExchange', False), 'text': (item.get('text') or '')[:300]}
            for code in item.get('targets') or item['codes'][:1]:
                ins_by_code.setdefault(code, []).append(entry)
    summary = load('daily-summary.json') if (DATA / 'daily-summary.json').exists() else None
    holdings = load('fund-holdings.json') if (DATA / 'fund-holdings.json').exists() else {'companies': {}}
    events = load('market-events.json')['events'] if (DATA / 'market-events.json').exists() else {}
    ev_by_code = {}
    for index, item in events.items():
        for code in item.get('codes', []):
            ev_by_code.setdefault(code, []).append(item)
    spk = load('spk-actions.json') if (DATA / 'spk-actions.json').exists() else {'actions': []}
    spk_by_code = {}
    for a in spk['actions']:
        spk_by_code.setdefault(a['code'], []).append({k: a.get(k) for k in ('bulletin', 'date', 'type', 'persons', 'ban', 'text', 'url')})
    latest_day = max((v.get('date') or '') for v in events.values())[:10] if events else ''
    risk = load('risk-flags.json') if (DATA / 'risk-flags.json').exists() else {'flags': {}}
    brokers = load('broker-reports.json') if (DATA / 'broker-reports.json').exists() else {}
    calls = load('broker-calls.json') if (DATA / 'broker-calls.json').exists() else {'targets': {}, 'ideas': {}}
    tg_day = max(calls['targets'], default=None)
    tg_by_code = {}
    for t in (calls['targets'][tg_day]['rows'] if tg_day else []):
        tg_by_code.setdefault(t['code'], []).append({'b': t['broker'], 't': t.get('target'), 'r': (t.get('rec') or '').rstrip('*') or None, 'p': t.get('prev')})
    idea_by_code = {}
    for url, art in calls['ideas'].items():
        for x in art['rows']:
            idea_by_code.setdefault(x['code'], []).append({'b': x['broker'], 'd': art['date'], 'e': x['entry'], 's': x['stop'], 't': x['targets'], 'sp': x['supports'], 'u': url, 'via': 'Paratic'})
    foreks = load('foreks-reports.json') if (DATA / 'foreks-reports.json').exists() else {'items': {}, 'ideas': {}}
    for rep in foreks['ideas'].values():
        for x in rep['rows']:
            idea = {'b': rep['broker'], 'd': x.get('since') or rep['date'], 'e': x['entry'], 's': x['stop'], 't': x['targets'], 'sp': x['supports'],
                    'u': rep['url'], 'via': 'Foreks'}
            for k_in, k_out in (('status', 'st'), ('result', 'res'), ('exit', 'x'), ('exitDate', 'xd'), ('horizon', 'h')):
                if x.get(k_in) is not None:
                    idea[k_out] = x[k_in]
            idea_by_code.setdefault(x['code'], []).append(idea)
    # The same idea is repeated in daily reports: keep the newest copy (latest status).
    for code, lst in idea_by_code.items():
        seen = {}
        for x in sorted(lst, key=lambda x: (x['d'] or '', x.get('st') == 'kapalı')):
            seen[((x['b'] or '').lower(), x['d'], x['e'], x['s'])] = x
        idea_by_code[code] = list(seen.values())
    karne = load('broker-scorecard.json') if (DATA / 'broker-scorecard.json').exists() else {'ideas': {}, 'brokers': {}}
    judged = {(x['broker'], x['code'], x['date'], x['entry']): x for x in karne['ideas'].values()}
    for code, lst in idea_by_code.items():
        for x in lst:
            j = judged.get((x['b'], code, x['d'], x['e']))
            if j and j.get('outcome') not in (None, 'açık', 'geçersiz'):
                x['o'] = j['outcome']
                if j.get('result') is not None:
                    x['or'] = j['result']
                if j.get('end'):
                    x['oe'] = j['end']
    foreign = load('foreign-ratios.json') if (DATA / 'foreign-ratios.json').exists() else {'days': {}, 'movers': {}}
    fdays = sorted(foreign['days'])
    streak_of = {x['c']: (d, x) for d in ('up', 'down') for x in foreign.get('movers', {}).get('streaks', {}).get(d, [])}
    week_of = {x['c']: x for side in ('up', 'down') for x in foreign.get('movers', {}).get('week', {}).get(side, [])}

    def foreign_row(code):
        if not fdays or code not in foreign['days'][fdays[-1]]:
            return None
        now = foreign['days'][fdays[-1]][code]
        out = {'now': now}
        back = [d for d in fdays if d <= (datetime.fromisoformat(fdays[-1]) - timedelta(days=7)).strftime('%Y-%m-%d')]
        if len(fdays) > 1 and code in foreign['days'][fdays[-2]]:
            out['d1'] = round(now - foreign['days'][fdays[-2]][code], 2)
        if back and code in foreign['days'][back[-1]]:
            out['w'] = round(now - foreign['days'][back[-1]][code], 2)
        elif code in week_of:
            out['w'] = week_of[code]['chg']
        if code in streak_of:
            direction, x = streak_of[code]
            out['streak'] = x['days'] * (1 if direction == 'up' else -1)
            if 'd1' not in out and len(x['hist']) > 1:
                out['d1'] = round(x['hist'][0] - x['hist'][1], 2)
            if 'w' not in out and len(x['hist']) > 5:
                out['w'] = round(x['hist'][0] - x['hist'][5], 2)
        return out

    takas = load('takas.json') if (DATA / 'takas.json').exists() else {'days': {}}
    tk_day = max(takas['days'], default=None)
    flows = load('foreign-flows.json') if (DATA / 'foreign-flows.json').exists() else {'weeks': {}}
    reports_by_code = {}
    for doc in foreks['items'].values():
        for c in doc.get('codes', []):
            reports_by_code.setdefault(c, []).append({'t': doc['title'], 'b': doc['broker'], 'd': doc['date'], 'u': doc['url']})
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    report_feed = sorted(({'t': d['title'], 'b': d['broker'], 'd': d['date'], 'u': d['url'], 'c': d.get('codes', [])}
                          for d in foreks['items'].values() if d['title'].upper().startswith('ANAL') and (d.get('date') or '') >= week_ago),
                         key=lambda x: x['d'] or '', reverse=True)
    rows = []
    for issuer in uni['companies']:
        codes = issuer['codes']
        code = max(codes, key=lambda c: quotes.get(c, {}).get('marketCap') or -1)
        q = quotes.get(code, {})
        row = {'c': code, 'n': issuer['name'], 'sn': q.get('name'), 's': q.get('sector'), 'seg': issuer['segments'],
               'kap': issuer['kapProfile'], 'px': q.get('price'), 'mc': q.get('marketCap'), 'pe': q.get('pe'),
               'pb': q.get('pb'), 'ytd': q.get('ytdReturn'), 'wk': q.get('weekReturn'), 'mo': q.get('monthReturn')}
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
        if code in smc:
            row['smc'] = smc[code]
        series = weekly.get(code)
        if series:
            last = series['d'][-1]
            year = [c for d, c in zip(series['d'], series['c']) if d > last - 365]
            if len(year) >= 40:
                row['hi52'] = max(year)
            if marks:
                perf = performance(series, marks)
                if perf:
                    row['perf'] = perf
        bb = sorted((x for c in codes for x in by_code.get(c, [])), key=lambda x: x['d'], reverse=True)
        if bb:
            row['bb'] = bb[:12]
            # Ratios that never fall over time are cumulative holdings; otherwise they may be daily amounts.
            ratios = [x['r'] for x in sorted(bb, key=lambda x: x['d']) if x.get('r') is not None]
            row['bbCum'] = len(ratios) >= 2 and all(b >= a - 0.01 for a, b in zip(ratios, ratios[1:]))
            cap = next((x['cap'] for x in bb if x.get('cap')), None)
            if cap and q.get('price') and q.get('marketCap'):
                shares = q['marketCap'] * 1e6 / q['price']
                row['bbCapPct'] = round(cap / shares * 100, 3)
            if series:
                first = min(x['d'] for x in bb)[:10]
                day = (datetime.fromisoformat(first) - datetime(1970, 1, 1)).days
                price = at_or_before(series, day)
                if price:
                    row['bbFrom'] = {'d': first, 'p': price}
            row['bbn'] = len(bb)
            ratio = next((x['r'] for x in bb if x.get('r') is not None), None)
            if ratio is not None:
                row['bbr'] = ratio
        ft = sorted((x for c in codes for x in ft_by_code.get(c, [])), key=lambda x: x['date'], reverse=True)
        if ft:
            row['ft'] = ft[:8]
        # The same trade is often filed by the insider and by the company; keep one.
        unique = {}
        for x in sorted((x for c in codes for x in ins_by_code.get(c, [])), key=lambda x: not x['who']):
            unique.setdefault((x['date'], x['buy'], x['sell'], x.get('endPct')), x)
        trades_here = sorted(unique.values(), key=lambda x: x['date'], reverse=True)
        if trades_here:
            row['ins'] = trades_here[:10]
            row['insN'] = len(trades_here)
        held = next((holdings['companies'][c] for c in codes if c in holdings['companies']), None)
        if held:
            row['fh'] = {k: held.get(k) for k in ('capital', 'floatRatio', 'funds', 'lots', 'value', 'floatShareBefore')}
        evs = [x for c in codes for x in ev_by_code.get(c, [])]
        if evs and latest_day:
            d30 = (datetime.fromisoformat(latest_day) - timedelta(days=30)).strftime('%Y-%m-%d')
            cb = sorted(x['date'][:10] for x in evs if x['kind'] == 'cb')
            if cb:
                row['cb'] = {'n30': sum(1 for d in cb if d >= d30), 'n': len(cb), 'last': cb[-1]}
            pick = lambda kind, n, keys: [{k: x.get(k) for k in keys} for x in sorted((x for x in evs if x['kind'] == kind), key=lambda x: x['date'], reverse=True)[:n]]
            for kind, keys in (('capital', ('date', 'type', 'bonusPct', 'rightsPct', 'summary', 'url')),
                               ('dividends', ('date', 'decision', 'grossPerShare', 'grossPct', 'summary', 'url')),
                               ('spk', ('date', 'summary', 'url')), ('funds3', ('date', 'holder', 'pct', 'url'))):
                got = pick(kind, 5, keys)
                if got:
                    row['ev_' + kind] = got
            reports = sorted((x for x in evs if x['kind'] == 'reports'), key=lambda x: x['date'], reverse=True)
            if reports:
                row['rep'] = {'date': reports[0]['date'][:10], 'year': reports[0].get('year'), 'period': reports[0].get('period'),
                              'rule': reports[0].get('rule'), 'url': reports[0]['url'], 'recent': [x['date'][:10] for x in reports[:3]]}
            ipo = [x for x in evs if x['kind'] == 'ipoResult']
            if ipo:
                first = min((x['date'][:10] for x in evs if x['kind'] == 'ipo'), default=ipo[0]['date'][:10])
                row['ipo'] = {'date': first, 'price': ipo[0].get('price'), 'url': ipo[0]['url']}
        if spk_by_code.get(code) or any(spk_by_code.get(c) for c in codes):
            row['spk'] = sorted((x for c in codes for x in spk_by_code.get(c, [])), key=lambda x: x['date'] or '', reverse=True)[:8]
        br = {k: v for k, v in (('isy', next((brokers.get('isy', {})[c] for c in codes if c in brokers.get('isy', {})), None)),
                                ('model', next((brokers.get('model', {})[c] for c in codes if c in brokers.get('model', {})), None)),
                                ('cons', next((brokers.get('consensus', {})[c] for c in codes if c in brokers.get('consensus', {})), None))) if v}
        if br:
            row['br'] = br
        tg = next((tg_by_code[c] for c in codes if c in tg_by_code), None)
        if tg:
            row['tg'] = tg
        ti = sorted((x for c in codes for x in idea_by_code.get(c, [])), key=lambda x: x['d'] or '', reverse=True)
        if ti:
            row['ti'] = ti[:10]
        fr = next((foreign_row(c) for c in codes if foreign_row(c)), None)
        if fr:
            row['fr'] = fr
        tk = next((takas['days'][d]['rows'][c] for d in sorted(takas['days'], reverse=True)[:5] for c in codes if c in takas['days'][d]['rows']), None)
        if tk:
            row['tk'] = {**tk, 'date': next(d for d in sorted(takas['days'], reverse=True) if any(c in takas['days'][d]['rows'] for c in codes))}
        rp = sorted((x for c in codes for x in reports_by_code.get(c, [])), key=lambda x: x['d'] or '', reverse=True)
        if rp:
            row['rp'] = rp[:8]
        flags = [f for c in codes for f in risk['flags'].get(c, [])]
        if flags:
            row['risk'] = flags
        rows.append(row)
    meta = {'priceDate': market['date'], 'priceFetchedAt': market.get('fetchedAt'), 'priceSource': market['source'], 'historySource': hist['source'],
            'collectedAt': hist['collectedAt'], 'note': hist['note'],
            'risk': {k: risk.get(k) for k in ('asOf', 'topic', 'note', 'levels', 'sources')},
            'buybackSince': buybacks.get('since'),
            'summary': summary,
            'eventsDay': latest_day,
            'broker': {k: brokers.get(k) for k in ('fetchedAt', 'sources', 'changes')} if brokers else None,
            'reports': report_feed,
            'karne': {'brokers': karne.get('brokers', {}), 'generatedAt': karne.get('generatedAt')},
            'foreign': {'date': foreign.get('date'), 'movers': {k: v for k, v in foreign.get('movers', {}).items() if k != 'streaks'},
                        'streakUp': len(foreign.get('movers', {}).get('streaks', {}).get('up', [])),
                        'streakDown': len(foreign.get('movers', {}).get('streaks', {}).get('down', []))},
            'takas': {'date': tk_day, 'url': takas['days'][tk_day]['url'] if tk_day else None,
                      'rows': takas['days'][tk_day]['rows'] if tk_day else {}},
            'flows': [{'week': w, **v['values']} for w, v in sorted(flows['weeks'].items())[-12:]],
            'health': load('health.json') if (DATA / 'health.json').exists() else None,
            'calls': {'targetsDate': tg_day, 'targetsUrl': calls['targets'][tg_day]['url'] if tg_day else None, 'fetchedAt': calls.get('fetchedAt')},
            'holdings': {k: holdings.get(k) for k in ('source', 'sourceUpdated', 'reports', 'note')}, 'universeDate': uni['date'], 'universeSource': uni['source']}
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
    # One small file per issuer, fetched only when its file is opened.
    prices = load('price-history.json')['companies'] if (DATA / 'price-history.json').exists() else {}
    (OUT / 'prices').mkdir(exist_ok=True)
    for old in (OUT / 'prices').glob('*.json'):
        old.unlink()
    for code, series in prices.items():
        (OUT / 'prices' / f'{code}.json').write_text(json.dumps(series, separators=(',', ':')))
    # Daily Smart Money files and the (uncommitted) delayed prices.
    # data/smc is not committed: when it is absent, publish-site.sh carries the
    # files over from the previously published site.
    if (DATA / 'smc').is_dir():
        (OUT / 'smc').mkdir(exist_ok=True)
        for old in (OUT / 'smc').glob('*.json'):
            old.unlink()
        for path in (DATA / 'smc').glob('*.json'):
            (OUT / 'smc' / path.name).write_text(path.read_text())
    for path in (ROOT / 'site' / 'static').glob('*'):
        (OUT / path.name).write_bytes(path.read_bytes())
    if (DATA / 'benchmarks.json').exists():
        (OUT / 'benchmarks.json').write_text((DATA / 'benchmarks.json').read_text())
    live = DATA / 'live.json'
    (OUT / 'live.json').write_text(live.read_text() if live.exists() else '{}')
    print(f"{len(data['companies'])} şirket · {len(prices)} fiyat serisi · {len(list((OUT / 'smc').glob('*.json')))} SMC · site/dist yazıldı")


if __name__ == '__main__':
    main()
