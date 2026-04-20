"""
KAIROFORGE — Stock Analysis Terminal
A lightweight stock analysis platform.

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
import html
import re
from urllib.parse import urlparse
import numpy as np
import plotly.graph_objects as go
from typing import List, Dict, Tuple
from collections import Counter

from modules.data_layer import (
    fetch_stock_data, fetch_price_history, fetch_ticker_news_state,
    fmt_large, fmt_pct, fmt_price, load_india_stocks,
)
from modules.valuation_engine import calculate_dcf, calculate_graham, get_relative_valuation
from modules.scoring_engine import compute_score
from modules.styles import inject_styles

# ── INJECT STYLES ─────────────────────────────────────────────────────────────
st.markdown(inject_styles(), unsafe_allow_html=True)

# ── STOCK UNIVERSE ─────────────────────────────────────────────────────────────
_stocks_df = load_india_stocks()
# Build display labels: "Company Name (TICKER)"
_TICKER_TO_LABEL = {
    row["ticker"]: f"{row['company']}  ({row['ticker']})"
    for _, row in _stocks_df.iterrows()
}
_LABEL_TO_TICKER = {v: k for k, v in _TICKER_TO_LABEL.items()}
_ALL_LABELS      = sorted(_TICKER_TO_LABEL.values())

PLOTLY_DARK = dict(
    paper_bgcolor="#0a0a0f",
    plot_bgcolor="#0d0d16",
    font=dict(color="#94a3b8", family="Inter, sans-serif"),
    xaxis=dict(gridcolor="#1e1e2e", showline=False, zeroline=False),
    yaxis=dict(gridcolor="#1e1e2e", showline=False, zeroline=False),
    margin=dict(l=10, r=10, t=30, b=10),
)

NEWS_POSITIVE_TERMS = (
    "beats", "surge", "rise", "gain", "growth", "bull", "record", "up"
)
NEWS_NEGATIVE_TERMS = (
    "miss", "fall", "drop", "decline", "cuts", "down", "warn", "loss"
)
NEWS_THEME_KEYWORD_MAP = {
    "Earnings": ("earnings", "profit", "results", "revenue", "quarter"),
    "Regulation": ("rbi", "sebi", "regulation", "policy", "approval"),
    "Deals": ("acquisition", "deal", "merger", "stake", "buyout"),
    "Market Move": ("target", "upgrade", "downgrade", "rating", "outlook"),
    "Operations": ("plant", "capacity", "expansion", "order", "contract"),
}

PROVIDED_LOGO_URL = os.getenv(
    "KAIROFORGE_LOGO_URL",
    "https://github.com/user-attachments/assets/31e5cbee-9a99-4fe1-89dd-bf7e4d1dd30b",
)
def resolve_logo_src() -> str:
    """Resolve logo source with URL-first strategy and local fallback."""
    if PROVIDED_LOGO_URL and PROVIDED_LOGO_URL.strip():
        return PROVIDED_LOGO_URL.strip()
    _local_logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(_local_logo_path):
        try:
            with open(_local_logo_path, "rb") as _f:
                return f"data:image/png;base64,{base64.b64encode(_f.read()).decode()}"
        except Exception:
            return ""
    return ""


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "page"      not in st.session_state: st.session_state.page      = "Landing"
if "selected"  not in st.session_state: st.session_state.selected  = ""


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # ── LOGO ──────────────────────────────────────────────────────────────
    try:
        _logo_src = resolve_logo_src()
        if _logo_src:
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:.75rem;
                            padding:.5rem 0 .75rem 0;margin-bottom:.25rem;">
                    <img src="{_logo_src}"
                         width="52" height="52"
                         style="border-radius:12px;flex-shrink:0;
                                box-shadow:0 2px 8px rgba(0,212,170,0.25);object-fit:cover;"
                         alt="KAIROFORGE logo"/>
                    <div>
                        <div class="kf-header-logo" style="font-size:1.15rem;
                             line-height:1.2;">KAIROFORGE</div>
                        <div class="kf-header-sub" style="font-size:0.7rem;">
                            Stock Analysis Terminal
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            raise ValueError(
                "Logo could not be loaded: neither KAIROFORGE_LOGO_URL nor local logo.png are available"
            )
    except Exception:
        st.markdown(
            """
            <div style="padding:.5rem 0 .75rem 0;margin-bottom:.25rem;">
                <div class="kf-header-logo">⚡ KAIROFORGE</div>
                <div class="kf-header-sub">Stock Analysis Terminal</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='border-color:#1e1e2e;margin:.75rem 0;'>", unsafe_allow_html=True)

    nav_choice = st.radio(
        "Navigate",
        ["🏠  Landing", "🔍  Stock Analysis"],
        index=0 if st.session_state.page == "Landing"
              else 1,
        label_visibility="hidden",
    )
    st.session_state.page = (
        "Landing"  if "Landing"  in nav_choice else
        "Analysis"
    )

    st.markdown("<hr style='border-color:#1e1e2e;margin:.75rem 0;'>", unsafe_allow_html=True)

    # ── SEARCHABLE STOCK SELECTOR ─────────────────────────────────────────
    st.markdown(
        "<div style='font-size:0.72rem;color:#64748b;font-weight:600;"
        "text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem;'>"
        "Search &amp; Analyse Stock</div>",
        unsafe_allow_html=True,
    )

    _cur_ticker  = st.session_state.selected
    _cur_label   = _TICKER_TO_LABEL.get(_cur_ticker, "")
    _placeholder = ["— choose a stock —"] + _ALL_LABELS
    _select_idx  = (_placeholder.index(_cur_label)
                    if _cur_label in _placeholder else 0)

    _jump_label = st.selectbox(
        "Search by company or ticker",
        options=_placeholder,
        index=_select_idx,
        label_visibility="collapsed",
        key="sidebar_stock_select",
    )

    if st.button("Analyse  →", use_container_width=True):
        if _jump_label and _jump_label != "— choose a stock —":
            st.session_state.selected = _LABEL_TO_TICKER.get(_jump_label, "")
            st.session_state.page     = "Analysis"
            st.rerun()

    st.markdown("<hr style='border-color:#1e1e2e;margin:.75rem 0;'>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.7rem;color:#334155;line-height:1.6;'>"
        f"📈 {len(_stocks_df):,} Indian stocks covered<br>"
        f"Data via yfinance · Refreshes hourly</div>",
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
    try:
        score = float(score)
        if not np.isfinite(score):
            score = 0.0
    except (TypeError, ValueError):
        score = 0.0
    # Gauge is defined on a bounded 0–100 scale.
    score = max(0.0, min(100.0, score))

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
#  PAGE: LANDING
# ══════════════════════════════════════════════════════════════════════════════

def page_landing():
    _landing_logo_src = resolve_logo_src()
    _landing_logo_html = (
        f'<img src="{_landing_logo_src}" class="kf-landing-logo" alt="KAIROFORGE logo" />'
        if _landing_logo_src else ""
    )
    st.markdown(
        f"""
        <section class="kf-landing-hero">
            {_landing_logo_html}
            <div class="kf-landing-kicker">India-Focused Equity Intelligence</div>
            <h1>KAIROFORGE Terminal</h1>
            <p>
                Search any stock from a {len(_stocks_df):,}+ coverage universe, open deep valuation analysis,
                and move from signal to decision with a modern research workflow.
            </p>
            <a class="kf-landing-scroll" href="#kf-scroll-target" aria-label="Scroll down to features section">Scroll down ↓</a>
        </section>
        """,
        unsafe_allow_html=True,
    )

    _cur_ticker = st.session_state.selected
    _cur_label = _TICKER_TO_LABEL.get(_cur_ticker, "")
    _options_with_placeholder = ["— choose a stock —"] + _ALL_LABELS
    _select_idx = (
        _options_with_placeholder.index(_cur_label)
        if _cur_label in _options_with_placeholder
        else 0
    )

    c1, c2, c3 = st.columns([1.1, 2.8, 1.1])
    with c2:
        st.markdown("<div class='kf-landing-search-title'>Search Stocks</div>", unsafe_allow_html=True)
        with st.form("landing_stock_search"):
            _jump_label = st.selectbox(
                "Search by company or ticker",
                options=_options_with_placeholder,
                index=_select_idx,
                key="landing_stock_select",
                label_visibility="collapsed",
            )
            _analyse_now = st.form_submit_button("Analyse Stock", use_container_width=True)
        if _analyse_now and _jump_label and _jump_label != "— choose a stock —":
            st.session_state.selected = _LABEL_TO_TICKER.get(_jump_label, "")
            st.session_state.page = "Analysis"
            st.rerun()

    st.markdown(
        """
        <section id="kf-scroll-target" role="region" aria-label="KairoForge feature overview">
            <div class="kf-landing-grid">
                <div class="kf-landing-card">
                    <h3>🔍 Deep Analysis</h3>
                    <p>Open detailed valuation, score breakdown, risk factors, and chart context instantly.</p>
                </div>
                <div class="kf-landing-card">
                    <h3>🧮 Intrinsic Value Models</h3>
                    <p>Use DCF, Graham, and relative valuation outputs with confidence-aware scoring.</p>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Stocks Covered", f"{len(_stocks_df):,}+")
    cc2.metric("Active Mode", st.session_state.page)
    cc3.metric("Data Refresh", "Hourly")
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
                    Search and select a stock from the sidebar to begin analysis.
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

    # ── ANALYST PRICE TARGET PANEL ──────────────────────────────────────────
    _render_price_target_panel(data)

    # ── TICKER NEWS ─────────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)
    ticker_news_state = fetch_ticker_news_state(ticker, limit=8)
    _render_news_feed(
        ticker_news_state.get("items", []),
        title=f"📰 {ticker} News",
        loading=False,
        state=ticker_news_state.get("state", "ok"),
        message=ticker_news_state.get("message", ""),
        source=ticker_news_state.get("source", ""),
    )

    _render_footer()


def _render_key_metrics(data: Dict):
    """Render a clean metrics grid."""
    def ratio(v: float, suffix: str = "x", digits: int = 2) -> str:
        if v is None:
            return "N/A"
        return f"{v:.{digits}f}{suffix}"

    st.markdown("<div class='kf-section-title'>Valuation Ratios</div>", unsafe_allow_html=True)
    m = [
        ("P/E Ratio",    ratio(data.get("pe_ratio")),
         "Price to trailing earnings"),
        ("P/B Ratio",    ratio(data.get("pb_ratio")),
         "Price to book value"),
        ("P/S Ratio",    ratio(data.get("ps_ratio")),
         "Price to sales"),
        ("PEG Ratio",    ratio(data.get("peg_ratio"), suffix="", digits=2),
         "P/E to growth — < 1 is attractive"),
        ("EV/EBITDA",    ratio(data.get("ev_to_ebitda")),
         "Enterprise value to EBITDA"),
        ("EV",           fmt_large(data.get("enterprise_value")),
         "Enterprise value"),
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
    framework = sc.get("framework", {})
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

    # Framework valuation rater
    if framework:
        st.markdown("<div class='kf-section-title' style='margin-top:1.25rem;'>Framework Valuation Rater</div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="kf-card" style="padding:1rem 1.1rem;">
                <div style="display:flex;gap:1rem;align-items:center;flex-wrap:wrap;">
                    <div style="color:#94a3b8;font-size:.78rem;">Rating</div>
                    <div style="color:#f1f5f9;font-size:1.15rem;font-weight:700;
                                font-family:'JetBrains Mono',monospace;">
                        {framework.get("rating", "N/A")}
                    </div>
                    <div style="color:#00d4aa;font-size:.86rem;font-weight:600;">
                        {framework.get("label", "—")}
                    </div>
                </div>
                <div style="margin-top:.55rem;color:#94a3b8;font-size:.78rem;line-height:1.5;">
                    {framework.get("explanation", "")}
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
    if not sc:
        st.warning("Score intelligence is temporarily unavailable for this symbol.")
        return

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
    else:
        st.markdown(
            "<div class='kf-explain' style='border-left-color:#475569;color:#94a3b8;'>"
            "Insufficient valuation inputs to render full score breakdown."
            "</div>",
            unsafe_allow_html=True,
        )

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
        "ev_to_ebitda": ("EV/EBITDA", f'{rel.get("ev_to_ebitda"):.2f}x' if rel.get("ev_to_ebitda") else "N/A",
                         rel.get("ev_ebitda_signal"), f'Sector median: {rel.get("benchmark_ev_ebitda",12):.1f}x'),
    }

    sig_label = {
        "cheap": "✅ Cheap", "fair": "◆ Fair", "slightly_rich": "⚠️ Rich",
        "expensive": "🔴 Expensive", "deep_value": "✅ Deep Value",
        "growth_premium": "◆ Growth Premium", "undervalued": "✅ Undervalued",
        "overvalued": "⚠️ Overvalued", "very_overvalued": "🔴 Very Overvalued", None: "—",
    }

    rows_html = ""
    for key, (label, val_str, signal, note) in label_map.items():
        safe_label = html.escape(str(label), quote=True)
        safe_val = html.escape(str(val_str), quote=True)
        safe_note = html.escape(str(note), quote=True)
        sig_disp = html.escape(str(sig_label.get(signal, "—")), quote=True)
        rows_html += f"""
        <div style="display:flex;gap:1.5rem;padding:.75rem 0;border-bottom:1px solid #1a1a28;
                    align-items:center;">
            <div style="width:100px;color:#94a3b8;font-size:.8rem;">{safe_label}</div>
            <div style="width:80px;color:#f1f5f9;font-weight:600;font-family:'JetBrains Mono',mono;">{safe_val}</div>
            <div style="width:160px;color:#e2e8f0;font-size:.8rem;">{sig_disp}</div>
            <div style="flex:1;color:#475569;font-size:.75rem;">{safe_note}</div>
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

def _render_news_feed(
    news_items: list,
    title: str = "Market News",
    loading: bool = False,
    state: str = "ok",
    message: str = "",
    source: str = "",
):
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

    if message:
        st.markdown(
            f"<div style='color:#64748b;font-size:.72rem;margin:-.4rem 0 .65rem 0;'>{message}</div>",
            unsafe_allow_html=True,
        )

    if source:
        st.markdown(
            f"<div style='color:#475569;font-size:.68rem;margin:-.25rem 0 .65rem 0;'>Source: {source}</div>",
            unsafe_allow_html=True,
        )

    if not news_items:
        st.markdown(
            "<div class='kf-explain' style='border-left-color:#475569;color:#64748b;'>"
            "No headlines available right now after checking all configured providers."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    _render_news_summary(news_items)

    rows_html = ""
    for item in news_items:
        title = html.escape(str(item.get("title", "Untitled")), quote=True)
        publisher = html.escape(str(item.get("publisher", "Unknown")), quote=True)
        published = html.escape(str(item.get("published", "—")), quote=True)
        link = str(item.get("link", "#")).strip()
        parsed_link = urlparse(link)
        if parsed_link.scheme.lower() not in ("http", "https"):
            link = "#"
            source_link = "#"
        else:
            source_link = f"{parsed_link.scheme}://{parsed_link.netloc}"
        link = html.escape(link, quote=True)
        source_link = html.escape(source_link, quote=True)
        rows_html += f"""
        <div style="padding:.65rem 0;border-bottom:1px solid #1a1a28;">
            <a href="{link}" target="_blank" rel="noopener noreferrer"
               style="color:#e2e8f0;font-size:.85rem;font-weight:500;text-decoration:none;
                        line-height:1.4;display:block;margin-bottom:.25rem;">
                {title}
            </a>
            <div style="display:flex;gap:1rem;align-items:center;">
                <a href="{source_link}" target="_blank" rel="noopener noreferrer"
                   style="color:#00d4aa;font-size:.72rem;font-weight:600;text-decoration:none;">
                    {publisher}
                </a>
                <span style="color:#334155;font-size:.72rem;">
                    {published}
                </span>
            </div>
        </div>
        """

    st.markdown(
        f'<div class="kf-card" style="padding:.5rem 1.25rem;">{rows_html}</div>',
        unsafe_allow_html=True,
    )


def _render_news_summary(news_items: list):
    """Render a compact summary panel for the current stock news set."""
    sentiment = _news_sentiment_label(news_items)
    themes = _news_themes(news_items)
    source_links = _news_sources(news_items)

    summary_parts = [
        f"Overall headline tone looks <b>{sentiment}</b> based on the latest coverage."
    ]
    if themes:
        summary_parts.append("Main themes: " + ", ".join(themes) + ".")
    summary_text = " ".join(summary_parts)

    sources_html = ""
    if source_links:
        chips = []
        for name, link in source_links:
            chips.append(
                f"<a href='{html.escape(link, quote=True)}' target='_blank' rel='noopener noreferrer' "
                f"style='color:#00d4aa;text-decoration:none;font-size:.72rem;'>"
                f"{html.escape(name, quote=True)}</a>"
            )
        sources_html = (
            "<div style='margin-top:.5rem;color:#64748b;font-size:.72rem;'>"
            "Sources: " + " · ".join(chips) + "</div>"
        )

    st.markdown(
        "<div class='kf-card' style='padding:.75rem 1rem;margin-bottom:.65rem;'>"
        "<div style='color:#cbd5e1;font-size:.82rem;line-height:1.55;'>"
        f"{summary_text}</div>{sources_html}</div>",
        unsafe_allow_html=True,
    )


def _news_sentiment_label(news_items: list) -> str:
    score = 0
    for item in news_items:
        text = str(item.get("title", "")).lower()
        score += sum(1 for term in NEWS_POSITIVE_TERMS if _contains_whole_word(text, term))
        score -= sum(1 for term in NEWS_NEGATIVE_TERMS if _contains_whole_word(text, term))
    if score > 0:
        return "positive"
    if score < 0:
        return "cautious"
    return "neutral"


def _news_themes(news_items: list, top_n: int = 3) -> List[str]:
    counts = Counter()
    for item in news_items:
        text = str(item.get("title", "")).lower()
        for theme, terms in NEWS_THEME_KEYWORD_MAP.items():
            if any(_contains_whole_word(text, term) for term in terms):
                counts[theme] += 1
    return [theme for theme, _ in counts.most_common(top_n)]


def _news_sources(news_items: list, top_n: int = 5) -> List[Tuple[str, str]]:
    seen = set()
    sources = []
    for item in news_items:
        publisher = str(item.get("publisher", "Unknown")).strip() or "Unknown"
        link = str(item.get("link", "#")).strip()
        parsed = urlparse(link)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            continue
        source_url = f"{parsed.scheme}://{parsed.netloc}"
        key = (publisher.lower(), source_url)
        if key in seen:
            continue
        seen.add(key)
        sources.append((publisher, source_url))
        if len(sources) >= top_n:
            break
    return sources


def _contains_whole_word(text: str, term: str) -> bool:
    """Return True when term appears as a whole word/phrase in text."""
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════════════════════════════════

page = st.session_state.page
if   page == "Landing":   page_landing()
elif page == "Analysis":  page_analysis()
