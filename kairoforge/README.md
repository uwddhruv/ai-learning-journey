# ⚡ KAIROFORGE — Equity Intelligence Terminal

> A lightweight **Bloomberg Terminal × Screener × TradingView hybrid**, built in Streamlit.

---

## What It Does

KAIROFORGE blends three core tools into one clean interface:

| Module | Description |
|--------|-------------|
| **Screener** | Scans 30 Nifty 50 stocks by default; add any of **500+ Indian equities** from the searchable dropdown. Each stock gets a signal: STRONG BUY → AVOID |
| **Stock Analysis** | Full equity report: Hero panel, price chart, DCF/Graham breakdown, scoring intelligence |
| **Portfolio Builder** | Build a portfolio using the searchable multi-stock selector. Interprets composition, risk profile, and concentration |

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
├── data/
│   └── india_stocks.csv      ← 500+ NSE stock universe (ticker, company, sector)
├── assets/
│   └── logo.png              ← Brand logo (auto-loaded in sidebar)
├── modules/
│   ├── data_layer.py         ← Defensive yfinance fetching, data quality scoring,
│   │                            and stock universe loader (load_india_stocks)
│   ├── valuation_engine.py   ← DCF, Graham Number, relative valuation
│   ├── scoring_engine.py     ← Value Opportunity Score (0–100)
│   └── styles.py             ← Premium dark CSS
├── .streamlit/
│   └── config.toml           ← Dark theme config
└── requirements.txt
```

### Indian Stock Universe (`data/india_stocks.csv`)

The file contains **500+ NSE-listed equities** with columns:

| Column | Description |
|--------|-------------|
| `ticker` | NSE ticker with `.NS` suffix (yfinance-compatible) |
| `company` | Full company name |
| `sector` | Broad sector classification |

Stocks span **Nifty 50, Nifty Next 50, Nifty Midcap 150** and beyond, covering
Financial Services, IT, Pharma, Automobile, Chemicals, Infrastructure, FMCG,
Defence, Retail, and more.

### Searchable Dropdown Selector

- **Sidebar**: "Search & Analyse Stock" selectbox — type to search by company name or ticker.
- **Screener**: Multi-select to add any stock from the 500+ universe to the screener watchlist.
- **Portfolio Builder**: Multi-select to build a portfolio from the full stock universe.
- No exact ticker typing required; search by partial company name or symbol.

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
- The stock universe CSV is cached for 24 hours (file rarely changes).
- If a metric is unavailable, the model degrades gracefully (adjusts confidence, doesn't crash).
- DCF output is capped at 50× base cashflow to prevent absurd results from high-growth outliers.
- This tool is for **educational purposes only**. It is not financial advice.

---

## Footer

**KAIROFORGE — Created by Dhruv Vaniawala | uwddhruv@gmail.com**
