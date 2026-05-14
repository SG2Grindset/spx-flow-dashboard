# ============================================================
# intraday_gamma_engine.py
# Tracks opening gamma vs current gamma
# ============================================================

import json
import os
from datetime import datetime


STATE_FILE = "gamma_state.json"


def load_gamma_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_gamma_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def update_intraday_gamma_state(levels):
    state = load_gamma_state()

    today = datetime.now().strftime("%Y-%m-%d")

    current = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "net_gex": levels.get("net_gex"),
        "call_wall": levels.get("call_wall"),
        "put_wall": levels.get("put_wall"),
        "zero_gamma": levels.get("zero_gamma"),
        "vol_trigger": levels.get("vol_trigger"),
    }

    if today not in state:
        state[today] = {
            "open": current,
            "latest": current
        }
    else:
        state[today]["latest"] = current

    save_gamma_state(state)

    return state[today]


def build_intraday_gamma_report(day_state):

    if not day_state:
        return {
            "error": "No intraday gamma state available."
        }

    open_data = day_state.get("open", {})
    latest = day_state.get("latest", {})

    try:
        gex_shift = (
            float(latest.get("net_gex", 0))
            - float(open_data.get("net_gex", 0))
        )
    except Exception:
        gex_shift = 0

    return {
        "open_gex": open_data.get("net_gex"),
        "current_gex": latest.get("net_gex"),
        "gex_shift": gex_shift,

        "open_call_wall": open_data.get("call_wall"),
        "current_call_wall": latest.get("call_wall"),

        "open_put_wall": open_data.get("put_wall"),
        "current_put_wall": latest.get("put_wall"),

        "open_zero_gamma": open_data.get("zero_gamma"),
        "current_zero_gamma": latest.get("zero_gamma"),

        "open_vol_trigger": open_data.get("vol_trigger"),
        "current_vol_trigger": latest.get("vol_trigger"),
    }