# ⚡ KAIROFORGE — Equity Intelligence Terminal

> A lightweight **Bloomberg Terminal × Screener × TradingView hybrid**, built in Streamlit.

---

## What It Does

KAIROFORGE blends three core tools into one clean interface:

| Module | Description |
|--------|-------------|
| **Screener** | Scans 20+ major equities in real time. Each stock gets a signal: STRONG BUY → AVOID |
| **Stock Analysis** | Full equity report: Hero panel, price chart, DCF/Graham breakdown, scoring intelligence |
| **Portfolio Builder** | Build an equal-weight portfolio. Interprets composition, risk profile, and concentration |

---

## Quick Start

### 1. Clone / download the project

```bash
cd kairoforge
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate.bat       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**.

---

## Architecture

```
kairoforge/
├── app.py                    ← Main Streamlit entry point / UI router
├── modules/
│   ├── data_layer.py         ← Defensive yfinance fetching + data quality scoring
│   ├── valuation_engine.py   ← DCF, Graham Number, relative valuation
│   ├── scoring_engine.py     ← Value Opportunity Score (0–100)
│   └── styles.py             ← Premium dark CSS
├── .streamlit/
│   └── config.toml           ← Dark theme config
└── requirements.txt
```

### Scoring Rubric

| Component | Max Points | Logic |
|-----------|-----------|-------|
| DCF Margin of Safety | 30 | Deeper discount → more points; scaled by data confidence |
| Graham MOS | 20 | Conservative asset-based safety margin |
| Profitability Quality | 20 | ROE, net margin, ROA |
| Relative Valuation | 15 | P/E vs sector median, PEG, P/B |
| Data Quality Bonus | 15 | Rewards complete, reliable data |

---

## Notes

- Data is cached for 1 hour per session to avoid redundant API calls.
- If a metric is unavailable, the model degrades gracefully (adjusts confidence, doesn't crash).
- DCF output is capped at 50× base cashflow to prevent absurd results from high-growth outliers.
- This tool is for **educational purposes only**. It is not financial advice.

---

## Footer

**KAIROFORGE — Created by Dhruv Vaniawala | uwddhruv@gmail.com**


"Built by Dhruv Vaniawala, a 16-year-old investor from Surat who has been investing in equity markets since age 10 and read Benjamin Graham's The Intelligent Investor at 12. KairoForge is the tool I always wished existed for Indian retail investors."
