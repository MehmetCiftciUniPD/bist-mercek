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
- Next milestone: collect the latest applicable KAP financial report IDs for the
  remaining issuers, then import and validate in batches. Separate consolidated,
  standalone, banking and industrial statement templates before scoring.
- Never commit local environment files, credentials, D1 records or personal notes.
  Review source snapshots in a branch before releasing to Sites.
