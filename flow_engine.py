# ============================================================
# flow_engine.py
# SPX / SPY / QQQ / TSLA / AAPL Options Data Engine - Tradier
# Pulls Today + Next Expirations
# Greeks Enabled + Flattened Greeks
# Includes get_flow_snapshot() for Streamlit app.py
# ============================================================

import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=True)

TRADIER_API_KEY = os.getenv("TRADIER_API_KEY")
TRADIER_BASE_URL = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1")

HEADERS = {
    "Authorization": f"Bearer {TRADIER_API_KEY}",
    "Accept": "application/json",
}


# ============================================================
# SYMBOL CONFIG
# ============================================================

SUPPORTED_SYMBOLS = ["SPX", "SPY", "QQQ", "TSLA", "AAPL"]

GAMMA_LEVELS = {
    "SPX": {
        "call_gamma": 5850,
        "put_gamma": 5800,
    },
    "SPY": {
        "call_gamma": 585,
        "put_gamma": 580,
    },
    "QQQ": {
        "call_gamma": 510,
        "put_gamma": 500,
    },
    "TSLA": {
        "call_gamma": 450,
        "put_gamma": 430,
    },
    "AAPL": {
        "call_gamma": 215,
        "put_gamma": 210,
    },
}


def get_option_root(symbol):
    """
    For SPX, Tradier often uses SPX for expirations/chains.
    If SPX chains return empty, try changing this to SPXW.
    For SPY, QQQ, TSLA, AAPL, the root is the same as the symbol.
    """
    symbol = symbol.upper().strip()

    if symbol == "SPX":
        return "SPX"

    return symbol


# ============================================================
# TRADIER GET
# ============================================================

def _tradier_get(endpoint, params=None):
    if not TRADIER_API_KEY:
        raise Exception("Missing TRADIER_API_KEY in .env file")

    url = f"{TRADIER_BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=20,
    )

    if response.status_code != 200:
        raise Exception(
            f"Tradier API Error {response.status_code}: {response.text}"
        )

    return response.json()


# ============================================================
# PRICE
# ============================================================

