"""Reviewed BDDK tables and dipnotes for the 2026/09 bank snapshot."""
from statistics import median

PERIOD = '2026/9'
HALK_KAP = 'https://kap.org.tr/tr/sirket-finansal-bilgileri/2423-turkiye-halk-bankasi-a-s'
HALK_PDF = ('https://www.halkbank.com.tr/content/dam/corporate-website/tr/dokumanlar/'
            'yatirimci-iliskileri/finansal-tablolar-ve-bagimsiz-denetim-raporlari/2026/'
            'Turkiye_Halk_Bankasi_AS_Konsolide_Rapor_30_09_2026')
IS_PDF = 'https://www.kap.org.tr/tr/api/file/download/4028328da17e515f01a1ac3458fd2bb2'
BIST = 'https://www.borsaistanbul.com/endeksler/bist-pay/gosterge-endeksler'
SEKER = 'https://www.sekeryatirim.com.tr/Arastirma/TavsiyeListesi'


def apply_fields(record, rows, source, label):
    """Four columns: 9A26, 9A25, 3Ç26, 3Ç25; two for balance-sheet rows."""
    targets = (record, record['previous'], record['quarter'], record['quarterPrevious'])
    for key, (name, values) in rows.items():
        for target, value in zip(targets, values):
            target[key] = value
        record['fieldSources'][key] = {
            'url': source, 'kind': 'Konsolide banka raporu', 'label': name,
            'note': label, 'raw': str(values[0]), 'unit': 'Milyon TL',
            'comparison': '31.12.2025' if len(values) == 2 else '9A25 ve 3Ç25',
        }


def regulatory(record, source, metrics, note):
    record['bankMetrics'] = [
        {'key': key, 'label': label, 'value': value, 'previous': prior,
         'period': period, 'previousPeriod': previous_period, 'source': source}
        for key, label, value, prior, period, previous_period in metrics
    ]
    for m in record['bankMetrics']:
        record['fieldSources'][m['key']] = {
            'url': source, 'kind': 'Konsolide banka dipnotu', 'label': m['label'],
            'note': note, 'raw': str(m['value']), 'unit': '%', 'comparison': m['previousPeriod'],
        }


