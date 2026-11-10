import json,urllib.request,subprocess,pathlib,concurrent.futures
R=pathlib.Path(__file__).resolve().parent
D=json.loads((R/'financials.json').read_text())
def work(c):
 d=D[c];u=d['attachments'][0]
 if c=='TTKOM':u='https://www.kap.org.tr/tr/api/file/download/4028328da17e515f01a1a64133ff50cb'
 p=R/(c+'-notes.pdf')
 try:
  if not p.exists():p.write_bytes(urllib.request.urlopen(u,timeout=90).read())
  subprocess.run(['pdftotext','-layout',str(p),str(p.with_suffix('.txt'))],check=True,capture_output=True)
  print(c,p.stat().st_size,flush=True)
 except Exception as e:print(c,str(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:list(p.map(work,['KCHOL','BIMAS','PGSUS','TCELL','MGROS','TTKOM']))
