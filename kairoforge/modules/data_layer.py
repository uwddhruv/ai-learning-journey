"""
data_layer.py — Defensive data fetching from yfinance.
Treats missing data as expected, not exceptional.
"""

import yfinance as yf
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings("ignore")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker: str) -> Dict:
    """
    Fetch comprehensive stock fundamentals from yfinance.

    Implements defensive fetching: missing fields become None,
    never raise exceptions. Data quality is scored separately.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info or {}

        def safe_get(key, default=None):
            val = info.get(key, default)
            if val is None:
                return default
            try:
                f = float(val)
                if np.isnan(f) or np.isinf(f):
                    return default
                return f
            except (TypeError, ValueError):
                return default

        # ── Price ───────────────────────────────────────────────
        current_price = safe_get("currentPrice") or safe_get("regularMarketPrice") or safe_get("previousClose")

        # ── P&L ─────────────────────────────────────────────────
        eps = safe_get("trailingEps") or safe_get("forwardEps")
        revenue = safe_get("totalRevenue")
        net_income = safe_get("netIncomeToCommon")
        ebitda = safe_get("ebitda")

        # ── Balance Sheet ────────────────────────────────────────
        bvps = safe_get("bookValue")
        total_debt = safe_get("totalDebt", 0) or 0
        cash = safe_get("totalCash", 0) or 0
        shares = safe_get("sharesOutstanding")

        # ── Cash Flow ────────────────────────────────────────────
        fcf = safe_get("freeCashflow")
        ocf = safe_get("operatingCashflow")

        # Derive FCF per share
        fcf_per_share = None
        if fcf and shares and shares > 0:
            fcf_per_share = fcf / shares
        elif ocf and shares and shares > 0:
            fcf_per_share = (ocf / shares) * 0.75  # conservative proxy

        # ── Valuation Ratios ─────────────────────────────────────
        pe = safe_get("trailingPE") or safe_get("forwardPE")
        pb = safe_get("priceToBook")
        ps = safe_get("priceToSalesTrailing12Months")
        peg = safe_get("pegRatio")

        # ── Quality Metrics ──────────────────────────────────────
        roe = safe_get("returnOnEquity")
        roa = safe_get("returnOnAssets")
        profit_margin = safe_get("profitMargins")
        gross_margin = safe_get("grossMargins")
        op_margin = safe_get("operatingMargins")

        # ── Growth ───────────────────────────────────────────────
        rev_growth = safe_get("revenueGrowth")
        earn_growth = safe_get("earningsGrowth") or safe_get("earningsQuarterlyGrowth")

        # ── Other ────────────────────────────────────────────────
        beta = safe_get("beta", 1.0) or 1.0
        market_cap = safe_get("marketCap")
        ev = safe_get("enterpriseValue")
        div_yield = safe_get("dividendYield", 0) or 0
        target_price = safe_get("targetMeanPrice")
        analyst_count = int(safe_get("numberOfAnalystOpinions", 0) or 0)

        # ── Metadata ─────────────────────────────────────────────
        company_name = info.get("longName") or info.get("shortName") or ticker
        sector = info.get("sector", "Unknown") or "Unknown"
        industry = info.get("industry", "Unknown") or "Unknown"
        description = info.get("longBusinessSummary", "")

        # ── Derived Growth Estimate ──────────────────────────────
        estimated_growth = _estimate_growth_rate(rev_growth, earn_growth, roe, pe, peg)

        # ── Data Quality Score ───────────────────────────────────
        data_quality = _score_data_quality(
            eps=eps, bvps=bvps, fcf=fcf,
            roe=roe, pe=pe, shares=shares,
            current_price=current_price
        )

        return {
            "ticker": ticker.upper(),
            "company_name": company_name,
            "sector": sector,
            "industry": industry,
            "description": description,
            "current_price": current_price,
            "eps": eps,
            "book_value_per_share": bvps,
            "revenue": revenue,
            "net_income": net_income,
            "ebitda": ebitda,
            "free_cashflow": fcf,
            "operating_cashflow": ocf,
            "fcf_per_share": fcf_per_share,
            "total_debt": total_debt,
            "cash": cash,
            "shares_outstanding": shares,
            "market_cap": market_cap,
            "enterprise_value": ev,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "ps_ratio": ps,
            "peg_ratio": peg,
            "roe": roe,
            "roa": roa,
            "profit_margin": profit_margin,
            "gross_margin": gross_margin,
            "operating_margin": op_margin,
            "revenue_growth": rev_growth,
            "earnings_growth": earn_growth,
            "estimated_growth_rate": estimated_growth,
            "beta": beta,
            "dividend_yield": div_yield,
            "target_price": target_price,
            "analyst_count": analyst_count,
            "data_quality": data_quality,
            "error": None,
        }

    except Exception as e:
        return {
            "ticker": ticker.upper(),
            "company_name": ticker.upper(),
            "error": str(e),
            "data_quality": 0.0,
            "current_price": None,
            "sector": "Unknown",
        }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_history(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Return OHLCV history or empty DataFrame on failure."""
    try:
        hist = yf.Ticker(ticker.upper()).history(period=period)
        return hist if not hist.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ── Internal helpers ─────────────────────────────────────────────────────────

