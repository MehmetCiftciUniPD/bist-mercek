// Sunucu tarafı: şirket analizi için istemi yalnızca depodaki kaynaklı
// verilerden kurar ve OpenAI uyumlu bir sohbet uç noktasını çağırır.
import { env } from 'cloudflare:workers';
import market from '../data/market-2026-11-09.json';
import { derivedRows, historyFields, historyWarnings, isFinancialGroup, periodLabel } from './history-fields';
import { codePattern, getHistory } from './history';
import { financialSnapshot } from './research-snapshot';

export const SNAPSHOT_PERIOD = '2026/9';
const DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1';
const DEFAULT_MODEL = 'openrouter/free';
const TIMEOUT_MS = 45_000;

export type AnalysisResult = {
  analysis: string;
  model: string;
  generatedAt: string;
  inputPeriods: string[];
};

export class AnalysisError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function setting(name: 'AI_API_KEY' | 'OPENROUTER_API_KEY' | 'AI_BASE_URL' | 'AI_MODEL'): string {
  const fromBinding = (env as Cloudflare.Env | undefined)?.[name];
  const fromProcess = typeof process !== 'undefined' ? process.env?.[name] : undefined;
  const value = typeof fromBinding === 'string' && fromBinding.trim() ? fromBinding : fromProcess;
  return typeof value === 'string' ? value.trim() : '';
}

const number = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};
const show = (value: number | null, digits = 1) =>
  value === null ? 'eksik' : value.toLocaleString('tr-TR', { maximumFractionDigits: digits });

const snapshotFields: [key: string, label: string][] = [
  ['revenue', 'Hasılat'],
  ['operating', 'Esas faaliyet kârı'],
  ['ebitda', 'FAVÖK'],
  ['netIncome', 'Net kâr (ana ortaklık)'],
  ['groupNetIncome', 'Net kâr (toplam)'],
  ['ocf', 'İşletme nakit akışı'],
  ['capex', 'Yatırım harcaması (pozitif = çıkış)'],
  ['fcf', 'Serbest nakit akışı'],
  ['cash', 'Nakit'],
  ['short', 'Kısa vadeli finansal borç'],
  ['totalDebt', 'Toplam finansal borç'],
  ['debt', 'Net borç'],
  ['assets', 'Toplam varlıklar'],
  ['deposits', 'Mevduat'],
  ['equity', 'Özkaynaklar'],
];
const marketFields: [key: string, label: string, digits: number][] = [
  ['price', 'Fiyat (TL)', 2],
  ['marketCap', 'Piyasa değeri (milyon TL)', 1],
  ['pe', 'F/K', 1],
  ['pb', 'PD/DD', 1],
  ['multiple', 'FD/FAVÖK', 1],
];

const SYSTEM_PROMPT = [
  'Sen titiz bir hisse senedi araştırma asistanısın. Yanıtını Türkçe yaz.',
  'YALNIZCA kullanıcının verdiği sayıları kullan; dışarıdan bilgi, tahmin veya hatırladığın rakam ekleme.',
  '"eksik" olarak işaretlenen ya da hiç verilmeyen kalemleri eksik olarak belirt; eksik veriyi tahmin etme, sıfır sayma.',
  'Yıllık değerler her dönemin kendi raporunda yayımlanan tutarlardır; TMS 29 (enflasyon muhasebesi) öncesi ve sonrası yıllar doğrudan karşılaştırılamaz. Bunu büyüme yorumlarında açıkça belirt.',
  'Ara dönem (ör. 6A, 9A) gelir ve nakit akışı kalemleri kümülatiftir; tam yıl ile büyüme olarak kıyaslama.',
  'Şu başlıkları ele al: büyüme, kârlılık, borçluluk ve likidite, nakit üretimi, öne çıkan riskler, sırada neye bakılmalı.',
  'Yaklaşık 250-400 kelime yaz. Kısa başlıklar ve madde işaretleri kullanabilirsin; tablo kullanma.',
  '"Veri uyarıları" verilmişse ilgili rakamları yorumlarken bu çekinceleri açıkça an.',
  'Al/sat/tut önerisi verme, hedef fiyat verme. Bu bir yatırım tavsiyesi değildir.',
].join('\n');

