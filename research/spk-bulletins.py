"""SPK weekly bulletins: criminal complaints, trading bans and fines per share.

Reads the 2026 bulletin PDFs listed on spk.gov.tr, takes the section
"SUÇ DUYURUSU, İDARİ PARA CEZASI İLE DİĞER YAPTIRIM VE TEDBİRLER", and for each
paragraph that names a listed share code in parentheses records the action
type (suç duyurusu / işlem yasağı / idari para cezası), the number of persons
listed under it and an excerpt. Output: data/spk-actions.json. Persons are
counted, never named on the site.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'spk-actions.json'
INDEX = 'https://spk.gov.tr/spk-bultenleri/2026-yili-spk-bultenleri'
CACHE = Path('/tmp/mercek-spk')
TYPES = [(r'suç\s+duyuru', 'suç duyurusu'), (r'işlem\s+yasağ', 'işlem yasağı'), (r'idari\s+para\s+ceza', 'idari para cezası')]


def get(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as r:
                return r.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3)


def bulletins():
    links = {}
    for page in range(1, 6):
        html = get(INDEX + (f'?s={page}' if page > 1 else '')).decode('utf-8', 'replace')
        found = re.findall(r'href="(https://spk\.gov\.tr/data/[0-9a-f]+/(2026-\d+)\.pdf)"', html)
        if not found:
            break
        for url, name in found:
            links[name] = url
    return links


def section(text):
    start = re.search(r'SUÇ DUYURUSU, İDARİ PARA CEZASI İLE DİĞER YAPTIRIM VE TEDBİRLER', text)
    if not start:
        return ''
    rest = text[start.end():]
    end = re.search(r'\n\s{4,}[A-Z]\.\s+[A-ZÇĞİÖŞÜ]', rest)
    return rest[:end.start()] if end else rest


def main():
    if not shutil.which('pdftotext'):
        sys.exit('pdftotext gerekli.')
    CACHE.mkdir(exist_ok=True)
    known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'bulletins': {}, 'actions': []}
    done, actions = old['bulletins'], old['actions']
    for name, url in sorted(bulletins().items(), key=lambda kv: int(kv[0].split('-')[1])):
        if name in done:
            continue
        pdf = CACHE / f'{name}.pdf'
        if not pdf.exists():
            pdf.write_bytes(get(url))
        text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], capture_output=True, text=True).stdout
        text = re.sub(r'MERKEZ Eskişehir Yolu[^\n]*\n[^\n]*İSTANBUL TEMSİLCİLİĞİ[^\n]*\n?', '', text)
        date = re.search(r'(\d{2})[./](\d{2})[./](2026)', text[:3000])
        day = f'{date[3]}-{date[2]}-{date[1]}' if date else None
        part = section(text)
        # Paragraphs start with an indented sentence naming the share; tables follow.
        current = 'diğer'
        for block in re.split(r'\n\s*\n', part):
            flat = ' '.join(block.split())
            for pattern, label in TYPES:
                if re.match(r'^\d?\.?\s*' + pattern, flat, re.I) or re.fullmatch(r'\d\.\s*[^.]{0,60}', flat):
                    current = next((lab for pat, lab in TYPES if re.search(pat, flat, re.I)), current)
            codes = [c for c in dict.fromkeys(re.findall(r'\(([A-Z0-9]{3,6})\)', flat)) if c in known]
            if not codes or len(flat) < 80:
                continue
            kind = next((lab for pat, lab in TYPES if re.search(pat, flat, re.I)), current)
            following = part[part.find(block) + len(block):][:6000]
            nxt = re.search(r'\n\s*\n\s{4,}\S[^\n]{60,}\(([A-Z0-9]{3,6})\)', following)
            table = following[:nxt.start()] if nxt else following
            persons = len(re.findall(r'\d{2}\*{5,}\d{2}', table))
            ban = re.search(r'(\d+)\s*(?:yıl|ay)\s*süreyle', flat)
            for code in codes:
                actions.append({'bulletin': name, 'date': day, 'code': code, 'type': kind, 'persons': persons,
                                'ban': ban.group(0) if ban else None, 'text': flat[:400], 'url': url})
        done[name] = day
    OUT.write_text(json.dumps({'source': INDEX, 'bulletins': done, 'actions': actions}, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(done)} bülten · {len(actions)} kayıt · {len({a["code"] for a in actions})} hisse')


if __name__ == '__main__':
    main()
