"""Brokerage reports relayed by Foreks, and the trade ideas inside them.

Foreks publishes brokers' daily and weekly reports as "ANALİZ- … (Kurum)"
items. Only public, crawl-allowed files are read:
- https://www.foreks.com/sitemap-post.xml (the last ~2 days of items) and
  https://www.foreks.com/llms-analysis.txt (machine-readable list) for titles;
- https://news-content.foreks.com/<id> for each item's body, whose
  "Rapor İndir" link gives the report file (a PDF on news-files.foreks.com or
  the broker's own site).
Foreks' forecast backend needs a login and is not used.

Every item is kept as a feed entry (title, broker, date, link, share codes in
the title). Reports whose titles suggest share ideas are downloaded and read
with pdftotext; tables whose header names a stop/zarar-kes or target column,
and single-share notes giving "Hedef fiyat: …" and "Zarar-kes/Stop: …", become
trade ideas. Output: data/foreks-reports.json; feed 30 days, ideas 60 days.
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'foreks-reports.json'
LISTS = ['https://www.foreks.com/sitemap-post.xml', 'https://www.foreks.com/llms-analysis.txt']
CONTENT = 'https://news-content.foreks.com/{}'
ITEM = re.compile(r'https://www\.foreks\.com/haber/detay/([0-9a-f]{24})/FRKS/tr/(analiz-[a-z0-9-]+)/')
IDEAS = re.compile(r'öneri|takip|teknik|portföy|yıldız|hisse|trade|al"|sat"', re.I)
ISTANBUL = timezone(timedelta(hours=3))
NUM = r'\d{1,3}(?:[.]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?'
CACHE = Path('/tmp/mercek-foreks')
UA = {'User-Agent': 'Mozilla/5.0 (mercek research)'}


def get(url, binary=False):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=UA), timeout=60) as r:
                body = r.read()
            time.sleep(0.4)
            return body if binary else body.decode('utf-8', 'replace')
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def num(text):
    t = text.strip()
    if ',' not in t and t.count('.') > 1:
        return float(t.replace('.', ''))
    if ',' in t:
        return float(t.replace('.', '').replace(',', '.'))
    if t.count('.') == 1 and len(t.split('.')[1]) == 3 and float(t.replace('.', '')) >= 1000:
        return float(t.replace('.', ''))
    return float(t)


ROLE_WORDS = [  # order matters: first match wins
    (r'zarar[ -]?kes|zarar\s+durdur|stop(?:\s*loss)?', 'stop'),
    (r'hedef(?:\s*fiyat)?\s*\d?|takip\s*seviyesi\s*\d?|sat[ıi][şsm]\s*bölgesi\s*\d?|\d\.\s*sat[ıi][şm]', 'target'),
    (r'direnç\s*\d?|\d\.\s*direnç', 'res'),
    (r'destek\s*\d?|\d\.\s*destek', 'sup'),
    (r'son\s+kapanış(?:\s+fiyatı)?|kapanış(?:\s+fiyatı)?|son\s+fiyat|spot(?:\s+fiyat)?|giriş(?:\s+fiyatı)?|alış(?:\s+fiyatı)?|alım\s*bölgesi\s*\d?|\d\.\s*alım|^\s*fiyat', 'entry'),
    (r'pivot|h\.\s?o\.|rating|uzaklık|getiri|değişim|potansiyel|ağırlık|%', 'skip'),
]


def tr_lower(text):
    return text.replace('İ', 'i').replace('I', 'ı').lower()


def header_roles(line):
    line = tr_lower(line)
    roles = []
    pattern = '|'.join(f'(?P<g{i}>{p})' for i, (p, _) in enumerate(ROLE_WORDS))
    for m in re.finditer(pattern, line, re.I):
        roles.append(ROLE_WORDS[int(m.lastgroup[1:])][1])
    return roles


def table_ideas(text, known):
    ideas, roles = [], None
    for line in text.splitlines():
        low = tr_lower(line)
        first = re.match(r'\s*([A-Z][A-Z0-9]{2,5})\s', line)
        if re.search(r'stop|zarar|hedef', low) and not (first and first[1] in known):
            found = header_roles(line)
            if 'stop' in found and len([r for r in found if r != 'skip']) >= 2 and len(line.strip()) < 220:
                roles = found
            elif re.search(r'hisse|kod|sembol', low) and ('stop' in found or 'target' in found):
                roles = found
            continue
        if not roles:
            continue
        m = re.match(r'\s*([A-Z][A-Z0-9]{2,5})\b(.*)', line)
        if not m or m[1] not in known:
            if not m and len(re.findall(r'[a-zçğıöşü]{3,}', line)) >= 8:
                roles = None   # prose: the table has ended
            continue
        values = [num(v) for v in re.findall(NUM, m[2])]
        pairs = list(zip(roles, values)) if len(values) == len(roles) else None
        groups = [r for r in roles if r != 'skip']
        if pairs is None and groups and groups[-1] == 'stop' and len(values) > len(groups) and (len(values) - 1) % (len(groups) - 1 or 1) == 0:
            # Two-row headers ("ALIM BÖLGESİ / Seviye 1 Seviye 2"): split the levels evenly.
            each = (len(values) - 1) // (len(groups) - 1 or 1)
            pairs = [(g, v) for i, g in enumerate(groups[:-1]) for v in values[i * each:(i + 1) * each]] + [('stop', values[-1])]
        if pairs is None:
            continue
        idea = {'code': m[1], 'entry': None, 'stop': None, 'targets': [], 'supports': []}
        for role, v in pairs:
            if role == 'entry' and idea['entry'] is None:
                idea['entry'] = v
            elif role == 'stop':
                idea['stop'] = v
            elif role in ('target', 'res') and (role == 'target' or not any(r == 'target' for r in roles)):
                idea['targets'].append(v)
            elif role == 'sup':
                idea['supports'].append(v)
        if idea['stop'] is not None and (idea['targets'] or idea['entry']):
            ideas.append(idea)
    return ideas


TRACK = re.compile(rf'(\d{{2}})/(\d{{2}})/(\d{{4}})\s+([A-Z][A-Z0-9]{{2,5}})\s+({NUM})\s+({NUM})\s+-?[\d,]+%\s+({NUM})\s+-?[\d,]+%'
                   rf'(?:\s+({NUM})\s+(\d{{2}})/(\d{{2}})/(\d{{4}})\s+(-?[\d,]+)%)?\s+\d+\s+(Açık|Kapalı)')


def tracked_ideas(text, known):
    """Brokers' own trade-idea ledgers (Ak Yatırım): date, code, entry, target,
    stop, and for closed ideas the exit price, date and result."""
    out, horizon = [], None
    for line in text.splitlines():
        if re.match(r'\s*(Kısa|Orta|Uzun) Vadeli İşlem Önerileri', line):
            horizon = line.split()[0].lower()
        m = TRACK.search(line)
        if m and m[4] in known:
            idea = {'code': m[4], 'since': f'{m[3]}-{m[2]}-{m[1]}', 'entry': num(m[5]), 'targets': [num(m[6])], 'stop': num(m[7]),
                    'supports': [], 'status': 'açık' if m[13] == 'Açık' else 'kapalı', 'horizon': horizon}
            if m[8]:
                idea.update(exit=num(m[8]), exitDate=f'{m[11]}-{m[10]}-{m[9]}', result=num(m[12].replace('-', '')) * (-1 if m[12].startswith('-') else 1))
            out.append(idea)
    return out


DATED = re.compile(rf'\b([A-Z][A-Z0-9]{{2,5}})\s+(\d{{2}})\.(\d{{2}})\.(\d{{4}})\s+({NUM})\s+(AL|SAT)\s+({NUM})\s+({NUM})\s+({NUM})(?:\s+([A-ZÇĞİÖŞÜ]{{2,8}}))?\s*$')


def dated_ideas(text, known):
    """Lists like Şeker Yatırım's: code, idea date, close before, AL/SAT,
    target, stop, last close and status (İZLE = still open)."""
    out = []
    for line in text.splitlines():
        m = DATED.search(line)
        if m and m[1] in known:
            idea = {'code': m[1], 'since': f'{m[4]}-{m[3]}-{m[2]}', 'entry': num(m[5]), 'side': m[6], 'targets': [num(m[7])],
                    'stop': num(m[8]), 'supports': [], 'status': 'açık' if not m[10] or m[10] == 'İZLE' else 'kapalı'}
            if idea['status'] == 'kapalı':
                # The list gives the last close, not the exit: a closed idea left at its target or stop.
                last, target, stop = num(m[9]), idea['targets'][0], idea['stop']
                up = m[6] == 'AL'
                idea['exit'] = target if (last >= target if up else last <= target) else stop if (last <= stop if up else last >= stop) else last
                idea['result'] = round((idea['exit'] / idea['entry'] - 1) * 100 * (1 if m[6] == 'AL' else -1), 1)
            out.append(idea)
    return out


def block_ideas(text, known):
    """Notes per share: a '(CODE)' heading, then 'Kapanış', 'Hedef Fiyat' and
    'Zarar Durdur' each followed by a number within the next lines."""
    out, code, seen = [], None, {}
    for line in text.splitlines():
        if m := re.search(r'\(([A-Z][A-Z0-9]{2,5})\)', line):
            if m[1] in known:
                code, seen = m[1], {}
            continue
        if not code:
            continue
        for label, value in re.findall(rf'(Kapanış|Son Fiyat|Hedef Fiyat|Hedef|Zarar Durdur|Zarar Kes|Stop[- ]?Loss|Stop)\s+({NUM})\b', line, re.I):
            key = 'stop' if re.match(r'zarar|stop', label, re.I) else 'target' if label.lower().startswith('hedef') else 'entry'
            seen.setdefault(key, num(value))
        if 'stop' in seen and 'target' in seen:
            out.append({'code': code, 'entry': seen.get('entry'), 'stop': seen['stop'], 'targets': [seen['target']], 'supports': []})
            code, seen = None, {}
    return out


def note_idea(text, title, known):
    """Single-share notes: 'Hedef fiyat: 68,50- 73,00' and 'Zarar-kes: 61,00'."""
    codes = [c for c in re.findall(r'\b([A-Z][A-Z0-9]{3,5})\b', title) if c in known]
    if len(codes) != 1:
        return []
    stop = re.search(rf'(?:zarar[ -]?kes|stop(?:\s*loss)?)\s*[:=]?\s*({NUM})', text, re.I)
    target = re.search(rf'hedef\s*(?:fiyat\w*)?\s*[:=]\s*((?:{NUM})(?:\s*[-–/]\s*(?:{NUM}))*)', text, re.I)
    if not stop or not target:
        return []
    entry = re.search(rf'(?:spot\s*fiyat|son\s*fiyat|kapanış)\s*[:=]?\s*({NUM})', text, re.I)
    return [{'code': codes[0], 'entry': num(entry[1]) if entry else None, 'stop': num(stop[1]),
             'targets': [num(v) for v in re.findall(NUM, target[1])][:3], 'supports': []}]


def item_info(doc_id, slug, page):
    title = re.search(r'class="Header\s*"[^>]*>(.*?)<', page, re.S)
    title = ' '.join(html.unescape(title[1]).split()) if title else slug.replace('-', ' ')
    broker = re.search(r'\(([^()]{2,60})\)\s*$', title)
    stamp = re.search(r'(\d{2})/(\d{2})/(\d{4}) (\d{2}:\d{2})', page)
    date = f'{stamp[3]}-{stamp[2]}-{stamp[1]}T{stamp[4]}' if stamp else None
    link = re.search(r'href="([^"]+)"[^>]*>\s*Rapor İndir', page)
    return title, broker[1].strip() if broker else None, date, html.unescape(link[1]) if link else None


ALIASES = {'fibayatirim': 'Fiba Yatırım', 'kuveytturk': 'Kuveyt Türk Yatırım', 'kuveytturkyatirim': 'Kuveyt Türk Yatırım',
           'ikonmenkul': 'İkon Menkul', 'phillipcapital': 'Phillip Capital', 'qnbinvest': 'QNB Invest'}


def fold(text):
    text = text.replace('İ', 'I').replace('ı', 'i').upper()
    for a, b in (('Ç', 'C'), ('Ğ', 'G'), ('Ö', 'O'), ('Ş', 'S'), ('Ü', 'U')):
        text = text.replace(a, b)
    return re.sub(r'[^A-Z0-9 ]', ' ', text)


def canon(name):
    return ALIASES.get(re.sub(r'[^a-z0-9]', '', fold(name or '').lower()), name) if name else name


def name_keys(universe):
    """First two words of each issuer's name, when no other issuer shares them."""
    keys, firsts = {}, {}
    for issuer in universe:
        words = [w for w in fold(issuer['name']).split() if w not in ('AS', 'A', 'S')]
        if len(words) >= 2 and len(words[0]) >= 3:
            keys.setdefault(' '.join(words[:2]), []).append(issuer['codes'][0])
        if words and len(words[0]) >= 6 and words[0] not in COMMON:
            firsts.setdefault(words[0], []).append(issuer['codes'][0])
    out = {k: v[0] for k, v in keys.items() if len(v) == 1}
    out.update({k: v[0] for k, v in firsts.items() if len(v) == 1})
    return out


