"""Daily market summary: facts from the data files plus a short free-model comment.

Facts are computed here from data already collected (prices, buybacks, fund
purchases, insider trades, Smart Money events). The comment is written by a
free OpenRouter model from those facts only; OPENROUTER_API_KEY comes from the
environment and is never stored. Without a key, or if the model fails, the
facts are kept and the comment is left empty. Output: data/daily-summary.json.
"""
import json
import os
import statistics
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
ISTANBUL = timezone(timedelta(hours=3))
MODELS = ['nvidia/nemotron-3-ultra-550b-a55b:free', 'nvidia/nemotron-3.5-super-vl:free']


def load(name, default=None):
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else default


def facts():
    market = load('market-latest.json') or load('market-2026-11-09.json')
    rows = [c for c in market['companies'] if isinstance(c.get('return'), (int, float))]
    day = market['date']
    since = (datetime.fromisoformat(day) - timedelta(days=6)).strftime('%Y-%m-%d')
    out = {'date': day, 'breadth': {'up': sum(c['return'] > 0 for c in rows), 'down': sum(c['return'] < 0 for c in rows),
                                    'flat': sum(c['return'] == 0 for c in rows),
                                    'median': round(statistics.median(c['return'] for c in rows), 2) if rows else None}}
    by_return = sorted(rows, key=lambda c: c['return'])
    out['gainers'] = [{'c': c['code'], 'r': c['return']} for c in by_return[::-1][:5]]
    out['losers'] = [{'c': c['code'], 'r': c['return']} for c in by_return[:5]]
    buybacks = load('buybacks.json', {'items': {}})['items'].values()
    recent = [b for b in buybacks if b['date'][:10] >= since and b['kind'] == 'islem']
    out['buybacks'] = {'notices': len(recent), 'companies': len({b['codes'][0] for b in recent})}
    fund = load('fund-transfers.json', {'items': {}})['items'].values()
    out['fundPurchases'] = sorted({(f.get('targets') or f['codes'])[0] for f in fund if f['kind'] == 'purchase' and f['date'][:10] >= since})
    trades = load('insider-trades.json', {'items': {}})['items'].values()
    net = {}
    for t in trades:
        code = (t.get('targets') or t['codes'])[0]
        for r in t['rows']:
            if r['date'] >= since:
                net[code] = net.get(code, 0) + (r['buy'] or 0) - (r['sell'] or 0)
    out['insiderBuyers'] = [c for c, v in sorted(net.items(), key=lambda kv: -kv[1]) if v > 0][:8]
    out['insiderSellers'] = [c for c, v in sorted(net.items(), key=lambda kv: kv[1]) if v < 0][:5]
    smc = load('smc-summary.json', {'companies': {}})['companies']
    epoch = datetime(1970, 1, 1)
    cutoff = (datetime.fromisoformat(since) - epoch).days
    out['choch'] = {'up': sorted(c for c, v in smc.items() if v.get('last') and v['last']['k'] == 'CHoCH' and v['last']['dir'] == 1 and v['last']['d'] >= cutoff),
                    'down': sorted(c for c, v in smc.items() if v.get('last') and v['last']['k'] == 'CHoCH' and v['last']['dir'] == -1 and v['last']['d'] >= cutoff)}
    return out


def comment(f):
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        return None, None
    prompt = '\n'.join([
        'Borsa İstanbul için kısa bir günlük piyasa özeti yaz. Türkçe, 120-180 kelime, 3-4 kısa paragraf ya da madde.',
        'YALNIZCA aşağıdaki verileri kullan; dışarıdan haber, rakam veya yorum ekleme. Al, sat önerisi verme.',
        'Konular: piyasanın genel yönü (yükselen/düşen sayısı), öne çıkan hisseler, şirketlerin geri alımları,',
        'tasfiyedeki fonlardan alımlar, yönetici/hakim ortak alımları ve yapı değişimi (CHoCH) sinyalleri.',
        '', 'VERİ (JSON):', json.dumps(f, ensure_ascii=False)])
    for model in MODELS:
        body = {'model': model, 'temperature': 0.2, 'max_tokens': 3000, 'reasoning': {'effort': 'low', 'exclude': True},
                'messages': [{'role': 'user', 'content': prompt}]}
        request = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', json.dumps(body).encode(),
                                         {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                reply = json.load(response)
        except OSError:
            continue
        choice = reply['choices'][0]
        text = (choice['message'].get('content') or '').strip()
        if choice.get('finish_reason') == 'stop' and len(text) > 200 and not reply.get('usage', {}).get('cost'):
            return text, reply.get('model') or model
    return None, None


def main():
    f = facts()
    text, model = comment(f)
    old = load('daily-summary.json')
    if not text and old and old.get('facts', {}).get('date') == f['date']:
        text, model = old.get('text'), old.get('model')
    (DATA / 'daily-summary.json').write_text(json.dumps({
        'generatedAt': datetime.now(ISTANBUL).isoformat(timespec='minutes'), 'facts': f, 'text': text, 'model': model},
        ensure_ascii=False, indent=1) + '\n')
    print(f"Özet {f['date']} · yorum {'var' if text else 'yok'}")


if __name__ == '__main__':
    main()
