# Inventory Coverage & Stockout-Alert Dashboard

An interactive dashboard that monitors warehouse inventory, calculates stock
coverage, and raises **proactive alerts** when parts fall below their reorder
point or run out — helping prevent material shortages that stop a production line.

Built with Python, SQL, Plotly and Streamlit.

**Live app:** https://akshaygade-inventory-stockout-dashboard.streamlit.app/

---

## Why this project

In a factory, a single stocked-out part can halt production. This project models
a warehouse supplying a production line and answers two operational questions:
*how many days of stock is left per part*, and *which parts need reordering now*.
It combines inventory KPIs with an automated alert layer and a data-quality check.

## Data

Synthetic warehouse data, generated in code and fully reproducible (fixed random
seed). It simulates 20 parts over 30 days of stock movements. This is synthetic
data built to demonstrate the approach — not from any real company.

## How it works

**1. PFEP master (Plan for Every Part).** Each part has an average daily demand,
lead time, reorder point, and max-stock level.
- Reorder point = average daily demand x lead time + a safety buffer (the stock
  level at which a part must be reordered to avoid running out during resupply).

**2. Daily stock ledger.** A 30-day, per-part record of opening stock, consumption,
replenishment, and closing stock, loaded into a SQLite warehouse.

**3. KPIs (SQL + Python).**
- Current stock per part (latest day, via a max-date-per-group SQL query)
- Days of coverage = current stock / average daily demand
- Parts below reorder point; stockout count

**4. Alert layer.** Flags each part at its most severe level:
- STOCKOUT (out of stock), REORDER (below reorder point), or LOW COVERAGE
  (few days of stock left) — a proactive alert on shortages.

**5. Data-quality check.** Reconciles the ledger (closing = opening - consumed +
received) to confirm the data is internally consistent.

**6. Dashboard (Streamlit + Plotly).** KPI tiles, a colour-coded alert panel, a
days-of-coverage bar chart, and an interactive per-part stock chart with the
reorder point marked.

## Tech stack

| Purpose | Tools |
|---------|-------|
| Data handling | Python, pandas, NumPy |
| Storage / querying | SQLite, SQL (joins, aggregations) |
| Visualisation | Plotly Express |
| Dashboard app | Streamlit |

## How to run

Locally:
1. Install dependencies: `pip install -r requirements.txt`
2. Launch the app: `streamlit run dashboard.py`

The app generates its data on startup, so no data files are required.

## Repository contents

| File | Description |
|------|-------------|
| `dashboard.py` | Streamlit app: data generation, SQL, KPIs, alerts, charts |
| `inventory_stockout_dashboard.ipynb` | Notebook walkthrough: step-by-step build with explanations |
| `DATA_DICTIONARY.md` | Schema and column definitions for both tables |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

## What I'd improve next

- Replace average-daily-demand with a proper demand **forecast** for coverage.
- Add a simple ordering simulation (reorder up to max-stock when triggered).
- Connect to live data instead of synthetic generation.
- Alerting via email/Slack for parts crossing the reorder point.

---

*Portfolio project demonstrating inventory analytics, SQL, data-quality checks,
and operational dashboards for supply-chain / intralogistics use cases.*
