import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

CONFIG_PATH = "config.json"

PALETTE = [
    "#4F46E5", "#10B981", "#F59E0B", "#EF4444",
    "#8B5CF6", "#06B6D4", "#EC4899", "#64748B",
]

st.set_page_config(page_title="Price Tracker", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Hero header */
        .hero {
            background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
            color: #fff;
            padding: 28px 32px;
            border-radius: 14px;
            margin-bottom: 24px;
            box-shadow: 0 4px 16px rgba(79, 70, 229, 0.18);
        }
        .hero h1 { color: #fff; margin: 0 0 4px 0; font-weight: 700; font-size: 1.9rem; }
        .hero p  { color: rgba(255,255,255,0.85); margin: 0; font-size: 0.95rem; }

        /* Bordered containers → lift on hover */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0,0,0,0.08);
        }

        /* Section headers get a little indigo accent bar */
        [data-testid="stMarkdownContainer"] h2 {
            position: relative;
            padding-left: 14px;
            margin-top: 1.6rem;
        }
        [data-testid="stMarkdownContainer"] h2::before {
            content: "";
            position: absolute;
            left: 0; top: 8px; bottom: 8px;
            width: 4px;
            background: #4F46E5;
            border-radius: 2px;
        }

        /* Status pills */
        .pill {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .pill-ok   { background: #D1FAE5; color: #047857; }
        .pill-warn { background: #FEF3C7; color: #92400E; }

        /* Muted caption line */
        .muted { color: #6B7280; font-size: 0.82rem; }

        /* Compact right-aligned Amazon link */
        .amz-link { font-size: 0.82rem; color: #4F46E5; text-decoration: none; }
        .amz-link:hover { text-decoration: underline; }

        /* Product card image sizing */
        div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stImage"] img {
            max-height: 160px;
            object-fit: contain;
            margin: 0 auto;
            display: block;
        }

        /* Empty state */
        .empty-state {
            text-align: center;
            color: #6B7280;
            padding: 40px 20px;
            font-size: 0.95rem;
        }

        /* Hide "Made with Streamlit" footer */
        footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

st.markdown(
    '<div class="hero"><h1>Amazon Price Tracker</h1>'
    '<p>Watch prices. Buy at the bottom.</p></div>',
    unsafe_allow_html=True,
)


# ── Config helpers ───────────────────────────────────────────────────────────

def load_config() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [data])


def save_config(products: list[dict]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"products": products}, f, indent=2, ensure_ascii=False)
        f.write("\n")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# ── Scraper runner ───────────────────────────────────────────────────────────

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


# ── Chart styling ────────────────────────────────────────────────────────────

def style_fig(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        yaxis_tickprefix="$",
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#374151", size=12),
        xaxis=dict(showgrid=False, showline=True, linecolor="#E5E7EB", linewidth=1),
        yaxis=dict(gridcolor="#F3F4F6", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def render_price_chart(df: pd.DataFrame, target: float, height: int = 440) -> go.Figure:
    """Full-featured single-product chart: buy-zone, spline+fill, target line,
    low annotation, range selector. Used by Home and Product Detail."""
    fig = go.Figure()

    fig.add_hrect(
        y0=0, y1=target,
        fillcolor="#10B981", opacity=0.07, line_width=0,
        layer="below",
    )

    fig.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["price"],
        mode="lines+markers",
        name="Price",
        line=dict(color=PALETTE[0], width=2.5, shape="spline", smoothing=0.6),
        marker=dict(size=5, color=PALETTE[0]),
        fill="tozeroy",
        fillcolor="rgba(79, 70, 229, 0.08)",
        hovertemplate="%{x|%b %d %Y %H:%M}<br>$%{y:,.2f}<extra></extra>",
    ))

    fig.add_hline(
        y=target,
        line_dash="dash",
        line_color="#EF4444",
        annotation_text=f"Target ${target:,.2f}",
        annotation_position="top right",
        annotation_font_color="#EF4444",
    )

    low_idx = df["price"].idxmin()
    fig.add_annotation(
        x=df["timestamp"].iloc[low_idx],
        y=df["price"].iloc[low_idx],
        text=f"Low ${df['price'].min():,.2f}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#10B981",
        ax=0, ay=-36,
        font=dict(color="#047857", size=11, family="Inter, sans-serif"),
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="#10B981",
        borderwidth=1,
        borderpad=4,
    )

    style_fig(fig, height=height)
    fig.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        yaxis=dict(
            gridcolor="#F3F4F6",
            zeroline=False,
            range=[max(0, df["price"].min() * 0.9), df["price"].max() * 1.05],
        ),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor="#E5E7EB",
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="#F3F4F6",
                activecolor="#4F46E5",
                font=dict(color="#111827"),
            ),
        ),
    )
    return fig


