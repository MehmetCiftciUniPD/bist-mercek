# Valuation and quality measures from annual statements + market multiples (implementable specs)

Research limits: only WebSearch worked; WebFetch failed (DNS) for pages.stern.nyu.edu, aaii.com, medium.com, S&P pdf host. No primary text was read directly. Anything marked **[UNVERIFIED-memory]** is from model knowledge of the primary work and was not confirmed by a fetched source. Search-result summaries are secondary.

## 1. DuPont decomposition (3-step, 5-step; average vs year-end)

### Takeaway
Both decompositions are algebraic identities for ROE; formulas are consistent across all sources found. Average vs year-end balances is not standardized: textbooks/CFA-style treatments commonly use averages, many screeners use year-end. No CFA Institute or textbook primary text could be retrieved.

### Cited Findings
- 5-step: ROE = tax burden (NI/EBT) x interest burden (EBT/EBIT) x EBIT margin (EBIT/Revenue) x asset turnover (Revenue/Total assets) x leverage (Total assets/Equity); tax burden = NI / pre-tax income, interest burden = pre-tax income / EBIT. Sources agree but are third-party — [Wall Street Prep](https://www.wallstreetprep.com/knowledge/dupont-analysis-template/), [beancount.io guide](https://beancount.io/blog/2026/05/18/dupont-analysis-three-step-five-step-roe-decomposition-net-margin-asset-turnover-equity-multiplier-tax-burden-interest-burden-guide)
- Several sources define asset turnover as revenue / average total assets and equity multiplier on averages; others use period-end; the convention varies — [DuPont search results, e.g. umbrex](https://umbrex.com/resources/frameworks/finance-frameworks/dupont-analysis/)
- Product of factors should reconcile to reported ROE (within rounding) — same sources.

### Inferences (spec)
- 3-step: ROE = (NI/Revenue) x (Revenue/Avg TA) x (Avg TA/Avg Equity). 5-step splits NI/Revenue into (NI/EBT) x (EBT/EBIT) x (EBIT/Revenue). Identity holds exactly only if the same numerator/denominator bases are used throughout (all average or all year-end; ROE = NI / same equity basis).
- Recommended: compute on average balances (opening+closing)/2 when two balance sheets exist; fall back to year-end for the oldest year; flag basis in output. Inputs: revenue, EBIT (operating income), interest expense, pre-tax income, income tax, net income (to parent; be consistent with parent equity), total assets, total equity (parent). Guard: EBT<=0 or EBIT<=0 makes burden ratios uninterpretable; negative equity breaks leverage.
- No universal thresholds; interpret vs own history and sector peers (practitioner use; no primary threshold).

### Gaps
- Could not fetch CFA Institute curriculum or Brigham/Ross/Bodie text to cite avg-vs-year-end as "standard". Suggested citation targets: CFA Program Level I/II "Financial Analysis Techniques"; Ross-Westerfield-Jaffe "Corporate Finance" (DuPont identity, uses year-end in textbook examples [UNVERIFIED-memory]).

## 2. Greenblatt Magic Formula

### Takeaway
Earnings yield = EBIT / EV; return on capital = EBIT / (net working capital + net fixed assets); exclude financials and utilities; rank each, sum ranks, lowest sum best. Secondary sources agree; the book itself was not accessed.

### Cited Findings
- EY = EBIT / enterprise value; ROC = EBIT / (net working capital + net fixed assets) ("tangible capital employed"); financials and utilities excluded; minimum market cap originally ~$50M (practitioners use $100M+); rank on each metric, add ranks, lowest combined rank is best — [AAII, Greenblatt's Magic Formula](https://www.aaii.com/journal/article/greenblatts-magic-formula), [Quant-Investing guide](https://www.quant-investing.com/blog/magic-formula-complete-guide/), [Screener.in](https://www.screener.in/screens/900752/greenblatt-magic-formula/)
- Sources note implementations differ slightly on ROC definition — [Quant-Investing](https://www.quant-investing.com/blog/magic-formula-complete-guide/)
- Primary: Greenblatt, *The Little Book That Beats the Market* (Wiley, 2005/2006; ISBN 978-0471733065 [UNVERIFIED-memory]).

### Inferences (spec)
- EV = market cap + interest-bearing debt (+ preferred, + minorities) - cash. [Book's exact EV wording: UNVERIFIED-memory; Greenblatt says "market cap plus net interest-bearing debt".]
- NWC = (current assets - cash and equivalents) - (current liabilities - short-term interest-bearing debt) [Greenblatt excludes excess cash and debt from working capital: UNVERIFIED-memory]. Net fixed assets = net PP&E (tangibles; excludes goodwill/intangibles [UNVERIFIED-memory]). Guard: denominator <=0 means ROC undefined/exclude.
- Procedure: universe filter (exclude financials, utilities, size floor, optionally ADR/foreign) -> compute EY, ROC -> rank 1..N descending each -> sum -> pick lowest sums (book: 20-30 stocks, hold ~1 year [UNVERIFIED-memory]). For BIST: banks, insurers, holding cos, REITs-like need exclusion/flag.
- No absolute thresholds: purely relative ranking.

### Gaps
- Exact book wording of EV/NWC could not be checked.

## 3. Graham: Graham number and defensive-investor criteria

### Takeaway
Graham number = sqrt(22.5 x EPS x BVPS), the price at which P/E x P/B = 22.5 (15 x 1.5). Seven defensive criteria exist (Intelligent Investor ch.14); my numeric list below is consistent with partial secondary confirmation but the primary text was not retrieved.

### Cited Findings
- Seven criteria in ch.14; criteria 6 and 7 combine into the Graham number sqrt(22.5 x EPS x BVPS); 22.5 = 15 x 1.5 — [Winvesta](https://www.winvesta.in/blog/investors/benjamin-grahams-7-ways-to-select-high-value-stocks), [GuruFocus Graham number](https://www.gurufocus.com/news/197280/using-the-graham-number-correctly)
- Current ratio >= 2 for industrials; utilities exempt from that test; long-term debt <= net current assets — [GuruFocus](https://www.gurufocus.com/news/136264/benjamin-graham-and-defensive-picks-part-3)
- Some earnings in each of past 10 years; one-third earnings increase over 10 years (screen sources); P/E x P/B <= ~22 — [Screener.in Graham screen](https://www.screener.in/screens/190633/the-defensive-intelligent-investor-benjamin-graham/), [GuruFocus 878628](https://www.gurufocus.com/news/878628)
- Size test $100M sales (1970s dollars; one source says ~$500M adjusted for CPI) — [Bajaj Finserv summary](https://bajajfinserv.in/benjamin-grahams-7-stock-criteria)
- 110%-of-net-current-assets debt rule belongs to Graham's different 1973-era net-net/enterprising screen, not the defensive list — GuruFocus above (search summary).

### Inferences (spec) — full list **[numbers UNVERIFIED-memory except where cited above]**
1. Adequate size: industrial annual sales >= $100M (1972 terms; inflation-adjust or use peer-relative size in TRY); utilities total assets >= $50M.
2. Strong financial condition: industrials current ratio >= 2.0 AND long-term debt <= net current assets (current assets - current liabilities); utilities: debt <= 2x book equity.
3. Earnings stability: positive EPS in each of the last 10 years.
4. Dividend record: uninterrupted dividends for at least 20 years.
5. Earnings growth: per-share earnings up >= 1/3 over last 10 years, comparing 3-yr averages at start and end.
6. Moderate P/E: price <= 15 x average earnings of last 3 years.
7. Moderate P/B: price <= 1.5 x book value (last balance sheet); alternatively P/E x P/B <= 22.5 (allows P/E up to ~22.5 only if P/B is ~1 - exception stated by Graham).
- Graham number: GN = sqrt(22.5 x EPS x BVPS); "undervalued" if price < GN. Requires EPS>0 and BVPS>0. Note: Graham's own P/E uses 3-yr average EPS; common implementations use TTM EPS (deviation; flag it).
- Not evaluable with 5-6 years of annual data: #3 (10-yr earnings), #4 (20-yr dividends), #5 (10-yr growth; with 6 years one can only do a shortened proxy e.g. avg of first 3 vs last 3 yrs - not Graham's test). #6 needs 3 yrs (OK). #1, #2, #7 need only latest year. #4 cannot be tested at all; treat as "insufficient data", not fail.

### Gaps
- Primary text of ch.14 not retrieved (medium.com blocked). Verify numbers against book (Harper, rev. ed. with Zweig commentary 2003; criteria listed in ch.14 "Stock Selection for the Defensive Investor").

## 4. Free cash flow yield

### Takeaway
No primary source retrieved. Definitions below are standard practitioner conventions [UNVERIFIED-memory] - no search was run on FCF.

### Cited Findings
- None retrieved with a source. (EV = equity + debt - cash per Damodaran slides — [Damodaran relval2014](https://pages.stern.nyu.edu/~adamodar/pdfiles/country/relval2014.pdf).)

### Inferences (spec) [UNVERIFIED-memory]
- FCF = Cash flow from operations - Capital expenditures (PP&E purchases; often incl. intangibles). Variants: FCFE = CFO - capex + net borrowing; FCFF = CFO + interest x (1-t) - capex; unlevered FCF for EV yields. Pre-IFRS16/post-IFRS16: lease principal payments sit in financing, flattering CFO - optionally subtract lease principal.
- FCF yield (equity) = FCF / market cap (pairs with levered FCF/FCFE); FCF yield (EV) = FCFF / EV (pairs with unlevered). Use consistent pairing; averaging 3-5 years of FCF smooths lumpy capex. No primary threshold; any "5%+ attractive" is a rule of thumb only. Banks: FCF not meaningful.

### Gaps
- No authoritative source retrieved (CFA, Damodaran "FCFE" chapters would be targets).

## 5. Net debt / EBITDA and interest coverage

### Takeaway
S&P core ratios are FFO/debt and debt/EBITDA with six financial-risk categories (minimal..highly leveraged); I could not retrieve the current numeric grid. Coverage and net debt/EBITDA "high" levels (e.g. >3-4x) are practitioner rules of thumb.

### Cited Findings
- S&P Corporate Methodology (Jan 2024) financial risk profile has six categories: minimal, modest, intermediate, significant, aggressive, highly leveraged; core ratios FFO/debt and debt/EBITDA; FFO = EBITDA - cash interest - cash taxes; "standard" and "medial" volatility tables exist — search summaries citing [Veolia S&P report](https://www.veolia.com/sites/g/files/dvc4206/files/document/2025/04/Finance_Standard_%26_Poors_Ratings_Direct_Veolia_Environnement_SA_Mars_2025_03-04-25.pdf), [Stockholm Exergi](https://www.stockholmexergi.se/wp-content/uploads/2025/11/RatingsDirect_StockholmExergiHoldingAB_Aug-27-2025.pdf)
- Older S&P matrix: "minimal" = FFO/debt > 60%, debt/EBITDA < 1.5x, debt/capital < 25%; "significant" illustrated by FFO/debt ~20% and debt/EBITDA ~4x — [S&P 2019 "How we rate nonfinancial corporate entities" (host unreachable; per search snippet)](https://sandpglobal-spglobal-live.cphostaccess.com/ratings/_division-assets/pdfs/041019_howweratenonfinancialcorporateentities.pdf)
- Primary to retrieve: S&P, "Corporate Methodology" (Jan 7, 2024) and "Corporate Methodology: Ratios And Adjustments", spglobal.com/ratings.

### Inferences (spec)
- Net debt/EBITDA = (interest-bearing debt incl. leases - cash and ST investments) / EBITDA (EBIT + D&A), annual; undefined/flag if EBITDA<=0; negative = net cash. Interest coverage = EBIT / interest expense (alt EBITDA/interest, S&P's ratio is EBITDA/interest and FFO/cash interest); flag if interest = 0.
- S&P grid values from memory for standard volatility [UNVERIFIED-memory, verify]: debt/EBITDA minimal <1.5x, modest 1.5-2x, intermediate 2-3x, significant 3-4x, aggressive 4-5x, highly leveraged >5x; FFO/debt >60%, 45-60, 30-45, 20-30, 12-20, <12%. Anchor is combined with business risk; grid is NOT a standalone credit score and agency ratios include adjustments (leases, pensions, etc.).
- "Net debt/EBITDA >3-4x is high" and "coverage <2-3x is weak" = informal rules of thumb, not from a primary source. Turkey: TRY inflation distorts interest/EBITDA; consider IAS 29 effects.

### Gaps
- Current S&P and Moody's tables not retrieved; Moody's grid (Debt/EBITDA, EBITDA/interest by Aaa-C per sector methodology) not searched.

## 6. Sector-relative multiples

### Takeaway
Damodaran's notes support using median (alongside mean) because multiple distributions are heavily right-skewed; dropping outliers or negative-earnings firms can bias results. No authoritative minimum peer count found.

### Cited Findings
- Report both average/SD and median; median often more reliable; outlier removal if all outliers on one side biases the estimate; ignoring firms with uncomputable multiples (negative earnings) may bias — [Damodaran valuation packet (Spring 2025)](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/valpacket2spr25.pdf)
- US Jan 2026: 5,994 firms, only 2,537 with a current P/E; mean P/E 72.19 vs median 18.65, skewness 40.1 — [Damodaran valuation packet (Spring 2026)](https://pages.stern.nyu.edu/~adamodar/pdfiles/eqnotes/valpacket2spr26.pdf)
- Harmonic mean preferred over arithmetic mean for price-over-fundamental multiples (CFA study note, secondary) — [AnalystNotes](https://www.analystnotes.com/cfa-study-notes-valuation-indicators-issues-in-practice.html)
- EV = market equity + market debt - cash; cross-holdings distort EV multiples — [Damodaran relval](https://pages.stern.nyu.edu/~adamodar/pdfiles/country/relval2014.pdf), [Damodaran on Valuation](https://www.oreilly.com/library/view/damodaran-on-valuation/9780471751212/9780471751212_conclusion-026.html)

### Inferences (spec)
- Relative score = firm multiple / sector median (or percentile rank within sector). Exclude firms with negative/zero denominator from the peer statistic and set own multiple to "n/a" (do not rank as cheap); report count of valid peers. Winsorize (e.g. 1st-99th) or use median/percentiles. Damodaran publishes industry datasets (pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html, not fetched).
- Minimum peer count: no authoritative source found; practitioner heuristic (e.g. >= 5-10 valid peers, else fall back to broader sector) - rule of thumb only. Banks: use P/E, P/B only (EV/EBITDA invalid).

### Gaps
- Damodaran's explicit stance on negative-earnings aggregation (aggregate-earnings method) and min peers not confirmed.

## 7. Composite quality measures

### Takeaway
Gross profitability, QMJ and G-Score definitions partly confirmed; full component lists need the papers.

### Cited Findings
- Novy-Marx: gross profitability = (revenues - COGS) / total assets; scaled by assets as gross profit is independent of leverage; roughly as strong as book-to-market in predicting returns — [NBER w15940](https://nber.org/papers/w15940), JFE 108(1) 1-28, 2013 [EconPapers](https://econpapers.repec.org/RePEc:eee:jfinec:v:108:y:2013:i:1:p:1-28). Compustat mapping (REVT-COGS)/AT is [UNVERIFIED-memory].
- QMJ (Asness, Frazzini, Pedersen, Rev. Account. Stud. 24(1), 2019, DOI 10.1007/s11142-018-9470-2): quality = profitability + growth + safety (+ payout) derived from Gordon growth P/B; profitability = ranks of gross profits/assets, ROE, ROA, CFO/assets, gross margin, low accruals; growth = prior 5-year growth in those measures; safety = low beta, idiosyncratic vol, leverage, bankruptcy risk (Z/O-score), ROE volatility; payout = net payout/issuance; composite = average of z-scores of ranks — [CBS repository PDF](https://research-api.cbs.dk/ws/portalfiles/portal/60211462/lasse_heje_pedersen_et_al_quality_minus_junk_publishersversion.pdf); component list varies by draft — [summary](https://www.cxoadvisory.com/fundamental-valuation/stock-quality-and-future-returns/). Beta/volatility need price history, not annual statements.
- Mohanram G-Score (Rev. Account. Stud. 10(2-3), 2005, DOI 10.1007/s11142-005-1526-4; [IDEAS](https://ideas.repec.org/a/spr/reaccs/v10y2005i2d10.1007_s11142-005-1526-4.html)): 8 binary signals, score 0-8, each compared to industry median; ROA, cash-flow ROA, CFO>NI (accrual), ROA variance (5 yrs, needs >=3 yrs), sales-growth variance, R&D intensity, capex intensity, advertising intensity; designed for low-B/M (glamour) stocks — [AAII summaries via search](https://www.aaii.com/stockideas/article/23359-separating-winning-and-losing-growth-stocks-with-the-g-score). Advertising often unavailable, max 7 then.

### Inferences (spec) [direction UNVERIFIED-memory]
- G-Score signals: G1 ROA > industry median; G2 CFO/assets > industry median; G3 CFO/assets > ROA; G4 ROA variance < industry median; G5 sales-growth variance < industry median; G6 R&D/assets > median; G7 capex/assets > median; G8 advertising/assets > median. ROA = NI before extraordinary items / beginning-of-year total assets [memory]. Score >=5-6 treated as "high" in paper's high-G group (paper evaluated G=0-1 vs 5-8, UNVERIFIED-memory).
- QMJ full replication impractical from annual data; a reduced "profitability" sub-score (GP/Assets, ROA, ROE, CFO/Assets, gross margin, accruals) is feasible. Piotroski F-score not in scope.

### Gaps
- Exact QMJ and G-Score formulas (denominators, timing) not read from the papers; verify before coding.

## Source-access note
pages.stern.nyu.edu, aaii.com, medium.com, S&P pdf host fail DNS in WebFetch but appear in WebSearch result lists (links above are from search results, unfetched).
