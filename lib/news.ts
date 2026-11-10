import { eq } from 'drizzle-orm';
import { getDb } from '../db';
import { records } from '../db/schema';

export const streams = ['kap', 'market'] as const;
export type NewsStream = typeof streams[number];
export type Headline = { id: string; title: string; summary: string; date: string; url: string; source: string };
export type NewsSnapshot = { updated: string; items: Headline[] };

const feeds = {
  kap: 'https://kap.org.tr/tr/api/disclosure/list/light',
  market: 'https://www.bloomberght.com/rss',
};
const key = (stream: NewsStream) => `news:${stream}`;
const clean = (value: unknown, max: number) => String(value ?? '').trim().slice(0, max);
const entity = (s: string) => s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
  .replace(/&#(x[\da-f]+|\d+);/gi, (original, code: string) => {
    const n = code.startsWith('x') ? parseInt(code.slice(1), 16) : Number(code);
    return n >= 0 && n <= 0x10ffff ? String.fromCodePoint(n) : original;
  }).replace(/&(amp|quot|apos|lt|gt);/g, (_, n: string) => ({ amp: '&', quot: '"', apos: "'", lt: '<', gt: '>' })[n] ?? '')
  .replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

export function isNewsStream(value: unknown): value is NewsStream {
  return value === 'kap' || value === 'market';
}

export async function readNews(stream: NewsStream): Promise<NewsSnapshot | null> {
  const [row] = await getDb().select({ data: records.data }).from(records).where(eq(records.id, key(stream)));
  return row ? JSON.parse(row.data) : null;
}

function kapItems(body: unknown): Headline[] {
  if (!Array.isArray(body)) throw Error('KAP yanıtı beklenen liste biçiminde değil.');
  const items: Headline[] = [];
  for (const row of body) {
    const id = String(row?.disclosureIndex ?? '');
    const subject = clean(row?.subject, 240);
    const title = clean(row?.title, 240);
    const match = /^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2}:\d{2})$/.exec(String(row?.publishDate));
    if (!match || !/^\d+$/.test(id) || !subject || !title) continue;
    if (!/finansal|faaliyet raporu|özel durum|yatırım|sözleşme|kâr payı|sermaye artır|geri alım|derecelendirme/i.test(subject)) continue;
    const date = new Date(`${match[3]}-${match[2]}-${match[1]}T${match[4]}+03:00`);
    if (!Number.isFinite(date.valueOf())) continue;
    items.push({ id, title: `${title} · ${subject}`, summary: clean(row.summary, 320), date: date.toISOString(), url: `https://kap.org.tr/tr/Bildirim/${id}`, source: 'KAP' });
  }
  return items;
}

function marketItems(xml: string): Headline[] {
  const items: Headline[] = [];
  for (const match of xml.matchAll(/<item>([\s\S]*?)<\/item>/gi)) {
    const tag = (name: string) => entity(match[1].match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\/${name}>`, 'i'))?.[1] ?? '');
    const title = tag('title');
    const date = new Date(tag('pubDate'));
    let url: URL;
    try { url = new URL(tag('link')); } catch { continue; }
    if (url.protocol !== 'https:' || !['www.bloomberght.com', 'bloomberght.com'].includes(url.hostname) || !title || !Number.isFinite(date.valueOf())) continue;
    items.push({ id: url.href, title: clean(title, 240), summary: '', date: date.toISOString(), url: url.href, source: 'Bloomberg HT' });
  }
  return items;
}

export async function refreshNews(stream: NewsStream): Promise<NewsSnapshot> {
  const response = await fetch(feeds[stream], { signal: AbortSignal.timeout(12000) });
  if (!response.ok) throw Error(`${stream === 'kap' ? 'KAP' : 'Piyasa haberleri'} kaynağı HTTP ${response.status} döndürdü.`);
  const incoming = stream === 'kap' ? kapItems(await response.json()) : marketItems(await response.text());
  if (!incoming.length) throw Error('Kaynakta işlenebilen haber bulunamadı; son kayıt korundu.');
  const before = await readNews(stream);
  const unique = new Map((before?.items ?? []).map(item => [item.id, item]));
  for (const item of incoming) unique.set(item.id, item);
  const snapshot = {
    updated: new Date().toISOString(),
    items: [...unique.values()].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 160),
  };
  const data = JSON.stringify(snapshot);
  await getDb().insert(records).values({ id: key(stream), data, revision: 1 })
    .onConflictDoUpdate({ target: records.id, set: { data } });
  return snapshot;
}
