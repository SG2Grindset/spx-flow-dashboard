# ============================================================
# gamma_level_engine.py
# Builds Gamma / Delta Levels from Option Chain Data
# Includes:
# - Directional Call / Put Walls
# - Zero Gamma
# - Vol Trigger
# - Magnet
# - Gamma Curve Chart
# - Dealer Gamma Regime
# - 0DTE Gamma Weighting
# ============================================================

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go


# ============================================================
# HELPERS
# ============================================================

def safe_num(series, default=0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def find_col(df, possible_names):
    cols = {c.lower(): c for c in df.columns}

    for name in possible_names:
        if name.lower() in cols:
            return cols[name.lower()]

    return None


def calc_dte(exp_value):
    try:
        today = datetime.now().date()
        exp_date = pd.to_datetime(exp_value).date()
        return max((exp_date - today).days, 0)
    except Exception:
        return 999


def gamma_weight_from_dte(dte):
    try:
        dte = int(dte)
    except Exception:
        return 1.0

    if dte == 0:
        return 3.0

    if dte == 1:
        return 2.0

    if dte <= 5:
        return 1.25

    return 1.0


# ============================================================
# MAIN LEVEL BUILDER
# ============================================================

def build_gamma_delta_levels(chain_df, spot_price):
    df = chain_df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]

    strike_col = find_col(df, ["strike"])
    type_col = find_col(df, ["type", "option_type"])
    gamma_col = find_col(df, ["gamma", "greeks.gamma"])
    delta_col = find_col(df, ["delta", "greeks.delta"])
    oi_col = find_col(df, ["open_interest", "oi"])
    volume_col = find_col(df, ["volume"])
    last_col = find_col(df, ["last", "mark", "price"])
    exp_col = find_col(df, ["expiration", "exp_date", "expiry"])

    if strike_col is None or type_col is None:
        return {
            "error": "Missing strike or option type column.",
            "levels": {},
            "detail": pd.DataFrame()
        }

    df[strike_col] = safe_num(df[strike_col])
    df[type_col] = df[type_col].astype(str).str.lower()

    if gamma_col is None:
        df["gamma"] = 0
        gamma_col = "gamma"
    else:
        df[gamma_col] = safe_num(df[gamma_col])

    if delta_col is None:
        df["delta"] = 0
        delta_col = "delta"
    else:
        df[delta_col] = safe_num(df[delta_col])

    if oi_col is None:
        df["open_interest"] = 0
        oi_col = "open_interest"
    else:
        df[oi_col] = safe_num(df[oi_col])

    if volume_col is None:
        df["volume"] = 0
        volume_col = "volume"
    else:
        df[volume_col] = safe_num(df[volume_col])

    if last_col is None:
        df["last"] = 0
        last_col = "last"
    else:
        df[last_col] = safe_num(df[last_col])

    df = df.dropna(subset=[strike_col])

    if df.empty:
        return {
            "error": "Option chain dataframe is empty after cleanup.",
            "levels": {},
            "detail": pd.DataFrame()
        }

    # ============================================================
    # EXPIRATION / 0DTE WEIGHTING
    # ============================================================

    if exp_col is not None:
        df["dte"] = df[exp_col].apply(calc_dte)
    else:
        df["dte"] = 999

    df["gamma_weight"] = df["dte"].apply(gamma_weight_from_dte)

    # ============================================================
    # CORE CALCULATIONS
    # ============================================================

    df["premium"] = df[last_col] * df[volume_col] * 100

    df["delta_notional"] = (
        df[delta_col]
        * df[volume_col]
        * 100
        * float(spot_price)
    )

    df["gex_raw"] = (
        df[gamma_col]
        * df[oi_col]
        * 100
        * float(spot_price) ** 2
        * 0.01
    )

    df["gex"] = df["gex_raw"] * df["gamma_weight"]

    # Dealer-style convention:
    # Calls = positive gamma
    # Puts  = negative gamma
    df.loc[df[type_col].str.contains("put"), "gex"] *= -1
    df.loc[df[type_col].str.contains("put"), "gex_raw"] *= -1

    # ============================================================
    # GROUP BY STRIKE
    # ============================================================

    by_strike = (
        df.groupby(strike_col)
        .agg(
            total_gex=("gex", "sum"),
            raw_gex=("gex_raw", "sum"),
            abs_gex=("gex", lambda x: x.abs().sum()),
            total_delta=("delta_notional", "sum"),
            abs_delta=("delta_notional", lambda x: x.abs().sum()),
            total_oi=(oi_col, "sum"),
            total_volume=(volume_col, "sum"),
            total_premium=("premium", "sum"),
            min_dte=("dte", "min"),
            avg_gamma_weight=("gamma_weight", "mean"),
        )
        .reset_index()
        .rename(columns={strike_col: "strike"})
        .sort_values("strike")
    )

    calls = df[df[type_col].str.contains("call")]
    puts = df[df[type_col].str.contains("put")]

    call_by_strike = (
        calls.groupby(strike_col)
        .agg(
            call_gex=("gex", "sum"),
            call_oi=(oi_col, "sum"),
            call_volume=(volume_col, "sum"),
            call_premium=("premium", "sum"),
            call_delta=("delta_notional", "sum"),
        )
        .reset_index()
        .rename(columns={strike_col: "strike"})
    )

    put_by_strike = (
        puts.groupby(strike_col)
        .agg(
            put_gex=("gex", "sum"),
            put_oi=(oi_col, "sum"),
            put_volume=(volume_col, "sum"),
            put_premium=("premium", "sum"),
            put_delta=("delta_notional", "sum"),
        )
        .reset_index()
        .rename(columns={strike_col: "strike"})
    )

    by_strike = by_strike.merge(call_by_strike, on="strike", how="left")
    by_strike = by_strike.merge(put_by_strike, on="strike", how="left")
    by_strike = by_strike.fillna(0)

    by_strike["distance_from_spot"] = abs(
        by_strike["strike"] - float(spot_price)
    )

    # ============================================================
    # DIRECTIONAL WALL LOGIC
    # ============================================================

    call_by_strike["call_pressure"] = (
        call_by_strike["call_gex"].abs()
        + call_by_strike["call_oi"]
        + call_by_strike["call_volume"]
        + call_by_strike["call_premium"]
    )

    put_by_strike["put_pressure"] = (
        put_by_strike["put_gex"].abs()
        + put_by_strike["put_oi"]
        + put_by_strike["put_volume"]
        + put_by_strike["put_premium"]
    )

    call_candidates = call_by_strike[
        call_by_strike["strike"] >= float(spot_price)
    ]

    put_candidates = put_by_strike[
        put_by_strike["strike"] <= float(spot_price)
    ]

    call_wall = (
        call_candidates.sort_values("call_pressure", ascending=False)
        .iloc[0]["strike"]
        if not call_candidates.empty else None
    )

    put_wall = (
        put_candidates.sort_values("put_pressure", ascending=False)
        .iloc[0]["strike"]
        if not put_candidates.empty else None
    )

    # ============================================================
    # MAGNET / VOL TRIGGER / ZERO GAMMA
    # ============================================================

    magnet = (
        by_strike.sort_values("abs_gex", ascending=False)
        .iloc[0]["strike"]
        if not by_strike.empty else None
    )

    nearby = by_strike.sort_values("distance_from_spot").head(15)

    vol_trigger = (
        nearby.sort_values("abs_gex", ascending=False)
        .iloc[0]["strike"]
        if not nearby.empty else None
    )

    by_strike["cum_gex"] = by_strike["total_gex"].cumsum()
    by_strike["abs_cum_gex"] = by_strike["cum_gex"].abs()

    zero_gamma = (
        by_strike.sort_values("abs_cum_gex")
        .iloc[0]["strike"]
        if not by_strike.empty else None
    )

    # ============================================================
    # TOP GAMMA / DELTA LEVELS
    # ============================================================

    top_positive_gex = (
        by_strike.sort_values("total_gex", ascending=False)
        .head(4)["strike"]
        .tolist()
    )

    top_negative_gex = (
        by_strike.sort_values("total_gex", ascending=True)
        .head(4)["strike"]
        .tolist()
    )

    top_delta = (
        by_strike.sort_values("abs_delta", ascending=False)
        .head(4)["strike"]
        .tolist()
    )

    net_gex = by_strike["total_gex"].sum()
    raw_net_gex = by_strike["raw_gex"].sum()
    net_delta = by_strike["total_delta"].sum()

    zero_dte_rows = df[df["dte"] == 0]
    zero_dte_gex = zero_dte_rows["gex"].sum() if not zero_dte_rows.empty else 0

    # ============================================================
    # FINAL LEVEL PACKAGE
    # ============================================================

    levels = {
        "call_wall": call_wall,
        "put_wall": put_wall,
        "zero_gamma": zero_gamma,
        "vol_trigger": vol_trigger,
        "magnet": magnet,

        "c1": top_positive_gex[0] if len(top_positive_gex) > 0 else None,
        "c2": top_positive_gex[1] if len(top_positive_gex) > 1 else None,
        "c3": top_positive_gex[2] if len(top_positive_gex) > 2 else None,
        "c4": top_positive_gex[3] if len(top_positive_gex) > 3 else None,

        "l1": top_negative_gex[0] if len(top_negative_gex) > 0 else None,
        "l2": top_negative_gex[1] if len(top_negative_gex) > 1 else None,
        "l3": top_negative_gex[2] if len(top_negative_gex) > 2 else None,
        "l4": top_negative_gex[3] if len(top_negative_gex) > 3 else None,

        "delta_1": top_delta[0] if len(top_delta) > 0 else None,
        "delta_2": top_delta[1] if len(top_delta) > 1 else None,
        "delta_3": top_delta[2] if len(top_delta) > 2 else None,
        "delta_4": top_delta[3] if len(top_delta) > 3 else None,

        "net_gex": net_gex,
        "raw_net_gex": raw_net_gex,
        "zero_dte_gex": zero_dte_gex,
        "net_delta": net_delta,
    }

    return {
        "error": None,
        "levels": levels,
        "detail": by_strike
    }


