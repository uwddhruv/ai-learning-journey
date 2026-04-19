"""
data_layer.py — Defensive data fetching from yfinance.
Treats missing data as expected, not exceptional.
"""

import os
import yfinance as yf
import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import warnings
warnings.filterwarnings("ignore")

# ── Stock Universe ────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def load_india_stocks() -> pd.DataFrame:
    """
    Load the curated Indian stock universe from the bundled CSV.
    Returns a DataFrame with columns: ticker, company, sector.
    Cached for 24 hours (data changes rarely).
    Falls back to a small hardcoded list if the CSV is unavailable.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "india_stocks.csv")
    try:
        df = pd.read_csv(csv_path, dtype=str).dropna(subset=["ticker", "company"])
        df["ticker"] = df["ticker"].str.strip()
        df["company"] = df["company"].str.strip()
        df["sector"] = df["sector"].fillna("Unknown").str.strip()
        return df.reset_index(drop=True)
    except Exception:
        # Minimal fallback
        fallback = [
            ("RELIANCE.NS", "Reliance Industries", "Energy"),
            ("TCS.NS", "Tata Consultancy Services", "Information Technology"),
            ("HDFCBANK.NS", "HDFC Bank", "Financial Services"),
            ("ICICIBANK.NS", "ICICI Bank", "Financial Services"),
            ("INFY.NS", "Infosys", "Information Technology"),
            ("SBIN.NS", "State Bank of India", "Financial Services"),
            ("BHARTIARTL.NS", "Bharti Airtel", "Telecom"),
            ("WIPRO.NS", "Wipro", "Information Technology"),
            ("TATAMOTORS.NS", "Tata Motors", "Automobile"),
            ("MARUTI.NS", "Maruti Suzuki India", "Automobile"),
        ]
        return pd.DataFrame(fallback, columns=["ticker", "company", "sector"])


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(ticker: str) -> Dict:
    """
    Fetch comprehensive stock fundamentals from yfinance.

    Implements defensive fetching: missing fields become None,
    never raise exceptions. Data quality is scored separately.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = _fetch_info_with_retries(stock)
        fast_info = _safe_fast_info(stock)

        def safe_get(key, default=None):
            val = info.get(key, fast_info.get(key, default))
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
        current_price = (
            safe_get("currentPrice")
            or safe_get("regularMarketPrice")
            or safe_get("previousClose")
            or safe_get("lastPrice")
            or safe_get("regularMarketPreviousClose")
        )

        # ── P&L ─────────────────────────────────────────────────
        eps = safe_get("trailingEps") or safe_get("forwardEps")
        revenue = safe_get("totalRevenue")
        net_income = safe_get("netIncomeToCommon")
        ebitda = safe_get("ebitda")

        # ── Balance Sheet ────────────────────────────────────────
        bvps = safe_get("bookValue")
        total_debt = safe_get("totalDebt", 0) or 0
        cash = safe_get("totalCash", 0) or 0
        shares = safe_get("sharesOutstanding") or safe_get("shares")

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
        ev_to_ebitda = safe_get("enterpriseToEbitda")
        div_yield = safe_get("dividendYield", 0) or 0
        target_price = safe_get("targetMeanPrice")
        analyst_count = int(safe_get("numberOfAnalystOpinions", 0) or 0)

        # ── Derived Fallbacks ────────────────────────────────────
        if current_price is None:
            current_price = _fallback_price_from_history(stock)
        if pe is None and current_price and eps and eps > 0:
            pe = current_price / eps
        if pb is None and current_price and bvps and bvps > 0:
            pb = current_price / bvps
        if ps is None and current_price and revenue and shares and shares > 0 and revenue > 0:
            ps = current_price / (revenue / shares)
        if ev is None and market_cap:
            ev = market_cap + total_debt - cash
        if ev_to_ebitda is None and ev and ebitda and ebitda > 0:
            ev_to_ebitda = ev / ebitda

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
            "ev_to_ebitda": ev_to_ebitda,
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


def fmt_large(n: Optional[float], prefix: str = "₹") -> str:
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
    return f"₹{n:,.2f}"


# ── News helpers ─────────────────────────────────────────────────────────────

