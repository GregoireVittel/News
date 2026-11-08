"""CAC 40 news barometer (stdlib only, no JavaScript).

Measures the tone and themes of France + Global Markets stories and sets them
next to CAC 40 daily moves. It shows co-movement, not cause and effect.

History lives in ``barometer.json`` on the published site and grows with every
build: per-story scores are kept for recent trading sessions (so hourly builds
never double count a story) and folded into one row per session after that.
"""
from datetime import date as Date, datetime, time, timedelta, timezone
from html import escape
from math import sqrt
from zoneinfo import ZoneInfo
from math import cos, pi, sin
import csv
import io
import json
import re
import unicodedata

PARIS = ZoneInfo('Europe/Paris')
MARKET_SECTIONS = ('France', 'Financial')
CLOSE = time(17, 30)          # Euronext Paris closing auction
KEEP_PENDING_DAYS = 10        # per-story scores kept this long, then folded into sessions
KEEP_MARKET_DAYS = 800
MIN_STORIES = 5               # sessions with fewer stories are too thin to score
MIN_SESSIONS = 20             # correlations stay hidden below this many sessions
CHART_SESSIONS = 60
SCHEMA = 1


def _text(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', (value or '').casefold().replace('ł', 'l'))
                   if not unicodedata.combining(c))


def _words(pattern):
    return re.compile(r'(?<![\w])(?:' + pattern + r')\b', re.I)


# Word lists (accents removed, ł -> l) in French, English and Polish. Prefix
# matches are deliberate: "chute" covers chutent/chuté, "plung" covers plunges.
POSITIVE = _words(
    r'hausse|rebond\w*|progress\w*|grimp\w*|bondi\w*|envol\w*|record\w*|croissance|reprise|optimis\w*|'
    r'accords?|benefice\w*|embellie|soulag\w*|ameliora\w*|confiance|'
    r'rall(?:y|ies|ied)|surg\w*|soar\w*|jump\w*|gain\w*|rise[sn]?|rising|rose|climb\w*|recover\w*|boost\w*|'
    r'beat\w*|upgrad\w*|growth|profit\w*|strong\w*|optimis\w*|deal\w*|agree\w*|relief|improv\w*|'
    r'wzrost\w*|wzros\w*|zysk\w*|odbici\w*|porozumien\w*|rekord\w*|popraw\w*|optymiz\w*')
NEGATIVE = _words(
    r'baiss\w*|chut\w*|recul\w*|plong\w*|effondr\w*|crise|recession|inquiet\w*|crainte\w*|menace\w*|'
    r'faillite\w*|perte\w*|deficit\w*|dette\w*|greve\w*|censure|degrad\w*|licenci\w*|tension\w*|guerre\w*|'
    r'sanction\w*|droits de douane|incertitude\w*|'
    r'fall\w*|fell|drop\w*|declin\w*|slump\w*|plung\w*|tumbl\w*|sink\w*|sank|crash\w*|loss\w*|lose[sr]?|'
    r'recession\w*|crisis|fear\w*|worr\w*|threat\w*|warn\w*|risk\w*|tariff\w*|war|wars|strike\w*|'
    r'downgrad\w*|default\w*|bankrupt\w*|layoff\w*|weak\w*|turmoil|uncertain\w*|sanction\w*|'
    r'spad\w*|strat(?:a|y|e|ami|ach)?|kryzys\w*|recesj\w*|obaw\w*|zagroz\w*|wojn\w*|cla|upadl\w*|zwolnien\w*')

