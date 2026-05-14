# ============================================================
# snapshot_engine.py
# Builds Morning Snapshot / Trade Brief
# ============================================================

from datetime import datetime


def _fmt(value):
    try:
        if value is None:
            return "—"
        return f"{float(value):,.2f}"
    except Exception:
        return "—"


def _fmt_money(value):
    try:
        value = float(value)
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        if abs(value) >= 1_000:
            return f"${value / 1_000:.1f}K"
        return f"${value:,.0f}"
    except Exception:
        return "—"


def build_morning_snapshot(
    symbol,
    spot_price,
    expiration,
    flow_result,
    gamma_delta_levels,
    gamma_regime,
    trendy_edges,
    trade_plan,
    a_plus,
):
    summary = flow_result.get("summary", {})

    daily = trendy_edges.get("daily", {})
    weekly = trendy_edges.get("weekly", {})

    snapshot = f"""
📊 MORNING SPX POSITIONING SNAPSHOT
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

SYMBOL: {symbol}
SPOT: {_fmt(spot_price)}
EXPIRATION: {expiration}

==============================
SIGNAL / FLOW
==============================
Signal: {a_plus.get("grade", "NEUTRAL")}
Score: {a_plus.get("score", "—")}
Flow Bias: {flow_result.get("bias", "NEUTRAL")}
Net Score: {flow_result.get("net_score", "—")}

Call Premium: {_fmt_money(summary.get("call_premium"))}
Put Premium: {_fmt_money(summary.get("put_premium"))}
Net Premium: {_fmt_money(summary.get("net_premium"))}

Top Call Target: {_fmt(summary.get("top_call_strike"))}
Top Put Target: {_fmt(summary.get("top_put_strike"))}

==============================
DEALER GAMMA REGIME
==============================
Regime: {gamma_regime.get("regime")}
Expected Behavior: {gamma_regime.get("behavior")}
Bias Note: {gamma_regime.get("bias")}
Net GEX: {_fmt_money(gamma_regime.get("net_gex"))}

==============================
GAMMA / DELTA LEVELS
==============================
Call Wall: {_fmt(gamma_delta_levels.get("call_wall"))}
Put Wall: {_fmt(gamma_delta_levels.get("put_wall"))}
Zero Gamma: {_fmt(gamma_delta_levels.get("zero_gamma"))}
Vol Trigger: {_fmt(gamma_delta_levels.get("vol_trigger"))}
Magnet: {_fmt(gamma_delta_levels.get("magnet"))}

Positive Gamma:
C1: {_fmt(gamma_delta_levels.get("c1"))}
C2: {_fmt(gamma_delta_levels.get("c2"))}
C3: {_fmt(gamma_delta_levels.get("c3"))}
C4: {_fmt(gamma_delta_levels.get("c4"))}

Negative Gamma:
L1: {_fmt(gamma_delta_levels.get("l1"))}
L2: {_fmt(gamma_delta_levels.get("l2"))}
L3: {_fmt(gamma_delta_levels.get("l3"))}
L4: {_fmt(gamma_delta_levels.get("l4"))}

Delta Magnets:
D1: {_fmt(gamma_delta_levels.get("delta_1"))}
D2: {_fmt(gamma_delta_levels.get("delta_2"))}
D3: {_fmt(gamma_delta_levels.get("delta_3"))}
D4: {_fmt(gamma_delta_levels.get("delta_4"))}

==============================
TR3NDY LEVELS
==============================
Daily Supply: {_fmt(daily.get("supply"))}
Daily Mid: {_fmt(daily.get("mid"))}
Daily Demand: {_fmt(daily.get("demand"))}

Weekly Supply: {_fmt(weekly.get("supply"))}
Weekly Mid: {_fmt(weekly.get("mid"))}
Weekly Demand: {_fmt(weekly.get("demand"))}

==============================
TRADE PLAN
==============================
Direction: {trade_plan.get("direction", "—")}
Entry: {_fmt(trade_plan.get("entry"))}
Stop: {_fmt(trade_plan.get("stop"))}
Target 1: {_fmt(trade_plan.get("target_1"))}
Target 2: {_fmt(trade_plan.get("target_2"))}
R/R: {_fmt(trade_plan.get("rr"))}

Risk Note:
{trade_plan.get("risk_note", "—")}

==============================
PLAYBOOK READ
==============================
Positive Gamma = fade extremes / expect chop.
Negative Gamma = respect trend / expansion risk.
Zero Gamma = regime pivot.
Call Wall = likely resistance / hedge zone.
Put Wall = likely support / hedge zone.
Vol Trigger = possible acceleration level.
Magnet = possible pin / attraction zone.
""".strip()

    return snapshot