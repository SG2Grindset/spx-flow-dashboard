from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh

from flow_engine import (
    get_near_money_spx_chain,
    summarize_premium_flow,
    summarize_premium_by_strike,
    identify_key_levels,
    generate_trade_signal,
    get_next_spx_expiration,
)

st.set_page_config(page_title="SPX Flow Dashboard", layout="wide")

SPIKE_THRESHOLD = 5_000_000
PROXIMITY_THRESHOLD = 5
PRICE_VIEW_RANGE = 30
EXPIRATION = get_next_spx_expiration()

CHART_WINDOW_MINUTES = 60
BAR_INTERVAL = "3min"

# ---------------------------------------------------------
# VOLATILITY / STRIKE WIDTH SETTINGS
# ---------------------------------------------------------
MIN_STRIKES_EACH_SIDE = 3
MAX_STRIKES_EACH_SIDE = 8
ATR_LENGTH = 14
ATR_LOW_THRESHOLD = 18.0
ATR_HIGH_THRESHOLD = 35.0

st.title("SPX 0DTE Flow Dashboard")
st_autorefresh(interval=10000, key="flow_refresh")

if "prior_net_premium" not in st.session_state:
    st.session_state["prior_net_premium"] = None

if "flow_history" not in st.session_state:
    st.session_state["flow_history"] = []

if "spot_history" not in st.session_state:
    st.session_state["spot_history"] = []


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def fmt_dollars(value: float) -> str:
    return f"${float(value):,.2f}"


def fmt_number(value: float) -> str:
    return f"{float(value):,.2f}"


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(value, max_value))


def compute_intraday_atr(prices: list[float], length: int = 14) -> float:
    if len(prices) < 2:
        return 0.0

    true_ranges = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    if not true_ranges:
        return 0.0

    lookback = true_ranges[-length:]
    return sum(lookback) / len(lookback)


def determine_strike_span(atr_value: float) -> tuple[int, str]:
    if atr_value >= ATR_HIGH_THRESHOLD:
        score = 3
    elif atr_value >= ATR_LOW_THRESHOLD:
        score = 2
    elif atr_value > 0:
        score = 1
    else:
        score = 0

    strikes_each_side = clamp(
        MIN_STRIKES_EACH_SIDE + score,
        MIN_STRIKES_EACH_SIDE,
        MAX_STRIKES_EACH_SIDE
    )

    if strikes_each_side <= 3:
        regime = "Tight"
    elif strikes_each_side <= 5:
        regime = "Balanced"
    else:
        regime = "Wide"

    return strikes_each_side, regime


def pick_label_colors(call_value: float, put_value: float) -> tuple[str, str]:
    if call_value > put_value:
        return "#22c55e", "#ef4444"
    if put_value > call_value:
        return "#ef4444", "#22c55e"
    return "orange", "dodgerblue"


# ---------------------------------------------------------
# MARKET STATUS
# ---------------------------------------------------------
now = datetime.now(ZoneInfo("America/Chicago"))
current_time = now.time()
weekday = now.weekday()

is_weekday = weekday < 5

market_open = (
    is_weekday
    and current_time >= datetime.strptime("08:30", "%H:%M").time()
    and current_time <= datetime.strptime("15:00", "%H:%M").time()
)

market_status = "OPEN" if market_open else "CLOSED"

# ---------------------------------------------------------
# LIGHT SPOT SNAPSHOT FIRST (FOR ATR HISTORY)
# ---------------------------------------------------------
initial_result = get_near_money_spx_chain(
    expiration=EXPIRATION,
    greeks=True,
    strikes_above=MIN_STRIKES_EACH_SIDE,
    strikes_below=MIN_STRIKES_EACH_SIDE
)

current_spot = float(initial_result["spot"])

spot_history_row = {
    "timestamp": now.replace(tzinfo=None),
    "spot": current_spot,
}

existing_spot_history = st.session_state["spot_history"]
if not existing_spot_history or existing_spot_history[-1]["timestamp"] != spot_history_row["timestamp"]:
    existing_spot_history.append(spot_history_row)

st.session_state["spot_history"] = existing_spot_history[-300:]

spot_prices = [float(x["spot"]) for x in st.session_state["spot_history"]]
intraday_atr = compute_intraday_atr(spot_prices, ATR_LENGTH)