# CAC 40 sectors first, then the market-wide drivers that move every sector.
THEMES = (
    ('banks', 'Banks & insurance', 'sector',
     r'banque\w*|bancaire\w*|bank\w*|assur\w*|insur\w*|ubezpiecz\w*|credit\w*|kredyt\w*'),
    ('luxury', 'Luxury & consumer', 'sector',
     r'luxe|luxury|consommat\w*|consumer\w*|retail\w*|distribution|cosmeti\w*|fashion|spirits?|spiritueux|konsum\w*'),
    ('energy', 'Energy & utilities', 'sector',
     r'petrol\w*|oil|brent|gaz|gas|energ\w*|electricit\w*|nuclea\w*|renouvelable\w*|renewable\w*|opep|opec|ropa|paliw\w*'),
    ('industry', 'Industry, aerospace & defence', 'sector',
     r'industri\w*|aeronauti\w*|aerospace|aircraft|avion\w*|defen[cs]e|defense|armement\w*|arms|zbrojen\w*|'
     r'construction|btp|ciment\w*|cement|chemicals?|chimi\w*|lotnicz\w*|przemysl\w*'),
    ('autos', 'Autos', 'sector',
     r'auto(?:mobile)?s?\b|automobil\w*|automotive|carmaker\w*|voitures?|cars?\b|electric vehicles?|vehicules? electriques?|samochod\w*'),
    ('tech', 'Tech & semiconductors', 'sector',
     r'tech\w*|semi-?conduct\w*|chip\w*|puce\w*|software|logiciel\w*|numerique|digital|cloud|intelligence artificielle|artificial intelligence'),
    ('health', 'Healthcare & pharma', 'sector',
     r'pharma\w*|sante|health\w*|medicament\w*|drugs?|vaccin\w*|hopital\w*|hospital\w*|lek(?:i|ow|ami)?|farmac\w*|zdrowi\w*'),
    ('rates', 'Rates, ECB & inflation', 'driver',
     r'bce|ecb|fed|federal reserve|banque centrale|central bank\w*|taux|interest rates?|rate (?:cut|hike)s?|'
     r'inflation|inflacj\w*|obligat\w*|bonds?|yields?|oat|stop\w* procent\w*'),
    ('politics', 'French politics & budget', 'driver',
     r'budget\w*|gouvernement|government|premier ministre|prime minister|assemblee|parlement\w*|parliament|'
     r'censure|dissolution|election\w*|matignon|elysee|macron|deficit\w*|dette publique|public debt|wybor\w*|rzad\w*'),
    ('trade', 'Trade & tariffs', 'driver',
     r'tarif\w*|droits de douane|douan\w*|trade (?:war|deal|talks)|guerre commerciale|commerce mondial|exports?|exportations?|imports?|importations?|protectionnis\w*|cla|handel\w*'),
    ('geopolitics', 'Geopolitics & war', 'driver',
     r'guerre\w*|war|wars|ukrain\w*|russi\w*|rosj\w*|iran\w*|israel\w*|gaza|missile\w*|attaque\w*|attack\w*|'
     r'otan|nato|sanction\w*|conflit\w*|conflict\w*|wojn\w*|atak\w*'),
)
THEME_PATTERNS = {key: _words(pattern) for key, _, _, pattern in THEMES}
THEME_LABELS = {key: label for key, label, _, _ in THEMES}

ZONES = ((-100, -40, 'Stormy'), (-40, -10, 'Rain'), (-10, 10, 'Changeable'), (10, 40, 'Fair'), (40, 101, 'Sunny'))


def zone(tone):
    return next(name for low, high, name in ZONES if low <= tone < high)


# --- Scoring ------------------------------------------------------------------

def session_for(moment):
    """Trading session a story can still move: news after 17:30 Paris counts for
    the next weekday's session; weekend news counts for Monday. Exchange
    holidays are not modelled; they simply have no CAC 40 close."""
    local = moment.astimezone(PARIS)
    day = local.date() + timedelta(days=1 if local.time() >= CLOSE else 0)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.isoformat()


def score(article):
    text = _text(article.get('title', '') + ' ' + article.get('description', ''))
    return dict(pos=len(POSITIVE.findall(text)), neg=len(NEGATIVE.findall(text)),
                themes=[key for key, pattern in THEME_PATTERNS.items() if pattern.search(text)])


def tone(pos, neg):
    """Net tone from -100 (all negative wording) to +100 (all positive)."""
    return round(100 * (pos - neg) / (pos + neg)) if pos + neg else 0


def summarize(entries):
    entries = list(entries)
    pos = sum(e['pos'] for e in entries)
    neg = sum(e['neg'] for e in entries)
    themes = {key: sum(1 for e in entries if key in e['themes']) for key in THEME_LABELS}
    return dict(stories=len(entries), pos=pos, neg=neg, tone=tone(pos, neg),
                themes={k: v for k, v in themes.items() if v})


