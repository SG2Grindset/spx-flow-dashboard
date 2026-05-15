# ============================================================
# expiration_flow_dashboard.py
# SPY / SPX / QQQ
# All Expirations Delta Notional Flow vs 0DTE Delta Notional Flow
# Public app version - Discord sending removed
# ============================================================

import os
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh


# ============================================================
# ENV
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
# PAGE
# ============================================================

st.set_page_config(
    page_title="Expiration Flow Dashboard",
    page_icon="🟢",
    layout="wide",
)

st.markdown("""
<style>
.stApp {
    background-color: #202326 !important;
    color: white !important;
}

html, body, [class*="css"] {
    color: white !important;
    font-family: "Segoe UI", sans-serif !important;
}

[data-testid="stHeader"] {
    background-color: #202326 !important;
}

section[data-testid="stSidebar"] {
    background-color: #16191c !important;
}

.block-container {
    padding-top: 0.5rem;
    max-width: 100%;
    background-color: #202326 !important;
}

[data-testid="metric-container"] {
    background: linear-gradient(145deg,#1b1f24,#111827) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    padding: 14px 16px !important;
    border-radius: 14px !important;
    box-shadow: 0 0 14px rgba(0,0,0,0.45) !important;
}

[data-testid="stMetricLabel"] p {
    color: #facc15 !important;
    font-weight: 900 !important;
    font-size: 16px !important;
    letter-spacing: 0.5px;
}

[data-testid="stMetricValue"] div {
    color: #ffffff !important;
    font-weight: 900 !important;
    font-size: 30px !important;
    text-shadow: 0 0 10px rgba(255,255,255,0.25);
}
</style>
""", unsafe_allow_html=True)

st.title("🟢 Expiration Flow Dashboard")
st.caption("0DTE Delta Notional Flow vs All Expirations Delta Notional Flow")


# ============================================================
# SIDEBAR
# ============================================================

SYMBOLS = ["SPY", "SPX", "QQQ"]

symbol = st.sidebar.selectbox(
    "Symbol",
    SYMBOLS,
    index=0,
)

auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)

refresh_seconds = st.sidebar.selectbox(
    "Refresh Interval",
    [15, 30, 60, 120],
    index=0,
)

expiration_count = st.sidebar.slider(
    "All Expirations Count",
    min_value=2,
    max_value=10,
    value=5,
    step=1,
)

bucket_minutes = st.sidebar.selectbox(
    "Chart Bucket",
    [1, 3, 5],
    index=0,
)

lookback_hours = st.sidebar.slider(
    "Lookback Hours",
    min_value=1,
    max_value=10,
    value=2,
    step=1,
)

show_flow_dots = st.sidebar.checkbox(
    "Show FLOW Dots",
    value=True,
)

flow_dot_threshold = st.sidebar.number_input(
    "FLOW Dot Threshold",
    min_value=0,
    value=100_000_000,
    step=25_000_000,
    help="Dot fires when delta notional flow crosses above/below this threshold. Use 0 for simple zero-line crosses.",
)

chain_width = st.sidebar.slider(
    "Strike Width Around Spot",
    min_value=25,
    max_value=1000,
    value=500 if symbol == "SPX" else 100,
    step=25,
)



st.sidebar.markdown("---")
st.sidebar.caption(
    "Public app mode: chart controls are session-based. "
    "Changing sliders here will not change another viewer's open session."
)

st.sidebar.caption(
    "Flow model: Delta Notional = Spot × |Delta| × Contracts × 100."
)

if auto_refresh:
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="expiration_flow_refresh",
    )


# ============================================================
# SESSION FILES
# ============================================================

SESSION_DIR = Path(__file__).parent / "expiration_flow_history"
SESSION_DIR.mkdir(exist_ok=True)


def session_file(symbol):
    return SESSION_DIR / f"expiration_flow_{symbol.upper()}.csv"


def reset_symbol_history(symbol):
    file_path = session_file(symbol)

    if file_path.exists():
        file_path.unlink()



