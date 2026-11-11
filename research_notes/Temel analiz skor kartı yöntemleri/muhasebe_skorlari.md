# Accounting-based scores: Piotroski F-Score, Altman Z-Score variants, Beneish M-Score

**Verification status (read first).** In this session WebFetch was blocked for every host tried (NYU Stern, Chicago Booth, Ivey, Wikipedia, arXiv, umbrex: DNS not in allowed domains). Only WebSearch snippets were available. Items marked [VERIFIED-SNIPPET] were seen in search results of secondary sources. Items marked [UNVERIFIED-MEMORY] come from the researcher's prior knowledge of the original papers and were NOT re-checked against the paper text this session; the report writer should flag them as such or re-check once nyu.edu / chicagobooth.edu / SSRN are allowed. Original-paper citation identifiers (DOIs) are from memory, not opened.

Primary-source pointers (not opened this session):
- Piotroski (2000), J. Accounting Research 38 (Supplement), 1-41. DOI 10.2307/2672906. Copy found by search: https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf ; UCLA copy: https://www.anderson.ucla.edu/documents/areas/prg/asam/2019/F-Score.pdf
- Altman (1968), J. Finance 23(4), 589-609. DOI 10.1111/j.1540-6261.1968.tb00843.x. Altman (2000) "Predicting Financial Distress of Companies: Revisiting the Z-Score and ZETA Models": https://pages.stern.nyu.edu/~ealtman/Zscores.pdf (not opened).
- Beneish (1999), Financial Analysts Journal 55(5), 24-36, "The Detection of Earnings Manipulation". DOI 10.2469/faj.v55.n5.2296 (not opened).

## 1. Piotroski F-Score: 9 criteria, denominators, bands

### Takeaway
F = sum of nine 0/1 signals (3 profitability, 3 leverage/liquidity/source of funds, 2 operating efficiency... precisely 4 profitability, 3 leverage/liquidity/equity, 2 efficiency). Paper's "high" = 8-9 and "low" = 0-1, applied to the top book-to-market quintile; the 0-2 / 3-6 / 7-9 style bands are practitioner conventions, not from the paper. Denominators: ROA, CFO, ACCRUAL, turnover use beginning-of-year total assets; ΔLEVER uses average total assets [UNVERIFIED-MEMORY for the paper text, snippets agree].