dynamic_strikes_each_side, volatility_regime = determine_strike_span(intraday_atr)

# ---------------------------------------------------------
# LOAD DATA WITH DYNAMIC STRIKE WIDTH
# ---------------------------------------------------------
result = get_near_money_spx_chain(
    expiration=EXPIRATION,
    greeks=True,
    strikes_above=dynamic_strikes_each_side,
    strikes_below=dynamic_strikes_each_side
)

summary = summarize_premium_flow(result["contracts"])
strike_summary = summarize_premium_by_strike(result["contracts"])
levels = identify_key_levels(strike_summary)

signal = generate_trade_signal(
    spot=result["spot"],
    summary=summary,
    levels=levels
)

# ---------------------------------------------------------
# FLOW ACCELERATION / SPIKE
# ---------------------------------------------------------
current_net = summary["net_premium"]
prior_net = st.session_state["prior_net_premium"]

if prior_net is None:
    net_change = 0.0
else:
    net_change = current_net - prior_net

st.session_state["prior_net_premium"] = current_net

if net_change > 0:
    acceleration_label = "BULLISH"
elif net_change < 0:
    acceleration_label = "BEARISH"
else:
    acceleration_label = "FLAT"

if net_change >= SPIKE_THRESHOLD:
    spike_label = "BULLISH SPIKE"
elif net_change <= -SPIKE_THRESHOLD:
    spike_label = "BEARISH SPIKE"
else:
    spike_label = "NO SPIKE"

# ---------------------------------------------------------
# PROXIMITY
# ---------------------------------------------------------
top_call_strike = levels["top_call_strike"]
top_put_strike = levels["top_put_strike"]
spot = float(result["spot"])

near_call_strike = abs(spot - top_call_strike) <= PROXIMITY_THRESHOLD
near_put_strike = abs(spot - top_put_strike) <= PROXIMITY_THRESHOLD

if near_call_strike and near_put_strike:
    proximity_label = "Near top call + put"
elif near_call_strike:
    proximity_label = f"Near call {fmt_number(top_call_strike)}"
elif near_put_strike:
    proximity_label = f"Near put {fmt_number(top_put_strike)}"
else:
    proximity_label = "Not near key strike"

# ---------------------------------------------------------
# STORE HISTORY FOR FLOW CHART
# ---------------------------------------------------------
history_row = {
    "timestamp": now.replace(tzinfo=None),
    "spx_price": float(result["spot"]),
    "call_premium": float(summary["call_premium"]),
    "put_premium": float(summary["put_premium"]),
    "net_premium": float(summary["net_premium"]),
}

existing_history = st.session_state["flow_history"]

if not existing_history or existing_history[-1]["timestamp"] != history_row["timestamp"]:
    existing_history.append(history_row)

st.session_state["flow_history"] = existing_history[-300:]

history_df = pd.DataFrame(st.session_state["flow_history"])

# ---------------------------------------------------------
# COMPACT HEADER
# ---------------------------------------------------------
st.caption(
    f"Updated: {now.strftime('%Y-%m-%d %H:%M:%S')} CT | "
    f"Exp: {EXPIRATION} | Market: {market_status}"
)

# ---------------------------------------------------------
# TOP SECTION: SUMMARY LEFT / FLOW CHART RIGHT
# ---------------------------------------------------------
top_left, top_right = st.columns([1, 1.6])

with top_left:
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    c5, c6 = st.columns(2)

    c1.metric("SPX", fmt_number(result["spot"]))
    c2.metric("Net Premium", fmt_dollars(summary["net_premium"]))
    c3.metric("Net Change", fmt_dollars(net_change))
    c4.metric("Bias", signal["bias"])
    c5.metric("Action", signal["signal"])
    c6.metric("Spike", spike_label)

    st.markdown(
        f"""
        <div style="
            margin-top:8px;
            padding:10px;
            border-radius:10px;
            background-color:#1f2937;
            color:white;
            font-size:14px;
        ">
            <b>Acceleration:</b> {acceleration_label}<br>
            <b>Proximity:</b> {proximity_label}<br>
            <b>Top Call:</b> {fmt_number(levels['top_call_strike'])} &nbsp; | &nbsp;
            <b>Top Put:</b> {fmt_number(levels['top_put_strike'])} &nbsp; | &nbsp;
            <b>Target:</b> {fmt_number(signal['target']) if isinstance(signal['target'], (int, float)) else signal['target']}<br>
            <b>Chart Window:</b> 1h &nbsp; | &nbsp;
            <b>Bar Size:</b> 3min<br>
            <b>ATR({ATR_LENGTH}):</b> {intraday_atr:,.2f} &nbsp; | &nbsp;
            <b>Strike Width:</b> {dynamic_strikes_each_side} above / {dynamic_strikes_each_side} below ({volatility_regime})
        </div>
        """,
        unsafe_allow_html=True
    )

