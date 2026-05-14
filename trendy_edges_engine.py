import pandas as pd
from flow_engine import _tradier_get


def _edges_from_high_low(high, low):
    high = float(high)
    low = float(low)
    rng = high - low

    return {
        "supply": low + (rng * 0.887),
        "mid": low + (rng * 0.500),
        "demand": high - (rng * 0.887),
        "bull": high - (rng * 0.382),
        "bear": low + (rng * 0.382),
    }


def get_trendy_edges(symbol):
    data = _tradier_get(
        "markets/history",
        params={
            "symbol": symbol,
            "interval": "daily"
        }
    )

    days = data.get("history", {}).get("day", [])

    if isinstance(days, dict):
        days = [days]

    df = pd.DataFrame(days)

    if df.empty or len(df) < 10:
        return {}

    df["date"] = pd.to_datetime(df["date"])
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")

    df = df.dropna().sort_values("date")

    prev_day = df.iloc[-2]
    daily = _edges_from_high_low(prev_day["high"], prev_day["low"])

    weekly = (
        df.set_index("date")
        .resample("W-FRI")
        .agg({"high": "max", "low": "min"})
        .dropna()
    )

    prev_week = weekly.iloc[-2]
    weekly_edges = _edges_from_high_low(prev_week["high"], prev_week["low"])

    return {
        "daily": daily,
        "weekly": weekly_edges
    }


def format_trendy_edges(edges):
    if not edges:
        return "Tr3ndy levels unavailable."

    d = edges["daily"]
    w = edges["weekly"]

    return f"""
Tr3ndy Daily / Weekly Levels

Daily:
Supply: {d['supply']:.2f}
Mid: {d['mid']:.2f}
Demand: {d['demand']:.2f}

Weekly:
Supply: {w['supply']:.2f}
Mid: {w['mid']:.2f}
Demand: {w['demand']:.2f}
""".strip()