def market_stories(articles):
    return [a for a in articles if a.get('section') in MARKET_SECTIONS]


def _date(value):
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def update(previous, articles, now, market=None):
    """Return the new history: previous history + this build's stories + prices."""
    history = dict(schemaVersion=SCHEMA, sessions=dict(previous.get('sessions', {})),
                   pending=dict(previous.get('pending', {})), market=dict(previous.get('market', {})))
    for article in market_stories(articles):
        try:
            published = _date(article['date'])
        except (KeyError, TypeError, ValueError):
            continue
        history['pending'][article['link']] = dict(session=session_for(published), **score(article))
    by_session = {}
    for entry in history['pending'].values():
        by_session.setdefault(entry['session'], []).append(entry)
    for session, entries in by_session.items():
        history['sessions'][session] = summarize(entries)
    cutoff = (now.astimezone(PARIS).date() - timedelta(days=KEEP_PENDING_DAYS)).isoformat()
    history['pending'] = {link: e for link, e in history['pending'].items() if e['session'] >= cutoff}
    history['market'].update(market or {})
    oldest = (now.astimezone(PARIS).date() - timedelta(days=KEEP_MARKET_DAYS)).isoformat()
    history['market'] = {d: round(float(v), 2) for d, v in sorted(history['market'].items()) if d >= oldest}
    return history


def load(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) and data.get('schemaVersion') == SCHEMA else {}
    except (OSError, ValueError):
        return {}


def backfill(history_root):
    """Stories from saved daily snapshots, used only when no barometer history exists yet."""
    stories = []
    for path in sorted(history_root.glob('[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/articles.json')):
        try:
            stories += [a for a in json.loads(path.read_text(encoding='utf-8')).get('articles', []) if isinstance(a, dict)]
        except (OSError, ValueError):
            continue
    return stories


# --- CAC 40 prices --------------------------------------------------------------

YAHOO = 'https://query1.finance.yahoo.com/v8/finance/chart/%5EFCHI?range=6mo&interval=1d'
STOOQ = 'https://stooq.com/q/d/l/?s=%5Ecac&i=d'


def parse_yahoo(data):
    result = json.loads(data)['chart']['result'][0]
    closes = result['indicators']['quote'][0]['close']
    out = {}
    for stamp, close in zip(result['timestamp'], closes):
        if close is not None:
            out[datetime.fromtimestamp(stamp, timezone.utc).astimezone(PARIS).date().isoformat()] = float(close)
    return out


def parse_stooq(data):
    rows = csv.DictReader(io.StringIO(data.decode('utf-8', 'replace')))
    out = {}
    for row in rows:
        try:
            Date.fromisoformat(row['Date'])
            out[row['Date']] = float(row['Close'])
        except (KeyError, TypeError, ValueError):
            continue
    return out


SOURCES = (('Yahoo Finance', YAHOO, parse_yahoo), ('Stooq', STOOQ, parse_stooq))


def fetch_market(get):
    """Daily CAC 40 closes from the first source that answers: (closes, source, errors)."""
    errors = []
    for name, url, parse in SOURCES:
        try:
            closes = parse(get(url))
            if len(closes) < 5:
                raise ValueError('too few prices')
            return closes, name, errors
        except Exception as error:  # any failure falls through to the next source
            errors.append(f'{name}: {type(error).__name__}: {error}')
    return {}, None, errors


# --- Analysis -------------------------------------------------------------------

def returns(market):
    days = sorted(market)
    return {day: round(100 * (market[day] / market[prev] - 1), 2) for prev, day in zip(days, days[1:]) if market[prev]}


def pearson(pairs):
    n = len(pairs)
    if n < 3:
        return None
    xs, ys = zip(*pairs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in pairs)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return round(sxy / sqrt(sxx * syy), 2) if sxx and syy else None


