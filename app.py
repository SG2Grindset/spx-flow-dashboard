import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

from flow_engine import get_flow_snapshot


st.set_page_config(
    page_title="SG2 FLOW Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# PASSWORD PROTECTION
# =========================================================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown(
        """
        <style>
        html, body, .stApp {
            background: radial-gradient(circle at top left, #14202b 0%, #070b10 45%, #020407 100%) !important;
            color: white !important;
        }

        .login-box {
            max-width: 480px;
            margin: 120px auto 0 auto;
            padding: 30px;
            border-radius: 18px;
            background: linear-gradient(180deg, #111923, #0b1118);
            border: 1px solid #00d46a;
            box-shadow: 0 0 25px rgba(0, 212, 106, .25);
            text-align: center;
        }

        .login-title {
            color: #00d46a;
            font-size: 34px;
            font-weight: 900;
        }

        .login-subtitle {
            color: #ffdd00;
            font-size: 16px;
            font-weight: 800;
            margin-top: 8px;
        }

        .password-label {
            color: #ffffff !important;
            font-size: 18px;
            font-weight: 900;
            margin-bottom: 8px;
            margin-top: 20px;
        }

        div[data-testid="stTextInput"] input {
            background-color: #ffffff !important;
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            font-weight: 900 !important;
            border-radius: 10px !important;
            border: 2px solid #00d46a !important;
            height: 52px !important;
            font-size: 18px !important;
        }

        div[data-testid="stButton"] button {
            background: linear-gradient(180deg, #00d46a, #00994d) !important;
            color: #ffffff !important;
            font-weight: 900 !important;
            font-size: 18px !important;
            border-radius: 12px !important;
            border: 1px solid #00ff88 !important;
            height: 56px !important;
            box-shadow: 0 0 18px rgba(0,212,106,.45) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="login-box">
            <div class="login-title">🔐 SG2 FLOW Dashboard</div>
            <div class="login-subtitle">Private Access Required</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="password-label">Enter Password</div>',
        unsafe_allow_html=True,
    )

    password = st.text_input("", type="password", label_visibility="collapsed")

    if st.button("ENTER THE FLOW by SG2", use_container_width=True):
        try:
            correct_password = st.secrets["APP_PASSWORD"]
        except Exception:
            st.error("APP_PASSWORD missing from secrets.toml")
            return False

        if password == correct_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")

    return False


if not check_password():
    st.stop()


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


# =========================================================
# SESSION STATE
# =========================================================
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "SPX"

if st.session_state.selected_symbol not in SYMBOLS:
    st.session_state.selected_symbol = "SPX"

symbol = st.session_state.selected_symbol


# =========================================================
# CSS
# =========================================================
st.markdown(
    """
<style>
html, body, .stApp {
    background: radial-gradient(circle at top left, #14202b 0%, #070b10 45%, #020407 100%) !important;
    color: #f4f7fb !important;
}

.main .block-container {
    background: transparent !important;
    padding-top: 1rem;
    padding-left: 1.4rem;
    padding-right: 1.4rem;
    max-width: 100%;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111922 0%, #070b10 100%) !important;
    border-right: 1px solid #263241;
}

section[data-testid="stSidebar"] * {
    color: #f4f7fb;
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
    opacity: 1 !important;
    font-weight: 900 !important;
}

section[data-testid="stSidebar"] div[data-baseweb="select"],
section[data-testid="stSidebar"] div[data-baseweb="input"] {
    background-color: #ffffff !important;
    border-radius: 8px !important;
}

section[data-testid="stSidebar"] input {
    background-color: #ffffff !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}

section[data-testid="stSidebar"] [data-baseweb="select"] div,
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="input"] div,
section[data-testid="stSidebar"] [data-baseweb="input"] input {
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
    opacity: 1 !important;
    font-weight: 900 !important;
}

section[data-testid="stSidebar"] [data-baseweb="select"] svg {
    fill: #111111 !important;
    color: #111111 !important;
}

section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * {
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
    font-weight: 900 !important;
}

section[data-testid="stSidebar"] .stNumberInput input {
    color: #111111 !important;
    -webkit-text-fill-color: #111111 !important;
    font-weight: 900 !important;
}

section[data-testid="stSidebar"] .stSlider label,
section[data-testid="stSidebar"] .stSlider span {
    color: #ffffff !important;
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

.metric-card,
.header-card,
.matrix-card {
    background: linear-gradient(180deg, #111923, #0b1118) !important;
    border: 1px solid #263241;
    border-radius: 14px;
    box-shadow: 0 0 18px rgba(0,0,0,.35);
}

.metric-card {
    padding: 14px 20px;
    margin-bottom: 12px;
}

.header-card {
    padding: 16px 20px;
    margin: 8px 0 10px 0;
}

.matrix-card {
    padding: 10px;
}

.metric-label {
    color: #ffdd00;
    font-size: 12px;
    font-weight: 900;
}

.metric-value {
    color: #ffffff;
    font-size: 19px;
    font-weight: 900;
}

.green-text { color: #31e75f !important; }
.red-text { color: #ff4b4b !important; }
.yellow-text { color: #ffdd00 !important; }
.cyan-text { color: #00e5ff !important; }

.matrix-title {
    color: white;
    font-size: 20px;
    font-weight: 900;
    margin-bottom: 10px;
    letter-spacing: .5px;
}

.sg2-matrix table {
    width: 100%;
    border-collapse: collapse;
    background: #0b1118;
    color: white;
    font-size: 13px;
    border-radius: 12px;
    overflow: hidden;
}

.sg2-matrix th {
    color: #ffdd00;
    background: #111923;
    padding: 8px;
    border: 1px solid #263241;
    text-align: center;
    font-weight: 900;
}

.sg2-matrix td {
    padding: 8px;
    border: 1px solid #263241;
    text-align: center;
    background: #0b1118;
}

.sg2-matrix td:first-child {
    text-align: left;
    font-weight: 900;
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
    st.markdown("## ⚙️ Dashboard Controls")

    auto_refresh = st.checkbox("Auto Refresh", value=True)

    refresh_interval = st.selectbox(
        "Refresh Interval",
        options=[5, 10, 15, 30, 60],
        index=2,
    )

    all_exp_count = st.slider(
        "All Expirations Count",
        min_value=1,
        max_value=10,
        value=5,
    )

    chart_bucket = st.selectbox(
        "Chart Bucket",
        options=[1, 3, 5],
        index=0,
    )

    lookback_hours = st.slider(
        "Lookback Hours",
        min_value=1,
        max_value=8,
        value=2,
    )

    show_flow_dots = st.checkbox("Show FLOW Dots", value=True)
    show_signed_delta_line = st.checkbox("Show Signed Delta Line", value=True)
    show_right_labels = st.checkbox("Show Right Edge Labels", value=True)

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
    )

    st.markdown("---")
    st.caption("Primary chart model: Premium Flow = Option Price × Contracts × 100.")
    st.caption("Cyan line: Signed Delta Notional = Spot × Delta × Contracts × 100.")


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


def fmt_num(value):
    try:
        value = float(value)
    except Exception:
        return "0"

    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"

    return f"{value:.0f}"


def metric_html(label, value, color_class=""):
    return f"""
    <div>
        <div class="metric-label">{label}</div>
        <div class="metric-value {color_class}">{value}</div>
    </div>
    """


def color_class(value):
    try:
        value = float(value)
    except Exception:
        return ""

    if value > 0:
        return "green-text"
    if value < 0:
        return "red-text"
    return ""


def safe_get(snapshot, key, default=0):
    if not isinstance(snapshot, dict):
        return default
    return snapshot.get(key, default)


def status_from_value(value):
    try:
        value = float(value)
    except Exception:
        value = 0

    if value > 0:
        return "BULLISH"
    if value < 0:
        return "BEARISH"
    return "NEUTRAL"


def dot_from_status(status):
    if status == "BULLISH":
        return "🟢"
    if status == "BEARISH":
        return "🔴"
    return "🟣"


def compute_volume_stats(snapshot, odte_exp):
    chain_df = safe_get(snapshot, "chain_df", pd.DataFrame())

    if not isinstance(chain_df, pd.DataFrame) or chain_df.empty:
        return 0, 0, 0, 0

    df = chain_df.copy()

    if "expiration" in df.columns:
        odte_df = df[df["expiration"].astype(str) == str(odte_exp)].copy()
        if odte_df.empty:
            odte_df = df.copy()
    else:
        odte_df = df.copy()

    if "volume" not in odte_df.columns or "type" not in odte_df.columns:
        return 0, 0, 0, 0

    calls = odte_df[odte_df["type"] == "call"]
    puts = odte_df[odte_df["type"] == "put"]

    call_volume = calls["volume"].sum()
    put_volume = puts["volume"].sum()
    total_volume = call_volume + put_volume
    pc_ratio = put_volume / call_volume if call_volume > 0 else 0

    return call_volume, put_volume, total_volume, pc_ratio


def add_right_edge_label(fig, x, y, text, bg, yref="y", xshift=14):
    fig.add_annotation(
        x=x,
        y=y,
        text=text,
        showarrow=False,
        font=dict(color="black", size=12, family="Arial Black"),
        bgcolor=bg,
        bordercolor=bg,
        borderwidth=1,
        borderpad=3,
        xanchor="left",
        yanchor="middle",
        xshift=xshift,
        yref=yref,
    )


# =========================================================
# TOP SYMBOL BUTTONS
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


# =========================================================
# ACTIVE BAR
# =========================================================
st.markdown(
    f"""
    <div class="active-bar">
        ACTIVE: &nbsp; {icon} &nbsp; {symbol}
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# LOAD SNAPSHOT
# =========================================================
try:
    snapshot = get_flow_snapshot(
        symbol=symbol,
        all_exp_count=all_exp_count,
        chart_bucket=chart_bucket,
        lookback_hours=lookback_hours,
        strike_width=strike_width,
    )
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

call_volume, put_volume, total_volume, pc_ratio = compute_volume_stats(snapshot, odte_exp)


# =========================================================
# FLOW HISTORY
# =========================================================
if "flow_history" not in st.session_state:
    st.session_state.flow_history = {}

if symbol not in st.session_state.flow_history:
    st.session_state.flow_history[symbol] = pd.DataFrame(
        columns=[
            "time",
            "odte_flow",
            "all_exp_flow",
            "signed_delta",
            "price",
        ]
    )

new_row = pd.DataFrame(
    [{
        "time": pd.Timestamp.now(tz="America/Chicago"),
        "odte_flow": odte_premium_net,
        "all_exp_flow": all_exp_premium_net,
        "signed_delta": odte_signed_delta,
        "price": spot,
    }]
)

st.session_state.flow_history[symbol] = pd.concat(
    [st.session_state.flow_history[symbol], new_row],
    ignore_index=True,
)

cutoff = pd.Timestamp.now(tz="America/Chicago") - pd.Timedelta(hours=lookback_hours)

history_df = st.session_state.flow_history[symbol].copy()
history_df["time"] = pd.to_datetime(history_df["time"], errors="coerce")
history_df = history_df.dropna(subset=["time"])
history_df = history_df[history_df["time"] >= cutoff]
history_df = history_df.sort_values("time")

st.session_state.flow_history[symbol] = history_df


# =========================================================
# METRICS
# =========================================================
st.markdown('<div class="metric-card">', unsafe_allow_html=True)

r1 = st.columns(5)

r1[0].markdown(metric_html("Spot", f"{spot:.2f}"), unsafe_allow_html=True)

r1[1].markdown(
    metric_html(
        "0DTE Premium Net",
        fmt_money(odte_premium_net),
        color_class(odte_premium_net),
    ),
    unsafe_allow_html=True,
)

r1[2].markdown(
    metric_html(
        "All Exp Premium Net",
        fmt_money(all_exp_premium_net),
        color_class(all_exp_premium_net),
    ),
    unsafe_allow_html=True,
)

r1[3].markdown(
    metric_html("Call Gamma", f"{call_gamma:.2f}", "green-text"),
    unsafe_allow_html=True,
)

r1[4].markdown(
    metric_html("Put Gamma", f"{put_gamma:.2f}", "green-text"),
    unsafe_allow_html=True,
)

st.markdown("<hr>", unsafe_allow_html=True)

r2 = st.columns(10)

r2[0].markdown(
    metric_html(
        "0DTE Signed Delta",
        fmt_money(odte_signed_delta),
        color_class(odte_signed_delta),
    ),
    unsafe_allow_html=True,
)

r2[1].markdown(
    metric_html(
        "0DTE Delta Bias",
        odte_delta_bias,
        "red-text" if "BEAR" in str(odte_delta_bias) else "green-text",
    ),
    unsafe_allow_html=True,
)

r2[2].markdown(
    metric_html(
        "All Exp Delta Bias",
        all_exp_delta_bias,
        "red-text" if "BEAR" in str(all_exp_delta_bias) else "green-text",
    ),
    unsafe_allow_html=True,
)

r2[3].markdown(
    metric_html(
        "Gamma Regime",
        gamma_regime,
        "green-text" if "ABOVE" in str(gamma_regime) else "red-text",
    ),
    unsafe_allow_html=True,
)

r2[4].markdown(metric_html("0DTE Rows", odte_rows), unsafe_allow_html=True)
r2[5].markdown(metric_html("All Exp Rows", all_exp_rows), unsafe_allow_html=True)

r2[6].markdown(
    metric_html("Call Vol", fmt_num(call_volume), "green-text"),
    unsafe_allow_html=True,
)

r2[7].markdown(
    metric_html("Put Vol", fmt_num(put_volume), "red-text"),
    unsafe_allow_html=True,
)

r2[8].markdown(
    metric_html("Total Vol", fmt_num(total_volume)),
    unsafe_allow_html=True,
)

r2[9].markdown(
    metric_html("P/C Ratio", f"{pc_ratio:.2f}", "yellow-text"),
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# HEADER
# =========================================================
today_txt = datetime.now().strftime("%A, %B %d, %Y")

header_html = f"""
<div class="header-card">
    <div style="font-size:25px;font-weight:900;color:white;">
        {symbol} {today_txt}
    </div>
    <div style="font-size:15px;font-weight:800;color:white;margin-top:8px;">
        Spot: <span class="green-text">{spot:.2f}</span>
        &nbsp;&nbsp; | &nbsp;&nbsp;
        0DTE Exp: <span class="yellow-text">{odte_exp}</span>
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="yellow-text">0DTE Flow:</span> {fmt_money(odte_premium_net)}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="cyan-text">Signed Delta:</span> {fmt_money(odte_signed_delta)}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        All Exp Used: {all_exp_count}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="yellow-text">All Exp Flow:</span> {fmt_money(all_exp_premium_net)}
    </div>
</div>
"""

st.markdown(header_html, unsafe_allow_html=True)


# =========================================================
# CHART + MATRIX
# =========================================================
left_chart, right_matrix = st.columns([4.2, 0.8])


# =========================================================
# FLOW CHART
# =========================================================
with left_chart:
    fig = go.Figure()

    if not history_df.empty:
        history_df["odte_flow"] = pd.to_numeric(
            history_df["odte_flow"],
            errors="coerce",
        ).fillna(0)

        history_df["all_exp_flow"] = pd.to_numeric(
            history_df["all_exp_flow"],
            errors="coerce",
        ).fillna(0)

        history_df["signed_delta"] = pd.to_numeric(
            history_df["signed_delta"],
            errors="coerce",
        ).fillna(0)

        history_df["price"] = pd.to_numeric(
            history_df["price"],
            errors="coerce",
        ).fillna(0)

        history_df = history_df.sort_values("time")

        fig.add_trace(
            go.Scatter(
                x=history_df["time"],
                y=history_df["odte_flow"],
                name="0DTE Flow",
                mode="lines",
                line=dict(color="#2cff1f", width=4, shape="spline"),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=history_df["time"],
                y=history_df["all_exp_flow"],
                name="All Exp Flow",
                mode="lines",
                line=dict(color="#ffe100", width=4, shape="spline"),
            )
        )

        if show_signed_delta_line:
            fig.add_trace(
                go.Scatter(
                    x=history_df["time"],
                    y=history_df["signed_delta"],
                    name="Signed Delta",
                    mode="lines",
                    line=dict(
                        color="#00e5ff",
                        width=1.6,
                        dash="dot",
                        shape="spline",
                    ),
                    opacity=0.9,
                )
            )

        fig.add_trace(
            go.Scatter(
                x=history_df["time"],
                y=history_df["price"],
                name="Price",
                mode="lines",
                line=dict(color="white", width=4, shape="spline"),
                yaxis="y2",
            )
        )

        if show_flow_dots:
            dot_df = history_df[
                history_df["odte_flow"].abs() >= flow_dot_threshold
            ].copy()

            if not dot_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=dot_df["time"],
                        y=dot_df["odte_flow"],
                        mode="markers+text",
                        name="FLOW X",
                        text=["FLOW"] * len(dot_df),
                        textposition="top center",
                        textfont=dict(color="white", size=10),
                        marker=dict(
                            size=11,
                            symbol="diamond",
                            color=[
                                "#26ff38" if v > 0 else "#ff3030"
                                for v in dot_df["odte_flow"]
                            ],
                            line=dict(width=1, color="white"),
                        ),
                    )
                )

        if show_right_labels and len(history_df) > 0:
            latest_time = history_df["time"].iloc[-1]
            latest_odte = history_df["odte_flow"].iloc[-1]
            latest_all = history_df["all_exp_flow"].iloc[-1]
            latest_price = history_df["price"].iloc[-1]

            add_right_edge_label(
                fig,
                latest_time,
                latest_odte,
                fmt_money(latest_odte),
                "#2cff1f",
                yref="y",
            )

            add_right_edge_label(
                fig,
                latest_time,
                latest_all,
                fmt_money(latest_all),
                "#ffe100",
                yref="y",
            )

            if show_signed_delta_line:
                latest_signed = history_df["signed_delta"].iloc[-1]

                add_right_edge_label(
                    fig,
                    latest_time,
                    latest_signed,
                    fmt_money(latest_signed),
                    "#00e5ff",
                    yref="y",
                )

            add_right_edge_label(
                fig,
                latest_time,
                latest_price,
                f"{latest_price:.2f}",
                "white",
                yref="y2",
            )

        fig.add_hline(
            y=flow_dot_threshold,
            line_dash="dash",
            line_color="#26ff38",
            annotation_text="FLOW Dot Threshold",
            annotation_position="right",
        )

        fig.add_hline(
            y=-flow_dot_threshold,
            line_dash="dash",
            line_color="#ff3030",
            annotation_text=f"-{flow_dot_threshold:,}",
            annotation_position="right",
        )

    fig.update_layout(
        title=f"{symbol} Flow Trend ({chart_bucket} Min)",
        template="plotly_dark",
        paper_bgcolor="#111923",
        plot_bgcolor="#252a2f",
        height=520,
        margin=dict(l=40, r=95, t=50, b=45),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(size=12, color="white"),
        ),
        yaxis=dict(
            title="Premium Flow / Signed Delta",
            gridcolor="rgba(255,255,255,.14)",
            zeroline=True,
            zerolinecolor="white",
            zerolinewidth=2,
            tickfont=dict(color="#ffdd00"),
        ),
        yaxis2=dict(
            title="Price",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color="white"),
        ),
        xaxis=dict(
            tickformat="%I:%M %p",
            dtick=chart_bucket * 60000,
            gridcolor="rgba(255,255,255,.10)",
            tickfont=dict(color="white"),
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False},
    )


# =========================================================
# MATRIX
# =========================================================
with right_matrix:
    if show_matrix:
        st.markdown('<div class="matrix-card">', unsafe_allow_html=True)

        st.markdown(
            '<div class="matrix-title">🧠 SG2 FLOW DASHBOARD</div>',
            unsafe_allow_html=True,
        )

        rows = []

        for sym in SYMBOLS:
            try:
                sym_snapshot = (
                    snapshot
                    if sym == symbol
                    else get_flow_snapshot(
                        symbol=sym,
                        all_exp_count=all_exp_count,
                        chart_bucket=chart_bucket,
                        lookback_hours=lookback_hours,
                        strike_width=strike_width,
                    )
                )
            except Exception as e:
                st.warning(f"{sym} matrix load failed: {e}")
                sym_snapshot = {}

            flow_net = safe_get(sym_snapshot, "odte_premium_net", 0)
            div_value = safe_get(sym_snapshot, "divergence_value", 0)
            gamma_value = safe_get(sym_snapshot, "gamma_signal", 0)
            pulse_value = safe_get(sym_snapshot, "pulse_drop_signal", 0)

            flow_status = status_from_value(
                1
                if flow_net >= FLOW_DOT_THRESHOLDS.get(sym, 25_000_000)
                else -1
                if flow_net <= -FLOW_DOT_THRESHOLDS.get(sym, 25_000_000)
                else 0
            )

            divergence_status = status_from_value(
                1
                if div_value >= DIVERGENCE_THRESHOLDS.get(sym, 10_000_000)
                else -1
                if div_value <= -DIVERGENCE_THRESHOLDS.get(sym, 10_000_000)
                else 0
            )

            gamma_status = status_from_value(gamma_value)
            pulse_status = status_from_value(pulse_value)

            rows.append(
                {
                    "Symbol": f"{SYMBOL_ICONS.get(sym, '')} {sym}",
                    "Flow": dot_from_status(flow_status),
                    "Div": dot_from_status(divergence_status),
                    "Gamma": dot_from_status(gamma_status),
                    "Pulse": dot_from_status(pulse_status),
                }
            )

        matrix_df = pd.DataFrame(rows)
        matrix_html = matrix_df.to_html(index=False, escape=False)

        st.markdown(
            f"""
            <div class="sg2-matrix">
                {matrix_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


st.caption(
    "All values are real-time estimates. Not financial advice. Data may be delayed."
)
