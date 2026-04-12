import time
from datetime import datetime

from flow_engine import (
    get_near_money_spx_chain,
    summarize_premium_flow,
    summarize_premium_by_strike,
    identify_key_levels,
    generate_trade_signal
)

EXPIRATION = "2026-04-13"
STRIKE_RANGE = 50
REFRESH_SECONDS = 30


def run_snapshot():
    result = get_near_money_spx_chain(
        expiration=EXPIRATION,
        strike_range=STRIKE_RANGE,
        greeks=False
    )

    summary = summarize_premium_flow(result["contracts"])
    strike_summary = summarize_premium_by_strike(result["contracts"])
    levels = identify_key_levels(strike_summary)
    signal = generate_trade_signal(
        spot=result["spot"],
        summary=summary,
        levels=levels
    )

    top_strikes = sorted(
        strike_summary.items(),
        key=lambda item: item[1]["total_premium"],
        reverse=True
    )[:5]

    print("\n" + "=" * 70)
    print("Snapshot time:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print(f"SPX spot: {result['spot']}")
    print(f"Near-money contracts: {result['count']}")
    print(f"Call premium: ${summary['call_premium']:,.2f}")
    print(f"Put premium:  ${summary['put_premium']:,.2f}")
    print(f"Net premium:  ${summary['net_premium']:,.2f}")

    print("\nKey Levels:")
    print(f"Top Call Strike: {levels['top_call_strike']}")
    print(f"Top Put Strike:  {levels['top_put_strike']}")

    strike, net = levels["strongest_net_strike"]
    direction = "CALLS" if net > 0 else "PUTS"
    print(f"Strongest Net Strike: {strike} ({direction} dominant)")

    print("\nTrade Signal:")
    print(f"Bias:   {signal['bias']}")
    print(f"Action: {signal['signal']}")
    print(f"Target: {signal['target']}")

    print("\nTop 5 strikes by total premium:")
    for strike, data in top_strikes:
        print(
            f"Strike {strike:.0f} | "
            f"Calls: ${data['call_premium']:,.2f} | "
            f"Puts: ${data['put_premium']:,.2f} | "
            f"Total: ${data['total_premium']:,.2f}"
        )


while True:
    try:
        run_snapshot()
    except Exception as e:
        print("\nERROR:", e)

    print(f"\nWaiting {REFRESH_SECONDS} seconds for next update...")
    time.sleep(REFRESH_SECONDS)