def pairs(history):
    """Rows of (session, tone, same-day return, next-session return) for scored sessions."""
    moves = returns(history['market'])
    days = sorted(moves)
    following = dict(zip(days, days[1:]))
    rows = []
    for day in days:
        info = history['sessions'].get(day)
        if not info or info['stories'] < MIN_STORIES:
            continue
        nxt = following.get(day)
        rows.append((day, info['tone'], moves[day], moves.get(nxt) if nxt else None))
    return rows


def strength(r):
    size = abs(r)
    word = 'no clear' if size < 0.1 else 'weak' if size < 0.3 else 'moderate' if size < 0.5 else 'strong'
    return word + ('' if size < 0.1 else ' positive' if r > 0 else ' negative')


# --- Rendering (inline SVG, native <title> tooltips) -----------------------------

POS = '#3987e5'    # positive tone / CAC 40 up   (validated on the dark page surface)
NEG = '#e66767'    # negative tone / CAC 40 down
MID = '#383835'


def _num(value, digits=1, sign=True):
    return f'{value:+.{digits}f}' if sign else f'{value:.{digits}f}'


def gauge(value):
    """Half-dial from -100 to +100 with five weather zones and a needle."""
    cx, cy, r = 160, 150, 120

    def point(v, radius):
        angle = pi * (1 - (v + 100) / 200)
        return cx + radius * cos(angle), cy - radius * sin(angle)

    arcs = ''
    fills = (NEG, NEG, MID, POS, POS)
    opacity = (1, .55, 1, .55, 1)
    for (low, high, name), fill, alpha in zip(ZONES, fills, opacity):
        high = min(high, 100)
        (x1, y1), (x2, y2) = point(low, r), point(high, r)
        arcs += (f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 0 1 {x2:.1f},{y2:.1f}" stroke="{fill}" stroke-opacity="{alpha}" '
                 f'stroke-width="22" fill="none"><title>{name}: {low:+d} to {high:+d}</title></path>')
        lx, ly = point((low + high) / 2, r + 26)
        arcs += f'<text class="gauge-zone" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{name}</text>'
    nx, ny = point(max(-100, min(100, value)), r - 30)
    return (f'<svg class="gauge" viewBox="-36 0 392 175" role="img" aria-label="Barometer reading {value:+d}, {zone(value)}">{arcs}'
            f'<line class="gauge-needle" x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}"/>'
            f'<circle class="gauge-hub" cx="{cx}" cy="{cy}" r="7"/></svg>')


def bars(points, label, unit, digits):
    """Diverging bars around zero for one measure; one chart per measure (no dual axis)."""
    width, height, top, bottom, left = 960, 150, 14, 22, 44
    values = [v for _, v in points if v is not None]
    peak = max([abs(v) for v in values] + [1e-9])
    plot = height - top - bottom
    zero = top + plot / 2
    step = (width - left) / max(1, len(points))
    bar = max(2, min(18, step - 2))
    marks = ''
    for i, (day, v) in enumerate(points):
        x = left + i * step + (step - bar) / 2
        if v is None:
            marks += f'<g><title>{day} · no data</title><rect class="hit" x="{left + i * step:.1f}" y="{top}" width="{step:.1f}" height="{plot}"/></g>'
            continue
        h = max(1, abs(v) / peak * plot / 2)
        y = zero - h if v >= 0 else zero
        marks += (f'<g><title>{day} · {label} {v:+.{digits}f}{unit}</title>'
                  f'<rect class="hit" x="{left + i * step:.1f}" y="{top}" width="{step:.1f}" height="{plot}"/>'
                  f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar:.1f}" height="{h:.1f}" rx="2" fill="{POS if v >= 0 else NEG}"/></g>')
    axis = (f'<line class="axis" x1="{left}" y1="{zero:.1f}" x2="{width}" y2="{zero:.1f}"/>'
            f'<text class="tick" x="{left - 6}" y="{top + 4}" text-anchor="end">{peak:+.{digits}f}</text>'
            f'<text class="tick" x="{left - 6}" y="{zero + 4:.1f}" text-anchor="end">0</text>'
            f'<text class="tick" x="{left - 6}" y="{top + plot + 4}" text-anchor="end">{-peak:+.{digits}f}</text>')
    if points:
        axis += (f'<text class="tick" x="{left}" y="{height - 4}">{points[0][0]}</text>'
                 f'<text class="tick" x="{width}" y="{height - 4}" text-anchor="end">{points[-1][0]}</text>')
    return (f'<div class="chart-scroll"><svg class="bars" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="{escape(label)} per session">{axis}{marks}</svg></div>')


