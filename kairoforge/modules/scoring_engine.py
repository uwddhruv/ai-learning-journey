"""
scoring_engine.py — Value Opportunity Score (0–100).

Scoring rubric (max points):
  ① DCF Margin of Safety     30
  ② Graham Margin of Safety  20
  ③ Profitability Quality    20
  ④ Relative Valuation       15
  ⑤ Data Quality Bonus       15
  ─────────────────────────────
  Total                     100

Logic principles:
  - Each component is normalized and bounded.
  - Low data quality reduces, not eliminates, the score.
  - Consistency across models is rewarded.
  - Outputs are penalised if only one model fires.
"""

from typing import Dict, Tuple
from modules.valuation_engine import calculate_dcf, calculate_graham, get_relative_valuation


# ── MAIN SCORING FUNCTION ─────────────────────────────────────────────────────

def compute_score(data: Dict) -> Dict:
    """
    Compute the Value Opportunity Score and return full analysis package.

    Returns:
        score       (float)  0-100
        signal      (str)    STRONG BUY | BUY | HOLD | AVOID | STRONG AVOID
        label       (str)    Human-readable valuation label
        color       (str)    Hex colour for UI
        confidence  (str)    High | Medium | Low | Very Low
        breakdown   (dict)   Per-component scores
        dcf         (dict)   Full DCF result
        graham      (dict)   Full Graham result
        relative    (dict)   Relative valuation result
        explanation (str)    Analyst narrative
    """
    price = data.get("current_price")
    if not price:
        return _null_score("No price data available.")

    dcf      = calculate_dcf(data)
    graham   = calculate_graham(data)
    relative = get_relative_valuation(data)

    breakdown = {}

    # ① DCF Margin of Safety (0–30) ────────────────────────────────
    dcf_score = 0.0
    if dcf.get("intrinsic_value") and price:
        mos = (dcf["intrinsic_value"] - price) / price
        raw = _mos_to_score(mos, max_pts=30)
        dcf_score = raw * dcf.get("confidence", 0.5)
    breakdown["DCF Value Gap"] = round(dcf_score, 1)

    # ② Graham MOS (0–20) ──────────────────────────────────────────
    graham_score = 0.0
    if graham.get("graham_number") and price:
        mos = graham.get("margin_of_safety") or 0
        graham_score = _mos_to_score(mos, max_pts=20)
    breakdown["Graham Safety"] = round(graham_score, 1)

    # ③ Profitability Quality (0–20) ───────────────────────────────
    quality = _score_quality(data)
    breakdown["Profitability"] = round(quality, 1)

    # ④ Relative Valuation (0–15) ──────────────────────────────────
    rel = _score_relative(relative)
    breakdown["Relative Value"] = round(rel, 1)

    # ⑤ Data Quality Bonus (0–15) ──────────────────────────────────
    dq = data.get("data_quality", 0.5)
    dq_pts = dq * 15
    breakdown["Data Quality"] = round(dq_pts, 1)

    # ── Multi-model consistency bonus ─────────────────────────────
    consistency = _consistency_bonus(dcf, graham, price)
    breakdown["Consistency"] = round(consistency, 1)

    total = sum(breakdown.values())
    final = max(0.0, min(100.0, total))

    signal, label, color = signal_from_score(final)
    confidence = _confidence_label(dq, dcf.get("confidence", 0.5))
    narrative  = _build_narrative(final, signal, data, dcf, graham, relative)

    return {
        "score":       round(final, 1),
        "signal":      signal,
        "label":       label,
        "color":       color,
        "confidence":  confidence,
        "breakdown":   breakdown,
        "dcf":         dcf,
        "graham":      graham,
        "relative":    relative,
        "explanation": narrative,
    }


def signal_from_score(score: float) -> Tuple[str, str, str]:
    """Map numeric score to actionable signal + hex colour."""
    if score >= 72:
        return "STRONG BUY",    "Undervalued",                "#00d4aa"
    elif score >= 58:
        return "BUY",           "Slightly Undervalued",       "#4ade80"
    elif score >= 43:
        return "HOLD",          "Fair Value",                 "#fbbf24"
    elif score >= 28:
        return "AVOID",         "Overvalued",                 "#f87171"
    else:
        return "STRONG AVOID",  "Significantly Overvalued",   "#ef4444"


# ── COMPONENT SCORERS ─────────────────────────────────────────────────────────

def _mos_to_score(mos: float, max_pts: int) -> float:
    """Convert margin of safety ratio to score out of max_pts."""
    if mos >= 0.50:  return max_pts * 1.00
    if mos >= 0.30:  return max_pts * 0.83
    if mos >= 0.10:  return max_pts * 0.60
    if mos >= -0.10: return max_pts * 0.33
    if mos >= -0.30: return max_pts * 0.17
    return 0.0


def _score_quality(data: Dict) -> float:
    """Score profitability quality on 0–20 scale."""
    score = 0.0
    roe    = data.get("roe")    or 0
    roa    = data.get("roa")    or 0
    margin = data.get("profit_margin") or 0
    g_mar  = data.get("gross_margin")  or 0

    # ROE (0–10)
    if   roe > 0.30: score += 10
    elif roe > 0.20: score += 7.5
    elif roe > 0.12: score += 5
    elif roe > 0.06: score += 2.5
    elif roe > 0:    score += 1

    # Net margin (0–6)
    if   margin > 0.25: score += 6
    elif margin > 0.15: score += 4
    elif margin > 0.08: score += 2.5
    elif margin > 0.03: score += 1

    # ROA bonus (0–4)
    if   roa > 0.12: score += 4
    elif roa > 0.07: score += 2.5
    elif roa > 0.03: score += 1

    return min(20.0, score)


