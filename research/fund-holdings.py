"""Shares held by the funds SPK put into liquidation, from fonoloji.com.

Fonoloji's public "SPK tasfiye" page (its /api/ is disallowed by robots.txt
and is not used) aggregates the liquidating funds' portfolio
reports (August to early October 2026) per share: estimated lots, number of
funds, share of the company's capital and size relative to the free float.
Only the largest positions by value (about 40) are on the page. This keeps
those figures, with the source and its update time, in
data/fund-holdings.json. Values are the source's estimates; nothing is
recomputed except unit conversion.
"""
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'fund-holdings.json'
SOURCE = 'https://fonoloji.com/spk-tasfiye'
UNITS = {'B': 1e3, 'K': 1e3, 'Mn': 1e6, 'Mr': 1e9}
NUM = r'[0-9][0-9.]*(?:,[0-9]+)?'
ROW = re.compile(
    rf'\b[A-Z0-9]{{2}} (?P<code>[A-Z0-9]{{4,6}}) (?P<name>.+?) (?P<lots>{NUM}) ?(?P<lu>Mr|Mn|B|K)? (?P<price>{NUM}) ₺ '
    rf'(?P<day>[−-]?%{NUM}) (?P<since>[−-]?%{NUM}) (?P<value>{NUM}) ?(?P<vu>Mr|Mn|B|K)? ₺ (?P<funds>\d+) '
    rf'%(?P<cap>{NUM}) (?P<float>{NUM}) ?(?P<fu>Mr|Mn|B|K)? % (?P<floatcap>{NUM}) oran(?: ↓ önce % (?P<before>{NUM}))? %(?P<ratio>{NUM})')


def num(text, unit=None):
    value = float(text.replace('.', '').replace(',', '.').replace('−', '-'))
    return value * UNITS.get(unit or '', 1)


def main():
    with urlopen(Request(SOURCE, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as r:
        raw = r.read().decode('utf-8', 'replace')
    text = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', raw)
    flat = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', text)).split())
    updated = re.search(r'Son güncelleme: (\d{1,2} \w+ \d{4} \d{2}:\d{2})', flat)
    period = re.search(r'Raporlar (.{0,40}?) arası', flat)
    rows = {}
    # The public page renders the largest positions (by value) as table rows.
    for part in raw.split('<tr class="tsf-satir"')[1:]:
        cells = [' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', c)).split())
                 for c in re.findall(r'<td[^>]*>([\s\S]*?)</td>', part.split('</tr>')[0])]
        if len(cells) < 9:
            continue
        head = re.match(r'\S{2} ([A-Z0-9]{4,6}) (.+)', cells[0])
        lots = re.match(rf'({NUM}) ?(Mr|Mn|B|K)?', cells[1])
        value = re.match(rf'({NUM}) ?(Mr|Mn|B|K)?', cells[4])
        cap = re.match(rf'%({NUM})', cells[6])
        ratio = re.match(rf'%({NUM})', cells[8])
        if not (head and lots and cap and ratio and cells[5].isdigit()):
            continue
        row = {'name': head[2], 'lots': round(num(lots[1], lots[2])), 'funds': int(cells[5]), 'capital': num(cap[1]),
               'floatRatio': num(ratio[1]), 'value': round(num(value[1], value[2])) if value else None}
        if before := re.search(rf'önce % ({NUM})', cells[7]):
            row['floatShareBefore'] = num(before[1])
        rows[head[1]] = row
    if len(rows) < 30:
        sys.exit(f'Yalnızca {len(rows)} satır okundu; eski dosya korundu.')
    OUT.write_text(json.dumps({
        'source': SOURCE, 'sourceUpdated': updated.group(1) if updated else None,
        'reports': period.group(1) if period else None,
        'fetchedAt': datetime.now(timezone(timedelta(hours=3))).isoformat(timespec='minutes'),
        'note': "Fonların portföy raporlarına dayanan tahmini lotlar. 'capital' şirket sermayesindeki pay (%), "
                "'floatRatio' fonların lotunun fiili dolaşımdaki paylara oranı (%, 100'ü geçebilir).",
        'companies': dict(sorted(rows.items(), key=lambda kv: -kv[1]['capital']))}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(rows)} hisse · kaynak güncelleme {updated.group(1) if updated else "?"}')


if __name__ == '__main__':
    main()
