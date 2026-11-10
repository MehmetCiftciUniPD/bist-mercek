"""Reproduce KAP 2026/9 snapshot. Requires lxml. No credentials required."""
import urllib.request,json,hashlib,concurrent.futures,pathlib
from lxml import html
ROOT=pathlib.Path(__file__).resolve().parent
IDS=dict(KCHOL=1695371,BIMAS=1695704,PGSUS=1695827,TCELL=1695603,THYAO=1691983,AKBNK=1688323,GARAN=1689151,ISCTR=1693299,YKBNK=1691272,TUPRS=1694197,FROTO=1693370,ASELS=1688432,SAHOL=1692755,EREGL=1686049,MGROS=1693491,TTKOM=1692808)
BANKS=['AKBNK','GARAN','ISCTR','YKBNK']
KEYS={
'revenue':'ifrs-full_Revenue','financeRevenue':'kap-fr_RevenueFromFinanceSectorOperations','operating':'ifrs-full_ProfitLossFromOperatingActivities','netIncome':'ifrs-full_ProfitLossAttributableToOwnersOfParent','pretax':'ifrs-full_ProfitLossBeforeTax','gross':'ifrs-full_GrossProfit','admin':'ifrs-full_AdministrativeExpense','marketing':'kap-fr_MarketingExpense','rd':'ifrs-full_ResearchAndDevelopmentExpense','da':'ifrs-full_AdjustmentsForDepreciationAndAmortisationExpense','ocf':'ifrs-full_CashFlowsFromUsedInOperatingActivities','capex':'kap-fr_PurchaseOfPropertyPlantEquipmentAndIntangibleAssetsClassifiedAsInvestingActivities','capexPPE':'ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities','capexIntangible':'ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities','tax':'ifrs-full_IncomeTaxExpenseContinuingOperations','monetary':'ifrs-full_GainsLossesOnNetMonetaryPosition','currentTax':'kap-fr_CurrentPeriodTaxExpenseContinuingOperations','deferredTax':'kap-fr_DeferredIncomeTaxExpenseContinuingOperations','cash':'ifrs-full_CashAndCashEquivalents','currentAssets':'ifrs-full_CurrentAssets','currentLiabilities':'ifrs-full_CurrentLiabilities','noncurrentLiabilities':'ifrs-full_NoncurrentLiabilities','assets':'ifrs-full_Assets','equity':'ifrs-full_Equity','receivables':'ifrs-full_CurrentTradeReceivables','inventory':'ifrs-full_Inventories','payables':'kap-fr_CurrentTradePayables','shortParent':'kap-fr_CurrentBorowings','shortRelated':'kap-fr_CurrentBorrowingsFromRelatedParties','shortOther':'kap-fr_CurrentBorrowingsFromUnrelatedParties','currentLong':'kap-fr_CurrentPortionOfNoncurrentBorrowings','longDebt':'ifrs-full_LongtermBorrowings','shortProvision':'ifrs-full_CurrentProvisions','longProvision':'ifrs-full_NoncurrentProvisions','netInterest':'kap-fr_InterestIncomeOrExpense','loans':'kap-fr_Loans','deposits':'kap-fr_Deposits','expectedLoss':'kap-fr_AllowanceForExpectedCreditLosses','eclExpense':'kap-fr_AllowanceExpensesForExpectedCreditLosses','capital':'ifrs-full_IssuedCapital'}
BALANCE=set('cash currentAssets currentLiabilities noncurrentLiabilities assets equity receivables inventory payables shortParent shortRelated shortOther currentLong longDebt shortProvision longProvision loans deposits expectedLoss capital'.split())
def get(url,path):
 if path.exists():return path.read_bytes()
 r=urllib.request.urlopen(url,timeout=90).read();path.write_bytes(r);return r
def number(s):
 try:return float(s.replace('.','').replace(',','.').replace('(','-').replace(')',''))
 except:return None