def _score_relative(rel: Dict) -> float:
    """Score relative valuation context on 0–15 scale."""
    pe_map  = {"cheap": 8, "fair": 5, "slightly_rich": 2, "expensive": 0}
    peg_map = {"undervalued": 7, "fair": 5, "overvalued": 2, "very_overvalued": 0}
    pb_map  = {"deep_value": 3, "fair": 2, "growth_premium": 1, "expensive": 0}

    score = 0.0
    score += pe_map.get(rel.get("pe_signal"),  4)   # neutral default 4
    score += peg_map.get(rel.get("peg_signal"), 3)  # neutral default 3 if no PEG
    score += pb_map.get(rel.get("pb_signal"),  1)

    return min(15.0, score)


def _consistency_bonus(dcf: Dict, graham: Dict, price: float) -> float:
    """
    Award up to 5 bonus points when both DCF and Graham agree the stock is cheap.
    Penalise if models disagree sharply (one says buy, one says sell).
    """
    d_mos = None
    g_mos = None

    if dcf.get("intrinsic_value") and price:
        d_mos = (dcf["intrinsic_value"] - price) / price
    if graham.get("margin_of_safety") is not None:
        g_mos = graham["margin_of_safety"]

    if d_mos is None or g_mos is None:
        return 0.0  # can't judge consistency

    # Both agree it's cheap
    if d_mos > 0.10 and g_mos > 0.10:
        return 5.0
    # Both agree it's rich
    if d_mos < -0.10 and g_mos < -0.10:
        return 2.0  # still some consistency, different direction
    # Disagreement
    if d_mos > 0.20 and g_mos < -0.10:
        return -3.0
    if d_mos < -0.10 and g_mos > 0.20:
        return -3.0
    return 0.0


# ── UTILITIES ─────────────────────────────────────────────────────────────────

def _confidence_label(dq: float, dcf_conf: float) -> str:
    avg = (dq + dcf_conf) / 2
    if avg >= 0.75: return "High"
    if avg >= 0.50: return "Medium"
    if avg >= 0.25: return "Low"
    return "Very Low"


def _build_narrative(score, signal, data, dcf, graham, relative) -> str:
    """Write a concise analyst-style paragraph explaining the score."""
    name  = data.get("company_name") or data.get("ticker", "This stock")
    price = data.get("current_price") or 0
    parts = []

    # Lead
    lead_map = {
        "STRONG BUY":   f"{name} scores {score:.0f}/100 — our models suggest meaningful undervaluation.",
        "BUY":          f"{name} scores {score:.0f}/100, pointing to modest undervaluation at current levels.",
        "HOLD":         f"{name} scores {score:.0f}/100, trading broadly in line with fair value estimates.",
        "AVOID":        f"{name} scores {score:.0f}/100 — valuation metrics suggest the stock is priced for perfection.",
        "STRONG AVOID": f"{name} scores {score:.0f}/100 — multiple models flag significant overvaluation.",
    }
    parts.append(lead_map.get(signal, f"Score: {score:.0f}/100."))

    # DCF insight
    if dcf.get("intrinsic_value") and price:
        mos_pct = (dcf["intrinsic_value"] - price) / price * 100
        iv = dcf["intrinsic_value"]
        if mos_pct > 25:
            parts.append(f"DCF intrinsic value is ₹{iv:.2f} — approximately {mos_pct:.0f}% above the market price.")
        elif mos_pct < -25:
            parts.append(f"DCF model values the business at ₹{iv:.2f}, below the current price of ₹{price:.2f}.")

    # Graham
    g_mos = graham.get("margin_of_safety")
    if g_mos is not None:
        if g_mos > 0.25:
            parts.append(f"Graham Number confirms cheapness — stock is {g_mos*100:.0f}% below this conservative anchor.")
        elif g_mos < -0.25:
            parts.append("Graham Number suggests the stock trades at a premium to its asset-based floor.")

    # Quality
    roe = data.get("roe") or 0
    if roe > 0.20:
        parts.append(f"ROE of {roe*100:.0f}% reflects a high-quality business with strong capital efficiency.")
    elif 0 < roe < 0.06:
        parts.append(f"ROE of {roe*100:.1f}% is below typical thresholds — profitability quality is a concern.")

    # Risk note
    beta = data.get("beta") or 1.0
    if beta > 1.5:
        parts.append(f"Beta of {beta:.1f} signals above-average volatility; position-size accordingly.")
    elif beta < 0.6:
        parts.append(f"Low beta ({beta:.1f}) reflects defensive characteristics — useful in volatile markets.")

    # Caveat
    dq = data.get("data_quality", 0.5)
    if dq < 0.4:
        parts.append("⚠️ Data coverage is limited — treat this score as directional rather than precise.")

    return " ".join(parts)


def _null_score(reason: str) -> Dict:
    return {
        "score": 0, "signal": "NO DATA", "label": "Insufficient Data",
        "color": "#6b7280", "confidence": "Very Low",
        "breakdown": {}, "dcf": {}, "graham": {}, "relative": {},
        "explanation": reason,
    }
