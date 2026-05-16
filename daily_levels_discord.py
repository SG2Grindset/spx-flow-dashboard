# ============================================================
# daily_levels_discord.py
# Auto-sends multi-symbol daily gamma levels ThinkScript
# Symbols: SPY, SPX, XSP, QQQ, IWM, TSLA, AAPL
# Uses next 10 expirations by default
# Sends daily at 6:30 AM Central
# ============================================================

import os
import time
import json
import requests
import pandas as pd

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from gamma_level_engine import build_gamma_delta_levels

load_dotenv(dotenv_path=".env", override=True)

TRADIER_API_KEY = os.getenv("TRADIER_API_KEY")
TRADIER_BASE_URL = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1")

DISCORD_WEBHOOK_URL = os.getenv(
    "DAILY_LEVELS_DISCORD_WEBHOOK_URL",
    ""
)

CENTRAL_TZ = ZoneInfo("America/Chicago")
SEND_TIME_CT = dt_time(6, 30)

STATE_FILE = "daily_levels_send_state.json"
OUTPUT_FILE = "Custom_Daily_Gamma_Levels.ts"

EXPIRATION_COUNT = 5

SYMBOLS = ["SPY", "SPX", "XSP", "QQQ", "IWM", "TSLA", "AAPL"]

WIDTH_BY_SYMBOL = {
    "SPY": 150,
    "SPX": 750,
    "XSP": 75,
    "QQQ": 150,
    "IWM": 75,
    "TSLA": 75,
    "AAPL": 75
}

HEADERS = {
    "Authorization": f"Bearer {TRADIER_API_KEY}",
    "Accept": "application/json"
}


# ============================================================
# STATE
# ============================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def already_sent_today():
    state = load_state()
    today_key = datetime.now(CENTRAL_TZ).strftime("%Y-%m-%d")
    return state.get("last_sent_date") == today_key


def mark_sent_today():
    state = load_state()
    now_ct = datetime.now(CENTRAL_TZ)

    state["last_sent_date"] = now_ct.strftime("%Y-%m-%d")
    state["last_sent_time_ct"] = now_ct.strftime("%Y-%m-%d %H:%M:%S %Z")

    save_state(state)


def is_send_time_now():
    now_ct = datetime.now(CENTRAL_TZ)

    after_send_time = now_ct.time() >= SEND_TIME_CT
    weekday = now_ct.weekday() < 5

    return weekday and after_send_time and not already_sent_today(), now_ct


# ============================================================
# TRADIER HELPERS
# ============================================================

def tradier_get(endpoint, params=None):
    if not TRADIER_API_KEY:
        raise Exception("Missing TRADIER_API_KEY in .env file")

    url = f"{TRADIER_BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=25
    )

    if response.status_code != 200:
        raise Exception(
            f"Tradier API Error {response.status_code}: {response.text}"
        )

    return response.json()


def get_price(symbol):
    data = tradier_get(
        "markets/quotes",
        params={"symbols": symbol}
    )

    quote = data.get("quotes", {}).get("quote", {})

    if isinstance(quote, list):
        quote = quote[0] if quote else {}

    for field in ["last", "close", "prevclose", "bid", "ask"]:
        try:
            value = float(quote.get(field))
            if value > 0:
                return value
        except Exception:
            pass

    raise Exception(f"Could not get valid price for {symbol}. Quote: {quote}")


def get_expirations(symbol):
    data = tradier_get(
        "markets/options/expirations",
        params={
            "symbol": symbol,
            "includeAllRoots": "true",
            "strikes": "false"
        }
    )

    expirations_block = data.get("expirations")

    if expirations_block is None:
        raise Exception(f"No expirations returned for {symbol}: {data}")

    expirations = expirations_block.get("date", [])

    if isinstance(expirations, str):
        expirations = [expirations]

    if not expirations:
        raise Exception(f"Expiration list empty for {symbol}: {data}")

    return expirations


def flatten_greeks(df):
    if "greeks" not in df.columns:
        return df

    def get_greek(row, key):
        try:
            g = row.get("greeks", {})
            if isinstance(g, dict):
                return g.get(key)
        except Exception:
            return None
        return None

    greek_map = {
        "delta": "delta",
        "gamma": "gamma",
        "theta": "theta",
        "vega": "vega",
        "rho": "rho",
        "mid_iv": "iv",
        "smv_vol": "iv",
        "iv": "iv",
    }

    for source_key, target_col in greek_map.items():
        values = df.apply(lambda row: get_greek(row, source_key), axis=1)

        if target_col not in df.columns:
            df[target_col] = values
        else:
            df[target_col] = df[target_col].fillna(values)

    return df


