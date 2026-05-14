# ============================================================
# exposure_dashboard.py
# Multi-Symbol Net Flow Dashboard
# Sends BIG net-flow-only Discord graphics to symbol-specific channels
# Includes FLOW crossover dots
# Includes Gamma Levels
# Includes SPY-only GZONE
# Fresh plots shifted left with future space on right side
# Fixes Plotly/Kaleido Timestamp serialization
# ============================================================

import os
import time
import tempfile
import requests
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

from flow_engine import get_spx_flow_data
from session_recorder import append_session_snapshot, load_session, reset_session
from gamma_level_engine import build_gamma_delta_levels


# ============================================================
# ENV
# ============================================================

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

CENTRAL_TZ = ZoneInfo("America/Chicago")


# ============================================================
# FLOW CROSS THRESHOLDS
# ============================================================

FLOW_CROSS_THRESHOLD = {
    "SPY": 2_000_000,
    "QQQ": 2_000_000,
    "IWM": 1_000_000,
    "SPX": 15_000_000,
    "XSP": 750_000,
    "TSLA": 1_000_000,
}


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Net Flow Dashboard",
    page_icon="🔥",
    layout="wide"
)

st.markdown("""
<style>
.stApp { background-color: #020617; color: white; }
html, body, [class*="css"] { color: white; font-family: "Segoe UI", sans-serif; }

[data-testid="metric-container"] {
    background: linear-gradient(145deg, #04142b 0%, #03101f 100%);
    border: 1px solid rgba(0,255,255,0.10);
    padding: 14px;
    border-radius: 14px;
    box-shadow: 0 0 12px rgba(0,255,255,0.05);
}

section[data-testid="stSidebar"] {
    background-color: #03101f;
    border-right: 1px solid rgba(255,255,255,0.06);
}

.block-container {
    padding-top: 0.5rem;
    padding-left: 0.6rem;
    padding-right: 0.6rem;
    max-width: 100%;
}
</style>
""", unsafe_allow_html=True)

st.title("🔥 Multi-Symbol Net Flow Dashboard")
st.caption("Price • Call Flow • Put Flow • Net Flow • Gamma Levels • FLOW Cross Dots • Symbol Discord Channels")


# ============================================================
# DISCORD HELPERS
# ============================================================

def get_discord_webhook_for_symbol(symbol):
    symbol = symbol.upper().strip()

    webhook_map = {
        "SPY": os.getenv("DISCORD_WEBHOOK_SPY", ""),
        "XSP": os.getenv("DISCORD_WEBHOOK_XSP", ""),
        "SPX": os.getenv("DISCORD_WEBHOOK_SPX", ""),
        "QQQ": os.getenv("DISCORD_WEBHOOK_QQQ", ""),
        "IWM": os.getenv("DISCORD_WEBHOOK_IWM", ""),
        "TSLA": os.getenv("DISCORD_WEBHOOK_TSLA", ""),
    }

    webhook_url = webhook_map.get(symbol, "")

    if not webhook_url or "..." in webhook_url:
        return ""

    return webhook_url


def discord_window_open():
    now_ct = datetime.now(CENTRAL_TZ)
    start = dt_time(7, 30)
    end = dt_time(16, 15)

    is_weekday = now_ct.weekday() < 5
    is_in_window = start <= now_ct.time() <= end

    return is_weekday and is_in_window, now_ct


# ============================================================
# SIDEBAR
# ============================================================

ALL_SYMBOLS = ["SPY", "SPX", "XSP", "QQQ", "IWM", "TSLA"]

st.sidebar.header("Settings")

chart_symbol = st.sidebar.selectbox(
    "Dashboard Symbol",
    ALL_SYMBOLS,
    index=0
)

discord_symbols = st.sidebar.multiselect(
    "Discord Symbols To Send",
    ALL_SYMBOLS,
    default=ALL_SYMBOLS
)

auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)

refresh_seconds = st.sidebar.selectbox(
    "Refresh Interval",
    [15, 30, 60, 120, 300],
    index=0
)