def scatter(rows):
    width, height, pad = 420, 300, 40
    points = [(day, t, nxt) for day, t, _, nxt in rows if nxt is not None]
    peak = max([abs(n) for _, _, n in points] + [0.5])
    sx = lambda t: pad + (t + 100) / 200 * (width - 2 * pad)
    sy = lambda r: height / 2 - r / peak * (height / 2 - pad)
    dots = ''.join(f'<g><title>{day} · tone {t:+d} · next session CAC 40 {n:+.2f}%</title>'
                   f'<circle class="hit" cx="{sx(t):.1f}" cy="{sy(n):.1f}" r="10"/>'
                   f'<circle class="dot" cx="{sx(t):.1f}" cy="{sy(n):.1f}" r="5"/></g>' for day, t, n in points)
    axes = (f'<line class="axis" x1="{pad}" y1="{height / 2}" x2="{width - pad}" y2="{height / 2}"/>'
            f'<line class="axis" x1="{sx(0):.1f}" y1="{pad}" x2="{sx(0):.1f}" y2="{height - pad}"/>'
            f'<text class="tick" x="{pad}" y="{height - pad + 18}">−100 negative</text>'
            f'<text class="tick" x="{width - pad}" y="{height - pad + 18}" text-anchor="end">positive +100</text>'
            f'<text class="tick" x="{sx(0) + 6:.1f}" y="{pad - 8}">{peak:+.1f}%</text>'
            f'<text class="tick" x="{sx(0) + 6:.1f}" y="{height - pad + 4}">{-peak:+.1f}%</text>')
    return (f'<svg class="scatter" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="News tone against the next session\'s CAC 40 move">{axes}{dots}</svg>')


def theme_bars(today, history, sessions):
    """Stories per theme in the last 24 hours, with the 30-session average as a tick."""
    recent = [history['sessions'][d] for d in sessions[-30:]]
    rows = []
    for key, label, kind, _ in THEMES:
        count = today['themes'].get(key, 0)
        average = sum(s['themes'].get(key, 0) for s in recent) / len(recent) if recent else None
        rows.append((count, key, label, kind, average))
    peak = max([r[0] for r in rows] + [r[4] or 0 for r in rows] + [1])
    out = ''
    for count, key, label, kind, average in sorted(rows, key=lambda r: (-r[0], r[2])):
        tick = (f'<span class="theme-avg" style="left:{100 * average / peak:.1f}%" title="30-session average {average:.1f}"></span>'
                if average is not None else '')
        out += (f'<li><span class="theme-label">{escape(label)}<span class="theme-kind">{"sector" if kind == "sector" else "market driver"}</span></span>'
                f'<span class="theme-track"><span class="theme-bar" style="width:{100 * count / peak:.1f}%"></span>{tick}</span>'
                f'<span class="theme-count">{count}</span></li>')
    return f'<ul class="theme-list">{out}</ul>'


