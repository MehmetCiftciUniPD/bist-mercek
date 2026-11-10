'use client';
import { Fragment, useState } from 'react';
import { Sparkles } from 'lucide-react';

type Result = { analysis: string; model: string; generatedAt: string; inputPeriods: string[] };
type Block =
  | { kind: 'heading' | 'paragraph'; text: string }
  | { kind: 'list'; items: string[] };

/** Model çıktısını düz metin olarak başlık, paragraf ve madde listelerine ayırır. */
function toBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || /^[-*_]{3,}$/.test(line)) continue;
    const heading = /^#{1,6}\s+(.*)$/.exec(line) ?? /^\*\*([^*]+)\*\*:?$/.exec(line);
    const bullet = /^(?:[-*•–]|\d{1,2}[.)])\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({ kind: 'heading', text: heading[1].replace(/\*\*/g, '').replace(/:$/, '') });
    } else if (bullet) {
      const last = blocks[blocks.length - 1];
      if (last?.kind === 'list') last.items.push(bullet[1]);
      else blocks.push({ kind: 'list', items: [bullet[1]] });
    } else {
      blocks.push({ kind: 'paragraph', text: line });
    }
  }
  return blocks;
}

/** **kalın** işaretlerini <strong> olarak gösterir; başka biçimlendirme yorumlanmaz. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>))}
    </>
  );
}

export const AI_DISCLAIMER = 'Yapay zekâ tarafından üretilmiştir; hata içerebilir. Yatırım tavsiyesi değildir.';

export default function Analysis({ code }: { code: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);

  async function run() {
    setBusy(true);
    setError('');
    try {
      const response = await fetch('/api/analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      const body = (await response.json().catch(() => null)) as (Partial<Result> & { error?: string }) | null;
      if (!response.ok || typeof body?.analysis !== 'string') {
        throw new Error(body?.error || 'Analiz üretilemedi; yeniden deneyin.');
      }
      setResult(body as Result);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : 'Analiz üretilemedi; yeniden deneyin.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="analysis">
      <div className="analysis-head">
        <button type="button" className="primary" onClick={run} disabled={busy}>
          <Sparkles size={16} aria-hidden="true" />
          {busy ? 'Analiz hazırlanıyor…' : result ? 'Analizi yenile' : 'Yapay zekâ analizi'}
        </button>
        <small>Yalnızca bu paneldeki kaynaklı geçmiş ve 2026/9 verileri modele gönderilir.</small>
      </div>
      {error && (
        <div className="gaps" role="alert">
          {error}
        </div>
      )}
      {busy && !result && (
        <p className="hint" role="status">
          Model yanıtı bekleniyor; bu işlem 45 saniyeye kadar sürebilir.
        </p>
      )}
      {result && (
        <article className="analysis-result" aria-busy={busy}>
          {toBlocks(result.analysis).map((block, i) =>
            block.kind === 'heading' ? (
              <h4 key={i}>{block.text}</h4>
            ) : block.kind === 'list' ? (
              <ul key={i}>
                {block.items.map((item, j) => (
                  <li key={j}>
                    <Inline text={item} />
                  </li>
                ))}
              </ul>
            ) : (
              <p key={i}>
                <Inline text={block.text} />
              </p>
            ),
          )}
          <small className="analysis-meta">
            Model: {result.model} · {new Date(result.generatedAt).toLocaleString('tr-TR')}
            {result.inputPeriods?.length > 0 && <> · Girdi dönemleri: {result.inputPeriods.join(', ')}</>}
          </small>
        </article>
      )}
      <p className="analysis-disclaimer">{AI_DISCLAIMER}</p>
    </div>
  );
}
