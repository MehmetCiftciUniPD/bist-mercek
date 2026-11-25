"""Brokerage target prices and weekly trade ideas compiled from public news pages.

- CNBC-e's weekly gallery "Borsada N hisseye M hedef fiyat" (id g40478; the
  short link redirects to the current week): per share, every broker's target
  price and recommendation, plus tables of brokers' revised targets (old and
  new target).
- Paratic's weekly articles on brokers' technical lists: per broker, share,
  last/entry price, targets (1-3) and stop-loss. New articles are found in
  Paratic's news sitemap and RSS feed by their address; known article
  addresses can be given with --url for a backfill.

Only the figures (code, broker, levels, recommendation) and the article link
are stored. Output: data/broker-calls.json. Ideas older than 60 days and
targets older than 120 days are dropped. Figures a table does not give stay null.
"""
import argparse
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'broker-calls.json'
CNBCE = 'https://www.cnbce.com/borsa/borsada-hedef-fiyat-g40478'
PARATIC_LISTS = ['https://paratic.com/news-sitemap.xml', 'https://paratic.com/feed/']
PARATIC_INDEX = 'https://paratic.com/sitemap_index.xml'
IDEA_URL = re.compile(r'https://paratic\.com/[a-z0-9-]*(?:stop-loss|zarar-kes|zarar-durdur|takip-listesi|takipteki-hisseler|hisse-onerileri|oneri-listesi|kritik-seviyeler|teknik-seviyeler|destek-ve-direnc|islem-stratejisi|haftanin-yildizlari|haftalik-hedef|hisse-rehberi|teknik-hisse)[a-z0-9-]*/')
ISTANBUL = timezone(timedelta(hours=3))
NUM = r'-?[0-9][0-9.]*(?:,[0-9]+)?'


def get(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0 (mercek research)'}), timeout=60) as r:
                return r.geturl(), r.read().decode('utf-8', 'replace')
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def clean(fragment):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', fragment)).replace('\xa0', ' ').split())


def num(text):
    m = re.search(NUM, (text or '').replace(' ', ''))
    if not m:
        return None
    t = m.group(0)
    if ',' not in t and t.count('.') == 1 and len(t.split('.')[1]) != 3:
        return float(t)        # 12.5 written with a dot
    return float(t.replace('.', '').replace(',', '.'))


def blocks(page):
    """Headings, paragraphs and tables in document order."""
    out = []
    for m in re.finditer(r'<(h[1-6]|p|strong)(?:\s[^>]*)?>(.*?)</\1>|<table.*?</table>', page, re.S):
        if m.group(0).startswith('<table'):
            rows = [[clean(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)] for r in re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(0), re.S)]
            out.append(('table', [r for r in rows if r]))
        else:
            text = clean(m.group(2))
            if text:
                out.append(('text', text))
    return out


ALIASES = {'kuveytturkyatirim': 'Kuveyt Türk Yatırım', 'phillipcapital': 'Phillip Capital', 'qnbinvest': 'QNB Invest',
           'garantibbvayatirim': 'Garanti BBVA Yatırım', 'ikonmenkul': 'İkon Menkul', 'a1capital': 'A1 Capital'}


