import json,pathlib,statistics
R=pathlib.Path(__file__).resolve().parent
D=json.loads((R/'financials.json').read_text());M=json.loads((R/'market-tables.json').read_text())
PRICE='https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx';TARGET='https://www.sekeryatirim.com.tr/Arastirma/TavsiyeListesi';SECOND='https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/takip-listesi.aspx?hl=tr-TR'
def tr(v):return f'{v:,.1f}'.replace(',','X').replace('.',',').replace('X','.')
def n(s):
 try:return float(s.replace('.','').replace(',','.').replace('%',''))
 except:return None
market={}
for t in M['ratios']:
 if 'Sektör' in t[0]:
  for r in t[1:]:
   if len(r)==8:market[r[0]]={'code':r[0],'name':r[1],'sector':r[2],'price':n(r[3]),'marketCap':n(r[4])}
for t in M['ratios']:
 if 'Son Dönem' in t[0]:
  for r in t[1:]:
   if r[0] in market:market[r[0]].update(dict(zip(['pe','multiple','evSales','pb'],map(n,r[2:6]))),ratioPeriod=r[6])
 if any('Günlük Getiri' in s for s in t[0]):
  for r in t[1:]:
   if r[0] in market:market[r[0]].update(dict(zip(['return','weekReturn','monthReturn','ytdReturn'],map(n,r[2:6]))))
for code,d in D.items():
 d.update(market[code]);d['priceDate']='2026-11-09';d['marketSource']=PRICE;d['bist']=2.0;d['bistYtd']=4.01;d['benchmarkSource']='https://www.borsaistanbul.com/endeksler/bist-pay/gosterge-endeksler'
 peers=[r for r in market.values() if r['sector']==d['sector']]
 d['sectorPeers']=[p['code'] for p in peers];d['peerStats']={}
 for key in ['pe','pb','multiple','return','ytdReturn']:
  vals=[p.get(key) for p in peers if p.get(key) is not None and (key in ['return','ytdReturn'] or p[key]>0) and (key in ['return','ytdReturn'] or p.get('ratioPeriod')=='9/2026')]
  d['peerStats'][key]={'median':statistics.median(vals) if len(vals)>=3 else None,'count':len(vals)}
 d['sectorReturn']=d['peerStats']['return']['median']
 for key in ['price','marketCap','pe','pb','multiple','return','weekReturn','monthReturn','ytdReturn']:d['fieldSources'][key]={'url':PRICE,'kind':'İş Yatırım · 09.11.2026 kapanış','formula':'Kurumun yayımladığı oran/getiri; finansal tablo oranı dönemi '+d.get('ratioPeriod','')}
for t in M['targets']:
 for r in t[1:]:
  if len(r)==9 and r[0] in D:
   d=D[r[0]];d['target']=n(r[3]);d['analystTargets']=[{'firm':'Şeker Yatırım','target':n(r[3]),'recommendation':r[1],'date':None,'source':TARGET}];d['fieldSources']['target']={'url':TARGET,'kind':'Aracı kurum hedefi','note':'10.11.2026 erişim; hedef revizyon tarihi belirtilmiyor.'}
for t in M['second']:
 if len(t[0])==7 and t[0][0]=='Kod':
  for r in t[1:]:
   if len(r)==7 and r[0] in D:D[r[0]]['analystTargets'].append({'firm':'İş Yatırım','target':n(r[2]),'recommendation':r[1],'date':r[4],'source':SECOND})
# Official EBITDA reconciliation from financial report segment notes; units million TL.
for code,values,page in [('TCELL',[99899.246,97128.335,36243.268,33944.364],'Bölümlere göre raporlama, basılı s.16–17'),('MGROS',[23382.392,23997.350,11435.543,11702.411],'FAVÖK mutabakatı, basılı s.41'),('TTKOM',[99086.290,90777.303,37017.101,34642.034],'Bölümlere göre raporlama / FAVÖK mutabakatı')]:
 d=D[code]
 for target,val in zip([d,d['previous'],d['quarter'],d['quarterPrevious']],values):target['calculatedEbitda']=target.get('ebitda');target['ebitda']=val
 d['ebitdaLabel']='Şirket açıklaması';d['fieldSources']['ebitda']={'url':d['source'],'kind':'Şirketin raporladığı FAVÖK','note':page,'unit':'Milyon TL'}
