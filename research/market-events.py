"""Corporate and market events from KAP for the site, in data/market-events.json.

Per listed code, over the last DAYS days:
- cb: dates of share-level circuit breakers ("Pay Bazında Devre Kesici");
- spk: SPK measure decisions published on KAP ("Sermaye Piyasası Kurulu Tedbir Kararı");
- capital: capital increases/decreases (type and bonus ratio read from the text);
- dividends: dividend decisions (gross TL per share read from the text);
- reports: financial report notices (date and period);
- ipo: first trading day and offer price, when the issuer listed in the window;
- funds3: fund managers' notices that their funds crossed 3% of a company.
Text-derived numbers stay null when the notice does not state them.
"""
import argparse
import importlib.util
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'market-events.json'
spec = importlib.util.spec_from_file_location('insiders', ROOT / 'research' / 'insiders.py')
ins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ins)
spec2 = importlib.util.spec_from_file_location('trades', ROOT / 'research' / 'insider-trades.py')
trades = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(trades)

SUBJECTS = {
    'cb': '4028328c5fc60da7016007ad193a5e2e',        # Pay Bazında Devre Kesici
    'spk': '8aca490d504b7afa01504bbff27602e3',       # SPK Tedbir Kararı
    'capital': '4028328d5988e2630159d5fd68661ff4',   # Sermaye Artırımı/Azaltımı
    'dividends': '4028328d5988e2630159d5fb51c81fe6', # Kar Payı Dağıtımı
    'reports': '4028328c594bfdca01594c0af9aa0057',   # Finansal Rapor
    'ipo': '8aca490d4ff02191014ff03637790093',       # Payların İşlem Görmeye Başlaması
    'ipoResult': '4028328d9c4c12ca019c6bf0a40c0518', # Halka Arz Sonuçları
}
OPEN = {'capital', 'dividends', 'ipoResult'}
FULL = True
NUM = r'[0-9][0-9.]*(?:,[0-9]+)?'
ISTANBUL = timezone(timedelta(hours=3))


def search_all(oid, days, member=True):
    rows = []
    for start, end in ins.windows(days, step=5):
        rows += ins.search([oid], start, end) if member else ins.search([oid], start, end)
    return rows


def body(index):
    text = trades.page_text(index)
    if FULL:
        return text
    for marker in ('oda_ExplanationTextBlock|', 'Ek Açıklamalar', 'Açıklamalar'):
        at = text.find(marker)
        if at >= 0:
            return text[at + len(marker):at + len(marker) + 1500]
    return text[:1500]


def num2(text):
    """Numbers written either 1.234,5 or 1,234.5."""
    if ',' in text and '.' in text and text.rfind('.') > text.rfind(','):
        return float(text.replace(',', ''))
    return ins.number(text)


def capital(text):
    out = {'type': 'bedelsiz' if re.search(r'bedelsiz', text, re.I) else 'bedelli' if re.search(r'bedelli', text, re.I)
           else 'tahsisli' if re.search(r'tahsisli', text, re.I) else 'azaltım' if re.search(r'azalt', text, re.I) else None}
    if m := re.search(r'%\s*([0-9][0-9.,]*)\s*(?:oranında\s+)?bedelsiz|bedelsiz[^.%]{0,60}%\s*([0-9][0-9.,]*)|iç\s+kaynaklardan[^%]{0,80}%\s*([0-9][0-9.,]*)\s*oranında', text, re.I):
        out['bonusPct'] = num2((m.group(1) or m.group(2) or m.group(3)).rstrip('.,'))
    if m := re.search(rf'%\s*({NUM})\s*(?:oranında\s+)?bedelli|bedelli[^.%]{{0,60}}%\s*({NUM})', text, re.I):
        out['rightsPct'] = ins.number(m.group(1) or m.group(2))
    return out