flow_lookback_hours = st.sidebar.slider(
    "Flow Chart Lookback Hours",
    min_value=1,
    max_value=10,
    value=2,
    step=1
)

flow_bucket_minutes = st.sidebar.selectbox(
    "Flow Chart Bucket",
    [1, 3, 5],
    index=1
)

record_session = st.sidebar.checkbox("Record Session History", value=True)

send_now = st.sidebar.button("Send Selected Symbols To Discord Now")

auto_send_discord = st.sidebar.checkbox(
    "Auto Send Selected Symbols Every 60 Seconds",
    value=False
)

show_debug = st.sidebar.checkbox("Show Discord Debug", value=True)


# ============================================================
# GZONE LEVELS - SPY ONLY
# ============================================================

st.sidebar.markdown("## GZONE - SPY Only")

gzone_high = st.sidebar.number_input(
    "GZONE High",
    value=0.0,
    step=0.01
)

gzone_low = st.sidebar.number_input(
    "GZONE Low",
    value=0.0,
    step=0.01
)

show_gzone = st.sidebar.checkbox(
    "Show GZONE on SPY",
    value=True
)


if st.sidebar.button(f"Reset {chart_symbol} Session History"):
    reset_session(chart_symbol)
    st.sidebar.success(f"{chart_symbol} session history reset.")

if auto_refresh:
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="net_flow_refresh"
    )


# ============================================================
# GENERAL HELPERS
# ============================================================

def money_fmt(v):
    try:
        v = float(v)

        if abs(v) >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f}B"

        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:.2f}M"

        if abs(v) >= 1_000:
            return f"{v / 1_000:.1f}K"

        return f"{v:.0f}"

    except Exception:
        return "—"


def fmt(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "—"


def safe_num(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def find_col(df, names):
    cols = {str(c).lower().strip(): c for c in df.columns}

    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]

    return None


def width_for_symbol(symbol):
    symbol = symbol.upper()

    if symbol == "SPX":
        return 100

    if symbol == "XSP":
        return 15

    if symbol == "TSLA":
        return 25

    return 50


def price_tick_size(symbol):
    symbol = symbol.upper()

    if symbol in ["SPY", "QQQ", "IWM", "XSP"]:
        return 0.50

    if symbol == "TSLA":
        return 1.00

    if symbol == "SPX":
        return 2.50

    return 1.00


def select_6_above_below(chain_df, spot):
    df = chain_df.copy()
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df = df.dropna(subset=["strike"])

    unique_strikes = sorted(df["strike"].dropna().unique().tolist())

    if not unique_strikes:
        return df

    spot_float = float(spot)

    below = [s for s in unique_strikes if s < spot_float][-6:]
    above = [s for s in unique_strikes if s > spot_float][:6]
    nearest = min(unique_strikes, key=lambda x: abs(x - spot_float))

    selected = sorted(set(below + [nearest] + above))

    return df[df["strike"].isin(selected)].copy()


def normalize_datetime_column(df):
    df = df.copy()

    df["datetime"] = pd.to_datetime(
        df.get("datetime", pd.NaT),
        errors="coerce"
    )

    if df["datetime"].isna().all() and "time" in df.columns:
        df["datetime"] = pd.to_datetime(
            pd.Timestamp.today().strftime("%Y-%m-%d")
            + " "
            + df["time"].astype(str),
            errors="coerce"
        )

    df = df.dropna(subset=["datetime"]).sort_values("datetime")

    return df


# ============================================================
# PREP CHAIN
# ============================================================

def prepare_chain(chain_df, spot):
    df = chain_df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]

    strike_col = find_col(df, ["strike"])
    type_col = find_col(df, ["type", "option_type"])
    volume_col = find_col(df, ["volume"])
    last_col = find_col(df, ["last", "mark", "price"])
    oi_col = find_col(df, ["open_interest", "oi"])

    if strike_col is None or type_col is None:
        raise ValueError("Missing strike or option type column.")

    df["strike"] = safe_num(df[strike_col])
    df["type"] = df[type_col].astype(str).str.lower()

    df["volume"] = safe_num(df[volume_col]) if volume_col else 0
    df["last"] = safe_num(df[last_col]) if last_col else 0
    df["open_interest"] = safe_num(df[oi_col]) if oi_col else 0

    df["activity"] = df["volume"]
    df.loc[df["activity"] <= 0, "activity"] = df["open_interest"]

    df["premium_raw"] = df["last"] * df["activity"] * 100

    df["call_premium"] = df["premium_raw"].where(
        df["type"].str.contains("call"),
        0
    )

    df["put_premium"] = df["premium_raw"].where(
        df["type"].str.contains("put"),
        0
    )

    df["net_premium"] = df["call_premium"] - df["put_premium"]

    return df.sort_values("strike")


