"""Foreign ownership ratios per share, from İş Yatırım's daily table on Foreks.

İş Yatırım publishes "Günlük Yabancı Oranları Tablosu" every morning; Foreks
relays it with a public download link (collected by foreks-reports.py into
data/foreks-reports.json). The PDF lists the shares whose foreign ratio rose
or fell most over a day, a week, a month and the year to date (current and
earlier ratio, change in points), and the current ratio of every share above
roughly 4%. Output: data/foreign-ratios.json with one snapshot per report date
(120 days kept) and the latest movers. Shares not in the table stay absent.
"""
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'foreign-ratios.json'
TITLE = re.compile(r'Günlük Yabancı Oranları', re.I)
ISTANBUL = timezone(timedelta(hours=3))
N = r'-?\d+(?:\.\d{3})*,\d+|-?\d+'
SIDE = rf'([A-Z][A-Z0-9]{{2,5}})\s+({N})\s+({N})\s+({N})\s+({N})\s+({N})'
PERIODS = [('GÜNLÜK', 'day'), ('HAFTALIK', 'week'), ('AYLIK', 'month'), ('YILİÇİ', 'ytd'), ('YIL İÇİ', 'ytd')]


def num(t):
    return float(t.replace('.', '').replace(',', '.'))


def parse(text, known):
    movers, current, period, streaks = {}, {}, None, {}
    in_current, streak = False, None
    for line in text.splitlines():
        compact = line.replace(' ', '')
        if 'ArtışMatrisi' in compact or 'DüşüşMatrisi' in compact:
            streak, in_current, period = ('up' if 'Artış' in compact else 'down'), False, None
            continue
        if streak:
            if 'GRAFİK' in line:
                streak = None
                continue
            for code, n, values in re.findall(r'\b([A-Z][A-Z0-9]{2,5})\s+(\d{1,2})\s+((?:\d+,\d+\s*)+)', line):
                if code in known:
                    streaks.setdefault(streak, []).append({'c': code, 'days': int(n), 'hist': [num(v) for v in values.split()]})
            continue
        for word, key in PERIODS:
            if word.replace(' ', '') + 'DEĞİŞİME' in compact:
                period, in_current = key, False
        if 'CARİ HİSSE YABANCI ORANLARI' in line:
            in_current, period = True, None
            continue
        if in_current:
            for code, value in re.findall(r'\b([A-Z][A-Z0-9]{2,5})\s+(\d+,\d+)(?=\s|$)', line):
                if code in known:
                    current[code] = num(value)
            continue
        if period:
            sides = re.findall(SIDE, line)
            for i, (code, cur, prev, bps, hao, ret) in enumerate(sides[:2]):
                if code in known:
                    movers.setdefault(period, {'up': [], 'down': []})['up' if i == 0 else 'down'].append(
                        {'c': code, 'now': num(cur), 'prev': num(prev), 'chg': num(bps), 'ret': num(ret)})
    return movers, current, streaks


def main():
    if not shutil.which('pdftotext'):
        raise SystemExit('pdftotext gerekli.')
    known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    reports = json.loads((DATA / 'foreks-reports.json').read_text())['items']
    old = json.loads(OUT.read_text()) if OUT.exists() else {'days': {}, 'movers': {}, 'read': []}
    days, read = old['days'], set(old.get('read', []))
    latest = (old.get('date'), old.get('movers', {}))
    for doc_id, item in sorted(reports.items(), key=lambda kv: kv[1].get('date') or ''):
        if doc_id in read or not TITLE.search(item['title']) or not item.get('file'):
            continue
        try:
            with urlopen(Request(item['file'], headers={'User-Agent': 'Mozilla/5.0 (mercek research)'}), timeout=60) as r:
                pdf = r.read()
        except OSError:
            continue
        text = subprocess.run(['pdftotext', '-layout', '-', '-'], input=pdf, capture_output=True).stdout.decode('utf-8', 'replace')
        stamp = re.search(r'(\d{2})/(\d{2})/(\d{4})', text[:200])
        day = f'{stamp[3]}-{stamp[2]}-{stamp[1]}' if stamp else (item.get('date') or '')[:10]
        movers, current, streaks = parse(text, known)
        movers['streaks'] = streaks
        read.add(doc_id)
        if len(current) < 100:
            print(f'{day}: tablo beklenenden kısa ({len(current)}), atlandı')
            continue
        days[day] = current
        if day >= (latest[0] or ''):
            latest = (day, movers)
        print(f'{day}: {len(current)} hisse · hareket listeleri {sorted(movers)}')
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=120)).strftime('%Y-%m-%d')
    days = {k: v for k, v in sorted(days.items()) if k >= cutoff}
    OUT.write_text(json.dumps({'source': 'İş Yatırım, Günlük Yabancı Oranları Tablosu (Foreks)', 'date': latest[0], 'movers': latest[1],
                               'days': days, 'read': sorted(read)[-200:]}, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'{len(days)} gün · son {latest[0]}')


if __name__ == '__main__':
    main()