with top_right:
    st.subheader(
        f"SPX Price vs Call / Put Buying (3min Bars | Last 1 Hour) | "
        f"Calls {fmt_dollars(summary['call_premium'])} | Puts {fmt_dollars(summary['put_premium'])}"
    )

    if not history_df.empty and len(history_df) >= 2:
        chart_df = history_df.copy()
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
        chart_df = chart_df.sort_values("timestamp")
        chart_df = chart_df.set_index("timestamp")

        chart_bars = (
            chart_df
            .resample(BAR_INTERVAL)
            .last()
            .ffill()
            .dropna()
            .reset_index()
        )

        if len(chart_bars) >= 2:
            latest_ts = chart_bars["timestamp"].max()
            cutoff = latest_ts - pd.Timedelta(minutes=CHART_WINDOW_MINUTES)
            chart_bars = chart_bars[chart_bars["timestamp"] >= cutoff]

            if len(chart_bars) >= 2:
                chart_bars["net_change"] = chart_bars["net_premium"].diff().fillna(0)

                bull_spikes = chart_bars[chart_bars["net_change"] >= SPIKE_THRESHOLD]
                bear_spikes = chart_bars[chart_bars["net_change"] <= -SPIKE_THRESHOLD]

                chart = make_subplots(specs=[[{"secondary_y": True}]])

                chart.add_trace(
                    go.Scatter(
                        x=chart_bars["timestamp"],
                        y=chart_bars["spx_price"],
                        mode="lines",
                        name="SPX Price",
                        line=dict(color="white", width=3),
                        connectgaps=True,
                    ),
                    secondary_y=False,
                )

                chart.add_trace(
                    go.Scatter(
                        x=chart_bars["timestamp"],
                        y=chart_bars["call_premium"],
                        mode="lines",
                        name="Calls",
                        line=dict(color="orange", width=3),
                        connectgaps=True,
                    ),
                    secondary_y=True,
                )

                chart.add_trace(
                    go.Scatter(
                        x=chart_bars["timestamp"],
                        y=chart_bars["put_premium"],
                        mode="lines",
                        name="Puts",
                        line=dict(color="dodgerblue", width=3),
                        connectgaps=True,
                    ),
                    secondary_y=True,
                )

                if not bull_spikes.empty:
                    chart.add_trace(
                        go.Scatter(
                            x=bull_spikes["timestamp"],
                            y=bull_spikes["call_premium"],
                            mode="markers+text",
                            name="Bull Spike",
                            marker=dict(color="lime", size=10),
                            text=["Bull"] * len(bull_spikes),
                            textposition="top center",
                            textfont=dict(color="lime", size=11),
                            connectgaps=True,
                        ),
                        secondary_y=True,
                    )

                if not bear_spikes.empty:
                    chart.add_trace(
                        go.Scatter(
                            x=bear_spikes["timestamp"],
                            y=bear_spikes["put_premium"],
                            mode="markers+text",
                            name="Bear Spike",
                            marker=dict(color="cyan", size=10),
                            text=["Bear"] * len(bear_spikes),
                            textposition="top center",
                            textfont=dict(color="cyan", size=11),
                            connectgaps=True,
                        ),
                        secondary_y=True,
                    )

                session_open = pd.Timestamp(now.date()) + pd.Timedelta(hours=8, minutes=30)
                chart.add_vline(
                    x=session_open,
                    line_width=1,
                    line_dash="dot",
                    line_color="gray",
                )

                latest_call = float(chart_bars["call_premium"].iloc[-1])
                latest_put = float(chart_bars["put_premium"].iloc[-1])
                latest_x = chart_bars["timestamp"].iloc[-1]

                call_label_color, put_label_color = pick_label_colors(latest_call, latest_put)

                chart.add_annotation(
                    x=latest_x,
                    y=latest_call,
                    xref="x",
                    yref="y2",
                    text=f"Calls: {fmt_dollars(latest_call)}",
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    xshift=40,
                    font=dict(color=call_label_color, size=12),
                    bgcolor="rgba(0,0,0,0.55)",
                    bordercolor=call_label_color,
                    borderwidth=1,
                )

                chart.add_annotation(
                    x=latest_x,
                    y=latest_put,
                    xref="x",
                    yref="y2",
                    text=f"Puts: {fmt_dollars(latest_put)}",
                    showarrow=False,
                    xanchor="left",
                    yanchor="middle",
                    xshift=40,
                    font=dict(color=put_label_color, size=12),
                    bgcolor="rgba(0,0,0,0.55)",
                    bordercolor=put_label_color,
                    borderwidth=1,
                )

                price_min = result["spot"] - PRICE_VIEW_RANGE
                price_max = result["spot"] + PRICE_VIEW_RANGE

                chart.update_layout(
                    height=420,
                    margin=dict(l=20, r=110, t=20, b=20),
                    paper_bgcolor="#0b1220",
                    plot_bgcolor="#0b1220",
                    font=dict(color="white"),
                    hovermode="x unified",
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="left",
                        x=0,
                    ),
                    xaxis=dict(
                        title="Time",
                        showgrid=True,
                        gridcolor="rgba(255,255,255,0.08)",
                        rangeslider=dict(visible=True),
                    ),
                    yaxis=dict(
                        title="SPX Price",
                        range=[price_min, price_max],
                        showgrid=True,
                        gridcolor="rgba(255,255,255,0.08)",
                        zeroline=False,
                    ),
                    yaxis2=dict(
                        title="Premium",
                        showgrid=False,
                        zeroline=False,
                    ),
                )

                st.plotly_chart(
                    chart,
                    use_container_width=True,
                    config={
                        "displayModeBar": True,
                        "scrollZoom": True,
                    },
                )
            else:
                st.info("Not enough data in the last hour yet.")
        else:
            st.info("Need more history to build the chart.")
    else:
        st.info("Flow chart will populate as refresh history builds.")

