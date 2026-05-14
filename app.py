# ============================================================
# app.py
# Options Flow Dashboard + Flow + Gamma + A+ + Tr3ndy
# + Trade Plan + Discord + Morning Snapshot
# + Intraday Gamma + Expected Move
# ============================================================

import os
import time
import streamlit as st

from streamlit_autorefresh import st_autorefresh

from flow_engine import get_spx_flow_data
from flow_scoring import score_options_flow, format_flow_alert
from gamma_engine import get_oi_levels, get_gamma_bias

from gamma_level_engine import (
    build_gamma_delta_levels,
    format_gamma_delta_levels,
    build_gamma_curve_chart,
    determine_gamma_regime
)

from intraday_gamma_engine import (
    update_intraday_gamma_state,
    build_intraday_gamma_report
)

from expected_move_engine import build_expected_move

from a_plus_engine import compute_a_plus_score
from alerts import send_discord_alert
from trendy_edges_engine import get_trendy_edges, format_trendy_edges
from chart_engine import build_trendy_levels_chart
from trade_plan_engine import build_trade_plan, format_trade_plan
from snapshot_engine import build_morning_snapshot


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_near_level(price, level, pct=0.002):
    try:
        if level is None:
            return False
        return abs(float(price) - float(level)) <= float(price) * pct
    except Exception:
        return False


def fmt(value):
    try:
        if value is None:
            return "—"
        return f"{float(value):,.2f}"
    except Exception:
        return "—"


def fmt_money(value):
    try:
        value = float(value)
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        if abs(value) >= 1_000:
            return f"${value / 1_000:.1f}K"
        return f"${value:,.0f}"
    except Exception:
        return "—"


# ============================================================
# PAGE SETTINGS
# ============================================================

st.set_page_config(
    page_title="Options Flow Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Options Flow Dashboard")
st.caption("Manual trade-decision support only — not auto-trading.")


# ============================================================
# SIDEBAR SETTINGS
# ============================================================

st.sidebar.header("Settings")

auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)

refresh_seconds = st.sidebar.selectbox(
    "Refresh Interval",
    options=[15, 30, 60, 120, 300],
    index=2
)

near_money_width = st.sidebar.slider(
    "Near-Money Strike Width",
    min_value=5,
    max_value=150,
    value=10,
    step=5
)

atm_width = st.sidebar.slider(
    "ATM Width",
    min_value=5,
    max_value=50,
    value=10,
    step=5
)

min_volume = st.sidebar.slider(
    "Minimum Option Volume",
    min_value=0,
    max_value=100,
    value=1,
    step=1
)

send_discord = st.sidebar.checkbox("Send Discord Alerts", value=True)

alert_level = st.sidebar.selectbox(
    "Discord Alert Level",
    ["A+ Only", "A+ & B+", "All Signals"],
    index=0
)

if auto_refresh:
    st_autorefresh(
        interval=refresh_seconds * 1000,
        key="flow_refresh"
    )


# ============================================================
# LOAD DATA
# ============================================================

chain_df = None
spot_price = None
expiration = None
symbol = "SPY"

try:
    data = get_spx_flow_data(width=near_money_width)

    symbol = data.get("symbol", "SPY")
    spot_price = data["spot_price"]
    expiration = data["expiration"]
    chain_df = data["chain_df"]

except Exception as e:
    st.error("Failed to load options flow data.")
    st.exception(e)

if chain_df is None or chain_df.empty:
    st.warning("No option chain data returned.")
    st.stop()


# ============================================================
# SCORE FLOW + GAMMA + A+ + TR3NDY + TRADE PLAN
# ============================================================