# ============================================================
# FLOW BUILDERS
# ============================================================

def build_flow_history_df(symbol, history_df, lookback_hours=2, bucket_minutes=3):
    if history_df is None or history_df.empty:
        return pd.DataFrame()

    df = normalize_datetime_column(history_df)

    if df.empty:
        return pd.DataFrame()

    max_time = df["datetime"].max()
    min_time = max_time - pd.Timedelta(hours=lookback_hours)
    df = df[df["datetime"] >= min_time]

    if df.empty:
        return pd.DataFrame()

    df = (
        df.set_index("datetime")
        .sort_index()
        .resample(f"{bucket_minutes}min")
        .agg({
            "spot": "last",
            "call_premium": "last",
            "put_premium": "last",
            "net_premium": "last",
        })
        .dropna(how="all")
        .reset_index()
    )

    if df.empty:
        return pd.DataFrame()

    for col in ["spot", "call_premium", "put_premium", "net_premium"]:
        df[col] = pd.to_numeric(
            df.get(col, 0),
            errors="coerce"
        ).ffill().fillna(0)

    df["call_flow"] = df["call_premium"].diff().fillna(0)
    df["put_flow"] = df["put_premium"].diff().fillna(0)

    df["cum_call_flow"] = df["call_flow"].cumsum()
    df["cum_put_flow"] = df["put_flow"].cumsum()
    df["net_flow"] = (df["call_flow"] - df["put_flow"]).cumsum()

    threshold = FLOW_CROSS_THRESHOLD.get(symbol.upper(), 1_000_000)

    df["bull_flow_cross"] = (
        (df["net_flow"] > threshold)
        & (df["net_flow"].shift(1) <= 0)
    )

    df["bear_flow_cross"] = (
        (df["net_flow"] < -threshold)
        & (df["net_flow"].shift(1) >= 0)
    )

    # IMPORTANT: convert timestamps to Python datetime for Plotly/Kaleido export
    df["time"] = pd.to_datetime(df["datetime"]).dt.to_pydatetime()

    return df


def load_symbol_flow(symbol):
    width = width_for_symbol(symbol)

    data = get_spx_flow_data(
        symbol=symbol,
        width=width
    )

    spot = data.get("spot_price")
    chain_df = data.get("chain_df")

    if chain_df is None or chain_df.empty:
        raise Exception(f"No option chain returned for {symbol}")

    filtered_chain = select_6_above_below(chain_df, spot)
    prepared_chain = prepare_chain(filtered_chain, spot)

    gamma_result = build_gamma_delta_levels(prepared_chain, spot)
    gamma_levels = gamma_result.get("levels", {})

    print(
        f"{symbol} | "
        f"Rows: {len(prepared_chain)} | "
        f"Calls: {prepared_chain['call_premium'].sum():,.0f} | "
        f"Puts: {prepared_chain['put_premium'].sum():,.0f}"
    )

    call_premium = prepared_chain["call_premium"].sum()
    put_premium = prepared_chain["put_premium"].sum()
    net_premium = call_premium - put_premium

    total_flow = call_premium + put_premium

    if total_flow > 0:
        flow_imbalance = (call_premium - put_premium) / total_flow * 100
    else:
        flow_imbalance = 0

    if flow_imbalance >= 50:
        flow_bias = f"CALLS +{flow_imbalance:.0f}% STRONG"
    elif flow_imbalance >= 20:
        flow_bias = f"CALLS +{flow_imbalance:.0f}% MODERATE"
    elif flow_imbalance <= -50:
        flow_bias = f"PUTS {flow_imbalance:.0f}% STRONG"
    elif flow_imbalance <= -20:
        flow_bias = f"PUTS {flow_imbalance:.0f}% MODERATE"
    else:
        flow_bias = f"MIXED {flow_imbalance:.0f}%"

    if record_session:
        history_df = append_session_snapshot(
            symbol=symbol,
            spot=spot,
            call_premium=call_premium,
            put_premium=put_premium,
            net_premium=net_premium,
            net_dex=0,
            net_gex=0,
        )
    else:
        history_df = load_session(symbol)

    return {
        "symbol": symbol,
        "spot": spot,
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": net_premium,
        "flow_bias": flow_bias,
        "gamma_levels": gamma_levels,
        "history_df": history_df,
    }


