"""Institutional custody (takas) changes per share, read from QNB Invest's daily images.

QNB Invest's "Kurumsal Takas Değişimleri" is relayed on Foreks every morning as
images (no text or PDF). For the 20 BIST-100 shares with the largest daily
change it gives the change in institutional custody share (%) and amount
(million TL) over 1, 5, 10 and 20 trading days, split into foreign investors
and funds. The images are read with Tesseract OCR, which misreads digits and
minus signs often enough that a raw read is not publishable, so every value is
checked before it is kept:
- each image is read with several preprocessing settings and readings vote;
- the total appears twice (period summary table and period block) and both
  reads must agree;
- foreign + funds must equal the total (the source's own identity), and that
  identity fixes the signs of the parts;
- the sign of the total needs a clear majority of reads (or, for the day, the
  ARTAN/AZALAN section it is listed in).
A value that fails any check is left out. Output: data/takas.json, 60 days.
"""
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'takas.json'
CONTENT = 'https://news-content.foreks.com/{}'
TITLE = re.compile(r'Kurumsal Takas Değişimleri', re.I)
ISTANBUL = timezone(timedelta(hours=3))
UA = {'User-Agent': 'Mozilla/5.0 (mercek research)'}
CONFIGS = [(4, 'L', 150), (4, 'max', 170), (3, 'L', 150), (3, 'max', 170), (5, 'L', 150), (4, 'L', 165), (5, 'max', 175)]
WHITELIST = ['-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,%- ']
PERIODS = ['d', 'w5', 'w10', 'w20']


def get(url, binary=False):
    with urlopen(Request(url, headers=UA), timeout=60) as r:
        body = r.read()
    return body if binary else body.decode('utf-8', 'replace')


def ocr(image_bytes, scale, mode, cut):
    from PIL import Image, ImageChops
    import io
    im = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    if mode == 'max':
        r, g, b = im.split()
        gray = ImageChops.lighter(ImageChops.lighter(r, g), b)
    else:
        gray = im.convert('L')
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        gray.point(lambda p: 255 if p > cut else 0).save(f.name)
        return subprocess.run(['tesseract', f.name, '-', '--psm', '6', *WHITELIST], capture_output=True, text=True).stdout


def tokens(rest):
    rest = rest.replace('--', '-').replace('—', '-')
    rest = re.sub(r'(-?\d{1,3})[.,](\d{3})\s+(\d)\b', r'\1\2.\3', rest)      # "2.275 4" -> "2275.4"
    rest = re.sub(r'(-?\d{1,3}),(\d{3}\.\d)', r'\1\2', rest)                 # "2,323.0" -> "2323.0"
    out = []
    for t in re.findall(r'-?\d+(?:\.\d+)?%?', rest):
        out.append(('pct' if t.endswith('%') else 'tl', t.startswith('-'), abs(float(t.rstrip('%')))))
    return out


def appearances(text, known=None):
    """code -> list of token lists, one per table row the code appears in.
    Only listed share codes count, so headings like ARTAN do not shift rows."""
    out = {}
    for line in text.splitlines():
        if (m := re.match(r'\s*([A-Z]{4,6})\b(.*)', line)) and (known is None or m[1] in known):
            out.setdefault(m[1], []).append(tokens(m[2]))
    return out


def tl(row):
    return [t for t in row if t[0] == 'tl']


def pct(row):
    return [t for t in row if t[0] == 'pct']


def best(counter, n):
    return [v for v, _ in counter.most_common(n)]


def solve(t_sum, t_blk, y_c, f_c, minus, section=None):
    """Pick (total, foreign, funds) that satisfy every check, or None.

    minus: cell -> [reads showing a minus sign, reads of that cell] for cells
    't', 'y', 'f' (amounts and percentages). OCR often drops a minus sign and
    rarely invents one, so a minus seen in a cell is the stronger evidence.
    section: +n / -n votes from the daily ARTAN/AZALAN sections."""
    found = []
    for t1, t2, y, f in product(best(t_sum, 3), best(t_blk, 3), best(y_c, 3), best(f_c, 3)):
        if abs(t1 - t2) > (0.55 if t1 == int(t1) or t2 == int(t2) else 0.05):
            continue
        t = t2 if t2 != int(t2) or t1 == int(t1) else t1   # the block value carries the decimal
        for sign in (1, -1):
            fits = [(sy * y, sf * f) for sy in (1, -1) for sf in (1, -1) if abs(sy * y + sf * f - t * sign) <= 0.15]
            if len(fits) != 1:
                continue
            yv, fv = fits[0]
            expected = {'t': sign, 'y': 1 if yv >= 0 else -1, 'f': 1 if fv >= 0 else -1}
            evidence = 0
            for cell, (neg, n) in minus.items():
                if abs({'t': t, 'y': y, 'f': f}[cell]) < 0.05:
                    continue
                evidence += neg if expected[cell] < 0 else -2 * neg
            evidence += 3 * section * sign if section else 0
            score = t_sum[t1] + t_blk[t2] + y_c[y] + f_c[f]
            found.append((score, evidence, round(t * sign, 1), round(yv, 1), round(fv, 1)))
    if not found:
        return None
    top = max(x[0] for x in found)
    best_reads = [x for x in found if x[0] == top]
    values = {x[2:] for x in best_reads}
    if len(values) > 2:
        return None
    best_reads.sort(key=lambda x: -x[1])
    if len(best_reads) > 1 and best_reads[0][2:] != best_reads[1][2:] and best_reads[0][1] - best_reads[1][1] < 2:
        return None   # the sign is not settled
    if best_reads[0][1] < 0 or top < 2 * len(CONFIGS):
        return None
    _, _, t, y, f = best_reads[0]
    return {'t': t, 'y': y, 'f': f}