try:
    flow_result = score_options_flow(
        df=chain_df,
        spot_price=spot_price,
        near_money_width=near_money_width,
        atm_width=atm_width,
        min_volume=min_volume
    )

    oi_levels = get_oi_levels(chain_df)
    gamma_bias = get_gamma_bias(chain_df, spot_price)

    gamma_delta_result = build_gamma_delta_levels(chain_df, spot_price)
    gamma_delta_text = format_gamma_delta_levels(gamma_delta_result)
    gamma_delta_levels = gamma_delta_result.get("levels", {})
    gamma_delta_detail = gamma_delta_result.get("detail")

    gamma_regime = determine_gamma_regime(gamma_delta_levels)

    expected_move = build_expected_move(
        chain_df,
        spot_price
    )

    intraday_state = update_intraday_gamma_state(
        gamma_delta_levels
    )

    intraday_gamma = build_intraday_gamma_report(
        intraday_state
    )

    a_plus = compute_a_plus_score(
        flow_result=flow_result,
        gamma_bias=gamma_bias,
        spot_price=spot_price,
        oi_levels=oi_levels
    )

    trendy_edges = get_trendy_edges(symbol)
    trendy_text = format_trendy_edges(trendy_edges)

    trendy_chart = build_trendy_levels_chart(
        symbol=symbol,
        spot_price=spot_price,
        trendy_edges=trendy_edges,
        gamma_levels=gamma_delta_levels,
        expected_move=expected_move
    )

    trade_plan = build_trade_plan(
        symbol=symbol,
        spot_price=spot_price,
        a_plus=a_plus,
        flow_result=flow_result,
        trendy_edges=trendy_edges
    )

    trade_plan_text = format_trade_plan(trade_plan)

    morning_snapshot = build_morning_snapshot(
        symbol=symbol,
        spot_price=spot_price,
        expiration=expiration,
        flow_result=flow_result,
        gamma_delta_levels=gamma_delta_levels,
        gamma_regime=gamma_regime,
        trendy_edges=trendy_edges,
        trade_plan=trade_plan,
        a_plus=a_plus,
    )

except Exception as e:
    st.error("Scoring / Gamma / Tr3ndy / Trade Plan error.")
    st.exception(e)
    st.stop()


# ============================================================
# COMPACT TRADER COCKPIT
# ============================================================

summary = flow_result.get("summary", {})

top_call = summary.get("top_call_strike")
top_put = summary.get("top_put_strike")

near_call_target = is_near_level(spot_price, top_call)
near_put_target = is_near_level(spot_price, top_put)

daily = trendy_edges.get("daily", {})
weekly = trendy_edges.get("weekly", {})

near_demand = (
    is_near_level(spot_price, daily.get("demand"))
    or is_near_level(spot_price, weekly.get("demand"))
)

near_supply = (
    is_near_level(spot_price, daily.get("supply"))
    or is_near_level(spot_price, weekly.get("supply"))
)

call_premium = summary.get("call_premium", 0)
put_premium = summary.get("put_premium", 0)
net_premium = summary.get("net_premium", 0)

st.subheader("⚡ Trader Cockpit")

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric(f"{symbol}", fmt(spot_price))
c2.metric("Signal", a_plus.get("grade", "NEUTRAL"))
c3.metric("Score", a_plus.get("score", 0))
c4.metric("Flow Bias", flow_result.get("bias", "NEUTRAL"))
c5.metric("Top Call Target", fmt(top_call))
c6.metric("Top Put Target", fmt(top_put))

c1, c2, c3, c4, c5, c6 = st.columns(6)

c1.metric("Net Premium", fmt_money(net_premium))
c2.metric("Call Prem", fmt_money(call_premium))
c3.metric("Put Prem", fmt_money(put_premium))
c4.metric("Entry", fmt(trade_plan.get("entry")))
c5.metric("Stop", fmt(trade_plan.get("stop")))
c6.metric("Target 1", fmt(trade_plan.get("target_1")))


# ============================================================
# MORNING GAMMA / DELTA LEVELS
# ============================================================

st.write("### 🧠 Morning Gamma / Delta Levels")

if gamma_delta_result.get("error"):
    st.warning(gamma_delta_result.get("error"))
