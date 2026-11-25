"""Brokerage research: recommendations, target prices and analyst consensus.

Sources (all public):
- İş Yatırım's covered-stock list ("Hisse Tavsiyeleri"): recommendation,
  target price, upside and recommendation date per code, and the same one
  week, one month and three months earlier;
- İş Yatırım's model portfolio ("İş Yatırım'ın Önerileri"): entry date, weight
  and return since entry;
- Yahoo Finance analyst consensus through yfinance (counts of buy/hold/sell and
  mean/low/high target from the brokers Yahoo aggregates), for covered codes
  and the largest --top companies by market value.

Each run is compared with the previous one: changed recommendations and target
prices are added to `changes` with the date seen, so the site can list the
week's revisions. Output: data/broker-reports.json. Values the source does not
state stay null.
"""
import argparse
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'broker-reports.json'
BASE = 'https://www.isyatirim.com.tr/tr-tr/analiz'
LIST = BASE + '/hisse/Sayfalar/takip-listesi.aspx'
MODEL = BASE + '/Sayfalar/is-yatirimin-onerileri.aspx'
CARD = BASE + '/hisse/Sayfalar/sirket-karti.aspx?hisse={}'
ISTANBUL = timezone(timedelta(hours=3))


def get(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def table_rows(page):
    out = []
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S):
        cells = [' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', c)).split()) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)]
        if len(cells) > 3:
            out.append(cells)
    return out


def num(text):
    text = (text or '').strip().replace('%', '')
    if not re.fullmatch(r'-?[0-9][0-9.]*(?:,[0-9]+)?', text):
        return None
    return float(text.replace('.', '').replace(',', '.'))


def day(text):
    m = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4})', text or '')
    return f'{m[3]}-{m[2]}-{m[1]}' if m else None


def isy_list(known):
    """Current recommendation (7-column table) and the same 1 week, 1 month and
    3 months earlier (14-column table, column groups in that order)."""
    out = {}
    rows = table_rows(get(LIST))
    for c in rows:
        if c[0] in known and len(c) == 7 and c[0] not in out:
            out[c[0]] = {'rec': c[1] or None, 'target': num(c[2]), 'upside': num(c[3]), 'date': day(c[4]), 'close': num(c[5])}
    for c in rows:
        if c[0] in out and len(c) == 14:
            for label, at in (('w1', 5), ('m1', 8), ('m3', 11)):
                out[c[0]][label] = {'rec': c[at] or None, 'target': num(c[at + 1])}
    return out


def isy_model(known):
    out = {}
    for c in table_rows(get(MODEL)):
        if c[0] in known and len(c) >= 11:
            out[c[0]] = {'since': day(c[1]), 'close': num(c[2]), 'target': num(c[3]), 'upside': num(c[4]),
                         'retTl': num(c[5]), 'retUsd': num(c[6]), 'retRel': num(c[7]), 'weight': num(c[10])}
    return out


def isy_note(code):
    """The analyst's one-paragraph thesis from the company card (first sentences)."""
    try:
        page = get(CARD.format(code))
    except OSError:
        return None
    at = page.find('Hisse Önerisi')
    if at < 0:
        return None
    text = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', page[at:at + 6000])).split())
    m = re.search(r'Yatırım Teması\s+(.*?)(?:Önceki Öneri Tarihi|$)', text)
    return m[1][:700] if m else None


def consensus(codes):
    try:
        import yfinance as yf
    except ImportError:
        return {}
    out = {}
    for code in codes:
        try:
            t = yf.Ticker(code + '.IS')
            pt = t.analyst_price_targets or {}
            rs = t.recommendations_summary
            row = rs.iloc[0].to_dict() if rs is not None and len(rs) else {}
        except Exception:
            continue
        counts = {k: int(row.get(k) or 0) for k in ('strongBuy', 'buy', 'hold', 'sell', 'strongSell')}
        if not sum(counts.values()) and not pt.get('mean'):
            continue
        out[code] = {**counts, 'mean': pt.get('mean'), 'median': pt.get('median'), 'low': pt.get('low'), 'high': pt.get('high'),
                     'price': pt.get('current')}
        time.sleep(0.4)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-consensus', action='store_true')
    parser.add_argument('--top', type=int, default=150, help='Consensus also for the largest N by market value')
    parser.add_argument('--notes', action='store_true', help='Also read analyst theses for recommendations newer than 14 days')
    args = parser.parse_args()
    known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    today = datetime.now(ISTANBUL).strftime('%Y-%m-%d')
    isy = isy_list(known)
    if len(isy) < 40:
        raise SystemExit(f'İş Yatırım listesi beklenenden kısa ({len(isy)}); eski dosya korunuyor.')
    model = isy_model(known)
    changes = old.get('changes', [])
    before = old.get('isy', {})
    for code, now in isy.items():
        prev = before.get(code)
        if prev and (prev.get('rec') != now['rec'] or (prev.get('target') or 0) != (now['target'] or 0)):
            changes.append({'seen': today, 'code': code, 'from': {'rec': prev.get('rec'), 'target': prev.get('target')},
                            'to': {'rec': now['rec'], 'target': now['target']}, 'date': now['date'], 'source': 'İş Yatırım'})
        if prev and prev.get('note') and prev.get('date') == now['date']:
            now['note'] = prev['note']
    if args.notes:
        cutoff = (datetime.now(ISTANBUL) - timedelta(days=14)).strftime('%Y-%m-%d')
        for code, now in isy.items():
            if (now['date'] or '') >= cutoff and not now.get('note') and now['rec'] in ('AL', 'TUT', 'SAT', 'Ö.Y.'):
                now['note'] = isy_note(code)
    market = json.loads((DATA / 'market-latest.json').read_text())['companies']
    big = [c['code'] for c in sorted(market, key=lambda c: -(c.get('marketCap') or 0))[:args.top] if c['code'] in known]
    cons = old.get('consensus', {}) if args.no_consensus else (consensus(sorted(set(isy) | set(big))) or old.get('consensus', {}))
    keep = (datetime.now(ISTANBUL) - timedelta(days=120)).strftime('%Y-%m-%d')
    OUT.write_text(json.dumps({
        'fetchedAt': datetime.now(ISTANBUL).isoformat(timespec='minutes'),
        'sources': {'isy': LIST, 'model': MODEL, 'consensus': 'Yahoo Finance (yfinance)'},
        'isy': isy, 'model': model, 'consensus': cons,
        'changes': [c for c in changes if c['seen'] >= keep]}, ensure_ascii=False, indent=1) + '\n')
    print(f'İş Yatırım {len(isy)} hisse · model portföy {len(model)} · konsensüs {len(cons)} · değişiklik {len(changes)}')


if __name__ == '__main__':
    main()
