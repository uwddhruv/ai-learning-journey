"""
KAIROFORGE — Equity Research Terminal
A lightweight Bloomberg × Screener × TradingView hybrid.

Entry point: streamlit run app.py
"""

# ── MUST BE FIRST ─────────────────────────────────────────────────────────────
import streamlit as st

st.set_page_config(
    page_title="KAIROFORGE",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "KAIROFORGE — Created by Dhruv Vaniawala | uwddhruv@gmail.com"
    },
)

# ── IMPORTS ───────────────────────────────────────────────────────────────────
import os
import base64
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from typing import List, Dict

from modules.data_layer import (
    fetch_stock_data, fetch_price_history, fetch_market_news, fetch_ticker_news,
    fmt_large, fmt_pct, fmt_price
)
from modules.valuation_engine import calculate_dcf, calculate_graham, get_relative_valuation
from modules.scoring_engine import compute_score, signal_from_score
from modules.styles import inject_styles

# ── INJECT STYLES ─────────────────────────────────────────────────────────────
st.markdown(inject_styles(), unsafe_allow_html=True)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
DEFAULT_TICKERS = [
    "RELIANCE.NS", "TCS.NS",        "HDFCBANK.NS",  "ICICIBANK.NS",  "INFY.NS",
    "HINDUNILVR.NS","ITC.NS",        "SBIN.NS",       "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS",        "AXISBANK.NS",   "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS",     "NESTLEIND.NS",  "WIPRO.NS",      "TECHM.NS",      "HCLTECH.NS",
    "POWERGRID.NS",
]