else:
    g1, g2, g3, g4, g5 = st.columns(5)

    g1.metric("Call Wall", fmt(gamma_delta_levels.get("call_wall")))
    g2.metric("Put Wall", fmt(gamma_delta_levels.get("put_wall")))
    g3.metric("Zero Gamma", fmt(gamma_delta_levels.get("zero_gamma")))
    g4.metric("Vol Trigger", fmt(gamma_delta_levels.get("vol_trigger")))
    g5.metric("Magnet", fmt(gamma_delta_levels.get("magnet")))

    g1, g2, g3, g4 = st.columns(4)

    g1.metric("C1", fmt(gamma_delta_levels.get("c1")))
    g2.metric("C2", fmt(gamma_delta_levels.get("c2")))
    g3.metric("L1", fmt(gamma_delta_levels.get("l1")))
    g4.metric("L2", fmt(gamma_delta_levels.get("l2")))


# ============================================================
# DEALER GAMMA REGIME
# ============================================================

st.write("### 🌐 Dealer Gamma Regime")

r1, r2, r3 = st.columns(3)

r1.metric("Gamma Regime", gamma_regime.get("regime"))
r2.metric("Expected Behavior", gamma_regime.get("behavior"))
r3.metric("Net GEX", fmt_money(gamma_regime.get("net_gex")))

st.info(gamma_regime.get("bias"))

if gamma_regime.get("odte_note"):
    st.caption(gamma_regime.get("odte_note"))


# ============================================================
# INTRADAY GAMMA SHIFT
# ============================================================

st.write("### 🔄 Intraday Gamma Shift")

i1, i2, i3 = st.columns(3)

i1.metric("Open GEX", fmt_money(intraday_gamma.get("open_gex")))
i2.metric("Current GEX", fmt_money(intraday_gamma.get("current_gex")))
i3.metric("GEX Shift", fmt_money(intraday_gamma.get("gex_shift")))

i1, i2 = st.columns(2)

i1.metric(
    "Call Wall Shift",
    f'{fmt(intraday_gamma.get("open_call_wall"))} → {fmt(intraday_gamma.get("current_call_wall"))}'
)

i2.metric(
    "Put Wall Shift",
    f'{fmt(intraday_gamma.get("open_put_wall"))} → {fmt(intraday_gamma.get("current_put_wall"))}'
)

i1, i2 = st.columns(2)

i1.metric(
    "Zero Gamma Shift",
    f'{fmt(intraday_gamma.get("open_zero_gamma"))} → {fmt(intraday_gamma.get("current_zero_gamma"))}'
)

i2.metric(
    "Vol Trigger Shift",
    f'{fmt(intraday_gamma.get("open_vol_trigger"))} → {fmt(intraday_gamma.get("current_vol_trigger"))}'
)

gex_shift = intraday_gamma.get("gex_shift", 0)

try:
    gex_shift = float(gex_shift)
except Exception:
    gex_shift = 0

if gex_shift > 5_000_000:
    st.success(
        "Dealers are adding positive gamma intraday. "
        "Pinning / mean reversion strengthening."
    )

elif gex_shift < -5_000_000:
    st.error(
        "Dealers are becoming more short gamma intraday. "
        "Trend / expansion risk increasing."
    )

else:
    st.info("No major intraday gamma regime shift detected.")


# ============================================================
# EXPECTED MOVE
# ============================================================

st.write("### 📦 Expected Move")

if expected_move.get("error"):
    st.warning(expected_move.get("error"))

else:
    e1, e2, e3, e4 = st.columns(4)

    e1.metric("ATM Strike", fmt(expected_move.get("atm_strike")))
    e2.metric("Expected Move", fmt(expected_move.get("expected_move")))
    e3.metric("Upper Expected", fmt(expected_move.get("upper")))
    e4.metric("Lower Expected", fmt(expected_move.get("lower")))

    st.caption(
        f'Expected Move %: {expected_move.get("expected_move_pct", 0):.2f}%'
    )

    cw = gamma_delta_levels.get("call_wall")
    pw = gamma_delta_levels.get("put_wall")

    upper_em = expected_move.get("upper")
    lower_em = expected_move.get("lower")

    try:
        if (
            cw is not None
            and upper_em is not None
            and float(cw) > float(upper_em)
        ):
            st.success(
                "Call Wall sits ABOVE expected move. "
                "Upside dealer resistance may be harder to reach."
            )

        if (
            pw is not None
            and lower_em is not None
            and float(pw) < float(lower_em)
        ):
            st.success(
                "Put Wall sits BELOW expected move. "
                "Downside dealer support may contain movement."
            )

        if (
            cw is not None
            and upper_em is not None
            and abs(float(cw) - float(upper_em)) < 5
        ):
            st.warning(
                "Call Wall aligns closely with Expected Move HIGH."
            )

        if (
            pw is not None
            and lower_em is not None
            and abs(float(pw) - float(lower_em)) < 5
        ):
            st.warning(
                "Put Wall aligns closely with Expected Move LOW."
            )

    except Exception:
        pass