def collect(pair):
 code,id=pair;source=f'https://www.kap.org.tr/tr/Bildirim/{id}';raw=get(source,ROOT/f'{code}.html');tree=html.fromstring(raw)
 rows=[[' '.join(c.text_content().split()) for c in tr.xpath('./td|./th')] for tr in tree.xpath('//tr')]
 unit=next((r[1] for r in rows if len(r)>1 and r[0]=='Sunum Para Birimi'),'')
 factor=1 if '1.000.000' in unit else .001 if '1.000' in unit else .000001
 tags={}
 for row in rows:
  if len(row)>=6 and '|' in row[0] and row[1]=='':tags.setdefault(row[0].split('|')[0],row)
 d={'source':source,'unit':'Milyon TL','originalUnit':unit,'verified':True,'importedAt':'2026-11-10T17:40:00Z','updated':'2026-11-10T17:40:00Z','financialDate':'2026-09-30','documentHash':hashlib.sha256(raw).hexdigest(),'previous':{},'quarter':{},'quarterPrevious':{},'fieldSources':{},'basis':'BDDK / konsolide' if code in BANKS else 'TFRS / konsolide · '+('EUR fonksiyonel, TL sunum' if code=='PGSUS' else 'USD fonksiyonel, TL sunum' if code in ['THYAO','EREGL'] else 'TMS 29'),'provenance':'KAP XBRL kalemleri; kalem etiketi ve dipnot numarası Kaynak izi sekmesinde. Milyon TL standardizasyonu; bilanço karşılaştırması 31.12.2025, gelir/nakit akışı 9A25.'}
 for key,tag in KEYS.items():
  if key=='ocf' and code in BANKS:tag='kap-fr_CashFlowsFromUsedInBankingOperations'
  row=tags.get(tag)
  if row is None:continue
  i,j=(6,9) if code in BANKS and key in BALANCE and len(row)>=10 else (4,5)
  for target,col in [(d,i),(d['previous'],j)]+([] if key in BALANCE or len(row)!=8 else [(d['quarter'],6),(d['quarterPrevious'],7)]):
   v=number(row[col]);target[key]=round(v*factor,6) if v is not None else None
  d['fieldSources'][key]={'tag':tag,'label':row[2],'note':row[3],'raw':row[i],'unit':unit,'url':source,'kind':'KAP bildirimi','comparison':'31.12.2025' if key in BALANCE else '9A25'}
 for target in [d,d['previous'],d['quarter'],d['quarterPrevious']]:
  def sumknown(keys):
   vals=[target.get(k) for k in keys];return sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None
  def derive(key,val,formula):
   if val is not None:target[key]=round(val,6)
   if target is d:d['fieldSources'][key]={'kind':'Hesaplanan','formula':formula,'url':source}
  if code not in BANKS:
   if target.get('financeRevenue') is not None:
    target['commercialRevenue']=target.get('revenue');derive('revenue',sumknown(['revenue','financeRevenue']),'Ticari hasılat + finans sektörü hasılatı')
   if target.get('gross') is not None and target.get('da') is not None:derive('ebitda',sumknown(['gross','admin','marketing','rd','da']),'Brüt kâr + işaretli yönetim, pazarlama, Ar-Ge giderleri + amortisman; hesaplanan esas faaliyet FAVÖK')
   if all(target.get(k) is not None for k in ['receivables','inventory','payables']):derive('working',target['receivables']+target['inventory']-target['payables'],'Ticari alacak + stok − ticari borç')
   short=(target['shortParent']+ (target.get('currentLong') or 0)) if target.get('shortParent') is not None else sumknown(['shortRelated','shortOther','currentLong']);derive('short',short,'Kısa vadeli borçlanmalar + uzun vadeli borçların kısa vadeli kısmı')
   derive('totalDebt',sumknown(['short','longDebt']),'Kısa + uzun vadeli finansal borç (kiralamalar dahil)')
   if target.get('totalDebt') is not None and target.get('cash') is not None:derive('debt',target['totalDebt']-target['cash'],'Toplam finansal borç − nakit; finansal yatırımlar düşülmez')
   derive('provision',sumknown(['shortProvision','longProvision']),'Kısa + uzun vadeli karşılıklar')
  if target.get('capex') is None:target['capex']=sumknown(['capexPPE','capexIntangible'])
  if target.get('capex') is not None:target['capex']=abs(target['capex'])
  if code not in BANKS and all(target.get(k) is not None for k in ['capex','ocf']):derive('fcf',target['ocf']-target['capex'],'İşletme nakit akışı − maddi/maddi olmayan duran varlık nakit yatırımı; kira anapara ödemesi öncesi')
  if target.get('pretax') and target.get('tax') is not None:derive('effectiveTax',-target['tax']/target['pretax']*100,'−Vergi kalemi / vergi öncesi kâr ×100')
 if code in BANKS:
  row=tags.get('ifrs-full_Provisions')
  if row:
   d['provision']=number(row[6])*factor;d['previous']['provision']=number(row[9])*factor
   d['fieldSources']['provision']={'url':source,'tag':'ifrs-full_Provisions','kind':'KAP bildirimi','note':row[3],'raw':row[6],'unit':unit,'comparison':'31.12.2025'}
  for key in ['revenue','ebitda','working','debt','short','totalDebt','fcf','monetary']:d.pop(key,None)
  if d.get('equity') and d['previous'].get('equity'):d['annualizedROE']=d['netIncome']*4/3/((d['equity']+d['previous']['equity'])/2)*100
  if d.get('deposits'):d['loanDeposit']=d['loans']/d['deposits']*100
 d['attachments']=list(dict.fromkeys('https://www.kap.org.tr'+a if a.startswith('/') else a for a in tree.xpath('//a/@href') if '/api/file/download/' in a))
 return code,d
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
 results=dict(pool.map(collect,IDS.items()))
(ROOT/'financials.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
for c,d in results.items():print(c,d['originalUnit'],d.get('revenue'),d.get('netIncome'),d.get('ebitda'),d.get('fcf'),flush=True)
