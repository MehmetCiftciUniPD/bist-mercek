"""Broker scorecard: how brokers' stop-loss trade ideas actually played out.

Takes every idea with an entry/reference price, a target and a stop from
data/broker-calls.json (Paratic) and data/foreks-reports.json (Foreks), keeps
them in data/broker-scorecard.json so the record outlives the 60-day source
windows, and checks each one against Yahoo Finance daily highs and lows from
its publication day:
- 'hedef'  the first target was reached before the stop;
- 'stop'   the stop was reached first;
- 'belirsiz' a day touched both and daily bars cannot tell which came first
           (left out of the hit rate);
- 'süre'   neither within the horizon (10 trading days for short-term ideas,
           30 for medium-term ones); result is the close on the last day;
- 'açık'   the horizon has not passed yet.
Results are in % from the reference price, without costs. An idea whose
reference price is more than 15% from that day's close is skipped as a likely
misread or unadjusted price. When the broker's own report closes an idea
(İş Yatırım's ledger, Şeker Yatırım's list), that record is used instead.
"""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'broker-scorecard.json'
CHART = 'https://query1.finance.yahoo.com/v8/finance/chart/{}.IS?range=6mo&interval=1d'
ISTANBUL = timezone(timedelta(hours=3))
HORIZON = {'kısa': 10, 'orta': 30, 'uzun': 60}


def load(name, default):
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else default


