"""Collect share buyback disclosures from KAP into data/buybacks.json.

- KAP's disclosure search (the endpoint its own "Bildirim Sorgu" page uses)
  returns every "Payların Geri Alınmasına İlişkin Bildirim" of the last
  LOOKBACK days in one request.
- Buyback programmes announced under other subjects are picked up from the
  public latest-disclosures feed when their summary names a programme.
- For each company the newest notices are opened (the public notice page) to
  read the cumulative share of capital bought back ("sermayedeki payı %0,39").
  Values outside 0-10% (the legal ceiling) are discarded. A notice whose text
  has no such figure keeps ratio = null; nothing is estimated.

Notices older than a year are dropped.
"""
import argparse
import html
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'buybacks.json'
SEARCH = 'https://www.kap.org.tr/tr/api/disclosure/members/byCriteria'
FEED = 'https://kap.org.tr/tr/api/disclosure/list/light'
NOTICE = 'https://www.kap.org.tr/tr/Bildirim/{}'
SUBJECT_OID = '4028328d6233239a01629b43e4694fae'   # Payların Geri Alınmasına İlişkin Bildirim
PROGRAM = re.compile(r'geri\s*al(ım|ınma)\s*program', re.I)
ISTANBUL = timezone(timedelta(hours=3))
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://www.kap.org.tr/tr/bildirim-sorgu'}
CAP = re.compile(r'(?:azami|en\s+fazla|üst\s+sınır\w*|maksimum)[^.]{0,80}?([0-9][0-9.]*(?:,[0-9]+)?)\s*(?:adet|TL\s+nominal|lot)', re.I)
CACHE = None


def search(start, end):
    body = {'fromDate': start, 'toDate': end, 'memberType': 'IGS', 'mkkMemberOidList': [], 'inactiveMkkMemberOidList': [],
            'disclosureClass': '', 'subjectList': [SUBJECT_OID], 'isLate': '', 'mainSector': '', 'sector': '',
            'subSector': '', 'marketOid': '', 'index': '', 'bdkReview': '', 'bdkMemberOidList': [], 'year': '',
            'term': '', 'ruleType': '', 'period': '', 'fromSrc': False, 'srcCategory': '', 'disclosureIndexList': []}
    request = Request(SEARCH, data=json.dumps(body).encode(), headers={**HEADERS, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def stamp(text):
    match = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2}):\d{2}', str(text or ''))
    return f'{match[3]}-{match[2]}-{match[1]}T{match[4]}' if match else None


RATIO = [
    re.compile(r'sermaye\w*\s+(?:içindeki|içerisindeki)?\s*(?:pay\w*|oran\w*)[^%]{0,40}%\s*([0-9]+(?:[.,][0-9]+)?)', re.I),
    re.compile(r'sermaye\w*[^%.]{0,60}(?:pay\w*|oran\w*)[^%]{0,30}%\s*([0-9]+(?:[.,][0-9]+)?)', re.I),
    re.compile(r'%\s*([0-9]+(?:[.,][0-9]+)?)[^%.]{0,40}(?:oranında|payına)[^.]{0,40}sermaye', re.I),
    re.compile(r'sermaye\w*[^%.]{0,40}%\s*([0-9]+(?:[.,][0-9]+)?)\W{0,3}\s*oran', re.I),
]


def ratio_of(index):
    """(cumulative share of capital bought back %, programme ceiling in shares, read ok)."""
    cached = CACHE / f'{index}.html' if CACHE else None
    if cached and cached.exists():
        raw = cached.read_text()
    else:
        request = Request(NOTICE.format(index), headers={'User-Agent': 'Mozilla/5.0'})
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    raw = response.read().decode('utf-8', 'replace')
                break
            except OSError:
                if attempt == 2:
                    return None, None, False
                time.sleep(2 * (attempt + 1))
        if cached:
            cached.write_text(raw)
    text = raw.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\"', '"')
    text = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    text = ' '.join(text.split())
    found = []
    for pattern in RATIO:
        for match in pattern.finditer(text):
            value = float(match.group(1).replace('.', '').replace(',', '.')) if match.group(1).count('.') and ',' in match.group(1) \
                else float(match.group(1).replace(',', '.'))
            if 0 < value <= 10:
                found.append(value)
        if found:
            break
    cap = CAP.search(text[text.find('Gönderim Tarihi'):] if 'Gönderim Tarihi' in text else text)
    cap_value = float(cap.group(1).replace('.', '').replace(',', '.')) if cap else None
    # The cumulative total is the largest share named in the notice.
    return (max(found) if found else None), cap_value, True


def key(name):
    name = unicodedata.normalize('NFKD', name.replace('İ', 'I').replace('ı', 'i').upper())
    name = ''.join(ch for ch in name if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z0-9]', '', name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=35)
    parser.add_argument('--cache', type=Path, help='Keep downloaded notice pages here')
    args = parser.parse_args()
    global CACHE
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
        CACHE = args.cache
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    known = {c for i in universe for c in i['codes']}
    names = {key(c['name']): c['codes'] for c in universe}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'items': {}}
    items = old['items']
    today = datetime.now(ISTANBUL)
    rows = search((today - timedelta(days=args.days)).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    added = 0
    for row in rows:
        index, date = str(row.get('disclosureIndex') or ''), stamp(row.get('publishDate'))
        codes = [c.strip() for c in str(row.get('stockCodes') or '').split(',') if c.strip() in known]
        if not index.isdigit() or not date or not codes:
            continue
        if index not in items:
            added += 1
        item = items.setdefault(index, {})
        item.update(codes=codes, kind='islem', date=date, summary=' '.join(str(row.get('summary') or '').split())[:200],
                    url=NOTICE.format(index))
    try:
        with urlopen(Request(FEED, headers=HEADERS), timeout=30) as response:
            for row in json.load(response):
                if not PROGRAM.search(str(row.get('summary') or '')):
                    continue
                index, date = str(row.get('disclosureIndex') or ''), stamp(row.get('publishDate'))
                codes = names.get(key(str(row.get('title') or '')))
                if index.isdigit() and date and codes and index not in items:
                    items[index] = {'codes': codes, 'kind': 'program', 'date': date,
                                    'summary': ' '.join(str(row.get('summary') or '').split())[:200], 'url': NOTICE.format(index)}
                    added += 1
    except (OSError, ValueError):
        pass
    cutoff = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    items = {k: v for k, v in items.items() if v['date'] >= cutoff}

    # Every notice is opened once for the share of capital and the programme ceiling.
    todo = [i for i, item in items.items() if item['kind'] == 'islem' and 'ratio' not in item]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, (value, cap, ok) in zip(todo, pool.map(ratio_of, todo)):
            if ok:
                items[index]['ratio'] = value
                if cap:
                    items[index]['cap'] = cap
    OUT.write_text(json.dumps({'source': SEARCH, 'since': min(v['date'] for v in items.values())[:10] if items else None,
                               'items': dict(sorted(items.items()))}, ensure_ascii=False, indent=1) + '\n')
    parsed = sum(1 for i in todo if items[i].get('ratio') is not None)
    print(f'{added} yeni bildirim · toplam {len(items)} · {len(todo)} bildirim açıldı, {parsed} tanesinde sermaye oranı bulundu')


if __name__ == '__main__':
    main()