type Built = { prompt: string; inputPeriods: string[] };

/** İstemi sunucudaki verilerden kurar. Şirket için hiçbir veri yoksa null döner. */
export function buildPrompt(code: string): Built | null {
  if (!codePattern.test(code)) return null;
  const history = getHistory(code);
  const snapshot: Record<string, unknown> | undefined = financialSnapshot[`${code}:${SNAPSHOT_PERIOD}`];
  if (!history && !snapshot) return null;

  const quote = market.companies.find(company => company.code === code) as Record<string, unknown> | undefined;
  const name = String(snapshot?.name ?? history?.company.name ?? quote?.name ?? code);
  const sector = String(snapshot?.sector ?? quote?.sector ?? '');
  const lines: string[] = [`Şirket: ${code} · ${name}`, `Sektör: ${sector || 'eksik'}`];
  const inputPeriods = new Set<string>();

  if (history) {
    const { company } = history;
    company.periods.forEach(period => inputPeriods.add(period));
    lines.push(
      '',
      `## Çok yıllı geçmiş (${history.unit}; kaynak: İş Yatırım şirket kartı; esas: ${company.basis})`,
      `Tablo şablonu: ${isFinancialGroup(company.group) ? 'finansal kuruluş (banka/sigorta/finansman)' : 'Seri XI No:29 (sanayi/ticaret/hizmet)'}`,
      `Not: ${history.note}`,
      `Dönemler: ${company.periods.map(periodLabel).join(' | ')}`,
    );
    for (const [key, label] of historyFields) {
      const series = company.values[key];
      if (!series?.some(value => number(value) !== null)) continue;
      lines.push(`${label}: ${company.periods.map((_, i) => show(number(series[i]))).join(' | ')}`);
    }
    for (const row of derivedRows(company)) {
      lines.push(`${row.label}${row.percent ? ' (%)' : ''} [hesaplanan]: ${row.values.map(value => show(value)).join(' | ')}`);
    }
    if (company.rejected?.length) {
      lines.push(`Bilanço tutarsızlığı nedeniyle çıkarılan dönemler: ${company.rejected.join(', ')}`);
    }
    const warnings = historyWarnings(company);
    if (warnings.length) {
      lines.push('Veri uyarıları (analizde çekince olarak belirt):', ...warnings.map(w => `- ${w.slice(0, 500)}`));
    }
    lines.push('Geçmiş tablosunda yatırım harcaması kaynak işaretiyle (genellikle negatif = nakit çıkışı) verilmiştir.');
  } else {
    lines.push('', 'Çok yıllı geçmiş: eksik (bu şirket için geçmiş verisi yok).');
  }

  if (snapshot) {
    inputPeriods.add(SNAPSHOT_PERIOD);
    const previous = (snapshot.previous && typeof snapshot.previous === 'object' ? snapshot.previous : {}) as Record<string, unknown>;
    lines.push(
      '',
      `## ${SNAPSHOT_PERIOD} kesiti (9 aylık kümülatif; ${String(snapshot.unit ?? 'Milyon TL')}; esas: ${String(snapshot.basis ?? 'eksik')})`,
      'Biçim: kalem: 2026/9 değeri (karşılaştırma: gelir/nakit için 9A25, bilanço için 31.12.2025)',
      'Karşılaştırma tutarları 2026/9 raporunda sunulan (yeniden düzenlenmiş olabilecek) tutarlardır; geçmiş tablosundaki yayımlandığı tutarlardan farklı olabilir.',
    );
    for (const [key, label] of snapshotFields) {
      const value = number(snapshot[key]);
      if (value === null) continue;
      const before = number(previous[key]);
      lines.push(`${label}: ${show(value)}${before === null ? '' : ` (karşılaştırma: ${show(before)})`}`);
    }
    const roe = number(snapshot.annualizedROE);
    if (roe !== null) lines.push(`Yaklaşık yıllıklandırılmış özkaynak kârlılığı (%): ${show(roe)}`);
  } else {
    lines.push('', `${SNAPSHOT_PERIOD} ayrıntılı kesiti: eksik.`);
  }

  const priced = { ...quote, ...snapshot } as Record<string, unknown>;
  const marketLines = marketFields
    .map(([key, label, digits]) => [label, number(priced[key]), digits] as const)
    .filter(([, value]) => value !== null)
    .map(([label, value, digits]) => `${label}: ${show(value, digits)}`);
  if (marketLines.length) {
    lines.push('', `## Piyasa verisi (${String(priced.priceDate ?? market.date)} kapanışı)`, ...marketLines);
  }

  return { prompt: lines.join('\n'), inputPeriods: [...inputPeriods] };
}

