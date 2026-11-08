"""Fear and greed in French markets (stdlib only, no JavaScript).

Four daily market readings, each ranked against its own last three years
(756 trading days) and averaged into one number from 0 (extreme fear) to 100
(extreme greed). The news tone from the Barometer is shown beside it, not in it.

Prices are daily closes from Yahoo Finance. Each reading on a given day uses
that day and earlier days only, so history is not rewritten as new data arrive.
"""
from bisect import bisect_left, bisect_right
from datetime import date as Date, timedelta
from html import escape
from math import log, sqrt
import json

if __package__:
    from . import barometer
else:
    import barometer

WINDOW = 756          # about three years of trading days
MIN_HISTORY = 252     # a rank needs at least one year of history
CARRY_DAYS = 5        # a series with no print carries its last value this long
SCHEMA = 1

SYMBOLS = {'cac': '^FCHI', 'eurchf': 'EURCHF=X', 'gold': 'GC=F', 'eurusd': 'EURUSD=X'}
YAHOO = 'https://query1.finance.yahoo.com/v8/finance/chart/{}?range=10y&interval=1d'

BANDS = ((0, 25, 'Extreme fear'), (25, 45, 'Fear'), (45, 55, 'Neutral'), (55, 75, 'Greed'), (75, 100.01, 'Extreme greed'))

LEGS = (
    dict(key='momentum', name='Equity momentum', flip=False, unit='%', digits=2, inputs='CAC 40',
         measure='CAC 40 vs its 125-day average, %',
         about='How far the CAC 40 sits above or below its own 125-day average. Further above than usual scores as greed.'),
    dict(key='volatility', name='Volatility', flip=True, unit='%', digits=1, inputs='CAC 40',
         measure='CAC 40 20-day volatility, annualised %, axis flipped',
         about='How much the CAC 40 has been swinging day to day over the last 20 sessions. Calm markets score as greed; '
               'wild swings score as fear.'),
    dict(key='haven', name='Safe haven', flip=False, unit='%', digits=2, inputs='EUR/CHF',
         measure='EUR/CHF 20-day change, %',
         about='Investors buy the Swiss franc when they are nervous. A franc gaining on the euro (EUR/CHF falling) scores as fear.'),
    dict(key='gold', name='Stocks vs gold', flip=False, unit=' pts', digits=2, inputs='CAC 40 · gold in euros',
         measure='CAC 40 20-day return minus gold\'s (in euros), points',
         about='The CAC 40\'s 20-day return minus gold\'s, with gold priced in euros. Shares pulling ahead of gold scores as greed; '
               'money moving into gold scores as fear.'),
)


def band(score):
    return next(name for low, high, name in BANDS if low <= score < high)


# --- Data -------------------------------------------------------------------------

def fetch(get):
    """Daily closes per input from Yahoo Finance: ({key: {date: close}}, errors)."""
    series, errors = {}, []
    for key, symbol in SYMBOLS.items():
        url = YAHOO.format(symbol.replace('^', '%5E').replace('=', '%3D'))
        try:
            closes = barometer.parse_yahoo(get(url))
            if len(closes) < MIN_HISTORY:
                raise ValueError(f'only {len(closes)} prices')
            series[key] = closes
        except Exception as error:
            errors.append(f'{symbol}: {type(error).__name__}: {error}')
    return series, errors


def _aligned(series, days):
    """Values on CAC 40 trading days, carrying the last print forward up to CARRY_DAYS days."""
    known = sorted(series)
    out = []
    for day in days:
        i = bisect_right(known, day) - 1
        if i >= 0 and (Date.fromisoformat(day) - Date.fromisoformat(known[i])).days <= CARRY_DAYS:
            out.append(series[known[i]])
        else:
            out.append(None)
    return out


def _change(values, i, lag=20):
    if i < lag or values[i] is None or not values[i - lag]:
        return None
    return 100 * (values[i] / values[i - lag] - 1)