# ============================================================
# GAMMA CURVE CHART
# ============================================================

gamma_curve_chart = build_gamma_curve_chart(
    gamma_delta_result,
    spot_price
)

if gamma_curve_chart is not None:
    st.write("### 📈 Gamma Curve")
    st.plotly_chart(gamma_curve_chart, use_container_width=True)


# ============================================================
# COMPACT REASONS / RISK
# ============================================================

left, right = st.columns([1, 1])

with left:
    st.write("**Why:**")
    if a_plus.get("reasons"):
        for reason in a_plus["reasons"][:3]:
            st.write(f"• {reason}")
    else:
        st.write("No strong reasons yet.")

with right:
    st.write("**Risk Plan:**")
    st.write(f"R/R: **{fmt(trade_plan.get('rr'))}**")
    st.write(trade_plan.get("risk_note", "No risk note."))

    if a_plus.get("warnings"):
        for warning in a_plus["warnings"][:2]:
            st.write(f"⚠️ {warning}")


# ============================================================
# TR3NDY CHART + LEVELS
# ============================================================

st.subheader("📐 Key Levels")

daily_edges = trendy_edges.get("daily", {})
weekly_edges = trendy_edges.get("weekly", {})

l1, l2, l3, l4, l5, l6 = st.columns(6)

l1.metric("D Supply", fmt(daily_edges.get("supply")))
l2.metric("D Mid", fmt(daily_edges.get("mid")))
l3.metric("D Demand", fmt(daily_edges.get("demand")))
l4.metric("W Supply", fmt(weekly_edges.get("supply")))
l5.metric("W Mid", fmt(weekly_edges.get("mid")))
l6.metric("W Demand", fmt(weekly_edges.get("demand")))

st.plotly_chart(trendy_chart, use_container_width=True)

st.write("### 📍 Location Check")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Near Call Target", "🟢 YES" if near_call_target else "🔴 NO")
col2.metric("Near Put Target", "🟢 YES" if near_put_target else "🔴 NO")
col3.metric("Near Demand", "🟢 YES" if near_demand else "🔴 NO")
col4.metric("Near Supply", "🟢 YES" if near_supply else "🔴 NO")


# ============================================================
# GREEN LIGHT ALIGNMENT CHECK
# ============================================================

current_grade = a_plus.get("grade", "NEUTRAL")

flow_aligned = a_plus.get("bullish_flow") or a_plus.get("bearish_flow")

gamma_aligned = (
    ("LONG" in current_grade and gamma_bias.get("net_oi", 0) > 0)
    or ("SHORT" in current_grade and gamma_bias.get("net_oi", 0) < 0)
)

location_aligned = (
    ("LONG" in current_grade and (near_demand or near_call_target))
    or ("SHORT" in current_grade and (near_supply or near_put_target))
)

all_three_aligned = flow_aligned and gamma_aligned and location_aligned

st.write("### ✅ Green Light Alignment")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Flow", "🟢 YES" if flow_aligned else "🔴 NO")
col2.metric("Gamma", "🟢 YES" if gamma_aligned else "🔴 NO")
col3.metric("Location", "🟢 YES" if location_aligned else "🔴 NO")
col4.metric("Green Light", "🟢 GO" if all_three_aligned else "🔴 WAIT")

