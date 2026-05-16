import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from flow_engine import get_flow_snapshot


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="SG2 FLOW Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# SYMBOL CONFIG
# =========================================================
SYMBOLS = ["SPX", "SPY", "QQQ", "TSLA", "AAPL"]

SYMBOL_ICONS = {
    "SPX": "📈",
    "SPY": "🕷️",
    "QQQ": "📊",
    "TSLA": "⚡",
    "AAPL": "🍎",
}

FLOW_DOT_THRESHOLDS = {
    "SPX": 100_000_000,
    "SPY": 25_000_000,
    "QQQ": 25_000_000,
    "TSLA": 75_000_000,
    "AAPL": 25_000_000,
}

DIVERGENCE_THRESHOLDS = {
    "SPX": 30_000_000,
    "SPY": 10_000_000,
    "QQQ": 10_000_000,
    "TSLA": 20_000_000,
    "AAPL": 10_000_000,
}

PULSE_DROP_THRESHOLDS = {
    "SPX": 100_000_000,
    "SPY": 25_000_000,
    "QQQ": 25_000_000,
    "TSLA": 75_000_000,
    "AAPL": 25_000_000,
}

PRICE_SCALE = {
    "SPX": 5,
    "SPY": 0.5,
    "QQQ": 0.5,
    "TSLA": 2.5,
    "AAPL": 0.5,
}


# =========================================================
# SESSION STATE
# =========================================================
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "SPX"

symbol = st.session_state.selected_symbol


