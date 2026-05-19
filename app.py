# ============================================================
# app.py
# SG² MATRIX
# SPY / SPX / QQQ
# Gamma-only chart + clean dot matrix
# Chart style based on expiration_flow_dashboard.py
# ============================================================

import os
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

CENTRAL_TZ = ZoneInfo("America/Chicago")

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="SG² MATRIX",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# ENV / TRADIER
# ============================================================

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

TRADIER_API_KEY = os.getenv("TRADIER_API_KEY")
TRADIER_BASE_URL = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1")

HEADERS = {
    "Authorization": f"Bearer {TRADIER_API_KEY}",
    "Accept": "application/json",
}

# ============================================================
# SYMBOL CONFIG
# ============================================================

SYMBOLS = ["SPY", "SPX", "QQQ"]

SYMBOL_ICONS = {
    "SPY": "🕷️",
    "SPX": "📈",
    "QQQ": "📊",
}

FLOW_DOT_DEFAULTS = {
    "SPY": 25_000_000,
    "SPX": 150_000_000,
    "QQQ": 25_000_000,
}

DIVERGENCE_DEFAULTS = {
    "SPY": 10_000_000,
    "SPX": 30_000_000,
    "QQQ": 10_000_000,
}

PULSE_DEFAULTS = {
    "SPY": 25_000_000,
    "SPX": 100_000_000,
    "QQQ": 25_000_000,
}

CHAIN_WIDTH_DEFAULTS = {
    "SPY": 100,
    "SPX": 500,
    "QQQ": 100,
}

# ============================================================
# PASSWORD PROTECTION
# ============================================================

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

    st.markdown('<div class="password-label">Enter Password</div>', unsafe_allow_html=True)

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

# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "SPX"

if st.session_state.selected_symbol not in SYMBOLS:
    st.session_state.selected_symbol = "SPX"

symbol = st.session_state.selected_symbol

# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown(
    """
<style>
html, body, .stApp {
    background: radial-gradient(circle at top left, #101923 0%, #060a0f 42%, #010305 100%) !important;
    color: #f4f7fb !important;
}

.main .block-container {
    background: transparent !important;
    padding-top: 1rem;
    padding-left: 1.25rem;
    padding-right: 1.25rem;
    max-width: 100%;
}

[data-testid="stHeader"] {
    background: transparent !important;
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

.top-card,
.chart-card,
.matrix-card,
.metric-card {
    background: linear-gradient(145deg, rgba(17,25,35,.98), rgba(6,11,16,.98)) !important;
    border: 1px solid #263746;
    border-radius: 16px;
    box-shadow: 0 0 22px rgba(0,0,0,.45);
}

.top-card {
    padding: 18px 22px;
    margin-bottom: 14px;
}

.chart-card {
    padding: 14px 14px 4px 14px;
}

.matrix-card {
    padding: 14px;
}

.top-title {
    font-size: 26px;
    font-weight: 950;
    color: white;
    margin-bottom: 12px;
}

.top-line {
    font-size: 14px;
    font-weight: 900;
    color: white;
}

.green-text { color: #31e75f !important; }
.red-text { color: #ff4b4b !important; }
.yellow-text { color: #ffdd00 !important; }
.cyan-text { color: #00e5ff !important; }

.matrix-title {
    color: white;
    font-size: 22px;
    font-weight: 950;
    margin-bottom: 14px;
    letter-spacing: .4px;
}

.sg2-dot-matrix table {
    width: 100%;
    border-collapse: collapse;
    background: #0b1118;
    color: white;
    font-size: 18px;
    border-radius: 14px;
    overflow: hidden;
    table-layout: fixed;
}

.sg2-dot-matrix th {
    color: #ffdd00;
    background: linear-gradient(180deg, #14202b, #0e1720);
    padding: 15px 8px;
    border: 1px solid rgba(38,50,65,.55);
    text-align: center;
    font-weight: 950;
}

.sg2-dot-matrix td {
    padding: 18px 8px;
    border: 1px solid rgba(38,50,65,.45);
    text-align: center;
    background: rgba(8,13,19,.86);
    font-weight: 950;
}

.sg2-dot-matrix tr:nth-child(even) td {
    background: rgba(13,20,29,.92);
}

.sg2-dot-matrix td:first-child,
.sg2-dot-matrix th:first-child {
    text-align: left;
    width: 28%;
}

.dot {
    display: inline-block;
    width: 19px;
    height: 19px;
    border-radius: 50%;
    vertical-align: middle;
    box-shadow: 0 0 12px currentColor, inset 0 0 7px rgba(255,255,255,.45);
}

.dot-green {
    background: #31e75f;
    color: #31e75f;
}

.dot-red {
    background: #ff4b4b;
    color: #ff4b4b;
}

.dot-purple {
    background: #a855f7;
    color: #a855f7;
}

.dot-yellow {
    background: #facc15;
    color: #facc15;
}

.symbol-cell {
    color: white;
    font-weight: 950;
    white-space: nowrap;
}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ Dashboard Controls")

    auto_refresh = st.checkbox("Auto Refresh", value=True)

    refresh_seconds = st.selectbox(
        "Refresh Interval",
        [5, 10, 15, 30, 60],
        index=2,
    )

    expiration_count = st.slider(
        "All Expirations Count",
        min_value=2,
        max_value=10,
        value=5,
        step=1,
    )

    bucket_minutes = st.selectbox(
        "Chart Bucket",
        [1, 3, 5],
        index=0,
    )

    lookback_hours = st.slider(
        "Lookback Hours",
        min_value=1,
        max_value=10,
        value=2,
        step=1,
    )

    show_flow_dots = st.checkbox("Show FLOW Dots", value=True)
    show_right_labels = st.checkbox("Show Right Edge Labels", value=True)

    default_flow_dot_threshold = FLOW_DOT_DEFAULTS.get(symbol.upper(), 25_000_000)

    flow_dot_threshold = st.number_input(
        "FLOW Dot Threshold",
        min_value=0,
        value=default_flow_dot_threshold,
        step=5_000_000,
    )

    divergence_threshold = st.number_input(
        "Divergence Threshold",
        min_value=0,
        value=DIVERGENCE_DEFAULTS.get(symbol.upper(), 10_000_000),
        step=1_000_000,
    )

    pulse_threshold = st.number_input(
        "Pulse Threshold",
        min_value=0,
        value=PULSE_DEFAULTS.get(symbol.upper(), 25_000_000),
        step=1_000_000,
    )

    chain_width = st.slider(
        "Strike Width Around Spot",
        min_value=25,
        max_value=1000,
        value=CHAIN_WIDTH_DEFAULTS.get(symbol.upper(), 100),
        step=25,
    )

    reset_history = st.button("Reset Flow Chart History")

if auto_refresh:
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="sg2_matrix_refresh",
    )

# ============================================================
# HELPERS
# ============================================================

def money_fmt(v):
    try:
        v = float(v)

        if abs(v) >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f}B"

        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"

        if abs(v) >= 1_000:
            return f"{v / 1_000:.0f}K"

        return f"{v:.0f}"

    except Exception:
        return "—"


def fmt(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "—"


def status_from_value(value, threshold=0):
    try:
        value = float(value)
        threshold = float(threshold)
    except Exception:
        return "neutral"

    if value > threshold:
        return "bull"
    if value < -threshold:
        return "bear"
    return "neutral"


def dot_html(status):
    if status == "bull":
        return '<span class="dot dot-green"></span>'
    if status == "bear":
        return '<span class="dot dot-red"></span>'
    return '<span class="dot dot-purple"></span>'


def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

# ============================================================
# TRADIER
# ============================================================

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

# ============================================================
# FLOW / GAMMA ENGINE
# ============================================================

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

    calls = df[(df["type"] == "call") & (df["strike"] >= spot)].copy()
    puts = df[(df["type"] == "put") & (df["strike"] <= spot)].copy()

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


def load_expiration_flow(symbol, width=None, exp_count=None):
    width = width if width is not None else CHAIN_WIDTH_DEFAULTS.get(symbol.upper(), 100)
    exp_count = exp_count if exp_count is not None else expiration_count

    spot = get_price(symbol)
    expirations = get_expirations(symbol)

    today_exp = expirations[0]
    selected_expirations = expirations[:exp_count]

    chains = []

    zero_dte_chain = get_option_chain(symbol, today_exp)

    if zero_dte_chain is not None and not zero_dte_chain.empty:
        zero_dte_chain = filter_near_spot(zero_dte_chain, spot, width)

    for exp in selected_expirations:
        temp = get_option_chain(symbol, exp)

        if temp is not None and not temp.empty:
            temp["expiration"] = exp
            chains.append(temp)

    if chains:
        all_chain = pd.concat(chains, ignore_index=True)
        all_chain = filter_near_spot(all_chain, spot, width)
    else:
        all_chain = pd.DataFrame()

    zero_flow = calculate_net_flow(zero_dte_chain)
    all_flow = calculate_net_flow(all_chain)
    gamma_levels = get_gamma_levels(all_chain, spot)

    return {
        "symbol": symbol,
        "spot": spot,
        "today_exp": today_exp,
        "expirations_used": selected_expirations,
        "zero_dte": zero_flow,
        "all_exp": all_flow,
        "gamma_levels": gamma_levels,
    }

# ============================================================
# SESSION HISTORY
# ============================================================

SESSION_DIR = Path(__file__).parent / "expiration_flow_history"
SESSION_DIR.mkdir(exist_ok=True)


def session_file(symbol):
    return SESSION_DIR / f"expiration_flow_{symbol.upper()}.csv"


def reset_symbol_history(symbol):
    file_path = session_file(symbol)

    if file_path.exists():
        file_path.unlink()


def append_snapshot(flow_data):
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

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
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
        .resample(f"{bucket_minutes}min")
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
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").ffill().fillna(0)

    df["zero_dte_flow"] = df["zero_dte_net_premium"].diff().fillna(0).cumsum()
    df["all_exp_flow"] = df["all_exp_net_premium"].diff().fillna(0).cumsum()
    df["zero_flow_change"] = df["zero_dte_flow"].diff().fillna(0)
    df["all_flow_change"] = df["all_exp_flow"].diff().fillna(0)
    df["time"] = pd.to_datetime(df["datetime"]).dt.strftime("%H:%M:%S")

    return df

# ============================================================
# CHART
# ============================================================

def flow_comparison_chart(history_df, symbol, flow_data):
    df = build_chart_df(history_df)

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"No flow history yet for {symbol}",
            height=720,
            paper_bgcolor="#202326",
            plot_bgcolor="#2b2f33",
            font=dict(color="white"),
        )
        return fig

    df["time"] = df["time"].astype(str)

    fig = go.Figure()

    # Price trace on right axis.
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

    # Flow traces on left axis.
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

    if call_gamma_level:
        fig.add_hline(
            y=call_gamma_level,
            line=dict(color="#22c55e", width=3, dash="dash"),
            yref="y2",
            annotation_text=f"Call Gamma {fmt(call_gamma_level)}",
            annotation_position="top left",
            annotation_font=dict(color="#22c55e", size=13, family="Arial Black"),
            annotation_bgcolor="rgba(0,0,0,0.70)",
        )

    if put_gamma_level:
        fig.add_hline(
            y=put_gamma_level,
            line=dict(color="#ef4444", width=3, dash="dash"),
            yref="y2",
            annotation_text=f"Put Gamma {fmt(put_gamma_level)}",
            annotation_position="bottom left",
            annotation_font=dict(color="#ef4444", size=13, family="Arial Black"),
            annotation_bgcolor="rgba(0,0,0,0.70)",
        )

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
                marker=dict(size=18, color="#22c55e", symbol="circle", line=dict(color="white", width=2)),
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
                marker=dict(size=18, color="#ef4444", symbol="circle", line=dict(color="white", width=2)),
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
                marker=dict(size=15, color="#facc15", symbol="diamond", line=dict(color="white", width=2)),
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
                marker=dict(size=15, color="#f97316", symbol="diamond", line=dict(color="white", width=2)),
                text=["FLOW"] * len(all_bear),
                textposition="bottom center",
                textfont=dict(color="white", size=10, family="Arial Black"),
                yaxis="y",
            )
        )

    fig.add_hline(y=0, line=dict(color="white", width=2, dash="solid"), yref="y")

    latest_all = df["all_exp_flow"].iloc[-1]
    latest_zero = df["zero_dte_flow"].iloc[-1]
    latest_spot = df["spot"].iloc[-1]
    latest_time = str(df["time"].iloc[-1])

    if show_right_labels:
        fig.add_annotation(
            x=latest_time,
            y=latest_all,
            text=f"<b>{money_fmt(latest_all)}</b>",
            showarrow=False,
            xanchor="left",
            xshift=10,
            font=dict(color="#ffe100", size=14, family="Arial Black"),
            bgcolor="rgba(0,0,0,0.70)",
            bordercolor="#ffe100",
            borderwidth=1,
            yref="y",
        )

        fig.add_annotation(
            x=latest_time,
            y=latest_zero,
            text=f"<b>{money_fmt(latest_zero)}</b>",
            showarrow=False,
            xanchor="left",
            xshift=10,
            font=dict(color="#00ff38", size=14, family="Arial Black"),
            bgcolor="rgba(0,0,0,0.70)",
            bordercolor="#00ff38",
            borderwidth=1,
            yref="y",
        )

        fig.add_annotation(
            x=latest_time,
            y=latest_spot,
            text=f"<b>{fmt(latest_spot)}</b>",
            showarrow=False,
            xanchor="left",
            xshift=10,
            font=dict(color="#ffffff", size=13, family="Arial Black"),
            bgcolor="rgba(0,0,0,0.70)",
            bordercolor="#ffffff",
            borderwidth=1,
            yref="y2",
        )

    # Separate flow and price scaling.
    flow_min = min(df["all_exp_flow"].min(), df["zero_dte_flow"].min(), 0)
    flow_max = max(df["all_exp_flow"].max(), df["zero_dte_flow"].max(), 0)

    flow_span = flow_max - flow_min
    if flow_span <= 0:
        flow_span = max(abs(flow_max), abs(flow_min), 1)

    flow_pad = flow_span * 0.18
    flow_range = [flow_min - flow_pad, flow_max + flow_pad]

    price_min = df["spot"].min()
    price_max = df["spot"].max()

    for gamma_key in ["top_call_gamma", "top_put_gamma"]:
        try:
            gamma_value = gamma_levels.get(gamma_key)
            if gamma_value:
                gamma_value = float(gamma_value)
                price_min = min(price_min, gamma_value)
                price_max = max(price_max, gamma_value)
        except Exception:
            pass

    price_span = price_max - price_min

    if price_span <= 0:
        if symbol.upper() == "SPX":
            price_span = 10
        elif symbol.upper() == "QQQ":
            price_span = 1
        else:
            price_span = 0.75

    price_pad = price_span * 0.35
    price_range = [price_min - price_pad, price_max + price_pad]

    if symbol.upper() == "SPX":
        price_dtick = 5
    elif symbol.upper() in ["SPY", "QQQ"]:
        price_dtick = 0.5
    else:
        price_dtick = 1

    flow_update_text = (
        f"0DTE Flow: {money_fmt(latest_zero)} | "
        f"All Exp Flow: {money_fmt(latest_all)}"
    )

    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.01,
        y=1.06,
        text=f"<b>{flow_update_text}</b>",
        showarrow=False,
        align="left",
        font=dict(color="#facc15", size=13, family="Arial Black"),
        bgcolor="rgba(0,0,0,0.55)",
        bordercolor="rgba(250,204,21,0.55)",
        borderwidth=1,
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{symbol} Flow Trend | {bucket_minutes}-Min Bars</b><br>"
                f"<span style='font-size:14px;'>"
                f"0DTE Exp: {flow_data['today_exp']} | "
                f"All Exp Used: {len(flow_data['expirations_used'])} | "
                f"Spot: {fmt(flow_data['spot'])}"
                f"</span>"
            ),
            x=0.01,
            xanchor="left",
            font=dict(size=20, color="white"),
        ),
        height=690,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#2b2f33",
        font=dict(color="white", size=13),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.16)",
            tickfont=dict(color="white", size=12, family="Arial Black"),
            nticks=18,
            type="category",
        ),
        yaxis=dict(
            title=dict(text="Flow Premium", font=dict(color="#facc15", size=14)),
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
            title=dict(text=f"{symbol} Price", font=dict(color="#ffffff", size=14)),
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
            y=-0.13,
            bgcolor="rgba(0,0,0,0.25)",
            font=dict(color="white", size=11, family="Arial Black"),
        ),
        margin=dict(l=75, r=105, t=90, b=80),
        hovermode="x unified",
    )

    return fig

# ============================================================
# MATRIX
# ============================================================

def matrix_statuses(sym, data, history_df):
    chart_df = build_chart_df(history_df)

    odte_net = safe_float(data["zero_dte"]["net_premium"])
    all_net = safe_float(data["all_exp"]["net_premium"])
    spot = safe_float(data["spot"])

    flow_threshold = FLOW_DOT_DEFAULTS.get(sym.upper(), 25_000_000)
    div_threshold = DIVERGENCE_DEFAULTS.get(sym.upper(), 10_000_000)
    pulse_threshold_local = PULSE_DEFAULTS.get(sym.upper(), 25_000_000)

    flow_status = status_from_value(odte_net, flow_threshold)

    divergence_value = odte_net - all_net
    div_status = status_from_value(divergence_value, div_threshold)

    gamma_levels = data.get("gamma_levels", {}) or {}
    call_gamma = gamma_levels.get("top_call_gamma")
    put_gamma = gamma_levels.get("top_put_gamma")

    gamma_status = "neutral"
    try:
        call_gamma = float(call_gamma) if call_gamma else None
        put_gamma = float(put_gamma) if put_gamma else None

        if call_gamma and spot > call_gamma:
            gamma_status = "bull"
        elif put_gamma and spot < put_gamma:
            gamma_status = "bear"
        elif call_gamma and put_gamma:
            mid = (call_gamma + put_gamma) / 2
            gamma_status = "bull" if spot >= mid else "bear"
    except Exception:
        gamma_status = "neutral"

    pulse_status = "neutral"
    if chart_df is not None and not chart_df.empty and len(chart_df) >= 2:
        pulse_value = safe_float(chart_df["zero_flow_change"].iloc[-1])
        pulse_status = status_from_value(pulse_value, pulse_threshold_local)

    return {
        "Flow": flow_status,
        "Div": div_status,
        "Gamma": gamma_status,
        "Pulse": pulse_status,
    }


def build_matrix_html(matrix_data):
    rows_html = []

    for sym in SYMBOLS:
        data = matrix_data.get(sym, {})
        statuses = data.get("statuses", {})

        rows_html.append(
            f"""
            <tr>
                <td><span class="symbol-cell">{SYMBOL_ICONS.get(sym, '')} &nbsp; {sym}</span></td>
                <td>{dot_html(statuses.get("Flow", "neutral"))}</td>
                <td>{dot_html(statuses.get("Div", "neutral"))}</td>
                <td>{dot_html(statuses.get("Gamma", "neutral"))}</td>
                <td>{dot_html(statuses.get("Pulse", "neutral"))}</td>
            </tr>
            """
        )

    return f"""
    <div class="matrix-card">
        <div class="matrix-title">🧠 SG² FLOW DASHBOARD</div>
        <div class="sg2-dot-matrix">
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Flow</th>
                        <th>Div</th>
                        <th>Gamma</th>
                        <th>Pulse</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
    </div>
    """

# ============================================================
# TOP SYMBOL BUTTONS
# ============================================================

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

# ============================================================
# RESET HISTORY
# ============================================================

if reset_history:
    reset_symbol_history(symbol)
    st.success(f"{symbol} flow chart history reset.")

# ============================================================
# LOAD DATA
# ============================================================

try:
    flow_data = load_expiration_flow(symbol, width=chain_width, exp_count=expiration_count)
    history_df = append_snapshot(flow_data)
except Exception as e:
    st.error(f"Failed to load expiration flow for {symbol}")
    st.exception(e)
    st.stop()

gamma_levels = flow_data.get("gamma_levels", {}) or {}
latest_zero = flow_data["zero_dte"]["net_premium"]
latest_all = flow_data["all_exp"]["net_premium"]

# ============================================================
# TOP SUMMARY CARD
# ============================================================

today_txt = datetime.now(CENTRAL_TZ).strftime("%A, %B %d, %Y")

top_html = f"""
<div class="top-card">
    <div class="top-title">{symbol} {today_txt}</div>
    <div class="top-line">
        Spot: <span class="green-text">{fmt(flow_data["spot"])}</span>
        &nbsp;&nbsp; | &nbsp;&nbsp;
        0DTE Exp: <span class="yellow-text">{flow_data["today_exp"]}</span>
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="yellow-text">0DTE Flow:</span> {money_fmt(latest_zero)}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="cyan-text">Signed Delta:</span> {money_fmt(latest_zero)}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        All Exp Used: <span class="green-text">{len(flow_data["expirations_used"])}</span>
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="yellow-text">All Exp Flow:</span> {money_fmt(latest_all)}
    </div>
