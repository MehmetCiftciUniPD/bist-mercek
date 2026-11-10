import { isNewsStream, readNews, refreshNews } from '../../lib/news';

const inputSchema = {
  type: 'object',
  properties: { stream: { type: 'string', enum: ['kap', 'market'] } },
  required: ['stream'],
  additionalProperties: false,
};
const tools = [
  { name: 'refresh_news', description: 'Refresh and save the private Mercek KAP or market headlines. Returns the update timestamp and headlines.', inputSchema },
  { name: 'read_news', description: 'Read the saved Mercek KAP or market news snapshot without changing it.', inputSchema, annotations: { readOnlyHint: true } },
];

export async function POST(req: Request) {
  let message: { id?: string | number | null; method?: string; params?: { name?: string; arguments?: { stream?: unknown } } } | null;
  try { message = await req.json() as typeof message; }
  catch { return Response.json({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Invalid JSON' } }); }
  const { id, method, params } = message ?? {};
  const result = (value: unknown) => Response.json({ jsonrpc: '2.0', id: id ?? null, result: value });
  const failure = (code: number, detail: string) => Response.json({ jsonrpc: '2.0', id: id ?? null, error: { code, message: detail } });
  if (method === 'server/discover') return result({ supportedVersions: ['2026-07-28'], capabilities: { tools: {} } });
  if (method === 'tools/list') return result({ tools });
  if (method !== 'tools/call') return failure(-32601, 'Unknown method');
  const stream = params?.arguments?.stream;
  if (!isNewsStream(stream)) return failure(-32602, 'Invalid stream');
  if (!tools.some(tool => tool.name === params?.name)) return failure(-32602, 'Unknown tool');
  try {
    const snapshot = params?.name === 'refresh_news' ? await refreshNews(stream) : await readNews(stream);
    return result({ content: [{ type: 'text', text: JSON.stringify(snapshot && {
      updated: snapshot.updated, count: snapshot.items.length, items: snapshot.items.slice(0, 12),
    }) }] });
  } catch (error) {
    return result({ isError: true, content: [{ type: 'text', text: error instanceof Error ? error.message : 'News source unavailable' }] });
  }
}
