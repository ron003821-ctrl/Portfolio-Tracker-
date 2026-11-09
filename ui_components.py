"""HTML building blocks for the Overview page (stat cards, sparklines, holdings table).

Pure functions that return HTML strings, so they can be tested without Streamlit.
The matching CSS classes (pf-card, pf-table, pf-up, ...) live in the app's stylesheet.
"""
from __future__ import annotations

import math
from html import escape

import pandas as pd

UP, DOWN, MUTED = "#3DDC84", "#FF6B6B", "#8D93A0"


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def eur(x: float, decimals: int = 0, sign: bool = False) -> str:
    """€1,234 / −€1,234 / +€1,234 (with sign=True)."""
    s = f"€{abs(x):,.{decimals}f}"
    if x < 0:
        return "−" + s
    return ("+" + s) if sign else s


def pct(x: float, decimals: int = 2) -> str:
    """Signed percentage of a fraction: 0.0123 -> +1.23%."""
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.{decimals}f}%"


def change_class(x) -> str:
    if not _ok(x) or x == 0:
        return "pf-muted"
    return "pf-up" if x > 0 else "pf-down"


def heat_color(change) -> str:
    """Tile color for the daily heatmap: darker = smaller move, brighter = bigger move."""
    if not _ok(change):
        return "#2A2E37"
    a = abs(change)
    if change >= 0:
        return "#123F27" if a < 0.005 else "#166534" if a < 0.015 else "#15803D" if a < 0.03 else "#16A34A"
    return "#5C1A1D" if a < 0.005 else "#7F1D1D" if a < 0.015 else "#991B1B" if a < 0.03 else "#B91C1C"


def sparkline_svg(values, width: int = 90, height: int = 24) -> str:
    """Small line of the last prices, green if the last is above the first, red if below."""
    vals = [float(v) for v in values if _ok(v)]
    if len(vals) < 2:
        return "<span class='pf-muted'>—</span>"
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 2
    step = (width - 2 * pad) / (len(vals) - 1)
    pts = " ".join(
        f"{pad + i * step:.1f},{pad + (height - 2 * pad) * (1 - (v - lo) / span):.1f}"
        for i, v in enumerate(vals))
    color = UP if vals[-1] > vals[0] else DOWN if vals[-1] < vals[0] else MUTED
    return (f"<svg aria-hidden='true' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2' "
            f"stroke-linejoin='round' stroke-linecap='round'/></svg>")


def stat_card(label: str, value: str, sub: str = "", value_class: str = "", visual: str = "") -> str:
    """One stat card; `visual` (HTML) is shown to the right of the number, or below it when narrow."""
    sub_html = f"<div class='pf-small'>{sub}</div>" if sub else ""
    vis_html = f"<div class='pf-visual'>{visual}</div>" if visual else ""
    return (f"<div class='pf-card'><div class='pf-label'>{escape(label)}</div>"
            f"<div class='pf-card-body'><div class='pf-card-main'>"
            f"<div class='pf-value {value_class}'>{value}</div>{sub_html}</div>{vis_html}</div></div>")


def trend_visual(values, caption: str = "", caption_class: str = "pf-muted") -> str:
    """Sparkline with a small caption under it (e.g. '30 days +2.4%')."""
    cap = f"<div class='pf-vis-cap {caption_class}'>{caption}</div>" if caption else ""
    return sparkline_svg(values, width=120, height=40) + cap


def movers_visual(movers: list[tuple[str, float]]) -> str:
    """Small chips for the best and worst mover today: [(ticker, change), ...]."""
    chips = []
    for t, ch in movers:
        if not _ok(ch):
            continue
        cls = 'pf-chip-up' if ch > 0 else 'pf-chip-down' if ch < 0 else 'pf-chip-flat'
        arrow = '▲' if ch > 0 else '▼' if ch < 0 else '•'
        chips.append(f"<span class='pf-chip {cls}'>{arrow} {escape(str(t))} {pct(ch, 1)}</span>")
    return "<div class='pf-chips'>" + "".join(chips) + "</div>" if chips else ""


def compare_bars(rows: list[tuple[str, float | None, str]], unit: str = "%") -> str:
    """Mini horizontal bars to compare a few numbers, e.g. your return vs a benchmark.

    rows: (label, value, color). Values are already in display units (6.1 for 6.1 %).
    Bars are scaled to the largest absolute value; None shows as '—'.
    """
    vals = [abs(v) for _, v, _ in rows if v is not None]
    top = max(vals) if vals and max(vals) > 0 else 1.0
    out = []
    for label, v, color in rows:
        if v is None:
            txt, w = "—", 0
        else:
            txt = (f"{v:+.1f}%" if unit == "%" else eur(v, sign=True)).replace('-', '−')
            w = max(4, round(abs(v) / top * 100))
        out.append(
            "<div class='pf-bar-row'>"
            f"<span class='pf-bar-label'>{escape(label)}</span>"
            f"<span class='pf-bar-track'><span class='pf-bar-fill' style='width:{w}%; background:{color}'></span></span>"
            f"<span class='pf-bar-val'>{txt}</span></div>")
    return "<div class='pf-bars'>" + "".join(out) + "</div>"


def stat_row(cards: list[str]) -> str:
    return "<div class='pf-stats'>" + "".join(cards) + "</div>"


