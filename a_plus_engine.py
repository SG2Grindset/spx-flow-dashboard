# ============================================================
# a_plus_engine.py
# High-Conviction A+ Trade Scoring Engine
# ============================================================

def compute_a_plus_score(flow_result, gamma_bias, spot_price, oi_levels):
    score = 0
    reasons = []
    warnings = []

    upside_score = flow_result.get("upside_score", 0)
    downside_score = flow_result.get("downside_score", 0)
    net_score = flow_result.get("net_score", 0)

    gamma_net_oi = gamma_bias.get("net_oi", 0)

    summary = flow_result.get("summary", {})
    call_premium = summary.get("call_premium", 0)
    put_premium = summary.get("put_premium", 0)
    net_premium = summary.get("net_premium", 0)

    top_call_strike = summary.get("top_call_strike")
    top_put_strike = summary.get("top_put_strike")

    spot_price = float(spot_price)

    # ========================================================
    # FLOW DIRECTION
    # ========================================================

    bullish_flow = (
        upside_score >= 70
        and net_score >= 25
        and call_premium > put_premium * 1.25
        and net_premium > 0
    )

    bearish_flow = (
        downside_score >= 70
        and net_score <= -25
        and put_premium > call_premium * 1.25
        and net_premium < 0
    )

    if bullish_flow:
        score += 3
        reasons.append("High-conviction bullish flow")

    elif bearish_flow:
        score -= 3
        reasons.append("High-conviction bearish flow")

    else:
        warnings.append("Flow is not strong enough for A+")
        if net_score > 0:
            score += 1
            reasons.append("Mild bullish flow")
        elif net_score < 0:
            score -= 1
            reasons.append("Mild bearish flow")

    # ========================================================
    # GAMMA / OI ALIGNMENT
    # ========================================================

    bullish_gamma = gamma_net_oi > 0
    bearish_gamma = gamma_net_oi < 0

    if bullish_flow and bullish_gamma:
        score += 2
        reasons.append("Gamma/OI confirms bullish side")

    elif bearish_flow and bearish_gamma:
        score -= 2
        reasons.append("Gamma/OI confirms bearish side")

    elif bullish_flow and bearish_gamma:
        warnings.append("Bullish flow but put OI dominates")
        score -= 1

    elif bearish_flow and bullish_gamma:
        warnings.append("Bearish flow but call OI dominates")
        score += 1

    # ========================================================
    # TARGET STRUCTURE / MAGNET LOGIC
    # ========================================================

    top_oi = oi_levels.get("top_oi") if oi_levels else None
    top_oi_strike = None

    if top_oi is not None and not top_oi.empty:
        top_oi_strike = float(top_oi.index[0])

        if bullish_flow:
            if top_oi_strike >= spot_price:
                score += 1
                reasons.append(f"Major OI magnet above/at spot: {top_oi_strike}")
            else:
                warnings.append(f"Major OI magnet below spot: {top_oi_strike}")

        if bearish_flow:
            if top_oi_strike <= spot_price:
                score -= 1
                reasons.append(f"Major OI magnet below/at spot: {top_oi_strike}")
            else:
                warnings.append(f"Major OI magnet above spot: {top_oi_strike}")

    # ========================================================
    # STRIKE LOCATION FILTER
    # ========================================================

    if bullish_flow and top_call_strike is not None:
        if top_call_strike >= spot_price:
            score += 1
            reasons.append(f"Top call strike above/at spot: {top_call_strike}")
        else:
            warnings.append(f"Top call strike below spot: {top_call_strike}")

    if bearish_flow and top_put_strike is not None:
        if top_put_strike <= spot_price:
            score -= 1
            reasons.append(f"Top put strike below/at spot: {top_put_strike}")
        else:
            warnings.append(f"Top put strike above spot: {top_put_strike}")

    # ========================================================
    # FINAL HIGH-CONVICTION CLASSIFICATION
    # ========================================================

    if score >= 6 and bullish_flow:
        grade = "A+ LONG"
        fire_alert = True

    elif score <= -6 and bearish_flow:
        grade = "A+ SHORT"
        fire_alert = True

    elif score >= 3:
        grade = "B LONG"
        fire_alert = False

    elif score <= -3:
        grade = "B SHORT"
        fire_alert = False

    else:
        grade = "NEUTRAL"
        fire_alert = False

    return {
        "score": score,
        "grade": grade,
        "fire_alert": fire_alert,
        "reasons": reasons,
        "warnings": warnings,
        "bullish_flow": bullish_flow,
        "bearish_flow": bearish_flow,
        "top_oi_strike": top_oi_strike,
    }