# Handover log

Newest entry first. Each agent adds an entry when it finishes a piece of work.

## 2026-11-25 · Claude Code · all brokers' targets and trade ideas

- `research/broker-calls.py` → `data/broker-calls.json`, from public news
  pages only (robots.txt allows them): CNBC-e's weekly target gallery
  (g40478; per share every broker's target and recommendation, and brokers'
  old → new target tables) and Paratic articles relaying brokers' technical
  lists (entry/reference, targets, stop, supports). Articles are found in
  Paratic's news sitemap, RSS and the two newest post sitemaps by address;
  `--url` adds one by hand. Broker names come from the heading before each
  table and are normalised in `canon()`.
- Foreks' forecast backend (web-forecast.foreks.com) holds the same data in a
  structured form, but it is a private API: the session's permission check
  refused calling it. Do not use it without the owner's explicit permission.
- Site: weekly view adds "Haftalık trade önerileri (stoplu)", support/resistance
  lists, all brokers' targets per share and target revisions; the stock box
  lists every broker's target and the short-term ideas. "Durum" compares the
  current price with the levels only (no intraday check).

## 2026-11-25 · Claude Code · weekly report and brokerage research

- `research/broker-reports.py` → `data/broker-reports.json`: İş Yatırım's
  covered list (recommendation, target, date, and the same 1 week / 1 month /
  3 months earlier from the 14-column table, groups in that order), its model
  portfolio, and Yahoo analyst consensus via yfinance (covered codes plus the
  150 largest). `--notes` reads analyst theses for recommendations newer than
  14 days. Revisions between runs go to `changes`. Workflow: after close and nightly.
- Site: "Haftalık · Kurum raporları" view (weekly market, sector medians,
  week's KAP flow, new/changed recommendations, model portfolio, sortable
  target table) and an "Aracı kurum görüşleri" box in the stock file.
  Yahoo mean targets above 3× price are shown as "şüpheli" (likely not
  adjusted for bonus issues) and excluded from sorting.
- Weekly returns come from İş Yatırım's `weekReturn` (row `wk`).

## 2026-11-24 · Claude Code · SPK bulletins, KAP events, screener, PWA

- `research/spk-bulletins.py` reads the 2026 SPK bulletin PDFs (pdftotext),
  the section "SUÇ DUYURUSU, İDARİ PARA CEZASI…", and records per share code:
  action type, number of persons (never names), ban length. Output
  `data/spk-actions.json`; bulletins already read are skipped. Workflow: Saturday
  and nightly runs.
- `research/market-events.py` collects from KAP search: share circuit breakers,
  SPK measure decisions, capital increases (bonus % read from text), dividends
  (gross per share from the form table; 0 → `nakit yok`), financial reports,
  first trading days and IPO results, and fund managers' 3% notices. Output
  `data/market-events.json`, events kept 400 days. `--reparse` re-reads stored
  capital and dividend notices; `--cache DIR` keeps pages.
- `research/price-history.py` now adjusts earlier prices for KAP bonus issues
  when the observed move matches 1/(1+pct/100) within 12% (field `adj`); other
  unexplained jumps still cut the series.
- Site: SPK/circuit-breaker risk box, "Şirket olayları" box, feed cards for
  these events, chips spk/cb/div/bonus/f3/ipo. Chips now combine (AND) and can
  be saved (`mercek.screens` in localStorage). PWA: `site/static/` manifest,
  icons and a network-first `sw.js`.
- Limits: IPO lock-up dates are not in KAP's structured data; most dividend
  notices are zero-cash decisions; only one bonus adjustment matched so far.

## 2026-11-24 · Claude Code · insiders, feed, sectors, compare, daily summary

- `research/insider-trades.py` writes `data/insider-trades.json` from every
  "Pay Alım Satım Bildirimi": company-filed notices (table read from the page)
  and insiders' own MKK notices (filed as "KAMUYU AYDINLATMA PLATFORMU"; the
  details are in a PDF attachment downloaded from KAP's file endpoint and read
  with `pdftotext`, installed in the workflow). Fund managers' notices are left
  out. A parent's trades in another listed company go to that company
  (`targets`). The site removes trades reported twice (insider + company).
- `buybacks.py` now opens every buyback notice once and also reads the
  programme ceiling ("azami ... adet"); the site shows usage only where a
  company's ratios rise over time (cumulative), otherwise it warns that the
  ratio may be daily.
- `research/daily-summary.py` writes `data/daily-summary.json`: breadth, top
  movers, buybacks, fund purchases, insider net buyers/sellers, CHoCH events,
  plus a free-model comment when OPENROUTER_API_KEY is set.
- Site: new views "Akış" (summary, 7-day events, price since fund purchases and
  buyback starts), "Sektörler" (medians per sector) and "Karşılaştır" (up to 3
  issuers, metrics table and rebased price chart; stored in the visitor's
  browser). New filter "Patron net alımı (30 gün)".

## 2026-11-24 · Claude Code · fund holdings and buyback candidates

