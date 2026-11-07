"""HTML building blocks for the Overview page (stat cards, sparklines, holdings table).

Pure functions that return HTML strings, so they can be tested without Streamlit.
The matching CSS classes (pf-card, pf-table, pf-up, ...) live in the app's stylesheet.
"""
from __future__ import annotations

import math
from html import escape

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


def stat_card(label: str, value: str, sub: str = "", value_class: str = "") -> str:
    sub_html = f"<div class='pf-small'>{sub}</div>" if sub else ""
    return (f"<div class='pf-card'><div class='pf-label'>{escape(label)}</div>"
            f"<div class='pf-value {value_class}'>{value}</div>{sub_html}</div>")


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