def raw_readings(series):
    """{leg: [raw value or None per CAC 40 trading day]} and the list of days."""
    cac = series.get('cac') or {}
    days = sorted(cac)
    close = [cac[d] for d in days]
    raw = {leg['key']: [None] * len(days) for leg in LEGS}
    chf = _aligned(series['eurchf'], days) if 'eurchf' in series else [None] * len(days)
    gold, usd = (_aligned(series[k], days) if k in series else [None] * len(days) for k in ('gold', 'eurusd'))
    gold_eur = [g / u if g and u else None for g, u in zip(gold, usd)]
    total = 0.0
    for i, value in enumerate(close):
        total += value
        if i >= 125:
            total -= close[i - 125]
        if i >= 124:
            raw['momentum'][i] = 100 * (value / (total / 125) - 1)
        if i >= 20:
            moves = [log(close[j] / close[j - 1]) for j in range(i - 19, i + 1)]
            mean = sum(moves) / 20
            raw['volatility'][i] = 100 * sqrt(sum((m - mean) ** 2 for m in moves) / 19) * sqrt(252)
        raw['haven'][i] = _change(chf, i)
        stock, metal = _change(close, i), _change(gold_eur, i)
        raw['gold'][i] = stock - metal if stock is not None and metal is not None else None
    return days, raw


def rank(history, value):
    """Percentile of value within history (ties count half), 0-100."""
    ordered = sorted(history)
    below, upto = bisect_left(ordered, value), bisect_right(ordered, value)
    return 100 * (below + (upto - below) / 2) / len(ordered)


def compute(series):
    """Daily index and leg scores. Each day ranks only against that day and the WINDOW-1 before it."""
    days, raw = raw_readings(series)
    rows = []
    for i, day in enumerate(days):
        legs = {}
        for leg in LEGS:
            values = raw[leg['key']]
            if values[i] is None:
                continue
            window = [v for v in values[max(0, i - WINDOW + 1):i + 1] if v is not None]
            if len(window) < MIN_HISTORY:
                continue
            score = rank(window, values[i])
            legs[leg['key']] = dict(raw=round(values[i], 4), score=round(100 - score if leg['flip'] else score, 1))
        if len(legs) >= 2:
            rows.append(dict(date=day, index=round(sum(l['score'] for l in legs.values()) / len(legs), 1), legs=legs))
    return rows