# ============================================================
# FORMAT HELPERS
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
        raise Exception(
            f"Tradier error {response.status_code}: {response.text}"
        )

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

    for col in ["strike", "last", "volume", "open_interest", "bid", "ask"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(subset=["strike"])
    df = df[df["type"].isin(["call", "put"])]

    return df


# ============================================================
# FLOW CALCULATION
# ============================================================

def filter_near_spot(df, spot, width):
    return df[
        (df["strike"] >= float(spot) - width)
        & (df["strike"] <= float(spot) + width)
    ].copy()


def calculate_net_flow(chain_df, spot_price):
    """
    Delta notional model:
    Delta Notional = Spot Price * ABS(Delta) * Contracts * 100

    Calls are treated as positive exposure.
    Puts are treated as negative exposure through net calculation:
        Net = Call Delta Notional - Put Delta Notional
    """

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

    # If volume is zero/missing, fall back to open interest.
    df.loc[df["activity"] <= 0, "activity"] = df["open_interest"]

    df["delta"] = pd.to_numeric(
        df.get("delta", 0),
        errors="coerce",
    ).fillna(0)

    df["delta_notional"] = (
        float(spot_price)
        * df["delta"].abs()
        * df["activity"]
        * 100
    )

    calls = df[df["type"].str.contains("call", na=False)]
    puts = df[df["type"].str.contains("put", na=False)]

    call_premium = calls["delta_notional"].sum()
    put_premium = puts["delta_notional"].sum()
    net_premium = call_premium - put_premium

    return {
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": net_premium,
        "rows": len(df),
    }


def get_gamma_levels(chain_df):
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

    df["gamma_exposure"] = df["gamma"] * df["open_interest"] * 100

    calls = df[df["type"] == "call"].copy()
    puts = df[df["type"] == "put"].copy()

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
    selected_expirations = expirations[:expiration_count]

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

    zero_flow = calculate_net_flow(zero_dte_chain, spot)
    all_flow = calculate_net_flow(all_chain, spot)
    gamma_levels = get_gamma_levels(all_chain)

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

def append_snapshot(flow_data):
    file_path = session_file(flow_data["symbol"])

    now = datetime.now()

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
        df[col] = pd.to_numeric(
            df.get(col, 0),
            errors="coerce",
        ).ffill().fillna(0)

    df["zero_dte_flow"] = df["zero_dte_net_premium"].diff().fillna(0).cumsum()
    df["all_exp_flow"] = df["all_exp_net_premium"].diff().fillna(0).cumsum()
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
            height=850,
            paper_bgcolor="#202326",
            plot_bgcolor="#2b2f33",
            font=dict(color="white"),
        )
        return fig

    # Plain string x-axis labels prevent Plotly/Kaleido Timestamp JSON errors.
    df["time"] = df["time"].astype(str)

    fig = go.Figure()

    # ========================================================
    # PRICE TRACE - RIGHT AXIS
    # ========================================================
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

    # ========================================================
    # FLOW TRACES - LEFT AXIS
    # ========================================================
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

    # ========================================================
    # FLOW DOTS
    # ========================================================
    if show_flow_dots:
        threshold = float(flow_dot_threshold)

        # Safety: create FLOW dot columns if missing.
        if "zero_bull_flow_dot" not in df.columns:
            df["zero_bull_flow_dot"] = (
                (df["zero_dte_flow"] > threshold)
                & (df["zero_dte_flow"].shift(1) <= threshold)
            )
        if "zero_bear_flow_dot" not in df.columns:
            df["zero_bear_flow_dot"] = (
                (df["zero_dte_flow"] < -threshold)
                & (df["zero_dte_flow"].shift(1) >= -threshold)
            )
        if "all_bull_flow_dot" not in df.columns:
            df["all_bull_flow_dot"] = (
                (df["all_exp_flow"] > threshold)
                & (df["all_exp_flow"].shift(1) <= threshold)
            )
        if "all_bear_flow_dot" not in df.columns:
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
                marker=dict(size=22, color="#22c55e", symbol="circle", line=dict(color="white", width=2)),
                text=["FLOW"] * len(zero_bull),
                textposition="top center",
                textfont=dict(color="white", size=13, family="Arial Black"),
                yaxis="y",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=zero_bear["time"],
                y=zero_bear["zero_dte_flow"],
                mode="markers+text",
                name="0DTE Bear FLOW",
                marker=dict(size=22, color="#ef4444", symbol="circle", line=dict(color="white", width=2)),
                text=["FLOW"] * len(zero_bear),
                textposition="bottom center",
                textfont=dict(color="white", size=13, family="Arial Black"),
                yaxis="y",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=all_bull["time"],
                y=all_bull["all_exp_flow"],
                mode="markers+text",
                name="All Exp Bull FLOW",
                marker=dict(size=18, color="#facc15", symbol="diamond", line=dict(color="white", width=2)),
                text=["FLOW"] * len(all_bull),
                textposition="top center",
                textfont=dict(color="white", size=12, family="Arial Black"),
                yaxis="y",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=all_bear["time"],
                y=all_bear["all_exp_flow"],
                mode="markers+text",
                name="All Exp Bear FLOW",
                marker=dict(size=18, color="#f97316", symbol="diamond", line=dict(color="white", width=2)),
                text=["FLOW"] * len(all_bear),
                textposition="bottom center",
                textfont=dict(color="white", size=12, family="Arial Black"),
                yaxis="y",
            )
        )

    fig.add_hline(y=0, line=dict(color="white", width=2, dash="solid"), yref="y")

    latest_all = df["all_exp_flow"].iloc[-1]
    latest_zero = df["zero_dte_flow"].iloc[-1]
    latest_spot = df["spot"].iloc[-1]
    latest_time = str(df["time"].iloc[-1])

    fig.add_annotation(
        x=latest_time,
        y=latest_all,
        text=f"<b>{money_fmt(latest_all)}</b>",
        showarrow=False,
        xanchor="left",
        xshift=10,
        font=dict(color="#ffe100", size=16, family="Arial Black"),
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
        font=dict(color="#00ff38", size=16, family="Arial Black"),
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
        font=dict(color="#ffffff", size=15, family="Arial Black"),
        bgcolor="rgba(0,0,0,0.70)",
        bordercolor="#ffffff",
        borderwidth=1,
        yref="y2",
    )

    # ========================================================
    # SEPARATE FLOW AND PRICE SCALING
    # ========================================================
    flow_min = min(df["all_exp_flow"].min(), df["zero_dte_flow"].min(), 0)
    flow_max = max(df["all_exp_flow"].max(), df["zero_dte_flow"].max(), 0)

    flow_span = flow_max - flow_min
    if flow_span <= 0:
        flow_span = max(abs(flow_max), abs(flow_min), 1)

    flow_pad = flow_span * 0.18
    flow_range = [flow_min - flow_pad, flow_max + flow_pad]

    price_min = df["spot"].min()
    price_max = df["spot"].max()

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

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{symbol} {datetime.now().strftime('%A, %B %d, %Y')}</b><br>"
                f"<span style='font-size:18px;'>"
                f"0DTE Exp: {flow_data['today_exp']} | "
                f"All Exp Used: {len(flow_data['expirations_used'])} | "
                f"Spot: {fmt(flow_data['spot'])}"
                f"</span>"
            ),
            x=0.01,
            xanchor="left",
            font=dict(size=24, color="white"),
        ),
        height=900,
        paper_bgcolor="#202326",
        plot_bgcolor="#2b2f33",
        font=dict(color="white", size=15),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.16)",
            tickfont=dict(color="white", size=14, family="Arial Black"),
            nticks=18,
            type="category",
        ),
        yaxis=dict(
            title=dict(text="Delta Notional Flow", font=dict(color="#facc15", size=16)),
            side="left",
            range=flow_range,
            showgrid=True,
            gridcolor="rgba(255,255,255,0.18)",
            zeroline=True,
            zerolinecolor="white",
            tickformat="~s",
            tickfont=dict(color="#facc15", size=15, family="Arial Black"),
        ),
        yaxis2=dict(
            title=dict(text=f"{symbol} Price", font=dict(color="#ffffff", size=16)),
            overlaying="y",
            side="right",
            range=price_range,
            showgrid=False,
            tickfont=dict(color="#ffffff", size=15, family="Arial Black"),
        ),
        legend=dict(
            orientation="h",
            x=0.01,
            y=0.04,
            bgcolor="rgba(0,0,0,0.25)",
            font=dict(color="white", size=14, family="Arial Black"),
        ),
        margin=dict(l=90, r=105, t=95, b=70),
        hovermode="x unified",
    )

    return fig