for code,d in D.items():
 d.setdefault('ebitdaLabel','Hesaplanan esas faaliyet FAVÖK');d['valuation']='Fiyat: 09.11.2026 kapanış. F/K, FD/FAVÖK ve PD/DD: İş Yatırım, 9/2026 son rapor dönemi. Hedef: Şeker Yatırım takip listesi, 10.11.2026 erişim; revizyon tarihi ve model varsayımları listede yok. Kurum hedefleri birbirinden farklıdır; konsensüs veya panelin kendi hedefi değildir.'
 d['guidance']='Bu veri setinde son ve önceki şirket rehberi henüz eşleştirilmedi. Değişmediği varsayılmaz.'
 d['oneoffNote']='Standart bir tek seferlik toplam bulunmadığından tutar üretilmedi. Vergi ve parasal pozisyon ayrı gösterilir; tekrarlanabilir kâr için işlem bazında dipnot ayrıştırması gerekli.'
 d['maturity']=f"12 ay içinde sınıflanan finansal borç: {tr(d.get('short',0))} mn TL. Toplam finansal borç: {tr(d.get('totalDebt',0))} mn TL. Kira yükümlülükleri dahildir. Yıl yıl geri ödeme takvimi ve sözleşme koşulları bu veri setinde ayrıştırılmadı." if code not in ['AKBNK','GARAN','ISCTR','YKBNK'] else 'Banka bilançosunda mevduat/kredi ve likidite vade uyumsuzluğu birlikte değerlendirilmelidir. Sanayi tipi kısa borç/toplam borç skoru uygulanmaz; likidite vade tablosu ayrıca incelenmeli.'
 d['gaps']=['Tek seferlik kalemlerin işlem bazında ayrıştırılması','Yıl yıl borç itfa / likidite vade takvimi','Son rehberin önceki rehberle eşleştirilmesi','Hedef fiyat model varsayımları ve Şeker Yatırım revizyon tarihi']
 d['confidence']='Finansallar: yüksek · değerleme: orta · dipnot incelemesi: kısmi'
 if d.get('assets') and d.get('equity') and d['previous'].get('equity'):d['annualizedROE']=d['netIncome']*4/3/((d['equity']+d['previous']['equity'])/2)*100
 for key in ['short','totalDebt','debt','working','provision','fcf','effectiveTax']:
  if d.get(key) is not None:d[key]=round(d[key],3)
 d['researchNotes']=[f"Ana ortaklık 9 aylık net kârı {tr(d['netIncome'])} mn TL; karşılaştırılabilir önceki dönem {d['previous'].get('netIncome',0):,.1f} mn TL."]
 if d.get('fcf') is not None:d['researchNotes'].append(('Nakit üretimi pozitif.' if d['fcf']>0 else 'Yatırım sonrası nakit açığı var.')+' Serbest nakit akışı kira anapara ödemesi öncesidir; net kârla aynı ölçü değildir.')
 if d.get('monetary') is not None:d['researchNotes'].append(f"Parasal pozisyon etkisi {tr(d['monetary'])} mn TL. Vergi kalemi {tr(d.get('tax',0))} mn TL (negatif gider, pozitif gelir). Bu etkiler nakit faaliyet performansından ayrı okunmalı.")
 if code in ['KCHOL','SAHOL']:
  d['researchNotes'].append('Holding: konsolide borç iştirakleri ve finansal kuruluşları içerir; holding solo net borcu değildir. NAD iskontosu için iştirak bazlı değerleme gerekir. Sanayi nakde dönüşüm/vade skorları uygulanmaz.')
 if code in ['AKBNK','GARAN','ISCTR','YKBNK']:
  d['researchNotes'].append('Konsolide BDDK seti kullanıldı. Ana ortaklık kârı solo banka kârıyla karıştırılmamalı. FAVÖK/serbest nakit akışı sanayi yaklaşımı uygulanmaz. ROE, 9 aylık kârın 4/3 ile yıllıklandırılmış yaklaşık göstergesidir; düzenleyici sermaye yeterlilik oranı değildir.')
 d['note']='\n\n'.join(d['researchNotes'])
