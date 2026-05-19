import os
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

CENTRAL_TZ = ZoneInfo("America/Chicago")

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

from flow_engine import get_flow_snapshot


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="SG² MATRIX",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# ENV / TRADIER
# =========================================================
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

TRADIER_API_KEY = os.getenv("TRADIER_API_KEY")
TRADIER_BASE_URL = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1")

HEADERS = {
    "Authorization": f"Bearer {TRADIER_API_KEY}",
    "Accept": "application/json",
}


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
            <div class="login-title">🔐 SG² MATRIX</div>
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

    if st.button("ENTER THE FLOW by SG²", use_container_width=True):
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
SYMBOLS = ["SPY", "SPX", "QQQ"]

SYMBOL_ICONS = {
    "SPY": "🕷️",
    "SPX": "📈",
    "QQQ": "📊",
}

FLOW_DOT_THRESHOLDS = {
    "SPY": 25_000_000,
    "SPX": 150_000_000,
    "QQQ": 25_000_000,
}

DIVERGENCE_THRESHOLDS = {
    "SPY": 10_000_000,
    "SPX": 30_000_000,
    "QQQ": 10_000_000,
}

PULSE_DROP_THRESHOLDS = {
    "SPY": 25_000_000,
    "SPX": 100_000_000,
    "QQQ": 25_000_000,
}

CHAIN_WIDTH_DEFAULTS = {
    "SPY": 100,
    "SPX": 500,
    "QQQ": 100,
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
    font-size: 19px;
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
        min_value=2,
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
    show_signed_delta_line = st.checkbox("Show Signed Delta Line", value=False)
    show_right_labels = st.checkbox("Show Right Edge Labels", value=True)

    st.markdown("---")
    st.markdown("### 🧭 Dealer / Structure Levels")

    show_primary_dealer_levels = st.checkbox("Show Primary Dealer Levels", value=True)
    show_oi_levels = st.checkbox("Show OI Levels", value=False)
    show_daily_levels = st.checkbox("Show Daily Supply/Demand", value=False)
    show_weekly_levels = st.checkbox("Show Weekly Levels", value=False)
    show_level_labels = st.checkbox("Show Level Labels", value=True)

    st.caption("Leave a level at 0 to hide it. Call/Put walls are calculated from option-chain gamma.")

    gamma_flip_level = st.number_input(
        "Gamma Flip",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.2f",
        key=f"gamma_flip_level_{symbol}",
    )

    volatility_trigger_level = st.number_input(
        "Volatility Trigger",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.2f",
        key=f"volatility_trigger_level_{symbol}",
    )

    with st.expander("Daily Supply / Demand Inputs", expanded=False):
        daily_supply_level = st.number_input(
            "Daily Supply", min_value=0.0, value=0.0, step=0.5, format="%.2f",
            key=f"daily_supply_level_{symbol}"
        )
        daily_mid_level = st.number_input(
            "Daily Mid", min_value=0.0, value=0.0, step=0.5, format="%.2f",
            key=f"daily_mid_level_{symbol}"
        )
        daily_demand_level = st.number_input(
            "Daily Demand", min_value=0.0, value=0.0, step=0.5, format="%.2f",
            key=f"daily_demand_level_{symbol}"
        )

    with st.expander("Weekly Supply / Demand Inputs", expanded=False):
        weekly_supply_level = st.number_input(
            "Weekly Supply", min_value=0.0, value=0.0, step=0.5, format="%.2f",
            key=f"weekly_supply_level_{symbol}"
        )
        weekly_mid_level = st.number_input(
            "Weekly Mid", min_value=0.0, value=0.0, step=0.5, format="%.2f",
            key=f"weekly_mid_level_{symbol}"
        )
        weekly_demand_level = st.number_input(
            "Weekly Demand", min_value=0.0, value=0.0, step=0.5, format="%.2f",
            key=f"weekly_demand_level_{symbol}"
        )

    default_flow_dot_threshold = FLOW_DOT_THRESHOLDS.get(symbol, 25_000_000)

    flow_dot_threshold = st.number_input(
        "FLOW Dot Threshold",
        min_value=0,
        value=default_flow_dot_threshold,
        step=5_000_000,
        key=f"flow_dot_threshold_{symbol}",
    )

    st.caption(f"Default for {symbol}: {default_flow_dot_threshold:,}")

    show_matrix = st.checkbox("Show SG² Matrix", value=True)

    divergence_threshold = st.number_input(
        "Divergence Threshold",
        min_value=0,
        value=DIVERGENCE_THRESHOLDS.get(symbol, 10_000_000),
        step=1_000_000,
        key=f"divergence_threshold_{symbol}",
    )

    pulse_drop_threshold = st.number_input(
        "Pulse/Drop Threshold",
        min_value=0,
        value=PULSE_DROP_THRESHOLDS.get(symbol, 25_000_000),
        step=1_000_000,
        key=f"pulse_drop_threshold_{symbol}",
    )

    chain_width = st.slider(
        "Strike Width Around Spot",
        min_value=25,
        max_value=1000,
        value=CHAIN_WIDTH_DEFAULTS.get(symbol, 100),
        step=25,
    )

    reset_exp_history = st.button("Reset Flow Chart History")

    st.markdown("---")
    st.caption("Chart model: 0DTE and All Expiration net premium flow changes.")
    st.caption("FLOW dots trigger when flow crosses positive/negative threshold.")


if auto_refresh:
    st_autorefresh(
        interval=refresh_interval * 1000,
        key="flow_refresh_main",
    )


# =========================================================
# FORMAT HELPERS
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


def fmt_price(value):
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "—"


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


# =========================================================
# TRADIER / EXPIRATION FLOW ENGINE
# =========================================================
def tradier_get(endpoint, params=None):
    if not TRADIER_API_KEY:
        raise Exception("Missing TRADIER_API_KEY in .env")

    url = f"{TRADIER_BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=25,
    )

    if response.status_code != 200:
        raise Exception(f"Tradier error {response.status_code}: {response.text}")

    return response.json()