def parse(images, known=None):
    """images: [summary+daily, 5-day+10-day, 20-day] as bytes."""
    if known is None:
        known = {c for i in json.loads((DATA / 'kap-universe.json').read_text())['companies'] for c in i['codes']}
    reads = [[appearances(ocr(img, *c), known) for c in CONFIGS] for img in images]
    codes = Counter(code for img in reads[:1] for r in img for code in r)
    # ARTAN (first ten rows) or AZALAN (next ten) in the summary table, voted over reads
    section = Counter()
    for r in reads[0]:
        ordered = list(r)
        if len(ordered) >= 20:
            for i, code in enumerate(ordered[:20]):
                section[code] += 1 if i < 10 else -1
    result = {}
    for code, n in codes.items():
        if n < len(CONFIGS) // 2 or not re.fullmatch(r'[A-Z]{4,6}', code):
            continue
        out = {}
        for p, period in enumerate(PERIODS):
            t_sum, t_blk, y_c, f_c, tp_sum, tp_blk = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
            minus = {'t': [0, 0], 'y': [0, 0], 'f': [0, 0]}

            def seen(cell, token):
                minus[cell][0] += token[1]
                minus[cell][1] += 1
            img, k = {'d': (0, 1), 'w5': (1, 0), 'w10': (1, 1), 'w20': (2, 0)}[period]
            for r0, ri in zip(reads[0], reads[img]):
                summary = r0.get(code, [])
                block = ri.get(code, [])
                if not summary or len(block) <= k:
                    continue
                s_tl, s_pct, b_tl, b_pct = tl(summary[0]), pct(summary[0]), tl(block[k]), pct(block[k])
                if len(s_tl) > p:
                    t_sum[s_tl[p][2]] += 1
                    seen('t', s_tl[p])
                if len(s_pct) > p:
                    tp_sum[s_pct[p][2]] += 1
                    seen('t', s_pct[p])
                if len(b_tl) >= 3:
                    y_c[b_tl[0][2]] += 1
                    f_c[b_tl[1][2]] += 1
                    t_blk[b_tl[2][2]] += 1
                    for cell, token in zip('yft', b_tl[:3]):
                        seen(cell, token)
                if len(b_pct) >= 3:
                    tp_blk[b_pct[2][2]] += 1
                    for cell, token in zip('yft', b_pct[:3]):
                        seen(cell, token)
            if not (t_sum and t_blk and y_c and f_c):
                continue
            value = solve(t_sum, t_blk, y_c, f_c, minus, section[code] if period == 'd' else None)
            if value:
                agree = set(best(tp_sum, 2)) & set(best(tp_blk, 2))
                if len(agree) == 1 and next(iter(agree)) <= 25:   # "1.41%" read as "141%" is dropped
                    value['tp'] = round(agree.pop() * (1 if value['t'] >= 0 else -1), 2)
                out[period] = value
        if out:
            result[code] = out
    return result


def main():
    if not shutil.which('tesseract'):
        raise SystemExit('tesseract gerekli.')
    reports = json.loads((DATA / 'foreks-reports.json').read_text())['items']
    old = json.loads(OUT.read_text()) if OUT.exists() else {'days': {}}
    days = old['days']
    for doc_id, item in sorted(reports.items(), key=lambda kv: kv[1].get('date') or ''):
        day = (item.get('date') or '')[:10]
        if not TITLE.search(item['title']) or not day or day in days:
            continue
        page = get(CONTENT.format(doc_id))
        urls = re.findall(r'https://news-files\.foreks\.com/content-images/[0-9a-f]+\.(?:jpe?g|png)', page)
        urls = list(dict.fromkeys(urls))
        if len(urls) < 4:
            print(f'{day}: beklenen görseller yok ({len(urls)})')
            continue
        images = [get(u, binary=True) for u in urls[1:4]]   # the first image is the written summary
        rows = parse(images)
        days[day] = {'url': item['url'], 'rows': rows}
        checked = sum(len(v) for v in rows.values())
        print(f'{day}: {len(rows)} hisse, {checked} dönem değeri doğrulandı')
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=60)).strftime('%Y-%m-%d')
    days = {k: v for k, v in sorted(days.items()) if k >= cutoff}
    OUT.write_text(json.dumps({'source': 'QNB Invest, Kurumsal Takas Değişimleri (Foreks)', 'days': days},
                              ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