def enrich_banks(base, market):
    isctr = base['ISCTR:2026/9']
    apply_fields(isctr, {
        'netFees': ('Net ücret ve komisyon gelirleri', [118618, 87793, 41431, 32765]),
        'groupNetIncome': ('Konsolide dönem net kârı', [59059, 60291, 17105, 19285]),
        'tradingIncome': ('Net ticari kâr/zarar', [-12750, 4356, -6006, 2056]),
        'deferredTax': ('Net ertelenmiş vergi geliri/gideri', [3360, 3721, 3001, 395]),
    }, IS_PDF, 'Konsolide gelir tablosu, basılı s.10. Ertelenmiş vergi = gelir etkisi − gider etkisi.')
    regulatory(isctr, IS_PDF, [
        ('car', 'Sermaye yeterliliği', 15.56, 17.14, '30.09.2026', '31.12.2025'),
        ('npl', 'Takipteki kredi oranı', 3.87, 3.1, '30.09.2026', '31.12.2025'),
        ('lcr', 'Likidite karşılama · TP+YP', 124.31, None, '3Ç26 ortalaması', None),
        ('nsfr', 'Net istikrarlı fonlama', 116.68, 117.76, '30.09.2026', '31.12.2025'),
    ], 'Konsolide risk yönetimi ve faaliyet raporu. Önceki takip oranı raporda tek ondalık.')
    isctr['companySource'] = IS_PDF
    isctr['provisionNote'] = '9A26 beklenen kredi zararı gideri 62.237 mn TL (9A25: 42.205). Banka, 2026 portföy satışları ve kayıttan düşümler olmadan takip oranının %3,87 yerine %4,19 olacağını hesaplıyor (kredi dipnotu).'
    isctr['maturity'] = 'Konsolide 3Ç26 toplam likidite karşılama ortalaması %124,31, net istikrarlı fonlama oranı %116,68. Kredi/mevduat oranı ayrıca gösterilir.'
    isctr['researchNotes'] = [
        '9A26 ana ortaklık net kârı 40.437 mn TL (9A25: 44.127); toplam konsolide kâr 59.059 mn TL. 3Ç26 ana ortaklık kârı 10.349 mn TL (3Ç25: 14.089).',
        'Net faiz geliri %63,0, net ücret ve komisyon geliri %35,1 arttı. Beklenen kredi zararı giderindeki artış ve 12.750 mn TL net ticari zarar kâra baskı yaptı.',
    ]
    isctr['note'] = '\n\n'.join(isctr['researchNotes'])

    halk = {
        'code': 'HALKB', 'name': 'Halkbank', 'sector': 'Bankacılık',
        'source': HALK_KAP, 'companySource': HALK_PDF + '.pdf',
        'attachments': [HALK_PDF + '_finansallar.pdf', HALK_PDF + '.pdf'],
        'basis': 'BDDK / konsolide', 'unit': 'Milyon TL', 'originalUnit': '1.000.000 TL',
        'financialDate': '2026-09-30', 'importedAt': '2026-11-10',
        'verified': True, 'previous': {}, 'quarter': {}, 'quarterPrevious': {}, 'fieldSources': {},
        'documentHash': 'b204cb9e3d6367d06a36ea59da56c84cf3679a60ff2ee0ac70ad02c2f71c31c9',
        'documentHashSource': HALK_PDF + '_finansallar.pdf',
        'provenance': 'Halkbank konsolide mali tabloları ve dipnotları; 2026/09 ana kalemleri KAP şirket finansal bilgileriyle eşleşiyor.',
        'confidence': 'KAP özeti ve banka mali tabloları eşleşti · konsolide',
        'guidance': 'Karşılaştırılabilir sayısal yönetim rehberi doğrulanmadı.',
        'gaps': ['Sayısal yönetim rehberinin karşılaştırılması', 'Hedef fiyat revizyon tarihi'],
        'oneoffNote': 'Tek seferlik kalemlerin tamamı ayrıştırılmadı. Net ertelenmiş vergi ve net ticari sonuç ayrı gösteriliyor.',
        'maturity': 'Konsolide 3Ç26 toplam likidite karşılama ortalaması %167,54; net istikrarlı fonlama oranı %134,00.',
        'provisionNote': '9A26 beklenen kredi zararı gideri 34.632 mn TL (9A25: 25.923). Bilanço karşılığı itfa edilmiş maliyetle ölçülen finansal varlıkların beklenen zarar satırıdır.',
        'catalysts': 'Net faiz gelirindeki artış ve takipteki kredi oranı izlenecek. KAP açıklamaları Haber ve Bildirimler ekranında yer alır.',
        'researchNotes': [
            '9A26 ana ortaklık kârı 25.941 mn TL (9A25: 20.204); toplam konsolide kâr 27.013 mn TL. 3Ç26 ana ortaklık kârı 8.212 mn TL (3Ç25: 7.546).',
            'Net faiz geliri %106,8, net ücret ve komisyonlar %32,1 arttı. Net ticari zarar 32.081 mn TL; takipteki kredi oranı %3,89’dan %4,59’a yükseldi.',
        ],
    }
    apply_fields(halk, {
        'assets': ('Varlıklar toplamı', [5383416, 4497070]),
        'equity': ('Özkaynaklar', [259290, 222945]),
        'loans': ('Krediler', [2704056, 2095987]),
        'deposits': ('Mevduat', [4130089, 3607838]),
        'provision': ('Karşılıklar', [21574, 15494]),
        'expectedLoss': ('İtfa edilmiş maliyetli finansal varlık beklenen zarar karşılıkları', [-85697, -68437]),
        'capital': ('Ödenmiş sermaye', [7185, 7185]),
    }, HALK_PDF + '_finansallar.pdf', 'Konsolide bilanço, basılı s.6–7.')
    apply_fields(halk, {
        'netInterest': ('Net faiz geliri', [134264, 64915, 52925, 23461]),
        'netFees': ('Net ücret ve komisyon gelirleri', [57821, 43780, 21713, 16118]),
        'tradingIncome': ('Net ticari kâr/zarar', [-32081, -9134, -15747, -2617]),
        'operating': ('Net faaliyet kârı', [32557, 19021, 11116, 6196]),
        'pretax': ('Vergi öncesi kâr', [32990, 19358, 11289, 6338]),
        'netIncome': ('Ana ortaklığa düşen net kâr', [25941, 20204, 8212, 7546]),
        'groupNetIncome': ('Konsolide dönem net kârı', [27013, 20721, 8401, 6913]),
        'eclExpense': ('Beklenen zarar karşılıkları giderleri', [-34632, -25923, -12165, -12099]),
        'tax': ('Net vergi etkisi', [-5977, 1363, -2888, 575]),
        'currentTax': ('Cari vergi gideri', [-4160, -2068, -1595, -816]),
        'deferredTax': ('Net ertelenmiş vergi etkisi', [-1817, 3431, -1293, 1391]),
    }, HALK_PDF + '_finansallar.pdf', 'Konsolide gelir tablosu, basılı s.10.')
    halk['ocf'], halk['previous']['ocf'] = -18251, 216854
    halk['fieldSources']['ocf'] = {'url': HALK_PDF + '_finansallar.pdf', 'kind': 'Konsolide nakit akışı', 'note': 'Basılı s.13; bankacılık faaliyetleri, 9A26 ve 9A25.'}
    regulatory(halk, HALK_PDF + '.pdf', [
        ('car', 'Sermaye yeterliliği', 13.55, 15.56, '30.09.2026', '31.12.2025'),
        ('npl', 'Takipteki kredi oranı', 4.59, 3.89, '30.09.2026', '31.12.2025'),
        ('lcr', 'Likidite karşılama · TP+YP', 167.54, None, '3Ç26 ortalaması', None),
        ('nsfr', 'Net istikrarlı fonlama', 134.00, 137.76, '3Ç26 ortalaması', '4Ç25 ortalaması'),
    ], 'Konsolide sermaye ve likidite dipnotları, faaliyet raporu gösterge rasyoları.')
    halk['annualizedROE'] = halk['netIncome'] * (4 / 3) / ((halk['equity'] + halk['previous']['equity']) / 2) * 100
    halk['loanDeposit'] = halk['loans'] / halk['deposits'] * 100
    halk['catalystComponents'] = [{'label': '9 aylık ana ortaklık kârı önceki döneme göre arttı', 'points': 10}]
    halk['catalystScore'] = 60
    halk['catalystMethod'] = '50 nötr taban + doğrulanmış yıllık kâr artışı (10 puan).'
    halk['note'] = '\n\n'.join(halk['researchNotes'])
    quote = next(row for row in market['companies'] if row['code'] == 'HALKB')
    halk.update(quote, priceDate=market['date'], marketSource=market['source'], bist=2.0, bistYtd=4.01, benchmarkSource=BIST)
    peers = [r for r in market['companies'] if r['sector'] == 'Bankacılık']
    halk['sectorPeers'] = [r['code'] for r in peers]
    halk['peerStats'] = {}
    for key in ('return', 'ytdReturn', 'pe', 'pb', 'multiple'):
        values = [r[key] for r in peers if r.get(key) is not None and
                  (key in {'return', 'ytdReturn'} or (r[key] > 0 and r.get('ratioPeriod') == '9/2026'))]
        halk['peerStats'][key] = {'median': median(values) if len(values) >= 3 else None, 'count': len(values)}
    halk['sectorReturn'] = halk['peerStats']['return']['median']
    halk['target'] = 52.30
    halk['analystTargets'] = [{'firm': 'Şeker Yatırım', 'target': 52.30, 'recommendation': 'TUT', 'date': None, 'source': SEKER}]
    halk['fieldSources']['target'] = {'url': SEKER, 'kind': 'Aracı kurum hedefi', 'note': '10.11.2026 erişim; revizyon tarihi kaynakta yok.'}
    for key in ('price', 'pe', 'pb', 'marketCap', 'return'):
        halk['fieldSources'][key] = {'url': market['source'], 'kind': 'İş Yatırım · 09.11.2026 kapanış'}
    halk['valuation'] = 'Fiyat ve çarpanlar İş Yatırım 09.11.2026 kesitidir. Şeker Yatırım hedefinin revizyon tarihi belirtilmiyor.'
    base['HALKB:2026/9'] = halk
