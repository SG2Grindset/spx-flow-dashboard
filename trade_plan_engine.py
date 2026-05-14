# ============================================================
# trade_plan_engine.py
# Entry / Stop / Target Plan from Signal + Tr3ndy Levels
# ============================================================

def build_trade_plan(symbol, spot_price, a_plus, flow_result, trendy_edges):
    spot = float(spot_price)
    grade = a_plus.get("grade", "NEUTRAL")

    daily = trendy_edges.get("daily", {})
    weekly = trendy_edges.get("weekly", {})

    daily_supply = daily.get("supply")
    daily_mid = daily.get("mid")
    daily_demand = daily.get("demand")

    weekly_supply = weekly.get("supply")
    weekly_mid = weekly.get("mid")
    weekly_demand = weekly.get("demand")

    plan = {
        "symbol": symbol,
        "bias": grade,
        "entry": None,
        "stop": None,
        "target_1": None,
        "target_2": None,
        "risk_note": "No valid trade plan.",
        "reason": []
    }

    # -----------------------------
    # LONG PLAN
    # -----------------------------
    if "LONG" in grade:
        plan["entry"] = spot

        # Stop: nearest demand/mid below spot
        downside_levels = [
            x for x in [daily_mid, daily_demand, weekly_mid, weekly_demand]
            if x is not None and x < spot
        ]

        upside_levels = [
            x for x in [daily_supply, weekly_supply]
            if x is not None and x > spot
        ]

        plan["stop"] = max(downside_levels) if downside_levels else spot * 0.995
        plan["target_1"] = min(upside_levels) if upside_levels else spot * 1.005
        plan["target_2"] = max(upside_levels) if len(upside_levels) > 1 else spot * 1.01

        plan["reason"].append("Long bias from flow/gamma engine.")
        plan["reason"].append("Stop placed below nearest Tr3ndy support/demand.")
        plan["reason"].append("Targets use nearest Daily/Weekly supply above spot.")

    # -----------------------------
    # SHORT PLAN
    # -----------------------------
    elif "SHORT" in grade:
        plan["entry"] = spot

        # Stop: nearest supply/mid above spot
        upside_levels = [
            x for x in [daily_mid, daily_supply, weekly_mid, weekly_supply]
            if x is not None and x > spot
        ]

        downside_levels = [
            x for x in [daily_demand, weekly_demand]
            if x is not None and x < spot
        ]

        plan["stop"] = min(upside_levels) if upside_levels else spot * 1.005
        plan["target_1"] = max(downside_levels) if downside_levels else spot * 0.995
        plan["target_2"] = min(downside_levels) if len(downside_levels) > 1 else spot * 0.99

        plan["reason"].append("Short bias from flow/gamma engine.")
        plan["reason"].append("Stop placed above nearest Tr3ndy resistance/supply.")
        plan["reason"].append("Targets use nearest Daily/Weekly demand below spot.")

    # -----------------------------
    # Risk / Reward
    # -----------------------------
    if plan["entry"] and plan["stop"] and plan["target_1"]:
        risk = abs(plan["entry"] - plan["stop"])
        reward = abs(plan["target_1"] - plan["entry"])

        rr = reward / risk if risk > 0 else 0

        plan["risk"] = risk
        plan["reward"] = reward
        plan["rr"] = rr

        if rr >= 2:
            plan["risk_note"] = "Strong R/R setup."
        elif rr >= 1:
            plan["risk_note"] = "Acceptable R/R setup."
        else:
            plan["risk_note"] = "Weak R/R — consider waiting."

    return plan


def format_trade_plan(plan):
    if not plan or plan.get("entry") is None:
        return "Trade Plan: No valid setup."

    return f"""
Trade Plan - {plan["symbol"]}

Bias: {plan["bias"]}
Entry Area: {plan["entry"]:.2f}
Stop Area: {plan["stop"]:.2f}
Target 1: {plan["target_1"]:.2f}
Target 2: {plan["target_2"]:.2f}

Risk: {plan.get("risk", 0):.2f}
Reward to T1: {plan.get("reward", 0):.2f}
R/R: {plan.get("rr", 0):.2f}

Note: {plan["risk_note"]}
""".strip()