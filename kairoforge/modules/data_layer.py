"""
data_layer.py — Defensive data fetching from yfinance.
Treats missing data as expected, not exceptional.
"""

import os
import re
import unicodedata
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

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
}

MARKET_NEWS_KEEP_TERMS = (
    "india", "indian", "nifty", "sensex", "nse", "bse", "rupee",
    "rbi", "sebi", "market", "stocks", "equity", "shares",
)

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

        def safe_get_any(*keys, default=None):
            for key in keys:
                val = info.get(key, fast_info.get(key, None))
                num = _to_number(val, default=None)
                if num is not None:
                    return num
            return default

        # ── Price ───────────────────────────────────────────────
        current_price = (
            safe_get_any("currentPrice", "current_price")
            or safe_get_any("regularMarketPrice", "regular_market_price")
            or safe_get_any("lastPrice", "last_price")
            or safe_get_any("previousClose", "previous_close")
            or safe_get_any("regularMarketPreviousClose", "regular_market_previous_close")
        )

        # ── P&L ─────────────────────────────────────────────────
        eps = safe_get_any("trailingEps", "trailing_eps") or safe_get_any("forwardEps", "forward_eps")
        revenue = safe_get_any("totalRevenue", "total_revenue")
        net_income = safe_get_any("netIncomeToCommon", "net_income_to_common")
        ebitda = safe_get_any("ebitda")

        # ── Balance Sheet ────────────────────────────────────────
        bvps = safe_get_any("bookValue", "book_value")
        total_debt = safe_get_any("totalDebt", "total_debt", default=0) or 0
        cash = safe_get_any("totalCash", "total_cash", default=0) or 0
        shares = safe_get_any("sharesOutstanding", "shares_outstanding") or safe_get_any("shares")

        # ── Cash Flow ────────────────────────────────────────────
        fcf = safe_get_any("freeCashflow", "free_cashflow")
        ocf = safe_get_any("operatingCashflow", "operating_cashflow")

        # Derive FCF per share
        fcf_per_share = None
        if fcf and shares and shares > 0:
            fcf_per_share = fcf / shares
        elif ocf and shares and shares > 0:
            fcf_per_share = (ocf / shares) * 0.75  # conservative proxy

        # ── Valuation Ratios ─────────────────────────────────────
        pe = safe_get_any("trailingPE", "trailing_pe") or safe_get_any("forwardPE", "forward_pe")
        pb = safe_get_any("priceToBook", "price_to_book")
        ps = safe_get_any("priceToSalesTrailing12Months", "price_to_sales_trailing_12_months")
        peg = safe_get_any("pegRatio", "peg_ratio")

        # ── Quality Metrics ──────────────────────────────────────
        roe = safe_get_any("returnOnEquity", "return_on_equity")
        roa = safe_get_any("returnOnAssets", "return_on_assets")
        profit_margin = safe_get_any("profitMargins", "profit_margins")
        gross_margin = safe_get_any("grossMargins", "gross_margins")
        op_margin = safe_get_any("operatingMargins", "operating_margins")

        # ── Growth ───────────────────────────────────────────────
        rev_growth = safe_get_any("revenueGrowth", "revenue_growth")
        earn_growth = safe_get_any("earningsGrowth", "earnings_growth") or safe_get_any("earningsQuarterlyGrowth", "earnings_quarterly_growth")

        # ── Other ────────────────────────────────────────────────
        beta = safe_get_any("beta", default=1.0) or 1.0
        market_cap = safe_get_any("marketCap", "market_cap")
        ev = safe_get_any("enterpriseValue", "enterprise_value")
        ev_to_ebitda = safe_get_any("enterpriseToEbitda", "enterprise_to_ebitda")
        div_yield = safe_get_any("dividendYield", "dividend_yield", default=0) or 0
        target_price = safe_get_any("targetMeanPrice", "target_mean_price")
        analyst_count = int(safe_get_any("numberOfAnalystOpinions", "number_of_analyst_opinions", default=0) or 0)

        # ── Statement fallbacks (when quote-summary fields are sparse) ───────
        stmt = _fallback_from_financial_statements(stock)
        revenue = revenue or stmt.get("revenue")
        net_income = net_income or stmt.get("net_income")
        ebitda = ebitda or stmt.get("ebitda")
        total_debt = total_debt or stmt.get("total_debt", 0)
        cash = cash or stmt.get("cash", 0)
        shares = shares or stmt.get("shares")
        fcf = fcf or stmt.get("free_cashflow")
        ocf = ocf or stmt.get("operating_cashflow")
        bvps = bvps or stmt.get("book_value_per_share")
        roe = roe or stmt.get("roe")
        roa = roa or stmt.get("roa")
        profit_margin = profit_margin or stmt.get("profit_margin")
        gross_margin = gross_margin or stmt.get("gross_margin")
        op_margin = op_margin or stmt.get("operating_margin")

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
            title = _clean_news_text(article.get("title") or content.get("title"))
            publisher = _clean_news_text(
                article.get("publisher") or content.get("provider", {}).get("displayName")
            ) or "Unknown"
            if not _has_visible_news_text(title):
                continue
            items.append({
                "title": title,
                "publisher": publisher,
                "link": _extract_news_link(article, content),
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
            y_items = _filter_market_relevant_news(_parse_news_items(raw))
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

    clean_symbol = symbol.replace(".NS", "").replace(".BO", "")
    rss_items = _fetch_google_news_rss(f"{clean_symbol} NSE stock India", limit)
    if not rss_items and clean_symbol != symbol:
        rss_items = _fetch_google_news_rss(f"{clean_symbol} stock news", limit)
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
            raw = str(raw_ts).strip()
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                try:
                    dt = parsedate_to_datetime(raw)
                except Exception:
                    return "—"
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
            r = requests.get(url, timeout=timeout, headers=HTTP_HEADERS)
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
            title = _clean_news_text(node.findtext("title"))
            link = (node.findtext("link") or "#").strip()
            pub = (node.findtext("pubDate") or "").strip()
            source = "Google News"
            source_node = node.find("source")
            if source_node is not None and source_node.text:
                source = _clean_news_text(source_node.text) or "Google News"
            if _has_visible_news_text(title):
                items.append({
                    "title": title,
                    "publisher": source,
                    "link": link,
                    "published": _format_publish_time(pub),
                })
    except Exception:
        return []
    return items


def _to_number(val, default=None) -> Optional[float]:
    """
    Convert mixed-value payloads into finite float.

    Args:
        val: Scalar number/string, or dict payload containing `raw`/`value` fields.
        default: Fallback value returned when conversion fails or value is non-finite.
    """
    if isinstance(val, dict):
        val = val.get("raw", val.get("value"))
    if val is None:
        return default
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _fallback_from_financial_statements(stock) -> Dict:
    """Extract common metrics from yfinance statement tables when info fields are missing."""
    try:
        income = getattr(stock, "income_stmt", None)
    except Exception:
        income = None
    try:
        balance = getattr(stock, "balance_sheet", None)
    except Exception:
        balance = None
    try:
        cashflow = getattr(stock, "cashflow", None)
    except Exception:
        cashflow = None

    income_idx = _statement_index_map(income)
    balance_idx = _statement_index_map(balance)
    cashflow_idx = _statement_index_map(cashflow)

    revenue = _statement_value(income, ["Total Revenue", "Revenue", "Operating Revenue"], index_map=income_idx)
    net_income = _statement_value(income, ["Net Income", "Net Income Common Stockholders", "NetIncome"], index_map=income_idx)
    ebitda = _statement_value(income, ["EBITDA"], index_map=income_idx)
    gross_profit = _statement_value(income, ["Gross Profit"], index_map=income_idx)
    op_income = _statement_value(income, ["Operating Income"], index_map=income_idx)

    total_debt = _statement_value(balance, ["Total Debt", "Long Term Debt", "Current Debt"], index_map=balance_idx)
    cash = _statement_value(balance, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash"], index_map=balance_idx)
    equity = _statement_value(balance, ["Stockholders Equity", "Total Stockholder Equity", "Total Equity Gross Minority Interest"], index_map=balance_idx)
    assets = _statement_value(balance, ["Total Assets"], index_map=balance_idx)
    shares = _statement_value(balance, ["Ordinary Shares Number", "Share Issued"], index_map=balance_idx)

    fcf = _statement_value(cashflow, ["Free Cash Flow"], index_map=cashflow_idx)
    ocf = _statement_value(cashflow, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], index_map=cashflow_idx)

    bvps = None
    if equity and shares and shares > 0:
        bvps = equity / shares

    profit_margin = (net_income / revenue) if (net_income is not None and revenue and revenue > 0) else None
    gross_margin = (gross_profit / revenue) if (gross_profit is not None and revenue and revenue > 0) else None
    operating_margin = (op_income / revenue) if (op_income is not None and revenue and revenue > 0) else None
    roe = (net_income / equity) if (net_income is not None and equity and equity > 0) else None
    roa = (net_income / assets) if (net_income is not None and assets and assets > 0) else None

    return {
        "revenue": revenue,
        "net_income": net_income,
        "ebitda": ebitda,
        "total_debt": total_debt,
        "cash": cash,
        "shares": shares,
        "free_cashflow": fcf,
        "operating_cashflow": ocf,
        "book_value_per_share": bvps,
        "profit_margin": profit_margin,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "roe": roe,
        "roa": roa,
    }


def _statement_index_map(df: Optional[pd.DataFrame]) -> Dict[str, str]:
    """Create case-insensitive index map: lowercase label -> original DataFrame index label."""
    if df is None or getattr(df, "empty", True) or not isinstance(df.index, pd.Index):
        return {}
    return {str(idx).strip().lower(): idx for idx in df.index}


def _statement_value(df: Optional[pd.DataFrame], labels: List[str], index_map: Optional[Dict[str, str]] = None) -> Optional[float]:
    """
    Return latest non-null value for the first matching statement row label.

    Args:
        df: Financial statement DataFrame with metrics on index and periods on columns.
        labels: Candidate row labels in priority order (first match wins).
        index_map: Optional precomputed lowercase index map for repeated lookups.
    """
    if df is None or getattr(df, "empty", True):
        return None
    if not isinstance(df.index, pd.Index):
        return None

    index_map = index_map or _statement_index_map(df)
    for label in labels:
        key = label.strip().lower()
        if key in index_map:
            row = df.loc[index_map[key]]
            if isinstance(row, pd.Series):
                vals = row.dropna()
                if not vals.empty:
                    return _to_number(vals.iloc[0], default=None)
            return _to_number(row, default=None)
    return None


def _extract_news_link(article: Dict, content: Dict) -> str:
    """Resolve a usable headline URL across multiple Yahoo news payload shapes."""
    return (
        article.get("link")
        or article.get("canonicalUrl", {}).get("url")
        or content.get("canonicalUrl", {}).get("url")
        or content.get("clickThroughUrl", {}).get("url")
        or "#"
    )


def _clean_news_text(text: Optional[str]) -> str:
    """Normalize provider text by collapsing tabs/newlines/multi-spaces into one space."""
    if text is None:
        return ""
    normalized = "".join(
        " " if unicodedata.category(ch) in {"Cf", "Cc", "Cs"} else ch
        for ch in str(text)
    )
    return re.sub(r"\s+", " ", normalized).strip(" \t\r\n-|•·")


def _has_visible_news_text(text: Optional[str]) -> bool:
    cleaned = _clean_news_text(text)
    return bool(cleaned and any(ch.isalnum() for ch in cleaned))


def _filter_market_relevant_news(items: List[Dict]) -> List[Dict]:
    """
    Keep broad India-market headlines for index proxy feeds and drop duplicates.

    Args:
        items: List of dicts shaped as {title, publisher, link, published}.
    Rules:
        - Ignore rows with empty titles.
        - Deduplicate by lower-cased title.
        - Keep only headlines whose title/publisher matches MARKET_NEWS_KEEP_TERMS.
    """
    if not items:
        return []
    seen = set()
    filtered = []
    for item in items:
        title = str(item.get("title", "")).strip()
        publisher = str(item.get("publisher", "")).strip()
        key = title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        combined_text = f"{title} {publisher}".lower()
        if any(term in combined_text for term in MARKET_NEWS_KEEP_TERMS):
            filtered.append({**item, "title": title, "publisher": publisher})
    return filtered
