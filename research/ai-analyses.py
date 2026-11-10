"""Pre-generate Turkish company analyses with a free OpenRouter model.

The key is read from the OPENROUTER_API_KEY environment variable and is never
written anywhere. Results go to data/ai-analyses.json and ship with the static
site, so visitors need no key and spend no quota. The free tier allows a small
number of requests per day; the script resumes where it stopped.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'ai-analyses.json'
API = 'https://openrouter.ai/api/v1/chat/completions'
MODELS = ['nvidia/nemotron-3-ultra-550b-a55b:free', 'nvidia/nemotron-3.5-super-vl:free']
FIELDS = [
    ('assets', 'Toplam varlıklar'), ('currentAssets', 'Dönen varlıklar'), ('noncurrentAssets', 'Duran varlıklar'),
    ('cash', 'Nakit ve benzerleri'), ('loans', 'Krediler'), ('deposits', 'Mevduat'),
    ('currentLiabilities', 'Kısa vadeli yükümlülükler'), ('noncurrentLiabilities', 'Uzun vadeli yükümlülükler'),
    ('shortDebt', 'Kısa vadeli finansal borç'), ('longDebt', 'Uzun vadeli finansal borç'),
    ('equity', 'Özkaynaklar'), ('parentEquity', 'Ana ortaklığa ait özkaynaklar'),
    ('revenue', 'Hasılat'), ('grossProfit', 'Brüt kâr'), ('netInterest', 'Net faiz geliri'), ('netFees', 'Net ücret ve komisyon'),
    ('operating', 'Esas faaliyet kârı'), ('pretax', 'Vergi öncesi kâr'), ('netIncome', 'Net kâr (ana ortaklık)'),
    ('groupNetIncome', 'Net kâr (toplam)'), ('depreciation', 'Amortisman'), ('ocf', 'İşletme nakit akışı'),
    ('capex', 'Yatırım harcaması'), ('fcf', 'Serbest nakit akışı'),
]
RULES = [
    'Titiz bir hisse senedi araştırma asistanısın. Türkçe yaz.',
    'YALNIZCA aşağıdaki sayıları kullan; dışarıdan rakam veya haber ekleme. "eksik" kalemleri eksik olarak an, tahmin etme.',
    'Tutarlar her dönemin kendi raporundaki nominal tutarlardır. 2023 ve sonrası TMS 29 (enflasyon muhasebesi) ile hazırlanmıştır; öncesiyle doğrudan kıyaslanamaz. Büyüme yorumunda bunu açıkça söyle.',
    'Ara dönem (6A, 9A) gelir ve nakit akışı kümülatiftir; tam yılla büyüme olarak kıyaslama.',
    'Veri uyarısı varsa ilgili rakamı yorumlarken çekince olarak belirt.',
    'Biçim: "## Başlık" satırları ve "- " ile maddeler. Başlıklar: Özet, Büyüme, Kârlılık, Borç ve likidite, Nakit üretimi, Riskler, Sırada neye bakmalı. 250-400 kelime. Tablo kullanma.',
    'Bir rakamı yazarken hangi döneme ait olduğunu köşeli parantezli dönem başlığından al; dönemleri karıştırma. Gelecek dönem tahmini yapma.',
    'Al, sat, tut önerisi ve hedef fiyat verme.',
]


def num(v):
    return isinstance(v, (int, float))


def fmt(v):
    return f'{v:,.1f}'.replace(',', ' ') if num(v) else 'eksik'


def label(period):
    if period.endswith('/12'):
        return f'{period[:4]} yıl sonu, 12 ay'
    return f"{period} ara dönem, ilk {period.split('/')[1]} ay kümülatif"


def prompt(row, meta):
    """One block per period: weaker models misread wide tables but not labelled lists."""
    h = row['h']
    lines = [f"Şirket: {row['c']} · {row['n']}", f"Sektör: {row.get('s') or 'eksik'}",
             f"Piyasa ({meta['priceDate']}): fiyat {row.get('px') or 'eksik'} TL, piyasa değeri {fmt(row.get('mc'))} milyon TL, "
             f"F/K {row.get('pe') or 'eksik'}, PD/DD {row.get('pb') or 'eksik'}", '',
             f"Mali tablolar (tüm tutarlar milyon TL; {h['basis']}; şablon: {'sanayi/ticaret' if h['g'] == 'XI_29' else 'finansal kuruluş'})"]
    for i, period in enumerate(h['p']):
        get = lambda f: h['v'].get(f, [None] * len(h['p']))[i]
        parts = [f'{name}={fmt(get(key))}' for key, name in FIELDS if any(num(v) for v in h['v'].get(key, []))]
        cash, sd, ld, ni, rev, eq, assets = (get(f) for f in ('cash', 'shortDebt', 'longDebt', 'netIncome', 'revenue', 'equity', 'assets'))
        if all(num(x) for x in (cash, sd, ld)):
            parts.append(f'Net borç [hesaplanan]={fmt(sd + ld - cash)}')
        if num(ni) and num(rev) and rev > 0:
            parts.append(f'Net kâr marjı [hesaplanan]=%{ni / rev * 100:.1f}')
        if num(eq) and num(assets) and assets > 0:
            parts.append(f'Özkaynak/varlık [hesaplanan]=%{eq / assets * 100:.1f}')
        lines += ['', f'[{label(period)}]', '; '.join(parts)]
    if h.get('w'):
        lines += ['', 'Veri uyarıları:'] + ['- ' + w for w in h['w']]
    if row.get('snap'):
        snap = row['snap']
        lines += ['', f"2026/9 resmî özet ({snap['prov']}, {snap.get('basis') or 'kapsam belirtilmemiş'}): "
                  + ', '.join(f'{k}={fmt(v)}' for k, v in snap['v'].items())]
    return '\n'.join(RULES + ['', '--- VERİ ---'] + lines)


def usable(answer, finish):
    """Reject short or cut-off replies."""
    return finish == 'stop' and len(answer) > 900 and 'Sırada' in answer


def ask(key, model, text):
    body = {'model': model, 'temperature': 0.2, 'max_tokens': 8000, 'reasoning': {'effort': 'low', 'exclude': True}, 'messages': [{'role': 'user', 'content': text}]}
    request = urllib.request.Request(API, json.dumps(body).encode(), {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        reply = json.load(response)
    if reply.get('usage', {}).get('cost'):
        raise SystemExit('Ücretli yanıt döndü; durduruldu.')
    choice = reply['choices'][0]
    return (choice['message'].get('content') or '').strip(), reply.get('model') or model, choice.get('finish_reason')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=40, help='Bu çalıştırmada en çok kaç yeni analiz üretilecek')
    parser.add_argument('--pause', type=float, default=4)
    args = parser.parse_args()
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        sys.exit('OPENROUTER_API_KEY tanımlı değil.')
    spec = importlib.util.spec_from_file_location('site', ROOT / 'research' / 'site.py')
    site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(site)
    data = site.companies()
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = sorted((r for r in data['companies'] if r.get('h') and r['c'] not in done), key=lambda r: -(r.get('mc') or 0))
    made = 0
    for row in todo:
        if made >= args.limit:
            break
        text, answer, used, finish = prompt(row, data['meta']), '', None, None
        for model in MODELS:
            try:
                answer, used, finish = ask(key, model, text)
            except urllib.error.HTTPError as error:
                detail = error.read().decode('utf-8', 'replace')[:160]
                print(f"{row['c']} · {model} · HTTP {error.code} {detail}", flush=True)
                if error.code == 429 and 'free-models-per-day' in detail:
                    print('Günlük ücretsiz istek sınırı doldu.', flush=True)
                    return
                continue
            except OSError as error:
                print(f"{row['c']} · {model} · {error}", flush=True)
                continue
            if usable(answer, finish):
                break
            print(f"{row['c']} · {model} · reddedildi (bitiş: {finish}, {len(answer)} karakter)", flush=True)
        if not usable(answer, finish):
            print(f"{row['c']} · kullanılabilir yanıt yok, atlandı", flush=True)
            continue
        # The period tags were only there to keep the model on the right column.
        answer = re.sub(r' ?\[[^\]\n]*(?:yıl sonu, 12 ay|kümülatif|Piyasa)[^\]\n]*\]', '', answer)
        done[row['c']] = {'text': answer, 'model': used, 'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                          'periods': row['h']['p']}
        OUT.write_text(json.dumps(dict(sorted(done.items())), ensure_ascii=False, indent=1) + '\n')
        made += 1
        print(f"{made}/{args.limit} · {row['c']} · {len(answer)} karakter · {used}", flush=True)
        time.sleep(args.pause)


if __name__ == '__main__':
    main()