### Cited Findings
- Score is the sum of nine binary signals; ROA, CFO, accrual and asset turnover are scaled by beginning-of-year total assets; ROA uses net income before extraordinary items; ΔLEVER uses long-term debt over average total assets (the one exception) — [search summary of sources incl. GuruFocus/Alpha Architect](https://www.gurufocus.com/term/fscore) and [Alpha Architect](https://alphaarchitect.com/value-investing-research-simple-methods-to-improve-the-piotroski-f-score/) (snippet-level; Calculator Academy page instead gives plain LTD/total assets, a simplification).
- ΔLIQUID = change in current ratio between t and t-1; ΔMARGIN = change in gross margin ratio; EQ_OFFER = common equity issuance indicator; ΔTURN = change in asset turnover — same search snippets as above.
- High F_SCORE = 8-9, low = 0-1 in Piotroski's study; sample is high book-to-market firms (top quintile); high-F firms earned ~13.4% mean annual market-adjusted return — [CXO Advisory summary](https://www.cxoadvisory.com/fundamental-valuation/piotroskis-efficient-value-investing/); replication also uses 8-9 vs 0-1: [Mo & Wang](http://arc.hhs.se/download.aspx?MediumId=4214).
- Sources did not confirm whether financial firms were excluded from Piotroski's sample (search returned nothing on it).

### Inferences
Implementable spec (from Piotroski 2000, [UNVERIFIED-MEMORY] for exact wording; t = current fiscal year, TA_beg = total assets at end of t-1):
1. F_ROA = 1 if ROA_t > 0, ROA = net income before extraordinary items / TA_beg(t).
2. F_CFO = 1 if CFO_t / TA_beg > 0.
3. F_ΔROA = 1 if ROA_t − ROA_{t-1} > 0 (ROA_{t-1} scaled by TA at start of t-1).
4. F_ACCRUAL = 1 if CFO > ROA (ACCRUAL = ROA − CFO, both scaled by TA_beg; i.e. accrual < 0).
5. F_ΔLEVER = 1 if the ratio (long-term debt / average total assets) fell year on year (increase is negative). Paper: long-term debt, not total liabilities; if LTD is missing, a total-debt proxy must be declared as a deviation.
6. F_ΔLIQUID = 1 if current ratio (CA/CL, year-end) increased.
7. EQ_OFFER = 1 if the firm did NOT issue common equity in the year before portfolio formation (practitioner proxy: shares outstanding not increased, or no stock issuance in cash flow statement; the paper uses issuance, not net of buybacks).
8. F_ΔMARGIN = 1 if gross margin ratio ((Sales−COGS)/Sales) increased.
9. F_ΔTURN = 1 if sales / TA_beg increased.
Bands: paper only contrasts 8-9 (high) vs 0-1 (low). Common retail bands (0-2 weak, 3-6 neutral, 7-9 strong or 8-9 strong) are conventions; the exact origin of "7-9 strong" and "0-2 weak" is not found in a primary source.
Needed inputs: net income before extraordinary items, CFO, total assets for t, t-1 and t-2 (ROA_{t-1} needs TA_{t-2}; average assets needs t-1), long-term debt, current assets/liabilities, sales, COGS, common-equity issuance (or shares outstanding).

### Gaps
- Primary text not opened; exact quotes, the financial-firm sample treatment, and the verbatim ΔLEVER definition need checking against the PDF.
- Origin of the 7-9 / 0-2 retail bands not located.

## 2. Altman Z-Score variants (Z, Z', Z'')

### Takeaway
Z (1968, public manufacturers) uses market value of equity; Z' (private firms) and Z'' (non-manufacturers/emerging markets) use book value of equity. Coefficients and zones in the question match search snippets; the emerging-market version is Z'' + 3.25.

### Cited Findings
- Z: weights 1.2, 1.4, 3.3, 0.6 and 0.999 (universally rounded to 1.0 for X5); zones >2.99 safe, 1.81-2.99 grey, <1.81 distress — [AccountingTools](https://www.accountingtools.com/articles/the-altman-z-score-formula.html) and other sources in [search results](https://en.wikipedia.org/wiki/Altman_Z-score).
- Z': 0.717, 0.847, 3.107, 0.420, 0.998; zones 1.23 / 2.90 — same search results (snippet-level).
- Z'': 6.56, 3.26, 6.72, 1.05; zones 1.10 / 2.60; emerging-market version Z = 3.25 + 6.56X1 + 3.26X2 + 6.72X3 + 1.05X4; the constant sets a D-rated bond to zero — [CreditGuru](https://www.creditguru.com/index.php/bankruptcy-and-insolvency/altman-z-score-insolvency-predictor-for-non-manufacturers-emerging-markets); sources attribute it to Altman et al. (1995). Some sources list 1.23-2.9 as the Z'' grey zone, which appears to be a mix-up with Z'.
- Z'' drops the sales/assets ratio X5 to reduce industry effects (snippet-level) — [Bajaj Finserv summary](https://www.bajajfinserv.in/altman-z-score).

### Inferences
Spec ([UNVERIFIED-MEMORY] for variable wording; consistent with snippets):
- X1 = working capital / total assets (WC = current assets − current liabilities); X2 = retained earnings / total assets; X3 = EBIT / total assets; X4 = equity / total liabilities (market value of equity in Z; BOOK value of equity in Z' and Z''); X5 = sales / total assets (not in Z'').
- Z = 1.2X1 + 1.4X2 + 3.3X3 + 0.6X4 + 0.999X5 (ratios as decimals; original 1968 form 0.012/0.014/0.033/0.006/0.999 with X1-X4 expressed in percent). Zones <1.81 / >2.99; 1968 single cutoff 2.675 (unverified).
- Z' = 0.717X1 + 0.847X2 + 3.107X3 + 0.420X4 + 0.998X5. Zones <1.23 / >2.90.
- Z'' = 6.56X1 + 3.26X2 + 6.72X3 + 1.05X4. Zones <1.10 / >2.60.
- Z''_EM = Z'' + 3.25 (Altman, Hartzell, Peck 1995; Altman 2005 Emerging Markets Review). Arithmetic: shifted zones 4.35 / 5.85. These shifted zones are arithmetic, not read from a paper.
- Altman 2017 (Altman, Iwanicz-Drozdowska, Laitinen, Suvas): I recall it tests the original Z-score across ~30+ countries and finds Z'' performing reasonably with country-specific re-estimation; not verified.
Needed inputs: current assets/liabilities, retained earnings, EBIT, total assets, total liabilities, sales, market cap (Z only) or book equity.

### Gaps
- Could not confirm against Altman papers; 0.999 vs 1.0 and 0.998 confirmed only by secondary sources.
- Altman's own wording on banks/insurers not retrieved (see section 4).

## 3. Beneish M-Score

### Takeaway
8-variable model: M = −4.84 + 0.920 DSRI + 0.528 GMI + 0.404 AQI + 0.892 SGI + 0.115 DEPI − 0.172 SGAI + 4.679 TATA − 0.327 LVGI. Threshold −1.78 is tied to the 1999 paper (20:1 error-cost); −2.22 origin unresolved.

### Cited Findings
- Coefficients above confirmed in several practitioner sources — [Umbrex](https://umbrex.com/resources/frameworks/finance-frameworks/beneish-m-score/), [Wikipedia](https://en.wikipedia.org/wiki/Beneish_M-score) (snippet). Sample: 74 SEC-sanctioned manipulators 1982-1992 plus matched controls (same snippet sources); financial firms excluded per [Wikipedia mirror](https://ipfs.ssi.eecc.de/ipns/en.wikipedia-on-ipfs.org/wiki/Beneish_M-score).
- −1.78 is linked to 20:1 (or 30:1) Type I:II cost assumptions; −2.22 is described by one source as probably 40:1 but explicitly an inference — [Polish-companies study](https://www.emerald.com/cemj/article/34/3/488/1304262/Evaluating-the-efficacy-of-modified-Beneish-and), [StableBread](https://stablebread.com/beneish-m-score/). Another search summary attributed −1.78 to a later (2013) study; contradictory, unresolved.
- TATA per one source: (ΔCA − ΔCash) − (ΔCL − ΔCurrent maturities of LTD − ΔIncome tax payable) − Dep&Amort, all / total assets — [Quant Investing](https://www.quant-investing.com/glossary/m-score-beneish/) and search source above.
- Note: one search summary claimed −4.84 is the 5-variable intercept and omitted LVGI; this is wrong/contradicted by sources above (−4.84 is the 8-variable intercept).

### Inferences
Variables ([UNVERIFIED-MEMORY], standard in the paper; t vs t-1; all annual):
- DSRI = (Receivables_t/Sales_t) / (Receivables_{t-1}/Sales_{t-1})
- GMI = GM_{t-1}/GM_t, GM = (Sales − COGS)/Sales
- AQI = [1 − (CA_t + net PPE_t)/TA_t] / [1 − (CA_{t-1} + net PPE_{t-1})/TA_{t-1}]
- SGI = Sales_t / Sales_{t-1}
- DEPI = [Dep_{t-1}/(Dep_{t-1} + net PPE_{t-1})] / [Dep_t/(Dep_t + net PPE_t)]
- SGAI = (SGA_t/Sales_t) / (SGA_{t-1}/Sales_{t-1})
- LVGI = [(CL_t + total LTD_t)/TA_t] / [(CL_{t-1} + total LTD_{t-1})/TA_{t-1}]
- TATA (1999) = (ΔCA − ΔCash − ΔCL + ΔCurrent maturities LTD + ΔIncome tax payable... sign convention: ΔCL excluding current LTD and tax payable is subtracted) − Dep&Amort, / TA_t. Practitioner simplification: (Net income from continuing operations − CFO) / TA_t. Note the snippet-based formula subtracts the changes in current maturities and tax payable inside the CL bracket; implement as ΔWC_noncash_nontax − Dep.
- 5-variable model [UNVERIFIED-MEMORY, from Beneish 1999 / Beneish-Lee-Nichols 2013, not seen this session]: −6.065 + 0.823 DSRI + 0.906 GMI + 0.593 AQI + 0.717 SGI + 0.107 DEPI.
- Rule: M > −1.78 flags probable manipulator (more conservative flag, fewer misses); M > −2.22 flags more firms. Probability check: Φ(−1.78) ≈ 0.0375 consistent with a 20:1 cutoff (arithmetic).
Needed inputs: receivables, sales, COGS, SG&A, current assets, net PP&E, depreciation, total assets, current liabilities, LTD, CFO or net income, two consecutive years (three years if growing historical ΔWC items).

### Gaps
- −2.22 provenance unresolved; 5-variable coefficients not verified this session; 1999 paper not opened.

## 4. Applicability to banks, insurers, financials

### Takeaway
Beneish excluded financial firms from his sample; Altman's models are for industrials (Z for manufacturers, Z'' relaxed to non-manufacturers). Primary author statements on financials were not retrieved.

### Cited Findings
- Beneish sample excluded financial firms — [Wikipedia mirror](https://ipfs.ssi.eecc.de/ipns/en.wikipedia-on-ipfs.org/wiki/Beneish_M-score).
- Search found no source stating Altman's inapplicability to banks/insurers; Z'' is for non-manufacturers; empirical bank use exists despite caveats — [Bajaj Finserv summary](https://www.bajajfinserv.in/altman-z-score).
- No result confirmed whether Piotroski excluded financials.

### Inferences
Prudent rule: do not compute Z, Z', Z'' or M for banks/insurers (current assets, working capital, COGS, receivables, gross margin are not meaningful); F-Score items such as gross margin and current ratio also break. Mark financials N/A for all three.

### Gaps
- Altman's exact words (recalled: Z-models not designed for financial institutions) and Piotroski's sample filter not verified.

## 5. Inputs often missing from summarised statement data

### Takeaway
Retained earnings, SG&A, receivables, net PP&E, depreciation, COGS, long-term debt and prior-year values are the usual gaps; Beneish needs the most.

### Inferences
- Piotroski: long-term debt (vs total debt), COGS/gross profit, share issuance (or shares outstanding two years), TA_{t-2}.
- Altman: retained earnings, EBIT (derive from operating income), working capital components, total liabilities, market cap (Z only).
- Beneish: net receivables, SG&A, depreciation (from cash flow statement), net PP&E, current maturities of LTD, income taxes payable (often absent; use simplification and document).
- Cross-cutting: two to three years of consecutive annual statements; consistent fiscal-year ends.

### Gaps
- Per-data-vendor availability (BIST/KAP) not researched.