def get_price(symbol):
    data = tradier_get(
        "markets/quotes",
        params={"symbols": symbol},
    )

    quote = data.get("quotes", {}).get("quote", {})

    if isinstance(quote, list):
        quote = quote[0] if quote else {}

    for field in ["last", "close", "prevclose", "bid", "ask"]:
        try:
            value = float(quote.get(field))
            if value > 0:
                return value
        except Exception:
            pass

    raise Exception(f"No valid price returned for {symbol}: {quote}")


def get_expirations(symbol):
    data = tradier_get(
        "markets/options/expirations",
        params={
            "symbol": symbol,
            "includeAllRoots": "true",
            "strikes": "false",
        },
    )

    block = data.get("expirations")

    if block is None:
        raise Exception(f"No expirations returned for {symbol}: {data}")

    expirations = block.get("date", [])

    if isinstance(expirations, str):
        expirations = [expirations]

    if not expirations:
        raise Exception(f"Empty expirations for {symbol}: {data}")

    return expirations


def flatten_greeks(df):
    if "greeks" not in df.columns:
        return df

    def get_greek(row, key):
        g = row.get("greeks", {})
        if isinstance(g, dict):
            return g.get(key)
        return None

    for key in ["delta", "gamma", "theta", "vega", "rho"]:
        if key not in df.columns:
            df[key] = df.apply(lambda row: get_greek(row, key), axis=1)

    return df


