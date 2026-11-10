import urllib.request,json,concurrent.futures,pathlib
from lxml import html
R=pathlib.Path(__file__).resolve().parent
urls={'ratios':'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx','targets':'https://www.sekeryatirim.com.tr/Arastirma/TavsiyeListesi','second':'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/takip-listesi.aspx?hl=tr-TR'}
def download(pair):
 k,u=pair;p=R/(k+'.html')
 if not p.exists():p.write_bytes(urllib.request.urlopen(u,timeout=90).read())
 t=html.fromstring(p.read_bytes());out=[]
 for table in t.xpath('//table'):
  rows=[[' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')] for tr in table.xpath('.//tr')]
  if rows:out.append(rows)
 return k,out
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p: tables=dict(p.map(download,urls.items()))
(R/'market-tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2))
for k,ts in tables.items():
 print(k)
 for t in ts:print(t[:3])
