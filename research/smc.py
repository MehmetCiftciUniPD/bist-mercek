"""Smart Money Concepts reading of one year of daily prices.

Writes data/smc/<code>.json (bars and zones for the chart) and
data/smc-summary.json (one line per issuer for the list). Definitions follow
the widely used open implementation by LuxAlgo ("Smart Money Concepts"):

- Swing points: a bar whose high (low) is the highest (lowest) of the SWING
  bars on each side; confirmed SWING bars later.
- Structure: a close above the last unbroken swing high is a bullish break.
  It is a CHoCH (change of character) when the prevailing structure was
  bearish, otherwise a BOS (break of structure). Mirror for bearish.
- Order block: on a bullish break, the bar with the lowest low between the
  broken swing high and the break; its range is the zone. It stays active
  until a later close falls below it. Mirror for bearish.
- Fair value gap: three bars where bar 3's low is above bar 1's high (bullish)
  or bar 3's high is below bar 1's low (bearish). Open until price trades
  through the far edge. Gaps smaller than 0.3 x ATR(14) are ignored.
- Liquidity: two swing highs (lows) within 0.1 x ATR(14) of each other form
  equal highs (lows); they stay open until price trades beyond them.
- Premium / discount: position of the last close inside the range between
  the latest swing high and swing low; above 52.5% is premium, below 47.5%
  discount, otherwise equilibrium.

Safeguards: the last daily close must match the official close in
market-latest.json within 3%, and a daily move beyond +25% / -25% (outside
BIST's price limits) is treated as an unadjusted split: bars before it are
dropped. Nothing is rescaled or estimated.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'smc'
API = 'https://query1.finance.yahoo.com/v8/finance/chart/{}.IS?range=1y&interval=1d'
SWING, ATR_N = 10, 14


def fetch(code):
    request = Request(API.format(code), headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 or attempt == 3:
                return None
            time.sleep(3 * (attempt + 1))
        except (OSError, ValueError, HTTPException):
            if attempt == 3:
                return None
            time.sleep(2 * (attempt + 1))


def bars(code, reference, reference_day):
    payload = fetch(code)
    result = (((payload or {}).get('chart') or {}).get('result') or [None])[0]
    if not result or (result.get('meta') or {}).get('currency') != 'TRY':
        return None, 'Yahoo günlük veri döndürmedi'
    q = (result.get('indicators', {}).get('quote') or [{}])[0]
    rows = []
    for stamp, o, h, l, c in zip(result.get('timestamp') or [], q.get('open') or [], q.get('high') or [],
                                 q.get('low') or [], q.get('close') or []):
        day = stamp // 86400
        if day > reference_day:
            break
        if None in (o, h, l, c) or min(o, h, l, c) <= 0 or h < max(o, c) - 1e-9 or l > min(o, c) + 1e-9:
            continue
        if rows and day <= rows[-1][0]:
            continue
        rows.append((day, o, h, l, c))
    for i in range(len(rows) - 1, 0, -1):
        move = rows[i][4] / rows[i - 1][4]
        if move > 1.25 or move < 0.75:
            rows = rows[i:]
            break
    if len(rows) < 60:
        return None, 'Yeterli günlük veri yok'
    if not reference or abs(rows[-1][4] / reference - 1) > 0.03:
        return None, 'Son günlük kapanış İş Yatırım ile tutmuyor'
    return rows, None


def analyse(rows):
    n = len(rows)
    day = [r[0] for r in rows]
    o, h, l, c = ([r[k] for r in rows] for k in (1, 2, 3, 4))
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, n)]
    atr = [sum(tr[max(0, i - ATR_N + 1):i + 1]) / min(i + 1, ATR_N) for i in range(n)]

    events, obs, highs, lows = [], [], [], []
    top = bottom = None          # last unbroken swing high / low: [price, index, broken]
    trend = 0
    for t in range(n):
        i = t - SWING
        if i >= SWING:
            window = range(i - SWING, i + SWING + 1)
            if all(h[i] >= h[k] for k in window) and h[i] > max(h[k] for k in window if k != i) - 1e-12:
                top = [h[i], i, False]
                highs.append(i)
            if all(l[i] <= l[k] for k in window) and l[i] < min(l[k] for k in window if k != i) + 1e-12:
                bottom = [l[i], i, False]
                lows.append(i)
        if top and not top[2] and c[t] > top[0]:
            kind = 'CHoCH' if trend == -1 else 'BOS'
            trend, top[2] = 1, True
            events.append({'k': kind, 'dir': 1, 'level': top[0], 'from': day[top[1]], 'd': day[t]})
            j = min(range(top[1], t), key=lambda k: l[k])
            obs.append({'dir': 1, 'top': h[j], 'bot': l[j], 'd': day[j], 'i': j})
        if bottom and not bottom[2] and c[t] < bottom[0]:
            kind = 'CHoCH' if trend == 1 else 'BOS'
            trend, bottom[2] = -1, True
            events.append({'k': kind, 'dir': -1, 'level': bottom[0], 'from': day[bottom[1]], 'd': day[t]})
            j = max(range(bottom[1], t), key=lambda k: h[k])
            obs.append({'dir': -1, 'top': h[j], 'bot': l[j], 'd': day[j], 'i': j})

    def active_ob(ob):
        after = range(ob['i'] + 1, n)
        if ob['dir'] == 1:
            return not any(c[k] < ob['bot'] for k in after), any(l[k] <= ob['top'] for k in after if day[k] > ob['d'] + 1)
        return not any(c[k] > ob['top'] for k in after), any(h[k] >= ob['bot'] for k in after if day[k] > ob['d'] + 1)

    live_obs = []
    for ob in obs:
        alive, tested = active_ob(ob)
        if alive:
            live_obs.append({'dir': ob['dir'], 'top': ob['top'], 'bot': ob['bot'], 'd': ob['d'], 'tested': tested})

    fvgs = []
    for i in range(2, n):
        if l[i] > h[i - 2] and l[i] - h[i - 2] >= 0.3 * atr[i]:
            gap = {'dir': 1, 'top': l[i], 'bot': h[i - 2], 'd': day[i - 1]}
            if not any(l[k] < gap['bot'] for k in range(i + 1, n)):
                fvgs.append(gap)
        if h[i] < l[i - 2] and l[i - 2] - h[i] >= 0.3 * atr[i]:
            gap = {'dir': -1, 'top': l[i - 2], 'bot': h[i], 'd': day[i - 1]}
            if not any(h[k] > gap['top'] for k in range(i + 1, n)):
                fvgs.append(gap)

    liquidity = []
    for pivots, side in ((highs, 1), (lows, -1)):
        for a, b in zip(pivots, pivots[1:]):
            pa, pb = (h[a], h[b]) if side == 1 else (l[a], l[b])
            if abs(pa - pb) <= 0.1 * atr[b]:
                level = max(pa, pb) if side == 1 else min(pa, pb)
                later = range(b + SWING + 1, n)
                swept = any(h[k] > level for k in later) if side == 1 else any(l[k] < level for k in later)
                if not swept:
                    liquidity.append({'dir': side, 'level': level, 'from': day[a], 'to': day[b]})

    last = c[-1]
    rng = None
    if highs and lows:
        hi, lo = max(h[highs[-1]:]), min(l[lows[-1]:])
        hi, lo = max(hi, h[highs[-1]]), min(lo, l[lows[-1]])
        if hi > lo:
            pos = (last - lo) / (hi - lo)
            rng = {'hi': hi, 'lo': lo, 'eq': (hi + lo) / 2, 'pos': round(pos, 3),
                   'zone': 'premium' if pos > 0.525 else 'discount' if pos < 0.475 else 'eq'}

    def nearest(items, side, key):
        pick = [x for x in items if (x[key] < last if side < 0 else x[key] > last)]
        return sorted(pick, key=lambda x: abs(x[key] - last))

    zones = {
        'demand': nearest([z for z in live_obs if z['dir'] == 1], -1, 'top')[:2],
        'supply': nearest([z for z in live_obs if z['dir'] == -1], 1, 'bot')[:2],
        'fvgUp': nearest([g for g in fvgs if g['dir'] == 1], -1, 'top')[:2],
        'fvgDown': nearest([g for g in fvgs if g['dir'] == -1], 1, 'bot')[:2],
        'liqAbove': nearest([q for q in liquidity if q['dir'] == 1], 1, 'level')[:2],
        'liqBelow': nearest([q for q in liquidity if q['dir'] == -1], -1, 'level')[:2],
    }
    # Zones that contain the last close are reported as "inside".
    zones['inside'] = [z for z in live_obs + fvgs if z['bot'] <= last <= z['top']][:2]
    return {'trend': trend, 'events': events[-6:], 'range': rng, 'zones': zones, 'last': last, 'atr': round(atr[-1], 4)}


def rnd(value):
    return round(value, 2 if value >= 10 else 4)


def tidy(obj):
    if isinstance(obj, float):
        return rnd(obj)
    if isinstance(obj, dict):
        return {k: tidy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [tidy(v) for v in obj]
    return obj


def run(code, reference, reference_day):
    rows, reason = bars(code, reference, reference_day)
    if not rows:
        return code, None, reason
    result = analyse(rows)
    keep = rows[-130:]
    result['bars'] = {'d': [r[0] for r in keep], 'o': [rnd(r[1]) for r in keep], 'h': [rnd(r[2]) for r in keep],
                      'l': [rnd(r[3]) for r in keep], 'c': [rnd(r[4]) for r in keep]}
    return code, tidy(result), None


def main():
    market = json.loads((DATA / 'market-latest.json').read_text())
    closes = {c['code']: c.get('price') for c in market['companies']}
    reference_day = int(datetime.fromisoformat(market['date']).replace(tzinfo=timezone.utc).timestamp() // 86400)
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    quotes = {c['code']: c for c in market['companies']}
    codes = [max(i['codes'], key=lambda c: quotes.get(c, {}).get('marketCap') or -1) for i in universe]
    OUT.mkdir(exist_ok=True)
    summary, gaps = {}, {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run, code, closes.get(code), reference_day) for code in codes]
        for count, future in enumerate(as_completed(futures), start=1):
            code, result, reason = future.result()
            if result:
                (OUT / f'{code}.json').write_text(json.dumps(result, separators=(',', ':')))
                ev = result['events'][-1] if result['events'] else None
                summary[code] = {'trend': result['trend'], 'zone': (result['range'] or {}).get('zone'),
                                 'last': {'k': ev['k'], 'dir': ev['dir'], 'd': ev['d']} if ev else None}
            else:
                gaps[code] = reason
                (OUT / f'{code}.json').unlink(missing_ok=True)
            if count % 100 == 0 or count == len(codes):
                print(f'{count}/{len(codes)} · analiz: {len(summary)} · açık: {len(gaps)}', flush=True)
    (DATA / 'smc-summary.json').write_text(json.dumps({
        'date': market['date'], 'swing': SWING, 'companies': dict(sorted(summary.items())), 'gaps': dict(sorted(gaps.items()))},
        ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
