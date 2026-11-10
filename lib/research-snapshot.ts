import detail from '../data/research-2026-09.json';
import kapSummaries from '../data/kap-summary-2026-09.json';
import brokerSummaries from '../data/broker-summary-2026-09.json';
import market from '../data/market-2026-11-09.json';

const quotes = new Map(market.companies.map(quote => [quote.code, quote]));
const balanceFields = new Set(['assets', 'equity', 'parentEquity', 'currentAssets', 'noncurrentAssets', 'currentLiabilities', 'noncurrentLiabilities', 'deposits']);
type Summary = {
  code: string;
  source: string;
  provider?: string;
  rawFields: Record<string, [string, string, string]>;
  previous: Record<string, number>;
};

const summaries = Object.fromEntries(
  Object.entries({ ...brokerSummaries, ...kapSummaries } as unknown as Record<string, Summary>)
    .map(([id, summary]) => {
      const { rawFields, ...record } = summary;
      const provider = summary.provider ?? 'KAP';
      const fieldSources = Object.fromEntries(Object.entries(rawFields).map(([key, [label, raw, unit]]) => [
        key, { label, raw, unit, kind: `${provider} · finansal özet`, url: summary.source,
          comparison: key in summary.previous ? (balanceFields.has(key) ? '31.12.2025' : '9A25') : undefined },
      ]));
      const quote = quotes.get(summary.code);
      return [id, {
        ...quote,
        ...record,
        provider,
        fieldSources,
        originalUnit: 'Kalem bazında kaynak izinde',
        marketSource: quote ? market.source : undefined,
        priceDate: quote ? market.date : undefined,
        confidence: `${provider} · dönem, TL ve tablo kapsamı kontrol edilen özet`,
        gaps: ['Tam finansal rapor ve dipnot mutabakatı', 'Çeyrek ayrıştırması ve nakit akışı'],
      }];
    }),
);

export const financialSnapshot: Record<string, any> = { ...summaries, ...detail };
export const detailedCount = Object.keys(detail).filter(id => !id.startsWith('macro:')).length;
export const summaryCount = Object.keys(summaries).filter(id => !(id in detail)).length;
