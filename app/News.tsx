'use client';

import { useEffect, useState } from 'react';
import type { NewsSnapshot, NewsStream } from '../lib/news';

const streams = [
  { code: 'kap', title: 'KAP bildirimleri', description: 'Finansal rapor, özel durum, yatırım ve sermaye hareketleri.' },
  { code: 'market', title: 'Piyasa haberleri', description: 'Bloomberg HT kaynaklı piyasa ve ekonomi başlıkları.' },
] as const;

function Feed({ code, title, description }: typeof streams[number]) {
  const [snapshot, setSnapshot] = useState<NewsSnapshot | null>(null);
  const [status, setStatus] = useState('Yükleniyor…');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const endpoint = `/api/news?stream=${code satisfies NewsStream}`;

  useEffect(() => {
    const signal = new AbortController();
    fetch(endpoint, { signal: signal.signal, cache: 'no-store' }).then(async response => {
      if (!response.ok) throw Error('Kayıtlı haberler yüklenemedi.');
      setSnapshot(await response.json());
      setStatus('');
    }).catch(error => { if (!signal.signal.aborted) setStatus(error.message); });
    return () => signal.abort();
  }, [endpoint]);

  async function refresh() {
    setBusy(true);
    setStatus('');
    try {
      const response = await fetch(endpoint, { method: 'POST' });
      const body = await response.json() as NewsSnapshot & { error?: string };
      if (!response.ok) throw Error(body.error || 'Yenileme başarısız.');
      setSnapshot(body);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Yenileme başarısız.');
    } finally {
      setBusy(false);
    }
  }

  const items = (snapshot?.items ?? []).filter(item =>
    `${item.title} ${item.summary}`.toLocaleLowerCase('tr').includes(query.trim().toLocaleLowerCase('tr')),
  ).slice(0, 30);
  const local = (value: string) => new Date(value).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' });
  return <section className="table-section">
    <div className="section-title"><h2>{title}</h2><button disabled={busy} onClick={refresh}>{busy ? 'Yenileniyor…' : 'Kaynağı yenile'}</button></div>
    <p className="hint market-hint">{description} {snapshot ? `Son kayıt ${local(snapshot.updated)} (TSİ).` : ''}</p>
    {status && <p role="status" className="hint market-hint">{status}</p>}
    <div className="filters"><input aria-label={`${title} içinde ara`} placeholder="Şirket veya başlık ara…" value={query} onChange={event => setQuery(event.target.value)} /></div>
    <div className="table-scroll"><table><thead><tr><th>Başlık ve kaynak</th><th>Yayın zamanı (TSİ)</th></tr></thead>
      <tbody>{items.map(item => <tr key={item.id}><td><a href={item.url} target="_blank" rel="noreferrer">{item.title} ↗</a><small>{item.source}{item.summary ? ` · ${item.summary}` : ''}</small></td><td>{local(item.date)}</td></tr>)}</tbody>
    </table></div>
    {!items.length && !status && <div className="empty-state">{snapshot ? 'Aramaya uygun başlık yok.' : 'Henüz kayıt yok. Kaynağı yenileyebilirsin.'}</div>}
  </section>;
}

export default function News() {
  return <><p className="hint market-hint">Kurum araştırmaları · <a href="https://www.isyatirim.com.tr/tr-tr/analiz/arastirma-raporlari/Sayfalar/default.aspx" target="_blank" rel="noreferrer">İş Yatırım ↗</a> · <a href="https://www.halkyatirim.com.tr/content/tr/arastirma" target="_blank" rel="noreferrer">Halk Yatırım ↗</a></p>{streams.map(stream => <Feed key={stream.code} {...stream} />)}</>;
}