def _parse_news_items(raw: list) -> List[Dict]:
    """Normalise yfinance news items into a consistent shape."""
    items = []
    for article in raw or []:
        try:
            content = article.get("content") or {}
            ts = (
                article.get("providerPublishTime")
                or article.get("pubDate")
                or article.get("publishedAt")
                or content.get("pubDate")
                or content.get("displayTime")
            )
            pub_dt = _format_publish_time(ts)
            items.append({
                "title":     article.get("title") or content.get("title") or "Untitled",
                "publisher": article.get("publisher") or content.get("provider", {}).get("displayName") or "Unknown",
                "link":      article.get("link") or article.get("canonicalUrl", {}).get("url") or content.get("clickThroughUrl", {}).get("url") or "#",
                "published": pub_dt,
            })
        except Exception:
            continue
    return items


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_news(limit: int = 10) -> List[Dict]:
    return fetch_market_news_state(limit=limit).get("items", [])


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_news_state(limit: int = 10) -> Dict:
    """
    Fetch recent broad-market headlines via yfinance (using ^NSEI as a market proxy).
    Cached for 15 minutes to stay within rate limits.
    Returns a list of dicts with title, publisher, link, published.
    """
    errors = []
    y_items = []
    for proxy in ("^NSEI", "^BSESN"):
        try:
            raw = _fetch_yfinance_news(proxy)
            y_items = _parse_news_items(raw)
            if y_items:
                return {
                    "items": y_items[:limit],
                    "state": "ok",
                    "source": f"Yahoo Finance ({proxy})",
                    "message": "",
                }
        except Exception as e:
            errors.append(f"{proxy}: {e}")

    rss_items = _fetch_google_news_rss("Indian stock market", limit)
    if rss_items:
        return {
            "items": rss_items[:limit],
            "state": "ok",
            "source": "Google News RSS",
            "message": "Primary provider unavailable, using fallback feed.",
        }

    msg = "No headlines available after trying primary and fallback providers."
    if errors:
        msg += " Please retry shortly."
    return {"items": [], "state": "empty", "source": "", "message": msg}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker_news(ticker: str, limit: int = 8) -> List[Dict]:
    return fetch_ticker_news_state(ticker=ticker, limit=limit).get("items", [])


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker_news_state(ticker: str, limit: int = 8) -> Dict:
    """
    Fetch recent news headlines scoped to *ticker*.
    Cached for 15 minutes to stay within rate limits.
    Returns a list of dicts with title, publisher, link, published.
    """
    symbol = ticker.upper()
    try:
        raw = _fetch_yfinance_news(symbol)
        items = _parse_news_items(raw)
        if items:
            return {"items": items[:limit], "state": "ok", "source": "Yahoo Finance", "message": ""}
    except Exception:
        pass

    rss_items = _fetch_google_news_rss(f"{symbol} NSE stock", limit)
    if rss_items:
        return {
            "items": rss_items[:limit],
            "state": "ok",
            "source": "Google News RSS",
            "message": "Using fallback news source.",
        }

    return {
        "items": [],
        "state": "empty",
        "source": "",
        "message": f"No recent headlines found for {symbol}.",
    }


def _fetch_info_with_retries(stock, retries: int = 3, delay: float = 0.6) -> Dict:
    """Fetch stock.info with lightweight retries to handle transient provider failures."""
    last_error = None
    for i in range(retries):
        try:
            info = stock.info or {}
            if info:
                return info
        except Exception as e:
            last_error = e
        if i < retries - 1:
            time.sleep(delay * (i + 1))
    if last_error:
        raise last_error
    return {}


def _safe_fast_info(stock) -> Dict:
    """Return stock.fast_info as a plain dict, or {} when unavailable."""
    try:
        fi = stock.fast_info or {}
        if hasattr(fi, "items"):
            return dict(fi.items())
        return dict(fi)
    except Exception:
        return {}


def _fallback_price_from_history(stock) -> Optional[float]:
    """Derive last close from recent history when quote endpoints return no live price."""
    try:
        h = stock.history(period="5d")
        if h.empty:
            return None
        close = h["Close"].dropna()
        if close.empty:
            return None
        return float(close.iloc[-1])
    except Exception:
        return None


def _fetch_yfinance_news(symbol: str, retries: int = 3, delay: float = 0.5) -> list:
    """Fetch Yahoo Finance news with retries; returns [] when no usable payload is found."""
    last_error = None
    for i in range(retries):
        try:
            news = yf.Ticker(symbol).news or []
            if news:
                return news
        except Exception as e:
            last_error = e
        if i < retries - 1:
            time.sleep(delay * (i + 1))
    if last_error:
        raise last_error
    return []


def _format_publish_time(raw_ts) -> str:
    """Normalize epoch/RFC/ISO-like timestamps into a UTC display string."""
    if raw_ts in (None, "", 0):
        return "—"
    try:
        if isinstance(raw_ts, (int, float)) or (isinstance(raw_ts, str) and raw_ts.isdigit()):
            dt = datetime.fromtimestamp(int(raw_ts), tz=timezone.utc)
        else:
            dt = parsedate_to_datetime(str(raw_ts))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%b %d, %Y  %H:%M UTC")
    except Exception:
        return "—"


def _fetch_google_news_rss(query: str, limit: int) -> List[Dict]:
    """Fetch Google News RSS search results and convert them into normalized news items."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    xml = _http_get_with_retries(url)
    if not xml:
        return []
    return _parse_rss_items(xml)[:limit]


def _http_get_with_retries(url: str, retries: int = 3, timeout: int = 6) -> str:
    """Perform GET with timeout + retries and return response text on success."""
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.ok and r.text:
                return r.text
        except Exception:
            pass
        if i < retries - 1:
            time.sleep(0.4 * (i + 1))
    return ""


def _parse_rss_items(xml_text: str) -> List[Dict]:
    """Parse RSS XML <item> nodes into {title, publisher, link, published} dictionaries."""
    items = []
    try:
        root = ET.fromstring(xml_text)
        for node in root.findall(".//item"):
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "#").strip()
            pub = (node.findtext("pubDate") or "").strip()
            source = "Google News"
            source_node = node.find("source")
            if source_node is not None and source_node.text:
                source = source_node.text.strip()
            if title:
                items.append({
                    "title": title,
                    "publisher": source,
                    "link": link,
                    "published": _format_publish_time(pub),
                })
    except Exception:
        return []
    return items
