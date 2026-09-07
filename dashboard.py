import numpy as np
import pandas as pd
import sqlite3
import streamlit as st
import plotly.express as px

# ---------- Page setup ----------
# This configures the overall page.
# page_title="..." sets the text shown in the browser tab.
# layout="wide" tells Streamlit to use the full width of the browser window. The default is a narrow centered column; "wide" is better for dashboards.
st.set_page_config(page_title="Inventory Coverage & Stockout Alerts", layout="wide")

# Displays a large heading on the page
st.title("Inventory Coverage & Stockout-Alert Dashboard")

# Displays small, greyed-out text — a caption.
st.caption("Synthetic warehouse data · PFEP-based reorder logic · portfolio project")

# ---------- Build all data (Steps 1–6, cached) ----------
#st.cache_data tells Streamlit run build_data() function once, remember (cache) its result, and on future reruns skip the work and hand back the saved result.
@st.cache_data       # runs once and caches, so the app is fast on reload
#User defined function with no parameter, returns pfep, stock_daily, kpi, bad_rows
#"Streamlit reruns the whole script on every interaction, so I put the expensive data preparation — PFEP master table creation, Daily stock simulation table creation,  SQL warehouse, KPIs: current stock + coverage, Data-quality check — inside a build_data() function decorated with @st.cache_data. That runs it once and caches the result, so the app stays fast instead of rebuilding everything on every click."
def build_data():
    np.random.seed(42)      #You can use any number, seed produces the exact same random values. Without it, you'd get different data on every run.


    # --- PFEP master (Step 1) ---
    parts = [f"P-{1000+i}" for i in range(1, 21)]   # Getting 20 part Ids: P-1001, P1002, ...

    # Creating DataFrame-pfea (Plan for Every Part with 20 rows)
    pfep = pd.DataFrame({
        "part_id": parts,
        "description": [f"Component {i}" for i in range(1, 21)],
        "location": np.random.choice(["WH-A", "WH-B", "Line-1", "Line-2"], 20),
        "avg_daily_demand": np.random.randint(20, 100, 20),     # avg units used per day
        "lead_time_days": np.random.randint(2, 10, 20), # days for new stock to arrive once ordered
    })

    # avg_daily_demand = 50 (you use 50 units/day)
    # lead_time_days = 4 (new stock takes 4 days to arrive after you order)
    # 20% safety buffer
    # reorder_point = 240 means: "When your stock drops to 240 units, order more NOW — because you'll burn through roughly 240 units in the time it takes the new order to arrive, and the buffer protects you if demand spikes."
    pfep["reorder_point"] = (pfep["avg_daily_demand"] * pfep["lead_time_days"] * 1.2).astype(int)

    # max_stock (full — start here, refill up to here)
    # order enough to bring stock back up to max_stock
    # mainly to set a sensible full-stock starting level per part, and as the reference for 'full'
    pfep["max_stock"] = (pfep["reorder_point"] * 2).astype(int)


    # --- Daily stock simulation (Step 2) ---
    # Simulate 30 days of stock movements
    rows = []

    # makes 30 consecutive dates (Jul 1-30). .date strips the time part
    dates = pd.date_range("2026-07-01", periods=30).date

    # iterrows holds (index, p) in a tuple
    # _, p -> used for tuple unpacking
    # programmers use _ by convention to signal "I'm required to catch this value, but I don't use it."
    for _, p in pfep.iterrows():
        stock = p["max_stock"]      #each part starts full as its max_stock
        for d in dates:
            # "I modeled daily consumption as a normal distribution around each part's average demand, so usage varies realistically day to day. I wrapped it in int() for whole units and max(0, …) so consumption can never go negative."
            consumed = max(0, int(np.random.normal(p["avg_daily_demand"], 10)))

            # "There's a 15% chance each day that a delivery arrives. If it does, it refills the part back up to its max_stock (received = the gap to full). Otherwise, received = 0 (nothing arrives)."
            # I kept the probability low on purpose so some parts drift below their reorder point, giving my alert layer real shortages to detect."
            received = (p["max_stock"] - stock) if np.random.rand() < 0.15 else 0
            opening = stock     #stock at the start of the day
            closing = max(0, opening - consumed + received)
            rows.append([p["part_id"], d, opening, consumed, received, closing])
            stock = closing     # today's closing becomes tomorrow's opening

    stock_daily = pd.DataFrame(rows, columns=["part_id","date","opening","consumed","received","closing"])  # Creating a DataFrame-stock_daily


    # --- SQL warehouse (Step 3) ---
    # Load both tables into the SQL warehouse

    # This opens a connection to a SQLite database — but instead of a file, it creates the database purely in RAM (memory). Rebuilt from data each run.
    conn = sqlite3.connect(":memory:")

    # conn — which database to write to (the connection from above).
    pfep.to_sql("pfep", conn, if_exists="replace", index=False)
    stock_daily.to_sql("stock_daily", conn, if_exists="replace", index=False)

    
    # --- KPIs: current stock + coverage (Step 4) ---
    # Compute the KPIs(current stock + days of coverage)

    # 1. Get each part's LATEST day's closing stock (its current stock)
    # The inner query (the part in parentheses, aliased m)
    latest = pd.read_sql('SELECT s.part_id, s.closing AS current_stock FROM stock_daily s JOIN (SELECT part_id, MAX(date) AS last_date FROM stock_daily GROUP BY part_id) m ON s.part_id = m.part_id AND s.date = m.last_date', conn)

    # 2. Join current stock to the PFEP master and compute coverage
    kpi = latest.merge(pfep, on='part_id')
   
    kpi['days_of_coverage'] = (kpi['current_stock'] / kpi['avg_daily_demand']).round(1)     # how many days until we run out ?    .round(1) keeps one decimal.


    # --- Data-quality check (Step 6) ---
    # A data-quality check

    # recompute what closing SHOULD be, and compare to what it IS
    check = stock_daily.copy()

    check['expected_closing'] = (check['opening'] - check['consumed'] + check['received']).clip(lower=0)         #.clip(lower=0) is the pandas way of doing max(0, ...) across a whole column
    bad_rows = int((check["closing"] != check["expected_closing"]).sum())

    return pfep, stock_daily, kpi, bad_rows

