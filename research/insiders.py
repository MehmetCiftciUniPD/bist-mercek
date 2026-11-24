"""Off-exchange share purchases by controlling shareholders and companies.

After SPK closed 131 investment funds in September 2026, liquidating funds
have been selling their holdings, and controlling shareholders or the
companies themselves have been buying those shares outside the exchange
("borsa dışında"). This collects such notices from KAP into
data/fund-transfers.json.

Sources (KAP disclosure search, the endpoint behind KAP's "Bildirim Sorgu"):
- "Pay Alım Satım Bildirimi" (insider trades): every notice is opened, since
  the off-exchange detail is only in the text;
- "Payların Geri Alınmasına İlişkin Bildirim": every notice is opened too,
  because daily buyback notices sometimes report a fund purchase in the text;
- "Özel Durum Açıklaması (Genel)": every notice is opened as well; many name
  only "pay devri" or "hakim ortak" in the summary.
- "Fon Kurucusu Tarafından Yapılan Pay Alım Satım Bildirimi": the fund side.

A notice is kept when its Turkish explanation mentions an off-exchange trade
or a liquidating fund. Amounts, prices and shares are read from the text with
conservative patterns and stay null when absent; the excerpt is always kept so
readers can check.
"""
import argparse
import html
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'fund-transfers.json'
SEARCH = 'https://www.kap.org.tr/tr/api/disclosure/members/byCriteria'
NOTICE = 'https://www.kap.org.tr/tr/Bildirim/{}'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Referer': 'https://www.kap.org.tr/tr/bildirim-sorgu'}
ISTANBUL = timezone(timedelta(hours=3))
INSIDER = '8aca490d50286f620150287614ae005c'      # Pay Alım Satım Bildirimi
FOUNDER = '4028328ca0b8418601a16798b5613c29'      # Fon Kurucusu Tarafından Yapılan Pay Alım Satım Bildirimi
BUYBACK = '4028328d6233239a01629b43e4694fae'      # Payların Geri Alınmasına İlişkin Bildirim
SUMMARY = re.compile(r'tasfiye|borsa\s*dış|yatırım\s*fon|fon(?:lar)?(?:ın|ı)?(?:dan|ndan)\b|portföy', re.I)
RELEVANT = re.compile(r'borsa\s*dışı|borsa\s+istanbul\s*\'?(?:da)?\s*dışında|tasfiye|virman|7596\s*sayılı|özel\s+işlem\s+bildirimi|özel\s+emir|toptan\s+satış|TMSF|tasarruf\s+mevduatı\s+sigorta\s+fonu', re.I)