# ---------------------------------------------------------
# STRIKE LADDER
# ---------------------------------------------------------
st.subheader("Strike Ladder")

all_strikes_sorted = sorted(
    strike_summary.items(),
    key=lambda item: item[0]
)

table_rows = []
atm_strike = min(
    [strike for strike, _ in all_strikes_sorted],
    key=lambda strike: abs(strike - spot)
)

for strike, data in all_strikes_sorted:
    call_premium = round(float(data["call_premium"]), 2)
    put_premium = round(float(data["put_premium"]), 2)
    total_premium = round(float(data["total_premium"]), 2)

    if call_premium > put_premium:
        dominance = "CALLS"
    elif put_premium > call_premium:
        dominance = "PUTS"
    else:
        dominance = "BALANCED"

    table_rows.append({
        "Strike": float(strike),
        "Dominance": dominance,
        "Call Premium": call_premium,
        "Put Premium": put_premium,
        "Total Premium": total_premium,
    })

df = pd.DataFrame(table_rows)

display_df = df.copy()
display_df["Strike"] = display_df["Strike"].map(lambda x: f"{float(x):,.2f}")
display_df["Call Premium"] = display_df["Call Premium"].map(lambda x: f"{float(x):,.2f}")
display_df["Put Premium"] = display_df["Put Premium"].map(lambda x: f"{float(x):,.2f}")
display_df["Total Premium"] = display_df["Total Premium"].map(lambda x: f"{float(x):,.2f}")

def style_rows(row):
    styles = []

    for col in row.index:
        cell_style = ""

        if col == "Dominance":
            if row["Dominance"] == "CALLS":
                cell_style = "background-color: #0f9d58; color: white"
            elif row["Dominance"] == "PUTS":
                cell_style = "background-color: #d93025; color: white"
            else:
                cell_style = "background-color: #9aa0a6; color: white"

        if row["Strike"] == f"{float(atm_strike):,.2f}" and col == "Strike":
            cell_style = "background-color: #f9ab00; color: black; font-weight: bold"

        styles.append(cell_style)

    return styles

styled_df = display_df.style.apply(style_rows, axis=1)
st.dataframe(styled_df, use_container_width=True)
