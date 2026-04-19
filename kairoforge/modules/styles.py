"""
styles.py — Premium dark UI CSS.
Injected once at app startup via st.markdown(unsafe_allow_html=True).
"""


def inject_styles() -> str:
    return """
<style>
/* ── GLOBAL RESET & TYPOGRAPHY ─────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    scroll-behavior: smooth;
}

/* ── APP BACKGROUND ─────────────────────────────────────────── */
.stApp {
    background: #0a0a0f !important;
}

.main .block-container {
    padding: 1.5rem 2rem 3rem 2rem !important;
    max-width: 1400px !important;
}

/* ── HIDE DEFAULT STREAMLIT CHROME ───────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── SIDEBAR ────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0d0d16 !important;
    border-right: 1px solid #1e1e2e !important;
}
[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1rem !important;
}

/* ── PAGE HEADER ─────────────────────────────────────────────── */
.kf-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #1e1e2e;
}
.kf-header-logo {
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #00d4aa 0%, #7c3aed 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.kf-header-sub {
    font-size: 0.8rem;
    color: #64748b;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 500;
}

/* ── CARDS ───────────────────────────────────────────────────── */
.kf-card {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 14px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s ease;
}
.kf-card:hover {
    border-color: #2d2d42;
}
.kf-card-sm {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
}

/* ── HERO PANEL ─────────────────────────────────────────────── */
.kf-hero {
    background: linear-gradient(135deg, #12121a 0%, #16162a 100%);
    border: 1px solid #2d2d42;
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 1.5rem;
}
.kf-hero-ticker {
    font-size: 0.85rem;
    color: #64748b;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.kf-hero-name {
    font-size: 1.8rem;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 0.5rem;
    line-height: 1.2;
}
.kf-hero-price {
    font-size: 2.8rem;
    font-weight: 700;
    color: #f8fafc;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
    margin-bottom: 0.25rem;
}
.kf-hero-meta {
    font-size: 0.8rem;
    color: #64748b;
}

/* ── LANDING PAGE ─────────────────────────────────────────────── */
.kf-landing-hero {
    background:
        radial-gradient(circle at 20% 20%, rgba(0,212,170,0.18), transparent 45%),
        radial-gradient(circle at 80% 0%, rgba(124,58,237,0.22), transparent 45%),
        linear-gradient(135deg, #0f1020 0%, #15152a 48%, #171735 100%);
    border: 1px solid #2b2b45;
    border-radius: 20px;
    min-height: 60vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2.5rem 1.5rem;
    margin-bottom: 1.25rem;
}
.kf-landing-logo {
    width: 112px;
    height: 112px;
    border-radius: 18px;
    object-fit: cover;
    border: 1px solid #2d2d42;
    box-shadow: 0 14px 35px rgba(0,0,0,0.35);
    margin-bottom: 1rem;
}
.kf-landing-kicker {
    color: #00d4aa;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: .16em;
    text-transform: uppercase;
    margin-bottom: .4rem;
}
.kf-landing-hero h1 {
    color: #f8fafc;
    font-size: clamp(2rem, 5vw, 3.3rem);
    margin: 0;
    letter-spacing: -0.03em;
}
.kf-landing-hero p {
    color: #94a3b8;
    font-size: 1rem;
    max-width: 720px;
    margin: .9rem auto 1.5rem auto;
    line-height: 1.7;
}
.kf-landing-scroll {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none !important;
    border: 1px solid #3a3a58;
    border-radius: 999px;
    color: #e2e8f0 !important;
    font-size: .84rem;
    font-weight: 600;
    padding: .55rem 1.1rem;
    background: rgba(10,10,15,0.35);
    transition: all .2s ease;
}
.kf-landing-scroll:hover {
    border-color: #00d4aa;
    color: #00d4aa !important;
}
.kf-landing-search-title {
    text-align: center;
    color: #cbd5e1;
    font-size: .8rem;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    margin: .5rem 0 .65rem 0;
}
.kf-landing-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 1rem;
    margin: 1.4rem 0 1.1rem 0;
}
.kf-landing-card {
    background: linear-gradient(180deg, rgba(18,18,27,.95) 0%, rgba(14,14,22,.95) 100%);
    border: 1px solid #23233a;
    border-radius: 14px;
    padding: 1.1rem 1.2rem;
}
.kf-landing-card h3 {
    margin: 0 0 .5rem 0;
    color: #f1f5f9;
    font-size: 1rem;
}
.kf-landing-card p {
    margin: 0;
    color: #94a3b8;
    font-size: .84rem;
    line-height: 1.6;
}

/* ── SIGNAL BADGE ────────────────────────────────────────────── */
.kf-signal {
    display: inline-block;
    padding: 0.35rem 1rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.kf-signal-STRONG-BUY  { background: rgba(0,212,170,0.15); color: #00d4aa; border: 1px solid rgba(0,212,170,0.3); }
.kf-signal-BUY          { background: rgba(74,222,128,0.15); color: #4ade80; border: 1px solid rgba(74,222,128,0.3); }
.kf-signal-HOLD         { background: rgba(251,191,36,0.15);  color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
.kf-signal-AVOID        { background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid rgba(248,113,113,0.3); }
.kf-signal-STRONG-AVOID{ background: rgba(239,68,68,0.15);   color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.kf-signal-NO-DATA     { background: rgba(107,114,128,0.15); color: #9ca3af; border: 1px solid rgba(107,114,128,0.3); }

/* ── METRIC GRID ─────────────────────────────────────────────── */
.kf-metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 1rem;
    margin: 1rem 0;
}
.kf-metric-box {
    background: #0d0d16;
    border: 1px solid #1e1e2e;
    border-radius: 10px;
    padding: 1rem 1.25rem;
}
.kf-metric-label {
    font-size: 0.72rem;
    color: #64748b;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
}
.kf-metric-value {
    font-size: 1.3rem;
    font-weight: 600;
    color: #e2e8f0;
    font-family: 'JetBrains Mono', monospace;
}
.kf-metric-sub {
    font-size: 0.7rem;
    color: #475569;
    margin-top: 0.2rem;
}

/* ── VALUATION BARS ──────────────────────────────────────────── */
.kf-val-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid #1a1a28;
}
.kf-val-label {
    width: 120px;
    font-size: 0.75rem;
    color: #94a3b8;
    font-weight: 500;
    flex-shrink: 0;
}
.kf-val-value {
    width: 90px;
    font-size: 1rem;
    font-weight: 600;
    font-family: 'JetBrains Mono', monospace;
    color: #f1f5f9;
    flex-shrink: 0;
}
.kf-val-bar-wrap {
    flex: 1;
    height: 6px;
    background: #1e1e2e;
    border-radius: 3px;
    overflow: hidden;
}
.kf-val-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s ease;
}

/* ── SCORE RING ──────────────────────────────────────────────── */
.kf-score-ring {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 120px;
    height: 120px;
    border-radius: 50%;
    border: 3px solid currentColor;
    margin: 0 auto 1rem auto;
}
.kf-score-number {
    font-size: 2rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
}
.kf-score-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0.7;
}

/* ── EXPLANATION BOX ─────────────────────────────────────────── */
.kf-explain {
    background: #0d0d16;
    border-left: 3px solid #7c3aed;
    border-radius: 0 10px 10px 0;
    padding: 1.25rem 1.5rem;
    font-size: 0.875rem;
    color: #cbd5e1;
    line-height: 1.7;
    margin: 1rem 0;
}

/* ── SECTION HEADER ──────────────────────────────────────────── */
.kf-section-title {
    font-size: 0.7rem;
    font-weight: 700;
    color: #475569;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin: 1.5rem 0 0.75rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.kf-section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #1e1e2e;
}

/* ── CONFIDENCE BADGE ─────────────────────────────────────────── */
.kf-confidence {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.kf-conf-High      { background: rgba(0,212,170,0.1); color: #00d4aa; }
.kf-conf-Medium    { background: rgba(251,191,36,0.1);  color: #fbbf24; }
.kf-conf-Low       { background: rgba(248,113,113,0.1); color: #f87171; }
.kf-conf-Very-Low { background: rgba(107,114,128,0.1); color: #9ca3af; }

/* ── STREAMLIT OVERRIDES ─────────────────────────────────────── */
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stTextInput > div > div > input {
    background: #12121a !important;
    border: 1px solid #2d2d42 !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
/* Multiselect tag pills */
.stMultiSelect span[data-baseweb="tag"] {
    background: rgba(0,212,170,0.15) !important;
    border: 1px solid rgba(0,212,170,0.3) !important;
    border-radius: 6px !important;
    color: #00d4aa !important;
    font-size: 0.75rem !important;
}
/* Dropdown listbox */
ul[data-testid="stSelectboxVirtualDropdown"],
ul[role="listbox"] {
    background: #12121a !important;
    border: 1px solid #2d2d42 !important;
}
.stButton > button {
    background: linear-gradient(135deg, #00d4aa 0%, #0891b2 100%) !important;
    color: #0a0a0f !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

div[data-testid="metric-container"] {
    background: #12121a !important;
    border: 1px solid #1e1e2e !important;
    border-radius: 10px !important;
    padding: 0.75rem 1rem !important;
}
div[data-testid="metric-container"] [data-testid="metric-label"] {
    color: #64748b !important;
    font-size: 0.75rem !important;
}
div[data-testid="metric-container"] [data-testid="metric-value"] {
    color: #f1f5f9 !important;
}

/* ── TABS ─────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #1e1e2e !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748b !important;
    border-radius: 0 !important;
    padding: 0.6rem 1.2rem !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    color: #00d4aa !important;
    border-bottom: 2px solid #00d4aa !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem !important;
}

/* ── SCROLLBAR ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0a0f; }
::-webkit-scrollbar-thumb { background: #2d2d42; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3d3d5c; }

/* ── FOOTER ──────────────────────────────────────────────────── */
.kf-footer {
    text-align: center;
    font-size: 0.72rem;
    color: #334155;
    padding: 2rem 0 1rem 0;
    letter-spacing: 0.05em;
    border-top: 1px solid #1a1a28;
    margin-top: 3rem;
}
.kf-footer a { color: #475569 !important; text-decoration: none; }
.kf-footer a:hover { color: #00d4aa !important; }
</style>
"""