function upstreamMessage(status: number) {
  if (status === 401 || status === 403) return 'Yapay zekâ sağlayıcısı anahtarı reddetti. AI_API_KEY değerini kontrol edin.';
  if (status === 402) return 'Yapay zekâ sağlayıcısında yeterli bakiye veya kota yok.';
  if (status === 404) return 'Yapay zekâ modeli veya uç noktası bulunamadı. AI_BASE_URL ve AI_MODEL değerlerini kontrol edin.';
  if (status === 429) return 'Yapay zekâ sağlayıcısının istek sınırına ulaşıldı. Biraz sonra yeniden deneyin.';
  return `Yapay zekâ sağlayıcısı yanıt veremedi (HTTP ${status}). Biraz sonra yeniden deneyin.`;
}

export async function analyzeCompany(code: string): Promise<AnalysisResult> {
  const built = buildPrompt(code);
  if (!built) throw new AnalysisError(404, `${code} için analiz edilecek veri bulunmuyor.`);

  const apiKey = setting('AI_API_KEY') || setting('OPENROUTER_API_KEY');
  if (!apiKey) {
    throw new AnalysisError(
      503,
      'Yapay zekâ anahtarı tanımlı değil. Sunucu ortamına AI_API_KEY (veya OPENROUTER_API_KEY) ekleyin; isteğe bağlı olarak AI_BASE_URL ve AI_MODEL ile sağlayıcıyı ve modeli seçin.',
    );
  }
  const model = setting('AI_MODEL') || DEFAULT_MODEL;
  let endpoint: URL;
  try {
    endpoint = new URL(`${(setting('AI_BASE_URL') || DEFAULT_BASE_URL).replace(/\/+$/, '')}/chat/completions`);
    if (!/^https?:$/.test(endpoint.protocol)) throw new Error('protocol');
  } catch {
    throw new AnalysisError(503, 'AI_BASE_URL geçerli bir http(s) adresi değil.');
  }

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model,
        temperature: 0.3,
        max_tokens: 2000,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: built.prompt },
        ],
      }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    const timedOut = error instanceof Error && (error.name === 'TimeoutError' || error.name === 'AbortError');
    throw new AnalysisError(
      502,
      timedOut
        ? 'Yapay zekâ sağlayıcısı zamanında yanıt vermedi. Biraz sonra yeniden deneyin.'
        : 'Yapay zekâ sağlayıcısına ulaşılamadı. Biraz sonra yeniden deneyin.',
    );
  }
  if (!response.ok) {
    await response.body?.cancel().catch(() => {});
    throw new AnalysisError(502, upstreamMessage(response.status));
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new AnalysisError(502, 'Yapay zekâ sağlayıcısından okunamayan bir yanıt geldi.');
  }
  const reply = body as { model?: unknown; choices?: { message?: { content?: unknown } }[] };
  const content = reply?.choices?.[0]?.message?.content;
  const analysis = typeof content === 'string' ? content.trim().slice(0, 12_000) : '';
  if (!analysis) throw new AnalysisError(502, 'Yapay zekâ sağlayıcısı boş bir yanıt döndürdü. Yeniden deneyin veya başka bir model seçin.');

  return {
    analysis,
    model: typeof reply.model === 'string' && reply.model ? reply.model.slice(0, 120) : model,
    generatedAt: new Date().toISOString(),
    inputPeriods: built.inputPeriods,
  };
}
