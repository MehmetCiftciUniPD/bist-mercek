'use client';
import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { TriangleAlert } from 'lucide-react';
import Analysis from './Analysis';
import {
  derivedRows,
  historyFields,
  historyWarnings,
  isFinancialGroup,
  isInterim,
  periodLabel,
  type HistoryCompany,
  type HistoryResponse,
} from '../lib/history-fields';

type State =
  | { status: 'loading' }
  | { status: 'empty' | 'error'; message: string }
  | { status: 'ready'; data: HistoryResponse };

// Doğrulanmış iki serili palet (açık zemin): kimlik rengi + gösterge etiketi.
const SERIES = { primary: '#1f8a62', net: '#3b6fb5' };

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const fmt = (value: unknown) =>
  finite(value)
    ? value.toLocaleString('tr-TR', { maximumFractionDigits: Math.abs(value) >= 1000 ? 0 : 1 })
    : '—';
const pct = (value: number | null) =>
  value === null
    ? '—'
    : (value < 0 ? '−%' : '%') + Math.abs(value).toLocaleString('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Eksen için kısa gösterim; girdiler milyon TL'dir. */
function compact(value: number) {
  const abs = Math.abs(value);
  const short = (n: number) => n.toLocaleString('tr-TR', { maximumFractionDigits: 1 });
  if (abs >= 1e6) return short(value / 1e6) + ' trn';
  if (abs >= 1e3) return short(value / 1e3) + ' mlr';
  return short(value) + ' mn';
}

type Point = { period: string; value: number | null };

/** Tek serili küçük grafik. Ölçekleri farklı iki ölçü ortak eksene konmaz. */
function MiniChart({ title, color, unit, points }: { title: string; color: string; unit: string; points: Point[] }) {
  const negative = points.some(point => (point.value ?? 0) < 0);
  return (
    <div className="history-chart-panel">
      <b>
        <i style={{ background: color }} />
        {title}
      </b>
      <div className="history-chart-plot">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 8, right: 4, bottom: 0, left: 0 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke="#e4e8e2" />
            <XAxis
              dataKey="period"
              tickLine={false}
              axisLine={{ stroke: '#cfd6cc' }}
              tick={{ fontSize: 10, fill: '#6b7b60' }}
              tickFormatter={(period: string) => period.slice(0, 4)}
              interval={0}
            />
            <YAxis width={56} tickLine={false} axisLine={false} tickFormatter={compact} tick={{ fontSize: 10, fill: '#6b7b60' }} />
            {negative && <ReferenceLine y={0} stroke="#9aa495" />}
            <Tooltip
              cursor={{ fill: '#21453412' }}
              formatter={value => [`${fmt(Number(value))} ${unit}`, title]}
              labelFormatter={label => `${label} · yıl sonu`}
              contentStyle={{ fontSize: 11, borderRadius: 7, border: '1px solid #e4e8e2', color: '#172d29' }}
              itemStyle={{ color: '#172d29' }}
            />
            <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} maxBarSize={30} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function AnnualChart({ company, unit }: { company: HistoryCompany; unit: string }) {
  const financial = isFinancialGroup(company.group);
  const primaryKey = financial ? 'assets' : 'revenue';
  const primaryLabel = financial ? 'Toplam varlıklar' : 'Hasılat';
  const series = (key: string): Point[] =>
    company.periods
      .map((period, i) => ({ period, value: finite(company.values[key]?.[i]) ? company.values[key][i] : null }))
      .filter(point => !isInterim(point.period));
  const panels = [
    { title: primaryLabel, color: SERIES.primary, points: series(primaryKey) },
    { title: 'Net kâr (ana ortaklık)', color: SERIES.net, points: series('netIncome') },
  ].filter(panel => panel.points.some(point => point.value !== null));
  if (!panels.length) return null;

  return (
    <figure className="history-chart">
      <figcaption>
        <b>Yıllık görünüm · {panels.map(panel => panel.title.toLocaleLowerCase('tr')).join(' ve ')}</b>
      </figcaption>
      <div className="history-chart-grid">
        {panels.map(panel => (
          <MiniChart key={panel.title} unit={unit} {...panel} />
        ))}
      </div>
      <small>
        Yalnızca yıl sonu dönemleri · {unit} · her grafiğin ekseni ayrıdır · nominal (yayımlandığı) tutarlar; yıllar
        arası fark enflasyon ve TMS 29 etkisini içerir.
      </small>
    </figure>
  );
}

function HistoryTable({ data }: { data: HistoryResponse }) {
  const { company } = data;
  const rows = historyFields.filter(([key]) => company.values[key]?.some(finite));
  const derived = derivedRows(company);
  return (
    <div className="table-scroll">
      <table className="financial-table history-table">
        <thead>
          <tr>
            <th>Kalem · mn TL</th>
            {company.periods.map(period => (
              <th key={period} className={isInterim(period) ? 'interim' : undefined}>
                {periodLabel(period)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, label]) => (
            <tr key={key}>
              <td>{label}</td>
              {company.periods.map((period, i) => (
                <td key={period} className={isInterim(period) ? 'interim' : undefined}>
                  {fmt(company.values[key][i])}
                </td>
              ))}
            </tr>
          ))}
          {derived.map(row => (
            <tr key={row.key} className="derived">
              <td>
                {row.label}
                <small>Hesaplanan</small>
              </td>
              {company.periods.map((period, i) => (
                <td key={period} className={isInterim(period) ? 'interim' : undefined}>
                  {row.percent ? pct(row.values[i]) : fmt(row.values[i])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CompanyHistory({ code }: { code: string }) {
  const [state, setState] = useState<State>({ status: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/history?code=' + encodeURIComponent(code), { signal: controller.signal })
      .then(async response => {
        const body = (await response.json().catch(() => null)) as (HistoryResponse & { error?: string }) | null;
        if (response.ok && body?.company) setState({ status: 'ready', data: body });
        else if (response.status === 404 || response.status === 400) {
          setState({ status: 'empty', message: body?.error || 'Bu şirket için çok yıllı geçmiş verisi bulunmuyor.' });
        } else setState({ status: 'error', message: body?.error || 'Geçmiş verisi yüklenemedi.' });
      })
      .catch(error => {
        if (error?.name !== 'AbortError') setState({ status: 'error', message: 'Geçmiş verisi yüklenemedi. Bağlantıyı kontrol edip yeniden deneyin.' });
      });
    return () => controller.abort();
  }, [code]);

  const data = state.status === 'ready' ? state.data : null;
  const hasValues = !!data && Object.values(data.company.values).some(series => series.some(finite));
  const interim = data?.company.periods.filter(isInterim) ?? [];
  const warnings = data ? historyWarnings(data.company) : [];

  return (
    <div className="research-view history-view">
      {warnings.length > 0 && (
        <div className="gaps history-warnings" role="note">
          <b>
            <TriangleAlert size={15} aria-hidden="true" /> Veri uyarısı
          </b>
          <ul>
            {warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      <Analysis code={code} />
      <h3>Çok yıllı finansal geçmiş</h3>
      {state.status === 'loading' && (
        <p className="hint" role="status">
          Geçmiş verisi yükleniyor…
        </p>
      )}
      {state.status === 'empty' && <div className="empty-state">{state.message}</div>}
      {state.status === 'error' && (
        <div className="gaps" role="alert">
          {state.message}
        </div>
      )}
      {data && (
        <>
          <div className="research-banner">
            <span>
              <b>{data.company.name}</b> · {data.company.basis} · {data.unit}
              {data.code !== data.requestedCode && <> · {data.code} kodu üzerinden</>}
            </span>
            <small>{data.note}</small>
            <small>
              <a href={data.company.source || data.source} target="_blank" rel="noreferrer">
                Kaynak: İş Yatırım şirket kartı ↗
              </a>{' '}
              · Toplanma: {new Date(data.collectedAt).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' })}
            </small>
          </div>
          {!!data.company.rejected?.length && (
            <div className="gaps">
              Bilanço eşitliği sağlanmadığı için gösterilmeyen dönemler: {data.company.rejected.join(', ')}
            </div>
          )}
          {hasValues ? (
            <>
              <AnnualChart company={data.company} unit={data.unit} />
              <HistoryTable data={data} />
              <p className="hint">
                — kaynakta bulunmayan değer; boş bırakılır, tahmin edilmez.
                {interim.length > 0 && (
                  <>
                    {' '}
                    {interim.map(periodLabel).join(' ve ')} ara dönemdir: gelir ve nakit akışı kalemleri yıl başından
                    itibaren kümülatiftir, tam yıl ile büyüme olarak karşılaştırılmaz.
                  </>
                )}{' '}
                Yatırım harcaması kaynak işaretiyle gösterilir. Türetilmiş satırlar yalnızca aynı dönemde tüm girdiler
                mevcutsa hesaplanır.
              </p>
            </>
          ) : (
            <div className="empty-state">Bu şirket için kaynakta sayısal geçmiş değeri bulunmuyor.</div>
          )}
        </>
      )}
    </div>
  );
}
