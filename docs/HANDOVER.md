# Handover log

Newest entry first. Each agent adds an entry when it finishes a piece of work.

## 2026-11-11 · Claude Code · 2026/9 basis and risk flags

- The scorecard now uses 2026/9 against 2025/9 (537 issuers); 54 issuers
  without both columns fall back to 2025 against 2024. Nine-month flows are
  multiplied by 12/9 where they meet a balance or market value. Piotroski
  compares the two nine-month periods directly.
- `research/history.py` also collects 2025/9. Existing values were unchanged.
- `data/risk-flags.json` lists shares named in the 2026 fund investigation,
  from press reports only, in three levels: `spk` (SPK decision reported),
  `savcilik` (in both press lists of the prosecutor's request) and `tek` (one
  list only or conflicting codes). The site's "Yüksek risk" filter covers the
  first two levels plus Yakın İzleme Pazarı. Update the file by hand from
  dated sources; never add a share without a source.
- The site's list columns show 2026/9 revenue and net income.

## 2026-11-11 · Claude Code · fundamental scorecard

- `research/scorecard.py` writes `data/scorecard.json`; the public site shows
  it in a "Temel analiz skor kartı" tab, with an F-Skor column and two filters.
- Templates: industrial 453, holding/GYO 113, financial 17, bank 10. Piotroski,
  Altman Z'', Greenblatt and net debt/EBITDA are computed for industrials only.
- Adaptations to the published methods: ratios use same-year year-end balances
  (statements are as published per year under TMS 29); Altman's retained
  earnings is prior-year earnings + period earnings + restricted reserves;
  the equity-issue signal reads the cash-flow line for paid capital increases;
  Beneish is not computed because its sales growth index is not comparable.
- `research/history.py` now also collects receivables, inventories, PP&E,
  reserves, prior-year and period earnings, marketing and admin expenses and
  capital increases. Existing values were unchanged by the reprocess.
- Verification: ASELS's F-Score inputs and Z'' were recomputed independently
  and matched. Coefficients and thresholds come from secondary sources; the
  research report lists what could not be checked against the original papers.
- Not done: the Mercek Next.js app does not show the scorecard yet.

## 2026-11-10 · Claude Code · public static site

- **Public site:** https://mehmetciftciunipd.github.io/bist-mercek/ is served by
  GitHub Pages from the `gh-pages` branch. It is a separate static page
  (`site/page.html`), not the Mercek Next.js app, and needs no server or key.
- **Rebuild and publish:** `bash research/publish-site.sh` (runs
  `research/site.py`, then force-pushes `site/dist` to `gh-pages`).
- **AI analyses:** `research/ai-analyses.py` pre-generates Turkish analyses with
  a free OpenRouter model into `data/ai-analyses.json`; the site shows them as
  stored text. The key is read from `OPENROUTER_API_KEY` and is not in the
  repo. The free tier allows 50 requests a day, so coverage grows by market
  cap, a few dozen companies per run. Replies that are short or cut off are
  rejected. Free models misread wide tables; keep the per-period prompt layout.
- **Not done:** `claude/history-ai-analysis` is still not merged into `main`.

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
