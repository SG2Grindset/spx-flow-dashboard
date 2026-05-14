# ============================================================
# run_alerts.py
# Headless alert runner (no Streamlit UI)
# ============================================================

from flow_engine import get_spx_flow_data
from flow_scoring import score_options_flow
from gamma_engine import get_oi_levels, get_gamma_bias
from a_plus_engine import compute_a_plus_score
from trendy_edges_engine import get_trendy_edges
from trade_plan_engine import build_trade_plan, format_trade_plan
from alerts import send_discord_alert


def main():
    data = get_spx_flow_data(width=10)

    symbol = data["symbol"]
    spot_price = data["spot_price"]
    expiration = data["expiration"]
    chain_df = data["chain_df"]

    flow_result = score_options_flow(
        df=chain_df,
        spot_price=spot_price,
        near_money_width=10,
        atm_width=10,
        min_volume=1
    )

    oi_levels = get_oi_levels(chain_df)
    gamma_bias = get_gamma_bias(chain_df, spot_price)

    a_plus = compute_a_plus_score(
        flow_result=flow_result,
        gamma_bias=gamma_bias,
        spot_price=spot_price,
        oi_levels=oi_levels
    )

    trendy_edges = get_trendy_edges(symbol)

    trade_plan = build_trade_plan(
        symbol=symbol,
        spot_price=spot_price,
        a_plus=a_plus,
        flow_result=flow_result,
        trendy_edges=trendy_edges
    )

    grade = a_plus.get("grade", "NEUTRAL")

    if "A+" not in grade:
        print("No A+ setup. No alert sent.")
        return

    message = f"""
🚨 PRE-MARKET ALERT 🚨

Symbol: {symbol}
Price: {spot_price:.2f}
Signal: {grade}

{format_trade_plan(trade_plan)}
"""

    ok, result = send_discord_alert(message)

    print(result)


if __name__ == "__main__":
    main()