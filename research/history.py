"""Collect multi-year statement history from İş Yatırım's published TRY tables.

Writes data/history.json (annual 2020-2025 plus 2026 interim columns) and
data/history-gaps.json. 2026/9 columns are compared with the KAP summary and
differences are stored as warnings on the issuer.

Values are stored as reported in each period's own filing, in million TL.
Years are therefore not restated to a common purchasing power (TMS 29).
"""
import argparse
import hashlib
import json
import re
import time
from http.client import HTTPException
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
API = 'https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo'
CARD = 'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx'
BATCHES = [
    ['2025/12', '2024/12', '2023/12', '2022/12'],
    ['2021/12', '2020/12', '2026/9', '2026/6'],
    # Same-period comparison column for the 2026/9 scorecard (the endpoint wants four slots).
    ['2025/9', '2025/9', '2025/9', '2025/9'],
]
PERIODS = ['2020/12', '2021/12', '2022/12', '2023/12', '2024/12', '2025/9', '2025/12', '2026/6', '2026/9']
GROUPS = ['XI_29', 'UFRS_K', 'UFRS']
BASIS = {'XI_29': 'Seri XI No:29', 'UFRS_K': 'Konsolide (finansal kuruluş)', 'UFRS': 'Konsolide olmayan (finansal kuruluş)'}
SUMMARY_PERIOD = '2026/9'

# Industrial template: stable item codes.
INDUSTRIAL = {
    '1BL': 'assets', '1A': 'currentAssets', '1AK': 'noncurrentAssets', '1AA': 'cash',
    '2A': 'currentLiabilities', '2B': 'noncurrentLiabilities', '2AA': 'shortDebt', '2BA': 'longDebt',
    '2N': 'equity', '2O': 'parentEquity', '3C': 'revenue', '3D': 'grossProfit', '3DF': 'operating',
    '3I': 'pretax', '3L': 'groupNetIncome', '3Z': 'netIncome', '4B': 'depreciation',
    '4C': 'ocf', '4CAI': 'capex', '4CB': 'fcf',
    # Inputs for the fundamental scorecard (research/scorecard.py).
    '1AC': 'receivables', '1AF': 'inventories', '1BG': 'ppe',
    '2OCD': 'restrictedReserves', '2OCE': 'priorYearsEarnings', '2OCF': 'periodEarnings',
    '3DA': 'marketingExpense', '3DB': 'adminExpense', '4CBC': 'capitalIncrease',
}
INDUSTRIAL_TOTAL = '2ODB'
# Financial templates (banks, insurers, leasing): codes differ, so match labels.
FINANCIAL = [
    (r'^aktif toplami$', 'assets'),
    (r'^mevduat$|^toplanan fonlar$', 'deposits'),
    (r'^krediler$|^krediler \(net\)$', 'loans'),
    (r'^ozkaynak(?:lar)?$|^ozsermaye toplami$', 'equity'),
    (r'^net faiz geliri/gideri|^net kar payi geliri/gideri', 'netInterest'),
    (r'^net ucret ve komisyon gelirleri/giderleri', 'netFees'),
    (r'^net faaliyet kari/zarari', 'operating'),
    (r'^genel teknik bolum dengesi', 'operating'),
    (r'^surdurulen faaliyetler vergi oncesi k/z', 'pretax'),
    (r'^donem kari ve zarari$', 'pretax'),
    (r'^net donem kari/zarari|^donem net kari veya zarari$', 'groupNetIncome'),
    (r'^grubun kari/zarari$', 'netIncome'),
    (r'^cari varliklar toplami$', 'currentAssets'),
    (r'^cari olmayan varliklar toplami$', 'noncurrentAssets'),
    (r'^kisa vadeli yukumlulukler toplami$', 'currentLiabilities'),
    (r'^uzun vadeli yukumlulukler toplami$', 'noncurrentLiabilities'),
]
FINANCIAL_TOTAL = r'^pasif toplami$'
FOLD = str.maketrans('çığüşöâî', 'cigusoai')


