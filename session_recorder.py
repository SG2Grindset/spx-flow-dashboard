# ============================================================
# session_recorder.py
# Symbol-specific session history recorder
# Prevents SPY / SPX / XSP / QQQ / IWM / TSLA histories mixing
# ============================================================

import os
import pandas as pd
from datetime import datetime


SESSION_DIR = "session_history"


def ensure_session_dir():
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)


def clean_symbol(symbol):
    return str(symbol).upper().replace("/", "").replace(":", "").replace(" ", "_")


def get_session_file(symbol):
    ensure_session_dir()
    safe_symbol = clean_symbol(symbol)
    return os.path.join(SESSION_DIR, f"session_history_{safe_symbol}.csv")


def append_session_snapshot(
    symbol,
    spot,
    call_premium,
    put_premium,
    net_premium,
    net_dex=0,
    net_gex=0,
):
    session_file = get_session_file(symbol)

    now = datetime.now()

    new_row = {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.strftime("%H:%M:%S"),
        "symbol": clean_symbol(symbol),
        "spot": float(spot) if spot is not None else 0,
        "call_premium": float(call_premium) if call_premium is not None else 0,
        "put_premium": float(put_premium) if put_premium is not None else 0,
        "net_premium": float(net_premium) if net_premium is not None else 0,
        "net_dex": float(net_dex) if net_dex is not None else 0,
        "net_gex": float(net_gex) if net_gex is not None else 0,
    }

    if os.path.exists(session_file):
        try:
            df = pd.read_csv(session_file)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    df = pd.concat(
        [df, pd.DataFrame([new_row])],
        ignore_index=True
    )

    df.to_csv(session_file, index=False)

    return df


def load_session(symbol):
    session_file = get_session_file(symbol)

    if not os.path.exists(session_file):
        return pd.DataFrame(
            columns=[
                "datetime",
                "time",
                "symbol",
                "spot",
                "call_premium",
                "put_premium",
                "net_premium",
                "net_dex",
                "net_gex",
            ]
        )

    try:
        df = pd.read_csv(session_file)
    except Exception:
        return pd.DataFrame()

    if "symbol" in df.columns:
        df = df[df["symbol"].astype(str).str.upper() == clean_symbol(symbol)]

    return df


def reset_session(symbol):
    session_file = get_session_file(symbol)

    if os.path.exists(session_file):
        os.remove(session_file)

    return True


def reset_all_sessions():
    ensure_session_dir()

    for filename in os.listdir(SESSION_DIR):
        if filename.startswith("session_history_") and filename.endswith(".csv"):
            os.remove(os.path.join(SESSION_DIR, filename))

    return True