# ============================================================
# BIG NET FLOW CHART
# ============================================================

def net_flow_chart(symbol_data, lookback_hours=2, bucket_minutes=3, discord=False):
    symbol = symbol_data["symbol"]
    spot = symbol_data["spot"]

    flow_df = build_flow_history_df(
        symbol,
        symbol_data["history_df"],
        lookback_hours=lookback_hours,
        bucket_minutes=bucket_minutes
    )

    if flow_df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"No flow history yet for {symbol}",
            height=900,
            paper_bgcolor="#020617",
            plot_bgcolor="#001a22",
            font=dict(color="white")
        )
        return fig

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=flow_df["time"],
            y=flow_df["spot"],
            mode="lines",
            line=dict(color="white", width=5 if discord else 4),
            name=f"{symbol} Price",
            yaxis="y",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=flow_df["time"],
            y=flow_df["cum_call_flow"],
            mode="lines",
            line=dict(color="#f59e0b", width=6 if discord else 4),
            name="Call Flow",
            yaxis="y2",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=flow_df["time"],
            y=flow_df["cum_put_flow"],
            mode="lines",
            line=dict(color="#3b82f6", width=6 if discord else 4),
            name="Put Flow",
            yaxis="y2",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=flow_df["time"],
            y=flow_df["net_flow"],
            mode="lines",
            line=dict(color="#a855f7", width=8 if discord else 5),
            name="Net Flow",
            yaxis="y2",
        )
    )

    bull_crosses = flow_df[flow_df["bull_flow_cross"]]
    bear_crosses = flow_df[flow_df["bear_flow_cross"]]

    fig.add_trace(
        go.Scatter(
            x=bull_crosses["time"],
            y=bull_crosses["net_flow"],
            mode="markers+text",
            marker=dict(
                size=26 if discord else 18,
                color="#22c55e",
                symbol="circle",
                line=dict(color="white", width=2),
            ),
            text=["FLOW"] * len(bull_crosses),
            textposition="top center",
            textfont=dict(
                color="white",
                size=22 if discord else 14,
                family="Arial Black"
            ),
            name="Bull Flow Cross",
            yaxis="y2",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=bear_crosses["time"],
            y=bear_crosses["net_flow"],
            mode="markers+text",
            marker=dict(
                size=26 if discord else 18,
                color="#ef4444",
                symbol="circle",
                line=dict(color="white", width=2),
            ),
            text=["FLOW"] * len(bear_crosses),
            textposition="bottom center",
            textfont=dict(
                color="white",
                size=22 if discord else 14,
                family="Arial Black"
            ),
            name="Bear Flow Cross",
            yaxis="y2",
        )
    )

    # ========================================================
    # REAL GAMMA LEVEL LINES
    # ========================================================

    gamma_levels = symbol_data.get("gamma_levels", {})

    gamma_line_map = {
        "Call Wall": {
            "key": "call_wall",
            "color": "#ef4444",
            "dash": "dash",
            "width": 3,
        },
        "Put Wall": {
            "key": "put_wall",
            "color": "#22c55e",
            "dash": "dash",
            "width": 3,
        },
        "Zero Gamma": {
            "key": "zero_gamma",
            "color": "#ffffff",
            "dash": "solid",
            "width": 4,
        },
        "Vol Trigger": {
            "key": "vol_trigger",
            "color": "#f97316",
            "dash": "dot",
            "width": 3,
        },
        "Magnet": {
            "key": "magnet",
            "color": "#38bdf8",
            "dash": "dashdot",
            "width": 3,
        },
    }

    for label, cfg in gamma_line_map.items():
        raw_level = gamma_levels.get(cfg["key"])

        try:
            level = float(raw_level)
        except Exception:
            continue

        if pd.isna(level) or level <= 0:
            continue

        fig.add_hline(
            y=level,
            line=dict(
                color=cfg["color"],
                width=cfg["width"],
                dash=cfg["dash"]
            ),
            yref="y"
        )

        fig.add_annotation(
            x=1.01,
            y=level,
            xref="paper",
            yref="y",
            text=f"<b>{label}: {level:.2f}</b>",
            showarrow=False,
            font=dict(
                color=cfg["color"],
                size=22 if discord else 13,
                family="Arial Black"
            ),
            align="left",
            xanchor="left",
            bgcolor="rgba(0,0,0,0.65)",
            bordercolor=cfg["color"],
            borderwidth=1,
        )

    # ========================================================
    # GZONE BOX - SPY ONLY
    # ========================================================

    if (
        symbol.upper() == "SPY"
        and show_gzone
        and gzone_high > 0
        and gzone_low > 0
    ):

        gzone_top = max(gzone_high, gzone_low)
        gzone_bottom = min(gzone_high, gzone_low)

        gzone_risk = abs(gzone_top - gzone_bottom)

        fig.add_hrect(
            y0=gzone_bottom,
            y1=gzone_top,
            fillcolor="rgba(255, 215, 0, 0.12)",
            line_width=0,
            layer="below",
            yref="y"
        )

        fig.add_hline(
            y=gzone_top,
            line=dict(
                color="#22c55e",
                width=3,
                dash="solid"
            ),
            yref="y"
        )

        fig.add_hline(
            y=gzone_bottom,
            line=dict(
                color="#ef4444",
                width=3,
                dash="solid"
            ),
            yref="y"
        )

        fig.add_annotation(
            x=1.01,
            y=gzone_top,
            xref="paper",
            yref="y",
            text=f"<b>GZONE HIGH: {gzone_top:.2f}</b>",
            showarrow=False,
            font=dict(
                color="#22c55e",
                size=22 if discord else 13,
                family="Arial Black"
            ),
            bgcolor="rgba(0,0,0,0.65)",
            bordercolor="#22c55e",
            borderwidth=1,
            xanchor="left"
        )

        fig.add_annotation(
            x=1.01,
            y=gzone_bottom,
            xref="paper",
            yref="y",
            text=f"<b>GZONE LOW: {gzone_bottom:.2f}</b>",
            showarrow=False,
            font=dict(
                color="#ef4444",
                size=22 if discord else 13,
                family="Arial Black"
            ),
            bgcolor="rgba(0,0,0,0.65)",
            bordercolor="#ef4444",
            borderwidth=1,
            xanchor="left"
        )

        fig.add_annotation(
            x=0.5,
            y=1.12,
            xref="paper",
            yref="paper",
            text=(
                f"<b>"
                f"<span style='color:#22c55e'>GZONE HIGH: {gzone_top:.2f}</span>"
                f" &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<span style='color:#ef4444'>GZONE LOW: {gzone_bottom:.2f}</span>"
                f" &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"<span style='color:#facc15'>RISK: {gzone_risk:.2f}</span>"
                f"</b>"
            ),
            showarrow=False,
            font=dict(
                size=24 if discord else 14,
                family="Arial Black"
            ),
            bgcolor="rgba(0,0,0,0.75)",
            bordercolor="#facc15",
            borderwidth=1,
        )

    # ========================================================
    # SHIFT CHART LEFT FOR FUTURE SPACE
    # ========================================================

    min_time = flow_df["time"].min()
    max_time = flow_df["time"].max()

    total_span = max_time - min_time

    if total_span.total_seconds() <= 0:
        total_span = pd.Timedelta(minutes=max(bucket_minutes, 1))

    future_padding = total_span * 0.50
    x_axis_max = max_time + future_padding

    # Convert pandas Timestamp objects to Python datetime for Plotly/Kaleido export
    min_time = min_time.to_pydatetime() if hasattr(min_time, "to_pydatetime") else min_time
    x_axis_max = x_axis_max.to_pydatetime() if hasattr(x_axis_max, "to_pydatetime") else x_axis_max

    # ========================================================
    # LAYOUT
    # ========================================================

    title_size = 36 if discord else 26
    axis_size = 26 if discord else 14
    legend_size = 26 if discord else 16
    height = 1350 if discord else 980
    width = 2300 if discord else None

    subtitle = (
        f"Spot: {float(spot):,.2f} | "
        f"Flow Bias: {symbol_data['flow_bias']} | "
        f"Calls: {money_fmt(symbol_data['call_premium'])} | "
        f"Puts: {money_fmt(symbol_data['put_premium'])} | "
        f"Net: {money_fmt(symbol_data['net_premium'])}"
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{symbol} Net Flow Dashboard | "
                f"{bucket_minutes}-Min Bars | Last {lookback_hours} Hours</b><br>"
                f"<span style='font-size:{24 if discord else 16}px;'>{subtitle}</span>"
            ),
            x=0.5,
            xanchor="center",
            y=0.97,
            font=dict(size=title_size, color="white")
        ),

        height=height,
        width=width,

        paper_bgcolor="#020617",
        plot_bgcolor="#001a22",

        font=dict(color="white", size=axis_size),

        xaxis=dict(
            range=[min_time, x_axis_max],
            title=dict(text="Time", font=dict(size=axis_size, color="white")),
            showgrid=True,
            gridcolor="rgba(255,255,255,0.10)",
            color="white",
            tickfont=dict(
                size=axis_size,
                color="white",
                family="Arial Black"
            ),
            tickangle=0,
            nticks=24 if discord else 14,
        ),

        yaxis=dict(
            title=dict(
                text=f"{symbol} Price",
                font=dict(size=axis_size, color="white")
            ),
            side="left",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.10)",
            color="white",
            dtick=price_tick_size(symbol),
            tickfont=dict(
                size=axis_size,
                color="white",
                family="Arial Black"
            )
        ),

        yaxis2=dict(
            title=dict(text="Premium Flow", font=dict(size=axis_size, color="white")),
            overlaying="y",
            side="right",
            showgrid=False,
            color="white",
            tickfont=dict(
                size=axis_size,
                color="white",
                family="Arial Black"
            ),
            tickformat="~s",
        ),

        legend=dict(
            orientation="h",
            y=1.05,
            x=0.5,
            xanchor="center",
            bgcolor="rgba(0,0,0,0.45)",
            bordercolor="rgba(255,255,255,0.30)",
            borderwidth=1,
            font=dict(
                size=legend_size,
                color="white",
                family="Arial Black"
            )
        ),

        margin=dict(
            l=100 if discord else 60,
            r=190 if discord else 130,
            t=180 if discord else 120,
            b=120 if discord else 70
        ),

        hovermode="x unified",
    )

    return fig


