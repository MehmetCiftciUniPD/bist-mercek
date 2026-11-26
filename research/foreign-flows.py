"""Weekly foreign investor flows into Turkish shares and bonds (market-wide).

Two brokers summarise the central bank's weekly securities statistics and
publish the PDFs on Foreks: Şeker Yatırım ("Yabancı Menkul Kıymet Stoku
Verileri ve BIST Yabancı Payı") and Bizim Menkul ("Yabancıların Hisse & DİBS
İşlemleri"). From whichever arrives (both when possible) this keeps, per
week: net foreign buying of shares, government bonds (DİBS) and corporate
bonds (ÖST) in million USD (price and FX effects removed), the year-to-date
share total, the foreign holdings of shares and bonds, and the foreign share
of the BIST free float. When both reports give a figure they must agree;
otherwise the figure is dropped. Output: data/foreign-flows.json, 2 years kept.
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
OUT = DATA / 'foreign-flows.json'
TITLES = re.compile(r'Yabancı Menkul Kıymet Stoku|Yabancıların Hisse', re.I)
MONTHS = ['ocak', 'şubat', 'mart', 'nisan', 'mayıs', 'haziran', 'temmuz', 'ağustos', 'eylül', 'ekim', 'kasım', 'aralık']
ISTANBUL = timezone(timedelta(hours=3))
N = r'-?\d{1,3}(?:\.\d{3})*(?:,\d+)?'


def num(t):
    return float(t.replace('.', '').replace(',', '.'))


def flat(text):
    # Şeker's PDF font drops the letter "i" in pdftotext ("h sse"); match on letters without it.
    return ' '.join(text.split())


def week_end(text):
    m = re.search(r'(\d{1,2})\s*-\s*(\d{1,2})\s+(\w+)\s+(\d{4})\s+(?:haftas|tar)', text)
    if not m or m[3].lower() not in MONTHS:
        return None
    return f'{m[4]}-{MONTHS.index(m[3].lower()) + 1:02d}-{int(m[2]):02d}'


def seker(text):
    t = flat(text)
    out = {'week': week_end(t)}
    for key, pattern in (('stockShares', r'Toplam Yabancı H[i ]?sse Stoku\s+(' + N + ')'),
                         ('stockBonds', r'Toplam Yabancı D[İI]BS[^0-9-]{0,30}Stoku\s+(' + N + ')'),
                         ('shares', r'Haftalık Net Yabancı H[i ]?sse G[i ]?r[i ]?ş/Çıkışı\s+(' + N + ')'),
                         ('bonds', r'Haftalık Net Yabancı D[İI]BS G[i ]?r[i ]?ş/Çıkışı\s+(' + N + ')')):
        if m := re.search(pattern, t):
            out[key] = num(m[1])
    if m := re.search(r'h[i ]?sse sened[i ]?nde\s+(' + N + r')\s+m[i ]?lyon dolar net (satış|alış)', t):
        out['sharesExact'] = num(m[1]) * (-1 if m[2] == 'satış' else 1)
    if m := re.search(r'başından bu yana [s ]*e yabancılar\s+(' + N + r')\s+m[i ]?lyon dolarlık net (alış|satış)', t):
        out['sharesYtd'] = num(m[1]) * (1 if m[2] == 'alış' else -1)
    if m := re.search(r'hafta\s+%(' + N + r')\s*\(T-3', t):
        out['foreignShare'] = num(m[1])
    return out


def bizim(text):
    t = flat(text)
    out = {'week': week_end(t)}
    sign = lambda word: -1 if word.startswith('sat') else 1
    if m := re.search(r'(' + N + r') milyon dolar hisse senedi (satışı|alımı)', t):
        out['sharesExact'] = num(m[1]) * sign(m[2])
    if m := re.search(r'(' + N + r') milyon dolar Devlet İç Borçlanma Senedi[^,.]{0,30}?(satışı|alımı)', t):
        out['bonds'] = num(m[1]) * sign(m[2])
    if m := re.search(r'(' + N + r') milyon dolar Özel Sektör Tahvil (satışı|alımı)', t):
        out['corporate'] = num(m[1]) * sign(m[2])
    if m := re.search(r'Yılbaşından beri[^.]*?toplam (' + N + r') milyon dolarlık hisse senedi (alımı|satışı)', t):
        out['sharesYtd'] = num(m[1]) * sign(m[2])
    if m := re.search(r'yabancıların payı \d+ \w+ itibariyle %(' + N + ')', t):
        out['foreignShareFloat'] = num(m[1])
    return out


def main():
    if not shutil.which('pdftotext'):
        raise SystemExit('pdftotext gerekli.')
    reports = json.loads((DATA / 'foreks-reports.json').read_text())['items']
    old = json.loads(OUT.read_text()) if OUT.exists() else {'weeks': {}, 'read': []}
    weeks, read = old['weeks'], set(old['read'])
    for doc_id, item in sorted(reports.items(), key=lambda kv: kv[1].get('date') or ''):
        if doc_id in read or not TITLES.search(item['title']) or not item.get('file'):
            continue
        try:
            with urlopen(Request(item['file'], headers={'User-Agent': 'Mozilla/5.0 (mercek research)'}), timeout=60) as r:
                pdf = r.read()
        except OSError:
            continue
        # Bizim Menkul's layout interleaves chart labels with the prose; read it in reading order.
        mode = ['-layout'] if 'Stoku' in item['title'] else []
        text = subprocess.run(['pdftotext', *mode, '-', '-'], input=pdf, capture_output=True).stdout.decode('utf-8', 'replace')
        got = seker(text) if 'Stoku' in item['title'] else bizim(text)
        read.add(doc_id)
        week = got.pop('week')
        if not week:
            print('hafta okunamadı:', item['title'])
            continue
        entry = weeks.setdefault(week, {'sources': {}})
        entry['sources'][item['broker'] or '?'] = {'url': item['url'], **got}
        print(week, item['broker'], got)
    # One figure per field when the sources agree (within rounding).
    for week, entry in weeks.items():
        merged, conflicts = {}, []
        for src in entry['sources'].values():
            for k, v in src.items():
                if k == 'url':
                    continue
                if k == 'sharesExact':
                    k = 'shares'
                if k in merged and abs(merged[k] - v) > max(1.0, abs(v) * 0.01):
                    conflicts.append(k)
                elif k not in merged or (v != int(v) and merged[k] == int(merged[k])):   # keep the more precise figure
                    merged[k] = v
        for k in conflicts:
            merged.pop(k, None)
        entry['values'] = merged
        entry['conflicts'] = sorted(set(conflicts)) or None
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=730)).strftime('%Y-%m-%d')
    weeks = {k: v for k, v in sorted(weeks.items()) if k >= cutoff}
    OUT.write_text(json.dumps({'source': 'TCMB haftalık menkul kıymet istatistikleri; Şeker Yatırım ve Bizim Menkul raporları (Foreks)',
                               'weeks': weeks, 'read': sorted(read)[-300:]}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(weeks)} hafta')


if __name__ == '__main__':
    main()
