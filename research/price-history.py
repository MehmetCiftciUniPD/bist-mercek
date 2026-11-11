"""Collect five years of weekly closing prices from Yahoo Finance.

Writes data/price-history.json and data/price-history-gaps.json. Nothing else
is touched. Safeguards against bad series:

- a series is kept only if its dates rise strictly, every close is positive
  and it has at least 20 points;
- its latest closes must agree with the İş Yatırım price in the market
  snapshot (within 8%), which catches wrong tickers and unadjusted splits;
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
OUT, GAPS = DATA / 'price-history.json', DATA / 'price-history-gaps.json'
TOLERANCE = 0.08


def fetch(code):
    request = Request(API.format(code), headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
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


def series(code, reference):
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
        if close <= 0 or (last_day is not None and day <= last_day):
            return None, 'Seri bozuk (tarih sırası veya sıfır/negatif fiyat)'
        points.append((day, round(close, 2 if close >= 10 else 4)))
        last_day = day
    if len(points) < 20:
        return None, 'Yeterli fiyat noktası yok'
    if not reference:
        return None, 'Karşılaştırılacak İş Yatırım fiyatı yok'
    gap = min(abs(close - reference) / reference for _, close in points[-2:])
    if gap > TOLERANCE:
        return None, f'Son fiyat İş Yatırım ile tutmuyor (Yahoo {points[-1][1]}, İş Yatırım {reference})'
    return {'d': [d for d, _ in points], 'c': [c for _, c in points]}, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    latest = DATA / 'market-latest.json'
    market = json.loads((latest if latest.exists() else DATA / 'market-2026-11-09.json').read_text())
    prices = {c['code']: c.get('price') for c in market['companies']}
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    quotes = {c['code']: c for c in market['companies']}
    codes = [max(i['codes'], key=lambda c: quotes.get(c, {}).get('marketCap') or -1) for i in universe]
    if args.limit:
        codes = codes[:args.limit]
    kept, gaps = {}, {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(series, code, prices.get(code)): code for code in codes}
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
    GAPS.write_text(json.dumps(dict(sorted(gaps.items())), ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