def page(history, articles, now, base, market_note):
    """Body of /barometer/: today's dial, themes, history charts, relationship, method."""
    stories = market_stories(articles)
    today = summarize(score(a) for a in stories)
    current = session_for(now)
    closed = sorted(d for d, s in history['sessions'].items() if d < current and s['stories'] >= MIN_STORIES)
    average = sum(history['sessions'][d]['stories'] for d in closed[-30:]) / len(closed[-30:]) if closed else None
    moves = returns(history['market'])
    market_days = sorted(history['market'])
    rows = pairs(history)

    # Today
    body = '<main class="shell barometer" id="main-content"><div class="edition-label"><h1>Barometer</h1>'
    body += ('<div class="statusline">France + Global Markets news vs the CAC 40 · '
             f'{len(stories)} stories in the past 24 hours</div></div>')
    cac = ''
    if market_days:
        last = market_days[-1]
        change = moves.get(last)
        cac = (f'<div class="stat"><span class="stat-label">CAC 40 · {last}</span><span class="stat-value">{history["market"][last]:,.2f}</span>'
               + (f'<span class="stat-note {"up" if change >= 0 else "down"}">{"▲" if change >= 0 else "▼"} {change:+.2f}% on previous close</span>' if change is not None else '')
               + '</div>')
    else:
        cac = '<div class="stat"><span class="stat-label">CAC 40</span><span class="stat-value">—</span><span class="stat-note">No market data yet</span></div>'
    body += ('<section class="panel barometer-today" aria-labelledby="today-title"><div class="section-heading">'
             '<h2 class="section-title" id="today-title">Today\'s reading</h2><span>tone of the past 24 hours</span></div>'
             f'<div class="today-grid"><div class="dial">{gauge(today["tone"])}'
             f'<div class="dial-value">{today["tone"]:+d}<span>{zone(today["tone"])}</span></div></div>'
             '<div class="stats">'
             f'<div class="stat"><span class="stat-label">Stories, past 24 hours</span><span class="stat-value">{today["stories"]}</span>'
             f'<span class="stat-note">{"30-session average " + format(average, ".0f") if average is not None else "Average builds up over the coming days"}</span></div>'
             f'<div class="stat"><span class="stat-label">Positive / negative words</span><span class="stat-value">{today["pos"]} / {today["neg"]}</span>'
             '<span class="stat-note">from headlines and RSS snippets</span></div>'
             f'{cac}</div></div>'
             + (f'<p class="mini-meta">{escape(market_note)}</p>' if market_note else '') + '</section>')

    # Themes
    body += ('<section class="panel" aria-labelledby="themes-title"><div class="section-heading">'
             '<h2 class="section-title" id="themes-title">CAC 40 sectors and market drivers</h2>'
             '<span>stories in the past 24 hours · tick = 30-session average</span></div>'
             f'{theme_bars(today, history, closed)}</section>')

    # History
    # Start at the first recorded news session so the two charts cover the same period.
    first = closed[0] if closed else current
    days = sorted(set(closed) | set(d for d in market_days if d in moves and first <= d < current))[-CHART_SESSIONS:]
    tone_points = [(d, history['sessions'][d]['tone'] if d in closed else None) for d in days]
    cac_points = [(d, moves.get(d)) for d in days]
    body += ('<section class="panel" aria-labelledby="history-title"><div class="section-heading">'
             '<h2 class="section-title" id="history-title">Session by session</h2>'
             f'<span>last {len(days)} trading sessions · same dates on both charts</span></div>')
    if days:
        body += ('<h3 class="chart-title">News tone (−100 to +100)</h3>' + bars(tone_points, 'Tone', '', 0)
                 + '<h3 class="chart-title">CAC 40 daily change (%)</h3>' + bars(cac_points, 'CAC 40', '%', 2)
                 + '<p class="legend"><span class="legend-item"><span class="key" style="background:' + POS + '"></span>positive tone / CAC 40 up</span>'
                 '<span class="legend-item"><span class="key" style="background:' + NEG + '"></span>negative tone / CAC 40 down</span></p>')
    else:
        body += '<p class="empty-mini">The charts fill in as sessions are recorded.</p>'
    table = ''.join(
        f'<tr><th scope="row">{d}</th><td>{history["sessions"][d]["stories"] if d in history["sessions"] else "—"}</td>'
        f'<td>{format(history["sessions"][d]["tone"], "+d") if d in history["sessions"] else "—"}</td>'
        f'<td>{format(history["market"][d], ",.2f") if d in history["market"] else "—"}</td>'
        f'<td>{format(moves[d], "+.2f") + "%" if d in moves else "—"}</td></tr>' for d in reversed(days))
    if days:
        body += ('<details class="data-table"><summary>Show as table</summary><div class="table-scroll"><table><thead><tr>'
                 '<th scope="col">Session</th><th scope="col">Stories</th><th scope="col">Tone</th><th scope="col">CAC 40 close</th>'
                 f'<th scope="col">Change</th></tr></thead><tbody>{table}</tbody></table></div></details>')
    body += '</section>'

    # Relationship
    same = pearson([(t, r) for _, t, r, _ in rows])
    nxt_pairs = [(t, n) for _, t, _, n in rows if n is not None]
    nxt = pearson(nxt_pairs)
    body += ('<section class="panel" aria-labelledby="link-title"><div class="section-heading">'
             '<h2 class="section-title" id="link-title">Does the news move with the CAC 40?</h2>'
             f'<span>{len(rows)} of {MIN_SESSIONS} sessions needed</span></div><div class="link-grid"><div>{scatter(rows)}'
             '<p class="mini-meta">Each dot is one session: news tone (across) against the CAC 40 move in the following session (up/down).</p></div><div>')
    if len(rows) >= MIN_SESSIONS and same is not None:
        body += (f'<div class="stat"><span class="stat-label">Same session</span><span class="stat-value">r = {same:+.2f}</span>'
                 f'<span class="stat-note">{strength(same)} link · {len(rows)} sessions</span></div>')
        if nxt is not None:
            body += (f'<div class="stat"><span class="stat-label">Next session</span><span class="stat-value">r = {nxt:+.2f}</span>'
                     f'<span class="stat-note">{strength(nxt)} link · {len(nxt_pairs)} sessions</span></div>')
        heavy = []
        for key, label, _, _ in THEMES:
            shares = [(history['sessions'][d]['themes'].get(key, 0) / history['sessions'][d]['stories'], r) for d, _, r, _ in rows]
            cut = sorted(s for s, _ in shares)[int(len(shares) * 2 / 3)]
            on = [r for s, r in shares if s >= cut and s > 0]
            off = [r for s, r in shares if not (s >= cut and s > 0)]
            if len(on) >= 5 and off:
                heavy.append((sum(on) / len(on) - sum(off) / len(off), label, len(on), sum(on) / len(on)))
        if heavy:
            body += ('<table class="theme-table"><thead><tr><th scope="col">Theme heavy in the news</th><th scope="col">Sessions</th>'
                     '<th scope="col">Avg CAC 40</th><th scope="col">vs other days</th></tr></thead><tbody>'
                     + ''.join(f'<tr><th scope="row">{escape(label)}</th><td>{n}</td><td>{avg:+.2f}%</td><td>{diff:+.2f} pts</td></tr>'
                               for diff, label, n, avg in sorted(heavy)) + '</tbody></table>')
    else:
        body += (f'<p class="empty-mini">Correlations appear once {MIN_SESSIONS} trading sessions have both news and a CAC 40 close '
                 f'(now {len(rows)}). Fewer sessions would mostly show chance.</p>')
    body += '</div></div></section>'

    # Method
    body += ('<section class="panel method" aria-labelledby="method-title"><div class="section-heading">'
             '<h2 class="section-title" id="method-title">How this is measured</h2></div><ul>'
             '<li><strong>Stories:</strong> France and Global Markets sections only, in all languages, from publishers\' headlines and RSS snippets.</li>'
             '<li><strong>Tone:</strong> positive minus negative market words (e.g. <em>hausse, rebond, rally / baisse, chute, plunge, spadek</em>) '
             'divided by all such words, from −100 to +100. Zones: Stormy below −40, Rain −40 to −10, Changeable −10 to +10, Fair +10 to +40, Sunny above +40. '
             'Word lists miss irony and negation, so read it as a rough gauge.</li>'
             '<li><strong>Sessions:</strong> news published after the 17:30 Paris close counts toward the next trading session; weekend news counts toward Monday. '
             f'Sessions with fewer than {MIN_STORIES} stories are left out.</li>'
             '<li><strong>CAC 40:</strong> daily closes from Yahoo Finance, with Stooq as a fallback; the latest value may be intraday while the market is open.</li>'
             '<li><strong>Read with care:</strong> a correlation shows the two moving together, not that news moves the market. '
             'News also reacts to the market, and checking many themes turns up some patterns by chance.</li></ul></section>')
    return body + '</main>'
