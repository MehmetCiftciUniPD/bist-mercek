# Mercek | BIST Araştırma

The Next.js app is deployed privately on Sites. Published snapshots are in
`data/`; personal notes and the audit log are stored separately in D1.

- Use Node 22+ and `npm ci`. Check TypeScript with `npx tsc --noEmit`.
- `python research/validate.py` verifies the existing sourced financial set.
- `python research/kap-universe.py --date YYYY-MM-DD` refreshes the issuer registry
  from the KAP market directory. It requires Python and lxml.
- `research/README.md` describes the source collection and normalization.
  Preserve dated source URLs, source values, reporting units and periods.
- Keep issuer membership, dated market quotes, and imported financial records
  distinct. Missing values stay null. Do not generate scores from missing inputs.
- `python research/kap-summary.py` refreshes the 2026/09 KAP summaries and
  `python research/history.py` the multi-year history (`data/history.json`).
  Both hit the network; use `--offline` to reprocess a cache. KAP outranks
  İş Yatırım wherever both exist.
- `data/history.json` is server-only (about 1 MB). Read it through
  `lib/history.ts` and `/api/history`; never import it from a client component.
- `/api/analysis` calls an OpenAI-compatible provider. The key comes only from
  the server environment: `AI_API_KEY` (or `OPENROUTER_API_KEY`), optional
  `AI_BASE_URL` and `AI_MODEL`. Locally use an ignored `.dev.vars`. The prompt
  is built from server-side data only.
- `app/page.tsx` and `app/Research.tsx` are dense; keep edits there minimal and
  put new code in separate files.
- Next milestone: resolve the 12 issuers whose history carries `warnings`
  (İş Yatırım differs from KAP, mostly GYO), fill the 35 issuers without a
  2026/9 column once they report, and separate consolidated, standalone,
  banking and industrial templates before scoring.
- Claude Code agent definitions live in `.claude/agents/`: `veri-toplayici`,
  `donem-guncelleyici`, `kaynak-uzlastirici`, `dogrulayici`,
  `arayuz-gelistirici`, `kod-temizleyici`, `temel-analiz-karti` and
  `ozetleyici` (cheap reader; use it before pulling large files into context).
  Five generic analysis agents adapted from a third-party set are listed in
  `docs/THIRD_PARTY_AGENTS.md`.
- Never commit an API key or other secret, in any file or encoding. The
  repository is public; keys belong in the host's server-side secret store.
- This repo is worked on by more than one coding agent. `AGENTS.md` is the
  shared source of truth (`CLAUDE.md` only points here). Record durable
  decisions and handovers in `docs/HANDOVER.md`, work on a branch, and do not
  rewrite another agent's files without reading that note first.
- Never commit local environment files, credentials, D1 records or personal notes.
  Review source snapshots in a branch before releasing to Sites.