def subjects_named(name):
    """Subject identifiers for a subject title, read from KAP's query page."""
    with urlopen(Request('https://www.kap.org.tr/tr/bildirim-sorgu', headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as r:
        page = r.read().decode('utf-8', 'replace')
    pattern = r'\\"subject\\":\\"' + re.escape(name) + r'\\",\\"subjectOid\\":\\"([0-9A-Za-z]+)\\"'
    return list(dict.fromkeys(re.findall(pattern, page)))


def search(subjects, start, end):
    body = {'fromDate': start, 'toDate': end, 'memberType': 'IGS', 'mkkMemberOidList': [], 'inactiveMkkMemberOidList': [],
            'disclosureClass': '', 'subjectList': subjects, 'isLate': '', 'mainSector': '', 'sector': '', 'subSector': '',
            'marketOid': '', 'index': '', 'bdkReview': '', 'bdkMemberOidList': [], 'year': '', 'term': '', 'ruleType': '',
            'period': '', 'fromSrc': False, 'srcCategory': '', 'disclosureIndexList': []}
    request = Request(SEARCH, data=json.dumps(body).encode(), headers={**HEADERS, 'Content-Type': 'application/json'})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def windows(days, step=5):
    today = datetime.now(ISTANBUL).date()
    start = today - timedelta(days=days)
    while start <= today:
        end = min(start + timedelta(days=step - 1), today)
        yield start.isoformat(), end.isoformat()
        start = end + timedelta(days=1)


CACHE = None


def explanation(index):
    """Turkish explanation text of a notice, or None if the page cannot be read."""
    cached = CACHE / f'{index}.html' if CACHE else None
    if cached and cached.exists():
        raw = cached.read_text()
    else:
        for attempt in range(3):
            try:
                with urlopen(Request(NOTICE.format(index), headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
                    raw = r.read().decode('utf-8', 'replace')
                break
            except OSError:
                if attempt == 2:
                    return None
                time.sleep(2 * (attempt + 1))
        if cached:
            cached.write_text(raw)
    text = raw.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&').replace('\\"', '"').replace('\\n', ' ')
    text = ' '.join(html.unescape(html.unescape(re.sub(r'<[^>]+>', ' ', text))).replace('\xa0', ' ').split())
    # Skip the site menu (it contains "Tasfiye Olmuş Fonlar") and the notice
    # header; the explanation sits in a different section per form, so anchor on
    # the first mention of an off-exchange trade or a liquidation after that.
    head = text.find('Gönderim Tarihi')
    text = text[head:] if head >= 0 else text
    text = text.replace('Tasfiye Olmuş Fonlar', '')
    # Prefer the form's explanation section; fall back to the sentence around
    # the first mention.
    for marker in ('oda_ExplanationTextBlock|', 'Ek Açıklamalar'):
        at = text.find(marker)
        if at >= 0:
            body = text[at + len(marker):at + len(marker) + 2000]
            cut = re.search(r'\b(?:Pursuant|In accordance|Within the scope|This statement|We hereby|Hereby|Our Company|Shares Transaction|Additional Explanations)\b', body)
            body = (body[:cut.start()] if cut else body).strip()
            body = re.split(r'\s\d+:\[\"\$', body)[0].strip()
            if RELEVANT.search(body):
                return body[:1500]
    hit = RELEVANT.search(text)
    if not hit:
        return ''
    start = text.rfind('. ', max(0, hit.start() - 500), hit.start())
    body = text[start + 2 if start >= 0 else hit.start():][:1500]
    cut = re.search(r'\b(?:Pursuant|In accordance|Within the scope|This statement|We hereby)\b', body)
    return (body[:cut.start()] if cut else body).strip()


def number(text):
    text = text.strip()
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    elif text.count('.') >= 1 and re.fullmatch(r'\d{1,3}(?:\.\d{3})+', text):
        text = text.replace('.', '')
    try:
        return float(text)
    except ValueError:
        return None


PURCHASE = re.compile(r'virman|borsa\s*dışı\w*\s+(?:yoluyla|olarak|işlem)|borsa\s+İstanbul\s+dışında|geri\s+alın\w*|geri\s+alım\w*\s+gerçekleş|satın\s+alın\w*|devral\w*|özel\s+işlem\s+bildirimi|(?:tarafımızdan|şirketimizce|şirketimiz\s+tarafından)[\s\S]{0,120}?(?:pay|hisse|lot)\w*[\s\S]{0,80}?alın\w*|(?:pay|hisse|lot)\w*[\s\S]{0,120}?(?:tarafımızdan|şirketimizce)[\s\S]{0,80}?alın\w*', re.I)


FUNDISH = re.compile(r'\bfon|tasfiye|TMSF|tasarruf\s+mevduatı|7596', re.I)
TENDER = re.compile(r'zorunlu\s+pay\s+alım\s+teklif', re.I)


def details(text):
    purchase = PURCHASE.search(text) and FUNDISH.search(text) and not TENDER.search(text)
    out = {'kind': 'purchase' if purchase else 'statement'}
    if m := re.search(r'pay\s+başına\s+([0-9][0-9.]*(?:,[0-9]+)?)\s*TL', text, re.I):
        out['price'] = number(m.group(1))
    if 'price' in out:
        pass
    elif m := re.search(r'([0-9][0-9.]*(?:,[0-9]+)?)\s*TL[^.]{0,60}?(?:fiyat|kapanış)', text, re.I) or \
            re.search(r'(?:fiyat|kapanış)\w*[^0-9.]{0,50}([0-9][0-9.]*(?:,[0-9]+)?)\s*TL', text, re.I):
        out['price'] = number(m.group(1))
    if m := re.search(r'bedel\w*\s+([0-9][0-9.]*(?:,[0-9]+)?)\s*(?:,-)?\s*-?\s*TL', text, re.I) or \
            re.search(r'toplam\s+([0-9][0-9.]*(?:,[0-9]+)?)\s*TL\s*(?:bedel|tutar|karşılığ)', text, re.I) or \
            re.search(r'([0-9][0-9.]*(?:,[0-9]+)?)\s*TL\s*(?:bedelle|bedel karşılığında|tutarında)', text, re.I):
        out['amount'] = number(m.group(1))
    if m := re.search(r'([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?|[0-9]{4,}(?:,[0-9]+)?)\s*(?:adet|lot)', text, re.I):
        out['shares'] = number(m.group(1))
    elif m := re.search(r'([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?)\s*TL\s*nominal|nominal\s+(?:değeri\s+)?([0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?)\s*TL', text, re.I):
        # Nominal value in TL; BIST shares have a 1 TL nominal value.
        out['shares'] = number(m.group(1) or m.group(2))
    if m := re.search(r'sermaye\w*[^%]{0,60}?%\s*([0-9]+(?:,[0-9]+)?)', text, re.I):
        value = number(m.group(1))
        if value is not None and 0 < value <= 100:
            out['ratio'] = value
    if 'amount' not in out and out.get('price') and out.get('shares'):
        # Price x shares, both read from the same notice; marked as calculated.
        out['amount'], out['amountCalc'] = round(out['price'] * out['shares'], 2), True
    out['buyer'] = 'company' if re.search(r'Şirketimiz tarafından geri alın|geri al(ın|ım)', text, re.I) else 'holder'
    out['side'] = 'sell' if re.search(r'sat(ış|ılmış|tı)\b', text, re.I) and not re.search(r'satın al|alın|alım', text, re.I) else 'buy'
    out['fund'] = bool(re.search(r'tasfiye|fon', text, re.I))
    out['offExchange'] = bool(re.search(r'borsa\s*dışı', text, re.I))
    return out


def fold(name):
    name = unicodedata.normalize('NFKD', name.replace('İ', 'I').replace('ı', 'i').upper())
    return re.sub(r'[^A-Z0-9]', '', ''.join(ch for ch in name if not unicodedata.combining(ch)))


NAMES = {}


def stamp(text):
    m = re.fullmatch(r'(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2}):\d{2}', str(text or ''))
    return f'{m[3]}-{m[2]}-{m[1]}T{m[4]}' if m else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=35)
    parser.add_argument('--cache', type=Path, help='Keep downloaded notice pages here')
    args = parser.parse_args()
    global CACHE
    if args.cache:
        args.cache.mkdir(parents=True, exist_ok=True)
        CACHE = args.cache
    universe = json.loads((DATA / 'kap-universe.json').read_text())['companies']
    known = {c for i in universe for c in i['codes']}
    for issuer in universe:
        NAMES[re.sub(r'AS$', '', fold(issuer['name']))] = issuer['codes']
    # Listed codes priced by İş Yatırım but missing from the KAP segment list (e.g. new listings).
    latest = DATA / 'market-latest.json'
    if latest.exists():
        known |= {c['code'] for c in json.loads(latest.read_text())['companies']}
    old = json.loads(OUT.read_text()) if OUT.exists() else {'items': {}, 'checked': []}
    items, checked = old['items'], set(old.get('checked', []))
    general = subjects_named('Özel Durum Açıklaması (Genel)')
    candidates = {}
    for start, end in windows(args.days):
        for subjects, filtered in (([INSIDER], False), ([BUYBACK], False), ([FOUNDER], False), (general, False)):
            if not subjects:
                continue
            for row in search(subjects, start, end):
                index = str(row.get('disclosureIndex') or '')
                # Notices filed by a person or fund carry the company in relatedStocks.
                listed = str(row.get('stockCodes') or '') or str(row.get('relatedStocks') or '')
                codes = [c.strip() for c in listed.split(',') if c.strip() in known]
                if not index.isdigit() or not codes or index in checked:
                    continue
                if filtered and not SUMMARY.search(str(row.get('summary') or '')):
                    continue
                candidates[index] = {'codes': codes, 'date': stamp(row.get('publishDate')), 'subject': row.get('subject'),
                                     'summary': ' '.join(str(row.get('summary') or '').split())[:200]}
            time.sleep(0.5)
    todo = [i for i in candidates if candidates[i]['date']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        texts = dict(zip(todo, pool.map(explanation, todo)))
    kept = 0
    for index in todo:
        text = texts[index]
        if text is None:
            continue
        checked.add(index)
        if not RELEVANT.search(text) or not FUNDISH.search(text):
            continue
        item = {**candidates[index], **details(text), 'text': text[:1200], 'url': NOTICE.format(index)}
        # A notice filed by a parent about another listed company's shares.
        # Only a company whose shares ("... paylarında / paylarının") the notice is about.
        folded = fold(text)
        others = sorted({c for key, codes in NAMES.items() if len(key) > 12
                         and re.search(re.escape(key) + r'(?:AS)?.{0,25}?PAY(?:LAR)?(?:IN|I)', folded)
                         for c in codes} - set(item['codes']))
        if others:
            item['targets'] = others
        items[index] = item
        kept += 1
    cutoff = (datetime.now(ISTANBUL) - timedelta(days=365)).strftime('%Y-%m-%d')
    items = {k: v for k, v in items.items() if v['date'] >= cutoff}
    OUT.write_text(json.dumps({'source': SEARCH, 'since': (datetime.now(ISTANBUL) - timedelta(days=args.days)).strftime('%Y-%m-%d')
                               if not old.get('since') else old['since'],
                               'items': dict(sorted(items.items())), 'checked': sorted(checked, key=int)[-5000:]},
                              ensure_ascii=False, indent=1) + '\n')
    print(f'{len(todo)} bildirim açıldı · {kept} yeni borsa dışı / fon işlemi · toplam {len(items)}')


if __name__ == '__main__':
    main()