def get_option_chain(symbol, expiration):
    data = tradier_get(
        "markets/options/chains",
        params={
            "symbol": symbol,
            "expiration": expiration,
            "greeks": "true",
        },
    )

    options_block = data.get("options")

    if not options_block:
        return pd.DataFrame()

    options = options_block.get("option", [])

    if isinstance(options, dict):
        options = [options]

    if not options:
        return pd.DataFrame()

    df = pd.DataFrame(options)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    df = flatten_greeks(df)

    if "option_type" in df.columns:
        df["type"] = df["option_type"]
    elif "put_call" in df.columns:
        df["type"] = df["put_call"]
    elif "contract_type" in df.columns:
        df["type"] = df["contract_type"]
    elif "type" not in df.columns:
        raise Exception(f"No option type column found. Columns: {df.columns.tolist()}")

    rename_map = {
        "last_price": "last",
        "trade_volume": "volume",
        "open_int": "open_interest",
        "oi": "open_interest",
        "expiration_date": "expiration",
        "exp_date": "expiration",
        "expiry": "expiration",
    }

    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    if "expiration" not in df.columns:
        df["expiration"] = expiration

    df["type"] = (
        df["type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .replace(
            {
                "calls": "call",
                "puts": "put",
                "c": "call",
                "p": "put",
            }
        )
    )

    if "last" not in df.columns:
        if "bid" in df.columns and "ask" in df.columns:
            df["last"] = (
                pd.to_numeric(df["bid"], errors="coerce").fillna(0)
                + pd.to_numeric(df["ask"], errors="coerce").fillna(0)
            ) / 2
        else:
            df["last"] = 0

    if "volume" not in df.columns:
        df["volume"] = 0

    if "open_interest" not in df.columns:
        df["open_interest"] = 0

    for col in [
        "strike",
        "last",
        "volume",
        "open_interest",
        "bid",
        "ask",
        "delta",
        "gamma",
        "theta",
        "vega",
        "rho",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(subset=["strike"])
    df = df[df["type"].isin(["call", "put"])]

    return df


def filter_near_spot(df, spot, width):
    return df[
        (df["strike"] >= float(spot) - width)
        & (df["strike"] <= float(spot) + width)
    ].copy()


def calculate_net_flow(chain_df):
    if chain_df is None or chain_df.empty:
        return {
            "call_premium": 0,
            "put_premium": 0,
            "net_premium": 0,
            "rows": 0,
        }

    df = chain_df.copy()

    df["activity"] = pd.to_numeric(
        df.get("volume", 0),
        errors="coerce",
    ).fillna(0)

    df["open_interest"] = pd.to_numeric(
        df.get("open_interest", 0),
        errors="coerce",
    ).fillna(0)

    df.loc[df["activity"] <= 0, "activity"] = df["open_interest"]

    df["last"] = pd.to_numeric(
        df.get("last", 0),
        errors="coerce",
    ).fillna(0)

    df["premium"] = df["last"] * df["activity"] * 100

    calls = df[df["type"].str.contains("call", na=False)]
    puts = df[df["type"].str.contains("put", na=False)]

    call_premium = calls["premium"].sum()
    put_premium = puts["premium"].sum()
    net_premium = call_premium - put_premium

    return {
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": net_premium,
        "rows": len(df),
    }


def get_gamma_levels(chain_df, spot):
    if chain_df is None or chain_df.empty:
        return {
            "top_call_gamma": None,
            "top_put_gamma": None,
        }

    df = chain_df.copy()

    if "gamma" not in df.columns:
        return {
            "top_call_gamma": None,
            "top_put_gamma": None,
        }

    df["gamma"] = pd.to_numeric(df["gamma"], errors="coerce").fillna(0)
    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce").fillna(0)

    df["gamma_exposure"] = df["gamma"] * df["open_interest"] * 100

    spot = float(spot)

    calls = df[
        (df["type"] == "call")
        & (df["strike"] >= spot)
    ].copy()

    puts = df[
        (df["type"] == "put")
        & (df["strike"] <= spot)
    ].copy()

    call_gamma = (
        calls.groupby("strike")["gamma_exposure"]
        .sum()
        .sort_values(ascending=False)
    )

    put_gamma = (
        puts.groupby("strike")["gamma_exposure"]
        .sum()
        .sort_values(ascending=False)
    )

    top_call = float(call_gamma.index[0]) if not call_gamma.empty else None
    top_put = float(put_gamma.index[0]) if not put_gamma.empty else None

    return {
        "top_call_gamma": top_call,
        "top_put_gamma": top_put,
    }




def get_top_oi_levels(chain_df, spot, top_n=2):
    if chain_df is None or chain_df.empty:
        return {"top_call_oi": [], "top_put_oi": []}

    df = chain_df.copy()

    if "open_interest" not in df.columns or "strike" not in df.columns or "type" not in df.columns:
        return {"top_call_oi": [], "top_put_oi": []}

    df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)
    df["strike"] = pd.to_numeric(df["strike"], errors="coerce").fillna(0)
    df = df[df["open_interest"] > 0]

    spot = float(spot)

    calls = df[(df["type"] == "call") & (df["strike"] >= spot)].copy()
    puts = df[(df["type"] == "put") & (df["strike"] <= spot)].copy()

    call_oi = (
        calls.groupby("strike")["open_interest"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
    )

    put_oi = (
        puts.groupby("strike")["open_interest"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
    )

    return {
        "top_call_oi": [float(x) for x in call_oi.index.tolist()],
        "top_put_oi": [float(x) for x in put_oi.index.tolist()],
    }


def build_manual_levels():
    return {
        "gamma_flip": gamma_flip_level,
        "volatility_trigger": volatility_trigger_level,
        "daily_supply": daily_supply_level,
        "daily_mid": daily_mid_level,
        "daily_demand": daily_demand_level,
        "weekly_supply": weekly_supply_level,
        "weekly_mid": weekly_mid_level,
        "weekly_demand": weekly_demand_level,
    }


def load_expiration_flow(symbol):
    spot = get_price(symbol)
    expirations = get_expirations(symbol)

    today_exp = expirations[0]
    selected_expirations = expirations[:all_exp_count]

    chains = []

    zero_dte_chain = get_option_chain(symbol, today_exp)

    if zero_dte_chain is not None and not zero_dte_chain.empty:
        zero_dte_chain = filter_near_spot(
            zero_dte_chain,
            spot,
            chain_width,
        )

    for exp in selected_expirations:
        temp = get_option_chain(symbol, exp)

        if temp is not None and not temp.empty:
            temp["expiration"] = exp
            chains.append(temp)

    if chains:
        all_chain = pd.concat(chains, ignore_index=True)
        all_chain = filter_near_spot(
            all_chain,
            spot,
            chain_width,
        )
    else:
        all_chain = pd.DataFrame()

    zero_flow = calculate_net_flow(zero_dte_chain)
    all_flow = calculate_net_flow(all_chain)
    gamma_levels = get_gamma_levels(all_chain, spot)
    oi_levels = get_top_oi_levels(all_chain, spot, top_n=2)

    return {
        "symbol": symbol,
        "spot": spot,
        "today_exp": today_exp,
        "expirations_used": selected_expirations,
        "zero_dte": zero_flow,
        "all_exp": all_flow,
        "gamma_levels": gamma_levels,
        "oi_levels": oi_levels,
        "manual_levels": build_manual_levels(),
    }


# =========================================================
# SESSION FILE HISTORY FOR DISCORD-STYLE CHART
# =========================================================
SESSION_DIR = Path(__file__).parent / "expiration_flow_history"
SESSION_DIR.mkdir(exist_ok=True)


def session_file(symbol):
    return SESSION_DIR / f"expiration_flow_{symbol.upper()}.csv"


def reset_symbol_history(symbol):
    file_path = session_file(symbol)
    if file_path.exists():
        file_path.unlink()


def append_exp_snapshot(flow_data):
    file_path = session_file(flow_data["symbol"])

    now = datetime.now(CENTRAL_TZ)

    row = {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.strftime("%H:%M:%S"),
        "symbol": flow_data["symbol"],
        "spot": flow_data["spot"],
        "zero_dte_call_premium": flow_data["zero_dte"]["call_premium"],
        "zero_dte_put_premium": flow_data["zero_dte"]["put_premium"],
        "zero_dte_net_premium": flow_data["zero_dte"]["net_premium"],
        "all_exp_call_premium": flow_data["all_exp"]["call_premium"],
        "all_exp_put_premium": flow_data["all_exp"]["put_premium"],
        "all_exp_net_premium": flow_data["all_exp"]["net_premium"],
        "zero_dte_rows": flow_data["zero_dte"]["rows"],
        "all_exp_rows": flow_data["all_exp"]["rows"],
    }

    if file_path.exists():
        try:
            df = pd.read_csv(file_path)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    df = pd.concat(
        [df, pd.DataFrame([row])],
        ignore_index=True,
    )

    df.to_csv(file_path, index=False)

    return df


def normalize_history(df):
    df = df.copy()

    df["datetime"] = pd.to_datetime(
        df.get("datetime", pd.NaT),
        errors="coerce",
    )

    df = df.dropna(subset=["datetime"]).sort_values("datetime")

    return df


def build_chart_df(history_df):
    if history_df is None or history_df.empty:
        return pd.DataFrame()

    df = normalize_history(history_df)

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
        .resample(f"{chart_bucket}min")
        .agg(
            {
                "spot": "last",
                "zero_dte_net_premium": "last",
                "all_exp_net_premium": "last",
            }
        )
        .dropna(how="all")
        .reset_index()
    )

    for col in ["spot", "zero_dte_net_premium", "all_exp_net_premium"]:
        df[col] = pd.to_numeric(
            df.get(col, 0),
            errors="coerce",
        ).ffill().fillna(0)

    df["zero_dte_flow"] = df["zero_dte_net_premium"].diff().fillna(0).cumsum()
    df["all_exp_flow"] = df["all_exp_net_premium"].diff().fillna(0).cumsum()
    df["time"] = pd.to_datetime(df["datetime"]).dt.strftime("%I:%M:%S %p")

    return df


def add_right_edge_label(fig, x, y, text, bg, yref="y", xshift=10):
    fig.add_annotation(
        x=x,
        y=y,
        text=f"<b>{text}</b>",
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




def valid_level(value):
    try:
        value = float(value)
        return value if value > 0 else None
    except Exception:
        return None


def add_price_level(fig, value, label, color, dash="dash", width=2, position="top left"):
    level = valid_level(value)
    if level is None:
        return

    fig.add_hline(
        y=level,
        line=dict(color=color, width=width, dash=dash),
        yref="y2",
        annotation_text=f"{label} {fmt_price(level)}" if show_level_labels else None,
        annotation_position=position,
        annotation_font=dict(color=color, size=12, family="Arial Black"),
        annotation_bgcolor="rgba(0,0,0,0.70)",
    )


def add_price_zone(fig, upper, lower, label, color):
    upper = valid_level(upper)
    lower = valid_level(lower)
    if upper is None or lower is None:
        return

    lo = min(upper, lower)
    hi = max(upper, lower)

    fig.add_hrect(
        y0=lo,
        y1=hi,
        yref="y2",
        line_width=0,
        fillcolor=color,
        opacity=0.11,
        annotation_text=label if show_level_labels else None,
        annotation_position="top left",
        annotation_font=dict(color="white", size=11, family="Arial Black"),
    )


# =========================================================
# CHART BUILDER - DISCORD STYLE
# =========================================================
def sg2_flow_chart(history_df, symbol, flow_data):
    df = build_chart_df(history_df)

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"No flow history yet for {symbol}",
            height=560,
            paper_bgcolor="#111923",
            plot_bgcolor="#252a2f",
            font=dict(color="white"),
        )
        return fig

    df["time"] = df["time"].astype(str)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["spot"],
            mode="lines",
            name=f"{symbol} Price",
            line=dict(color="#ffffff", width=4),
            yaxis="y2",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["all_exp_flow"],
            mode="lines",
            name="All Expirations",
            line=dict(color="#ffe100", width=5),
            yaxis="y",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["zero_dte_flow"],
            mode="lines",
            name="0DTE",
            line=dict(color="#00ff38", width=5),
            yaxis="y",
        )
    )

    if show_signed_delta_line:
        try:
            signed_snapshot = get_flow_snapshot(
                symbol=symbol,
                all_exp_count=all_exp_count,
                chart_bucket=chart_bucket,
                lookback_hours=lookback_hours,
                strike_width=chain_width,
            )
            signed_delta_value = safe_get(signed_snapshot, "odte_signed_delta", 0)
            df["signed_delta"] = float(signed_delta_value)
            fig.add_trace(
                go.Scatter(
                    x=df["time"],
                    y=df["signed_delta"],
                    mode="lines",
                    name="Signed Delta",
                    line=dict(color="#00e5ff", width=1.5, dash="dot"),
                    yaxis="y",
                )
            )
        except Exception:
            pass

    gamma_levels = flow_data.get("gamma_levels", {}) or {}

    call_gamma_level = gamma_levels.get("top_call_gamma")
    put_gamma_level = gamma_levels.get("top_put_gamma")

    try:
        call_gamma_level = float(call_gamma_level) if call_gamma_level else None
    except Exception:
        call_gamma_level = None

    try:
        put_gamma_level = float(put_gamma_level) if put_gamma_level else None
    except Exception:
        put_gamma_level = None

    manual_levels = flow_data.get("manual_levels", {}) or {}
    oi_levels = flow_data.get("oi_levels", {}) or {}

    if show_primary_dealer_levels:
        add_price_level(fig, call_gamma_level, "Call Wall", "#22c55e", dash="dash", width=4, position="top left")
        add_price_level(fig, put_gamma_level, "Put Wall", "#ef4444", dash="dash", width=4, position="bottom left")
        add_price_level(fig, manual_levels.get("gamma_flip"), "Gamma Flip", "#00e5ff", dash="solid", width=4, position="top right")
        add_price_level(fig, manual_levels.get("volatility_trigger"), "Vol Trigger", "#a855f7", dash="solid", width=4, position="bottom right")

    if show_oi_levels:
        for idx, level in enumerate(oi_levels.get("top_call_oi", []), start=1):
            add_price_level(fig, level, f"Call OI {idx}", "#facc15", dash="dot", width=2, position="top left")

        for idx, level in enumerate(oi_levels.get("top_put_oi", []), start=1):
            add_price_level(fig, level, f"Put OI {idx}", "#cbd5e1", dash="dot", width=2, position="bottom left")

    if show_daily_levels:
        add_price_zone(fig, manual_levels.get("daily_supply"), manual_levels.get("daily_mid"), "Daily Supply", "#ef4444")
        add_price_zone(fig, manual_levels.get("daily_mid"), manual_levels.get("daily_demand"), "Daily Demand", "#22c55e")
        add_price_level(fig, manual_levels.get("daily_supply"), "Daily Supply", "#ef4444", dash="dash", width=2, position="top left")
        add_price_level(fig, manual_levels.get("daily_mid"), "Daily Mid", "#facc15", dash="dot", width=2, position="top left")
        add_price_level(fig, manual_levels.get("daily_demand"), "Daily Demand", "#22c55e", dash="dash", width=2, position="bottom left")

    if show_weekly_levels:
        add_price_zone(fig, manual_levels.get("weekly_supply"), manual_levels.get("weekly_mid"), "Weekly Supply", "#991b1b")
        add_price_zone(fig, manual_levels.get("weekly_mid"), manual_levels.get("weekly_demand"), "Weekly Demand", "#166534")
        add_price_level(fig, manual_levels.get("weekly_supply"), "Weekly Supply", "#f87171", dash="longdash", width=3, position="top right")
        add_price_level(fig, manual_levels.get("weekly_mid"), "Weekly Mid", "#fde047", dash="dot", width=2, position="top right")
        add_price_level(fig, manual_levels.get("weekly_demand"), "Weekly Demand", "#4ade80", dash="longdash", width=3, position="bottom right")

    if show_flow_dots:
        threshold = float(flow_dot_threshold)

        df["zero_bull_flow_dot"] = (
            (df["zero_dte_flow"] > threshold)
            & (df["zero_dte_flow"].shift(1) <= threshold)
        )

        df["zero_bear_flow_dot"] = (
            (df["zero_dte_flow"] < -threshold)
            & (df["zero_dte_flow"].shift(1) >= -threshold)
        )

        df["all_bull_flow_dot"] = (
            (df["all_exp_flow"] > threshold)
            & (df["all_exp_flow"].shift(1) <= threshold)
        )

        df["all_bear_flow_dot"] = (
            (df["all_exp_flow"] < -threshold)
            & (df["all_exp_flow"].shift(1) >= -threshold)
        )

        zero_bull = df[df["zero_bull_flow_dot"]]
        zero_bear = df[df["zero_bear_flow_dot"]]
        all_bull = df[df["all_bull_flow_dot"]]
        all_bear = df[df["all_bear_flow_dot"]]

        fig.add_trace(
            go.Scatter(
                x=zero_bull["time"],
                y=zero_bull["zero_dte_flow"],
                mode="markers+text",
                name="0DTE Bull FLOW",
                marker=dict(
                    size=18,
                    color="#22c55e",
                    symbol="circle",
                    line=dict(color="white", width=2),
                ),
                text=["FLOW"] * len(zero_bull),
                textposition="top center",
                textfont=dict(color="white", size=11, family="Arial Black"),
                yaxis="y",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=zero_bear["time"],
                y=zero_bear["zero_dte_flow"],
                mode="markers+text",
                name="0DTE Bear FLOW",
                marker=dict(
                    size=18,
                    color="#ef4444",
                    symbol="circle",
                    line=dict(color="white", width=2),
                ),
                text=["FLOW"] * len(zero_bear),
                textposition="bottom center",
                textfont=dict(color="white", size=11, family="Arial Black"),
                yaxis="y",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=all_bull["time"],
                y=all_bull["all_exp_flow"],
                mode="markers+text",
                name="All Exp Bull FLOW",
                marker=dict(
                    size=16,
                    color="#facc15",
                    symbol="diamond",
                    line=dict(color="white", width=2),
                ),
                text=["FLOW"] * len(all_bull),
                textposition="top center",
                textfont=dict(color="white", size=10, family="Arial Black"),
                yaxis="y",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=all_bear["time"],
                y=all_bear["all_exp_flow"],
                mode="markers+text",
                name="All Exp Bear FLOW",
                marker=dict(
                    size=16,
                    color="#f97316",
                    symbol="diamond",
                    line=dict(color="white", width=2),
                ),
                text=["FLOW"] * len(all_bear),
                textposition="bottom center",
                textfont=dict(color="white", size=10, family="Arial Black"),
                yaxis="y",
            )
        )

    fig.add_hline(
        y=0,
        line=dict(color="white", width=2, dash="solid"),
        yref="y",
    )

    latest_all = df["all_exp_flow"].iloc[-1]
    latest_zero = df["zero_dte_flow"].iloc[-1]
    latest_spot = df["spot"].iloc[-1]
    latest_time = str(df["time"].iloc[-1])

    if show_right_labels:
        add_right_edge_label(
            fig,
            latest_time,
            latest_all,
            fmt_money(latest_all),
            "#ffe100",
            yref="y",
        )

        add_right_edge_label(
            fig,
            latest_time,
            latest_zero,
            fmt_money(latest_zero),
            "#00ff38",
            yref="y",
        )

        add_right_edge_label(
            fig,
            latest_time,
            latest_spot,
            fmt_price(latest_spot),
            "#ffffff",
            yref="y2",
        )

    flow_min = min(df["all_exp_flow"].min(), df["zero_dte_flow"].min(), 0)
    flow_max = max(df["all_exp_flow"].max(), df["zero_dte_flow"].max(), 0)

    flow_span = flow_max - flow_min
    if flow_span <= 0:
        flow_span = max(abs(flow_max), abs(flow_min), 1)

    flow_pad = flow_span * 0.18
    flow_range = [flow_min - flow_pad, flow_max + flow_pad]

    price_min = df["spot"].min()
    price_max = df["spot"].max()

    extra_price_levels = []

    for gamma_key in ["top_call_gamma", "top_put_gamma"]:
        extra_price_levels.append(gamma_levels.get(gamma_key))

    manual_levels = flow_data.get("manual_levels", {}) or {}
    extra_price_levels.extend(manual_levels.values())

    oi_levels = flow_data.get("oi_levels", {}) or {}
    extra_price_levels.extend(oi_levels.get("top_call_oi", []))
    extra_price_levels.extend(oi_levels.get("top_put_oi", []))

    for level in extra_price_levels:
        try:
            level = float(level)
            if level > 0:
                price_min = min(price_min, level)
                price_max = max(price_max, level)
        except Exception:
            pass

    price_span = price_max - price_min

    if price_span <= 0:
        if symbol.upper() == "SPX":
            price_span = 10
        elif symbol.upper() == "TSLA":
            price_span = 5
        elif symbol.upper() == "QQQ":
            price_span = 1
        else:
            price_span = 0.75

    price_pad = price_span * 0.35
    price_range = [price_min - price_pad, price_max + price_pad]

    if symbol.upper() == "SPX":
        price_dtick = 5
    elif symbol.upper() == "TSLA":
        price_dtick = 2.5
    elif symbol.upper() in ["SPY", "QQQ"]:
        price_dtick = 0.5
    else:
        price_dtick = 1

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{symbol} Flow Trend | {chart_bucket}-Min Bars</b><br>"
                f"<span style='font-size:14px;'>"
                f"0DTE Exp: {flow_data['today_exp']} | "
                f"All Exp Used: {len(flow_data['expirations_used'])} | "
                f"Spot: {fmt_price(flow_data['spot'])}"
                f"</span>"
            ),
            x=0.01,
            xanchor="left",
            font=dict(size=20, color="white"),
        ),
        height=540,
        paper_bgcolor="#111923",
        plot_bgcolor="#252a2f",
        font=dict(color="white", size=13),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.16)",
            tickfont=dict(color="white", size=11, family="Arial Black"),
            nticks=18,
            type="category",
        ),
        yaxis=dict(
            title=dict(
                text="Premium Flow",
                font=dict(color="#facc15", size=14),
            ),
            side="left",
            range=flow_range,
            showgrid=True,
            gridcolor="rgba(255,255,255,0.18)",
            zeroline=True,
            zerolinecolor="white",
            tickformat="~s",
            tickfont=dict(color="#facc15", size=13, family="Arial Black"),
        ),
        yaxis2=dict(
            title=dict(
                text=f"{symbol} Price",
                font=dict(color="#ffffff", size=14),
            ),
            overlaying="y",
            side="right",
            range=price_range,
            showgrid=False,
            dtick=price_dtick,
            tickfont=dict(color="#ffffff", size=13, family="Arial Black"),
        ),
        legend=dict(
            orientation="h",
            x=0.01,
            y=-0.24,
            bgcolor="rgba(0,0,0,0.25)",
            font=dict(color="white", size=12, family="Arial Black"),
        ),
        margin=dict(l=75, r=105, t=80, b=95),
        hovermode="x unified",
    )

    return fig


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
# RESET HISTORY
# =========================================================
if reset_exp_history:
    reset_symbol_history(symbol)
    st.success(f"{symbol} flow chart history reset.")