# ============================================================
# DISCORD SEND
# ============================================================

def send_symbol_to_discord(symbol_data):
    symbol = symbol_data["symbol"]
    webhook_url = get_discord_webhook_for_symbol(symbol)

    if webhook_url:
        print(f"{symbol} webhook ending: {webhook_url[-16:]}")

    if not webhook_url:
        print(f"Missing Discord webhook for {symbol}")
        return False

    try:
        fig = net_flow_chart(
            symbol_data,
            lookback_hours=flow_lookback_hours,
            bucket_minutes=flow_bucket_minutes,
            discord=True
        )

        image_file = tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False
        )

        image_path = image_file.name
        image_file.close()

        fig.write_image(
            image_path,
            width=2300,
            height=1350,
            scale=2
        )

        with open(image_path, "rb") as f:
            response = requests.post(
                webhook_url,
                files={
                    "file": (
                        f"{symbol}_net_flow_dashboard.png",
                        f,
                        "image/png"
                    )
                },
                timeout=30
            )

        try:
            os.remove(image_path)
        except Exception:
            pass

        print(f"{symbol} Discord status:", response.status_code, response.text)

        return response.status_code in [200, 204]

    except Exception as e:
        print(f"{symbol} Discord send failed:")
        print(e)
        return False


# ============================================================
# LOAD DASHBOARD SYMBOL
# ============================================================

