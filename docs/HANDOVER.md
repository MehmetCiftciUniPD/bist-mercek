# Handover log

Newest entry first. Each agent adds an entry when it finishes a piece of work.

## 2026-11-10 · Claude Code · branch `claude/history-ai-analysis`

Not merged to `main` and not published to Sites.

### What changed

- **KAP coverage.** `data/kap-summary-2026-09.json` went from 186 to 555 issuers;
  the earlier run had stopped on download errors. The 186 existing records are
  unchanged. 572 codes now have a 2026/9 record. 35 issuers have no 2026/09
  column on KAP (`data/kap-summary-gaps.json`).
- **History.** New `research/history.py` writes `data/history.json`: 593 of 607
  issuers, year-end 2020-2025 plus 2026/6 and 2026/9, million TL, from
  İş Yatırım company cards. 550 issuers have five or more year-ends. The 14
  misses are in `data/history-gaps.json`. Values are as published in each
  period's own report, not restated under TMS 29. Interim income and cash-flow
  figures are cumulative.
- **Warnings.** 12 issuers (AGYO, AVGYO, EKGYO, HLGYO, KRDMD, KZBGY, OZGYO,
  PSGYO, QUICK, RYGYO, SNGYO, TRGYO) differ from KAP by more than 0.5% in
  2026/9 and carry a `warnings` array. Which source is right is unresolved.
- **UI.** New "Geçmiş" tab in the company drawer (`app/History.tsx`,
  `lib/history-fields.ts`, `lib/history.ts`, `/api/history`). `app/page.tsx`
  has three small edits only.
- **AI analysis.** "Yapay zekâ analizi" button (`app/Analysis.tsx`,
  `lib/analysis.ts`, `/api/analysis`). Default provider is OpenRouter with
  model `openrouter/free`; Kimi is not free there. Any OpenAI-compatible
  provider works through `AI_BASE_URL` and `AI_MODEL`.

### Verified

- `npx tsc --noEmit` and `npm run build` pass. `python research/validate.py` passes.
- Geçmiş tab checked in a browser with real data.
- `/api/analysis` checked end to end against a local fake provider only.

### Not done or not verified

- No real AI provider was called; no key was available.
- How to define the `AI_API_KEY` secret on Sites is unknown. Until it is set,
  the button shows "Yapay zekâ anahtarı tanımlı değil".
- `npm run lint` fails with 42 problems, all in files that predate this branch.
- `/api/records` returns 500 in local dev; this predates the branch and was
  not investigated.
- `data/kap-summary-2026-09.json` grew from 316 KB to 948 KB and is in the
  client bundle through `lib/research-snapshot.ts`.

### To publish

1. Merge `claude/history-ai-analysis` into `main` after the checks above.
2. Set `AI_API_KEY` as a server secret on Sites.
3. Publish, then open a company, the Geçmiş tab and the analysis button.
