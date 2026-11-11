"""Compute the fundamental scorecard (data/scorecard.json) from data/history.json.

Method notes are in reports/Temel analiz skor kartı yöntemleri.md. Rules:

- A measure is computed only when every input exists for the same period;
  otherwise it stays null. Nothing is estimated.
- Issuers are scored by template. Piotroski, Altman, Greenblatt and
  net debt / EBITDA are computed for industrial issuers only. Banks, other
  financial firms, holdings and REITs get the measures that fit them.
- The basis is 2026/9 against 2025/9 where both exist, otherwise 2025 against
  2024. Nine-month flows are multiplied by 12/9 wherever they are set against
  a balance or a market value (Altman's EBIT term, net debt / EBITDA,
  Greenblatt, cash-flow yield, return on equity and assets). Piotroski compares
  the two nine-month periods directly.
- Year-on-year signals compare ratios, never TL levels, because each year's
  figures are in that year's own purchasing power (TMS 29). For the same
  reason ratios use year-end balances of the same report, and Beneish's
  M-Score (which needs a sales growth index) is not computed.
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
# Preferred basis first: nine months of 2026 against the same nine months of 2025,
# otherwise the last two year-ends.
BASES = [('2026/9', '2025/9', 9), ('2025/12', '2024/12', 12)]
HOLDING_SECTORS = {'Holdingler', 'GYO', 'Yatırım Ortaklıkları'}
BANK_SECTORS = {'Bankacılık'}
FINANCIAL_SECTORS = {'Aracı Kurumlar', 'Fin.Kiralama ve Faktoring', 'Sigorta', 'Varlık Yönetim'}
MIN_PEERS = 5


def num(value):
    return isinstance(value, (int, float))


def ratio(a, b, positive_denominator=True):
    if not num(a) or not num(b) or b == 0 or (positive_denominator and b < 0):
        return None
    return a / b


def r(value, digits=4):
    return round(value, digits) if num(value) else None


class Year:
    """Values of one period; missing items read as None."""

    def __init__(self, record, period):
        self.values = {}
        if period in record['periods']:
            index = record['periods'].index(period)
            self.values = {k: v[index] for k, v in record['values'].items() if num(v[index])}

    def __getattr__(self, name):
        return self.values.get(name)

    def __bool__(self):
        return bool(self.values)


def add(*items):
    return sum(items) if all(num(i) for i in items) else None


def piotroski(now, before):
    """Nine binary signals (Piotroski 2000), with same-year denominators."""
    roa, roa0 = ratio(now.netIncome, now.assets), ratio(before.netIncome, before.assets)
    cfo = ratio(now.ocf, now.assets)
    lever, lever0 = ratio(now.longDebt, now.assets), ratio(before.longDebt, before.assets)
    liquid, liquid0 = ratio(now.currentAssets, now.currentLiabilities), ratio(before.currentAssets, before.currentLiabilities)
    margin, margin0 = ratio(now.grossProfit, now.revenue), ratio(before.grossProfit, before.revenue)
    turn, turn0 = ratio(now.revenue, now.assets), ratio(before.revenue, before.assets)

    def test(key, a, b, passed):
        return {'k': key, 'pass': passed if num(a) and (b is None or num(b)) else None, 'a': r(a), 'b': r(b)}

    def cmp(key, a, b, better):
        return {'k': key, 'pass': better(a, b) if num(a) and num(b) else None, 'a': r(a), 'b': r(b)}

    items = [
        test('roa', roa, None, num(roa) and roa > 0),
        test('cfo', cfo, None, num(cfo) and cfo > 0),
        cmp('droa', roa, roa0, lambda a, b: a > b),
        cmp('accrual', cfo, roa, lambda a, b: a > b),
        cmp('lever', lever, lever0, lambda a, b: a < b),
        cmp('liquid', liquid, liquid0, lambda a, b: a > b),
        test('issue', now.capitalIncrease, None, num(now.capitalIncrease) and now.capitalIncrease <= 0),
        cmp('margin', margin, margin0, lambda a, b: a > b),
        cmp('turnover', turn, turn0, lambda a, b: a > b),
    ]
    judged = [i for i in items if i['pass'] is not None]
    return {'score': sum(i['pass'] for i in judged), 'n': len(judged), 'items': items}


def altman(now, k=1):
    """Z'' for non-manufacturers and emerging markets, book equity (Altman 1995/2005)."""
    liabilities = add(now.assets, -now.equity if num(now.equity) else None)
    retained = add(now.priorYearsEarnings, now.periodEarnings, now.restrictedReserves)
    x1 = ratio(add(now.currentAssets, -now.currentLiabilities if num(now.currentLiabilities) else None), now.assets)
    x2, x3 = ratio(retained, now.assets), ratio(now.operating * k if num(now.operating) else None, now.assets)
    x4 = ratio(now.equity, liabilities)
    if not all(num(x) for x in (x1, x2, x3, x4)):
        return None
    z = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    return {'z': r(z, 2), 'zone': 'safe' if z > 2.60 else 'grey' if z >= 1.10 else 'distress',
            'x': [r(x1), r(x2), r(x3), r(x4)]}


def dupont(now, k=1):
    margin, turnover, multiplier = ratio(now.netIncome, now.revenue), ratio(now.revenue * k if num(now.revenue) else None, now.assets), ratio(now.assets, now.equity)
    if not all(num(x) for x in (margin, turnover, multiplier)):
        return None
    return {'margin': r(margin), 'turnover': r(turnover), 'multiplier': r(multiplier), 'roe': r(margin * turnover * multiplier)}


def classify(record, sector):
    if sector in BANK_SECTORS:
        return 'bank'
    if record['group'] != 'XI_29' or sector in FINANCIAL_SECTORS:
        return 'financial'
    if sector in HOLDING_SECTORS:
        return 'holding'
    return 'industrial'


def main():
    history = json.loads((DATA / 'history.json').read_text())['companies']
    market = json.loads((DATA / 'market-2026-11-09.json').read_text())
    quotes = {q['code']: q for q in market['companies']}
    cards = {}
    for code, record in history.items():
        quote = quotes.get(code, {})
        sector = quote.get('sector')
        template = classify(record, sector)
        basis = next(((y, p, m) for y, p, m in BASES if y in record['periods'] and p in record['periods']), None)
        if basis is None and BASES[-1][0] in record['periods']:
            basis = (BASES[-1][0], None, 12)
        latest = Year(record, record['periods'][-1])
        card = {'t': template, 'sector': sector}
        if basis is None:
            card['reason'] = '2026/9 veya 2025 yıl sonu tablosu yok'
            cards[code] = card
            continue
        year, previous, months = basis
        k = 12 / months
        now, before = Year(record, year), Year(record, previous) if previous else None
        scale = lambda v: v * k if num(v) else None
        card.update(year=year, months=months)
        card['dupont'] = dupont(now, k)
        card['equityAssets'] = r(ratio(now.equity, now.assets))
        cap = quote.get('marketCap')
        value = {'pe': quote.get('pe'), 'pb': quote.get('pb'), 'evEbitda': quote.get('multiple')}
        if num(value['pe']) and num(value['pb']) and value['pe'] > 0 and value['pb'] > 0:
            value['graham'] = r(value['pe'] * value['pb'], 2)
        card['val'] = value
        net_income = scale(now.netIncome)
        if template == 'bank':
            card['bank'] = {'roe': r(ratio(net_income, now.equity)), 'roa': r(ratio(net_income, now.assets)),
                            'loanDeposit': r(ratio(now.loans, now.deposits)), 'loanAssets': r(ratio(now.loans, now.assets))}
        elif template == 'financial':
            card['fin'] = {'roe': r(ratio(net_income, now.equity)), 'roa': r(ratio(net_income, now.assets))}
        else:
            net_debt = add(now.shortDebt, now.longDebt, -now.cash if num(now.cash) else None)
            card['netDebtEquity'] = r(ratio(net_debt, now.equity))
        if template == 'industrial':
            if before:
                card['prev'] = previous
                card['f'] = piotroski(now, before)
            card['z'] = altman(now, k)
            card['grossProfitability'] = r(ratio(scale(now.grossProfit), now.assets))
            value['fcfYield'] = r(ratio(scale(now.fcf), cap))
            ebitda = scale(add(now.operating, now.depreciation))
            net_debt = add(now.shortDebt, now.longDebt, -now.cash if num(now.cash) else None)
            card['lev'] = {'netDebt': r(net_debt, 1), 'ebitda': r(ebitda, 1),
                           'ratio': r(net_debt / ebitda, 2) if num(net_debt) and num(ebitda) and ebitda > 0 else None}
            # Greenblatt: EBIT / enterprise value and EBIT / (net working capital + net fixed assets).
            latest_debt = add(latest.shortDebt, latest.longDebt, -latest.cash if num(latest.cash) else None)
            ev = add(cap, latest_debt)
            working = add(now.currentAssets, -now.cash if num(now.cash) else None,
                          -now.currentLiabilities if num(now.currentLiabilities) else None, now.shortDebt)
            capital = add(max(working, 0) if num(working) else None, now.ppe)
            ebit = scale(now.operating)
            card['magic'] = {'yield': r(ratio(ebit, ev)), 'roc': r(ratio(ebit, capital))}
        cards[code] = card

    # Greenblatt rank: each measure ranked best-first, ranks summed, lowest total is best.
    pool = [c for c in cards.values() if c['t'] == 'industrial' and c.get('magic') and num(c['magic']['yield']) and num(c['magic']['roc'])]
    for key in ('yield', 'roc'):
        for rank, card in enumerate(sorted(pool, key=lambda c: -c['magic'][key]), start=1):
            card['magic'][key + 'Rank'] = rank
    for rank, card in enumerate(sorted(pool, key=lambda c: c['magic']['yieldRank'] + c['magic']['rocRank']), start=1):
        card['magic'].update(rank=rank, of=len(pool))

    # Sector medians of positive multiples, same template only.
    groups = {}
    for card in cards.values():
        if card.get('val'):
            groups.setdefault((card['t'], card['sector']), []).append(card)
    for group in groups.values():
        for key in ('pe', 'pb', 'evEbitda'):
            values = [c['val'][key] for c in group if num(c['val'].get(key)) and c['val'][key] > 0]
            median = statistics.median(values) if len(values) >= MIN_PEERS else None
            for card in group:
                card['val'][key + 'Median'] = r(median, 2)
                card['val'][key + 'Peers'] = len(values)

    out = {'bases': [list(b) for b in BASES], 'priceDate': market['date'],
           'report': 'reports/Temel analiz skor kartı yöntemleri.md', 'companies': dict(sorted(cards.items()))}
    (DATA / 'scorecard.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    scored = [c for c in cards.values() if c.get('f')]
    print(f"{len(cards)} şirket · şablon: " + ', '.join(f"{t} {sum(c['t'] == t for c in cards.values())}" for t in ('industrial', 'holding', 'bank', 'financial'))
          + ' · esas: ' + ', '.join(f"{y} {sum(c.get('year') == y for c in cards.values())}" for y, _, _ in BASES)
          + f" · F-Skor hesaplanan {len(scored)} · Altman {sum(bool(c.get('z')) for c in cards.values())} · Greenblatt {len(pool)}")


if __name__ == '__main__':
    main()