# ── Load products ────────────────────────────────────────────────────────────

products = load_config()

# ── Sidebar — navigation ────────────────────────────────────────────────────

st.sidebar.subheader("Pages")
page = st.sidebar.radio(
    "Navigation",
    ["Home", "Product Detail", "Compare Products", "Manage Products"],
    label_visibility="collapsed",
)

# ── Sidebar — run scraper ────────────────────────────────────────────────────

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


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Home (overview of all products)
# ═════════════════════════════════════════════════════════════════════════════

if page == "Home":
    if not products:
        st.warning("No products configured. Go to **Manage Products** to add one.")
        st.stop()

    st.header("Overview")

    # Build summary data for every product
    alerts: list[str] = []
    cards: list[dict] = []
    for p in products:
        df = load_csv(p["log_file"])
        if df is not None and not df.empty:
            current = df["price"].iloc[-1]
            low = df["price"].min()
            delta = current - df["price"].iloc[-2] if len(df) > 1 else 0.0
            below = current < p["target_price"]
            if below:
                alerts.append(p["name"])
            cards.append({
                "name": p["name"],
                "current": current,
                "target": p["target_price"],
                "low": low,
                "delta": delta,
                "below": below,
                "points": len(df),
                "last_checked": df["timestamp"].iloc[-1],
                "image_url": p.get("image_url", "").strip(),
                "url": p["url"],
            })
        else:
            cards.append({
                "name": p["name"],
                "current": None,
                "target": p["target_price"],
                "low": None,
                "delta": 0.0,
                "below": False,
                "points": 0,
                "last_checked": None,
                "image_url": p.get("image_url", "").strip(),
                "url": p["url"],
            })

    # Alert banner
    if alerts:
        names = ", ".join(f"**{a}**" for a in alerts)
        st.success(f"Price alert! {names} {'is' if len(alerts) == 1 else 'are'} below target.")

    # Metric cards in a grid
    cols = st.columns(min(len(cards), 3))
    for i, card in enumerate(cards):
        col = cols[i % len(cols)]
        with col:
            with st.container(border=True):
                if card["image_url"]:
                    st.image(card["image_url"], use_container_width=True)

                st.subheader(card["name"])

                if card["current"] is not None:
                    st.metric(
                        "Current Price",
                        f"${card['current']:,.2f}",
                        delta=f"{card['delta']:+.2f}" if card["delta"] else None,
                        delta_color="inverse",
                    )
                    gap = card["current"] - card["target"]
                    if card["below"]:
                        pill = f'<span class="pill pill-ok">${abs(gap):,.2f} below target</span>'
                    else:
                        pill = f'<span class="pill pill-warn">${gap:,.2f} above target</span>'
                    st.markdown(pill, unsafe_allow_html=True)

                    st.markdown(
                        f'<div class="muted" style="margin-top:8px">'
                        f'Low ${card["low"]:,.2f} · {card["points"]} points · '
                        f'Last checked {card["last_checked"]:%b %d, %H:%M}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="muted">No data yet — run the scraper.</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div style="margin-top:10px;text-align:right">'
                    f'<a class="amz-link" href="{card["url"]}" target="_blank">↗ Amazon</a>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Per-product price history charts (same style as Product Detail page)
    products_with_data = [
        (p, load_csv(p["log_file"]))
        for p, card in zip(products, cards)
        if card["current"] is not None
    ]

    if products_with_data:
        st.subheader("Price History")
        for p, df in products_with_data:
            st.markdown(f"**{p['name']}**")
            st.plotly_chart(
                render_price_chart(df, p["target_price"], height=360),
                use_container_width=True,
                key=f"home_chart_{slugify(p['name'])}",
            )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Product Detail (single-product view)
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Product Detail":
    if not products:
        st.warning("No products configured. Go to **Manage Products** to add one.")
        st.stop()

    product_names = [p["name"] for p in products]
    selected_name = st.selectbox("Select product", product_names)
    product = next(p for p in products if p["name"] == selected_name)

    st.header(selected_name)
    st.markdown(f"[View on Amazon]({product['url']})")

    df = load_csv(product["log_file"])
    target = product["target_price"]

    if df is not None and not df.empty:
        current_price = df["price"].iloc[-1]
        lowest_price = df["price"].min()
        highest_price = df["price"].max()
        below_target = current_price < target

        col1, col2, col3, col4 = st.columns(4)
        col1.metric(
            "Current Price",
            f"${current_price:,.2f}",
            delta=f"{current_price - df['price'].iloc[-2]:+.2f}" if len(df) > 1 else None,
            delta_color="inverse",
        )
        col2.metric("Target Price", f"${target:,.2f}")
        col3.metric("Lowest Recorded", f"${lowest_price:,.2f}")
        col4.metric("Highest Recorded", f"${highest_price:,.2f}")

        if below_target:
            st.success(f"✅ Price is below your target of ${target:,.2f}! Now is a good time to buy.")
        else:
            gap = current_price - target
            st.info(f"📌 Price is ${gap:,.2f} above your target of ${target:,.2f}.")

        # ── Price history chart ──────────────────────────────────────────
        st.subheader("Price History")
        st.plotly_chart(
            render_price_chart(df, target, height=440),
            use_container_width=True,
        )

        # ── Raw data table ───────────────────────────────────────────────
        with st.expander("View raw data"):
            display = df[["timestamp", "price"]].copy()
            display["price"] = display["price"].map("${:,.2f}".format)
            display.columns = ["Timestamp", "Price"]
            st.dataframe(display, use_container_width=True, hide_index=True)

    else:
        st.warning(
            f"No data found for **{selected_name}**. "
            "Use the **Run Scraper** button in the sidebar to fetch prices."
        )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Compare Products
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Compare Products":
    st.header("Compare Products")

    if len(products) < 2:
        st.info("Add at least two products to compare them.")
        st.stop()

    product_names = [p["name"] for p in products]
    selected = st.multiselect(
        "Select products to compare",
        product_names,
        default=product_names,
    )

    if len(selected) < 2:
        st.info("Select at least two products to compare.")
        st.stop()

    selected_products = [p for p in products if p["name"] in selected]

    # ── Summary table ────────────────────────────────────────────────────
    rows = []
    dataframes: dict[str, pd.DataFrame] = {}
    for p in selected_products:
        df = load_csv(p["log_file"])
        if df is not None and not df.empty:
            dataframes[p["name"]] = df
            current = df["price"].iloc[-1]
            rows.append({
                "Product": p["name"],
                "Current Price": f"${current:,.2f}",
                "Target": f"${p['target_price']:,.2f}",
                "Low": f"${df['price'].min():,.2f}",
                "High": f"${df['price'].max():,.2f}",
                "vs Target": f"${current - p['target_price']:+,.2f}",
            })
        else:
            rows.append({
                "Product": p["name"],
                "Current Price": "No data",
                "Target": f"${p['target_price']:,.2f}",
                "Low": "–",
                "High": "–",
                "vs Target": "–",
            })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if not dataframes:
        st.warning("No price data yet. Run the scraper first.")
        st.stop()

    # ── Overlay chart ────────────────────────────────────────────────────
    st.subheader("Price History Comparison")

    fig = go.Figure()
    for i, (name, df) in enumerate(dataframes.items()):
        color = PALETTE[i % len(PALETTE)]
        fig.add_trace(go.Scatter(
            x=df["timestamp"],
            y=df["price"],
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=2.5, shape="spline", smoothing=0.6),
            marker=dict(size=5, color=color),
            hovertemplate=f"{name}<br>" + "%{x|%b %d %Y %H:%M}<br>$%{y:,.2f}<extra></extra>",
        ))

    show_targets = st.checkbox("Show target prices", value=True)
    if show_targets:
        for i, p in enumerate(selected_products):
            if p["name"] in dataframes:
                color = PALETTE[i % len(PALETTE)]
                fig.add_hline(
                    y=p["target_price"],
                    line_dash="dot",
                    line_color=color,
                    opacity=0.5,
                    annotation_text=f"{p['name']} target",
                    annotation_position="top right",
                    annotation_font_size=10,
                )

    style_fig(fig, height=500)

    st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Manage Products