</div>
"""

st.markdown(top_html, unsafe_allow_html=True)

# ============================================================
# LOAD MATRIX DATA
# ============================================================

matrix_data = {}

for sym in SYMBOLS:
    try:
        if sym == symbol:
            sym_flow_data = flow_data
            sym_history_df = history_df
        else:
            sym_flow_data = load_expiration_flow(
                sym,
                width=CHAIN_WIDTH_DEFAULTS.get(sym.upper(), 100),
                exp_count=expiration_count,
            )
            sym_history_df = append_snapshot(sym_flow_data)

        matrix_data[sym] = {
            "flow_data": sym_flow_data,
            "history_df": sym_history_df,
            "statuses": matrix_statuses(sym, sym_flow_data, sym_history_df),
        }

    except Exception as e:
        matrix_data[sym] = {
            "flow_data": {},
            "history_df": pd.DataFrame(),
            "statuses": {
                "Flow": "neutral",
                "Div": "neutral",
                "Gamma": "neutral",
                "Pulse": "neutral",
            },
        }
        st.warning(f"{sym} matrix load failed: {e}")

# ============================================================
# MAIN LAYOUT
# ============================================================

left_chart, right_matrix = st.columns([2.75, 1.05])

with left_chart:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(
        flow_comparison_chart(history_df, symbol, flow_data),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right_matrix:

    st.markdown(
        build_matrix_html(matrix_data),
        unsafe_allow_html=True,
)


st.caption("All values are real-time estimates. Not financial advice. Data may be delayed.")
