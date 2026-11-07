"""Daily recap card: how your positions moved since the previous close.

UI only — the numbers come from finance_utils.daily_moves, so this file can be
rendered with sample data for testing.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

_GREEN, _RED, _GREY = "#34d399", "#e5484d", "#9ca0ab"


def _eur(x: float) -> str:
    sign = "+" if x >= 0 else "−"
    return f"{sign}€{abs(x):,.0f}" if abs(x) >= 100 else f"{sign}€{abs(x):,.2f}"


def _pct(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.2f}%"


def _color(x: float) -> str:
    return _GREEN if x > 0 else _RED if x < 0 else _GREY


def _day_label(d: date | None, today: date) -> str:
    if d is None:
        return "—"
    if d == today:
        return "today"
    if d == today - timedelta(days=1):
        return "yesterday"
    return d.strftime("%a %d %b")


def _mover_lines(rows: pd.DataFrame) -> str:
    if rows.empty:
        return f"<div style='font-family:Inter; font-size:0.75rem; color:#676c77;'>None</div>"
    out = []
    for _, r in rows.iterrows():
        c = _color(r['Move'])
        out.append(
            "<div style='display:flex; justify-content:space-between; gap:0.8rem; "
            "font-family:Inter; font-size:0.8rem; padding:0.18rem 0;'>"
            f"<span style='color:#eef0f4;'>{escape(str(r['Ticker']))}</span>"
            f"<span style='color:{c}; white-space:nowrap;'>{_pct(r['Change'])} · {_eur(r['Move'])}</span>"
            "</div>"
        )
    return "".join(out)


def render_daily_recap(table: pd.DataFrame, total_move: float, total_change: float | None,
                       stock_date: date | None, has_crypto: bool, today: date) -> None:
    """Show the recap card. `table` comes from finance_utils.daily_moves."""
    known = table.dropna(subset=['Move'])
    unknown = table[table['Move'].isna()]['Ticker'].tolist()

    if known.empty:
        st.markdown(
            "<div style='background:#16171e; border:1px solid #262833; border-left:3px solid #676c77; "
            "border-radius:8px; padding:0.9rem 1.2rem; font-family:Inter; font-size:0.8rem; color:#9ca0ab;'>"
            "Daily recap: no price history available right now — try Refresh in a few minutes.</div>",
            unsafe_allow_html=True)
        return

    accent = _color(total_move)
    pct_txt = f" ({_pct(total_change)})" if total_change is not None else ""
    basis = []
    if stock_date is not None:
        basis.append(f"stocks &amp; ETFs: {_day_label(stock_date, today)} vs previous close")
    if has_crypto:
        basis.append("crypto: since 00:00 UTC")
    gainers = known[known['Move'] > 0].sort_values('Move', ascending=False).head(3)
    losers = known[known['Move'] < 0].sort_values('Move').head(3)
    up, down = int((known['Move'] > 0).sum()), int((known['Move'] < 0).sum())

    st.markdown(
        f"<div style='background:#16171e; border:1px solid #262833; border-left:3px solid {accent}; "
        "border-radius:8px; padding:1rem 1.2rem;'>"
        "<div style='display:flex; flex-wrap:wrap; gap:1.2rem 2.5rem; align-items:flex-start;'>"
        # Headline
        "<div style='min-width:220px; flex:1.2;'>"
        "<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.12em; "
        "color:#676c77; margin-bottom:0.45rem;'>Since the last close</div>"
        f"<div style='font-family:Space Grotesk; font-size:1.7rem; color:{accent}; line-height:1.1;'>"
        f"{_eur(total_move)}<span style='font-size:1rem;'>{pct_txt}</span></div>"
        f"<div style='font-family:Inter; font-size:0.72rem; color:{_GREY}; margin-top:0.35rem;'>"
        f"Price moves only · {up} up, {down} down</div>"
        f"<div style='font-family:Inter; font-size:0.65rem; color:#676c77; margin-top:0.2rem;'>"
        f"{' · '.join(basis)}</div>"
        "</div>"
        # Movers
        "<div style='min-width:200px; flex:1;'>"
        "<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.12em; "
        "color:#676c77; margin-bottom:0.3rem;'>Biggest gains</div>"
        f"{_mover_lines(gainers)}</div>"
        "<div style='min-width:200px; flex:1;'>"
        "<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.12em; "
        "color:#676c77; margin-bottom:0.3rem;'>Biggest losses</div>"
        f"{_mover_lines(losers)}</div>"
        "</div></div>",
        unsafe_allow_html=True)

    with st.expander(f"All positions since the last close ({len(table)})"):
        view = table.copy()
        view['Change'] = view['Change'] * 100
        st.dataframe(
            view, hide_index=True, width="stretch",
            column_config={
                'Ticker': st.column_config.TextColumn('Ticker'),
                'Value': st.column_config.NumberColumn('Value now', format="€%.2f"),
                'Change': st.column_config.NumberColumn('Price change', format="%+.2f%%"),
                'Move': st.column_config.NumberColumn('€ move', format="%+.2f"),
            })
        if unknown:
            st.caption("No previous close found for: " + ", ".join(map(str, unknown)))
