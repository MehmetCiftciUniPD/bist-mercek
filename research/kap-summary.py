"""Collect 2026/09 KAP summary tables, retaining original periods and units."""
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
PERIOD = '2026/09'
SCOPE = '2026/9'
BALANCE = {
    'Varlıklar Toplamı': 'assets', 'Toplam Varlıklar': 'assets', 'Varlıklar': 'assets',
    'Dönen Varlıklar': 'currentAssets', 'Duran Varlıklar': 'noncurrentAssets',
    'Kısa Vadeli Yükümlülükler': 'currentLiabilities',
    'Uzun Vadeli Yükümlülükler': 'noncurrentLiabilities',
    'Toplam Özkaynaklar': 'equity', 'Özkaynaklar': 'equity',
    'Ana Ortaklığa Ait Özkaynaklar': 'parentEquity', 'Mevduat': 'deposits',
}
INCOME = {
    'Hasılat': 'revenue', 'Esas Faaliyet Kârı (Zararı)': 'operating',
    'Net Faaliyet Kârı (zararı)': 'operating',
    'Sürdürülen Faaliyetler Vergi Öncesi Kârı (Zararı)': 'pretax',
    'Vergi Öncesi Kârı (Zararı)': 'pretax',
    'Ana Ortaklık Payları': 'netIncome',
    'Dönem Kârının (Zararının) Dağılımı, Ana Ortaklık Payları': 'netIncome',
    'Dönem Kârının (Zararının) Dağılımı, Grubun Kârı (Zararı)': 'netIncome',
    'Dönem Kârı (Zararı)': 'groupNetIncome', 'Dönem Kârı veya Zararı': 'groupNetIncome', 'Net Dönem Kârı (Zararı)': 'groupNetIncome',
    'Net Faiz Geliri veya Gideri': 'netInterest',
    'Net Ücret ve Komisyon Gelirleri veya Giderleri': 'netFees',
    'Ticari Kâr veya Zarar (Net)': 'tradingIncome',
}


def rows(raw):
    return [
        [' '.join(cell.text_content().split()) for cell in row.xpath('./td|./th')]
        for row in html.fromstring(raw).xpath('//tr')
    ]


def parse(raw):
    groups = []
    for row in rows(raw):
        if len(row) < 2:
            continue
        if row[0].startswith(('FİNANSAL DURUM TABLOSU', 'KAR VEYA ZARAR', 'KÂR VEYA ZARAR')):
            groups.append((row[0], row[1:], {}))
        elif groups:
            groups[-1][2][row[0]] = row[1:]
    if not groups:
        return {}, {}, {}, None, 'KAP özet tablosu bulunamadı'
    results, previous, provenance = {}, {}, {}
    basis = None
    for heading, periods, items in groups:
        if PERIOD not in periods:
            continue
        column = periods.index(PERIOD)
        units = items.get('Sunum Para Birimi', [])
        scope = items.get('Finansal Tablo Niteliği', [])
        if len(units) <= column or len(scope) <= column:
            continue
        if scope[column] not in {'Konsolide', 'Konsolide Olmayan', 'Konsolide olmayan'}:
            continue
        if basis and scope[column].casefold() != basis.casefold():
            continue
        basis = scope[column]
        balance = heading.startswith('FİNANSAL DURUM')
        for label, key in (BALANCE if balance else INCOME).items():
            if label not in items:
                continue
            def read(index):
                values = items[label]
                if index >= len(values) or index >= len(units):
                    return None
                unit = re.sub(r'[.\s]', '', units[index]).upper()
                factors = {'TL': 1e-6, '1000TL': 1e-3, '1000000TL': 1}
                value = values[index].replace('.', '').replace(',', '.')
                if unit not in factors or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
                    return None
                return round(float(value) * factors[unit], 6)
            value = read(column)
            if value is None:
                continue
            results[key] = value
            provenance[key] = [label, items[label][column], units[column]]
            if balance and '2025/12' in periods:
                prior = periods.index('2025/12')
                if prior < len(scope) and scope[prior].casefold() == scope[column].casefold():
                    prior_value = read(prior)
                    if prior_value is not None:
                        previous[key] = prior_value
    reason = '2026/09 sütunu veya karşılaştırılabilir TL tablosu yok'
    return results, previous, provenance, basis, reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path('/tmp/mercek-kap-summary'))
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--limit-new', type=int, help='Limit the number of new network requests')
    parser.add_argument('--output-dir', type=Path, default=DATA)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    detailed = json.loads((DATA / 'research-2026-09.json').read_text())
    market = {r['code']: r for r in json.loads((DATA / 'market-2026-11-09.json').read_text())['companies']}
    at = datetime.now(timezone.utc).isoformat(timespec='seconds')
    jobs = [i for i in universe if not any(f'{c}:{SCOPE}' in detailed for c in i['codes'])]
    def primary(issuer):
        return max(issuer['codes'], key=lambda c: market.get(c, {}).get('marketCap') or -1)
    if args.limit_new is not None:
        cached_jobs = [i for i in jobs if (args.cache / f'{primary(i)}.html').exists()]
        new_jobs = [i for i in jobs if i not in cached_jobs]
        jobs = cached_jobs + new_jobs[:args.limit_new]
    def fetch(issuer):
        code = primary(issuer)
        url = issuer['kapProfile'].replace('/sirket-bilgileri/ozet/', '/sirket-finansal-bilgileri/')
        cached = args.cache / f'{code}.html'
        try:
            if not cached.exists():
                if args.offline:
                    return code, None, 'KAP özeti indirilemedi'
                with urlopen(url, timeout=16) as response:
                    raw = response.read()
                cached.write_bytes(raw)
            raw = cached.read_bytes()
            values, previous, fields, basis, reason = parse(raw)
            if not values.get('assets', 0) > 0:
                return code, None, reason
            return code, {
                'code': code, 'name': issuer['name'], 'source': url,
                'basis': basis, 'unit': 'Milyon TL', 'summaryOnly': True,
                'financialDate': '2026-09-30', 'importedAt': at,
                'documentHash': hashlib.sha256(raw).hexdigest(),
                'previous': previous, 'rawFields': fields, **values,
            }, None
        except (OSError, ValueError) as exc:
            return code, None, f'Kaynağa erişilemedi: {exc}'
    out, missing = {}, {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch, issuer) for issuer in jobs]
        for count, future in enumerate(as_completed(futures), start=1):
            code, data, error = future.result()
            if data:
                out[f'{code}:{SCOPE}'] = data
            else:
                missing[code] = error
            if count % 50 == 0 or count == len(jobs):
                print(f'{count}/{len(jobs)} · kaynaklı özet: {len(out)} · açık: {len(missing)}', flush=True)
                (args.output_dir / 'kap-summary-2026-09.json').write_text(json.dumps(dict(sorted(out.items())), ensure_ascii=False, separators=(',', ':')) + '\n')
                (args.output_dir / 'kap-summary-gaps.json').write_text(json.dumps(dict(sorted(missing.items())), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
