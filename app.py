import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

from flow_engine import get_flow_snapshot

CENTRAL_TZ = ZoneInfo("America/Chicago")

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

CHAIN_WIDTH_DEFAULTS = {
    "SPY": 5,
    "SPX": 25,
    "QQQ": 5,
}

STRIKE_COUNT_DEFAULTS = {
    "SPY": 5,
    "QQQ": 5,
    "SPX": 25,
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
    margin: 12px 0 8px 0;
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
.header-card {
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

hr { border-color: #263241; }
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

    flow_display_mode = st.radio(
        "Main Flow Display",
        options=["Net Premium", "Delta Notional"],
        index=0,
        horizontal=True,
    )

    show_flow_dots = st.checkbox("Show FLOW Dots", value=True)
    show_signed_delta_line = st.checkbox("Show Signed Delta Line", value=False)

    show_delta_notional_lines = st.checkbox(
        "Overlay Delta Notional Lines",
        value=False,
        disabled=(flow_display_mode == "Delta Notional"),
        help="Only needed when the main chart is set to Net Premium. Delta Notional mode already uses these lines as the main chart.",
    )

    show_right_labels = st.checkbox("Show Right Edge Labels", value=True)

    default_flow_dot_threshold = FLOW_DOT_THRESHOLDS.get(symbol, 25_000_000)

    flow_dot_threshold = st.number_input(
        "FLOW Dot Threshold",
        min_value=0,
        value=default_flow_dot_threshold,
        step=5_000_000,
        key=f"flow_dot_threshold_{symbol}",
    )

    strike_count_each_side = STRIKE_COUNT_DEFAULTS.get(symbol, 5)
    chain_width = CHAIN_WIDTH_DEFAULTS.get(symbol, 100)

    st.caption(f"Default FLOW threshold for {symbol}: {default_flow_dot_threshold:,}")
    st.caption(
        f"Strike filter: {strike_count_each_side} strikes above and "
        f"{strike_count_each_side} strikes below spot for {symbol}."
    )

    reset_exp_history = st.button("Reset Flow Chart History")

    st.markdown("---")
    st.caption(f"Chart model: 0DTE and All Expiration {flow_display_mode.lower()} flow changes.")
    st.caption("History files are capped at 1,500 rows per symbol.")
    st.caption("Delta Notional = Delta × Spot × Contracts × 100.")

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

def filter_near_spot(df, spot, strikes_each_side):
    """
    Keep a fixed number of listed strikes above and below spot.
    SPY/QQQ: 5 each side. SPX: 25 each side.
    """
    if df is None or df.empty or "strike" not in df.columns:
        return pd.DataFrame()

    temp = df.copy()
    temp["strike"] = pd.to_numeric(temp["strike"], errors="coerce")
    temp = temp.dropna(subset=["strike"])

    if temp.empty:
        return temp

    spot = float(spot)
    strikes_each_side = int(strikes_each_side)
    strikes = sorted(temp["strike"].dropna().unique())

    if not strikes:
        return temp.iloc[0:0].copy()

    atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    start_idx = max(0, atm_idx - strikes_each_side)
    end_idx = min(len(strikes), atm_idx + strikes_each_side + 1)
    selected_strikes = set(strikes[start_idx:end_idx])

    return temp[temp["strike"].isin(selected_strikes)].copy()

def calculate_net_flow(chain_df, spot=None):
    if chain_df is None or chain_df.empty:
        return {
            "call_premium": 0,
            "put_premium": 0,
            "net_premium": 0,
            "call_delta_notional": 0,
            "put_delta_notional": 0,
            "net_delta_notional": 0,
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

    # Delta Notional estimates directional exposure / hedge pressure.
    # Calls usually carry positive delta; puts usually carry negative delta.
    try:
        spot_value = float(spot) if spot is not None else 0.0
    except Exception:
        spot_value = 0.0

    if "delta" not in df.columns:
        df["delta"] = 0

    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["delta_notional"] = df["delta"] * spot_value * df["activity"] * 100

    calls = df[df["type"].str.contains("call", na=False)]
    puts = df[df["type"].str.contains("put", na=False)]

    call_premium = calls["premium"].sum()
    put_premium = puts["premium"].sum()
    net_premium = call_premium - put_premium

    call_delta_notional = calls["delta_notional"].sum()
    put_delta_notional = puts["delta_notional"].sum()
    net_delta_notional = df["delta_notional"].sum()

    return {
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": net_premium,
        "call_delta_notional": call_delta_notional,
        "put_delta_notional": put_delta_notional,
        "net_delta_notional": net_delta_notional,
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

def load_expiration_flow(symbol):
    spot = get_price(symbol)
    expirations = get_expirations(symbol)

    today_exp = expirations[0]
    selected_expirations = expirations[:all_exp_count]
    strikes_each_side = STRIKE_COUNT_DEFAULTS.get(symbol.upper(), 5)

    chains = []

    zero_dte_chain = get_option_chain(symbol, today_exp)

    if zero_dte_chain is not None and not zero_dte_chain.empty:
        zero_dte_chain = filter_near_spot(
            zero_dte_chain,
            spot,
            strikes_each_side,
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
            strikes_each_side,
        )
    else:
        all_chain = pd.DataFrame()

    zero_flow = calculate_net_flow(zero_dte_chain, spot)
    all_flow = calculate_net_flow(all_chain, spot)
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

# =========================================================
# SESSION FILE HISTORY FOR CHART
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
        "zero_dte_delta_notional": flow_data["zero_dte"].get("net_delta_notional", 0),
        "all_exp_call_premium": flow_data["all_exp"]["call_premium"],
        "all_exp_put_premium": flow_data["all_exp"]["put_premium"],
        "all_exp_net_premium": flow_data["all_exp"]["net_premium"],
        "all_exp_delta_notional": flow_data["all_exp"].get("net_delta_notional", 0),
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

    # Prevent massive CSV files and hard drive fill-up.
    df = df.tail(1500).copy()
    df.to_csv(file_path, index=False)

    return df

def normalize_history(df):
    df = df.copy()
    df["datetime"] = pd.to_datetime(df.get("datetime", pd.NaT), errors="coerce")
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

    for missing_col in ["zero_dte_delta_notional", "all_exp_delta_notional"]:
        if missing_col not in df.columns:
            df[missing_col] = 0

    df = (
        df.set_index("datetime")
        .sort_index()
        .resample(f"{chart_bucket}min")
        .agg(
            {
                "spot": "last",
                "zero_dte_net_premium": "last",
                "all_exp_net_premium": "last",
                "zero_dte_delta_notional": "last",
                "all_exp_delta_notional": "last",
            }
        )
        .dropna(how="all")
        .reset_index()
    )

    for col in [
        "spot",
        "zero_dte_net_premium",
        "all_exp_net_premium",
        "zero_dte_delta_notional",
        "all_exp_delta_notional",
    ]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").ffill().fillna(0)

    df["zero_dte_flow"] = df["zero_dte_net_premium"].diff().fillna(0).cumsum()
    df["all_exp_flow"] = df["all_exp_net_premium"].diff().fillna(0).cumsum()
    df["zero_dte_delta_notional_flow"] = df["zero_dte_delta_notional"].diff().fillna(0).cumsum()
    df["all_exp_delta_notional_flow"] = df["all_exp_delta_notional"].diff().fillna(0).cumsum()
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

def add_event_trace(fig, events_df, x_col, y_col, name, marker_color, marker_symbol, text_position, marker_size):
    """Add a FLOW event trace and keep the legend item visible even with no events."""
    if events_df is None or events_df.empty:
        x_values = [None]
        y_values = [None]
        text_values = [""]
    else:
        x_values = events_df[x_col]
        y_values = events_df[y_col]
        text_values = ["FLOW"] * len(events_df)

    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="markers+text",
            name=name,
            showlegend=True,
            visible=True,
            marker=dict(
                size=marker_size,
                color=marker_color,
                symbol=marker_symbol,
                line=dict(color="white", width=2),
            ),
            text=text_values,
            textposition=text_position,
            textfont=dict(color="white", size=10, family="Arial Black"),
            hoverinfo="skip" if events_df is None or events_df.empty else "x+y+name",
            yaxis="y",
        )
    )

# =========================================================
# CHART BUILDER
# =========================================================
def sg2_flow_chart(history_df, symbol, flow_data):
    df = build_chart_df(history_df)

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"No flow history yet for {symbol}",
            height=680,
            paper_bgcolor="#111923",
            plot_bgcolor="#252a2f",
            font=dict(color="white"),
        )
        return fig

    df["time"] = df["time"].astype(str)
    fig = go.Figure()

    if flow_display_mode == "Delta Notional":
        all_flow_col = "all_exp_delta_notional_flow"
        zero_flow_col = "zero_dte_delta_notional_flow"
        flow_axis_title = "Delta Notional Flow"
        all_line_name = "All Exp Δ Notional"
        zero_line_name = "0DTE Δ Notional"
        chart_mode_title = "Delta Notional"
    else:
        all_flow_col = "all_exp_flow"
        zero_flow_col = "zero_dte_flow"
        flow_axis_title = "Premium Flow"
        all_line_name = "All Exp Premium"
        zero_line_name = "0DTE Premium"
        chart_mode_title = "Net Premium"

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["spot"],
            mode="lines",
            name=f"{symbol} Price",
            line=dict(color="#ffffff", width=4),
            yaxis="y2",
            showlegend=True,
            visible=True,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df[all_flow_col],
            mode="lines",
            name=all_line_name,
            line=dict(color="#ffe100", width=5),
            yaxis="y",
            showlegend=True,
            visible=True,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df[zero_flow_col],
            mode="lines",
            name=zero_line_name,
            line=dict(color="#00ff38", width=5),
            yaxis="y",
            showlegend=True,
            visible=True,
        )
    )

    if show_delta_notional_lines and flow_display_mode == "Net Premium":
        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["all_exp_delta_notional_flow"],
                mode="lines",
                name="All Exp Δ Notional",
                line=dict(color="#a855f7", width=3, dash="dot"),
                yaxis="y",
                showlegend=True,
                visible=True,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["time"],
                y=df["zero_dte_delta_notional_flow"],
                mode="lines",
                name="0DTE Δ Notional",
                line=dict(color="#00e5ff", width=3, dash="dot"),
                yaxis="y",
                showlegend=True,
                visible=True,
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

    if show_flow_dots:
        threshold = float(flow_dot_threshold)
        zero_prev = df[zero_flow_col].shift(1).fillna(0)
        all_prev = df[all_flow_col].shift(1).fillna(0)

        df["zero_bull_flow_dot"] = (df[zero_flow_col] > threshold) & (zero_prev <= threshold)
        df["zero_bear_flow_dot"] = (df[zero_flow_col] < -threshold) & (zero_prev >= -threshold)
        df["all_bull_flow_dot"] = (df[all_flow_col] > threshold) & (all_prev <= threshold)
        df["all_bear_flow_dot"] = (df[all_flow_col] < -threshold) & (all_prev >= -threshold)

        zero_bull = df[df["zero_bull_flow_dot"]]
        zero_bear = df[df["zero_bear_flow_dot"]]
        all_bull = df[df["all_bull_flow_dot"]]
        all_bear = df[df["all_bear_flow_dot"]]

        add_event_trace(
            fig,
            zero_bull,
            "time",
            zero_flow_col,
            "0DTE Bull FLOW",
            "#22c55e",
            "circle",
            "top center",
            18,
        )

        add_event_trace(
            fig,
            zero_bear,
            "time",
            zero_flow_col,
            "0DTE Bear FLOW",
            "#ef4444",
            "circle",
            "bottom center",
            18,
        )

        add_event_trace(
            fig,
            all_bull,
            "time",
            all_flow_col,
            "All Exp Bull FLOW",
            "#facc15",
            "diamond",
            "top center",
            16,
        )

        add_event_trace(
            fig,
            all_bear,
            "time",
            all_flow_col,
            "All Exp Bear FLOW",
            "#f97316",
            "diamond",
            "bottom center",
            16,
        )

    fig.add_hline(
        y=0,
        line=dict(color="white", width=2, dash="solid"),
        yref="y",
    )

    latest_all = df[all_flow_col].iloc[-1]
    latest_zero = df[zero_flow_col].iloc[-1]
    latest_spot = df["spot"].iloc[-1]
    latest_zero_delta_notional = df["zero_dte_delta_notional_flow"].iloc[-1]
    latest_all_delta_notional = df["all_exp_delta_notional_flow"].iloc[-1]
    latest_time = str(df["time"].iloc[-1])

    if show_right_labels:
        add_right_edge_label(fig, latest_time, latest_all, fmt_money(latest_all), "#ffe100", yref="y")
        add_right_edge_label(fig, latest_time, latest_zero, fmt_money(latest_zero), "#00ff38", yref="y")
        add_right_edge_label(fig, latest_time, latest_spot, fmt_price(latest_spot), "#ffffff", yref="y2")

        if show_delta_notional_lines and flow_display_mode == "Net Premium":
            add_right_edge_label(fig, latest_time, latest_all_delta_notional, fmt_money(latest_all_delta_notional), "#a855f7", yref="y")
            add_right_edge_label(fig, latest_time, latest_zero_delta_notional, fmt_money(latest_zero_delta_notional), "#00e5ff", yref="y")

    flow_values_for_range = [
        df[all_flow_col].min(),
        df[zero_flow_col].min(),
        0,
    ]
    flow_values_for_range_max = [
        df[all_flow_col].max(),
        df[zero_flow_col].max(),
        0,
    ]

    if show_delta_notional_lines and flow_display_mode == "Net Premium":
        flow_values_for_range.extend([
            df["all_exp_delta_notional_flow"].min(),
            df["zero_dte_delta_notional_flow"].min(),
        ])
        flow_values_for_range_max.extend([
            df["all_exp_delta_notional_flow"].max(),
            df["zero_dte_delta_notional_flow"].max(),
        ])

    flow_min = min(flow_values_for_range)
    flow_max = max(flow_values_for_range_max)
    flow_span = flow_max - flow_min

    if flow_span <= 0:
        flow_span = max(abs(flow_max), abs(flow_min), 1)

    flow_pad = flow_span * 0.18
    flow_range = [flow_min - flow_pad, flow_max + flow_pad]

    positive_spots = pd.to_numeric(df.get("spot", pd.Series(dtype=float)), errors="coerce")
    positive_spots = positive_spots[positive_spots > 0]

    if not positive_spots.empty:
        price_min = float(positive_spots.min())
        price_max = float(positive_spots.max())
        spot_reference = float(positive_spots.iloc[-1])
    else:
        spot_reference = float(flow_data.get("spot", 0) or 0)
        price_min = spot_reference
        price_max = spot_reference

    price_span = price_max - price_min
    min_price_span = 12 if symbol.upper() == "SPX" else 2.0

    if price_span < min_price_span:
        center = spot_reference if spot_reference > 0 else (price_min + price_max) / 2
        price_min = center - (min_price_span / 2)
        price_max = center + (min_price_span / 2)
        price_span = min_price_span

    price_pad = price_span * 0.08
    price_range = [price_min - price_pad, price_max + price_pad]

    if symbol.upper() == "SPX":
        if price_span <= 25:
            price_dtick = 5
        elif price_span <= 75:
            price_dtick = 10
        else:
            price_dtick = 25
    else:
        if price_span <= 5:
            price_dtick = 0.5
        elif price_span <= 15:
            price_dtick = 1
        else:
            price_dtick = 2.5

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{symbol} {chart_mode_title} Flow Trend | {chart_bucket}-Min Bars</b><br>"
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
        height=700,
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
            title=dict(text=flow_axis_title, font=dict(color="#facc15", size=14)),
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
            y=-0.20,
            bgcolor="rgba(0,0,0,0.25)",
            font=dict(color="white", size=12, family="Arial Black"),
        ),
        margin=dict(l=75, r=105, t=80, b=120),
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
# TRADESTATION EXPORT
# =========================================================
TS_EXPORT_DIR = Path(r"C:\SG2\tradestation_flow")
TS_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def export_spx_to_tradestation(flow_data, history_df):

    if flow_data.get("symbol", "").upper() != "SPX":
        return

    chart_df = build_chart_df(history_df)

    zero_flow = 0
    all_flow = 0

    if chart_df is not None and not chart_df.empty:
        zero_flow = float(chart_df["zero_dte_flow"].iloc[-1])
        all_flow = float(chart_df["all_exp_flow"].iloc[-1])

    gamma_levels = flow_data.get("gamma_levels", {})

    call_gamma = gamma_levels.get("top_call_gamma") or 0
    put_gamma = gamma_levels.get("top_put_gamma") or 0
    spot = flow_data.get("spot", 0)

    bull_flow = 1 if zero_flow > 100000 else 0
    bear_flow = 1 if zero_flow < -100000 else 0

    export_file = TS_EXPORT_DIR / "SG2_SPX_FLOW.txt"

    export_file.write_text("\n".join(lines))

    print("SG2 EXPORT WRITTEN")
    print(export_file)
    print(lines)([
            f"SPOT={spot}",
            f"ZERO_DTE_FLOW={zero_flow}",
            f"ALL_EXP_FLOW={all_flow}",
            f"CALL_GAMMA={call_gamma}",
            f"PUT_GAMMA={put_gamma}",
            f"BULL_FLOW={bull_flow}",
            f"BEAR_FLOW={bear_flow}",
            f"UPDATED={datetime.now(CENTRAL_TZ).strftime('%H:%M:%S')}"
        ])
    )