try:
    chart_data = load_symbol_flow(chart_symbol)

except Exception as e:
    st.error(f"Failed to load {chart_symbol}.")
    st.exception(e)
    st.stop()


# ============================================================
# DISCORD AUTO SEND
# ============================================================

discord_status = None

if "last_discord_send" not in st.session_state:
    st.session_state.last_discord_send = 0

DISCORD_INTERVAL_SECONDS = 60

seconds_since_last_send = time.time() - st.session_state.last_discord_send

discord_is_open, now_ct = discord_window_open()

should_auto_send = (
    auto_send_discord
    and discord_is_open
    and seconds_since_last_send >= DISCORD_INTERVAL_SECONDS
)

if send_now or should_auto_send:
    send_results = []

    for sym in discord_symbols:
        try:
            # Use the exact same data already plotted on screen
            # when sending the currently selected dashboard symbol.
            # This keeps FLOW dots synchronized between dashboard and Discord.
            if sym == chart_symbol:
                sym_data = chart_data
            else:
                sym_data = load_symbol_flow(sym)

            ok = send_symbol_to_discord(sym_data)
            send_results.append(f"{sym}: {'OK' if ok else 'FAILED'}")

        except Exception as e:
            print(f"{sym} failed:")
            print(e)
            send_results.append(f"{sym}: FAILED")

    st.session_state.last_discord_send = time.time()

    discord_status = " | ".join(send_results)


