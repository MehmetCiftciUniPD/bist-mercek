import json,math,pathlib
R=pathlib.Path(__file__).resolve().parent.parent
D=json.loads((R/'data/research-2026-09.json').read_text());M=json.loads((R/'data/market-2026-11-09.json').read_text())
companies=[v for k,v in D.items() if not k.startswith('macro')]
assert len(companies)==17
assert len(M['companies'])==629
for d in companies:
 assert d['unit']=='Milyon TL' and d['netIncome'] is not None and d['previous']['netIncome'] is not None
 assert d['price']>0 and d['target']>0 and d['source'].startswith(('https://www.kap.org.tr/', 'https://kap.org.tr/'))
 assert d['fieldSources'] and len(d['documentHash'])==64
 if d.get('currentAssets') is not None:
  assert abs(d['assets']-d['equity']-d['currentLiabilities']-d['noncurrentLiabilities'])<.02,d['code']
 if d.get('fcf') is not None:assert abs(d['fcf']-(d['ocf']-d['capex']))<.002,d['code']
 for k,v in d.items():
  if isinstance(v,float):assert math.isfinite(v)
assert D['TCELL:2026/9']['ebitda']==99899.246
assert D['TCELL:2026/9']['revenue']==235065.367
assert D['PGSUS:2026/9']['netIncome']<0
assert D['TUPRS:2026/9']['debt']<0
assert D['AKBNK:2026/9'].get('ebitda') is None
assert D['FROTO:2026/9']['guidanceDirection']==-1
assert D['KCHOL:2026/9']['totalDebt']==1674974
assert sum(r['current'] for r in D['KCHOL:2026/9']['debtSchedule']['rows'])==829246
assert abs(sum(r['current'] for r in D['PGSUS:2026/9']['debtSchedule']['rows'])-204246.603)<.002
print('PASS: 17 source records, 629 market rows, balance checks, FCF reconciliation, EBITDA overrides, bank exclusions and negative values.')

for code, fees, net, group, car in [('HALKB', 57821, 25941, 27013, 13.55), ('ISCTR', 118618, 40437, 59059, 15.56)]:
 d=D[f'{code}:2026/9']
 assert d['netFees']==fees and d['netIncome']==net and d['groupNetIncome']==group
 assert d['netIncome']!=d['groupNetIncome']
 assert next(m['value'] for m in d['bankMetrics'] if m['key']=='car')==car
 for period in (d,d['previous'],d['quarter'],d['quarterPrevious']):
  assert period['currentTax'] + period['deferredTax'] == period['tax']
summary_count=0
for file in ('kap-summary-2026-09.json','broker-summary-2026-09.json'):
 summary=json.loads((R/'data'/file).read_text())
 for key,record in summary.items():
  assert key.endswith(':2026/9') and key not in D and record['financialDate']=='2026-09-30'
  assert record['assets']>0 and record['unit']=='Milyon TL' and record['summaryOnly']
  assert len(record['documentHash'])==64 and record['rawFields']['assets']
 summary_count+=len(summary)
print(f'PASS: {summary_count} sourced summary records and both bank reconciliations.')
