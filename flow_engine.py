from dotenv import load_dotenv
import os
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

API_KEY = os.getenv("TRADIER_API_KEY")
BASE_URL = os.getenv("TRADIER_BASE_URL")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}


def get_spx_quote():
    response = requests.get(
        f"{BASE_URL}/markets/quotes",
        headers=HEADERS,
        params={"symbols": "SPX"}
    )
    response.raise_for_status()
    data = response.json()
    return data["quotes"]["quote"]["last"]


def get_spx_expirations():
    response = requests.get(
        f"{BASE_URL}/markets/options/expirations",
        headers=HEADERS,
        params={
            "symbol": "SPX",
            "includeAllRoots": "true"
        }
    )
    response.raise_for_status()
    data = response.json()

    expirations_block = data.get("expirations")
    if not expirations_block or not expirations_block.get("date"):
        return []

    return expirations_block["date"]


def get_next_spx_expiration():
    expirations = get_spx_expirations()
    if not expirations:
        raise ValueError("No SPX expirations returned from Tradier.")
    return expirations[0]


def get_spx_chain(expiration, greeks=False):
    response = requests.get(
        f"{BASE_URL}/markets/options/chains",
        headers=HEADERS,
        params={
            "symbol": "SPX",
            "expiration": expiration,
            "greeks": str(greeks).lower()
        }
    )
    response.raise_for_status()
    data = response.json()

    options_block = data.get("options")
    if not options_block or not options_block.get("option"):
        return []

    return options_block["option"]


def filter_near_money(options, spot, strike_range=50):
    filtered = []
    for contract in options:
        strike = contract.get("strike")
        if strike is None:
            continue
        if abs(strike - spot) <= strike_range:
            filtered.append(contract)
    return filtered


def filter_strike_window(options, spot, strikes_above=20, strikes_below=20):
    unique_strikes = sorted(
        {contract.get("strike") for contract in options if contract.get("strike") is not None}
    )

    if not unique_strikes:
        return []

    closest_index = min(
        range(len(unique_strikes)),
        key=lambda i: abs(unique_strikes[i] - spot)
    )

    start_index = max(0, closest_index - strikes_below)
    end_index = min(len(unique_strikes), closest_index + strikes_above + 1)

    selected_strikes = set(unique_strikes[start_index:end_index])

    filtered = [
        contract for contract in options
        if contract.get("strike") in selected_strikes
    ]

    return filtered


def get_near_money_spx_chain(
    expiration,
    strike_range=50,
    greeks=False,
    strikes_above=20,
    strikes_below=20
):
    spot = get_spx_quote()
    contracts = get_spx_chain(expiration, greeks=greeks)
    filtered = filter_strike_window(
        contracts,
        spot,
        strikes_above=strikes_above,
        strikes_below=strikes_below
    )
    return {
        "spot": spot,
        "contracts": filtered,
        "count": len(filtered)
    }


def summarize_premium_flow(contracts):
    call_premium = 0.0
    put_premium = 0.0

    for contract in contracts:
        option_type = contract.get("option_type")
        last = contract.get("last")
        volume = contract.get("volume")

        if last is None or volume is None:
            continue

        premium = float(last) * int(volume) * 100

        if option_type == "call":
            call_premium += premium
        elif option_type == "put":
            put_premium += premium

    net_premium = call_premium - put_premium

    return {
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_premium": net_premium
    }


def summarize_premium_by_strike(contracts):
    strike_map = {}

    for contract in contracts:
        strike = contract.get("strike")
        option_type = contract.get("option_type")
        last = contract.get("last")
        volume = contract.get("volume")

        if strike is None or last is None or volume is None:
            continue

        premium = float(last) * int(volume) * 100

        if strike not in strike_map:
            strike_map[strike] = {
                "call_premium": 0.0,
                "put_premium": 0.0,
                "total_premium": 0.0
            }

        if option_type == "call":
            strike_map[strike]["call_premium"] += premium
        elif option_type == "put":
            strike_map[strike]["put_premium"] += premium

        strike_map[strike]["total_premium"] += premium

    return strike_map


def summarize_gamma_by_strike(contracts):
    strike_map = {}

    for contract in contracts:
        strike = contract.get("strike")
        option_type = contract.get("option_type")
        open_interest = contract.get("open_interest")

        greeks = contract.get("greeks") or {}
        gamma = greeks.get("gamma")

        if strike is None or gamma is None or open_interest is None:
            continue

        gamma_exposure = float(gamma) * int(open_interest) * 100

        if strike not in strike_map:
            strike_map[strike] = {
                "call_gamma": 0.0,
                "put_gamma": 0.0,
                "total_gamma": 0.0
            }

        if option_type == "call":
            strike_map[strike]["call_gamma"] += gamma_exposure
        elif option_type == "put":
            strike_map[strike]["put_gamma"] += gamma_exposure

        strike_map[strike]["total_gamma"] += abs(gamma_exposure)

    return strike_map


def identify_key_levels(strike_summary):
    top_call = None
    top_put = None
    strongest_net = None

    max_call = 0
    max_put = 0
    max_net = 0

    for strike, data in strike_summary.items():
        call_prem = data["call_premium"]
        put_prem = data["put_premium"]
        net = call_prem - put_prem

        if call_prem > max_call:
            max_call = call_prem
            top_call = strike

        if put_prem > max_put:
            max_put = put_prem
            top_put = strike

        if abs(net) > max_net:
            max_net = abs(net)
            strongest_net = (strike, net)

    return {
        "top_call_strike": top_call,
        "top_put_strike": top_put,
        "strongest_net_strike": strongest_net
    }


def generate_trade_signal(spot, summary, levels):
    net = summary["net_premium"]

    top_call = levels["top_call_strike"]
    top_put = levels["top_put_strike"]
    net_strike, net_value = levels["strongest_net_strike"]

    if net > 0:
        bias = "BULLISH"
    elif net < 0:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    if bias == "BULLISH" and top_call is not None and spot > top_call:
        signal = "LONG"
    elif bias == "BEARISH" and top_put is not None and spot < top_put:
        signal = "SHORT"
    else:
        signal = "WAIT"

    return {
        "bias": bias,
        "signal": signal,
        "target": net_strike
    }