# =========================================================
# LOAD SG2 SNAPSHOT FOR METRICS / MATRIX
# =========================================================
try:
    snapshot = get_flow_snapshot(
        symbol=symbol,
        all_exp_count=all_exp_count,
        chart_bucket=chart_bucket,
        lookback_hours=lookback_hours,
        strike_width=chain_width,
    )
except Exception as e:
    st.warning(f"Could not load SG² metric snapshot for {symbol}: {e}")
    snapshot = {}


# =========================================================
# LOAD EXPIRATION FLOW FOR MAIN CHART
# =========================================================
try:
    exp_flow_data = load_expiration_flow(symbol)
    exp_history_df = append_exp_snapshot(exp_flow_data)
except Exception as e:
    st.error(f"Could not load expiration flow chart data for {symbol}: {e}")
    st.stop()


spot = safe_get(snapshot, "spot", exp_flow_data.get("spot", 0))
odte_exp = safe_get(snapshot, "odte_exp", exp_flow_data.get("today_exp", ""))

odte_premium_net = exp_flow_data["zero_dte"]["net_premium"]
all_exp_premium_net = exp_flow_data["all_exp"]["net_premium"]

odte_signed_delta = safe_get(snapshot, "odte_signed_delta", 0)
odte_delta_bias = safe_get(snapshot, "odte_delta_bias", "NEUTRAL")
all_exp_delta_bias = safe_get(snapshot, "all_exp_delta_bias", "NEUTRAL")