if all_three_aligned:
    st.success("✅ GREEN LIGHT: Flow + Gamma + Location are aligned.")
else:
    st.warning("⏳ WAIT: Full alignment not confirmed yet.")


# ============================================================
# ALERT TIER LOGIC
# ============================================================

alert_tier = None

if current_grade in ["A+ LONG", "A+ SHORT"]:
    alert_tier = "A+"

elif current_grade in ["B+ LONG", "B+ SHORT"]:
    alert_tier = "B+"

elif current_grade in ["B LONG", "B SHORT"]:
    alert_tier = "B"

elif a_plus.get("bullish_flow") or a_plus.get("bearish_flow"):
    alert_tier = "WATCH"


send_it = False

if alert_level == "A+ Only":
    send_it = alert_tier == "A+"

elif alert_level == "A+ & B+":
    send_it = alert_tier in ["A+", "B+"]

elif alert_level == "All Signals":
    send_it = alert_tier in ["A+", "B+", "B", "WATCH"]


# ============================================================
# ALERT SYSTEM
# ============================================================

st.subheader("🔔 Alert Status")

if "last_alert_key" not in st.session_state:
    st.session_state.last_alert_key = None

if "last_alert_time" not in st.session_state:
    st.session_state.last_alert_time = 0

ALERT_COOLDOWN_SECONDS = 60

now = time.time()

alert_file = None

if current_grade == "A+ LONG":
    st.success("A+ LONG DETECTED 🚀")
    alert_file = "a_plus_long.mp3"

elif current_grade == "A+ SHORT":
    st.error("A+ SHORT DETECTED 🔻")
    alert_file = "a_plus_short.mp3"

elif current_grade in ["B+ LONG", "B+ SHORT"]:
    st.warning(f"{current_grade} setup ⚡")
    alert_file = "b_setup.mp3"

elif current_grade in ["B LONG", "B SHORT"]:
    st.warning(f"{current_grade} setup 👀")
    alert_file = "b_setup.mp3"

elif alert_tier == "WATCH":
    st.info("Watch setup forming 👀")

else:
    st.info("No high-quality setup")


alert_key = f"{symbol}_{current_grade}_{round(float(spot_price), 1)}_{expiration}"

should_alert = (
    send_it
    and alert_tier is not None
    and all_three_aligned
    and alert_key != st.session_state.last_alert_key
    and (now - st.session_state.last_alert_time) > ALERT_COOLDOWN_SECONDS
)


if should_alert:
    cockpit_text = f"""
📊 COCKPIT DATA — {symbol}

Spot: {fmt(spot_price)}
Signal: {a_plus.get("grade")}
Score: {a_plus.get("score")}
Flow Bias: {flow_result.get("bias")}
Net Score: {flow_result.get("net_score")}

Top Call Target: {fmt(top_call)}
Top Put Target: {fmt(top_put)}

Net Premium: {fmt_money(net_premium)}
Call Premium: {fmt_money(call_premium)}
Put Premium: {fmt_money(put_premium)}

Dealer Gamma Regime:
- Regime: {gamma_regime.get("regime")}
- Behavior: {gamma_regime.get("behavior")}
- Net GEX: {fmt_money(gamma_regime.get("net_gex"))}
- 0DTE Note: {gamma_regime.get("odte_note")}

Intraday Gamma:
- Open GEX: {fmt_money(intraday_gamma.get("open_gex"))}
- Current GEX: {fmt_money(intraday_gamma.get("current_gex"))}
- GEX Shift: {fmt_money(intraday_gamma.get("gex_shift"))}

Expected Move:
- ATM Strike: {fmt(expected_move.get("atm_strike"))}
- Expected Move: {fmt(expected_move.get("expected_move"))}
- Upper: {fmt(expected_move.get("upper"))}
- Lower: {fmt(expected_move.get("lower"))}

Location:
- Near Call Target: {"YES" if near_call_target else "NO"}
- Near Put Target: {"YES" if near_put_target else "NO"}
- Near Demand: {"YES" if near_demand else "NO"}
- Near Supply: {"YES" if near_supply else "NO"}

Green Light:
- Flow: {"YES" if flow_aligned else "NO"}
- Gamma: {"YES" if gamma_aligned else "NO"}
- Location: {"YES" if location_aligned else "NO"}
- Final: {"GO" if all_three_aligned else "WAIT"}
""".strip()

    base_message = (
        cockpit_text
        + "\n\n"
        + gamma_delta_text
        + "\n\n"
        + trendy_text
        + "\n\n"
        + trade_plan_text
    )

    if alert_tier == "A+":
        discord_message = f"🚨🚨 **{alert_tier} SIGNAL** 🚨🚨\n{base_message}"
    elif alert_tier == "B+":
        discord_message = f"⚡ **{alert_tier} SETUP** ⚡\n{base_message}"
    elif alert_tier == "B":
        discord_message = f"👀 **{alert_tier} WATCHLIST SETUP**\n{base_message}"
    else:
        discord_message = f"📡 **WATCH SIGNAL**\n{base_message}"

    if alert_file and os.path.exists(alert_file):
        with open(alert_file, "rb") as f:
            st.audio(f.read(), format="audio/mp3")

    if send_discord:
        ok, result = send_discord_alert(discord_message)

        if ok:
            st.success(f"Discord alert sent: {alert_tier}")
        else:
            st.warning(result)

    st.session_state.last_alert_key = alert_key
    st.session_state.last_alert_time = now

    st.write(f"🔊 Alert fired: {alert_tier}")


