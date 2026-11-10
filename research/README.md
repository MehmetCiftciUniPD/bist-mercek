# Mercek source-backed snapshot

Research date: 2026-11-10. Financial statements: consolidated 2026/9; price snapshot: 2026-11-09 close.

Reproduce with Python and lxml:

1. `python research/collect.py` — download the 16 pinned KAP reports and extract tagged cells, current/prior values, source note identifiers, original units and SHA-256.
2. `python research/market.py` — download current broker tables. These are mutable pages: running later produces a different snapshot; update the dates in the normalization before publication.
3. `python research/enrich.py` — normalize million TL, compute derived metrics, join market data, apply reviewed company EBITDA and PDF-note overrides in `note-enrichment.py`.
4. `python research/validate.py` — balance reconciliation, FCF arithmetic, company-specific EBITDA, KCHOL debt-note total and lease maturity checks.

`docs.py` and `notes.py` download supplementary PDF material for review. Raw documents are ignored; the committed normalized dataset retains their URLs, XBRL labels and original values. PDF extraction overrides are explicit, source-attributed research decisions, not an automated inference engine.

## Comparability

- Income/cash flow previous values: 9A25 as presented in the current filing. Balance previous: 31 December 2025.
- Q3 figures come directly from the four-column income statement; no six-month subtraction for missing Q3 cash flow.
- `kap-fr_CurrentBorowings` (one r in Borowings) is the parent short-term borrowing tag. Prefer it to summing children to avoid omissions or duplication. KCHOL debt is checked against note 13 (1,674,974 million TL).
- Revenue includes separately disclosed finance revenue; `commercialRevenue` preserves the commercial component when present.
- FCF excludes lease-principal payments. Net debt subtracts cash only, not other financial investments.
- Official EBITDA overrides are kept alongside the calculated core measure. Pegasus EUR EBITDA is a separate currency series. Ford adjusted EBITDA is separately labeled and rounded.
- Banks and holdings do not receive industrial leverage/vade scores. Bank ROE is approximate annualization, not regulatory capital adequacy.
- BIMAS note 30 lease cash-flow buckets do not reconcile with the balance-sheet current lease classification. The discrepancy is disclosed; source values are not silently corrected.
- One-off candidates are not automatically subtracted from parent net earnings without tax and non-controlling-interest attribution.
- Broker targets are individually attributed, not a consensus. Undated targets are explicitly undated. Sector peers come from the broker's 629-pay universe, not official sector indexes.

## Persistence

The baseline ships with source. D1 stores personal edits, notes and before/after audit records. Saved overrides are merged over the baseline. The app does not claim a live or unattended financial feed. Future periods require a new source-backed import or manual entries.