def daily(code):
    request = Request(CHART.format(code), headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as r:
                result = json.load(r)['chart']['result'][0]
            q = result['indicators']['quote'][0]
            rows = []
            for t, h, l, c in zip(result['timestamp'], q['high'], q['low'], q['close']):
                if None not in (h, l, c):
                    rows.append((datetime.fromtimestamp(t, ISTANBUL).strftime('%Y-%m-%d'), h, l, c))
            time.sleep(0.3)
            return rows
        except (OSError, KeyError, IndexError, TypeError, ValueError):
            time.sleep(2 * (attempt + 1))
    return None


def collect():
    ideas = {}
    calls = load('broker-calls.json', {'ideas': {}})
    for url, art in calls['ideas'].items():
        for x in art['rows']:
            if x.get('stop') is not None and x.get('targets') and x.get('entry'):
                ideas[f"{x['broker']}|{x['code']}|{art['date']}|{x['entry']}"] = {
                    'broker': x['broker'], 'code': x['code'], 'date': art['date'], 'entry': x['entry'], 'target': x['targets'][0],
                    'stop': x['stop'], 'side': 'AL', 'horizon': 'kısa', 'url': url, 'via': 'Paratic'}
    foreks = load('foreks-reports.json', {'ideas': {}})
    for rep in foreks['ideas'].values():
        for x in rep['rows']:
            day = x.get('since') or rep['date']
            if x.get('stop') is not None and x.get('targets') and x.get('entry') and day:
                ideas[f"{rep['broker']}|{x['code']}|{day}|{x['entry']}"] = {
                    'broker': rep['broker'], 'code': x['code'], 'date': day, 'entry': x['entry'], 'target': x['targets'][0],
                    'stop': x['stop'], 'side': x.get('side', 'AL'), 'horizon': x.get('horizon') or 'kısa', 'url': rep['url'], 'via': 'Foreks',
                    'record': {k: x[k] for k in ('status', 'exit', 'result', 'exitDate') if x.get(k) is not None} or None}
    return ideas


def judge(idea, bars, today):
    up = idea['side'] != 'SAT'
    if (idea['target'] > idea['entry']) != up or (idea['stop'] < idea['entry']) != up:
        return {'outcome': 'geçersiz'}
    days = [b for b in bars if b[0] >= idea['date']]
    if not days:
        return {'outcome': 'açık', 'days': 0}
    if abs(days[0][3] / idea['entry'] - 1) > 0.15:
        return {'outcome': 'geçersiz'}
    limit = HORIZON.get(idea['horizon'], 10)
    sign = 1 if up else -1
    pct = lambda price: round((price / idea['entry'] - 1) * 100 * sign, 2)
    for n, (d, high, low, close) in enumerate(days[:limit], start=1):
        hit_stop = low <= idea['stop'] if up else high >= idea['stop']
        hit_target = high >= idea['target'] if up else low <= idea['target']
        if hit_stop and hit_target:
            return {'outcome': 'belirsiz', 'days': n, 'end': d}
        if hit_stop:
            return {'outcome': 'stop', 'days': n, 'end': d, 'result': pct(idea['stop'])}
        if hit_target:
            return {'outcome': 'hedef', 'days': n, 'end': d, 'result': pct(idea['target'])}
    if len(days) >= limit:
        d, _, _, close = days[limit - 1]
        return {'outcome': 'süre', 'days': limit, 'end': d, 'result': pct(close)}
    return {'outcome': 'açık', 'days': len(days), 'result': pct(days[-1][3])}


def main():
    old = load('broker-scorecard.json', {'ideas': {}})
    ideas = old['ideas']
    def repeat_of(idea):
        # Running lists repeat an open idea daily ("devam eden"): keep the first publication.
        for k, x in ideas.items():
            if (x['broker'], x['code'], x['entry'], x['target'], x['stop']) == (idea['broker'], idea['code'], idea['entry'], idea['target'], idea['stop']) \
                    and x['date'] < idea['date'] <= (datetime.fromisoformat(x['date']) + timedelta(days=21)).strftime('%Y-%m-%d'):
                return k
        return None

    for key, idea in sorted(collect().items(), key=lambda kv: kv[1]['date']):
        record = idea.pop('record', None)
        key = repeat_of(idea) or key
        ideas.setdefault(key, idea)
        if record and record.get('status') == 'kapalı' and record.get('result') is not None:
            x = ideas[key]
            up = x['side'] != 'SAT'
            exit_ = record.get('exit')
            outcome = 'hedef' if exit_ is not None and (exit_ >= x['target'] if up else exit_ <= x['target']) else \
                'stop' if exit_ is not None and (exit_ <= x['stop'] if up else exit_ >= x['stop']) else 'süre'
            x.update(outcome=outcome, result=record['result'], end=record.get('exitDate'), by='kurum')
    today = datetime.now(ISTANBUL).strftime('%Y-%m-%d')
    todo = sorted({x['code'] for x in ideas.values() if x.get('outcome') in (None, 'açık')})
    bars = {}
    for code in todo:
        rows = daily(code)
        if rows:
            bars[code] = rows
    for idea in ideas.values():
        if idea.get('outcome') in (None, 'açık') and idea['code'] in bars and idea.get('by') != 'kurum':
            idea.update(judge(idea, bars[idea['code']], today))
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=365)).strftime('%Y-%m-%d')
    ideas = {k: v for k, v in ideas.items() if v['date'] >= cutoff}
    brokers = {}
    for x in ideas.values():
        if x.get('outcome') in (None, 'geçersiz'):
            continue
        b = brokers.setdefault(x['broker'], {'n': 0, 'hedef': 0, 'stop': 0, 'süre': 0, 'açık': 0, 'belirsiz': 0, 'results': [], 'days': []})
        b['n'] += 1
        b[x['outcome']] += 1
        if x['outcome'] in ('hedef', 'stop', 'süre') and x.get('result') is not None:
            b['results'].append(x['result'])
            if x.get('days'):
                b['days'].append(x['days'])
    for b in brokers.values():
        closed = b['hedef'] + b['stop'] + b['süre']
        b['hit'] = round(b['hedef'] / closed * 100, 1) if closed else None
        b['avg'] = round(sum(b['results']) / len(b['results']), 2) if b['results'] else None
        b['avgDays'] = round(sum(b['days']) / len(b['days']), 1) if b['days'] else None
        del b['results'], b['days']
    OUT.write_text(json.dumps({'generatedAt': datetime.now(ISTANBUL).isoformat(timespec='minutes'), 'source': 'Yahoo Finance günlük fiyatlar',
                               'brokers': dict(sorted(brokers.items(), key=lambda kv: -kv[1]['n'])), 'ideas': ideas},
                              ensure_ascii=False, indent=1) + '\n')
    counts = {}
    for x in ideas.values():
        counts[x.get('outcome')] = counts.get(x.get('outcome'), 0) + 1
    print(f'{len(ideas)} öneri · {len(brokers)} kurum · {counts}')


if __name__ == '__main__':
    main()