def load(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if data.get('schemaVersion') == SCHEMA and data.get('days') else {}
    except (OSError, ValueError, AttributeError):
        return {}


def csv_text(rows):
    head = 'date,index,' + ','.join(f'{l["key"]}_raw,{l["key"]}_score' for l in LEGS)
    lines = [head]
    for row in rows:
        cells = [row['date'], f'{row["index"]:.1f}']
        for leg in LEGS:
            got = row['legs'].get(leg['key'])
            cells += [f'{got["raw"]:.4f}', f'{got["score"]:.1f}'] if got else ['', '']
        lines.append(','.join(cells))
    return '\n'.join(lines) + '\n'


# --- Rendering ---------------------------------------------------------------------

def _fmt_day(day):
    return Date.fromisoformat(day).strftime('%-d %b %Y')


def _ago(rows, days_back):
    target = (Date.fromisoformat(rows[-1]['date']) - timedelta(days=days_back)).isoformat()
    i = bisect_right([r['date'] for r in rows], target) - 1
    return rows[i] if i >= 0 else None


def line_chart(points, label, height=200, bands=True, width=960, left=36, bottom=22, top=10):
    """Index line on a 0-100 scale with the fear/greed bands shaded behind it."""
    plot_h = height - top - bottom
    y = lambda v: top + plot_h * (1 - v / 100)
    n = len(points)
    x = lambda i: left + (width - left) * (i / max(1, n - 1))
    shade = ''
    if bands:
        tones = {'Extreme fear': (barometer.NEG, .22), 'Fear': (barometer.NEG, .10), 'Neutral': (barometer.MID, .25),
                 'Greed': (barometer.POS, .10), 'Extreme greed': (barometer.POS, .22)}
        for low, high, name in BANDS:
            fill, alpha = tones[name]
            shade += (f'<rect x="{left}" y="{y(min(high, 100)):.1f}" width="{width - left}" height="{y(low) - y(min(high, 100)):.1f}" '
                      f'fill="{fill}" fill-opacity="{alpha}"><title>{name}: {low}–{min(high, 100):.0f}</title></rect>')
    ticks = ''.join(f'<text class="tick" x="{left - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>' for v in (0, 25, 45, 55, 75, 100))
    path = ' '.join(f'{x(i):.1f},{y(v):.1f}' for i, (_, v) in enumerate(points))
    years, last = '', None
    for i, (day, _) in enumerate(points):
        if day[:4] != last and i:
            years += f'<text class="tick" x="{x(i):.1f}" y="{height - 4}" text-anchor="middle">{day[:4]}</text>'
        last = day[:4]
    step = max(1, n // 160)
    hits = ''.join(f'<g><title>{_fmt_day(day)} · {v:.1f} · {band(v)}</title><circle class="hit" cx="{x(i):.1f}" cy="{y(v):.1f}" r="7"/>'
                   f'<circle class="dot" cx="{x(i):.1f}" cy="{y(v):.1f}" r="3"/></g>'
                   for i, (day, v) in enumerate(points) if i % step == 0 or i == n - 1)
    return (f'<div class="chart-scroll"><svg class="line-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">'
            f'{shade}{ticks}{years}<polyline class="index-line" points="{path}"/>{hits}</svg></div>')


def spark(points):
    """A leg's score over its ranking window: small line on 0-100, no axis."""
    width, height = 300, 60
    n = len(points)
    coords = ' '.join(f'{4 + (width - 8) * i / max(1, n - 1):.1f},{4 + (height - 8) * (1 - v / 100):.1f}' for i, v in enumerate(points))
    mid = 4 + (height - 8) / 2
    return (f'<svg class="leg-spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">'
            f'<line class="axis" x1="0" y1="{mid}" x2="{width}" y2="{mid}"/><polyline class="index-line" points="{coords}"/></svg>')


def page(rows, news, base, note):
    """Body of /sentiment/. rows: computed daily history; news: barometer reading for today or None."""
    body = '<main class="shell sentiment" id="main-content">'
    if not rows:
        return (body + '<div class="edition-label"><h1>Sentiment</h1></div><p class="empty">Market data is not available yet; '
                'the index appears after the next successful update.</p></main>')
    today = rows[-1]
    value = today['index']
    month = _ago(rows, 30)
    body += (f'<div class="edition-label"><h1>Sentiment</h1><div class="statusline">Fear and greed in French markets · '
             f'close of {_fmt_day(today["date"])}</div></div>')
    if note:
        body += f'<p class="mini-meta">{escape(note)}</p>'

    # Headline
    since = next((r for r in reversed(rows[:-1]) if r['index'] >= 45), None)
    summary = f'The index reads <strong>{value:.1f}</strong> of 100.'
    if month:
        summary += (f' A month ago it was {month["index"]:.0f} ({band(month["index"]).lower()}), '
                    f'a change of {value - month["index"]:+.0f} points.')
    if value < 45 and since:
        summary += f' The last close at neutral or better was {_fmt_day(since["date"])}.'
    body += ('<section class="panel" aria-labelledby="now-title"><div class="section-heading">'
             '<h2 class="section-title" id="now-title">One number from 0 to 100</h2>'
             '<span>four market readings, each ranked against its own last 3 years, then averaged</span></div>'
             '<div class="today-grid"><div class="dial">'
             + barometer.gauge(value, BANDS, 0, 100, 'Fear and greed index', '{:.0f}')
             + f'<div class="dial-value">{value:.1f}<span>{band(value)}</span></div></div><div><p class="lede">{summary}</p><div class="tiles">')
    for label, back in (('Previous close', None), ('1 week ago', 7), ('1 month ago', 30), ('1 year ago', 365)):
        then = rows[-2] if back is None and len(rows) > 1 else _ago(rows, back) if back else None
        if then:
            diff = value - then['index']
            body += (f'<div class="stat"><span class="stat-label">{label}</span><span class="stat-value">{then["index"]:.1f}</span>'
                     f'<span class="stat-note {"up" if diff >= 0 else "down"}">{"▲" if diff >= 0 else "▼"} {diff:+.1f} since · {_fmt_day(then["date"])}</span></div>')
    body += '</div></div></div></section>'

    # Record
    values = sorted(r['index'] for r in rows)
    at_or_below = 100 * bisect_right(values, value) / len(values)
    streak = 0
    for r in reversed(rows):
        if band(r['index']) != band(value):
            break
        streak += 1
    start_band = rows[-streak]['date']
    fearful = 100 * sum(1 for v in values if v < 45) / len(values)
    body += ('<section class="panel" aria-labelledby="record-title"><div class="section-heading">'
             '<h2 class="section-title" id="record-title">Where today sits in the record</h2>'
             f'<span>{len(rows):,} daily readings since {_fmt_day(rows[0]["date"])}</span></div><ul class="record">'
             f'<li><strong>{at_or_below:.0f}%</strong> of daily readings were at or below today\'s.</li>'
             f'<li>Day <strong>{streak}</strong> in {band(value).lower()}, since {_fmt_day(start_band)}.</li>'
             f'<li>The index was below 45 (fear or worse) on <strong>{fearful:.0f}%</strong> of trading days.</li></ul>'
             '<p class="mini-meta">Counts of the record, not a forecast of what follows.</p></section>')

    # Legs
    body += ('<section class="panel" aria-labelledby="legs-title"><div class="section-heading">'
             '<h2 class="section-title" id="legs-title">The four market readings</h2>'
             f'<span>each scored 0–100 against its last {WINDOW} trading days · the index is their plain average</span></div><div class="legs">')
    window = rows[-WINDOW:]
    for leg in LEGS:
        got = today['legs'].get(leg['key'])
        history = [r['legs'][leg['key']] for r in window if leg['key'] in r['legs']]
        if not got or not history:
            body += (f'<article class="leg"><h3>{leg["name"]}</h3><p class="empty-mini">No reading today '
                     f'({escape(leg["inputs"])} not available).</p></article>')
            continue
        raws = sorted(h['raw'] for h in history)
        median = raws[len(raws) // 2]
        u, d = leg['unit'], leg['digits']
        body += (f'<article class="leg"><div class="leg-head"><h3>{leg["name"]}</h3><span class="leg-band">{band(got["score"])}</span>'
                 f'<span class="leg-score">{got["score"]:.0f}</span></div>'
                 f'<div class="leg-raw"><span>{escape(leg["measure"])}</span><strong>{got["raw"]:+.{d}f}{u}</strong></div>'
                 f'<div class="leg-range"><span>3-year low {raws[0]:+.{d}f}</span><span>median {median:+.{d}f}</span><span>high {raws[-1]:+.{d}f}</span></div>'
                 f'{spark([h["score"] for h in history])}'
                 f'<div class="leg-dates"><span>{_fmt_day(window[0]["date"])}</span><span>score, ranked within its last 3 years</span>'
                 f'<span>{_fmt_day(today["date"])}</span></div>'
                 f'<p>{escape(leg["about"])}</p><p class="mini-meta">{escape(leg["inputs"])}</p></article>')
    body += '</div></section>'

    # Alongside
    body += ('<section class="panel" aria-labelledby="beside-title"><div class="section-heading">'
             '<h2 class="section-title" id="beside-title">The news, shown alongside</h2><span>not in the index</span></div>')
    if news:
        body += (f'<div class="stat"><span class="stat-label">News tone, past 24 hours</span><span class="stat-value">{news["tone"]:+d}</span>'
                 f'<span class="stat-note">{barometer.zone(news["tone"])} · {news["stories"]} France + Global Markets stories</span></div>')
    body += (f'<p>Market mood and news tone answer different questions, so they are kept apart. '
             f'The <a href="{base}barometer/">Barometer</a> sets the news tone against the CAC 40 session by session.</p></section>')

    # History
    weekly = []
    for r in rows:
        week = Date.fromisoformat(r['date']).isocalendar()[:2]
        if weekly and weekly[-1][0] == week:
            weekly[-1] = (week, r)
        else:
            weekly.append((week, r))
    weekly = [r for _, r in weekly]
    recent = [(r['date'], r['index']) for r in rows[-WINDOW:]]
    body += ('<section class="panel" aria-labelledby="history-title"><div class="section-heading">'
             '<h2 class="section-title" id="history-title">The index through time</h2>'
             f'<span>shaded bands: fear to greed</span></div>'
             '<h3 class="chart-title">Last 3 years · daily closes</h3>' + line_chart(recent, 'Index, last 3 years')
             + f'<h3 class="chart-title">Since {weekly[0]["date"][:4]} · weekly closes</h3>'
             + line_chart([(r['date'], r['index']) for r in weekly], 'Index, weekly closes', height=160))
    shares = ''.join(f'<tr><th scope="row">{name}</th><td>{low}–{min(high, 100):.0f}</td>'
                     f'<td>{100 * sum(1 for r in weekly if low <= r["index"] < high) / len(weekly):.0f}%</td></tr>'
                     for low, high, name in BANDS)
    body += ('<table class="theme-table band-table"><thead><tr><th scope="col">Band</th><th scope="col">Range</th>'
             f'<th scope="col">Share of weeks</th></tr></thead><tbody>{shares}</tbody></table>'
             f'<p class="mini-meta"><a href="{base}sentiment.csv">Download the daily index and every reading (CSV)</a></p></section>')

    # Method
    body += ('<section class="panel method" aria-labelledby="method-title"><div class="section-heading">'
             '<h2 class="section-title" id="method-title">How the index is built</h2></div><ul>'
             '<li><strong>Readings:</strong> every CAC 40 trading day gets up to four raw readings: the CAC 40\'s distance from its '
             '125-day average; its 20-day volatility (standard deviation of daily log returns, annualised); the 20-day change in EUR/CHF; '
             'and the CAC 40\'s 20-day return minus that of gold priced in euros (gold futures divided by EUR/USD).</li>'
             f'<li><strong>Scores:</strong> each reading is ranked as a percentile within its last {WINDOW} trading days (about 3 years), '
             f'using that day and earlier days only. A rank needs at least {MIN_HISTORY} days of history. Volatility is flipped '
             '(100 minus the rank) so that, for every reading, high means greed.</li>'
             '<li><strong>Index:</strong> the plain average of the readings available that day, left blank when fewer than two are. '
             f'Currency and gold prices carry their last value over market holidays for up to {CARRY_DAYS} days.</li>'
             '<li><strong>Bands:</strong> below 25 extreme fear, 25–45 fear, 45–55 neutral, 55–75 greed, 75 and above extreme greed.</li>'
             '<li><strong>Relative, not absolute:</strong> each reading is judged against the last three years, so the same volatility can '
             'score as fear after a calm stretch and as calm after a crisis. It describes how stretched the mood is, not a timing signal.</li>'
             '<li><strong>Data:</strong> daily closes from Yahoo Finance (CAC 40, EUR/CHF, gold futures, EUR/USD), refreshed every hour. '
             'Not investment advice.</li></ul></section>')
    return body + '</main>'
