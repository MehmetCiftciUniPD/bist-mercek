"""Collect share buyback disclosures from KAP's public latest-disclosures feed.

The feed holds roughly the last day of disclosures, so this runs often (with
the 15-minute price job) and keeps what it has seen in data/buybacks.json for
a year. History therefore starts on the day collection began.
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'buybacks.json'
FEED = 'https://kap.org.tr/tr/api/disclosure/list/light'
SUBJECT = 'Payların Geri Alınmasına İlişkin Bildirim'
PROGRAM = re.compile(r'geri\s*al(ım|ınma)\s*program', re.I)
ISTANBUL = timezone(timedelta(hours=3))


def key(name):
    name = unicodedata.normalize('NFKD', name.replace('İ', 'I').replace('ı', 'i').upper())
    name = ''.join(ch for ch in name if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z0-9]', '', name)


def main():
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    names = {key(c['name']): c['codes'] for c in universe}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'items': {}}
    items = old['items']
    request = Request(FEED, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urlopen(request, timeout=30) as response:
        feed = json.load(response)
    added = 0
    for row in feed:
        subject, summary = str(row.get('subject') or ''), str(row.get('summary') or '')
        kind = 'islem' if subject == SUBJECT else 'program' if PROGRAM.search(summary) else None
        if not kind:
            continue
        index = str(row.get('disclosureIndex') or '')
        match = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2}):\d{2}', str(row.get('publishDate') or ''))
        codes = names.get(key(str(row.get('title') or '')))
        if not index.isdigit() or not match or not codes or index in items:
            continue
        items[index] = {'codes': codes, 'kind': kind, 'date': f'{match[3]}-{match[2]}-{match[1]}T{match[4]}',
                        'summary': ' '.join(summary.split())[:200], 'url': f'https://www.kap.org.tr/tr/Bildirim/{index}'}
        added += 1
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=365)).strftime('%Y-%m-%d')
    items = {k: v for k, v in items.items() if v['date'] >= cutoff}
    since = old.get('since') or datetime.now(ISTANBUL).strftime('%Y-%m-%d')
    OUT.write_text(json.dumps({'source': FEED, 'since': since, 'items': dict(sorted(items.items()))},
                              ensure_ascii=False, indent=1) + '\n')
    print(f'{added} yeni geri alım bildirimi · toplam {len(items)}')


if __name__ == '__main__':
    main()