# ============================================================
# LOAD DATA
# ============================================================

try:
    flow_data = load_expiration_flow(symbol)
    history_df = append_snapshot(flow_data)

except Exception as e:
    st.error(f"Failed to load expiration flow for {symbol}")
    st.exception(e)
    st.stop()


# ============================================================
# DISPLAY METRICS
# ============================================================

gamma_levels = flow_data.get("gamma_levels", {})

m1, m2, m3, m4, m5, m6 = st.columns(6)

m1.metric("Symbol", symbol)
m2.metric("Spot", fmt(flow_data["spot"]))
m3.metric("0DTE Delta Net", money_fmt(flow_data["zero_dte"]["net_premium"]))
m4.metric("All Exp Delta Net", money_fmt(flow_data["all_exp"]["net_premium"]))
m5.metric(
    "Call Gamma",
    fmt(gamma_levels.get("top_call_gamma"))
    if gamma_levels.get("top_call_gamma")
    else "N/A",
)
m6.metric(
    "Put Gamma",
    fmt(gamma_levels.get("top_put_gamma"))
    if gamma_levels.get("top_put_gamma")
    else "N/A",
)

m7, m8, m9 = st.columns(3)

m7.metric("0DTE Rows", flow_data["zero_dte"]["rows"])
m8.metric("All Exp Rows", flow_data["all_exp"]["rows"])
m9.metric("0DTE Exp", flow_data["today_exp"])


# ============================================================
# DISPLAY CHART
# ============================================================

st.plotly_chart(
    flow_comparison_chart(
        history_df,
        symbol,
        flow_data,
    ),
    width="stretch",
)


# ============================================================
# RAW DATA
# ============================================================

with st.expander("Advanced: Expiration Flow Data"):
    st.json(flow_data)

with st.expander("Advanced: Session History"):
    st.dataframe(history_df, width="stretch")
