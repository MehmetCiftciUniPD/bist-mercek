import urllib.request,pathlib,concurrent.futures,json,subprocess
from lxml import html
R=pathlib.Path(__file__).resolve().parent
urls={'FROTO-guidance':'https://www.kap.org.tr/tr/Bildirim/1693371','PGSUS-deck':'https://www.kap.org.tr/tr/Bildirim/1695830','MGROS-web':'https://migroskurumsal.com/yatirimci-iliskileri/yatirimci-seti'}
def work(x):
 k,u=x;b=urllib.request.urlopen(u,timeout=60).read();(R/(k+'.html')).write_bytes(b);tree=html.fromstring(b);links=list(dict.fromkeys(tree.xpath('//a/@href')));links=[urllib.request.urljoin(u,a) for a in links if '/api/file/download/' in a or '.pdf' in a]
 (R/(k+'-links.json')).write_text(json.dumps(links));print(k,links,flush=True)
 for i,l in enumerate(links[:8]):
  try:
   p=R/f'{k}-{i}.pdf';p.write_bytes(urllib.request.urlopen(l,timeout=60).read());subprocess.run(['pdftotext','-layout',str(p),str(p.with_suffix('.txt'))],capture_output=True)
  except Exception as e:print(k,str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:list(p.map(work,urls.items()))
