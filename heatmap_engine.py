# ============================================================
# heatmap_engine.py
# SG2 FLOW Dashboard - GEX / VEX Heatmap Engine
# Uses existing Tradier chain logic from flow_engine.py
# ============================================================

import pandas as pd

from flow_engine import (
    get_price,
    get_filtered_expirations,
    get_option_chain,
)


# ============================================================
# CORE CONFIG
# ============================================================

DEFAULT_EXP_COUNT = 5

DEFAULT_STRIKE_WIDTH = {
    "SPX": 150,
    "XSP": 20,
    "SPY": 25,
    "QQQ": 25,
    "TSLA": 75,
    "AAPL": 25,
}


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_large_number(value):
    try:
        value = float(value)
    except Exception:
        return "$0.0K"

    sign = "-" if value < 0 else ""
    value = abs(value)

    if value >= 1_000_000_000:
        return f"{sign}${value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:
        return f"{sign}${value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"{sign}${value / 1_000:.1f}K"

    return f"{sign}${value:.0f}"


def clean_numeric(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


# ============================================================
# CHAIN BUILDER
# ============================================================

def get_heatmap_chain(
    symbol="SPY",
    exp_count=DEFAULT_EXP_COUNT,
    strike_width=None,
):
    """
    Pulls multiple expirations and returns one clean chain dataframe.

    Returns:
        chain_df, spot, expirations
    """

    symbol = symbol.upper().strip()

    if strike_width is None:
        strike_width = DEFAULT_STRIKE_WIDTH.get(symbol, 25)

    spot = get_price(symbol)

    expirations = get_filtered_expirations(
        symbol=symbol,
        all_exp_count=exp_count,
    )

    chains = []

    for exp in expirations:
        try:
            df = get_option_chain(symbol=symbol, expiration=exp)

            if df is None or df.empty:
                continue

            df["expiration"] = str(exp)
            chains.append(df)

        except Exception as e:
            print(f"Skipping {symbol} {exp}: {e}")

    if not chains:
        return pd.DataFrame(), spot, expirations

    chain_df = pd.concat(chains, ignore_index=True)

    chain_df = clean_numeric(
        chain_df,
        [
            "strike",
            "last",
            "bid",
            "ask",
            "volume",
            "open_interest",
            "delta",
            "gamma",
            "theta",
            "vega",
            "iv",
        ],
    )

    chain_df["type"] = (
        chain_df["type"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    chain_df = chain_df[
        (chain_df["strike"] >= spot - strike_width)
        & (chain_df["strike"] <= spot + strike_width)
    ].copy()

    return chain_df, spot, expirations


# ============================================================
# GEX CALCULATION
# ============================================================

def calculate_gex(chain_df, spot):
    """
    Gamma Exposure approximation.

    GEX = gamma * open_interest * spot * 100

    Calls are treated as positive.
    Puts are treated as negative.
    """

    if chain_df is None or chain_df.empty:
        return pd.DataFrame()

    df = chain_df.copy()

    required = ["strike", "expiration", "type", "gamma", "open_interest"]

    for col in required:
        if col not in df.columns:
            df[col] = 0

    df = clean_numeric(df, ["strike", "gamma", "open_interest"])

    df["raw_gex"] = (
        df["gamma"]
        * df["open_interest"]
        * float(spot)
        * 100
    )

    df["gex"] = df.apply(
        lambda row: row["raw_gex"]
        if row["type"] == "call"
        else -row["raw_gex"],
        axis=1,
    )

    return df


# ============================================================
# VEX / VANNA-LIKE CALCULATION
# ============================================================

def calculate_vex(chain_df, spot):
    """
    VEX / Vanna-like exposure approximation.

    True vanna requires a direct vanna greek.
    Tradier often does not provide vanna directly.

    This approximation uses:
        vega * delta * open_interest * spot

    Calls are positive when delta is positive.
    Puts are negative when delta is negative.
    """

    if chain_df is None or chain_df.empty:
        return pd.DataFrame()

    df = chain_df.copy()

    required = ["strike", "expiration", "type", "vega", "delta", "open_interest"]

    for col in required:
        if col not in df.columns:
            df[col] = 0

    df = clean_numeric(
        df,
        ["strike", "vega", "delta", "open_interest"],
    )

    df["raw_vex"] = (
        df["vega"]
        * df["delta"]
        * df["open_interest"]
        * float(spot)
        * 100
    )

    df["vex"] = df["raw_vex"]

    return df


# ============================================================
# PREMIUM HEATMAP
# ============================================================

def calculate_premium_exposure(chain_df):
    """
    Premium exposure by strike and expiration.

    Premium = last * volume * 100

    Calls are positive.
    Puts are negative.
    """

    if chain_df is None or chain_df.empty:
        return pd.DataFrame()

    df = chain_df.copy()

    required = ["strike", "expiration", "type", "last", "volume"]

    for col in required:
        if col not in df.columns:
            df[col] = 0

    df = clean_numeric(df, ["strike", "last", "volume"])

    df["raw_premium"] = df["last"] * df["volume"] * 100

    df["premium_exposure"] = df.apply(
        lambda row: row["raw_premium"]
        if row["type"] == "call"
        else -row["raw_premium"],
        axis=1,
    )

    return df


# ============================================================
# PIVOT BUILDER
# ============================================================

def build_heatmap_pivot(
    df,
    value_col,
):
    """
    Creates strike x expiration pivot.

    Rows:
        strike

    Columns:
        expiration

    Values:
        summed exposure
    """

    if df is None or df.empty:
        return pd.DataFrame()

    if value_col not in df.columns:
        return pd.DataFrame()

    pivot = (
        df
        .groupby(["strike", "expiration"], as_index=False)[value_col]
        .sum()
        .pivot(
            index="strike",
            columns="expiration",
            values=value_col,
        )
        .fillna(0)
        .sort_index(ascending=False)
    )

    return pivot


# ============================================================
# MAIN HEATMAP SNAPSHOT
# ============================================================

def get_heatmap_snapshot(
    symbol="SPY",
    exp_count=DEFAULT_EXP_COUNT,
    strike_width=None,
):
    """
    Main function used by Streamlit page.

    Returns:
        {
            symbol,
            spot,
            expirations,
            chain_df,
            gex_df,
            vex_df,
            premium_df,
            gex_pivot,
            vex_pivot,
            premium_pivot,
            top_positive_gex,
            top_negative_gex,
            top_positive_vex,
            top_negative_vex,
        }
    """

    symbol = symbol.upper().strip()

    chain_df, spot, expirations = get_heatmap_chain(
        symbol=symbol,
        exp_count=exp_count,
        strike_width=strike_width,
    )

    if chain_df is None or chain_df.empty:
        return {
            "symbol": symbol,
            "spot": spot,
            "expirations": expirations,
            "chain_df": pd.DataFrame(),
            "gex_df": pd.DataFrame(),
            "vex_df": pd.DataFrame(),
            "premium_df": pd.DataFrame(),
            "gex_pivot": pd.DataFrame(),
            "vex_pivot": pd.DataFrame(),
            "premium_pivot": pd.DataFrame(),
            "top_positive_gex": None,
            "top_negative_gex": None,
            "top_positive_vex": None,
            "top_negative_vex": None,
        }

    gex_df = calculate_gex(chain_df, spot)
    vex_df = calculate_vex(chain_df, spot)
    premium_df = calculate_premium_exposure(chain_df)

    gex_pivot = build_heatmap_pivot(gex_df, "gex")
    vex_pivot = build_heatmap_pivot(vex_df, "vex")
    premium_pivot = build_heatmap_pivot(premium_df, "premium_exposure")

    gex_by_strike = (
        gex_df
        .groupby("strike", as_index=False)["gex"]
        .sum()
        .sort_values("gex", ascending=False)
    )

    vex_by_strike = (
        vex_df
        .groupby("strike", as_index=False)["vex"]
        .sum()
        .sort_values("vex", ascending=False)
    )

    top_positive_gex = None
    top_negative_gex = None
    top_positive_vex = None
    top_negative_vex = None

    if not gex_by_strike.empty:
        top_positive_gex = gex_by_strike.iloc[0].to_dict()
        top_negative_gex = gex_by_strike.iloc[-1].to_dict()

    if not vex_by_strike.empty:
        top_positive_vex = vex_by_strike.iloc[0].to_dict()
        top_negative_vex = vex_by_strike.iloc[-1].to_dict()

    return {
        "symbol": symbol,
        "spot": spot,
        "expirations": expirations,
        "chain_df": chain_df,
        "gex_df": gex_df,
        "vex_df": vex_df,
        "premium_df": premium_df,
        "gex_pivot": gex_pivot,
        "vex_pivot": vex_pivot,
        "premium_pivot": premium_pivot,
        "top_positive_gex": top_positive_gex,
        "top_negative_gex": top_negative_gex,
        "top_positive_vex": top_positive_vex,
        "top_negative_vex": top_negative_vex,
    }


# ============================================================
# STREAMLIT PLOTLY HELPER
# ============================================================

def pivot_to_plotly_heatmap_data(pivot):
    """
    Converts pivot table into x/y/z/text data for Plotly heatmap.
    """

    if pivot is None or pivot.empty:
        return [], [], [], []

    x = list(pivot.columns)
    y = list(pivot.index)
    z = pivot.values.tolist()

    text = []

    for row in z:
        text.append([format_large_number(v) for v in row])

    return x, y, z, text


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    test_symbol = "SPY"

    print(f"Testing heatmap engine for {test_symbol}")

    snap = get_heatmap_snapshot(
        symbol=test_symbol,
        exp_count=5,
        strike_width=25,
    )

    print("Spot:", snap["spot"])
    print("Expirations:", snap["expirations"])
    print("Chain rows:", len(snap["chain_df"]))

    print("GEX Pivot:")
    print(snap["gex_pivot"].head())

    print("VEX Pivot:")
    print(snap["vex_pivot"].head())

    print("Top Positive GEX:")
    print(snap["top_positive_gex"])

    print("Top Negative GEX:")
    print(snap["top_negative_gex"])