# =========================================================
# LOAD EXPIRATION FLOW FOR MAIN CHART
# =========================================================
try:
    exp_flow_data = load_expiration_flow(symbol)
    exp_history_df = append_exp_snapshot(exp_flow_data)

    export_spx_to_tradestation(exp_flow_data, exp_history_df)

except Exception as e:
    st.error(f"Could not load expiration flow chart data for {symbol}: {e}")
    st.stop()

# =========================================================
# MAIN FLOW CHART - FULL WIDTH DIRECTLY UNDER ACTIVE BAR
# =========================================================
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
# LOAD SG2 SNAPSHOT FOR METRICS BELOW CHART
# =========================================================
try:
    snapshot = get_flow_snapshot(
        symbol=symbol,
        all_exp_count=all_exp_count,
        chart_bucket=chart_bucket,
        lookback_hours=lookback_hours,
        strike_width=chain_width,
    )
except Exception:
    snapshot = {}

spot = safe_get(snapshot, "spot", exp_flow_data.get("spot", 0))
odte_exp = safe_get(snapshot, "odte_exp", exp_flow_data.get("today_exp", ""))

odte_premium_net = exp_flow_data["zero_dte"]["net_premium"]
all_exp_premium_net = exp_flow_data["all_exp"]["net_premium"]
odte_delta_notional_net = exp_flow_data["zero_dte"].get("net_delta_notional", 0)
all_exp_delta_notional_net = exp_flow_data["all_exp"].get("net_delta_notional", 0)

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
# HEADER / SUMMARY BELOW CHART
# =========================================================
today_txt = datetime.now(CENTRAL_TZ).strftime("%A, %B %d, %Y")