# ============================================================
# TEXT FORMATTER
# ============================================================

def format_gamma_delta_levels(result):
    levels = result.get("levels", {})

    if result.get("error"):
        return f"Gamma/Delta Level Error: {result['error']}"

    return f"""
🧠 GAMMA / DELTA LEVELS

Call Wall: {levels.get("call_wall")}
Put Wall: {levels.get("put_wall")}
Zero Gamma: {levels.get("zero_gamma")}
Vol Trigger: {levels.get("vol_trigger")}
Magnet: {levels.get("magnet")}

Positive Gamma:
C1: {levels.get("c1")}
C2: {levels.get("c2")}
C3: {levels.get("c3")}
C4: {levels.get("c4")}

Negative Gamma:
L1: {levels.get("l1")}
L2: {levels.get("l2")}
L3: {levels.get("l3")}
L4: {levels.get("l4")}

Delta Magnets:
D1: {levels.get("delta_1")}
D2: {levels.get("delta_2")}
D3: {levels.get("delta_3")}
D4: {levels.get("delta_4")}

Weighted Net GEX: {levels.get("net_gex")}
Raw Net GEX: {levels.get("raw_net_gex")}
0DTE GEX: {levels.get("zero_dte_gex")}
Net Delta: {levels.get("net_delta")}
""".strip()


