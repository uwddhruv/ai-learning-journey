"""
valuation_engine.py — Multi-model intrinsic value calculations.

Three complementary lenses:
  1. Graham Number  — conservative book-value floor
  2. Multi-Stage DCF — primary intrinsic value estimate
  3. Relative Valuation — market context (P/E, PEG, P/B)

All functions return dicts, never raise.
"""

import math
import numpy as np
from typing import Dict, Optional


# ── SECTOR P/E BENCHMARKS ────────────────────────────────────────────────────

SECTOR_PE = {
    "Technology": 25,
    "Healthcare": 35,
    "Financial Services": 20,
    "Consumer Cyclical": 40,
    "Consumer Defensive": 50,
    "Energy": 15,
    "Utilities": 18,
    "Real Estate": 30,
    "Industrials": 25,
    "Basic Materials": 18,
    "Communication Services": 20,
    "Unknown": 25,
}


# ── GRAHAM NUMBER ────────────────────────────────────────────────────────────

def calculate_graham(data: Dict) -> Dict:
    """
    Graham Number = √(22.5 × EPS × BVPS)

    A conservative floor; appropriate for traditional businesses.
    Growth stocks routinely trade multiples above it.
    """
    eps  = data.get("eps")
    bvps = data.get("book_value_per_share")
    price = data.get("current_price")

    if eps is None or bvps is None:
        return _graham_error("Missing EPS or Book Value Per Share.")

    if eps <= 0 or bvps <= 0:
        return _graham_error(
            "Graham Number is undefined for negative earnings or book value. "
            "This often characterises growth-stage or financially stressed companies.",
            confidence=0.05,
        )

    gn = math.sqrt(22.5 * eps * bvps)

    mos = None
    if price and price > 0:
        mos = (gn - price) / price

    explanation = _graham_narrative(gn, price, eps, bvps, mos)

    return {
        "graham_number": round(gn, 2),
        "eps": eps,
        "bvps": bvps,
        "margin_of_safety": round(mos, 4) if mos is not None else None,
        "confidence": 0.75,
        "error": None,
        "explanation": explanation,
    }


# ── MULTI-STAGE DCF ──────────────────────────────────────────────────────────

def calculate_dcf(data: Dict) -> Dict:
    """
    Three-stage discounted cashflow model.

    Stage 1 (Years 1–5):  High growth at estimated_growth_rate
    Stage 2 (Years 6–10): Fading growth (50% of Stage 1)
    Stage 3:              Terminal value at 2.5% perpetual growth

    WACC is estimated from beta + market risk premium.
    Output is capped at 50× base cashflow to prevent absurd results.
    """
    fcf_ps = data.get("fcf_per_share")
    eps    = data.get("eps")
    growth = data.get("estimated_growth_rate", 0.07)
    beta   = data.get("beta", 1.0) or 1.0

    # Select base cashflow
    base_cf, cf_source = _select_base_cashflow(fcf_ps, eps)
    if base_cf is None:
        return _dcf_error(
            "Negative or missing free cashflow and earnings — DCF not computable."
        )

    # WACC
    rfr  = 0.068          # India 10-Year G-Sec proxy
    erp  = 0.065          # India equity risk premium
    wacc = max(0.09, min(0.18, rfr + beta * erp))

    # Growth rates
    g1 = growth
    g2 = growth * 0.50
    g_t = 0.035

    # Stage 1
    cf = base_cf
    pv1 = []
    for yr in range(1, 6):
        cf *= (1 + g1)
        pv1.append(cf / (1 + wacc) ** yr)

    # Stage 2
    pv2 = []
    for yr in range(6, 11):
        cf *= (1 + g2)
        pv2.append(cf / (1 + wacc) ** yr)

    # Terminal value
    tv   = (cf * (1 + g_t)) / (wacc - g_t)
    tv_pv = tv / (1 + wacc) ** 10

    raw = sum(pv1) + sum(pv2) + tv_pv

    # Sanity cap
    cap   = base_cf * 50
    capped = raw > cap
    value  = min(raw, cap)

    confidence = data.get("data_quality", 0.5)
    if cf_source != "FCF/share":
        confidence *= 0.70

    price = data.get("current_price")
    explanation = _dcf_narrative(base_cf, growth, wacc, value, price, cf_source, capped)

    return {
        "intrinsic_value": round(value, 2),
        "stage1_pv":       round(sum(pv1), 2),
        "stage2_pv":       round(sum(pv2), 2),
        "terminal_pv":     round(tv_pv, 2),
        "wacc":            round(wacc, 4),
        "stage1_growth":   round(g1, 4),
        "stage2_growth":   round(g2, 4),
        "terminal_growth": g_t,
        "base_cashflow":   round(base_cf, 4),
        "cashflow_source": cf_source,
        "confidence":      round(confidence, 3),
        "sanity_capped":   capped,
        "error":           None,
        "explanation":     explanation,
    }