header_html = f"""
<div class="header-card">
    <div style="font-size:25px;font-weight:900;color:white;">
        {symbol} {today_txt}
    </div>
    <div style="font-size:15px;font-weight:800;color:white;margin-top:8px;">
        Spot: <span class="green-text">{float(spot):.2f}</span>
        &nbsp;&nbsp; | &nbsp;&nbsp;
        Mode: <span class="cyan-text">{flow_display_mode}</span>
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
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="cyan-text">0DTE Δ Notional:</span> {fmt_money(odte_delta_notional_net)}
        &nbsp;&nbsp; | &nbsp;&nbsp;
        <span class="cyan-text">All Exp Δ Notional:</span> {fmt_money(all_exp_delta_notional_net)}
    </div>
</div>
"""

st.markdown(header_html, unsafe_allow_html=True)

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
# METRICS BELOW CHART
# =========================================================
st.markdown('<div class="metric-card">', unsafe_allow_html=True)

r1 = st.columns(7)
r1[0].markdown(metric_html("Spot", f"{float(spot):.2f}"), unsafe_allow_html=True)
r1[1].markdown(metric_html("0DTE Premium Net", fmt_money(odte_premium_net), color_class(odte_premium_net)), unsafe_allow_html=True)
r1[2].markdown(metric_html("All Exp Premium Net", fmt_money(all_exp_premium_net), color_class(all_exp_premium_net)), unsafe_allow_html=True)
r1[3].markdown(metric_html("0DTE Δ Notional", fmt_money(odte_delta_notional_net), color_class(odte_delta_notional_net)), unsafe_allow_html=True)
r1[4].markdown(metric_html("All Exp Δ Notional", fmt_money(all_exp_delta_notional_net), color_class(all_exp_delta_notional_net)), unsafe_allow_html=True)
r1[5].markdown(metric_html("Call Gamma", fmt_price(call_gamma), "green-text"), unsafe_allow_html=True)
r1[6].markdown(metric_html("Put Gamma", fmt_price(put_gamma), "red-text"), unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

r2 = st.columns(10)
r2[0].markdown(metric_html("0DTE Signed Delta", fmt_money(odte_signed_delta), color_class(odte_signed_delta)), unsafe_allow_html=True)
r2[1].markdown(metric_html("0DTE Delta Bias", odte_delta_bias, "red-text" if "BEAR" in str(odte_delta_bias) else "green-text"), unsafe_allow_html=True)
r2[2].markdown(metric_html("All Exp Delta Bias", all_exp_delta_bias, "red-text" if "BEAR" in str(all_exp_delta_bias) else "green-text"), unsafe_allow_html=True)
r2[3].markdown(metric_html("Gamma Regime", gamma_regime, "green-text" if "ABOVE" in str(gamma_regime) else "red-text"), unsafe_allow_html=True)
r2[4].markdown(metric_html("0DTE Rows", odte_rows), unsafe_allow_html=True)
r2[5].markdown(metric_html("All Exp Rows", all_exp_rows), unsafe_allow_html=True)
r2[6].markdown(metric_html("Call Vol", fmt_num(call_volume), "green-text"), unsafe_allow_html=True)
r2[7].markdown(metric_html("Put Vol", fmt_num(put_volume), "red-text"), unsafe_allow_html=True)
r2[8].markdown(metric_html("Total Vol", fmt_num(total_volume)), unsafe_allow_html=True)
r2[9].markdown(metric_html("P/C Ratio", f"{pc_ratio:.2f}", "yellow-text"), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.caption("All values are real-time estimates. Not financial advice. Data may be delayed.")


