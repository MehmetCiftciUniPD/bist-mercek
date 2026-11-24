"""Share trades by controlling shareholders and executives, from KAP.

Reads every "Pay Alım Satım Bildirimi" filed by a listed company about its
insiders, and those that insiders file themselves through MKK (their details
are in a PDF attachment, read with pdftotext). Notices filed by fund managers
for their funds are left out. Keeps the form's transaction table: trade date, nominal bought, nominal sold,
holding at the start and end of the day and as a share of capital. Price and
amount are read from the explanation text when given. Output:
data/insider-trades.json. BIST shares have a 1 TL nominal value, so nominal
TL equals the number of shares.
"""
import argparse
import html
import importlib.util
import json
import re
import shutil
import subprocess
import time
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'insider-trades.json'
spec = importlib.util.spec_from_file_location('insiders', ROOT / 'research' / 'insiders.py')
ins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ins)
NUM = r'-?[0-9][0-9.]*(?:,[0-9]+)?'
ROW = re.compile(rf'(\d{{2}}/\d{{2}}/\d{{4}}) ({NUM}) ({NUM}) ({NUM}) ({NUM}) ({NUM}) % ?({NUM}) % ?({NUM}) % ?({NUM}) % ?({NUM})')


def page_text(index):
    """Full text of a notice after its header (uses the insiders.py cache)."""
    ins.explanation(index)  # downloads into the cache when one is set
    cached = ins.CACHE / f'{index}.html' if ins.CACHE else None
    if cached and cached.exists():
        raw = cached.read_text()
    else:
        from urllib.request import Request, urlopen
        with urlopen(Request(ins.NOTICE.format(index), headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
            raw = r.read().decode('utf-8', 'replace')
    text = raw.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&').replace('\\"', '"').replace('\\n', ' ')
    text = ' '.join(html.unescape(html.unescape(re.sub(r'<[^>]+>', ' ', text))).replace('\xa0', ' ').split())
    head = text.find('Gönderim Tarihi')
    return text[head:] if head >= 0 else text


PLATFORM = 'KAMUYU AYDINLATMA PLATFORMU'
DOWNLOAD = 'https://www.kap.org.tr/tr/api/file/download/{}'
PDF_ROW = re.compile(rf'(\d{{2}}/\d{{2}}/\d{{4}})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})')


def pdf_notice(index):
    """Name, role, explanation and rows from an insider's own (MKK) notice."""
    if not shutil.which('pdftotext'):
        return None
    page = ins.CACHE / f'{index}.html' if ins.CACHE else None
    raw = page.read_text() if page and page.exists() else None
    if raw is None:
        with urlopen(Request(ins.NOTICE.format(index), headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
            raw = r.read().decode('utf-8', 'replace')
        if page:
            page.write_text(raw)
    obj = re.search(r'\\?"objId\\?":\\?"([0-9a-f]{32})', raw)
    if not obj:
        return None
    pdf = (ins.CACHE / f'{obj[1]}.pdf') if ins.CACHE else Path('/tmp') / f'{obj[1]}.pdf'
    if not pdf.exists():
        for attempt in range(3):
            try:
                with urlopen(Request(DOWNLOAD.format(obj[1]), headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
                    pdf.write_bytes(r.read())
                break
            except OSError:
                if attempt == 2:
                    return None
                time.sleep(2)
    try:
        text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    field = lambda label: (re.search(label + r'\s*:\s*(.*)', text) or [None, ''])[1].strip()
    rows = []
    for m in PDF_ROW.finditer(text):
        d, mth, y = m[1].split('/')
        rows.append({'date': f'{y}-{mth}-{d}', 'buy': ins.number(m[2]), 'sell': ins.number(m[3]),
                     'start': ins.number(m[5]), 'end': ins.number(m[6]),
                     'startPct': ins.number(m[7]), 'endPct': ins.number(m[9])})
    explanation = re.search(r'Açıklama\s*:\s*([\s\S]*?)\n\s*Ad Soyad', text)
    note = ' '.join(explanation[1].split()) if explanation else ''
    out = {'rows': rows, 'who': field('Ad Soyad / Ticaret Ünvanı'), 'role': field('Görevi'), 'text': note[:600]}
    if m := re.search(rf'({NUM})\s*TL\s*(?:fiyat|ortalama)|ortalama\w*\s+({NUM})\s*TL', note, re.I):
        out['price'] = ins.number(m.group(1) or m.group(2))
    out['offExchange'] = bool(re.search(r'borsa\s*dışı', note, re.I))
    return out


def parse(text):
    rows, seen = [], set()
    for m in ROW.finditer(text):
        key = m.group(0)
        if key in seen:
            continue
        seen.add(key)
        d, mth, y = m[1].split('/')
        rows.append({'date': f'{y}-{mth}-{d}', 'buy': ins.number(m[2]), 'sell': ins.number(m[3]),
                     'start': ins.number(m[5]), 'end': ins.number(m[6]),
                     'startPct': ins.number(m[7]), 'endPct': ins.number(m[9])})
    explanation = ''
    at = text.find('oda_ExplanationTextBlock|')
    if at >= 0:
        body = text[at + len('oda_ExplanationTextBlock|'):at + 1500]
        cut = re.search(r'\b(?:Pursuant|Our (?:Company|shareholder)|The (?:Chairman|Board)|Mr\.|Ms\.|We hereby|This statement)\b|Pay Alım Satım Bilgileri', body)
        explanation = (body[:cut.start()] if cut else body).strip()
    out = {'rows': rows, 'text': explanation[:600]}
    if m := re.search(rf'ağırlıklı\s+ortalama\w*\s+(?:fiyat\w*\s+)?({NUM})\s*TL', explanation, re.I) or \
            re.search(rf'({NUM})\s*TL\s*(?:fiyat|ortalama)', explanation, re.I) or \
            re.search(rf'pay\s+başına\s+({NUM})\s*TL', explanation, re.I):
        out['price'] = ins.number(m.group(1))
    if m := re.search(rf'({NUM})\s*TL\s*(?:işlem\s+)?bedel', explanation, re.I):
        out['amount'] = ins.number(m.group(1))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=35)
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
        ins.CACHE = args.cache
    known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'items': {}}
    items = old['items']
    todo = {}
    for start, end in ins.windows(args.days):
        for row in ins.search([ins.INSIDER], start, end):
            index = str(row.get('disclosureIndex') or '')
            own = str(row.get('kapTitle') or '') == PLATFORM
            listed = str(row.get('stockCodes') or '') or (str(row.get('relatedStocks') or '') if own else '')
            codes = [c.strip() for c in listed.split(',') if c.strip() in known]
            if index.isdigit() and codes and index not in items:
                todo[index] = {'codes': codes, 'published': ins.stamp(row.get('publishDate')), 'url': ins.NOTICE.format(index),
                               'filer': 'insider' if own else 'company'}
    for issuer in json.loads((DATA / 'kap-universe.json').read_text())['companies']:
        ins.NAMES[re.sub(r'AS$', '', ins.fold(issuer['name']))] = issuer['codes']
    indexes = list(todo)

    def read(index):
        if todo[index]['filer'] == 'insider':
            return pdf_notice(index)
        return parse(page_text(index))

    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, parsed in zip(indexes, pool.map(read, indexes)):
            if not parsed or not parsed['rows']:
                continue
            item = {**todo[index], **parsed}
            # A parent reporting trades in another listed company's shares.
            folded = ins.fold(parsed.get('text', ''))
            targets = sorted({c for key, codes in ins.NAMES.items() if len(key) > 12
                              and re.search(re.escape(key) + r'(?:AS)?.{0,25}?PAY', folded) for c in codes} - set(item['codes']))
            if targets:
                item['targets'] = targets
            items[index] = item
    cutoff = (datetime.now(timezone(timedelta(hours=3))) - timedelta(days=365)).strftime('%Y-%m-%d')
    items = {k: v for k, v in items.items() if (v.get('published') or '') >= cutoff}
    OUT.write_text(json.dumps({'source': ins.SEARCH, 'items': dict(sorted(items.items()))}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(indexes)} bildirim okundu · toplam {len(items)} işlem bildirimi')


if __name__ == '__main__':
    main()