def dividend(text):
    out = {}
    # Form table: header ends with "... Nakit Kar Payı - Net(%)", then per group: gross TL, gross %, tax %, net TL, net %.
    start = text.find('Net(%)')
    if start >= 0:
        table = text[start:text.find('Pay Olarak Kar Payı', start) if text.find('Pay Olarak Kar Payı', start) > 0 else start + 800]
        rows = [(ins.number(g), ins.number(p)) for g, p in re.findall(rf'TR[A-Z0-9]{{10}}\s+({NUM})\s+({NUM})', table)]
        if rows:
            # The traded group's cash dividend; other groups may get none.
            out['grossPerShare'], out['grossPct'] = max(rows)
    if m := re.search(rf'(?:pay\s+başına|1\s*TL\s*nominal[^.]{{0,40}}için)[^.]{{0,40}}?brüt\s*({NUM})\s*TL|brüt\s*({NUM})\s*TL[^.]{{0,40}}pay\s+başına', text, re.I):
        out['grossPerShare'] = ins.number(m.group(1) or m.group(2))
    if m := re.search(r'(\d{2}\.\d{2}\.\d{4})\s*tarihinde\s*(?:başlan|ödenme|dağıtıl)', text, re.I):
        d = m.group(1).split('.')
        out['payDate'] = f'{d[2]}-{d[1]}-{d[0]}'
    out['decision'] = 'dağıtmama' if re.search(r'dağıtılmamas|dağıtım\s+yapılmamas', text, re.I) else 'dağıtım'
    if out.get('grossPerShare') == 0:
        out['decision'] = 'nakit yok'
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=120)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--reparse', action='store_true', help='Re-read capital and dividend notices already stored')
    args = parser.parse_args()
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
        ins.CACHE = args.cache
        trades.ins.CACHE = args.cache   # insider-trades loads its own copy of insiders.py
    known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'events': {}}
    events = old['events']   # disclosure index -> event, kept across runs
    if args.reparse:
        for index, event in events.items():
            if event['kind'] in ('capital', 'dividends') and '-' not in index:
                text = body(index)
                event.update(capital(text) if event['kind'] == 'capital' else dividend(text))
        OUT.write_text(json.dumps({'source': ins.SEARCH, 'events': dict(sorted(events.items()))}, ensure_ascii=False, separators=(',', ':')) + '\n')
        return
    for kind, oid in SUBJECTS.items():
        rows = search_all(oid, args.days)
        todo = []
        for row in rows:
            index = str(row.get('disclosureIndex') or '')
            listed = str(row.get('stockCodes') or '') or str(row.get('relatedStocks') or '')
            codes = [c.strip().removesuffix('.E') for c in listed.split(',') if c.strip().removesuffix('.E') in known]
            if not index.isdigit() or not codes or index in events:
                continue
            event = {'kind': kind, 'codes': codes, 'date': ins.stamp(row.get('publishDate')), 'summary': ' '.join(str(row.get('summary') or '').split())[:160],
                     'url': ins.NOTICE.format(index)}
            if kind == 'reports':
                event.update(year=row.get('year'), period=row.get('period'), rule=row.get('ruleType'))
            events[index] = event
            if kind in OPEN:
                todo.append(index)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for index, text in zip(todo, pool.map(body, todo)):
                kind = events[index]['kind']
                if kind == 'capital':
                    events[index].update(capital(text))
                elif kind == 'dividends':
                    events[index].update(dividend(text))
                elif kind == 'ipoResult':
                    if m := re.search(rf'(?:halka\s+arz\s+fiyatı|satış\s+fiyatı|pay\s+başına)[^.]{{0,40}}?({NUM})\s*TL', text, re.I):
                        events[index]['price'] = ins.number(m.group(1))
                events[index]['text'] = ' '.join(text.split())[:400]
        print(f'{kind}: {len(rows)} bildirim, {len(todo)} açıldı', flush=True)
    # Funds crossing 3% (fund managers' insider notices).
    for start, end in ins.windows(args.days):
        for row in ins.search([ins.INSIDER], start, end):
            title = str(row.get('kapTitle') or '')
            index = str(row.get('disclosureIndex') or '')
            if not re.search(r'PORTFÖY|EMEKLİLİK|HAYAT|SİGORTA|FON', title) or not index.isdigit() or index in events:
                continue
            text = trades.page_text(index)
            for m in re.finditer(rf'Pay Kodu\s*:\s*([A-Z0-9]{{3,6}})[^%]{{0,160}}?Oranı\s*\(%\)\s*:\s*({NUM})', text):
                if m[1] in known:
                    events[f'{index}-{m[1]}'] = {'kind': 'funds3', 'codes': [m[1]], 'date': ins.stamp(row.get('publishDate')),
                                                'holder': title, 'pct': ins.number(m[2]), 'url': ins.NOTICE.format(index)}
            events.setdefault(index, {'kind': 'checked', 'codes': [], 'date': ins.stamp(row.get('publishDate'))})
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=400)).strftime('%Y-%m-%d')
    events = {k: v for k, v in events.items() if (v.get('date') or '') >= cutoff}
    OUT.write_text(json.dumps({'source': ins.SEARCH, 'events': dict(sorted(events.items()))}, ensure_ascii=False, separators=(',', ':')) + '\n')
    counts = {}
    for v in events.values():
        counts[v['kind']] = counts.get(v['kind'], 0) + 1
    print('toplam', counts)


if __name__ == '__main__':
    main()
