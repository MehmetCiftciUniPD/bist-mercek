import { AnalysisError, analyzeCompany } from '../../../lib/analysis';
import { codePattern } from '../../../lib/history';

export async function POST(req: Request) {
  let code: unknown;
  try {
    code = ((await req.json()) as { code?: unknown } | null)?.code;
  } catch {
    return Response.json({ error: 'Geçersiz istek gövdesi.' }, { status: 400 });
  }
  if (typeof code !== 'string' || !codePattern.test(code)) {
    return Response.json({ error: 'Geçersiz hisse kodu.' }, { status: 400 });
  }
  try {
    return Response.json(await analyzeCompany(code), { headers: { 'Cache-Control': 'no-store' } });
  } catch (error) {
    if (error instanceof AnalysisError) {
      return Response.json({ error: error.message }, { status: error.status });
    }
    return Response.json({ error: 'Analiz üretilemedi; yeniden deneyin.' }, { status: 500 });
  }
}
