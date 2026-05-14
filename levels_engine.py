import pandas as pd

def compute_price_levels(chain_df, spot_price):

    if chain_df is None or chain_df.empty:
        return {}

    df = chain_df.copy()
    spot_price = float(spot_price)

    calls = df[df["type"] == "call"]
    puts = df[df["type"] == "put"]

    calls_above = calls[calls["strike"] >= spot_price]
    puts_below = puts[puts["strike"] <= spot_price]

    call_levels = (
        calls_above.groupby("strike")
        .agg(call_oi=("open_interest", "sum"),
             call_premium=("premium", "sum"))
        .sort_values(["call_premium", "call_oi"], ascending=False)
    )

    put_levels = (
        puts_below.groupby("strike")
        .agg(put_oi=("open_interest", "sum"),
             put_premium=("premium", "sum"))
        .sort_values(["put_premium", "put_oi"], ascending=False)
    )

    total_oi = (
        df.groupby("strike")["open_interest"]
        .sum()
        .sort_values(ascending=False)
    )

    return {
        "spot_price": spot_price,
        "upside_target": call_levels.index[0] if not call_levels.empty else None,
        "downside_target": put_levels.index[0] if not put_levels.empty else None,
        "nearest_resistance": calls_above["strike"].min() if not calls_above.empty else None,
        "nearest_support": puts_below["strike"].max() if not puts_below.empty else None,
        "max_oi_magnet": total_oi.index[0] if not total_oi.empty else None,
        "call_levels": call_levels.head(10),
        "put_levels": put_levels.head(10)
    }