# ============================================================
# SIGNAL MESSAGE PREVIEW
# ============================================================

if alert_tier:
    st.write("### Signal Message Preview")
    st.code(
        format_flow_alert(flow_result, symbol=symbol)
        + "\n\n"
        + gamma_delta_text
        + "\n\n"
        + trendy_text
        + "\n\n"
        + trade_plan_text
    )


# ============================================================
# EXPANDERS
# ============================================================

with st.expander("🔥 Full Options Flow Bias"):
    st.write(flow_result.get("message", "No flow message available."))

    col1, col2, col3 = st.columns(3)

    col1.metric("Upside Score", f'{flow_result.get("upside_score", 0)}/100')
    col2.metric("Downside Score", f'{flow_result.get("downside_score", 0)}/100')
    col3.metric("Bias", flow_result.get("bias", "NEUTRAL"))


with st.expander("🧠 Gamma / OI Details"):
    col1, col2, col3 = st.columns(3)

    col1.metric("Gamma Bias", gamma_bias.get("bias", "N/A"))
    col2.metric("Call OI", f'{gamma_bias.get("call_oi", 0):,.0f}')
    col3.metric("Put OI", f'{gamma_bias.get("put_oi", 0):,.0f}')

    left, right = st.columns(2)

    with left:
        st.write("### Top Total OI")
        st.dataframe(oi_levels.get("top_oi"), use_container_width=True)

    with right:
        st.write("### Top Call OI")
        st.dataframe(oi_levels.get("top_calls"), use_container_width=True)

        st.write("### Top Put OI")
        st.dataframe(oi_levels.get("top_puts"), use_container_width=True)


with st.expander("🧠 Gamma / Delta Level Detail"):
    if gamma_delta_result.get("error"):
        st.warning(gamma_delta_result.get("error"))
    else:
        st.write(gamma_delta_text)

        if gamma_delta_detail is not None:
            st.dataframe(gamma_delta_detail, use_container_width=True)


with st.expander("🔄 Intraday Gamma Detail"):
    st.json(intraday_gamma)


with st.expander("📦 Expected Move Detail"):
    st.json(expected_move)


with st.expander("📝 Morning Snapshot Export"):
    st.code(morning_snapshot)

    st.download_button(
        label="Download Morning Snapshot",
        data=morning_snapshot,
        file_name=f"{symbol}_morning_snapshot.txt",
        mime="text/plain"
    )


with st.expander("📊 Raw Option Chain"):
    st.dataframe(chain_df, use_container_width=True)