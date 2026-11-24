"""Collect five years of weekly closing prices from Yahoo Finance.

Writes data/price-history.json and data/price-history-gaps.json. Nothing else
is touched. Safeguards against bad series:

- a series is kept only if its dates rise strictly, every close is positive
  and it has at least 20 points;
- bars after the market snapshot's date are dropped, and the last close must
  agree with the İş Yatırım price in that snapshot (within 3%), which catches
  wrong tickers and unadjusted splits;
- a weekly move above x2.5 or below x0.4 usually means a split or bonus issue
  Yahoo did not adjust for; the series is cut so that it starts after the last
  such move, and the cut date is stored. Nothing is rescaled or estimated;
- if fewer than 80% of the priced issuers pass, the previous file is kept.

Closes are split-adjusted, in nominal TL, not adjusted for dividends.
Yahoo's endpoint is unofficial; treat it as a convenience source.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
API = 'https://query1.finance.yahoo.com/v8/finance/chart/{}.IS?range=5y&interval=1wk'
RAW = 'https://query1.finance.yahoo.com/v8/finance/chart/{}?range=5y&interval=1wk'
BENCHMARKS = {'XU100': ('XU100.IS', 'TRY', 'BIST 100 endeksi'), 'USDTRY': ('USDTRY=X', 'TRY', 'Dolar/TL'), 'GOLD': ('GC=F', 'USD', 'Altın (ons, dolar)')}
OUT, GAPS = DATA / 'price-history.json', DATA / 'price-history-gaps.json'
TOLERANCE = 0.03


def fetch(code, url=API):
    request = Request(url.format(code), headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404:
                return None
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
        except (OSError, ValueError, HTTPException):
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def series(code, reference, reference_day, bonuses=()):
    """Return ({'d': day numbers, 'c': closes}, None) or (None, reason)."""
    try:
        payload = fetch(code)
    except (OSError, ValueError, HTTPException) as error:
        return None, f'Yahoo yanıt vermedi: {error}'
    result = ((payload or {}).get('chart') or {}).get('result') or []
    if not result:
        return None, 'Yahoo bu kod için veri döndürmedi'
    result = result[0]
    if (result.get('meta') or {}).get('currency') != 'TRY':
        return None, 'Para birimi TL değil'
    stamps = result.get('timestamp') or []
    closes = (result.get('indicators', {}).get('quote') or [{}])[0].get('close') or []
    points, last_day = [], None
    for stamp, close in zip(stamps, closes):
        if close is None:
            continue
        day = stamp // 86400
        if day > reference_day:
            # A bar after the reference close holds a session still in progress.
            break
        if close <= 0 or (last_day is not None and day <= last_day):
            return None, 'Seri bozuk (tarih sırası veya sıfır/negatif fiyat)'
        points.append((day, round(close, 2 if close >= 10 else 4)))
        last_day = day
    # Bonus issues announced on KAP: when the price drop in the weeks around the
    # issue matches the announced ratio, earlier prices are divided accordingly.
    adjusted = []
    for event_day, pct, url in bonuses:
        factor = 1 / (1 + pct / 100)
        near = [i for i in range(1, len(points)) if -21 <= points[i][0] - event_day <= 56]
        if not near:
            continue
        best = min(near, key=lambda i: abs(points[i][1] / points[i - 1][1] / factor - 1))
        if abs(points[best][1] / points[best - 1][1] / factor - 1) < 0.12:
            points = [(d, round(c * factor, 4)) for d, c in points[:best]] + points[best:]
            adjusted.append({'day': points[best][0], 'factor': round(factor, 6), 'url': url})
    cut = None
    for i in range(len(points) - 1, 0, -1):
        move = points[i][1] / points[i - 1][1]
        if move > 2.5 or move < 0.4:
            cut = points[i][0]
            points = points[i:]
            break
    if len(points) < 20:
        return None, 'Yeterli fiyat noktası yok' + (' (düzeltilmemiş bölünme sonrası kısa seri)' if cut else '')
    if not reference:
        return None, 'Karşılaştırılacak İş Yatırım fiyatı yok'
    gap = abs(points[-1][1] - reference) / reference
    if gap > TOLERANCE:
        return None, f'Son fiyat İş Yatırım ile tutmuyor (Yahoo {points[-1][1]}, İş Yatırım {reference})'
    out = {'d': [d for d, _ in points], 'c': [c for _, c in points]}
    if cut:
        out['cut'] = cut
    if adjusted:
        out['adj'] = adjusted
    return out, None


def benchmark(symbol, currency, reference_day):
    payload = fetch(symbol, RAW)
    result = (((payload or {}).get('chart') or {}).get('result') or [None])[0]
    if not result or (result.get('meta') or {}).get('currency') != currency:
        return None
    points, last = [], None
    for stamp, close in zip(result.get('timestamp') or [], (result['indicators']['quote'][0].get('close') or [])):
        day = stamp // 86400
        if close is None or day > reference_day or (last is not None and day <= last):
            continue
        if close <= 0 or (points and not 0.5 < close / points[-1][1] < 2):
            return None
        points.append((day, round(close, 4)))
        last = day
    return {'d': [d for d, _ in points], 'c': [c for _, c in points]} if len(points) >= 100 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    latest = DATA / 'market-latest.json'
    market = json.loads((latest if latest.exists() else DATA / 'market-2026-11-09.json').read_text())
    prices = {c['code']: c.get('price') for c in market['companies']}
    reference_day = (datetime.fromisoformat(market['date']).replace(tzinfo=timezone.utc).timestamp()) // 86400
    bonuses = {}
    events_file = DATA / 'market-events.json'
    if events_file.exists():
        for event in json.loads(events_file.read_text())['events'].values():
            if event.get('kind') == 'capital' and event.get('type') == 'bedelsiz' and event.get('bonusPct') and 1 <= event['bonusPct'] <= 5000:
                day = int(datetime.fromisoformat(event['date'][:10]).replace(tzinfo=timezone.utc).timestamp() // 86400)
                for c in event['codes']:
                    bonuses.setdefault(c, set()).add((day, event['bonusPct'], event['url']))
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    quotes = {c['code']: c for c in market['companies']}
    codes = [max(i['codes'], key=lambda c: quotes.get(c, {}).get('marketCap') or -1) for i in universe]
    if args.limit:
        codes = codes[:args.limit]
    kept, gaps = {}, {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(series, code, prices.get(code), reference_day, sorted(bonuses.get(code, ()))): code for code in codes}
        for count, future in enumerate(as_completed(futures), start=1):
            code = futures[future]
            data, reason = future.result()
            if data:
                kept[code] = data
            else:
                gaps[code] = reason
            if count % 100 == 0 or count == len(codes):
                print(f'{count}/{len(codes)} · seri: {len(kept)} · açık: {len(gaps)}', flush=True)
    priced = sum(1 for code in codes if prices.get(code))
    if not args.limit and len(kept) < priced * 0.8:
        sys.exit(f'Yalnızca {len(kept)}/{priced} seri doğrulandı; eski dosya korundu.')
    out = {'source': 'https://finance.yahoo.com', 'fetchedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'interval': '1wk', 'reference': market['date'],
           'note': 'Haftalık kapanış, bölünmelere göre düzeltilmiş, nominal TL; temettüye göre düzeltilmemiştir. Tarihler 1970-01-01 gününden itibaren gün sayısıdır.',
           'companies': dict(sorted(kept.items()))}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    marks = {}
    for name, (symbol, currency, label) in BENCHMARKS.items():
        found = benchmark(symbol, currency, reference_day)
        if found:
            marks[name] = {'label': label, 'symbol': symbol, **found}
    if len(marks) == len(BENCHMARKS):
        (DATA / 'benchmarks.json').write_text(json.dumps({'source': 'https://finance.yahoo.com', 'interval': '1wk', 'series': marks},
                                                         ensure_ascii=False, separators=(',', ':')) + '\n')
    else:
        print('Karşılaştırma serileri eksik geldi; eski dosya korundu.')
    GAPS.write_text(json.dumps(dict(sorted(gaps.items())), ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