def holdings_table(rows: list[dict], title: str, hint: str = "") -> str:
    """rows: ticker, category, closes (list), change (fraction or None), value, weight (fraction),
    profit (EUR), profit_pct (fraction or None). Rendered in the given order."""
    body = []
    for r in rows:
        ch = r.get('change')
        today = f"<span class='{change_class(ch)}' style='font-weight:700'>{pct(ch)}</span>" if _ok(ch) \
            else "<span class='pf-muted'>—</span>"
        pp = r.get('profit_pct')
        profit = eur(r['profit'], sign=True) + (f" <span class='pf-muted'>{pct(pp, 1)}</span>" if _ok(pp) else "")
        body.append(
            "<tr>"
            f"<td><span class='pf-tk'>{escape(str(r['ticker']))}</span>"
            f"<span class='pf-cat'>{escape(str(r.get('category') or ''))}</span></td>"
            f"<td>{sparkline_svg(r.get('closes') or [])}</td>"
            f"<td>{today}</td>"
            f"<td>{eur(r['value'])}</td>"
            f"<td class='pf-muted'>{r['weight'] * 100:.1f}%</td>"
            f"<td class='{change_class(r['profit'])}'>{profit}</td>"
            "</tr>")
    hint_html = f"<span class='pf-hint'>{hint}</span>" if hint else ""
    return (
        "<div class='pf-table-wrap'>"
        f"<div class='pf-card-title'><h2>{escape(title)}</h2>{hint_html}</div>"
        "<div class='pf-scroll'><table class='pf-table'>"
        "<thead><tr><th>Asset</th><th>Last 5 days</th><th>Today</th><th>Value</th><th>Weight</th><th>Profit</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div></div>")


# ─────────────────────────────────────────────────────────────
# Transactions page
# ─────────────────────────────────────────────────────────────
TRANS_TYPES = ['Buy', 'Sell', 'Dividend', 'Staking', 'Staking Reward', 'Transfer']


def transaction_amount(r) -> float | None:
    """Cash effect of one transaction in EUR: money out negative, money in positive.
    None when it moves no euros (staking rewards, transfers paid in tokens)."""
    t = r.get('Type')
    q, p = float(r.get('Quantity') or 0), float(r.get('Purchase Price') or 0)
    fee = float(r.get('Fee Amount') or 0) if r.get('Fee Unit') == 'EUR' else 0.0
    if t == 'Buy':
        return -(q * p + fee)
    if t == 'Sell':
        return q * p - fee
    if t == 'Staking':
        return -(q * p)
    if t == 'Dividend':
        return float(r.get('Income') or 0)
    if t == 'Transfer':
        return -fee if fee else None
    return None


def validate_transaction(v: dict) -> str | None:
    """Return an error message for an incomplete transaction, or None when it can be saved."""
    t = v.get('type')
    if not str(v.get('ticker') or '').strip():
        return "Enter a ticker."
    if t in ('Buy', 'Sell', 'Staking', 'Staking Reward') and not (v.get('quantity') or 0) > 0:
        return "Quantity must be more than 0."
    if t in ('Buy', 'Sell', 'Staking') and not (v.get('price') or 0) > 0:
        return "Price per unit must be more than 0."
    if t == 'Dividend' and not (v.get('income') or 0) > 0:
        return "Dividend amount must be more than 0."
    if t == 'Transfer' and not (v.get('fee_amount') or 0) > 0:
        return "Transfer fee must be more than 0."
    return None


def transaction_summary(r) -> str:
    """One line describing a transaction, e.g. 'Buy 6 QDVE.DE at €41.30 on 9 Nov 2026'."""
    t, tk = r.get('Type'), r.get('Ticker')
    d = r.get('Date')
    when = d.strftime('%-d %b %Y') if hasattr(d, 'strftime') else str(d)
    q = float(r.get('Quantity') or 0)
    qs = f"{q:.8f}".rstrip('0').rstrip('.')
    if t in ('Buy', 'Sell', 'Staking'):
        return f"{t} {qs} {tk} at {eur(float(r.get('Purchase Price') or 0), 2)} on {when}"
    if t == 'Staking Reward':
        return f"Staking reward of {qs} {tk} on {when}"
    if t == 'Dividend':
        return f"Dividend of {eur(float(r.get('Income') or 0), 2)} from {tk} on {when}"
    if t == 'Transfer':
        unit = 'EUR' if r.get('Fee Unit') == 'EUR' else 'tokens'
        return f"Transfer of {tk} on {when} (fee {float(r.get('Fee Amount') or 0):g} {unit})"
    return f"{t} {tk} on {when}"


def transactions_view(trans: pd.DataFrame, search: str = "", types=None) -> pd.DataFrame:
    """Table for the Transactions page: newest first, filtered by ticker text and types.
    Keeps the 'id' column so a selected row can be found again."""
    if trans is None or trans.empty:
        return pd.DataFrame(columns=['id', 'Date', 'Type', 'Ticker', 'Quantity', 'Price', 'Fee', 'Amount'])
    df = trans.copy()
    if search:
        df = df[df['Ticker'].astype(str).str.upper().str.contains(search.strip().upper(), regex=False)]
    if types:
        df = df[df['Type'].isin(list(types))]
    df = df.assign(_t=df['Time'].astype(str)).sort_values(['Date', '_t', 'id'], ascending=False)
    out = pd.DataFrame({
        'id': df['id'],
        'Date': pd.to_datetime(df['Date']),
        'Type': df['Type'],
        'Ticker': df['Ticker'],
        'Quantity': [float(q) if t not in ('Dividend', 'Transfer') else None
                     for q, t in zip(df['Quantity'], df['Type'])],
        'Price': [float(p) if t in ('Buy', 'Sell', 'Staking') else None
                  for p, t in zip(df['Purchase Price'], df['Type'])],
        'Fee': [float(f) if (u in ('EUR', 'Asset') and float(f or 0) > 0) else None
                for f, u in zip(df['Fee Amount'], df['Fee Unit'])],
        'Amount': [transaction_amount(r) for r in df.to_dict('records')],
    })
    return out.reset_index(drop=True)