def get_option_chain(symbol, expiration):
    data = tradier_get(
        "markets/options/chains",
        params={
            "symbol": symbol,
            "expiration": expiration,
            "greeks": "true"
        }
    )

    options_block = data.get("options")

    if not options_block:
        return pd.DataFrame()

    options = options_block.get("option", [])

    if isinstance(options, dict):
        options = [options]

    if not options:
        return pd.DataFrame()

    df = pd.DataFrame(options)
    df = df.loc[:, ~df.columns.duplicated()].copy()

    df = flatten_greeks(df)

    if "option_type" in df.columns:
        df["type"] = df["option_type"]
    elif "put_call" in df.columns:
        df["type"] = df["put_call"]
    elif "contract_type" in df.columns:
        df["type"] = df["contract_type"]
    elif "type" not in df.columns:
        raise Exception(
            f"No call/put column for {symbol}. Columns: {df.columns.tolist()}"
        )

    rename_map = {
        "last_price": "last",
        "trade_volume": "volume",
        "open_int": "open_interest",
        "oi": "open_interest",
        "expiration_date": "expiration",
        "exp_date": "expiration",
        "expiry": "expiration",
    }

    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    if "expiration" not in df.columns:
        df["expiration"] = expiration

    df["type"] = (
        df["type"]
        .astype(str)
        .str.lower()
        .str.strip()
        .replace({
            "calls": "call",
            "puts": "put",
            "c": "call",
            "p": "put"
        })
    )

    if "last" not in df.columns:
        if "bid" in df.columns and "ask" in df.columns:
            df["last"] = (
                pd.to_numeric(df["bid"], errors="coerce").fillna(0)
                + pd.to_numeric(df["ask"], errors="coerce").fillna(0)
            ) / 2
        else:
            df["last"] = 0

    if "open_interest" not in df.columns:
        df["open_interest"] = 0

    for col in [
        "strike",
        "last",
        "volume",
        "open_interest",
        "bid",
        "ask",
        "delta",
        "gamma",
        "theta",
        "vega",
        "rho",
        "iv",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(subset=["strike"])
    df = df[df["type"].isin(["call", "put"])]

    if df.empty:
        return pd.DataFrame()

    df["premium"] = df["last"] * df["volume"] * 100

    return df


def filter_near_money(df, spot, width):
    return df[
        (df["strike"] >= float(spot) - width)
        & (df["strike"] <= float(spot) + width)
    ].copy()


# ============================================================
# LEVEL ENGINE
# ============================================================

def get_levels_for_symbol(symbol):
    width = WIDTH_BY_SYMBOL.get(symbol, 150)

    print(f"Getting price for {symbol}...")
    spot = get_price(symbol)

    print(f"Getting expirations for {symbol}...")
    expirations = get_expirations(symbol)[:EXPIRATION_COUNT]

    chains = []

    for exp in expirations:
        print(f"Getting chain for {symbol} {exp}...")
        temp_chain = get_option_chain(symbol, exp)

        if temp_chain is not None and not temp_chain.empty:
            temp_chain["expiration"] = exp
            chains.append(temp_chain)

    if not chains:
        raise Exception(f"No option chains returned for {symbol}")

    chain = pd.concat(chains, ignore_index=True)

    chain = filter_near_money(chain, spot, width)

    if chain.empty:
        raise Exception(f"No near-money options after filter for {symbol}")

    result = build_gamma_delta_levels(chain, spot)
    levels = result.get("levels", {})

    return {
        "symbol": symbol,
        "spot": spot,
        "expirations": expirations,
        "expiration_count": len(expirations),
        "levels": levels
    }


def safe_level(levels, key):
    value = levels.get(key)

    try:
        if value is None:
            return "Double.NaN"
        return round(float(value), 2)
    except Exception:
        return "Double.NaN"


# ============================================================
# THINKSCRIPT BUILDER
# ============================================================

def build_symbol_value_block(symbol, data):
    levels = data["levels"]
    prefix = symbol.upper()

    return f"""
# {prefix} Values
def {prefix}_cw = {safe_level(levels, "call_wall")};
def {prefix}_c1 = {safe_level(levels, "c1")};
def {prefix}_c2 = {safe_level(levels, "c2")};
def {prefix}_c3 = {safe_level(levels, "c3")};
def {prefix}_c4 = {safe_level(levels, "c4")};
def {prefix}_l1 = {safe_level(levels, "l1")};
def {prefix}_l2 = {safe_level(levels, "l2")};
def {prefix}_l3 = {safe_level(levels, "l3")};
def {prefix}_l4 = {safe_level(levels, "l4")};
def {prefix}_pw = {safe_level(levels, "put_wall")};
def {prefix}_vt = {safe_level(levels, "vol_trigger")};
def {prefix}_zg = {safe_level(levels, "zero_gamma")};
""".strip()


def build_symbol_condition(symbol, first=False):
    prefix = symbol.upper()

    starter = "if" if first else "else if"

    return f"""
{starter} (GetSymbol() == "{symbol}") {{
    _cw = {prefix}_cw;
    _c1 = {prefix}_c1;
    _c2 = {prefix}_c2;
    _c3 = {prefix}_c3;
    _c4 = {prefix}_c4;
    _l1 = {prefix}_l1;
    _l2 = {prefix}_l2;
    _l3 = {prefix}_l3;
    _l4 = {prefix}_l4;
    _pw = {prefix}_pw;
    _vt = {prefix}_vt;
    _zg = {prefix}_zg;
}}
""".strip()


def build_thinkscript(all_data):
    now_ct = datetime.now(CENTRAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

    value_blocks = "\n\n".join(
        build_symbol_value_block(symbol, all_data[symbol])
        for symbol in SYMBOLS
        if symbol in all_data
    )

    conditions = "\n\n".join(
        build_symbol_condition(symbol, first=(i == 0))
        for i, symbol in enumerate([s for s in SYMBOLS if s in all_data])
    )

    script = f"""
############################################################################################################
# Custom Daily Gamma Levels
# Generated: {now_ct}
# Symbols: {", ".join([s for s in SYMBOLS if s in all_data])}
# Expirations Used: Next {EXPIRATION_COUNT}
############################################################################################################

input Labels_On_Top = yes;
input Some_Bubbles_Off = yes;
input All_Bubbles_Off = no;
input Line_Weight = 1;

def someOff = Some_Bubbles_Off or All_Bubbles_Off;

def isRollover = GetYYYYMMDD() != GetYYYYMMDD()[1];
def beforeStart = GetTime() < RegularTradingStart(GetYYYYMMDD());
def afterEnd = GetTime() > RegularTradingEnd(GetYYYYMMDD());
def firstBarOfDay = if (beforeStart[1] == 1 and beforeStart == 0) or
  (isRollover and beforeStart == 0) then 1 else 0;
def lastBarOfDay = if (afterEnd[-1] == 1 and afterEnd == 0) or
  (isRollover[-1] and firstBarOfDay[-1]) then 1 else 0;

def day = GetDay();
def lastDay = GetLastDay();
def isToday = day == lastDay;
def x = if (IsNaN(close[-1]) and !IsNaN(close), BarNumber(), x[1]);

############################################################################################################

def _cw;
def _c1;
def _c2;
def _c3;
def _c4;
def _l1;
def _l2;
def _l3;
def _l4;
def _pw;
def _vt;
def _zg;

{value_blocks}

############################################################################################################

{conditions}

else {{
    _cw = Double.NaN;
    _c1 = Double.NaN;
    _c2 = Double.NaN;
    _c3 = Double.NaN;
    _c4 = Double.NaN;
    _l1 = Double.NaN;
    _l2 = Double.NaN;
    _l3 = Double.NaN;
    _l4 = Double.NaN;
    _pw = Double.NaN;
    _vt = Double.NaN;
    _zg = Double.NaN;
}}

plot CallWall = _cw;
plot ComboL1 = _c1;
plot ComboL2 = _c2;
plot ComboL3 = _c3;
plot ComboL4 = _c4;
plot L1 = _l1;
plot L2 = _l2;
plot L3 = _l3;
plot L4 = _l4;
plot PutWall = _pw;
plot VolTrig = _vt;
plot ZeroGamma = _zg;

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, ComboL1, "C1", Color.CYAN, no);
ComboL1.HideTitle();
ComboL1.SetLineWeight(Line_Weight);
ComboL1.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, ComboL2, "C2", Color.CYAN, no);
ComboL2.HideTitle();
ComboL2.SetLineWeight(Line_Weight);
ComboL2.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, ComboL3, "C3", Color.CYAN, no);
ComboL3.HideTitle();
ComboL3.SetLineWeight(Line_Weight);
ComboL3.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, ComboL4, "C4", Color.CYAN, no);
ComboL4.HideTitle();
ComboL4.SetLineWeight(Line_Weight);
ComboL4.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, L1, "L1", Color.GRAY, no);
L1.HideTitle();
L1.SetLineWeight(Line_Weight);
L1.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, L2, "L2", Color.GRAY, no);
L2.HideTitle();
L2.SetLineWeight(Line_Weight);
L2.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, L3, "L3", Color.GRAY, no);
L3.HideTitle();
L3.SetLineWeight(Line_Weight);
L3.SetDefaultColor(Color.RED);

AddChartBubble(!someOff and BarNumber() == HighestAll(x) + 15, L4, "L4", Color.GRAY, no);
L4.HideTitle();
L4.SetLineWeight(Line_Weight);
L4.SetDefaultColor(Color.RED);

AddChartBubble(!All_Bubbles_Off and BarNumber() == HighestAll(x) + 10, PutWall, "PW", Color.GREEN, Labels_On_Top);
PutWall.HideTitle();
PutWall.SetLineWeight(Line_Weight);
PutWall.SetDefaultColor(Color.RED);

AddChartBubble(!All_Bubbles_Off and BarNumber() == HighestAll(x) + 10, VolTrig, "VT", Color.LIGHT_ORANGE, Labels_On_Top);
VolTrig.HideTitle();
VolTrig.SetLineWeight(Line_Weight);
VolTrig.SetDefaultColor(Color.RED);

AddChartBubble(!All_Bubbles_Off and BarNumber() == HighestAll(x) + 10, CallWall, "CW", Color.LIGHT_RED, Labels_On_Top);
CallWall.HideTitle();
CallWall.SetLineWeight(Line_Weight);
CallWall.SetDefaultColor(Color.RED);

AddChartBubble(!All_Bubbles_Off and BarNumber() == HighestAll(x) + 10, ZeroGamma, "ZG", Color.WHITE, Labels_On_Top);
ZeroGamma.HideTitle();
ZeroGamma.SetLineWeight(Line_Weight);
ZeroGamma.SetDefaultColor(Color.RED);
""".strip()

    return script


# ============================================================
# DISCORD SEND
# ============================================================

def send_script_to_discord(script_text, all_data):
    if not DISCORD_WEBHOOK_URL:
        raise Exception(
            "Missing DAILY_LEVELS_DISCORD_WEBHOOK_URL in .env"
        )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(script_text)

    now_ct = datetime.now(CENTRAL_TZ)

    lines = [
        "🔥 **Custom Daily Gamma Levels**",
        "",
        f"Generated: {now_ct.strftime('%Y-%m-%d %I:%M:%S %p CT')}",
        f"Expirations Used: Next {EXPIRATION_COUNT}",
        "",
    ]

    for symbol in SYMBOLS:
        if symbol not in all_data:
            continue

        data = all_data[symbol]
        levels = data["levels"]

        lines.extend([
            f"**{symbol}**",
            f"Spot: {data['spot']:.2f}",
            f"Expirations: {', '.join(data['expirations'][:5])}"
            + (" ..." if len(data["expirations"]) > 5 else ""),
            f"CW: {levels.get('call_wall')}",
            f"PW: {levels.get('put_wall')}",
            f"ZG: {levels.get('zero_gamma')}",
            f"VT: {levels.get('vol_trigger')}",
            f"MAG: {levels.get('magnet')}",
            "",
        ])

    lines.append("ThinkScript attached below.")

    message = "\n".join(lines)

    with open(OUTPUT_FILE, "rb") as f:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data={"content": message},
            files={"file": (OUTPUT_FILE, f, "text/plain")},
            timeout=30
        )

    if response.status_code not in [200, 204]:
        raise Exception(
            f"Discord send failed: {response.status_code} {response.text}"
        )

    print("Sent daily levels script to Discord.")


# ============================================================
# RUN JOB
# ============================================================

def run_daily_levels_job():
    all_data = {}

    for symbol in SYMBOLS:
        try:
            print(f"Building {symbol} levels...")
            all_data[symbol] = get_levels_for_symbol(symbol)

        except Exception as e:
            print(f"Failed to build {symbol}:")
            print(e)

    if not all_data:
        raise Exception("No symbols successfully built.")

    print("Building ThinkScript...")
    script = build_thinkscript(all_data)

    print("Sending to Discord...")
    send_script_to_discord(
        script_text=script,
        all_data=all_data
    )

    mark_sent_today()


# ============================================================
# AUTO LOOP
# ============================================================

def auto_loop():
    print("Daily Levels Discord sender started.")
    print("Scheduled send time: 6:30 AM Central daily.")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Expirations Used: Next {EXPIRATION_COUNT}")

    while True:
        should_send, now_ct = is_send_time_now()

        if should_send:
            print(f"Send window reached: {now_ct.strftime('%Y-%m-%d %I:%M:%S %p CT')}")

            try:
                run_daily_levels_job()

            except Exception as e:
                print("Daily levels send failed:")
                print(e)

        else:
            print(
                f"Waiting... Current CT: {now_ct.strftime('%Y-%m-%d %I:%M:%S %p')} | "
                f"Already sent today: {already_sent_today()}"
            )

        time.sleep(60)


# ============================================================
# MAIN
# ============================================================

def main():
    mode = os.getenv("DAILY_LEVELS_MODE", "AUTO").upper().strip()

    if mode == "ONCE":
        run_daily_levels_job()
    else:
        auto_loop()


if __name__ == "__main__":
    main()
