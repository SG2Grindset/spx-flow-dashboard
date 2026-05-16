# ============================================================
# pages/2_GEX_VEX_Heatmaps.py
# SG2 FLOW Dashboard - GEX / VEX Heatmap Page
# ============================================================

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from heatmap_engine import (
    get_heatmap_snapshot,
    pivot_to_plotly_heatmap_data,
    format_large_number,
)


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="SG2 GEX / VEX Heatmaps",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# SYMBOL CONFIG
# ============================================================
SYMBOLS = ["SPX", "XSP", "SPY", "QQQ", "TSLA", "AAPL"]

SYMBOL_ICONS = {
    "SPX": "📈",
    "XSP": "🧩",
    "SPY": "🕷️",
    "QQQ": "📊",
    "TSLA": "⚡",
    "AAPL": "🍎",
}

DEFAULT_STRIKE_WIDTH = {
    "SPX": 150,
    "XSP": 20,
    "SPY": 25,
    "QQQ": 25,
    "TSLA": 75,
    "AAPL": 25,
}


# ============================================================
# SESSION STATE
# ============================================================
if "heatmap_symbol" not in st.session_state:
    st.session_state.heatmap_symbol = "SPY"

symbol = st.session_state.heatmap_symbol


# ============================================================
# CSS
# ============================================================
st.markdown(
    """
<style>
html, body, .stApp {
    background: radial-gradient(circle at top left, #14202b 0%, #070b10 45%, #020407 100%) !important;
    color: #f4f7fb !important;
}

.main .block-container {
    padding-top: 1rem;
    padding-left: 1.4rem;
    padding-right: 1.4rem;
    max-width: 100%;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111922 0%, #070b10 100%) !important;
    border-right: 1px solid #263241;
}

[data-testid="stSidebar"] label {
    color: #ffdd00 !important;
    font-weight: 900 !important;
}

section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] select,
section[data-testid="stSidebar"] option,
section[data-testid="stSidebar"] div[data-baseweb="select"] span,
section[data-testid="stSidebar"] div[data-baseweb="input"] input {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    font-weight: 900 !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"],
section[data-testid="stSidebar"] div[data-baseweb="input"] {
    background-color: #ffffff !important;
    border-radius: 8px !important;
}

.stButton > button {
    height: 58px;
    border-radius: 13px;
    font-size: 17px;
    font-weight: 900;
    background: linear-gradient(180deg, #101923, #071018);
    border: 1px solid #8f7500;
    color: white;
    box-shadow: 0 0 16px rgba(0,0,0,.45);
}

.stButton > button[kind="primary"] {
    background: linear-gradient(180deg, #064225, #052417);
    border: 1px solid #00d46a;
    color: #ffffff;
    box-shadow: 0 0 22px rgba(0, 212, 106, .45);
}

.active-bar {
    width: 100%;
    padding: 15px 0;
    margin: 12px 0 14px 0;
    text-align: center;
    border-radius: 14px;
    color: #ffffff;
    font-size: 22px;
    font-weight: 900;
    background: linear-gradient(90deg, #064225, #06381f, #052416);
    border: 1px solid #00d46a;
    box-shadow: 0 0 24px rgba(0, 212, 106, .35);
}

.card {
    background: linear-gradient(180deg, #111923, #0b1118);
    border: 1px solid #263241;
    border-radius: 14px;
    padding: 15px 18px;
    box-shadow: 0 0 18px rgba(0,0,0,.35);
    margin-bottom: 12px;
}

.card-title {
    color: #ffdd00;
    font-size: 13px;
    font-weight: 900;
}

.card-value {
    color: white;
    font-size: 22px;
    font-weight: 900;
}

.green-text { color: #31e75f !important; }
.red-text { color: #ff4b4b !important; }
.yellow-text { color: #ffdd00 !important; }
.cyan-text { color: #00e5ff !important; }

.page-title {
    font-size: 28px;
    font-weight: 900;
    color: #ffffff;
    margin-bottom: 4px;
}

.page-subtitle {
    font-size: 14px;
    color: #b8c2cc;
    margin-bottom: 12px;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Heatmap Controls")

    auto_refresh = st.checkbox("Auto Refresh", value=True)

    refresh_interval = st.selectbox(
        "Refresh Interval",
        options=[10, 15, 30, 60],
        index=1,
    )

    exp_count = st.slider(
        "Expirations Count",
        min_value=1,
        max_value=10,
        value=5,
    )

    heatmap_type = st.selectbox(
        "Heatmap Type",
        options=["GEX", "VEX", "Premium"],
        index=0,
    )

    strike_width = st.slider(
        "Strike Width Around Spot",
        min_value=10,
        max_value=300,
        value=DEFAULT_STRIKE_WIDTH.get(symbol, 25),
        step=5,
    )

    show_values = st.checkbox("Show Cell Values", value=True)
    show_spot_marker = st.checkbox("Show Spot Marker", value=True)

    st.markdown("---")
    st.caption("GEX = Gamma Exposure approximation.")
    st.caption("VEX = Vanna-like exposure approximation.")
    st.caption("Rows = strikes. Columns = expirations.")


if auto_refresh:
    st_autorefresh(
        interval=refresh_interval * 1000,
        key="heatmap_refresh",
    )


# ============================================================
# HELPERS
# ============================================================
def metric_card(label, value, color_class=""):
    return f"""
    <div class="card">
        <div class="card-title">{label}</div>
        <div class="card-value {color_class}">{value}</div>
    </div>
    """


def safe_dict_value(d, key, default=0):
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def get_selected_pivot(snapshot, heatmap_type):
    if heatmap_type == "GEX":
        return snapshot.get("gex_pivot", pd.DataFrame()), "GEX"
    if heatmap_type == "VEX":
        return snapshot.get("vex_pivot", pd.DataFrame()), "VEX"
    return snapshot.get("premium_pivot", pd.DataFrame()), "Premium"


def build_heatmap_figure(
    pivot,
    symbol,
    spot,
    heatmap_type,
    show_values=True,
    show_spot_marker=True,
):
    x, y, z, text = pivot_to_plotly_heatmap_data(pivot)

    if not x or not y:
        return go.Figure()

    max_abs = max(abs(float(v)) for row in z for v in row) if z else 1

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            z=z,
            x=x,
            y=y,
            text=text if show_values else None,
            texttemplate="%{text}" if show_values else None,
            textfont=dict(color="white", size=12),
            colorscale=[
                [0.00, "#4b0055"],
                [0.25, "#283a78"],
                [0.50, "#315f95"],
                [0.75, "#22a884"],
                [1.00, "#f7e225"],
            ],
            zmid=0,
            zmin=-max_abs,
            zmax=max_abs,
            colorbar=dict(
                title=heatmap_type,
                tickfont=dict(color="white"),
                titlefont=dict(color="white"),
            ),
            hovertemplate=(
                "Expiration: %{x}<br>"
                "Strike: %{y}<br>"
                f"{heatmap_type}: %{{text}}"
                "<extra></extra>"
            ),
        )
    )

    if show_spot_marker and spot:
        fig.add_hline(
            y=spot,
            line_color="white",
            line_width=3,
            annotation_text=f"Spot {spot:.2f}",
            annotation_position="left",
        )

    fig.update_layout(
        title=f"{symbol} {heatmap_type} Heatmap",
        template="plotly_dark",
        paper_bgcolor="#0b1118",
        plot_bgcolor="#252a2f",
        height=720,
        margin=dict(l=70, r=40, t=60, b=50),
        xaxis=dict(
            title="Expiration",
            tickfont=dict(color="white", size=13),
            titlefont=dict(color="white"),
            side="top",
        ),
        yaxis=dict(
            title="Strike",
            tickfont=dict(color="white", size=13),
            titlefont=dict(color="white"),
            autorange="reversed",
        ),
        font=dict(color="white"),
    )

    return fig


# ============================================================
# TOP SYMBOL BUTTONS
# ============================================================
st.markdown('<div class="page-title">🔥 SG2 GEX / VEX Heatmaps</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Dealer exposure by strike and expiration. Use this page to identify gamma walls, vanna zones, and pressure pockets.</div>',
    unsafe_allow_html=True,
)

symbol_cols = st.columns(len(SYMBOLS))

for i, sym in enumerate(SYMBOLS):
    icon = SYMBOL_ICONS.get(sym, "📊")
    is_active = sym == st.session_state.heatmap_symbol

    with symbol_cols[i]:
        if st.button(
            f"{icon}  {sym}",
            key=f"heatmap_symbol_button_{sym}_{i}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.heatmap_symbol = sym
            st.rerun()

symbol = st.session_state.heatmap_symbol
icon = SYMBOL_ICONS.get(symbol, "📊")

st.markdown(
    f"""
    <div class="active-bar">
        ACTIVE HEATMAP: &nbsp; {icon} &nbsp; {symbol} &nbsp; | &nbsp; {heatmap_type}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOAD DATA
# ============================================================
try:
    snapshot = get_heatmap_snapshot(
        symbol=symbol,
        exp_count=exp_count,
        strike_width=strike_width,
    )
except Exception as e:
    st.error(f"Could not load heatmap data for {symbol}: {e}")
    st.stop()


spot = snapshot.get("spot", 0)
expirations = snapshot.get("expirations", [])
chain_df = snapshot.get("chain_df", pd.DataFrame())

pivot, selected_label = get_selected_pivot(snapshot, heatmap_type)


# ============================================================
# METRIC CARDS
# ============================================================
top_positive_gex = snapshot.get("top_positive_gex")
top_negative_gex = snapshot.get("top_negative_gex")
top_positive_vex = snapshot.get("top_positive_vex")
top_negative_vex = snapshot.get("top_negative_vex")

m1, m2, m3, m4, m5 = st.columns(5)

m1.markdown(
    metric_card("Spot", f"{spot:.2f}", "green-text"),
    unsafe_allow_html=True,
)

m2.markdown(
    metric_card("Expirations Used", len(expirations), "yellow-text"),
    unsafe_allow_html=True,
)

m3.markdown(
    metric_card("Chain Rows", len(chain_df), "cyan-text"),
    unsafe_allow_html=True,
)

if heatmap_type == "GEX":
    pos_strike = safe_dict_value(top_positive_gex, "strike", 0)
    pos_value = safe_dict_value(top_positive_gex, "gex", 0)
    neg_strike = safe_dict_value(top_negative_gex, "strike", 0)
    neg_value = safe_dict_value(top_negative_gex, "gex", 0)

    m4.markdown(
        metric_card(
            "Top +GEX",
            f"{pos_strike:.2f} / {format_large_number(pos_value)}",
            "green-text",
        ),
        unsafe_allow_html=True,
    )

    m5.markdown(
        metric_card(
            "Top -GEX",
            f"{neg_strike:.2f} / {format_large_number(neg_value)}",
            "red-text",
        ),
        unsafe_allow_html=True,
    )

elif heatmap_type == "VEX":
    pos_strike = safe_dict_value(top_positive_vex, "strike", 0)
    pos_value = safe_dict_value(top_positive_vex, "vex", 0)
    neg_strike = safe_dict_value(top_negative_vex, "strike", 0)
    neg_value = safe_dict_value(top_negative_vex, "vex", 0)

    m4.markdown(
        metric_card(
            "Top +VEX",
            f"{pos_strike:.2f} / {format_large_number(pos_value)}",
            "green-text",
        ),
        unsafe_allow_html=True,
    )

    m5.markdown(
        metric_card(
            "Top -VEX",
            f"{neg_strike:.2f} / {format_large_number(neg_value)}",
            "red-text",
        ),
        unsafe_allow_html=True,
    )

else:
    total_premium = pivot.values.sum() if pivot is not None and not pivot.empty else 0
    abs_premium = abs(pivot.values).sum() if pivot is not None and not pivot.empty else 0

    m4.markdown(
        metric_card("Net Premium", format_large_number(total_premium), "yellow-text"),
        unsafe_allow_html=True,
    )

    m5.markdown(
        metric_card("Gross Premium", format_large_number(abs_premium), "cyan-text"),
        unsafe_allow_html=True,
    )


# ============================================================
# HEATMAP
# ============================================================
if pivot is None or pivot.empty:
    st.warning("No heatmap data available for this symbol/settings.")
else:
    fig = build_heatmap_figure(
        pivot=pivot,
        symbol=symbol,
        spot=spot,
        heatmap_type=selected_label,
        show_values=show_values,
        show_spot_marker=show_spot_marker,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


# ============================================================
# INTERPRETATION
# ============================================================
with st.expander("How to read this heatmap", expanded=True):
    st.markdown(
        """
### What this page shows

Rows are **strikes**.  
Columns are **expirations**.  
Each cell shows exposure at that strike and expiration.

### GEX

**Positive GEX** usually represents call-side dealer positioning or stabilizing zones.  
**Negative GEX** usually represents put-side pressure or volatility expansion zones.

Use large positive/negative nodes as:

- reaction zones
- magnets
- support/resistance
- breakout confirmation levels
- potential reversal zones

### VEX

VEX is a vanna-like exposure estimate.

Use it to identify:

- volatility sensitivity zones
- spots where changes in IV may affect dealer hedging
- areas where price movement can accelerate if volatility shifts

### Best trading read

The strongest heatmap levels are the ones that line up with:

- current spot
- FLOW X dots
- 0DTE flow direction
- All Exp flow direction
- gamma regime
- SPX/SPY/QQQ alignment
        """
    )


# ============================================================
# FOOTER
# ============================================================
st.caption(
    "GEX/VEX are approximations based on available option chain Greeks. Not financial advice. Data may be delayed."
)