# ── RELATIVE VALUATION ───────────────────────────────────────────────────────

def get_relative_valuation(data: Dict) -> Dict:
    """
    Context-aware relative valuation.
    Compares P/E, P/B, PEG against sector norms.
    """
    pe     = data.get("pe_ratio")
    pb     = data.get("pb_ratio")
    peg    = data.get("peg_ratio")
    sector = data.get("sector", "Unknown")

    bench_pe = SECTOR_PE.get(sector, 20)

    def pe_signal(v):
        if v is None or v <= 0:
            return None
        if v < bench_pe * 0.70: return "cheap"
        if v < bench_pe * 1.00: return "fair"
        if v < bench_pe * 1.50: return "slightly_rich"
        return "expensive"

    def pb_signal(v):
        if v is None or v <= 0: return None
        if v < 1.0:  return "deep_value"
        if v < 2.0:  return "fair"
        if v < 4.0:  return "growth_premium"
        return "expensive"

    def peg_signal(v):
        if v is None or v <= 0: return None
        if v < 1.0:  return "undervalued"
        if v < 1.5:  return "fair"
        if v < 2.5:  return "overvalued"
        return "very_overvalued"

    return {
        "pe_ratio":    pe,
        "pb_ratio":    pb,
        "peg_ratio":   peg,
        "benchmark_pe": bench_pe,
        "sector":      sector,
        "pe_signal":   pe_signal(pe),
        "pb_signal":   pb_signal(pb),
        "peg_signal":  peg_signal(peg),
    }


# ── PRIVATE HELPERS ──────────────────────────────────────────────────────────

def _select_base_cashflow(fcf_ps, eps):
    if fcf_ps and fcf_ps > 0:
        return fcf_ps, "FCF/share"
    if eps and eps > 0:
        return eps * 0.70, "EPS (proxy)"
    return None, None


def _graham_error(msg: str, confidence: float = 0.0) -> Dict:
    return {
        "graham_number": None, "eps": None, "bvps": None,
        "margin_of_safety": None, "confidence": confidence,
        "error": msg, "explanation": msg,
    }


def _dcf_error(msg: str) -> Dict:
    return {
        "intrinsic_value": None, "confidence": 0,
        "error": msg, "explanation": msg,
        "stage1_pv": None, "stage2_pv": None, "terminal_pv": None,
        "wacc": None, "cashflow_source": None, "sanity_capped": False,
    }


def _graham_narrative(gn, price, eps, bvps, mos) -> str:
    lines = [
        f"Graham Number = √(22.5 × EPS ₹{eps:.2f} × BVPS ₹{bvps:.2f}) = ₹{gn:.2f}."
    ]
    if mos is not None:
        if mos > 0.30:
            lines.append(
                f"The stock trades {mos*100:.0f}% below this floor — "
                "Benjamin Graham would consider this a significant safety margin."
            )
        elif mos > 0:
            lines.append("Priced modestly below the Graham Number — within value territory.")
        else:
            lines.append(
                f"Trading {abs(mos)*100:.0f}% above the Graham Number. "
                "Graham would consider this pricing rich, though growth stocks commonly exceed it."
            )
    lines.append(
        "Remember: Graham Number is a conservative, asset-based anchor — "
        "not a ceiling. High-quality franchises often deserve premiums."
    )
    return " ".join(lines)


def _dcf_narrative(base_cf, growth, wacc, value, price, source, capped) -> str:
    lines = [
        f"DCF anchors on {source} of ₹{base_cf:.2f}/share.",
        f"Assumed {growth*100:.1f}% growth (Years 1–5), fading to 3.5% terminal rate.",
        f"Discount rate (WACC): {wacc*100:.1f}% — reflecting the stock's risk profile.",
    ]
    if price and value:
        mos_pct = (value - price) / price * 100
        if mos_pct > 25:
            lines.append(
                f"At ₹{price:.2f}, the stock appears ~{mos_pct:.0f}% below estimated intrinsic value "
                f"of ₹{value:.2f} — a meaningful margin of safety."
            )
        elif mos_pct > 0:
            lines.append(f"Modestly undervalued vs. intrinsic estimate of ₹{value:.2f}.")
        else:
            lines.append(
                f"Stock trades {abs(mos_pct):.0f}% above DCF estimate — "
                "requires growth acceleration to justify current price."
            )
    if capped:
        lines.append(
            "⚠️ Raw model output was capped at 50× base cashflow "
            "to prevent unrealistic extreme values."
        )
    return " ".join(lines)