def _estimate_growth_rate(rev_growth, earn_growth, roe, pe, peg) -> float:
    """
    Synthesize a credible near-term growth rate from available signals.
    Applies sanity bounds: -5% to 30%.
    """
    candidates = []

    if earn_growth and -0.5 < earn_growth < 1.0:
        candidates.append(earn_growth)
    if rev_growth and -0.3 < rev_growth < 0.8:
        candidates.append(rev_growth * 0.85)

    # PEG-implied growth
    if pe and peg and peg > 0:
        implied = pe / peg / 100
        if 0 < implied < 0.5:
            candidates.append(implied)

    # Sustainable growth rate from ROE
    if roe and 0 < roe < 0.5:
        candidates.append(roe * 0.65)  # assume 65% retention

    if candidates:
        rate = float(np.median(candidates))
    else:
        rate = 0.07  # neutral default

    return round(max(-0.05, min(0.30, rate)), 4)


def _score_data_quality(eps, bvps, fcf, roe, pe, shares, current_price) -> float:
    """
    Returns 0-1 score reflecting how complete and reliable the data is.
    Used to discount valuations derived from sparse inputs.
    """
    weights = {
        "current_price": (current_price, 0.20),
        "eps":           (eps,           0.20),
        "bvps":          (bvps,          0.15),
        "fcf":           (fcf,           0.20),
        "roe":           (roe,           0.15),
        "pe":            (pe,            0.10),
    }
    score = sum(w for _, (v, w) in weights.items() if v is not None and v != 0)
    return round(score, 3)


def fmt_large(n: Optional[float], prefix: str = "$") -> str:
    """Format large numbers: 1.23T, 456.7B, etc."""
    if n is None:
        return "N/A"
    abs_n = abs(n)
    if abs_n >= 1e12:
        return f"{prefix}{n/1e12:.2f}T"
    elif abs_n >= 1e9:
        return f"{prefix}{n/1e9:.2f}B"
    elif abs_n >= 1e6:
        return f"{prefix}{n/1e6:.2f}M"
    else:
        return f"{prefix}{n:,.0f}"


def fmt_pct(n: Optional[float]) -> str:
    if n is None:
        return "N/A"
    return f"{n*100:.1f}%"


def fmt_price(n: Optional[float]) -> str:
    if n is None:
        return "N/A"
    return f"${n:,.2f}"


# ── News helpers ─────────────────────────────────────────────────────────────

def _parse_news_items(raw: list) -> List[Dict]:
    """Normalise yfinance news items into a consistent shape."""
    items = []
    for article in raw or []:
        try:
            ts = article.get("providerPublishTime") or article.get("pubDate")
            if ts:
                pub_dt = datetime.utcfromtimestamp(int(ts)).strftime("%b %d, %Y  %H:%M UTC")
            else:
                pub_dt = "—"
            items.append({
                "title":     article.get("title", "Untitled"),
                "publisher": article.get("publisher", "Unknown"),
                "link":      article.get("link", "#"),
                "published": pub_dt,
            })
        except Exception:
            continue
    return items


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_news(limit: int = 10) -> List[Dict]:
    """
    Fetch recent broad-market headlines via yfinance (using SPY as a market proxy).
    Cached for 15 minutes to stay within rate limits.
    Returns a list of dicts with title, publisher, link, published.
    """
    try:
        raw = yf.Ticker("SPY").news or []
        if not raw:
            # Fallback to a second broad-market proxy
            raw = yf.Ticker("^GSPC").news or []
        return _parse_news_items(raw)[:limit]
    except Exception:
        return []


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker_news(ticker: str, limit: int = 8) -> List[Dict]:
    """
    Fetch recent news headlines scoped to *ticker*.
    Cached for 15 minutes to stay within rate limits.
    Returns a list of dicts with title, publisher, link, published.
    """
    try:
        raw = yf.Ticker(ticker.upper()).news or []
        return _parse_news_items(raw)[:limit]
    except Exception:
        return []
