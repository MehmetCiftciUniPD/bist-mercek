// Geçmiş tablosu ve yapay zekâ istemi için ortak, veri içermeyen tanımlar.
// İstemci bileşenleri de içe aktarır; data/history.json buraya alınmamalıdır.

export type HistoryGroup = 'XI_29' | 'UFRS_K' | 'UFRS';

export type HistoryCompany = {
  name: string;
  group: HistoryGroup;
  basis: string;
  source: string;
  documentHash?: string;
  periods: string[];
  values: Record<string, (number | null)[]>;
  rejected?: string[];
  /** Kaynaklar arası fark gibi Türkçe veri uyarıları. */
  warnings?: string[];
};

/** Yalnızca boş olmayan metin uyarılarını döndürür; alan yoksa boş dizi. */
export function historyWarnings(company: HistoryCompany): string[] {
  return Array.isArray(company.warnings)
    ? company.warnings.filter((w): w is string => typeof w === 'string' && w.trim().length > 0)
    : [];
}

export type HistoryResponse = {
  code: string;
  requestedCode: string;
  unit: string;
  note: string;
  source: string;
  collectedAt: string;
  company: HistoryCompany;
};

export const historyFields: [key: string, label: string][] = [
  ['assets', 'Toplam varlıklar'],
  ['currentAssets', 'Dönen varlıklar'],
  ['noncurrentAssets', 'Duran varlıklar'],
  ['cash', 'Nakit'],
  ['loans', 'Krediler'],
  ['deposits', 'Mevduat'],
  ['currentLiabilities', 'Kısa vadeli yükümlülükler'],
  ['noncurrentLiabilities', 'Uzun vadeli yükümlülükler'],
  ['shortDebt', 'Kısa vadeli finansal borç'],
  ['longDebt', 'Uzun vadeli finansal borç'],
  ['equity', 'Özkaynaklar'],
  ['parentEquity', 'Ana ortaklığa ait özkaynaklar'],
  ['revenue', 'Hasılat'],
  ['grossProfit', 'Brüt kâr'],
  ['netInterest', 'Net faiz geliri'],
  ['netFees', 'Net ücret ve komisyon'],
  ['operating', 'Esas faaliyet kârı'],
  ['pretax', 'Vergi öncesi kâr'],
  ['netIncome', 'Net kâr (ana ortaklık)'],
  ['groupNetIncome', 'Net kâr (toplam)'],
  ['depreciation', 'Amortisman'],
  ['ocf', 'İşletme nakit akışı'],
  ['capex', 'Yatırım harcaması'],
  ['fcf', 'Serbest nakit akışı'],
];

export const isFinancialGroup = (group: string) => group !== 'XI_29';

/** Yıl sonu dışındaki dönemler kümülatif ara dönemdir. */
export const isInterim = (period: string) => !period.endsWith('/12');

/** "2026/9" → "2026/9 (9A)"; yıl sonu dönemleri değişmeden kalır. */
export function periodLabel(period: string) {
  const month = period.split('/')[1];
  return isInterim(period) ? `${period} (${month}A)` : period;
}

const finite = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

export type DerivedRow = { key: string; label: string; percent: boolean; values: (number | null)[] };

/**
 * Türetilmiş satırlar. Bir dönemde girdilerden biri eksikse o hücre null kalır;
 * eksik girdi sıfır sayılmaz.
 */
export function derivedRows(company: HistoryCompany): DerivedRow[] {
  const v = company.values;
  const at = (key: string, i: number) => {
    const value = v[key]?.[i];
    return finite(value) ? value : null;
  };
  const each = (fn: (i: number) => number | null) => company.periods.map((_, i) => fn(i));
  const rows: DerivedRow[] = [
    {
      key: 'netDebt',
      label: 'Net borç',
      percent: false,
      values: each(i => {
        const s = at('shortDebt', i), l = at('longDebt', i), c = at('cash', i);
        return s === null || l === null || c === null ? null : s + l - c;
      }),
    },
    {
      key: 'netMargin',
      label: 'Net kâr marjı',
      percent: true,
      values: each(i => {
        const n = at('netIncome', i), r = at('revenue', i);
        return n === null || r === null || r <= 0 ? null : (n / r) * 100;
      }),
    },
    {
      key: 'equityToAssets',
      label: 'Özkaynak / varlık',
      percent: true,
      values: each(i => {
        const e = at('equity', i), a = at('assets', i);
        return e === null || a === null || a <= 0 ? null : (e / a) * 100;
      }),
    },
  ];
  return rows.filter(row => row.values.some(value => value !== null));
}
