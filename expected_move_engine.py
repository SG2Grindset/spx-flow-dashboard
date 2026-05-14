# ============================================================
# expected_move_engine.py
# Calculates Expected Move using ATM Straddle
# ============================================================

import pandas as pd


def safe_num(series, default=0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def build_expected_move(chain_df, spot_price):

    df = chain_df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]

    required = ["strike", "type"]

    for col in required:
        if col not in df.columns:
            return {
                "error": f"Missing required column: {col}"
            }

    if "last" not in df.columns:
        if "mark" in df.columns:
            df["last"] = df["mark"]
        else:
            return {
                "error": "Missing option price column."
            }

    df["strike"] = safe_num(df["strike"])
    df["last"] = safe_num(df["last"])

    # ============================================================
    # FIND ATM STRIKE
    # ============================================================

    df["distance"] = abs(df["strike"] - float(spot_price))

    atm_strike = (
        df.groupby("strike")["distance"]
        .min()
        .sort_values()
        .index[0]
    )

    atm_options = df[df["strike"] == atm_strike]

    calls = atm_options[
        atm_options["type"].astype(str).str.lower().str.contains("call")
    ]

    puts = atm_options[
        atm_options["type"].astype(str).str.lower().str.contains("put")
    ]

    if calls.empty or puts.empty:
        return {
            "error": "Could not locate ATM call/put."
        }

    atm_call = calls.iloc[0]["last"]
    atm_put = puts.iloc[0]["last"]

    straddle_price = float(atm_call) + float(atm_put)

    expected_move = straddle_price

    upper = float(spot_price) + expected_move
    lower = float(spot_price) - expected_move

    expected_move_pct = (
        expected_move / float(spot_price)
    ) * 100

    return {
        "error": None,

        "atm_strike": atm_strike,

        "atm_call": atm_call,
        "atm_put": atm_put,

        "straddle": straddle_price,

        "expected_move": expected_move,
        "expected_move_pct": expected_move_pct,

        "upper": upper,
        "lower": lower,
    }