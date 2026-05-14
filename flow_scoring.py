# ============================================================
# flow_scoring.py
# SPX Options Flow Scoring Module
# Purpose:
#   - Score upside/downside potential from option volume/premium
#   - Identify top call/put strikes
#   - Judge flow dominance, near-money pressure, and target zones
# ============================================================

import pandas as pd
import numpy as np


def _money(value):
    try:
        value = float(value)
    except Exception:
        return "$0"

    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def _safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize_option_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Makes the module more forgiving if your option chain columns
    use slightly different names.
    """

    df = df.copy()

    rename_map = {
        "option_type": "type",
        "put_call": "type",
        "contract_type": "type",
        "bid_price": "bid",
        "ask_price": "ask",
        "last_price": "last",
        "trade_volume": "volume",
    }

    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    if "type" in df.columns:
        df["type"] = df["type"].astype(str).str.lower()
        df["type"] = df["type"].replace({
            "calls": "call",
            "puts": "put",
            "c": "call",
            "p": "put",
        })

    required = ["strike", "type", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required option column: {col}")

    if "last" not in df.columns:
        if "bid" in df.columns and "ask" in df.columns:
            df["last"] = (df["bid"].astype(float) + df["ask"].astype(float)) / 2
        else:
            df["last"] = 0.0

    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["last"] = pd.to_numeric(df["last"], errors="coerce").fillna(0)

    if "open_interest" in df.columns:
        df["open_interest"] = pd.to_numeric(df["open_interest"], errors="coerce").fillna(0)
    elif "oi" in df.columns:
        df["open_interest"] = pd.to_numeric(df["oi"], errors="coerce").fillna(0)
    else:
        df["open_interest"] = 0

    df = df.dropna(subset=["strike"])
    df = df[df["type"].isin(["call", "put"])]

    return df


def score_options_flow(
    df: pd.DataFrame,
    spot_price: float,
    previous_top_call_strike=None,
    previous_top_put_strike=None,
    near_money_width: float = 30,
    atm_width: float = 10,
    min_volume: int = 1,
) -> dict:
    """
    Main scoring function.

    Returns:
        dict with upside_score, downside_score, bias, top strikes,
        premium stats, and human-readable interpretation.
    """

    spot_price = float(spot_price)
    df = normalize_option_columns(df)

    # Keep relevant strikes around spot
    df = df[
        (df["strike"] >= spot_price - near_money_width)
        & (df["strike"] <= spot_price + near_money_width)
    ].copy()

    df = df[df["volume"] >= min_volume].copy()

    if df.empty:
        return {
            "bias": "NO FLOW",
            "upside_score": 0,
            "downside_score": 0,
            "net_score": 0,
            "message": "No usable option flow found near spot.",
            "top_call_strike": None,
            "top_put_strike": None,
            "summary": {},
            "top_calls": pd.DataFrame(),
            "top_puts": pd.DataFrame(),
        }

    # Premium = option price * contracts * multiplier
    df["premium"] = df["last"] * df["volume"] * 100
    df["distance_from_spot"] = (df["strike"] - spot_price).abs()

    calls = df[df["type"] == "call"].copy()
    puts = df[df["type"] == "put"].copy()

    call_premium = calls["premium"].sum()
    put_premium = puts["premium"].sum()

    call_volume = calls["volume"].sum()
    put_volume = puts["volume"].sum()

    total_premium = call_premium + put_premium
    net_premium = call_premium - put_premium

    call_ratio = call_premium / put_premium if put_premium > 0 else np.inf
    put_ratio = put_premium / call_premium if call_premium > 0 else np.inf

    # Top strikes by premium
    top_calls = (
        calls.groupby("strike", as_index=False)
        .agg(
            premium=("premium", "sum"),
            volume=("volume", "sum"),
            open_interest=("open_interest", "sum"),
            distance_from_spot=("distance_from_spot", "min"),
        )
        .sort_values("premium", ascending=False)
        .head(5)
    )

    top_puts = (
        puts.groupby("strike", as_index=False)
        .agg(
            premium=("premium", "sum"),
            volume=("volume", "sum"),
            open_interest=("open_interest", "sum"),
            distance_from_spot=("distance_from_spot", "min"),
        )
        .sort_values("premium", ascending=False)
        .head(5)
    )

    top_call_strike = None if top_calls.empty else float(top_calls.iloc[0]["strike"])
    top_put_strike = None if top_puts.empty else float(top_puts.iloc[0]["strike"])

    top_call_premium = 0 if top_calls.empty else float(top_calls.iloc[0]["premium"])
    top_put_premium = 0 if top_puts.empty else float(top_puts.iloc[0]["premium"])

    top_call_distance = 999 if top_calls.empty else float(top_calls.iloc[0]["distance_from_spot"])
    top_put_distance = 999 if top_puts.empty else float(top_puts.iloc[0]["distance_from_spot"])

    # ========================================================
    # UPSIDE SCORE
    # ========================================================
    upside_score = 0
    upside_reasons = []

    if net_premium > 0:
        upside_score += 20
        upside_reasons.append("Calls have positive net premium advantage")

    if call_premium > put_premium * 1.25:
        upside_score += 20
        upside_reasons.append("Call premium is meaningfully stronger than put premium")

    if call_volume > put_volume * 1.25:
        upside_score += 10
        upside_reasons.append("Call volume is stronger than put volume")

    if top_call_strike is not None and top_call_strike >= spot_price:
        upside_score += 10
        upside_reasons.append("Top call strike is above/at spot")

    if top_call_distance <= atm_width:
        upside_score += 15
        upside_reasons.append("Top call strike is near the money")

    if top_call_premium > top_put_premium:
        upside_score += 10
        upside_reasons.append("Largest call strike premium exceeds largest put strike premium")

    if previous_top_call_strike is not None and top_call_strike == previous_top_call_strike:
        upside_score += 15
        upside_reasons.append("Top call strike is repeating from prior scan")

    upside_score = min(upside_score, 100)

    # ========================================================
    # DOWNSIDE SCORE
    # ========================================================
    downside_score = 0
    downside_reasons = []

    if net_premium < 0:
        downside_score += 20
        downside_reasons.append("Puts have positive net premium advantage")

    if put_premium > call_premium * 1.25:
        downside_score += 20
        downside_reasons.append("Put premium is meaningfully stronger than call premium")

    if put_volume > call_volume * 1.25:
        downside_score += 10
        downside_reasons.append("Put volume is stronger than call volume")

    if top_put_strike is not None and top_put_strike <= spot_price:
        downside_score += 10
        downside_reasons.append("Top put strike is below/at spot")

    if top_put_distance <= atm_width:
        downside_score += 15
        downside_reasons.append("Top put strike is near the money")

    if top_put_premium > top_call_premium:
        downside_score += 10
        downside_reasons.append("Largest put strike premium exceeds largest call strike premium")

    if previous_top_put_strike is not None and top_put_strike == previous_top_put_strike:
        downside_score += 15
        downside_reasons.append("Top put strike is repeating from prior scan")

    downside_score = min(downside_score, 100)

    net_score = upside_score - downside_score

    # Bias interpretation
    if upside_score >= 80 and upside_score >= downside_score + 15:
        bias = "STRONG UPSIDE"
    elif upside_score >= 60 and upside_score > downside_score:
        bias = "MODERATE UPSIDE"
    elif downside_score >= 80 and downside_score >= upside_score + 15:
        bias = "STRONG DOWNSIDE"
    elif downside_score >= 60 and downside_score > upside_score:
        bias = "MODERATE DOWNSIDE"
    else:
        bias = "BALANCED / CHOP"

    summary = {
        "spot_price": spot_price,
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": net_premium,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "call_ratio": call_ratio,
        "put_ratio": put_ratio,
        "top_call_strike": top_call_strike,
        "top_put_strike": top_put_strike,
        "top_call_premium": top_call_premium,
        "top_put_premium": top_put_premium,
    }

    message = (
        f"{bias} | "
        f"Upside Score: {upside_score}/100 | "
        f"Downside Score: {downside_score}/100 | "
        f"Calls: {_money(call_premium)} | "
        f"Puts: {_money(put_premium)} | "
        f"Net: {_money(net_premium)}"
    )

    return {
        "bias": bias,
        "upside_score": upside_score,
        "downside_score": downside_score,
        "net_score": net_score,
        "message": message,
        "summary": summary,
        "upside_reasons": upside_reasons,
        "downside_reasons": downside_reasons,
        "top_call_strike": top_call_strike,
        "top_put_strike": top_put_strike,
        "top_calls": top_calls,
        "top_puts": top_puts,
        "scored_chain": df,
    }


def format_flow_alert(flow_result: dict, symbol: str = "SPX") -> str:
    """
    Creates a clean alert message for Discord, Telegram, email, etc.
    """

    summary = flow_result.get("summary", {})

    msg = f"""
🚨 {symbol} OPTIONS FLOW ALERT

Bias: {flow_result.get("bias")}
Upside Score: {flow_result.get("upside_score")}/100
Downside Score: {flow_result.get("downside_score")}/100

Spot: {summary.get("spot_price")}

Calls: {_money(summary.get("call_premium", 0))}
Puts: {_money(summary.get("put_premium", 0))}
Net Premium: {_money(summary.get("net_premium", 0))}

Top Call Strike: {summary.get("top_call_strike")}
Top Put Strike: {summary.get("top_put_strike")}

Reason:
{chr(10).join("- " + r for r in flow_result.get("upside_reasons", [])[:4])}

Manual confirmation required.
"""
    return msg.strip()