gamma_levels = exp_flow_data.get("gamma_levels", {})
call_gamma = gamma_levels.get("top_call_gamma") or safe_get(snapshot, "call_gamma", 0)
put_gamma = gamma_levels.get("top_put_gamma") or safe_get(snapshot, "put_gamma", 0)
gamma_regime = safe_get(snapshot, "gamma_regime", "NEUTRAL")

odte_rows = exp_flow_data["zero_dte"]["rows"]
all_exp_rows = exp_flow_data["all_exp"]["rows"]


# =========================================================
# VOLUME STATS
# =========================================================
chain_df = safe_get(snapshot, "chain_df", pd.DataFrame())

if isinstance(chain_df, pd.DataFrame) and not chain_df.empty and "volume" in chain_df.columns:
    try:
        calls = chain_df[chain_df["type"] == "call"]
        puts = chain_df[chain_df["type"] == "put"]
        call_volume = calls["volume"].sum()
        put_volume = puts["volume"].sum()
        total_volume = call_volume + put_volume
        pc_ratio = put_volume / call_volume if call_volume > 0 else 0
    except Exception:
        call_volume, put_volume, total_volume, pc_ratio = 0, 0, 0, 0
else:
    call_volume, put_volume, total_volume, pc_ratio = 0, 0, 0, 0


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
    metric_html("Call Wall", fmt_price(call_gamma), "green-text"),
    unsafe_allow_html=True,
)

r1[4].markdown(
    metric_html("Put Wall", fmt_price(put_gamma), "red-text"),
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
today_txt = datetime.now(CENTRAL_TZ).strftime("%A, %B %d, %Y")

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
left_chart, right_matrix = st.columns([2.7, 1.5])


# =========================================================
# MAIN FLOW CHART
# =========================================================
with left_chart:
    st.plotly_chart(
        sg2_flow_chart(
            exp_history_df,
            symbol,
            exp_flow_data,
        ),
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
            '<div class="matrix-title">🧠 SG² MATRIX</div>',
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
                        strike_width=chain_width,
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