# Company-specific source-linked catalysts, not trading advice.
notes={
'KCHOL':'İştirak kârlarının holding kârına katkısı, enerji döngüsü ve NAD iskontosu izlenecek. Konsolide nakit, holding solo nakdi yerine kullanılamaz.',
'BIMAS':'Reel satış büyümesi, mağaza verimliliği ve kira sonrası nakit dönüşümü izlenecek. Kira dahil borç ile kira öncesi FCF birlikte okunmalı.',
'PGSUS':'Şirket sunumu: 9A26 FAVÖK 486 mn EUR (9A25: 692); 3Ç26 404 mn EUR (3Ç25: 395). 9 aylık baskıya karşı üçüncü çeyrekte toparlanma. Yakıt fiyatı, doluluk ve birim gelir önemli.',
'TCELL':'3Ç26 açıklanan FAVÖK 36.243 mn TL; şirket sitesinde yayımlanan analist medyanı 33.500 mn TL. Yaklaşık %8,2 pozitif sürpriz. Beklenti şirket rehberi değildir. 5G yatırım harcamaları ve nakit dönüşümü izlenecek.',
'THYAO':'Yakıt, döviz, yolcu bileşimi ve uçak/kira yatırımları takip edilecek. USD fonksiyonel raporlama nedeniyle TL büyüme tek başına operasyonel büyüme değildir.',
'AKBNK':'Net faiz geliri, kredi/mevduat oranı ve beklenen kredi zararı giderleri izlenecek. Banka endeksi liderliği piyasa katalizörü; bilanço kalitesinin yerine geçmez.',
'GARAN':'Net faiz geliri, özkaynak getirisi ve kredi zararı maliyeti takip edilecek. Konsolide ana ortaklık kârı solo açıklamalarla farklılaşabilir.',
'ISCTR':'Kredi karşılıkları, net faiz geliri ve iştirak katkısı izlenecek. Sermaye/aktif oranı düzenleyici sermaye yeterliliği değildir.',
'YKBNK':'Fonlama maliyeti, mevduat vadesi ve kredi zarar karşılıkları takip edilecek. Net faiz gelirindeki değişim, kredi büyümesiyle birlikte okunmalı.',
'TUPRS':'Rafineri marjları, petrol fiyatı, stok etkisi ve dağıtılabilir nakit izlenecek. Net nakit pozisyonu petrol döngüsü riskini ortadan kaldırmaz.',
'FROTO':'05.11.2026 rehber güncellemesi: Türkiye pazar ve iç satış adet beklentileri aşağı çekildi. Düzeltilmiş FAVÖK marjı %6–7 aralığında korundu.',
'ASELS':'Siparişlerin nakde dönüşmesi ve işletme sermayesi kritik. Pozitif muhasebe kârına rağmen yatırım sonrası nakit açığı izlenecek.',
'SAHOL':'Banka/enerji iştirak katkıları ve NAD iskontosu izlenecek. Zarar bazından kâra geçiş yüzde büyümeyle ifade edilmez.',
'EREGL':'Çelik marjları, talep, kur ve vergi etkisi izlenecek. Pozitif vergi geliri ile faaliyet kârlılığı ayrı değerlendirilmeli.',
'MGROS':'05.11.2026 KAP açıklaması yıl sonu rehberinin güncellendiğini doğruluyor. Eski/yeni sayısal rehber henüz birincil belgeden eşleştirilmedi; marj ve kira sonrası nakit izlenecek.',
'TTKOM':'Yatırım harcamaları ve FAVÖK’ün nakde dönüşümü kritik. Pozitif FAVÖK yanında yatırım sonrası nakit açığı izlenecek.'}
for c,d in D.items():d['catalysts']=notes[c]
D['PGSUS']['companySource']='https://www.kap.org.tr/tr/Bildirim/1695830';D['PGSUS']['officialEbitdaEUR']={'current':486,'previous':692,'quarter':404,'quarterPrevious':395,'unit':'Milyon EUR','source':'https://www.kap.org.tr/tr/api/file/download/4028328ca17e4f5d01a1c1164bd62428'}
D['TCELL']['expectationSource']='https://www.turkcell.com.tr/hakkimizda/yatirimci-iliskileri/hisse-tahvil-ve-analist-bilgisi/analist-beklentileri/detay';D['TCELL']['earningsSurprise']=8.19
D['BIMAS']['companySource']='https://www.kap.org.tr/tr/Bildirim/1695731';D['KCHOL']['companySource']='https://www.kap.org.tr/tr/Bildirim/1695490';D['MGROS']['companySource']='https://www.kap.org.tr/tr/Bildirim/1693497'
f=D['FROTO'];f['companySource']='https://www.kap.org.tr/tr/Bildirim/1693371';f['guidance']='05.11.2026 faaliyet raporu s.11: Türkiye otomotiv pazarı 1,2–1,3 milyon → 1,1–1,2 milyon; perakende satış 75–85 bin → 65–75 bin; toplam satış 655–715 bin → 645–705 bin. Düzeltilmiş FAVÖK marjı %6–7 ve yatırım 300–400 mn EUR korundu (önceki: 04.08.2026).';f['guidanceDirection']=-1;f['gaps'].remove('Son rehberin önceki rehberle eşleştirilmesi');f['officialAdjustedEbitda']=42200;f['officialAdjustedEbitdaPrevious']=60800;f['adjustedEbitdaNote']='Şirket faaliyet raporu s.7; yuvarlatılmış 42,2 ve 60,8 milyar TL. Esas faaliyetlerden diğer gelir/gider ve embedded lease düzeltmesi içerir.'
# Catalyst score: explicit evidence-based heuristic, each component shown.
for c,d in D.items():
 changes=[];prev=d['previous'].get('netIncome');cur=d.get('netIncome')
 if prev is not None and cur is not None:changes.append({'label':'9 aylık ana ortaklık kârı önceki döneme göre '+('arttı' if cur>prev else 'azaldı'),'points':10 if cur>prev else -10})
 if d.get('fcf') is not None:changes.append({'label':'Yatırım sonrası nakit '+('pozitif' if d['fcf']>0 else 'negatif'),'points':10 if d['fcf']>0 else -10})
 if d.get('guidanceDirection'):changes.append({'label':'Adet rehberi aşağı revize','points':-10})
 if d.get('earningsSurprise',0)>5:changes.append({'label':'3Ç FAVÖK analist medyanının %5 üzerinde','points':10})
 d['catalystComponents']=changes;d['catalystScore']=50+sum(x['points'] for x in changes)
 d['catalystMethod']='50 nötr taban + kâr değişimi (±10) + banka/holding hariç FCF işareti (±10) + doğrulanan rehber yönü (±10) + doğrulanan >%5 FAVÖK sürprizi (+10). Eksik bileşen puan eklemez; skor kapsamlı olasılık tahmini değildir.'
 if c in ['KCHOL','SAHOL']:
  d['catalystComponents']=[x for x in changes if not x['label'].startswith('Yatırım sonrası')];d['catalystScore']=50+sum(x['points'] for x in d['catalystComponents'])
 d['catalysts']+='\n\n'+d['catalystMethod']