PLOTLY_DARK = dict(
    paper_bgcolor="#0a0a0f",
    plot_bgcolor="#0d0d16",
    font=dict(color="#94a3b8", family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#1e1e2e", showline=False, zeroline=False),
    yaxis=dict(gridcolor="#1e1e2e", showline=False, zeroline=False),
    margin=dict(l=10, r=10, t=30, b=10),
)


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "page"      not in st.session_state: st.session_state.page      = "Screener"
if "selected"  not in st.session_state: st.session_state.selected  = ""
if "portfolio" not in st.session_state: st.session_state.portfolio = []


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # ── LOGO ──────────────────────────────────────────────────────────────
    _logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(_logo_path):
        with open(_logo_path, "rb") as _f:
            _logo_b64 = base64.b64encode(_f.read()).decode()
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem;">
                <img src="data:image/png;base64,{_logo_b64}"
                     width="48" height="48"
                     style="border-radius:50%;flex-shrink:0;" alt="KAIROFORGE logo"/>
                <div>
                    <div class="kf-header-logo" style="font-size:1.1rem;">KAIROFORGE</div>
                    <div class="kf-header-sub">Equity Intelligence Terminal</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="kf-header" style="border-bottom:none;margin-bottom:0.5rem;">
                <div>
                    <div class="kf-header-logo">⚡ KAIROFORGE</div>
                    <div class="kf-header-sub">Equity Intelligence Terminal</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border-color:#1e1e2e;margin:1rem 0;'>", unsafe_allow_html=True)

    nav_choice = st.radio(
        "Navigate",
        ["📊  Screener", "🔍  Stock Analysis", "💼  Portfolio Builder"],
        index=["📊  Screener", "🔍  Stock Analysis", "💼  Portfolio Builder"].index(
            "📊  Screener" if st.session_state.page == "Screener"
            else "🔍  Stock Analysis" if st.session_state.page == "Analysis"
            else "💼  Portfolio Builder"
        ),
        label_visibility="hidden",
    )
    st.session_state.page = (
        "Screener"  if "Screener"  in nav_choice else
        "Analysis"  if "Analysis"  in nav_choice else
        "Portfolio"
    )

    st.markdown("<hr style='border-color:#1e1e2e;margin:1rem 0;'>", unsafe_allow_html=True)

    # Quick ticker jump
    jump = st.text_input("🔎  Analyse a ticker", placeholder="e.g. RELIANCE.NS").strip().upper()
    if st.button("Analyse →") and jump:
        st.session_state.selected = jump
        st.session_state.page     = "Analysis"
        st.rerun()

    st.markdown("<hr style='border-color:#1e1e2e;margin:1rem 0;'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:0.7rem;color:#334155;'>Data via yfinance · Refreshes hourly</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def signal_html(signal: str) -> str:
    cls = signal.replace(" ", "\\ ")
    return f'<span class="kf-signal kf-signal-{cls}">{signal}</span>'


def confidence_html(conf: str) -> str:
    cls = conf.replace(" ", "\\ ")
    return f'<span class="kf-confidence kf-conf-{cls}">{conf} confidence</span>'


def color_for_value(v: float, v_min: float, v_max: float) -> str:
    """Green→Yellow→Red gradient based on relative position."""
    if v_max == v_min:
        return "#fbbf24"
    ratio = (v - v_min) / (v_max - v_min)
    ratio = max(0, min(1, ratio))
    if ratio > 0.5:
        r = int(255 * (1 - ratio) * 2)
        g = 200
    else:
        r = 240
        g = int(200 * ratio * 2)
    return f"rgb({r},{g},60)"


def render_score_gauge(score: float, color: str) -> str:
    """SVG donut gauge for the score."""
    r = 50
    cx = cy = 60
    circumference = 2 * np.pi * r
    filled = circumference * (score / 100)
    bg_color = "#1e1e2e"
    return f"""
    <svg width="120" height="120" viewBox="0 0 120 120" style="display:block;margin:0 auto;">
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{bg_color}" stroke-width="8"/>
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="8"
              stroke-dasharray="{filled:.1f} {circumference:.1f}"
              stroke-linecap="round"
              transform="rotate(-90 {cx} {cy})"/>
      <text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central"
            fill="{color}" font-size="22" font-weight="700"
            font-family="JetBrains Mono, monospace">{score:.0f}</text>
      <text x="{cx}" y="{cy+18}" text-anchor="middle"
            fill="#64748b" font-size="9" letter-spacing="1">/100</text>
    </svg>
    """


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: SCREENER
# ══════════════════════════════════════════════════════════════════════════════

def page_screener():
    st.markdown(
        """
        <div class="kf-section-title">Stock Screener</div>
        <p style="color:#64748b;font-size:0.85rem;margin-bottom:1.5rem;">
            Real-time valuation signals across major equities. Click a card to open deep analysis.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Controls
    col_a, col_b, col_c = st.columns([3, 1, 1])
    with col_a:
        extra = st.text_input(
            "Add tickers (comma-separated)",
            placeholder="e.g. BAJFINANCE.NS, ADANIENT.NS, ZOMATO.NS",
            label_visibility="collapsed",
        )
    with col_b:
        sort_by = st.selectbox(
            "Sort",
            ["Score ↓", "Price ↓", "P/E ↑", "MOS ↓"],
            label_visibility="collapsed",
        )
    with col_c:
        sig_filter = st.selectbox(
            "Filter",
            ["All Signals", "STRONG BUY", "BUY", "HOLD", "AVOID"],
            label_visibility="collapsed",
        )

    tickers = DEFAULT_TICKERS.copy()
    if extra.strip():
        tickers += [t.strip().upper() for t in extra.split(",") if t.strip()]

    # Progress + fetch
    progress_bar = st.progress(0, text="Loading market data…")
    results = []
    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers), text=f"Analysing {ticker}…")
        data  = fetch_stock_data(ticker)
        score = compute_score(data)
        results.append({**data, **{"_score": score}})
    progress_bar.empty()

    # Sort
    def sort_key(r):
        s = r["_score"]
        if sort_by == "Score ↓":       return -s.get("score", 0)
        elif sort_by == "Price ↓":     return -(r.get("current_price") or 0)
        elif sort_by == "P/E ↑":       return  (r.get("pe_ratio") or 9999)
        elif sort_by == "MOS ↓":
            dcf_iv = s.get("dcf", {}).get("intrinsic_value")
            price  = r.get("current_price")
            if dcf_iv and price: return -(dcf_iv - price) / price
            return 0
        return 0

    results.sort(key=sort_key)

    # Filter
    if sig_filter != "All Signals":
        results = [r for r in results if r["_score"].get("signal") == sig_filter]

    # Summary row
    signals = [r["_score"].get("signal", "NO DATA") for r in results]
    sb = signals.count("STRONG BUY") + signals.count("BUY")
    hold = signals.count("HOLD")
    av   = signals.count("AVOID") + signals.count("STRONG AVOID")

    st.markdown(
        f"""
        <div class="kf-card-sm" style="display:flex;gap:2rem;align-items:center;margin-bottom:1.5rem;">
            <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.1em;">
                Market Pulse
            </div>
            <div style="display:flex;gap:1.5rem;">
                <span style="color:#00d4aa;font-size:0.85rem;font-weight:600;">
                    ▲ {sb} Buys
                </span>
                <span style="color:#fbbf24;font-size:0.85rem;font-weight:600;">
                    ◆ {hold} Hold
                </span>
                <span style="color:#f87171;font-size:0.85rem;font-weight:600;">
                    ▼ {av} Avoid
                </span>
                <span style="color:#475569;font-size:0.8rem;">
                    {len(results)} stocks
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Header row
    st.markdown(
        """
        <div style="display:flex;padding:0 1.5rem;margin-bottom:0.5rem;gap:1.25rem;">
            <div style="width:60px;font-size:0.7rem;color:#334155;font-weight:600;
                        text-transform:uppercase;letter-spacing:.08em;">Ticker</div>
            <div style="flex:1;font-size:0.7rem;color:#334155;font-weight:600;
                        text-transform:uppercase;letter-spacing:.08em;">Company</div>
            <div style="width:80px;text-align:right;font-size:0.7rem;color:#334155;
                        font-weight:600;text-transform:uppercase;letter-spacing:.08em;">Price</div>
            <div style="width:80px;text-align:right;font-size:0.7rem;color:#334155;
                        font-weight:600;text-transform:uppercase;letter-spacing:.08em;">Score</div>
            <div style="width:120px;font-size:0.7rem;color:#334155;font-weight:600;
                        text-transform:uppercase;letter-spacing:.08em;">Signal</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Cards
    for r in results:
        sc    = r["_score"]
        score = sc.get("score", 0)
        sig   = sc.get("signal", "NO DATA")
        col   = sc.get("color", "#6b7280")
        price = r.get("current_price")
        name  = r.get("company_name", r.get("ticker", ""))
        expl  = sc.get("explanation", "")

        # Short explanation (first 100 chars)
        short_expl = expl[:120] + "…" if len(expl) > 120 else expl

        st.markdown(
            f"""
            <div class="kf-screener-card" onclick="">
                <div class="kf-screener-ticker">{r["ticker"]}</div>
                <div class="kf-screener-name">
                    <div style="color:#cbd5e1;font-size:0.85rem;font-weight:500;">{name[:30]}</div>
                    <div style="color:#334155;font-size:0.7rem;margin-top:2px;">{short_expl}</div>
                </div>
                <div class="kf-screener-price">{fmt_price(price)}</div>
                <div class="kf-screener-score">
                    <div class="kf-screener-score-num" style="color:{col};">{score:.0f}</div>
                    <div style="font-size:0.65rem;color:#334155;">/100</div>
                </div>
                <div style="width:120px;flex-shrink:0;">{signal_html(sig)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Analyse button per card
        if st.button(f"Analyse {r['ticker']}", key=f"btn_{r['ticker']}", help="Open deep analysis"):
            st.session_state.selected = r["ticker"]
            st.session_state.page     = "Analysis"
            st.rerun()

    # ── MARKET NEWS ────────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:2.5rem;'></div>", unsafe_allow_html=True)
    with st.spinner("Loading market headlines…"):
        market_news = fetch_market_news(limit=10)
    _render_news_feed(market_news, title="📰 Market News", loading=False)

    _render_footer()


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: STOCK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def page_analysis():
    ticker = st.session_state.selected

    if not ticker:
        st.markdown(
            """
            <div class="kf-card" style="text-align:center;padding:3rem;">
                <div style="font-size:3rem;margin-bottom:1rem;">🔍</div>
                <div style="color:#64748b;font-size:1rem;">
                    Enter a ticker in the sidebar or select one from the Screener.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Fetch data
    with st.spinner(f"Loading {ticker}…"):
        data  = fetch_stock_data(ticker)
        score = compute_score(data)

    if data.get("error") and not data.get("current_price"):
        st.error(f"Could not load data for **{ticker}**: {data['error']}")
        return

    sc    = score
    price = data.get("current_price") or 0
    name  = data.get("company_name", ticker)
    sig   = sc.get("signal", "NO DATA")
    col   = sc.get("color", "#6b7280")
    conf  = sc.get("confidence", "Low")

    # ── HERO PANEL ─────────────────────────────────────────────────────────
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"""
            <div class="kf-hero">
                <div class="kf-hero-ticker">{ticker} · {data.get("sector","Unknown")} · {data.get("industry","")}</div>
                <div class="kf-hero-name">{name}</div>
                <div class="kf-hero-price">{fmt_price(price)}</div>
                <div class="kf-hero-meta" style="margin-top:.75rem;display:flex;gap:1rem;align-items:center;">
                    {signal_html(sig)}
                    {confidence_html(conf)}
                    <span style="color:#475569;font-size:0.75rem;">
                        Market Cap: {fmt_large(data.get("market_cap"))}
                    </span>
                    <span style="color:#475569;font-size:0.75rem;">
                        Analyst target: {fmt_price(data.get("target_price"))}
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"""
            <div class="kf-card" style="text-align:center;padding:1.5rem 1rem;">
                <div class="kf-section-title" style="justify-content:center;margin-top:0;">
                    Opportunity Score
                </div>
                {render_score_gauge(sc.get("score",0), col)}
                <div style="color:{col};font-size:0.85rem;font-weight:600;margin-top:.5rem;">
                    {sc.get("label","—")}
                </div>
                <div style="color:#334155;font-size:0.72rem;margin-top:.3rem;">
                    Data quality: {data.get("data_quality",0)*100:.0f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── DESCRIPTION ────────────────────────────────────────────────────────
    desc = data.get("description", "")
    if desc:
        with st.expander("About this company", expanded=False):
            st.markdown(
                f"<div style='color:#94a3b8;font-size:0.85rem;line-height:1.7;'>{desc[:800]}…</div>",
                unsafe_allow_html=True,
            )

    # ── TABS ───────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Key Metrics", "📊 Price Chart", "🧮 Valuation", "🧠 Intelligence"]
    )

    # ─ TAB 1: Key Metrics ──────────────────────────────────────────────────
    with tab1:
        _render_key_metrics(data)

    # ─ TAB 2: Price Chart ──────────────────────────────────────────────────
    with tab2:
        _render_price_chart(ticker, price)

    # ─ TAB 3: Valuation Breakdown ──────────────────────────────────────────
    with tab3:
        _render_valuation_breakdown(data, sc)

    # ─ TAB 4: Intelligence / Score ─────────────────────────────────────────
    with tab4:
        _render_intelligence(data, sc)

    # ── ADD TO PORTFOLIO ────────────────────────────────────────────────────
    st.markdown("<div class='kf-section-title'>Portfolio</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3])
    with c1:
        if ticker not in st.session_state.portfolio:
            if st.button(f"➕ Add {ticker} to Portfolio"):
                st.session_state.portfolio.append(ticker)
                st.success(f"{ticker} added to your portfolio.")
        else:
            if st.button(f"✕ Remove {ticker} from Portfolio"):
                st.session_state.portfolio.remove(ticker)
                st.info(f"{ticker} removed from portfolio.")
    with c2:
        if st.session_state.portfolio:
            tags = " ".join(f'<span class="kf-port-tag">{t}</span>' for t in st.session_state.portfolio)
            st.markdown(
                f"<div style='padding-top:.4rem;'>Portfolio: {tags}</div>",
                unsafe_allow_html=True,
            )

    # ── ANALYST PRICE TARGET PANEL ──────────────────────────────────────────
    _render_price_target_panel(data)

    # ── TICKER NEWS ─────────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    with st.spinner(f"Loading {ticker} news…"):
        ticker_news = fetch_ticker_news(ticker, limit=8)
    _render_news_feed(ticker_news, title=f"📰 {ticker} News", loading=False)

    _render_footer()


def _render_key_metrics(data: Dict):
    """Render a clean metrics grid."""
    st.markdown("<div class='kf-section-title'>Valuation Ratios</div>", unsafe_allow_html=True)
    m = [
        ("P/E Ratio",    fmt_price(data.get("pe_ratio")).lstrip("₹") if data.get("pe_ratio") else "N/A",
         "Price to trailing earnings"),
        ("P/B Ratio",    f"{data.get('pb_ratio'):.2f}x" if data.get("pb_ratio") else "N/A",
         "Price to book value"),
        ("P/S Ratio",    f"{data.get('ps_ratio'):.2f}x" if data.get("ps_ratio") else "N/A",
         "Price to sales"),
        ("PEG Ratio",    f"{data.get('peg_ratio'):.2f}"  if data.get("peg_ratio") else "N/A",
         "P/E to growth — < 1 is attractive"),
        ("EV",           fmt_large(data.get("enterprise_value")),
         "Enterprise value"),
        ("Div. Yield",   fmt_pct(data.get("dividend_yield")),
         "Trailing annual dividend"),
    ]
    _metric_row(m)

    st.markdown("<div class='kf-section-title'>Profitability</div>", unsafe_allow_html=True)
    m2 = [
        ("ROE",          fmt_pct(data.get("roe")),            "Return on equity"),
        ("ROA",          fmt_pct(data.get("roa")),            "Return on assets"),
        ("Net Margin",   fmt_pct(data.get("profit_margin")),  "Net profit margin"),
        ("Gross Margin", fmt_pct(data.get("gross_margin")),   "Gross profit margin"),
        ("Op. Margin",   fmt_pct(data.get("operating_margin")),"Operating margin"),
        ("FCF",          fmt_large(data.get("free_cashflow")), "Free cash flow (TTM)"),
    ]
    _metric_row(m2)

    st.markdown("<div class='kf-section-title'>Growth & Risk</div>", unsafe_allow_html=True)
    m3 = [
        ("Rev. Growth",  fmt_pct(data.get("revenue_growth")),   "YoY revenue growth"),
        ("EPS Growth",   fmt_pct(data.get("earnings_growth")),  "YoY earnings growth"),
        ("Est. Growth",  fmt_pct(data.get("estimated_growth_rate")), "Model-estimated growth"),
        ("Beta",         f"{data.get('beta', 1.0):.2f}",        "Market sensitivity"),
        ("Revenue",      fmt_large(data.get("revenue")),         "Total revenue (TTM)"),
        ("Net Income",   fmt_large(data.get("net_income")),      "Net income (TTM)"),
    ]
    _metric_row(m3)


def _metric_row(metrics: list):
    cols = st.columns(len(metrics))
    for col, (label, value, tip) in zip(cols, metrics):
        with col:
            st.metric(label=label, value=value, help=tip)


def _render_price_target_panel(data: Dict):
    """Render an analyst consensus price-target panel, styled like existing KPI cards."""
    target      = data.get("target_price")
    price       = data.get("current_price")
    n_analysts  = data.get("analyst_count", 0)

    # Compute upside / downside vs current price
    if target and price and price > 0:
        upside_pct = (target - price) / price * 100
        upside_str = (
            f'<span style="color:#00d4aa;font-size:.8rem;font-weight:600;">▲ +{upside_pct:.1f}%</span>'
            if upside_pct >= 0 else
            f'<span style="color:#f87171;font-size:.8rem;font-weight:600;">▼ {upside_pct:.1f}%</span>'
        )
    else:
        upside_str = ""

    analyst_note = (
        f"{n_analysts} analyst{'s' if n_analysts != 1 else ''}"
        if n_analysts else "analyst consensus"
    )

    st.markdown("<div class='kf-section-title'>🎯 Analyst Price Target</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="kf-card" style="display:flex;align-items:center;gap:2.5rem;padding:1.25rem 1.5rem;
                                     flex-wrap:wrap;">
            <div>
                <div class="kf-metric-label">Consensus Target</div>
                <div style="color:#f1f5f9;font-size:1.6rem;font-weight:700;
                            font-family:'JetBrains Mono',monospace;">
                    {fmt_price(target)}
                </div>
            </div>
            <div>
                <div class="kf-metric-label">Current Price</div>
                <div style="color:#94a3b8;font-size:1.1rem;font-weight:600;
                            font-family:'JetBrains Mono',monospace;">
                    {fmt_price(price)}
                </div>
            </div>
            <div>
                <div class="kf-metric-label">Implied Move</div>
                <div style="font-size:1.1rem;">{upside_str if upside_str else '<span style="color:#64748b;">N/A</span>'}</div>
            </div>
            <div>
                <div class="kf-metric-label">Coverage</div>
                <div style="color:#64748b;font-size:.8rem;">{analyst_note}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_price_chart(ticker: str, current_price: float):
    """5-year price chart with moving averages."""
    with st.spinner("Loading chart…"):
        hist = fetch_price_history(ticker, "5y")

    if hist.empty:
        st.warning("Price history unavailable.")
        return

    hist = hist.reset_index()

    # Moving averages
    hist["MA50"]  = hist["Close"].rolling(50).mean()
    hist["MA200"] = hist["Close"].rolling(200).mean()

    fig = go.Figure()

    # Price area
    fig.add_trace(go.Scatter(
        x=hist["Date"], y=hist["Close"],
        name="Price", mode="lines",
        line=dict(color="#00d4aa", width=2),
        fill="tozeroy",
        fillcolor="rgba(0,212,170,0.05)",
    ))

    # MA50
    fig.add_trace(go.Scatter(
        x=hist["Date"], y=hist["MA50"],
        name="50-day MA", mode="lines",
        line=dict(color="#7c3aed", width=1.5, dash="dot"),
    ))

    # MA200
    fig.add_trace(go.Scatter(
        x=hist["Date"], y=hist["MA200"],
        name="200-day MA", mode="lines",
        line=dict(color="#f97316", width=1.5, dash="dot"),
    ))

    fig.update_layout(
        **PLOTLY_DARK,
        height=380,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11),
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(rangeslider_visible=False)

    st.plotly_chart(fig, use_container_width=True)

    # 52-week stats
    if len(hist) >= 52:
        recent = hist.tail(252)
        low52  = recent["Close"].min()
        high52 = recent["Close"].max()
        pos    = (current_price - low52) / (high52 - low52) * 100 if high52 != low52 else 50

        c1, c2, c3 = st.columns(3)
        c1.metric("52-Week Low",  fmt_price(low52))
        c2.metric("52-Week High", fmt_price(high52))
        c3.metric("Position in 52W Range", f"{pos:.0f}%",
                  help="100% = at 52-week high, 0% = at 52-week low")


def _render_valuation_breakdown(data: Dict, sc: Dict):
    """Side-by-side DCF vs Graham vs Market Price."""
    dcf    = sc.get("dcf",    {})
    graham = sc.get("graham", {})
    price  = data.get("current_price") or 0

    dcf_iv  = dcf.get("intrinsic_value")
    grah_iv = graham.get("graham_number")
    target  = data.get("target_price")

    # Waterfall-style comparison
    values = {}
    if dcf_iv:   values["DCF Intrinsic Value"]    = dcf_iv
    if grah_iv:  values["Graham Number"]           = grah_iv
    if target:   values["Analyst Target Price"]    = target
    values["Current Market Price"] = price

    if values:
        all_vals = list(values.values())
        v_min = min(all_vals) * 0.85
        v_max = max(all_vals) * 1.10
        span  = v_max - v_min or 1

        st.markdown("<div class='kf-section-title'>Valuation Comparison</div>", unsafe_allow_html=True)

        for label, val in values.items():
            is_market = label == "Current Market Price"
            bar_color = "#00d4aa" if not is_market else "#94a3b8"
            pct       = (val - v_min) / span * 100
            mos_str   = ""
            if not is_market and val and price:
                mos = (val - price) / price * 100
                mos_str = (
                    f"<span style='color:#00d4aa;font-size:0.75rem;margin-left:.5rem;'>+{mos:.0f}%</span>"
                    if mos > 0 else
                    f"<span style='color:#f87171;font-size:0.75rem;margin-left:.5rem;'>{mos:.0f}%</span>"
                )
            st.markdown(
                f"""
                <div class="kf-val-row">
                    <div class="kf-val-label">{label}</div>
                    <div class="kf-val-value">₹{val:.2f}{mos_str}</div>
                    <div class="kf-val-bar-wrap">
                        <div class="kf-val-bar-fill" style="width:{pct:.0f}%;background:{bar_color};"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # DCF Detail
    st.markdown("<div class='kf-section-title' style='margin-top:2rem;'>DCF Breakdown</div>", unsafe_allow_html=True)
    if dcf.get("intrinsic_value"):
        d1 = dcf.get("stage1_pv", 0) or 0
        d2 = dcf.get("stage2_pv", 0) or 0
        dt = dcf.get("terminal_pv", 0) or 0
        total = d1 + d2 + dt or 1

        fig = go.Figure(go.Bar(
            x=["Stage 1\n(Yrs 1–5)", "Stage 2\n(Yrs 6–10)", "Terminal\nValue"],
            y=[d1, d2, dt],
            marker_color=["#00d4aa", "#7c3aed", "#f97316"],
            text=[f"₹{v:.2f}" for v in [d1, d2, dt]],
            textposition="outside",
            textfont=dict(color="#94a3b8", size=12),
        ))
        fig.update_layout(
            **PLOTLY_DARK,
            height=260,
            showlegend=False,
            yaxis_title="Value per share ($)",
        )
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("WACC", f"{dcf.get('wacc',0)*100:.1f}%", help="Weighted avg cost of capital used")
        c2.metric("Stage 1 Growth", f"{dcf.get('stage1_growth',0)*100:.1f}%", help="Applied in years 1–5")
        c3.metric("Cashflow Base", f"₹{dcf.get('base_cashflow',0):.2f}", help=dcf.get("cashflow_source",""))

        st.markdown(
            f'<div class="kf-explain">{dcf.get("explanation","")}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="kf-explain" style="border-left-color:#f87171;">'
            f'{dcf.get("explanation") or dcf.get("error","DCF unavailable.")}</div>',
            unsafe_allow_html=True,
        )

    # Graham Detail
    st.markdown("<div class='kf-section-title'>Graham Number Analysis</div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="kf-explain">'
        f'{graham.get("explanation") or graham.get("error","Graham Number unavailable.")}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_intelligence(data: Dict, sc: Dict):
    """Score breakdown + narrative intelligence layer."""
    breakdown = sc.get("breakdown", {})

    # Score breakdown radar / bar
    st.markdown("<div class='kf-section-title'>Score Breakdown</div>", unsafe_allow_html=True)

    if breakdown:
        fig = go.Figure(go.Bar(
            y=list(breakdown.keys()),
            x=list(breakdown.values()),
            orientation="h",
            marker_color=["#00d4aa", "#7c3aed", "#f97316", "#4ade80", "#fbbf24", "#60a5fa"],
            text=[f"{v:.1f}" for v in breakdown.values()],
            textposition="outside",
            textfont=dict(color="#94a3b8"),
        ))
        max_x = {
            "DCF Value Gap": 30, "Graham Safety": 20,
            "Profitability": 20, "Relative Value": 15,
            "Data Quality":  15, "Consistency":    5,
        }
        fig.update_layout(
            **{**PLOTLY_DARK, "xaxis": dict(gridcolor="#1e1e2e", showline=False, zeroline=False, range=[0, 35])},
            height=280,
            showlegend=False,
            xaxis_title="Points scored",
        )
        # Add max gridlines
        for key, mx in max_x.items():
            if key in breakdown:
                fig.add_vline(
                    x=mx, line_dash="dot", line_color="#1e1e2e",
                    annotation_text=f"max {mx}", annotation_position="top",
                    annotation_font_color="#2d2d42",
                )
        st.plotly_chart(fig, use_container_width=True)

    # Analyst Narrative
    st.markdown("<div class='kf-section-title'>Analyst Intelligence</div>", unsafe_allow_html=True)
    st.markdown(
        f'<div class="kf-explain" style="font-size:0.9rem;">'
        f'{sc.get("explanation","")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Relative valuation table
    rel = sc.get("relative", {})
    st.markdown("<div class='kf-section-title'>Relative Valuation Context</div>", unsafe_allow_html=True)

    rel_data = []
    label_map = {
        "pe_ratio":  ("P/E Ratio",  f'{rel.get("pe_ratio"):.1f}x' if rel.get("pe_ratio") else "N/A",
                      rel.get("pe_signal"),  f'Sector median: {rel.get("benchmark_pe",20):.0f}x'),
        "pb_ratio":  ("P/B Ratio",  f'{rel.get("pb_ratio"):.2f}x' if rel.get("pb_ratio") else "N/A",
                      rel.get("pb_signal"),  "< 1.0 often considered deep value"),
        "peg_ratio": ("PEG Ratio",  f'{rel.get("peg_ratio"):.2f}'  if rel.get("peg_ratio") else "N/A",
                      rel.get("peg_signal"), "< 1.0 suggests growth at reasonable price"),
    }

    sig_label = {
        "cheap": "✅ Cheap", "fair": "◆ Fair", "slightly_rich": "⚠️ Rich",
        "expensive": "🔴 Expensive", "deep_value": "✅ Deep Value",
        "growth_premium": "◆ Growth Premium", "undervalued": "✅ Undervalued",
        "overvalued": "⚠️ Overvalued", "very_overvalued": "🔴 Very Overvalued", None: "—",
    }

    rows_html = ""
    for key, (label, val_str, signal, note) in label_map.items():
        sig_disp = sig_label.get(signal, "—")
        rows_html += f"""
        <div style="display:flex;gap:1.5rem;padding:.75rem 0;border-bottom:1px solid #1a1a28;
                    align-items:center;">
            <div style="width:100px;color:#94a3b8;font-size:.8rem;">{label}</div>
            <div style="width:80px;color:#f1f5f9;font-weight:600;font-family:'JetBrains Mono',mono;">{val_str}</div>
            <div style="width:160px;color:#e2e8f0;font-size:.8rem;">{sig_disp}</div>
            <div style="flex:1;color:#475569;font-size:.75rem;">{note}</div>
        </div>
        """

    st.markdown(
        f'<div class="kf-card">{rows_html}</div>',
        unsafe_allow_html=True,
    )

    # Risks & caveats
    st.markdown("<div class='kf-section-title'>What Could Go Wrong</div>", unsafe_allow_html=True)
    risks = _generate_risks(data, sc)
    risk_html = "".join(f"<li style='margin-bottom:.5rem;color:#94a3b8;'>{r}</li>" for r in risks)
    st.markdown(
        f'<div class="kf-explain"><ul style="padding-left:1.25rem;margin:0;">{risk_html}</ul></div>',
        unsafe_allow_html=True,
    )


def _generate_risks(data: Dict, sc: Dict) -> List[str]:
    """Generate contextual risk bullets."""
    risks = []
    beta = data.get("beta") or 1.0
    dq   = data.get("data_quality", 0.5)
    pe   = data.get("pe_ratio")
    debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0
    roe  = data.get("roe") or 0

    if dq < 0.5:
        risks.append("Limited financial data coverage — model outputs may be imprecise.")
    if beta > 1.5:
        risks.append(f"High market sensitivity (β={beta:.1f}) amplifies both gains and losses.")
    if pe and pe > 40:
        risks.append(f"High P/E of {pe:.0f}× demands sustained growth; multiple compression is a real risk.")
    if debt > cash * 3:
        risks.append("Debt-heavy balance sheet — interest rate sensitivity and refinancing risk present.")
    if roe < 0.05 and roe > 0:
        risks.append("Thin returns on equity suggest limited competitive moat or pricing power.")
    if sc.get("dcf", {}).get("cashflow_source") == "EPS (proxy)":
        risks.append("DCF used EPS as a cashflow proxy due to missing FCF data — estimate less reliable.")
    if not risks:
        risks.append("No major structural red flags identified, but all investments carry risk.")
        risks.append("Past financial performance does not guarantee future results.")

    risks.append("This is a quantitative model, not financial advice. Always conduct your own research.")
    return risks


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE: PORTFOLIO BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def page_portfolio():
    st.markdown(
        """
        <div class="kf-section-title">Portfolio Builder</div>
        <p style="color:#64748b;font-size:0.85rem;margin-bottom:1.5rem;">
            Select stocks from the screener or type tickers below. KAIROFORGE will interpret
            your portfolio's composition and risk profile.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Manual input
    manual = st.text_input(
        "Add tickers to portfolio (comma-separated)",
        value=", ".join(st.session_state.portfolio),
        placeholder="e.g. RELIANCE.NS, TCS.NS, HDFCBANK.NS",
    )
    if manual.strip():
        st.session_state.portfolio = [
            t.strip().upper() for t in manual.split(",") if t.strip()
        ]

    if st.button("Clear Portfolio"):
        st.session_state.portfolio = []
        st.rerun()

    if not st.session_state.portfolio:
        st.markdown(
            """
            <div class="kf-card" style="text-align:center;padding:3rem;">
                <div style="font-size:2rem;margin-bottom:.75rem;">💼</div>
                <div style="color:#64748b;">Your portfolio is empty.<br>
                Add stocks from the Screener or enter tickers above.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_footer()
        return

    # Fetch & score
    progress = st.progress(0, text="Analysing portfolio…")
    port_data = []
    for i, ticker in enumerate(st.session_state.portfolio):
        progress.progress((i + 1) / len(st.session_state.portfolio), text=f"Loading {ticker}…")
        d = fetch_stock_data(ticker)
        s = compute_score(d)
        port_data.append({**d, "_score": s})
    progress.empty()

    # ── PORTFOLIO METRICS ─────────────────────────────────────────────────
    signals  = [p["_score"].get("signal", "NO DATA") for p in port_data]
    scores   = [p["_score"].get("score", 0) for p in port_data]
    betas    = [p.get("beta") or 1.0 for p in port_data]
    sectors  = [p.get("sector", "Unknown") for p in port_data]

    avg_score = np.mean(scores)
    avg_beta  = np.mean(betas)
    n         = len(port_data)
    sector_counts = {s: sectors.count(s) for s in set(sectors)}
    max_sector_weight = max(sector_counts.values()) / n if n else 0

    # Portfolio signal
    buy_count  = sum(1 for s in signals if s in ("STRONG BUY", "BUY"))
    avoid_count = sum(1 for s in signals if s in ("AVOID", "STRONG AVOID"))

    if avg_score >= 60:     port_verdict = "🟢 Predominantly Undervalued"
    elif avg_score >= 45:   port_verdict = "🟡 Mixed — Some Value, Some Risk"
    else:                   port_verdict = "🔴 Predominantly Overvalued"

    if avg_beta > 1.3:       risk_profile = "Aggressive — High volatility exposure"
    elif avg_beta < 0.8:     risk_profile = "Defensive — Below-market volatility"
    else:                    risk_profile = "Balanced — Near-market volatility"

    if max_sector_weight > 0.5 and n > 2:
        concentration_flag = f"⚠️ {max(sector_counts, key=sector_counts.get)} sector is overweight ({max_sector_weight*100:.0f}%)"
    else:
        concentration_flag = "✅ Reasonable sector diversification"

    # Summary panel
    st.markdown("<div class='kf-section-title'>Portfolio Summary</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks",       str(n))
    c2.metric("Avg Score",    f"{avg_score:.0f}/100")
    c3.metric("Avg Beta",     f"{avg_beta:.2f}")
    c4.metric("Buys / Avoids", f"{buy_count} / {avoid_count}")

    st.markdown(
        f"""
        <div class="kf-card" style="margin-top:1rem;">
            <div style="display:flex;gap:2rem;flex-wrap:wrap;">
                <div>
                    <div class="kf-metric-label">Valuation Verdict</div>
                    <div style="color:#e2e8f0;font-size:0.95rem;font-weight:600;">{port_verdict}</div>
                </div>
                <div>
                    <div class="kf-metric-label">Risk Profile</div>
                    <div style="color:#e2e8f0;font-size:0.95rem;font-weight:600;">{risk_profile}</div>
                </div>
                <div>
                    <div class="kf-metric-label">Concentration Risk</div>
                    <div style="color:#e2e8f0;font-size:0.95rem;font-weight:600;">{concentration_flag}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── PER-STOCK TABLE ───────────────────────────────────────────────────
    st.markdown("<div class='kf-section-title' style='margin-top:2rem;'>Holdings</div>", unsafe_allow_html=True)

    for p in port_data:
        sc    = p["_score"]
        score = sc.get("score", 0)
        sig   = sc.get("signal", "NO DATA")
        col   = sc.get("color",  "#6b7280")
        price = p.get("current_price")
        dcf_iv = sc.get("dcf", {}).get("intrinsic_value")

        mos_str = ""
        if dcf_iv and price:
            mos = (dcf_iv - price) / price * 100
            mos_str = (
                f'<span style="color:#00d4aa;font-size:.75rem;"> +{mos:.0f}% MOS</span>'
                if mos > 0 else
                f'<span style="color:#f87171;font-size:.75rem;"> {mos:.0f}% premium</span>'
            )

        st.markdown(
            f"""
            <div class="kf-screener-card">
                <div class="kf-screener-ticker">{p["ticker"]}</div>
                <div class="kf-screener-name">
                    <div style="color:#cbd5e1;font-size:.85rem;font-weight:500;">
                        {p.get("company_name","")[:28]}
                    </div>
                    <div style="color:#334155;font-size:.7rem;">
                        {p.get("sector","Unknown")} · β {p.get("beta",1.0):.2f}
                    </div>
                </div>
                <div class="kf-screener-price">{fmt_price(price)}{mos_str}</div>
                <div class="kf-screener-score">
                    <div class="kf-screener-score-num" style="color:{col};">{score:.0f}</div>
                    <div style="font-size:.65rem;color:#334155;">/100</div>
                </div>
                <div style="width:120px;flex-shrink:0;">{signal_html(sig)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── PORTFOLIO CHARTS ──────────────────────────────────────────────────
    st.markdown("<div class='kf-section-title' style='margin-top:2rem;'>Portfolio Composition</div>", unsafe_allow_html=True)

    ch1, ch2 = st.columns(2)

    with ch1:
        # Signal distribution
        sig_counts = {}
        for s in signals:
            sig_counts[s] = sig_counts.get(s, 0) + 1

        color_map = {
            "STRONG BUY": "#00d4aa", "BUY": "#4ade80",
            "HOLD": "#fbbf24", "AVOID": "#f87171",
            "STRONG AVOID": "#ef4444", "NO DATA": "#6b7280",
        }
        fig_sig = go.Figure(go.Pie(
            labels=list(sig_counts.keys()),
            values=list(sig_counts.values()),
            marker_colors=[color_map.get(k, "#6b7280") for k in sig_counts.keys()],
            hole=0.6,
            textfont=dict(color="#e2e8f0"),
        ))
        fig_sig.update_layout(
            **PLOTLY_DARK,
            title=dict(text="Signal Distribution", font=dict(color="#94a3b8", size=13)),
            height=280,
            showlegend=True,
            legend=dict(font=dict(color="#94a3b8", size=11)),
        )
        st.plotly_chart(fig_sig, use_container_width=True)

    with ch2:
        # Sector allocation
        fig_sec = go.Figure(go.Pie(
            labels=list(sector_counts.keys()),
            values=list(sector_counts.values()),
            marker_colors=px.colors.qualitative.Prism,
            hole=0.6,
            textfont=dict(color="#e2e8f0"),
        ))
        fig_sec.update_layout(
            **PLOTLY_DARK,
            title=dict(text="Sector Allocation", font=dict(color="#94a3b8", size=13)),
            height=280,
            showlegend=True,
            legend=dict(font=dict(color="#94a3b8", size=11)),
        )
        st.plotly_chart(fig_sec, use_container_width=True)

    # Score distribution
    st.markdown("<div class='kf-section-title'>Opportunity Score Distribution</div>", unsafe_allow_html=True)
    tickers_sorted = [p["ticker"] for p in port_data]
    colors_sorted  = [p["_score"].get("color","#6b7280") for p in port_data]

    fig_scores = go.Figure(go.Bar(
        x=tickers_sorted, y=scores,
        marker_color=colors_sorted,
        text=[f"{s:.0f}" for s in scores],
        textposition="outside",
        textfont=dict(color="#94a3b8"),
    ))
    fig_scores.update_layout(
        **{**PLOTLY_DARK, "yaxis": dict(gridcolor="#1e1e2e", showline=False, zeroline=False, range=[0, 105], title="Score")},
        height=280,
        showlegend=False,
    )
    fig_scores.add_hline(y=72, line_dash="dot", line_color="#00d4aa",
                         annotation_text="Strong Buy", annotation_font_color="#00d4aa")
    fig_scores.add_hline(y=43, line_dash="dot", line_color="#fbbf24",
                         annotation_text="Hold",       annotation_font_color="#fbbf24")
    st.plotly_chart(fig_scores, use_container_width=True)

    # Portfolio narrative
    st.markdown("<div class='kf-section-title'>Portfolio Intelligence</div>", unsafe_allow_html=True)
    narrative = _build_portfolio_narrative(port_data, avg_score, avg_beta, sector_counts)
    st.markdown(
        f'<div class="kf-explain" style="font-size:.9rem;">{narrative}</div>',
        unsafe_allow_html=True,
    )

    _render_footer()


def _build_portfolio_narrative(port_data, avg_score, avg_beta, sector_counts):
    n = len(port_data)
    buys  = [p["ticker"] for p in port_data if p["_score"].get("signal") in ("STRONG BUY","BUY")]
    avds  = [p["ticker"] for p in port_data if p["_score"].get("signal") in ("AVOID","STRONG AVOID")]
    top_sector = max(sector_counts, key=sector_counts.get) if sector_counts else "Unknown"

    parts = [
        f"Your {n}-stock portfolio has an average Opportunity Score of {avg_score:.0f}/100."
    ]
    if avg_score >= 60:
        parts.append("Overall, the portfolio skews toward undervalued names — a constructive setup.")
    elif avg_score >= 43:
        parts.append("The portfolio is broadly at fair value; limited systematic margin of safety.")
    else:
        parts.append("Most holdings appear overvalued by our models — consider rotating toward better-valued opportunities.")

    if buys:
        parts.append(f"{', '.join(buys)} contribute the most value to the portfolio's upside case.")
    if avds:
        parts.append(f"Caution: {', '.join(avds)} score in the Avoid range and may weigh on risk-adjusted returns.")

    if avg_beta > 1.3:
        parts.append(f"Average beta of {avg_beta:.2f} indicates an aggressive tilt — suitable for risk-tolerant investors with a long horizon.")
    elif avg_beta < 0.8:
        parts.append(f"Average beta of {avg_beta:.2f} suggests a defensive portfolio — may underperform in strong bull markets.")

    if len(sector_counts) == 1:
        parts.append(f"⚠️ 100% concentration in {top_sector} — minimal diversification.")
    elif sector_counts.get(top_sector, 0) / n > 0.5:
        pct = sector_counts[top_sector] / n * 100
        parts.append(f"⚠️ {top_sector} represents {pct:.0f}% of holdings — consider adding exposure to other sectors.")

    return " ".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED FOOTER
# ══════════════════════════════════════════════════════════════════════════════

def _render_footer():
    st.markdown(
        """
        <div class="kf-footer">
            ⚡ KAIROFORGE — Created by Dhruv Vaniawala &nbsp;|&nbsp;
            <a href="mailto:uwddhruv@gmail.com">uwddhruv@gmail.com</a>
            &nbsp;·&nbsp;
            For educational purposes only. Not financial advice.
            &nbsp;·&nbsp;
            Data via Yahoo Finance
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED NEWS RENDERER
# ══════════════════════════════════════════════════════════════════════════════

def _render_news_feed(news_items: list, title: str = "Market News", loading: bool = False):
    """
    Render a list of news items inside a styled card.
    Each item: {title, publisher, link, published}
    """
    st.markdown(f"<div class='kf-section-title'>{title}</div>", unsafe_allow_html=True)

    if loading:
        st.markdown(
            "<div class='kf-explain' style='color:#64748b;'>Loading headlines…</div>",
            unsafe_allow_html=True,
        )
        return

    if not news_items:
        st.markdown(
            "<div class='kf-explain' style='border-left-color:#475569;color:#64748b;'>"
            "No headlines available right now. Check back shortly."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    rows_html = ""
    for item in news_items:
        rows_html += f"""
        <div style="padding:.65rem 0;border-bottom:1px solid #1a1a28;">
            <a href="{item['link']}" target="_blank" rel="noopener noreferrer"
               style="color:#e2e8f0;font-size:.85rem;font-weight:500;text-decoration:none;
                      line-height:1.4;display:block;margin-bottom:.25rem;">
                {item['title']}
            </a>
            <div style="display:flex;gap:1rem;align-items:center;">
                <span style="color:#00d4aa;font-size:.72rem;font-weight:600;">
                    {item['publisher']}
                </span>
                <span style="color:#334155;font-size:.72rem;">
                    {item['published']}
                </span>
            </div>
        </div>
        """

    st.markdown(
        f'<div class="kf-card" style="padding:.5rem 1.25rem;">{rows_html}</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════════════════════════════════

page = st.session_state.page
if   page == "Screener":  page_screener()
elif page == "Analysis":  page_analysis()
elif page == "Portfolio": page_portfolio()
