import { isNewsStream, readNews, refreshNews } from '../../../lib/news';

export async function GET(req: Request) {
  const stream = new URL(req.url).searchParams.get('stream');
  if (!isNewsStream(stream)) return Response.json({ error: 'Geçersiz haber akışı.' }, { status: 400 });
  try { return Response.json(await readNews(stream), { headers: { 'Cache-Control': 'no-store' } }); }
  catch { return Response.json({ error: 'Kayıtlı haberler yüklenemedi.' }, { status: 503 }); }
}

export async function POST(req: Request) {
  const stream = new URL(req.url).searchParams.get('stream');
  if (!isNewsStream(stream)) return Response.json({ error: 'Geçersiz haber akışı.' }, { status: 400 });
  try { return Response.json(await refreshNews(stream)); }
  catch (error) { return Response.json({ error: error instanceof Error ? error.message : 'Haberler yenilenemedi.' }, { status: 502 }); }
}