exec((R/'note-enrichment.py').read_text())
base={c+':2026/9':d for c,d in D.items()}
macro={
'Sonuçlar':('16 şirketin 2026/9 konsolide KAP finansalı ve 3Ç kârları işlendi. Odak: KCHOL, BIMAS, PGSUS, TCELL. Kaynak düzeltmeleri ve farklı FAVÖK tanımları şirket ekranlarında.','Nötr','https://www.kap.org.tr/tr/'),
'Rehber':('FROTO 05.11: iç satış ve toplam satış adet aralıkları aşağı çekildi; düzeltilmiş FAVÖK marjı %6–7 korundu. MGROS rehber güncellemesi KAP’ta açıklandı; sayısal önce/sonra teyidi bekliyor.','Belirsiz','https://www.kap.org.tr/tr/Bildirim/1693371'),
'Hacim':('09.11.2026: BIST 100 işlem hacmi 143,3 milyar TL; endeks 11.712,67, günlük +%2,00. 20 günlük hacim ortalaması bu sete alınmadı; hacim teyidi iddiası yapılmaz.','Nötr','https://www.aa.com.tr/tr/ekonomi/borsa-gunu-yukselisle-tamamladi/4117552'),
'Banka liderliği':('09.11.2026: bankacılık endeksi +%3,80; BIST 100 +%2,00. Günlük göreli fark +1,80 yüzde puan. Liderliğin devamlılığı sonraki seanslarda izlenecek.','Olumlu','https://www.aa.com.tr/tr/ekonomi/borsa-gunu-yukselisle-tamamladi/4117552'),
'Petrol':('10.11.2026 sabah Tacirler bülteni: Brent 90,43 USD/varil, günlük −%1,62. Havacılık yakıt maliyeti için olumlu yönde; rafineri etkisi ürün marjı ve stoklara bağlı. Gün içi canlı fiyat değildir.','Belirsiz','https://tacirler.com.tr/upload/files/arastirma/gunluk-bulten/2026/kasim/tacirler-gunluk-bulten-10-kasim.pdf'),
'Kur':('10.11.2026 sabah Tacirler bülteni: USD/TRY 50,25; EUR/TRY 56,38. İhracat gelirleri, yabancı para borcu ve fonksiyonel para birimi birlikte değerlendirilmeli. Canlı fiyat değildir.','Belirsiz','https://tacirler.com.tr/upload/files/arastirma/gunluk-bulten/2026/kasim/tacirler-gunluk-bulten-10-kasim.pdf')}
for k,(note,direction,url) in macro.items():base['macro:2026/9:'+k]={'note':note,'direction':direction,'source':url,'updated':'2026-11-10T08:00:00Z'}
(R.parent/'data/research-2026-09.json').write_text(json.dumps(base,ensure_ascii=False,indent=2))
(R.parent/'data/market-2026-11-09.json').write_text(json.dumps({'date':'2026-11-09','source':PRICE,'companies':list(market.values())},ensure_ascii=False,indent=2))
print('Saved',len(D),'financials;',len(market),'market rows;',sum(len(d['fieldSources']) for d in D.values()),'field source mappings')