pfep, stock_daily, kpi, bad_rows = build_data()


# ---------- Alert layer (Step 5) ----------

def stock_alerts(kpi):
    alerts = []

    for _, r in kpi.iterrows():
        if r['current_stock'] == 0:
            alerts.append(('STOCKOUT', f"{r['part_id']} is OUT OF STOCK at {r['location']}"))
        elif r['current_stock'] < r['reorder_point']:
            alerts.append(('REORDER', f"{r['part_id']} at {int(r['current_stock'])} units "
                           f"(reorder point {int(r['reorder_point'])}, ~{r['days_of_coverage']} days left)"))
        elif r['days_of_coverage'] < 4:
            alerts.append(('LOW COVERAGE', f"{r['part_id']} has only {r['days_of_coverage']} days left"))

    return alerts

alerts = stock_alerts(kpi)

# ---------- KPI tiles ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Parts tracked", len(kpi))
c2.metric("Below reorder point", int((kpi["current_stock"] < kpi["reorder_point"]).sum()))
c3.metric("Stockouts", int((kpi["current_stock"] == 0).sum()))
c4.metric("Data-quality issues", bad_rows)

# ---------- Alert panel ----------
st.subheader("⚠️ Stock Alerts")
if not alerts:
    st.success("All parts above reorder point.")
else:
    for level, msg in alerts:
        if level == "STOCKOUT":
            st.error(f"🔴 STOCKOUT — {msg}")
        elif level == "REORDER":
            st.warning(f"🟠 REORDER — {msg}")
        else:
            st.info(f"🟡 LOW COVERAGE — {msg}")

# ---------- Charts ----------
st.subheader("Days of Coverage by Part")
kpi_sorted = kpi.sort_values('days_of_coverage')
st.plotly_chart(
    px.bar(kpi_sorted, x="part_id", y="days_of_coverage", color='location',
           category_orders={'part_id': kpi_sorted['part_id'].tolist()},     #category_orders explicitly sets the left-to-right order of part_id to match your sorted list, so bars stay in coverage order and keep their location colors.
           title="Days of Coverage (lowest = most at risk)"),
    use_container_width=True)

st.subheader("Stock Level Over Time")
# Makes the dropdown menu
# stock_daily["part_id"] - the part_id column (600 rows — every part repeated 30 times).
# .unique() - collapses that to just the distinct part IDs (20 of them, no repeats).
# sorted(...) - puts them in order (P-1000, P-1001, …) so the dropdown is tidy.
# Streamlit draws a dropdown labeled "Select a part," filled with those 20 IDs.
#whatever the user picks is stored in part. Key Streamlit behavior: when the user changes the dropdown, the whole script re-runs, and part now holds the new selection — so everything below updates automatically.
part = st.selectbox("Select a part", sorted(stock_daily["part_id"].unique()))

# one keeps 30 True rows (whole 30 rows) of only one selected part. So one is the 30-day history of just the selected part.
one = stock_daily[stock_daily["part_id"] == part]

# pfep["part_id"] == part - boolean mask finding that part's row in the PFEP master.
# pfep.loc[<mask>, "reorder_point"] - .loc selects by label: the reorder_point value(s) for the matching row. This returns a Series (even though it's one value).
# .iloc[0] - grab the first (and only) value out of that Series by position — turning a one-element Series into a single scalar.
# int(...) - make it a clean integer.
# So rp = the reorder point number for the chosen part.
rp = int(pfep.loc[pfep["part_id"] == part, "reorder_point"].iloc[0])

# Builds the line chart
fig = px.line(one, x="date", y="closing", markers=True, title=f"{part} — daily closing stock")

# add_hline draws a horizontal line across the chart at height y=rp (the reorder point).
# line_dash="dash" - makes it a dashed line
# line_color="red" — makes the reorder line red.
# annotation_text=... - labels it "Reorder point (240)" or similar.
# annotation_font_color="red" — matches the label text color to the dash line color.
fig.add_hline(y=rp, line_dash="dash", line_color='orange', annotation_text=f"Reorder point ({rp})", annotation_font_color='orange')

# Displays the chart in Streamlit.
st.plotly_chart(fig, use_container_width=True)      #use_container_width=True stretches it to the full page width