# ============================================================
# GAMMA CURVE CHART
# ============================================================

def build_gamma_curve_chart(result, spot_price):
    detail = result.get("detail")

    if detail is None or detail.empty:
        return None

    df = detail.copy()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["strike"],
            y=df["total_gex"],
            name="Weighted Gamma Exposure",
            width=8,
            marker=dict(
                color=[
                    "#00ff99" if v >= 0 else "#ff4d4d"
                    for v in df["total_gex"]
                ],
                line=dict(width=0)
            ),
            opacity=0.95
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["strike"],
            y=df["cum_gex"],
            mode="lines",
            line=dict(width=4, color="#00ccff"),
            name="Cumulative Weighted GEX",
            yaxis="y2",
        )
    )

    fig.add_vline(
        x=float(spot_price),
        line_dash="dash",
        line_color="white",
        annotation_text="Spot",
        annotation_position="top"
    )

    levels = result.get("levels", {})

    if levels.get("zero_gamma") is not None:
        fig.add_vline(
            x=float(levels.get("zero_gamma")),
            line_dash="dot",
            line_color="yellow",
            annotation_text="Zero Gamma",
            annotation_position="top"
        )

    if levels.get("call_wall") is not None:
        fig.add_vline(
            x=float(levels.get("call_wall")),
            line_dash="dash",
            line_color="red",
            annotation_text="Call Wall",
            annotation_position="top"
        )

    if levels.get("put_wall") is not None:
        fig.add_vline(
            x=float(levels.get("put_wall")),
            line_dash="dash",
            line_color="lime",
            annotation_text="Put Wall",
            annotation_position="bottom"
        )

    fig.update_layout(
        title="0DTE-Weighted Gamma Curve by Strike",
        height=600,
        paper_bgcolor="black",
        plot_bgcolor="black",

        font=dict(
            color="white",
            size=14
        ),

        xaxis=dict(
            title="Strike",
            showgrid=False,
            zeroline=False,
            color="white"
        ),

        yaxis=dict(
            title="Weighted Net GEX",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            zeroline=False,
            color="white"
        ),

        yaxis2=dict(
            title="Cumulative Weighted GEX",
            overlaying="y",
            side="right",
            showgrid=False,
            color="white"
        ),

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)"
        ),

        margin=dict(
            l=20,
            r=20,
            t=60,
            b=20
        ),

        hovermode="x unified"
    )

    return fig


