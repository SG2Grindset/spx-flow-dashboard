# ============================================================
# gamma_engine.py
# Open Interest / Gamma Levels Engine
# ============================================================

import pandas as pd


def get_oi_levels(df):
    if df is None or df.empty:
        return {}

    # Total OI by strike
    oi_by_strike = (
        df.groupby("strike")["open_interest"]
        .sum()
        .sort_values(ascending=False)
    )

    # Separate calls and puts
    calls = df[df["type"] == "call"]
    puts = df[df["type"] == "put"]

    call_oi = (
        calls.groupby("strike")["open_interest"]
        .sum()
        .sort_values(ascending=False)
    )

    put_oi = (
        puts.groupby("strike")["open_interest"]
        .sum()
        .sort_values(ascending=False)
    )

    # Top levels
    top_oi = oi_by_strike.head(5)
    top_calls = call_oi.head(5)
    top_puts = put_oi.head(5)

    return {
        "top_oi": top_oi,
        "top_calls": top_calls,
        "top_puts": top_puts
    }


def get_gamma_bias(df, spot_price):
    if df is None or df.empty:
        return {}

    calls = df[df["type"] == "call"]
    puts = df[df["type"] == "put"]

    call_oi = calls["open_interest"].sum()
    put_oi = puts["open_interest"].sum()

    net_oi = call_oi - put_oi

    if net_oi > 0:
        bias = "CALL DOMINANT (Upside Pressure)"
    elif net_oi < 0:
        bias = "PUT DOMINANT (Downside Pressure)"
    else:
        bias = "BALANCED"

    return {
        "call_oi": call_oi,
        "put_oi": put_oi,
        "net_oi": net_oi,
        "bias": bias
    }