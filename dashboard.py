import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CONFIG_PATH = "config.json"

st.set_page_config(page_title="Price Tracker", page_icon="📈", layout="wide")
st.title("📈 Amazon Price Tracker")


def load_config() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [data])


def run_scraper() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "scraper.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )
    output = result.stdout
    if result.stderr:
        output += "\n--- stderr ---\n" + result.stderr
    return result.returncode == 0, output.strip()


def load_csv(log_file: str) -> pd.DataFrame | None:
    path = Path(log_file)
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


products = load_config()

if not products:
    st.error("No products found in config.json.")
    st.stop()

# Sidebar — product selector
product_names = [p["name"] for p in products]
selected_name = st.sidebar.radio("Select product", product_names)
product = next(p for p in products if p["name"] == selected_name)

# Sidebar — run scraper
st.sidebar.divider()
st.sidebar.subheader("Update Prices")

n = len(products)
product_label = "product" if n == 1 else "products"

if st.sidebar.button(f"Run Scraper ({n} {product_label})", use_container_width=True):
    with st.sidebar.status("Scraping prices...", expanded=True) as status:
        success, output = run_scraper()
        if success:
            status.update(label="Scrape complete", state="complete", expanded=False)
        else:
            status.update(label="Scrape finished with errors", state="error", expanded=True)

    if output:
        st.sidebar.code(output, language=None)

    st.rerun()

df = load_csv(product["log_file"])
target = product["target_price"]

# ── Summary metrics ──────────────────────────────────────────────────────────
if df is not None and not df.empty:
    current_price = df["price"].iloc[-1]
    lowest_price = df["price"].min()
    highest_price = df["price"].max()
    below_target = current_price < target

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Price", f"${current_price:,.2f}",
                delta=f"{current_price - df['price'].iloc[-2]:+.2f}" if len(df) > 1 else None)
    col2.metric("Target Price", f"${target:,.2f}")
    col3.metric("Lowest Recorded", f"${lowest_price:,.2f}")
    col4.metric("Highest Recorded", f"${highest_price:,.2f}")

    if below_target:
        st.success(f"✅ Price is below your target of ${target:,.2f}! Now is a good time to buy.")
    else:
        gap = current_price - target
        st.info(f"📌 Price is ${gap:,.2f} above your target of ${target:,.2f}.")

    # ── Price history chart ───────────────────────────────────────────────────
    st.subheader("Price History")
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["price"],
        mode="lines+markers",
        name="Price",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=6),
        hovertemplate="%{x|%b %d %Y %H:%M}<br>$%{y:,.2f}<extra></extra>",
    ))

    fig.add_hline(
        y=target,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Target ${target:,.2f}",
        annotation_position="top right",
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        yaxis_tickprefix="$",
        hovermode="x unified",
        height=420,
        margin=dict(l=0, r=0, t=20, b=0),
    )

    st.plotly_chart(fig, width="stretch")

    # ── Raw data table ────────────────────────────────────────────────────────
    with st.expander("View raw data"):
        display = df[["timestamp", "price"]].copy()
        display["price"] = display["price"].map("${:,.2f}".format)
        display.columns = ["Timestamp", "Price"]
        st.dataframe(display, width="stretch", hide_index=True)

else:
    st.warning(f"No data found for **{selected_name}**. Use the **Run Scraper** button in the sidebar to fetch prices.")