- `research/fund-holdings.py` reads Fonoloji's public "SPK tasfiye" page into
  `data/fund-holdings.json`: for the ~40 largest positions, the liquidating
  funds' estimated lots, share of capital and size against the free float
  (from the funds' Aug-Oct 2026 reports). Fonoloji's /api/ is disallowed in
  its robots.txt and is not used; smaller positions are not on the page.
- The site marks "Olası fon geri alımı adayı" when a company has no purchase
  notice yet and either the funds held >= 2% of capital or >= 20% of the free
  float, or it is on the prosecutor's press lists without a Fonoloji figure.
- `insiders.py` now keeps only notices with a fund link, treats tender-offer
  notices as statements, and records `targets` when a parent buys another
  listed company's shares (IZMDC -> IZENR, TRALT -> TRENJ). Web research on
  2026-11-24 found no fund purchase beyond those on KAP; Endeks24's roundup of
  the eight 12 November purchases matches ours.

## 2026-11-23 · Claude Code · off-exchange purchases from liquidating funds

- `research/insiders.py` writes `data/fund-transfers.json`: notices where the
  company or a controlling shareholder bought shares outside the exchange from
  funds SPK put into liquidation (Sept 2026), plus company statements about
  those funds. It opens every "Pay Alım Satım Bildirimi" and buyback notice and
  the general material-event notices whose summary mentions funds, and keeps
  those whose text mentions an off-exchange trade or a liquidation.
  `kind` is `purchase` or `statement`; price, amount and share of capital are
  read from the text and stay null when absent; a missing amount is filled
  with price x shares from the same notice and flagged `amountCalc`. `checked`
  lists notices already opened. All general material-event notices are
  opened (not only those whose summary names a fund), and TMSF sales count. The KAP site menu contains "Tasfiye Olmuş Fonlar", so text
  before "Gönderim Tarihi" is ignored. Since 2026-09-09: 20 purchases by 17 companies, 79 statements.
- Runs daily with `--days 7` in the workflow (not in the 15-minute job).
- GitHub's scheduled runs start 45-60 minutes late in this repository and the
  15-minute schedule did not fire at all in its first hour; the owner plans to
  move delayed prices to a Cloudflare Worker later.

## 2026-11-23 · Claude Code · buybacks, benchmarks, watchlist

- `research/buybacks.py` keeps share buyback disclosures in
  `data/buybacks.json`. With the owner's permission it uses KAP's disclosure
  search (the endpoint behind KAP's own "Bildirim Sorgu" page; subject OID
  4028328d6233239a01629b43e4694fae), 7 days back in the 15-minute job and 35
  days otherwise; history starts 2026-10-23. For the three newest notices per
  company it opens the public notice page and reads the cumulative share of
  capital bought back from the text (95 of 117 companies; the rest have no
  figure in the text and stay null). Companies missing from
  `kap-universe.json` (e.g. new listings such as AYES) are skipped.
- `research/price-history.py` also writes `data/benchmarks.json` (BIST 100,
  USD/TRY, gold in USD, weekly). The site shows one-year returns in TL, dollars
  and against BIST 100, a 3m/1y/3y/5y comparison table, and chart views in
  dollars or relative to BIST 100.
- The watchlist and price alarms live in the visitor's browser (localStorage);
  alarms fire only while the page is open, checked on each delayed-price load.

## 2026-11-23 · Claude Code · delayed prices and Smart Money

- TradingView's official embed widgets refuse BIST symbols ("only available on
  TradingView"), and pulling its data into the site would breach its terms, so
  delayed prices come from Yahoo Finance (about 15 minutes behind, the same
  delay TradingView's free data has).
- `research/live.py` writes `data/live.json` (not committed): every price must
  be in TL and within ±11% of the last official close. The workflow fetches it
  every 15 minutes during the session and publishes the site without a commit.
  Market cap and multiples stay at the official close.
- `research/smc.py` reads one year of daily bars and writes `data/smc/<code>.json`
  (not committed; carried over from the published site between daily runs) and
  `data/smc-summary.json`. Definitions follow LuxAlgo's open "Smart Money
  Concepts": swing points (10 bars each side), BOS/CHoCH on closes, order
  blocks, fair value gaps (>= 0.3 x ATR14), equal highs/lows, premium/discount.
  Same safeguards as the price history (last close must match within 3%; daily
  moves beyond ±25% cut the series). Runs after each close.
- In November 2026, 551 of 601 issuers read as bearish structure; 583 had a
  negative 60-day return, so this reflects the market, not a bug.

## 2026-11-23 · Claude Code · price history

- `research/price-history.py` collects five years of weekly closes from Yahoo
  Finance into `data/price-history.json` (589 issuers); the site shows them as
  a chart in each company file, loaded per issuer from `prices/<code>.json`.
- Safeguards: bars after the market snapshot date are dropped; the last close
  must match `market-latest.json` within 3% (it matches exactly for all kept
  series); a weekly move beyond x2.5 or x0.4 is treated as an unadjusted split
  and the series starts after it (17 issuers, `cut` holds the date). Nothing is
  rescaled. Rejected issuers and reasons are in `price-history-gaps.json`
  (DUNYH and FLAP: Yahoo's price disagrees with İş Yatırım).
- The workflow refreshes it on Saturdays. The daily price step was confirmed
  working on GitHub (main has daily "Update prices" commits).

## 2026-11-11 · Claude Code · daily prices

- `research/prices.py` refreshes prices and multiples for all issuers in one
  request into `data/market-latest.json`; the public site and the scorecard
  prefer it. The dated `market-2026-11-09.json` is unchanged for Mercek.
- The workflow now also runs on weekdays at 16:40 UTC (after the Istanbul
  close) for prices, scorecard and site; analyses run only in the 02:23 job.
- Not verified: whether GitHub's runners can reach the İş Yatırım page. If
  they cannot, the step fails softly and the previous prices stay.
- The `surucu` MCP (borsa-mcp) is connected in Claude sessions and is useful
  for spot checks; bulk pulls through it cost assistant usage.

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
