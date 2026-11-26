"""Data health check: is every source still delivering fresh, non-empty data?

Collectors run with continue-on-error, so a broken source would otherwise go
unnoticed: the step passes and the file silently ages. For each data file this
reads the newest timestamp it carries and its record count, compares them with
a limit, and writes data/health.json (shown on the site). With --issue it also
opens, updates or closes a GitHub issue through the gh CLI (needs GH_TOKEN).
Limits are in calendar days and allow for weekends and holidays.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'health.json'
ISTANBUL = timezone(timedelta(hours=3))
ISSUE_TITLE = 'Veri sağlığı uyarısı'


def newest(values):
    values = [str(v)[:16] for v in values if v]
    return max(values) if values else None


# name, label, file, (newest timestamp, record count), max age in days, min records
CHECKS = [
    ('prices', 'Kapanış fiyatları (İş Yatırım)', 'market-latest.json', lambda d: (d.get('date'), len(d['companies'])), 4, 400),
    ('history', 'Haftalık fiyat geçmişi (Yahoo)', 'price-history.json', lambda d: (d.get('fetchedAt'), len(d.get('companies', {}))), 9, 400),
    ('smc', 'Smart Money okuması', 'smc-summary.json', lambda d: (d.get('date'), len(d['companies'])), 4, 400),
    ('scorecard', 'Temel analiz skor kartı', 'scorecard.json', lambda d: (d.get('priceDate'), len(d['companies'])), 4, 400),
    ('buybacks', 'Geri alımlar (KAP)', 'buybacks.json', lambda d: (newest(v['date'] for v in d['items'].values()), len(d['items'])), 5, 50),
    ('insiders', 'Yönetici ve ortak işlemleri (KAP)', 'insider-trades.json', lambda d: (newest(v.get('published') for v in d['items'].values()), len(d['items'])), 5, 50),
    ('funds', 'Fondan borsa dışı alımlar (KAP)', 'fund-transfers.json', lambda d: (newest(v['date'] for v in d['items'].values()), len(d['items'])), 30, 1),
    ('holdings', 'Tasfiyedeki fon portföyleri (Fonoloji)', 'fund-holdings.json', lambda d: (d.get('fetchedAt'), len(d.get('companies', {}))), 4, 10),
    ('events', 'Şirket olayları, devre kesici (KAP)', 'market-events.json', lambda d: (newest(v.get('date') for v in d['events'].values()), len(d['events'])), 4, 100),
    ('spk', 'SPK bültenleri', 'spk-actions.json', lambda d: (newest(d['bulletins'].values()), len(d['actions'])), 14, 10),
    ('isy', 'İş Yatırım tavsiyeleri ve konsensüs', 'broker-reports.json', lambda d: (d.get('fetchedAt'), len(d.get('isy', {}))), 3, 40),
    ('calls', 'Kurum hedefleri (CNBC-e) ve teknik öneriler (Paratic)', 'broker-calls.json',
     lambda d: (d.get('fetchedAt'), sum(len(v['rows']) for v in d['targets'].values())), 3, 100),
    ('cnbce', 'CNBC-e haftalık hedef derlemesi', 'broker-calls.json', lambda d: (max(d['targets'], default=None), 1 if d['targets'] else 0), 21, 1),
    ('foreks', 'Kurum raporları (Foreks)', 'foreks-reports.json', lambda d: (newest(v.get('date') for v in d['items'].values()), len(d['items'])), 4, 20),
    ('foreign', 'Yabancı payı (İş Yatırım)', 'foreign-ratios.json', lambda d: (d.get('date'), len(d['days'].get(d.get('date'), {}))), 5, 100),
    ('takas', 'Kurumsal takas değişimi (QNB, OCR)', 'takas.json', lambda d: (max(d['days'], default=None), len(d['days'][max(d['days'])]['rows']) if d['days'] else 0), 4, 5),
    ('flows', 'Haftalık yabancı akımları (TCMB, Şeker/Bizim)', 'foreign-flows.json', lambda d: (max(d['weeks'], default=None), len(d['weeks'])), 14, 1),
    ('karne', 'Kurum karnesi', 'broker-scorecard.json', lambda d: (d.get('generatedAt'), len(d['ideas'])), 3, 1),
    ('summary', 'Günlük özet', 'daily-summary.json', lambda d: (d.get('generatedAt'), 1 if d.get('facts') else 0), 3, 1),
]


def run():
    today = datetime.now(ISTANBUL)
    results = []
    for name, label, file, get, max_age, min_n in CHECKS:
        path = DATA / file
        row = {'name': name, 'label': label, 'file': file, 'maxAge': max_age, 'min': min_n}
        try:
            stamp, n = get(json.loads(path.read_text()))
        except (OSError, ValueError, KeyError, TypeError) as e:
            results.append({**row, 'ok': False, 'problem': f'okunamadı ({type(e).__name__})'})
            continue
        age = None
        if stamp:
            day = datetime.fromisoformat(stamp[:10]).replace(tzinfo=ISTANBUL)
            age = (today - day).days
        problems = []
        if age is None:
            problems.append('tarih yok')
        elif age > max_age:
            problems.append(f'{age} gündür güncellenmedi')
        if n < min_n:
            problems.append(f'kayıt sayısı {n} (en az {min_n})')
        results.append({**row, 'ok': not problems, 'latest': stamp, 'age': age, 'n': n, 'problem': ', '.join(problems) or None})
    return results


def issue(results):
    bad = [r for r in results if not r['ok']]
    found = subprocess.run(['gh', 'issue', 'list', '--state', 'open', '--search', f'"{ISSUE_TITLE}" in:title', '--json', 'number'],
                           capture_output=True, text=True)
    numbers = [i['number'] for i in json.loads(found.stdout or '[]')] if found.returncode == 0 else []
    if not bad:
        for number in numbers:
            subprocess.run(['gh', 'issue', 'close', str(number), '--comment', 'Tüm kaynaklar yeniden güncel.'])
        return
    body = '\n'.join(['Aşağıdaki kaynaklar beklenen sürede güncellenmedi ya da boş geldi. Kaynak sitesi değişmiş olabilir; '
                      'ilgili betiği (research/) çalıştırıp çıktısına bakın.', '',
                      *[f"- **{r['label']}** (`data/{r['file']}`): {r['problem']}" for r in bad], '',
                      f"Son kontrol: {datetime.now(ISTANBUL).strftime('%d.%m.%Y %H:%M')}"])
    if numbers:
        subprocess.run(['gh', 'issue', 'edit', str(numbers[0]), '--body', body])
    else:
        subprocess.run(['gh', 'issue', 'create', '--title', ISSUE_TITLE, '--body', body])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issue', action='store_true', help='Open/update/close the GitHub issue')
    args = parser.parse_args()
    results = run()
    OUT.write_text(json.dumps({'checkedAt': datetime.now(ISTANBUL).isoformat(timespec='minutes'), 'checks': results},
                              ensure_ascii=False, indent=1) + '\n')
    bad = [r for r in results if not r['ok']]
    for r in results:
        print(('✓' if r['ok'] else '⚠'), r['label'], r.get('latest'), r.get('n'), r.get('problem') or '')
    if args.issue and os.environ.get('GH_TOKEN'):
        issue(results)
    print(f'{len(results) - len(bad)}/{len(results)} kaynak sağlıklı')


if __name__ == '__main__':
    main()
