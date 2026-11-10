import { codePattern, getHistory } from '../../../lib/history';

export async function GET(req: Request) {
  const code = new URL(req.url).searchParams.get('code') ?? '';
  if (!codePattern.test(code)) {
    return Response.json({ error: 'Geçersiz hisse kodu.' }, { status: 400 });
  }
  const record = getHistory(code);
  if (!record) {
    return Response.json({ error: `${code} için çok yıllı geçmiş verisi bulunmuyor.` }, { status: 404 });
  }
  return Response.json(record, { headers: { 'Cache-Control': 'private, max-age=300' } });
}