def norm(text):
    text = text.replace('İ', 'i').replace('I', 'ı').lower().translate(FOLD)
    text = ' '.join(text.split())
    # Drop outline prefixes such as "XVI.", "16.4.2", "A-", "III -", "1-".
    text = re.sub(r'^(?:[ivxlcdm]+\s*[.\-–]|[0-9]+(?:\.[0-9]+)*\.?\s*-?|[a-z]\s*-)\s*', '', text)
    return text.strip()


def number(raw):
    if raw in (None, '', 'None'):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def url_for(code, group, batch):
    query = {'companyCode': code, 'exchange': 'TRY', 'financialGroup': group}
    for index, period in enumerate(batch, start=1):
        year, month = period.split('/')
        query[f'year{index}'] = year
        query[f'period{index}'] = month
    return API + '?' + urlencode(query)


def download(code, group, index, cache, offline):
    path = cache / f'{code}.{group}.{index}.json'
    if not path.exists():
        if offline:
            return None
        request = Request(url_for(code, group, BATCHES[index]), headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    raw = response.read()
                json.loads(raw)
                path.write_bytes(raw)
                break
            except (OSError, ValueError, HTTPException):
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
    return path.read_bytes()


def extract(group, items, slot):
    """Return ({field: million TL}, {field: [label, raw]}, liabilities total) for one column."""
    values, labels, total = {}, {}, None
    for item in items:
        raw = item.get(f'value{slot}')
        value = number(raw)
        label = ' '.join((item.get('itemDescTr') or '').split())
        if group == 'XI_29':
            key = INDUSTRIAL.get(item['itemCode'])
            if item['itemCode'] == INDUSTRIAL_TOTAL:
                total = value
        else:
            folded = norm(label)
            key = next((field for pattern, field in FINANCIAL if re.search(pattern, folded)), None)
            if re.search(FINANCIAL_TOTAL, folded):
                total = value
        # Financial outlines repeat a label on an empty sub-line; the first non-zero line wins.
        if key and value is not None and (key not in values or (group != 'XI_29' and values[key] == 0)):
            values[key] = round(value / 1e6, 3)
            labels[key] = [label, raw]
    if group != 'XI_29':
        for key in ('loans', 'deposits'):
            if values.get(key) == 0:
                del values[key], labels[key]
    return values, labels, total


def collect(issuer, code, cache, offline):
    """Read every statement template and keep the one with the newest, longest history."""
    best = None
    for group in GROUPS:
        try:
            raws = [download(code, group, index, cache, offline) for index in range(len(BATCHES))]
        except (OSError, ValueError, HTTPException) as exc:
            return None, f'İş Yatırım tablosuna erişilemedi: {exc}'
        if any(raw is None for raw in raws):
            return None, 'İş Yatırım tablosu indirilemedi'
        periods, digest, rejected = {}, hashlib.sha256(), []
        for batch, raw in zip(BATCHES, raws):
            digest.update(raw)
            items = json.loads(raw).get('value') or []
            for slot, period in enumerate(batch, start=1):
                values, labels, total = extract(group, items, slot)
                assets = values.get('assets')
                if not assets or assets <= 0:
                    continue
                # A column is kept only when the balance sheet closes.
                if total is None or abs(total / 1e6 - assets) > max(0.5, abs(assets) * 1e-4):
                    rejected.append(period)
                    continue
                if group != 'XI_29' and 'netIncome' not in values and 'groupNetIncome' in values:
                    values['netIncome'] = values['groupNetIncome']
                    labels['netIncome'] = labels['groupNetIncome']
                periods[period] = (values, labels)
        if not periods:
            continue
        rank = (max(PERIODS.index(p) for p in periods), len(periods))
        if best is None or rank > best[0]:
            best = (rank, {
                'code': code, 'name': issuer['name'], 'group': group, 'basis': BASIS[group],
                'source': CARD + '?' + urlencode({'hisse': code}), 'documentHash': digest.hexdigest(),
                'periods': periods, 'rejected': rejected,
            })
        if group == 'XI_29':
            break
    if best:
        return best[1], None
    return None, 'İş Yatırım mali tablosu yok veya bilanço toplamı tutmuyor'


CHECKED = {'assets': 'toplam varlıklar', 'equity': 'özkaynaklar', 'revenue': 'hasılat', 'netIncome': 'net kâr'}


def kap_differences(kap, record):
    """Describe 2026/9 fields where this table differs from the KAP summary by more than 0.5%."""
    if not kap or SUMMARY_PERIOD not in record['periods']:
        return []
    values = record['periods'][SUMMARY_PERIOD][0]
    fields = [label for key, label in CHECKED.items()
              if kap.get(key) is not None and values.get(key) is not None
              and abs(kap[key] - values[key]) > max(1, abs(kap[key]) * 0.005)]
    if not fields:
        return []
    return [f"2026/9 döneminde İş Yatırım tablosu KAP özetinden farklı: {', '.join(fields)}. "
            f"KAP özeti {kap.get('basis', 'kapsam belirtilmemiş')} esaslıdır; bu şirketin geçmiş serisi KAP ile teyit edilmeden kullanılmamalı."]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path('/tmp/mercek-isy-history'))
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    market = {r['code']: r for r in json.loads((DATA / 'market-2026-11-09.json').read_text())['companies']}
    kap = json.loads((DATA / 'kap-summary-2026-09.json').read_text())
    jobs = [(issuer, max(issuer['codes'], key=lambda c: market.get(c, {}).get('marketCap') or -1)) for issuer in universe]
    if args.limit:
        jobs = jobs[:args.limit]
    at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if args.offline and (DATA / 'history.json').exists():
        # Reprocessing a cache does not change when the source was read.
        at = json.loads((DATA / 'history.json').read_text()).get('collectedAt', at)
    companies, gaps = {}, {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(collect, issuer, code, args.cache, args.offline): (issuer, code) for issuer, code in jobs}
        for count, future in enumerate(as_completed(futures), start=1):
            issuer, code = futures[future]
            record, error = future.result()
            if not record:
                gaps[code] = error
            else:
                available = [p for p in PERIODS if p in record['periods']]
                fields = sorted({f for p in available for f in record['periods'][p][0]})
                companies[code] = {
                    'name': record['name'], 'group': record['group'], 'basis': record['basis'],
                    'source': record['source'], 'documentHash': record['documentHash'],
                    'periods': available,
                    'values': {f: [record['periods'][p][0].get(f) for p in available] for f in fields},
                }
                if record['rejected']:
                    companies[code]['rejected'] = sorted(record['rejected'])
                warnings = kap_differences(kap.get(f'{code}:{SUMMARY_PERIOD}'), record)
                if warnings:
                    companies[code]['warnings'] = warnings
            if count % 50 == 0 or count == len(jobs):
                print(f'{count}/{len(jobs)} · geçmiş: {len(companies)} · açık: {len(gaps)}', flush=True)
    history = {
        'source': CARD, 'collectedAt': at, 'unit': 'Milyon TL', 'periodOrder': PERIODS,
        'note': 'Değerler her dönemin kendi raporunda yayımlandığı tutardır; yıllar ortak satın alma gücüne (TMS 29) getirilmemiştir. Ara dönem gelir ve nakit akışı kalemleri kümülatiftir.',
        'companies': dict(sorted(companies.items())),
    }
    compact = dict(ensure_ascii=False, separators=(',', ':'))
    (DATA / 'history.json').write_text(json.dumps(history, **compact) + '\n')
    (DATA / 'history-gaps.json').write_text(json.dumps(dict(sorted(gaps.items())), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