# =========================================================
# CSS
# =========================================================
st.markdown(
    """
<style>
html, body, [class*="css"] {
    background-color: #0b1117;
    color: #f4f7fb;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111922 0%, #0b1117 100%);
    border-right: 1px solid #263241;
}

[data-testid="stSidebar"] label {
    color: #ffdd00 !important;
    font-weight: 800 !important;
}

.stButton > button {
    height: 64px;
    border-radius: 14px;
    font-size: 18px;
    font-weight: 900;
    background: linear-gradient(180deg, #101923, #081018);
    border: 1px solid #8f7500;
    color: white;
    box-shadow: 0 0 16px rgba(0,0,0,.35);
}

.stButton > button[kind="primary"] {
    background: linear-gradient(180deg, #063f27, #052417);
    border: 1px solid #00d46a;
    color: #ffffff;
    box-shadow: 0 0 20px rgba(0, 212, 106, .35);
}

.active-bar {
    width: 100%;
    padding: 18px 0;
    margin: 16px 0 18px 0;
    text-align: center;
    border-radius: 14px;
    color: #ffffff;
    font-size: 22px;
    font-weight: 900;
    background: linear-gradient(90deg, #064225, #073f25, #052416);
    border: 1px solid #00d46a;
    box-shadow: 0 0 22px rgba(0, 212, 106, .35);
}

.metric-card {
    background: linear-gradient(180deg, #111923, #0d141d);
    border: 1px solid #263241;
    border-radius: 14px;
    padding: 16px 22px;
    margin-bottom: 14px;
}

.metric-label {
    color: #ffdd00;
    font-size: 14px;
    font-weight: 900;
}

.metric-value {
    color: #f5f7fb;
    font-size: 23px;
    font-weight: 900;
}

.green-text {
    color: #31e75f !important;
}

.red-text {
    color: #ff4b4b !important;
}

.yellow-text {
    color: #ffdd00 !important;
}

.header-card {
    background: linear-gradient(180deg, #111923, #0d141d);
    border-radius: 14px;
    padding: 18px 22px;
    margin: 10px 0;
}

.matrix-card {
    background: linear-gradient(180deg, #111923, #0d141d);
    border: 1px solid #263241;
    border-radius: 14px;
    padding: 18px;
}

.matrix-title {
    color: white;
    font-size: 22px;
    font-weight: 900;
    margin-bottom: 12px;
}

.small-note {
    color: #a8b2c1;
    font-size: 13px;
}

hr {
    border-color: #263241;
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    auto_refresh = st.checkbox("Auto Refresh", value=True)

    refresh_interval = st.selectbox(
        "Refresh Interval",
        options=[5, 10, 15, 30, 60],
        index=2,
        key="refresh_interval",
    )

    all_exp_count = st.slider(
        "All Expirations Count",
        min_value=1,
        max_value=10,
        value=5,
        key="all_exp_count",
    )

    chart_bucket = st.selectbox(
        "Chart Bucket",
        options=[1, 3, 5],
        index=0,
        key="chart_bucket",
    )

    lookback_hours = st.slider(
        "Lookback Hours",
        min_value=1,
        max_value=8,
        value=2,
        key="lookback_hours",
    )

    show_flow_dots = st.checkbox("Show FLOW Dots", value=True)

    default_flow_dot_threshold = FLOW_DOT_THRESHOLDS.get(symbol, 25_000_000)
    default_divergence_threshold = DIVERGENCE_THRESHOLDS.get(symbol, 10_000_000)
    default_pulse_drop_threshold = PULSE_DROP_THRESHOLDS.get(symbol, 25_000_000)

    flow_dot_threshold = st.number_input(
        "FLOW Dot Threshold",
        min_value=0,
        value=default_flow_dot_threshold,
        step=1_000_000,
        key=f"flow_dot_threshold_{symbol}",
    )
    st.caption(f"Default for {symbol}: {default_flow_dot_threshold:,}")

    show_matrix = st.checkbox("Show SG2 Flow Matrix", value=True)

    divergence_threshold = st.number_input(
        "Divergence Threshold",
        min_value=0,
        value=default_divergence_threshold,
        step=1_000_000,
        key=f"divergence_threshold_{symbol}",
    )

    pulse_drop_threshold = st.number_input(
        "Pulse/Drop Threshold",
        min_value=0,
        value=default_pulse_drop_threshold,
        step=1_000_000,
        key=f"pulse_drop_threshold_{symbol}",
    )

    strike_width = st.slider(
        "Strike Width Around Spot",
        min_value=25,
        max_value=300,
        value=100,
        step=25,
        key=f"strike_width_{symbol}",
    )

    st.markdown("---")
    st.caption("Primary chart model: Premium Flow = Option Price × Contracts × 100.")
    st.caption("Secondary bias model: Signed Delta Notional = Spot × Delta × Contracts × 100.")


if auto_refresh:
    st_autorefresh(
        interval=refresh_interval * 1000,
        key="flow_refresh_main",
    )


# =========================================================
# HELPERS
# =========================================================
def fmt_money(value):
    try:
        value = float(value)
    except Exception:
        return "0"

    abs_val = abs(value)

    if abs_val >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def metric_html(label, value, color_class=""):
    return f"""
    <div>
        <div class="metric-label">{label}</div>
        <div class="metric-value {color_class}">{value}</div>
    </div>
    """


def get_color_class(value):
    try:
        value = float(value)
    except Exception:
        return ""

    if value > 0:
        return "green-text"
    if value < 0:
        return "red-text"
    return ""


def build_signal_status(value):
    if value > 0:
        return "BULLISH"
    if value < 0:
        return "BEARISH"
    return "NEUTRAL"


def signal_dot(status):
    if status == "BULLISH":
        return "🟢"
    if status == "BEARISH":
        return "🔴"
    return "🟣"


def safe_get(snapshot, key, default=0):
    if not isinstance(snapshot, dict):
        return default
    return snapshot.get(key, default)


# =========================================================
# SYMBOL BUTTONS
# =========================================================
symbol_cols = st.columns(len(SYMBOLS))

for i, sym in enumerate(SYMBOLS):
    icon = SYMBOL_ICONS.get(sym, "📊")
    is_active = sym == st.session_state.selected_symbol

    with symbol_cols[i]:
        if st.button(
            f"{icon}  {sym}",
            key=f"symbol_button_{sym}_{i}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.selected_symbol = sym
            st.rerun()

symbol = st.session_state.selected_symbol
icon = SYMBOL_ICONS.get(symbol, "📊")

st.markdown(
    f"""
    <div class="active-bar">
        ACTIVE: &nbsp; {icon} &nbsp; {symbol}
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# LOAD DATA
# =========================================================
try:
    snapshot = get_flow_snapshot(
        symbol=symbol,
        all_exp_count=all_exp_count,
        chart_bucket=chart_bucket,
        lookback_hours=lookback_hours,
        strike_width=strike_width,
    )
except TypeError:
    snapshot = get_flow_snapshot(symbol)
except Exception as e:
    st.error(f"Could not load flow data for {symbol}: {e}")
    st.stop()


spot = safe_get(snapshot, "spot", 0)
exp_date = safe_get(snapshot, "expiration", "")
odte_exp = safe_get(snapshot, "odte_exp", exp_date)

odte_premium_net = safe_get(snapshot, "odte_premium_net", 0)
all_exp_premium_net = safe_get(snapshot, "all_exp_premium_net", 0)

odte_signed_delta = safe_get(snapshot, "odte_signed_delta", 0)
odte_delta_bias = safe_get(snapshot, "odte_delta_bias", "NEUTRAL")
all_exp_delta_bias = safe_get(snapshot, "all_exp_delta_bias", "NEUTRAL")

call_gamma = safe_get(snapshot, "call_gamma", 0)
put_gamma = safe_get(snapshot, "put_gamma", 0)
gamma_regime = safe_get(snapshot, "gamma_regime", "NEUTRAL")

odte_rows = safe_get(snapshot, "odte_rows", 0)
all_exp_rows = safe_get(snapshot, "all_exp_rows", 0)

chart_df = safe_get(snapshot, "chart_df", pd.DataFrame())


# =========================================================
# METRIC GRID
# =========================================================
st.markdown('<div class="metric-card">', unsafe_allow_html=True)

r1 = st.columns(5)
r1[0].markdown(metric_html("Spot", f"{spot:.2f}" if spot else "0"), unsafe_allow_html=True)
r1[1].markdown(metric_html("0DTE Premium Net", fmt_money(odte_premium_net), get_color_class(odte_premium_net)), unsafe_allow_html=True)
r1[2].markdown(metric_html("All Exp Premium Net", fmt_money(all_exp_premium_net), get_color_class(all_exp_premium_net)), unsafe_allow_html=True)
r1[3].markdown(metric_html("Call Gamma", f"{call_gamma:.2f}" if call_gamma else "0", "green-text"), unsafe_allow_html=True)
r1[4].markdown(metric_html("Put Gamma", f"{put_gamma:.2f}" if put_gamma else "0", "green-text"), unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

r2 = st.columns(6)
r2[0].markdown(metric_html("0DTE Signed Delta", fmt_money(odte_signed_delta), get_color_class(odte_signed_delta)), unsafe_allow_html=True)
r2[1].markdown(metric_html("0DTE Delta Bias", odte_delta_bias, "red-text" if "BEAR" in str(odte_delta_bias) else "green-text" if "BULL" in str(odte_delta_bias) else ""), unsafe_allow_html=True)
r2[2].markdown(metric_html("All Exp Delta Bias", all_exp_delta_bias, "red-text" if "BEAR" in str(all_exp_delta_bias) else "green-text" if "BULL" in str(all_exp_delta_bias) else ""), unsafe_allow_html=True)
r2[3].markdown(metric_html("Gamma Regime", gamma_regime, "red-text" if "BELOW" in str(gamma_regime) or "BEAR" in str(gamma_regime) else "green-text" if "ABOVE" in str(gamma_regime) or "BULL" in str(gamma_regime) else ""), unsafe_allow_html=True)
r2[4].markdown(metric_html("0DTE Rows", odte_rows), unsafe_allow_html=True)
r2[5].markdown(metric_html("All Exp Rows", all_exp_rows), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# HEADER
# =========================================================
today_txt = datetime.now().strftime("%A, %B %d, %Y")

st.markdown(
    f"""
    <div class="header-card">
        <div style="font-size:26px;font-weight:900;color:white;">{symbol} {today_txt}</div>
        <div style="font-size:15px;font-weight:800;color:white;margin-top:8px;">
            Spot: <span class="green-text">{spot:.2f}</span>
            &nbsp;&nbsp; | &nbsp;&nbsp;
            0DTE Exp: <span class="yellow-text">{odte_exp}</span>
            &nbsp;&nbsp; | &nbsp;&nbsp;
            <span class="yellow-text">0DTE Flow:</span> {fmt_money(odte_premium_net)}
            &nbsp;&nbsp; | &nbsp;&nbsp;
            All Exp Used: {all_exp_count}
            &nbsp;&nbsp; | &nbsp;&nbsp;
            <span class="yellow-text">All Exp Flow:</span> {fmt_money(all_exp_premium_net)}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# CHART + MATRIX LAYOUT
# =========================================================
left_chart, right_matrix = st.columns([2.2, 1])

with left_chart:
    fig = go.Figure()

    if isinstance(chart_df, pd.DataFrame) and not chart_df.empty:
        x_col = "time" if "time" in chart_df.columns else chart_df.columns[0]

        if "premium_flow" in chart_df.columns:
            flow_col = "premium_flow"
        elif "flow" in chart_df.columns:
            flow_col = "flow"
        elif "net_flow" in chart_df.columns:
            flow_col = "net_flow"
        else:
            flow_col = None

        price_col = "price" if "price" in chart_df.columns else "spot" if "spot" in chart_df.columns else None

        if flow_col:
            bullish = chart_df[chart_df[flow_col] > 0]
            bearish = chart_df[chart_df[flow_col] < 0]
            neutral = chart_df[chart_df[flow_col] == 0]

            fig.add_trace(
                go.Bar(
                    x=bullish[x_col],
                    y=bullish[flow_col],
                    name="Bullish Flow",
                    marker_color="#28e337",
                    opacity=0.95,
                )
            )

            fig.add_trace(
                go.Bar(
                    x=bearish[x_col],
                    y=bearish[flow_col],
                    name="Bearish Flow",
                    marker_color="#ff3030",
                    opacity=0.95,
                )
            )

            if not neutral.empty:
                fig.add_trace(
                    go.Bar(
                        x=neutral[x_col],
                        y=neutral[flow_col],
                        name="Other Flow",
                        marker_color="#a6adb7",
                        opacity=0.75,
                    )
                )

            if show_flow_dots:
                dot_df = chart_df[chart_df[flow_col].abs() >= flow_dot_threshold]
                if not dot_df.empty:
                    fig.add_trace(
                        go.Scatter(
                            x=dot_df[x_col],
                            y=dot_df[flow_col],
                            mode="markers",
                            name="FLOW X",
                            marker=dict(
                                size=9,
                                color=dot_df[flow_col].apply(lambda v: "#28e337" if v > 0 else "#ff3030"),
                                line=dict(width=1, color="white"),
                            ),
                        )
                    )

            fig.add_hline(
                y=flow_dot_threshold,
                line_dash="dash",
                line_color="#28e337",
                annotation_text=f"FLOW Dot Threshold: {flow_dot_threshold:,}",
                annotation_position="right",
            )

            fig.add_hline(
                y=-flow_dot_threshold,
                line_dash="dash",
                line_color="#ff3030",
                annotation_text=f"-{flow_dot_threshold:,}",
                annotation_position="right",
            )

        if price_col:
            fig.add_trace(
                go.Scatter(
                    x=chart_df[x_col],
                    y=chart_df[price_col],
                    name="Price",
                    mode="lines",
                    line=dict(color="white", width=3),
                    yaxis="y2",
                )
            )

    if call_gamma:
        fig.add_hline(
            y=flow_dot_threshold * 1.4,
            line_dash="dash",
            line_color="#00ff66",
            annotation_text=f"Call Gamma {call_gamma:.2f}",
            annotation_position="left",
        )

    if put_gamma:
        fig.add_hline(
            y=-flow_dot_threshold * 0.65,
            line_dash="dash",
            line_color="#ff3333",
            annotation_text=f"Put Gamma {put_gamma:.2f}",
            annotation_position="left",
        )

    fig.update_layout(
        title=f"{symbol} Premium Flow ({chart_bucket} Min)",
        template="plotly_dark",
        paper_bgcolor="#111923",
        plot_bgcolor="#252a2f",
        height=520,
        margin=dict(l=40, r=55, t=55, b=45),
        barmode="relative",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5,
        ),
        yaxis=dict(
            title="Premium Flow",
            gridcolor="rgba(255,255,255,.12)",
            zeroline=True,
            zerolinecolor="white",
        ),
        yaxis2=dict(
            title="Price",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        xaxis=dict(gridcolor="rgba(255,255,255,.10)"),
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


with right_matrix:
    if show_matrix:
        st.markdown('<div class="matrix-card">', unsafe_allow_html=True)
        st.markdown('<div class="matrix-title">🧠 SG2 FLOW AI SIGNAL MATRIX</div>', unsafe_allow_html=True)

        rows = []

        for sym in SYMBOLS:
            try:
                sym_snapshot = snapshot if sym == symbol else get_flow_snapshot(
                    symbol=sym,
                    all_exp_count=all_exp_count,
                    chart_bucket=chart_bucket,
                    lookback_hours=lookback_hours,
                    strike_width=strike_width,
                )
            except TypeError:
                try:
                    sym_snapshot = snapshot if sym == symbol else get_flow_snapshot(sym)
                except Exception:
                    sym_snapshot = {}
            except Exception:
                sym_snapshot = {}

            flow_net = safe_get(sym_snapshot, "odte_premium_net", 0)
            div_value = safe_get(sym_snapshot, "divergence_value", 0)
            gamma_value = safe_get(sym_snapshot, "gamma_signal", 0)
            pulse_value = safe_get(sym_snapshot, "pulse_drop_signal", 0)

            flow_status = build_signal_status(
                1 if flow_net >= FLOW_DOT_THRESHOLDS.get(sym, 25_000_000)
                else -1 if flow_net <= -FLOW_DOT_THRESHOLDS.get(sym, 25_000_000)
                else 0
            )

            divergence_status = build_signal_status(
                1 if div_value >= DIVERGENCE_THRESHOLDS.get(sym, 10_000_000)
                else -1 if div_value <= -DIVERGENCE_THRESHOLDS.get(sym, 10_000_000)
                else 0
            )

            gamma_status = build_signal_status(gamma_value)
            pulse_status = build_signal_status(pulse_value)

            rows.append(
                {
                    "Symbol": f"{SYMBOL_ICONS.get(sym, '')} {sym}",
                    "Flow X": signal_dot(flow_status),
                    "Divergence": signal_dot(divergence_status),
                    "Gamma Level": signal_dot(gamma_status),
                    "Pulse/Drop": signal_dot(pulse_status),
                    "Status": flow_status,
                }
            )

        matrix_df = pd.DataFrame(rows)

        st.dataframe(
            matrix_df,
            use_container_width=True,
            hide_index=True,
            height=310,
        )

        st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# FOOTER
# =========================================================
st.caption("All values are real-time estimates. Not financial advice. Data may be delayed.")
