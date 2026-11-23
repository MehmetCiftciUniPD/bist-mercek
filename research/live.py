"""Fetch 15-minute delayed prices for all issuers from Yahoo Finance.

Writes data/live.json, which is not committed: it is published with the site
only. Each price must be in TL, positive, and within BIST's daily limit band
(±10%, checked loosely at ±11%) of the last official close in
market-latest.json; anything else is dropped. Market multiples elsewhere stay
at the official close.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
API = 'https://query1.finance.yahoo.com/v7/finance/spark?symbols={}&range=1d&interval=15m'
BATCH = 20


def fetch(codes):
    request = Request(API.format(','.join(f'{c}.IS' for c in codes)), headers={'User-Agent': 'Mozilla/5.0'})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response).get('spark', {}).get('result') or []
        except (OSError, ValueError):
            if attempt == 2:
                return []
            time.sleep(2 * (attempt + 1))


def main():
    market = json.loads((DATA / 'market-latest.json').read_text())
    closes = {c['code']: c.get('price') for c in market['companies']}
    codes = [c for c, p in closes.items() if p]
    live, dropped = {}, 0
    for start in range(0, len(codes), BATCH):
        for item in fetch(codes[start:start + BATCH]):
            meta = ((item.get('response') or [{}])[0]).get('meta') or {}
            code = (item.get('symbol') or '').removesuffix('.IS')
            price, stamp, close = meta.get('regularMarketPrice'), meta.get('regularMarketTime'), closes.get(code)
            if meta.get('currency') != 'TRY' or not price or price <= 0 or not stamp or not close:
                dropped += 1
                continue
            if abs(price / close - 1) > 0.11:
                dropped += 1
                continue
            live[code] = {'p': round(price, 4), 't': stamp}
        time.sleep(0.5)
    if len(live) < len(codes) * 0.7:
        sys.exit(f'Yalnızca {len(live)}/{len(codes)} gecikmeli fiyat alındı; yayımlanmadı.')
    out = {'source': 'https://finance.yahoo.com', 'fetchedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'base': market['date'], 'note': 'Yaklaşık 15 dakika gecikmeli. Değişim, son resmî kapanışa göredir.', 'prices': live}
    (DATA / 'live.json').write_text(json.dumps(out, separators=(',', ':')) + '\n')
    print(f'{len(live)} gecikmeli fiyat · {dropped} reddedildi')


if __name__ == '__main__':
    main()