# ═════════════════════════════════════════════════════════════════════════════

elif page == "Manage Products":
    st.header("Manage Products")

    # ── Edit existing products ───────────────────────────────────────────
    if products:
        st.subheader("Edit Products")

        updated_products = []
        removed_indices: set[int] = set()

        for i, p in enumerate(products):
            with st.expander(p["name"], expanded=False):
                col_form, col_btn = st.columns([5, 1])
                with col_form:
                    new_name = st.text_input("Name", value=p["name"], key=f"name_{i}")
                    new_url = st.text_input("URL", value=p["url"], key=f"url_{i}")
                    new_target = st.number_input(
                        "Target Price ($)",
                        value=p["target_price"],
                        min_value=0.0,
                        step=10.0,
                        format="%.2f",
                        key=f"target_{i}",
                    )
                    new_log = st.text_input("Log File", value=p["log_file"], key=f"log_{i}")
                    new_image = st.text_input(
                        "Image URL (optional)",
                        value=p.get("image_url", ""),
                        placeholder="https://m.media-amazon.com/images/...",
                        key=f"image_{i}",
                    )
                with col_btn:
                    st.write("")  # spacer
                    if st.button("Remove", key=f"remove_{i}", type="secondary"):
                        removed_indices.add(i)

                updated_products.append({
                    "name": new_name.strip(),
                    "url": new_url.strip(),
                    "target_price": new_target,
                    "log_file": new_log.strip(),
                    "image_url": new_image.strip(),
                })

        # Apply removals
        final_products = [p for i, p in enumerate(updated_products) if i not in removed_indices]

        if removed_indices:
            save_config(final_products)
            st.rerun()

        if st.button("Save Changes", type="primary", use_container_width=True):
            save_config(final_products)
            st.success("Config saved.")
            st.rerun()

    else:
        st.info("No products configured yet. Add one below.")

    # ── Add new product ──────────────────────────────────────────────────
    st.divider()
    st.subheader("Add Product")

    with st.form("add_product", clear_on_submit=True):
        new_name = st.text_input("Product Name", placeholder="e.g. MacBook Air M5")
        new_url = st.text_input("Amazon URL", placeholder="https://www.amazon.com/...")
        new_target = st.number_input(
            "Target Price ($)", value=0.0, min_value=0.0, step=10.0, format="%.2f"
        )
        new_log = st.text_input(
            "Log File (optional)",
            placeholder="auto-generated from name if left blank",
        )
        new_image = st.text_input(
            "Image URL (optional)",
            placeholder="https://m.media-amazon.com/images/...",
        )
        submitted = st.form_submit_button("Add Product", type="primary")

    if submitted:
        new_name = new_name.strip()
        new_url = new_url.strip()
        new_log = new_log.strip()
        new_image = new_image.strip()

        if not new_name:
            st.error("Product name is required.")
        elif not new_url:
            st.error("Amazon URL is required.")
        elif any(p["name"] == new_name for p in products):
            st.error(f"A product named **{new_name}** already exists.")
        else:
            if not new_log:
                new_log = slugify(new_name) + ".csv"
            products.append({
                "name": new_name,
                "url": new_url,
                "target_price": new_target,
                "log_file": new_log,
                "image_url": new_image,
            })
            save_config(products)
            st.success(f"Added **{new_name}**.")
            st.rerun()