def get_price(symbol="SPY"):
    symbol = symbol.upper().strip()

    data = _tradier_get(
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

    raise Exception(
        f"Could not get valid {symbol} price. Quote response: {quote}"
    )


# ============================================================
# EXPIRATIONS
# ============================================================

def get_expirations(symbol="SPY"):
    symbol = symbol.upper().strip()
    option_root = get_option_root(symbol)

    data = _tradier_get(
        "markets/options/expirations",
        params={
            "symbol": option_root,
            "includeAllRoots": "true",
            "strikes": "false",
        },
    )

    expirations_block = data.get("expirations")

    if expirations_block is None:
        raise Exception(
            f"No expirations returned for {option_root}. Raw response: {data}"
        )

    expirations = expirations_block.get("date", [])

    if isinstance(expirations, str):
        expirations = [expirations]

    if not expirations:
        raise Exception(
            f"Expiration list empty for {option_root}. Raw response: {data}"
        )

    return expirations


def get_next_expiration(symbol="SPY"):
    expirations = get_expirations(symbol)
    return expirations[0]


# ============================================================
# GREEKS
# ============================================================

def flatten_greeks(df):
    if df is None or df.empty:
        return pd.DataFrame()

    if "greeks" not in df.columns:
        return df

    def get_greek(row, key):
        try:
            g = row.get("greeks", {})
            if isinstance(g, dict):
                value = g.get(key)
                if value is not None:
                    return value
        except Exception:
            pass

        return None

    greek_map = {
        "delta": "delta",
        "gamma": "gamma",
        "theta": "theta",
        "vega": "vega",
        "rho": "rho",
        "mid_iv": "iv",
        "smv_vol": "iv",
        "iv": "iv",
    }

    for source_key, target_col in greek_map.items():
        values = df.apply(lambda row: get_greek(row, source_key), axis=1)

        if target_col not in df.columns:
            df[target_col] = values
        else:
            df[target_col] = df[target_col].fillna(values)

    return df


# ============================================================
# OPTION CHAIN
# ============================================================

def get_option_chain(symbol="SPY", expiration=None):
    symbol = symbol.upper().strip()
    option_root = get_option_root(symbol)

    if expiration is None:
        expiration = get_next_expiration(symbol)

    data = _tradier_get(
        "markets/options/chains",
        params={
            "symbol": option_root,
            "expiration": expiration,
            "greeks": "true",
        },
    )

    options_block = data.get("options")

    if not options_block:
        print(f"NO OPTIONS BLOCK FOR {option_root} {expiration}. RAW RESPONSE:")
        print(data)
        return pd.DataFrame()

    options = options_block.get("option", [])

    if isinstance(options, dict):
        options = [options]

    if not options:
        print(f"NO OPTIONS FOUND FOR {option_root} {expiration}. RAW RESPONSE:")
        print(data)
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
        raise Exception(
            f"No call/put type column found for {option_root}. "
            f"Columns: {df.columns.tolist()}"
        )

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

    required_cols = ["strike", "type", "volume"]
    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        raise Exception(
            f"Missing required columns for {option_root}: {missing}. "
            f"Available columns: {df.columns.tolist()}"
        )

    df["type"] = (
        df["type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .replace({
            "calls": "call",
            "puts": "put",
            "c": "call",
            "p": "put",
        })
    )

    if "last" not in df.columns:
        if "bid" in df.columns and "ask" in df.columns:
            df["last"] = (
                pd.to_numeric(df["bid"], errors="coerce").fillna(0)
                + pd.to_numeric(df["ask"], errors="coerce").fillna(0)
            ) / 2
        else:
            df["last"] = 0

    if "open_interest" not in df.columns:
        df["open_interest"] = 0

    numeric_cols = [
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
        "iv",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(subset=["strike"])
    df = df[df["type"].isin(["call", "put"])]

    if df.empty:
        print(f"DATAFRAME EMPTY AFTER CALL/PUT FILTER FOR {option_root} {expiration}.")
        return pd.DataFrame()

    df["symbol_root"] = option_root
    df["display_symbol"] = symbol
    df["expiration"] = str(expiration)
    df["premium"] = df["last"] * df["volume"] * 100

    keep_cols = [
        "symbol",
        "symbol_root",
        "display_symbol",
        "description",
        "expiration",
        "strike",
        "type",
        "bid",
        "ask",
        "last",
        "volume",
        "open_interest",
        "delta",
        "gamma",
        "theta",
        "vega",
        "rho",
        "iv",
        "premium",
    ]

    existing_cols = [c for c in keep_cols if c in df.columns]
    extra_cols = [
        c for c in df.columns
        if c not in existing_cols and c != "greeks"
    ]

    return df[existing_cols + extra_cols]


# ============================================================
# FILTER / SUMMARY
# ============================================================

def filter_near_money(df, spot_price, width=10, min_strikes=9):
    if df is None or df.empty:
        return pd.DataFrame()

    spot_price = float(spot_price)

    filtered = df[
        (df["strike"] >= spot_price - width)
        & (df["strike"] <= spot_price + width)
    ].copy()

    if filtered.empty or filtered["strike"].nunique() < min_strikes:
        expanded_width = width * 2

        filtered = df[
            (df["strike"] >= spot_price - expanded_width)
            & (df["strike"] <= spot_price + expanded_width)
        ].copy()

    return filtered


def summarize_flow(df):
    if df is None or df.empty:
        return {
            "call_premium": 0,
            "put_premium": 0,
            "net_premium": 0,
            "call_volume": 0,
            "put_volume": 0,
        }

    calls = df[df["type"] == "call"]
    puts = df[df["type"] == "put"]

    call_premium = calls["premium"].sum()
    put_premium = puts["premium"].sum()
    call_volume = calls["volume"].sum()
    put_volume = puts["volume"].sum()

    return {
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": call_premium - put_premium,
        "call_volume": call_volume,
        "put_volume": put_volume,
    }


def bias_from_value(value):
    try:
        value = float(value)
    except Exception:
        value = 0

    if value > 0:
        return "BULLISH"
    if value < 0:
        return "BEARISH"
    return "NEUTRAL"


# ============================================================
# MAIN DATA FUNCTION
# ============================================================

def get_spx_flow_data(symbol="SPY", width=10, all_exp_count=3):
    """
    Name kept so existing dashboard imports do not break.

    Supports:
    - SPX
    - SPY
    - QQQ
    - TSLA
    - AAPL

    Pulls:
    - Today expiration
    - Next expirations based on all_exp_count
    """

    symbol = symbol.upper().strip()
    option_root = get_option_root(symbol)

    spot_price = get_price(symbol)

    expirations = get_expirations(symbol)[:all_exp_count]

    chains = []

    for exp in expirations:
        temp_chain = get_option_chain(symbol, exp)

        if temp_chain is not None and not temp_chain.empty:
            temp_chain["expiration"] = str(exp)
            chains.append(temp_chain)

    if not chains:
        raise Exception(
            f"No option chains returned. "
            f"Symbol={symbol}, OptionRoot={option_root}, "
            f"Spot={spot_price}, Expirations={expirations}"
        )

    chain_df = pd.concat(chains, ignore_index=True)

    chain_df = filter_near_money(
        chain_df,
        spot_price,
        width=width,
    )

    if chain_df is None or chain_df.empty:
        raise Exception(
            f"Option chain returned empty dataframe after near-money filter. "
            f"Symbol={symbol}, OptionRoot={option_root}, "
            f"Spot={spot_price}, Expirations={expirations}"
        )

    flow_summary = summarize_flow(chain_df)

    return {
        "symbol": symbol,
        "option_root": option_root,
        "spot_price": spot_price,
        "expiration": expirations[0],
        "expirations": expirations,
        "chain_df": chain_df,
        "flow_summary": flow_summary,
    }


# ============================================================
# DASHBOARD SNAPSHOT WRAPPER
# ============================================================

def get_flow_snapshot(
    symbol="SPY",
    all_exp_count=5,
    chart_bucket=1,
    lookback_hours=2,
    strike_width=100,
):
    """
    Wrapper used by app.py.

    Converts get_spx_flow_data() output into the newer dashboard format.
    """

    symbol = symbol.upper().strip()

    data = get_spx_flow_data(
        symbol=symbol,
        width=strike_width,
        all_exp_count=all_exp_count,
    )

    chain_df = data.get("chain_df", pd.DataFrame())
    flow_summary = data.get("flow_summary", {})

    spot = data.get("spot_price", 0)
    expiration = data.get("expiration", "")
    expirations = data.get("expirations", [])

    call_gamma_level = GAMMA_LEVELS.get(symbol, {}).get("call_gamma", 0)
    put_gamma_level = GAMMA_LEVELS.get(symbol, {}).get("put_gamma", 0)

    if chain_df is None or chain_df.empty:
        return {
            "symbol": symbol,
            "spot": spot,
            "expiration": expiration,
            "odte_exp": expiration,
            "expirations": expirations,
            "odte_premium_net": 0,
            "all_exp_premium_net": 0,
            "odte_signed_delta": 0,
            "odte_delta_bias": "NEUTRAL",
            "all_exp_delta_bias": "NEUTRAL",
            "call_gamma": call_gamma_level,
            "put_gamma": put_gamma_level,
            "gamma_regime": "NEUTRAL",
            "gamma_signal": 0,
            "divergence_value": 0,
            "pulse_drop_signal": 0,
            "odte_rows": 0,
            "all_exp_rows": 0,
            "chain_df": pd.DataFrame(),
            "chart_df": pd.DataFrame(),
        }

    odte_exp = str(expiration)

    odte_df = chain_df[
        chain_df["expiration"].astype(str) == odte_exp
    ].copy()

    if odte_df.empty:
        odte_df = chain_df.copy()

    calls = odte_df[odte_df["type"] == "call"]
    puts = odte_df[odte_df["type"] == "put"]

    call_premium = calls["premium"].sum() if "premium" in calls.columns else 0
    put_premium = puts["premium"].sum() if "premium" in puts.columns else 0

    odte_premium_net = call_premium - put_premium
    all_exp_premium_net = flow_summary.get("net_premium", 0)

    if "delta" in odte_df.columns:
        odte_df["signed_delta_notional"] = (
            float(spot)
            * odte_df["delta"]
            * odte_df["volume"]
            * 100
        )
        odte_signed_delta = odte_df["signed_delta_notional"].sum()
    else:
        odte_signed_delta = 0

    if call_gamma_level and spot >= call_gamma_level:
        gamma_regime = "ABOVE CALL GAMMA"
        gamma_signal = 1
    elif put_gamma_level and spot <= put_gamma_level:
        gamma_regime = "BELOW PUT GAMMA"
        gamma_signal = -1
    else:
        gamma_regime = "BETWEEN GAMMA LEVELS"
        gamma_signal = 0

    chart_df = odte_df.copy()

    if not chart_df.empty:
        chart_df["price"] = spot

        if "premium" in chart_df.columns:
            chart_df["premium_flow"] = chart_df.apply(
                lambda row: row["premium"] if row["type"] == "call" else -row["premium"],
                axis=1,
            )
        else:
            chart_df["premium_flow"] = 0

        chart_df = (
            chart_df
            .groupby("strike", as_index=False)
            .agg({
                "premium_flow": "sum",
                "price": "last",
            })
        )

        chart_df["time"] = chart_df["strike"]

    divergence_value = odte_premium_net - odte_signed_delta

    pulse_drop_signal = (
        1 if odte_premium_net > 0
        else -1 if odte_premium_net < 0
        else 0
    )

    return {
        "symbol": symbol,
        "spot": spot,
        "expiration": expiration,
        "odte_exp": odte_exp,
        "expirations": expirations,

        "odte_premium_net": odte_premium_net,
        "all_exp_premium_net": all_exp_premium_net,

        "odte_signed_delta": odte_signed_delta,
        "odte_delta_bias": bias_from_value(odte_signed_delta),
        "all_exp_delta_bias": bias_from_value(all_exp_premium_net),

        "call_gamma": call_gamma_level,
        "put_gamma": put_gamma_level,
        "gamma_regime": gamma_regime,
        "gamma_signal": gamma_signal,

        "divergence_value": divergence_value,
        "pulse_drop_signal": pulse_drop_signal,

        "odte_rows": len(odte_df),
        "all_exp_rows": len(chain_df),

        "chain_df": chain_df,
        "chart_df": chart_df,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    test_symbol = os.getenv("TEST_SYMBOL", "SPY").upper().strip()

    print("Testing flow_engine.py...")
    print(f"Symbol: {test_symbol}")
    print(f"Option Root: {get_option_root(test_symbol)}")

    print("Price:")
    print(get_price(test_symbol))

    print("Expirations:")
    expirations = get_expirations(test_symbol)
    print(expirations[:5])

    print("Using first 3 expirations:")
    print(expirations[:3])

    data = get_spx_flow_data(
        symbol=test_symbol,
        width=150,
        all_exp_count=3,
    )

    chain = data["chain_df"]

    print("Chain rows:")
    print(len(chain))

    print("Expirations in dataframe:")
    print(chain["expiration"].unique())

    print("Unique option types:")
    print(chain["type"].unique())

    print("Columns:")
    print(chain.columns.tolist())

    print("Greek sample:")
    print(
        chain[
            [
                c for c in [
                    "display_symbol",
                    "symbol_root",
                    "expiration",
                    "strike",
                    "type",
                    "delta",
                    "gamma",
                    "theta",
                    "vega",
                    "iv",
                    "open_interest",
                    "volume",
                ]
                if c in chain.columns
            ]
        ].head()
    )

    print("Head:")
    print(chain.head())

    print("Snapshot:")
    snapshot = get_flow_snapshot(test_symbol)
    print(snapshot.keys())