# ============================================================
# TOP DISPLAY
# ============================================================

if discord_status:
    if "FAILED" in discord_status:
        st.warning(discord_status)
    else:
        st.success(discord_status)

if show_debug:
    webhook_status = {
        sym: bool(get_discord_webhook_for_symbol(sym))
        for sym in ALL_SYMBOLS
    }

    webhook_endings = {
        sym: get_discord_webhook_for_symbol(sym)[-16:]
        if get_discord_webhook_for_symbol(sym) else "MISSING"
        for sym in ALL_SYMBOLS
    }

    st.caption(f"Webhook endings: {webhook_endings}")

    st.caption(
        f"Discord Auto Send: {auto_send_discord} | "
        f"Discord Window Open: {discord_is_open} | "
        f"Current CT: {now_ct.strftime('%I:%M:%S %p')} | "
        f"Seconds Since Last Send: {round(seconds_since_last_send, 1)} | "
        f"Webhooks: {webhook_status}"
    )


m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Symbol", chart_symbol)
m2.metric("Spot", fmt(chart_data["spot"]))
m3.metric("Flow Bias", chart_data["flow_bias"])
m4.metric("Calls", money_fmt(chart_data["call_premium"]))
m5.metric("Puts", money_fmt(chart_data["put_premium"]))


# ============================================================
# MAIN CHART
# ============================================================

st.plotly_chart(
    net_flow_chart(
        chart_data,
        lookback_hours=flow_lookback_hours,
        bucket_minutes=flow_bucket_minutes,
        discord=False
    ),
    use_container_width=True
)


# ============================================================
# RAW DATA
# ============================================================

with st.expander("Session History"):
    st.dataframe(chart_data["history_df"], use_container_width=True)