def canon(name):
    if not name:
        return name
    key = re.sub(r'[^a-z0-9]', '', name.lower().replace('ı', 'i').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c').replace('ğ', 'g').replace('i̇', 'i'))
    return ALIASES.get(key, name.strip())


def broker_from(text):
    """'A1 Capital’in haftalık …' -> 'A1 Capital'."""
    m = re.match(r"(.{2,40}?)[’']\s?(?:in|ın|un|ün|nin|nın|nun|nün|e|a|ye|ya|dan|den|tan|ten|ndan|nden)\b", text)
    return canon(m[1].strip()) if m else None


def published(page):
    for pattern in (r'"datePublished"\s*:\s*"([^"]+)"', r'article:published_time" content="([^"]+)"', r'HABER GİRİŞ\s*(\d{1,2} \w+ \d{4})'):
        if m := re.search(pattern, page):
            return m[1][:10] if m[1][:4].isdigit() else turkish_date(m[1])
    return None


MONTHS = ['ocak', 'şubat', 'mart', 'nisan', 'mayıs', 'haziran', 'temmuz', 'ağustos', 'eylül', 'ekim', 'kasım', 'aralık']


def turkish_date(text):
    m = re.match(r'(\d{1,2}) (\w+) (\d{4})', text)
    if not m or m[2].lower() not in MONTHS:
        return None
    return f'{m[3]}-{MONTHS.index(m[2].lower()) + 1:02d}-{int(m[1]):02d}'


def cnbce(known):
    url, page = get(CNBCE)
    day = published(page)
    targets = []
    heading = None
    for kind, value in blocks(page):
        if kind == 'text':
            if re.search(r'\(([A-Z0-9]{3,6})\)\s*$', value) or broker_from(value):
                heading = value
            continue
        head = [h.lower() for h in value[0]]
        body = value[1:]
        code_in_heading = re.search(r'\(([A-Z0-9]{3,6})\)\s*$', heading or '')
        if 'aracı kurum' in head and code_in_heading and code_in_heading[1] in known:
            ib, it, ir = head.index('aracı kurum'), next((i for i, h in enumerate(head) if 'hedef' in h), None), next((i for i, h in enumerate(head) if 'tavsiye' in h), None)
            for r in body:
                if len(r) == len(head) and r[ib]:
                    targets.append({'code': code_in_heading[1], 'broker': canon(r[ib]), 'target': num(r[it]) if it is not None else None,
                                    'rec': r[ir] if ir is not None else None})
        elif 'hisse' in head and broker_from(heading or ''):
            broker = broker_from(heading)
            ih = head.index('hisse')
            iold = next((i for i, h in enumerate(head) if 'eski' in h), None)
            inew = next((i for i, h in enumerate(head) if 'yeni' in h or (h.startswith('hedef') and 'eski' not in h)), None)
            ir = next((i for i, h in enumerate(head) if 'tavsiye' in h), None)
            for r in body:
                code = (re.search(r'\b([A-Z0-9]{3,6})\b', r[ih]) or [None, None])[1] if len(r) == len(head) else None
                if code in known:
                    targets.append({'code': code, 'broker': broker, 'target': num(r[inew]) if inew is not None else None,
                                    'prev': num(r[iold]) if iold is not None else None, 'rec': r[ir] if ir is not None else None})
    # One line per (code, broker): broker tables carry the revision, keep the richer one.
    merged = {}
    for t in targets:
        key = (t['code'], t['broker'].lower())
        if key not in merged or t.get('prev') is not None:
            merged[key] = {**merged.get(key, {}), **{k: v for k, v in t.items() if v is not None}}
    return url, day, list(merged.values())


COLS = [('stop', r'stop|zarar'), ('target', r'hedef|direnç|satış|satım|takip seviyesi'), ('entry', r'alış|alım|giriş|kapanış|son fiyat|son \(|^son$|fiyat'), ('support', r'destek')]


def ideas_from(url, known):
    _, page = get(url)
    article = page[page.find('<article'):page.find('</article>')] if '<article' in page else page
    day = published(page)
    out, heading = [], None
    for kind, value in blocks(article):
        if kind == 'text':
            heading = value if broker_from(value) else heading
            continue
        head = [h.lower() for h in value[0]]
        roles = []
        for h in head:
            role = next((name for name, pattern in COLS if re.search(pattern, h)), None)
            if re.search(r'hisse|kod|şirket', h) and role != 'target':
                role = 'code'
            if 'getiri' in h or 'değişim' in h:
                role = None
            roles.append(role)
        if 'code' not in roles or not any(r in ('stop', 'target') for r in roles):
            continue
        for r in value[1:]:
            if len(r) != len(head):
                continue
            code = (re.search(r'\b([A-Z0-9]{3,6})\b', r[roles.index('code')]) or [None, None])[1]
            if code not in known:
                continue
            idea = {'code': code, 'broker': broker_from(heading or ''), 'entry': None, 'stop': None, 'targets': [], 'supports': []}
            for role, cell in zip(roles, r):
                v = num(cell)
                if role == 'entry' and idea['entry'] is None:
                    idea['entry'] = v
                elif role == 'stop':
                    idea['stop'] = v
                elif role == 'target' and v is not None:
                    idea['targets'].append(v)
                elif role == 'support' and v is not None:
                    idea['supports'].append(v)
            if idea['stop'] is not None or idea['targets']:
                out.append(idea)
    return day, out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', action='append', default=[], help='Paratic article to read (backfill)')
    args = parser.parse_args()
    known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'targets': {}, 'ideas': {}}
    today = datetime.now(ISTANBUL).strftime('%Y-%m-%d')
    targets, ideas = old['targets'], old['ideas']
    try:
        url, day, rows = cnbce(known)
        if rows:
            targets[day or today] = {'url': url, 'rows': rows}
        print(f'CNBC-e: {len(rows)} hedef fiyat ({day})')
    except OSError as e:
        print('CNBC-e okunamadı:', e)
    found = set(args.url)
    try:
        posts = re.findall(r'https://paratic\.com/post-sitemap(\d+)\.xml', get(PARATIC_INDEX)[1])
        newest = sorted({int(n) for n in posts})[-2:]
        PARATIC_LISTS.extend(f'https://paratic.com/post-sitemap{n}.xml' for n in newest)
    except OSError:
        pass
    for feed in PARATIC_LISTS:
        try:
            found |= set(IDEA_URL.findall(get(feed)[1]))
        except OSError:
            pass
    for url in sorted(found - set(ideas)):
        try:
            day, rows = ideas_from(url, known)
        except OSError:
            continue
        ideas[url] = {'date': day, 'rows': rows}
        print(f'{url} · {day} · {len(rows)} öneri')
    t_cut = (datetime.now(ISTANBUL) - timedelta(days=120)).strftime('%Y-%m-%d')
    i_cut = (datetime.now(ISTANBUL) - timedelta(days=60)).strftime('%Y-%m-%d')
    targets = {k: v for k, v in targets.items() if k >= t_cut}
    ideas = {k: v for k, v in ideas.items() if (v.get('date') or today) >= i_cut}
    OUT.write_text(json.dumps({'fetchedAt': datetime.now(ISTANBUL).isoformat(timespec='minutes'),
                               'sources': {'targets': CNBCE, 'ideas': 'https://paratic.com'},
                               'targets': dict(sorted(targets.items())), 'ideas': ideas}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(targets)} haftalık hedef derlemesi · {sum(len(v["rows"]) for v in ideas.values())} teknik öneri, {len(ideas)} yazı')


if __name__ == '__main__':
    main()