# ============================================================
# DEALER GAMMA REGIME
# ============================================================

def determine_gamma_regime(levels):
    try:
        net_gex = float(levels.get("net_gex", 0))
    except Exception:
        net_gex = 0

    try:
        zero_dte_gex = float(levels.get("zero_dte_gex", 0))
    except Exception:
        zero_dte_gex = 0

    abs_gex = abs(net_gex)

    if net_gex > 5_000_000:
        regime = "POSITIVE GAMMA"
        behavior = "Mean Reversion / Pinning"
        bias = "Fade extremes. Expect chop unless price breaks a major wall."
        color = "green"

    elif net_gex < -5_000_000:
        regime = "NEGATIVE GAMMA"
        behavior = "Expansion / Trend"
        bias = "Respect momentum. Breaks can extend quickly."
        color = "red"

    else:
        regime = "NEUTRAL GAMMA"
        behavior = "Balanced / Rotational"
        bias = "Mixed environment. Wait for flow + location confirmation."
        color = "gray"

    if abs(zero_dte_gex) > abs(net_gex) * 0.50 and abs(net_gex) > 0:
        odte_note = "0DTE is dominant today."
    elif abs(zero_dte_gex) > 0:
        odte_note = "0DTE is present but not dominant."
    else:
        odte_note = "No clear 0DTE gamma contribution detected."

    return {
        "regime": regime,
        "behavior": behavior,
        "bias": bias,
        "net_gex": net_gex,
        "zero_dte_gex": zero_dte_gex,
        "odte_note": odte_note,
        "abs_gex": abs_gex,
        "color": color,
    }