COMMON = {'ULUSLARARASI', 'TURKIYE', 'GLOBAL', 'ENERJI', 'YATIRIM', 'HOLDING', 'PETROL', 'TEKNIK', 'GUNLUK', 'PIYASA', 'STRATEJI',
          'EKONOMI', 'FINANS', 'SERMAYE', 'GAYRIMENKUL', 'BULTEN', 'HAFTALIK', 'DUNYA', 'AVRUPA', 'ISTANBUL', 'ANKARA', 'GENEL',
          'SANAYI', 'TICARET', 'DESTEK', 'DIRENC', 'HEDEF', 'ORTAK', 'ULUSAL', 'INVEST', 'CAPITAL', 'PORTFOY', 'MENKUL', 'KUVEYT', 'ZIRAAT', 'VAKIFLAR', 'GARANTI'}


def title_codes(title, known, keys):
    title = re.sub(r'\([^()]*\)\s*$', '', title)   # the broker's own name
    codes = {c for c in re.findall(r'\b([A-Z][A-Z0-9]{3,5})\b', title) if c in known}
    folded = ' ' + ' '.join(fold(title).split()) + ' '
    codes |= {code for key, code in keys.items() if f' {key} ' in folded}
    return sorted(codes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-files', type=int, default=60, help='Report files to download per run')
    args = parser.parse_args()
    CACHE.mkdir(exist_ok=True)
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    known = {c for i in universe for c in i['codes']}
    keys = name_keys(universe)
    old = json.loads(OUT.read_text()) if OUT.exists() else {'items': {}, 'ideas': {}}
    items, ideas = old['items'], old['ideas']
    found = {}
    for url in LISTS:
        try:
            for doc_id, slug in ITEM.findall(get(url)):
                found[doc_id] = slug
        except OSError as e:
            print('liste okunamadı', url, e)
    files = 0
    pdftotext = shutil.which('pdftotext')
    for doc_id, slug in sorted(found.items()):
        if doc_id in items:
            continue
        try:
            page = get(CONTENT.format(doc_id))
        except OSError:
            continue
        title, broker, date, link = item_info(doc_id, slug, page)
        codes = title_codes(title, known, keys)
        items[doc_id] = {'title': title, 'broker': broker, 'date': date, 'url': f'https://www.foreks.com/haber/detay/{doc_id}/FRKS/tr/{slug}/',
                         'codes': codes, 'file': link}
        if not (link and pdftotext and IDEAS.search(title)) or files >= args.max_files:
            continue
        pdf = CACHE / f'{doc_id}.pdf'
        try:
            if not pdf.exists():
                pdf.write_bytes(get(link, binary=True))
                files += 1
            text = subprocess.run([pdftotext, '-layout', str(pdf), '-'], capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        found_ideas = (tracked_ideas(text, known) + dated_ideas(text, known) or table_ideas(text, known) or block_ideas(text, known)
                       or note_idea(text, title, known))
        if found_ideas:
            ideas[doc_id] = {'date': (date or '')[:10] or None, 'broker': canon(broker), 'title': title, 'url': items[doc_id]['url'], 'rows': found_ideas}
            print(f'{title[:80]} · {len(found_ideas)} öneri')
    for doc_id, item in items.items():   # names and codes are re-derived for older entries too
        item['broker'] = canon(item['broker'])
        item['codes'] = title_codes(item['title'], known, keys)
    for rep in ideas.values():
        rep['broker'] = canon(rep['broker'])
    now = datetime.now(ISTANBUL)
    items = {k: v for k, v in items.items() if (v.get('date') or now.isoformat()) >= (now - timedelta(days=30)).isoformat()}
    ideas = {k: v for k, v in ideas.items() if (v.get('date') or now.isoformat()) >= (now - timedelta(days=60)).strftime('%Y-%m-%d')}
    OUT.write_text(json.dumps({'fetchedAt': now.isoformat(timespec='minutes'), 'source': 'https://www.foreks.com/analizler/',
                               'items': dict(sorted(items.items())), 'ideas': ideas}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(items)} rapor · {sum(len(v["rows"]) for v in ideas.values())} öneri ({len(ideas)} rapordan) · {files} dosya indirildi')


if __name__ == '__main__':
    main()
