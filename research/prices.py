"""Refresh prices and multiples for every issuer in one request.

Writes data/market-latest.json in the same shape as the dated baseline
(data/market-2026-11-09.json), which stays untouched for the Mercek app.
Runs on GitHub's servers from the daily workflow, so it costs no assistant
usage. If the page cannot be read or looks incomplete, the previous file is
kept and the script exits with an error.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SOURCE = 'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx'
BASELINE = DATA / 'market-2026-11-09.json'
OUT = DATA / 'market-latest.json'
ISTANBUL = timezone(timedelta(hours=3))


class Tables(HTMLParser):
    """Collect every table as rows of cell texts."""

    def __init__(self):
        super().__init__()
        self.tables, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.tables.append([])
        elif tag == 'tr' and self.tables:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.tables[-1].append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def number(text):
    try:
        return float(text.replace('.', '').replace(',', '.').replace('%', ''))
    except ValueError:
        return None


def last_close(now):
    """Date of the most recent session close; exchange holidays are not known here."""
    day = now.date()
    if now.weekday() >= 5 or (now.hour, now.minute) < (18, 30):
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def parse(raw):
    parser = Tables()
    parser.feed(raw)
    market = {}
    for table in parser.tables:
        if table and 'Sektör' in table[0]:
            for r in table[1:]:
                if len(r) == 8:
                    market[r[0]] = {'code': r[0], 'name': r[1], 'sector': r[2], 'price': number(r[3]), 'marketCap': number(r[4])}
    for table in parser.tables:
        if not table:
            continue
        if 'Son Dönem' in table[0]:
            for r in table[1:]:
                if r and r[0] in market and len(r) >= 7:
                    market[r[0]].update(zip(['pe', 'multiple', 'evSales', 'pb'], map(number, r[2:6])), ratioPeriod=r[6])
        if any('Günlük Getiri' in cell for cell in table[0]):
            for r in table[1:]:
                if r and r[0] in market and len(r) >= 6:
                    market[r[0]].update(zip(['return', 'weekReturn', 'monthReturn', 'ytdReturn'], map(number, r[2:6])))
    return list(market.values())


def main():
    request = Request(SOURCE, headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'tr-TR,tr;q=0.9'})
    with urlopen(request, timeout=90) as response:
        raw = response.read().decode('utf-8', 'replace')
    companies = parse(raw)
    baseline = {c['code'] for c in json.loads(BASELINE.read_text())['companies']}
    priced = [c for c in companies if c.get('price')]
    known = sum(c['code'] in baseline for c in priced)
    with_ratio = sum(1 for c in priced if c.get('pb') is not None)
    if known < len(baseline) * 0.9 or with_ratio < len(priced) * 0.8:
        sys.exit(f'Sayfa eksik görünüyor ({len(priced)} fiyat, {known} bilinen kod, {with_ratio} çarpan); eski dosya korundu.')
    now = datetime.now(ISTANBUL)
    OUT.write_text(json.dumps({'date': last_close(now), 'fetchedAt': now.isoformat(timespec='minutes'), 'source': SOURCE,
                               'companies': companies}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(companies)} satır · {len(priced)} fiyat · son kapanış {last_close(now)} · çekim {now:%d.%m.%Y %H:%M}')


if __name__ == '__main__':
    main()
