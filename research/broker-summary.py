"""Fill missing 2026/09 snapshots with İş Yatırım's published TRY company tables."""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SOURCE = 'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx'
PERIOD = '2026/9'
BALANCE = {
    'dönen varlıklar': 'currentAssets', 'duran varlıklar': 'noncurrentAssets',
    'toplam varlıklar': 'assets', 'varlıklar toplamı': 'assets', 'aktif toplamı': 'assets',
    'kısa vadeli yükümlülükler': 'currentLiabilities', 'uzun vadeli yükümlülükler': 'noncurrentLiabilities',
    'toplam özkaynaklar': 'equity', 'özkaynaklar': 'equity', 'mevduat': 'deposits',
    'ana ortaklığa ait özkaynaklar': 'parentEquity',
}
INCOME = {
    'satış gelirleri': 'revenue', 'hasılat': 'revenue', 'esas faaliyet karı (zararı)': 'operating',
    'net faaliyet karı/zararı': 'operating', 'faaliyet karı (zararı)': 'operating',
    'ana ortaklık payları': 'netIncome', 'grubun karı / zararı': 'netIncome',
    'net dönem karı/zararı': 'groupNetIncome', 'dönem karı (zararı)': 'groupNetIncome',
    'net faiz geliri/gideri': 'netInterest', 'net ücret ve komisyon gelirleri/giderleri': 'netFees',
}
ALIASES = {'ç':'c', 'ı':'i', 'ğ':'g', 'ü':'u', 'ş':'s', 'ö':'o', 'â':'a', 'î':'i'}


def norm(text):
    text = text.replace('İ', 'i').replace('I', 'ı').lower().translate(str.maketrans(ALIASES))
    text = re.sub(r'^(?:[ivxlcdm]+\.|[0-9]+(?:\.[0-9]+)*\.?)\s+', '', text)
    return re.sub(r'\s*\([^)]*[+±−].*\)$', '', text).strip()


def parse(raw):
    tree = html.fromstring(raw)
    group = tree.xpath('//*[@id="ddlMaliTabloGroup"]/option[@selected]/text()')
    currency = tree.xpath('//*[@id="ddlMaliTabloExchange"]/option[1]/@value')
    periods = [tree.xpath(f'//*[@id="ddlMaliTabloDonem{i}"]/option[@selected]/@value') for i in range(1, 5)]
    periods = [p[0] if p else '' for p in periods]
    if not group or currency != ['TRY'] or PERIOD not in periods:
        return None
    current = periods.index(PERIOD) + 1
    values, previous, sources = {}, {}, {}
    section = ''
    balance = {norm(k): v for k, v in BALANCE.items()}
    income = {norm(k): v for k, v in INCOME.items()}
    for row in tree.xpath('//*[@id="tbodyMTablo"]/tr'):
        cells = [' '.join(c.text_content().split()) for c in row.xpath('./td')]
        if len(cells) == 1:
            section = norm(cells[0])
            continue
        if len(cells) < 5:
            continue
        is_balance = section == 'bilanco'
        if not is_balance and 'gelir tablosu' not in section and 'kar veya zarar' not in section:
            continue
        label = norm(cells[0])
        key = (balance if is_balance else income).get(label)
        if not key and not is_balance:
            key = next((mapped for name, mapped in income.items() if label.startswith(name+' (')), None)
        if not key:
            continue
        def value(index):
            s = cells[index].replace('.', '').replace(',', '.')
            return round(float(s) / 1e6, 6) if re.fullmatch(r'-?\d+(?:\.\d+)?', s) else None
        v = value(current)
        if v is None:
            continue
        values[key] = v
        sources[key] = [cells[0], cells[current], 'TL']
        prior = '2025/12' if is_balance else '2025/9'
        if prior in periods:
            v = value(periods.index(prior) + 1)
            if v is not None:
                previous[key] = v
    return (values, previous, sources, group[0].strip()) if values.get('assets', 0) > 0 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    market = {r['code']: r for r in json.loads((DATA / 'market-2026-11-09.json').read_text())['companies']}
    detailed = json.loads((DATA / 'research-2026-09.json').read_text())
    kap = json.loads((DATA / 'kap-summary-2026-09.json').read_text())
    cache = Path('/tmp/mercek-isy-summary')
    cache.mkdir(exist_ok=True)
    at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    jobs = []
    for issuer in universe:
        code = max(issuer['codes'], key=lambda c: market.get(c, {}).get('marketCap') or -1)
        if code not in market or any(f'{c}:{PERIOD}' in detailed or f'{c}:{PERIOD}' in kap for c in issuer['codes']):
            continue
        # Broker normalizes multiple share classes by profit allocation.
        if len(issuer['codes']) > 1:
            continue
        jobs.append((issuer, code))
    def fetch(job):
        issuer, code = job
        url = SOURCE + '?' + urlencode({'hisse': code})
        try:
            path = cache / f'{code}.html'
            if not path.exists():
                if args.offline:
                    return code, None, 'İş Yatırım tablosu indirilemedi'
                with urlopen(url, timeout=20) as response:
                    path.write_bytes(response.read())
            raw = path.read_bytes()
            parsed = parse(raw)
            if not parsed:
                return code, None, 'Dönem, TL veya kapsam teyit edilemedi'
            values, previous, fields, scope = parsed
            return code, {'code': code, 'name': issuer['name'], 'source': url,
                'basis': scope, 'unit': 'Milyon TL', 'summaryOnly': True,
                'provider': 'İş Yatırım', 'financialDate': '2026-09-30',
                'importedAt': at, 'documentHash': hashlib.sha256(raw).hexdigest(),
                'previous': previous, 'rawFields': fields, **values}, None
        except (OSError, ValueError) as exc:
            return code, None, str(exc)
    result, missing = {}, {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, job) for job in jobs]
        for count, f in enumerate(as_completed(futures), 1):
            code, record, error = f.result()
            if record:
                result[f'{code}:{PERIOD}'] = record
            else:
                missing[code] = error
            if count % 25 == 0 or count == len(jobs):
                print(f'{count}/{len(jobs)} · kaynaklı: {len(result)} · açık: {len(missing)}', flush=True)
                (DATA / 'broker-summary-2026-09.json').write_text(json.dumps(dict(sorted(result.items())), ensure_ascii=False, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
