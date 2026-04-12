import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from flow_engine import (
    get_near_money_spx_chain,
    summarize_premium_flow,
    summarize_premium_by_strike,
    summarize_gamma_by_strike,
    identify_key_levels,
    generate_trade_signal,
    get_next_spx_expiration
)

st.set_page_config(page_title="SPX Flow Dashboard", layout="wide")

SPIKE_THRESHOLD = 5_000_000
PROXIMITY_THRESHOLD = 5
STRIKES_ABOVE = 10
STRIKES_BELOW = 10
PRICE_VIEW_RANGE = 30
EXPIRATION = get_next_spx_expiration()

st.title("SPX 0DTE Flow Dashboard")
st_autorefresh(interval=15000, key="flow_refresh")

if "prior_net_premium" not in st.session_state:
    st.session_state["prior_net_premium"] = None

if "flow_history" not in st.session_state:
    st.session_state["flow_history"] = []

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
# LOAD DATA
# ---------------------------------------------------------
result = get_near_money_spx_chain(
    expiration=EXPIRATION,
    greeks=True,
    strikes_above=STRIKES_ABOVE,
    strikes_below=STRIKES_BELOW
)

summary = summarize_premium_flow(result["contracts"])
strike_summary = summarize_premium_by_strike(result["contracts"])
gamma_summary = summarize_gamma_by_strike(result["contracts"])
levels = identify_key_levels(strike_summary)

signal = generate_trade_signal(
    spot=result["spot"],
    summary=summary,
    levels=levels
)

top_3_by_premium = sorted(
    strike_summary.items(),
    key=lambda item: item[1]["total_premium"],
    reverse=True
)[:3]

top_5_gamma = sorted(
    gamma_summary.items(),
    key=lambda item: item[1]["total_gamma"],
    reverse=True
)[:5]

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
spot = result["spot"]

near_call_strike = abs(spot - top_call_strike) <= PROXIMITY_THRESHOLD
near_put_strike = abs(spot - top_put_strike) <= PROXIMITY_THRESHOLD

if near_call_strike and near_put_strike:
    proximity_label = "Near top call + put"
elif near_call_strike:
    proximity_label = f"Near call {top_call_strike}"
elif near_put_strike:
    proximity_label = f"Near put {top_put_strike}"
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

    c1.metric("SPX", f"{result['spot']}")
    c2.metric("Net Premium", f"${summary['net_premium']:,.0f}")
    c3.metric("Net Change", f"${net_change:,.0f}")
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
            <b>Top Call:</b> {levels['top_call_strike']} &nbsp; | &nbsp;
            <b>Top Put:</b> {levels['top_put_strike']} &nbsp; | &nbsp;
            <b>Target:</b> {signal['target']}
        </div>
        """,
        unsafe_allow_html=True
    )

    timeframe_choice = st.select_slider(
        "Chart Window",
        options=["30m", "1h", "2h", "4h", "All"],
        value="All"
    )

    bar_interval = st.select_slider(
        "Chart Bar Size",
        options=["1min", "3min", "5min", "15min"],
        value="5min"
    )

    st.caption("Purple = premium levels | Green = gamma levels | Orange = ATM")

with top_right:
    st.subheader(f"SPX Price vs Call / Put Buying ({bar_interval} Bars)")

    if not history_df.empty and len(history_df) >= 2:
        chart_df = history_df.copy()
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
        chart_df = chart_df.sort_values("timestamp")
        chart_df = chart_df.set_index("timestamp")

        chart_bars = chart_df.resample(bar_interval).last().dropna().reset_index()

        if len(chart_bars) >= 2:
            latest_ts = chart_bars["timestamp"].max()

            if timeframe_choice == "30m":
                cutoff = latest_ts - pd.Timedelta(minutes=30)
                chart_bars = chart_bars[chart_bars["timestamp"] >= cutoff]
            elif timeframe_choice == "1h":
                cutoff = latest_ts - pd.Timedelta(hours=1)
                chart_bars = chart_bars[chart_bars["timestamp"] >= cutoff]
            elif timeframe_choice == "2h":
                cutoff = latest_ts - pd.Timedelta(hours=2)
                chart_bars = chart_bars[chart_bars["timestamp"] >= cutoff]
            elif timeframe_choice == "4h":
                cutoff = latest_ts - pd.Timedelta(hours=4)
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
                        line=dict(color="white", width=3)
                    ),
                    secondary_y=False
                )

                chart.add_trace(
                    go.Scatter(
                        x=chart_bars["timestamp"],
                        y=chart_bars["call_premium"],
                        mode="lines",
                        name="Calls",
                        line=dict(color="orange", width=3)
                    ),
                    secondary_y=True
                )

                chart.add_trace(
                    go.Scatter(
                        x=chart_bars["timestamp"],
                        y=chart_bars["put_premium"],
                        mode="lines",
                        name="Puts",
                        line=dict(color="dodgerblue", width=3)
                    ),
                    secondary_y=True
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
                            textfont=dict(color="lime", size=11)
                        ),
                        secondary_y=True
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
                            textfont=dict(color="cyan", size=11)
                        ),
                        secondary_y=True
                    )

                # Premium level markers
                key_line_specs = {
                    "K1": {"color": "#c084fc", "width": 2.5},
                    "K2": {"color": "#a855f7", "width": 1.8},
                    "K3": {"color": "#9333ea", "width": 1.2}
                }

                for idx, (strike, _) in enumerate(top_3_by_premium, start=1):
                    rank = f"K{idx}"
                    spec = key_line_specs[rank]
                    chart.add_hline(
                        y=strike,
                        line_width=spec["width"],
                        line_dash="dot",
                        line_color=spec["color"],
                        annotation_text=f"{rank} {strike}",
                        annotation_position="top left",
                        annotation_font_color=spec["color"],
                        secondary_y=False
                    )

                # Gamma level markers
                gamma_line_specs = {
                    "G1": {"color": "#22c55e", "width": 2.2},
                    "G2": {"color": "#16a34a", "width": 1.6},
                    "G3": {"color": "#15803d", "width": 1.2}
                }

                top_3_gamma_for_chart = top_5_gamma[:3]

                for idx, (strike, _) in enumerate(top_3_gamma_for_chart, start=1):
                    rank = f"G{idx}"
                    spec = gamma_line_specs[rank]
                    chart.add_hline(
                        y=strike,
                        line_width=spec["width"],
                        line_dash="dash",
                        line_color=spec["color"],
                        annotation_text=f"{rank} {strike}",
                        annotation_position="bottom right",
                        annotation_font_color=spec["color"],
                        secondary_y=False
                    )

                # ATM marker
                atm_strike = min(
                    [s for s, _ in strike_summary.items()],
                    key=lambda s: abs(s - result["spot"])
                )

                chart.add_hline(
                    y=atm_strike,
                    line_width=1,
                    line_dash="dash",
                    line_color="#f9ab00",
                    annotation_text=f"ATM {atm_strike}",
                    annotation_position="bottom left",
                    annotation_font_color="#f9ab00",
                    secondary_y=False
                )

                # Session open marker
                session_open = pd.Timestamp(now.date()) + pd.Timedelta(hours=8, minutes=30)
                chart.add_vline(
                    x=session_open,
                    line_width=1,
                    line_dash="dot",
                    line_color="gray"
                )

                # Price axis fixed to +/- 30 points around current spot
                price_min = result["spot"] - PRICE_VIEW_RANGE
                price_max = result["spot"] + PRICE_VIEW_RANGE

                chart.update_layout(
                    height=420,
                    margin=dict(l=20, r=20, t=20, b=20),
                    paper_bgcolor="#0b1220",
                    plot_bgcolor="#0b1220",
                    font=dict(color="white"),
                    hovermode="x unified",
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="left",
                        x=0
                    ),
                    xaxis=dict(
                        title="Time",
                        showgrid=True,
                        gridcolor="rgba(255,255,255,0.08)",
                        rangeslider=dict(visible=True)
                    ),
                    yaxis=dict(
                        title="SPX Price",
                        range=[price_min, price_max],
                        showgrid=True,
                        gridcolor="rgba(255,255,255,0.08)",
                        zeroline=False
                    ),
                    yaxis2=dict(
                        title="Premium",
                        showgrid=False,
                        zeroline=False
                    ),
                )

                st.plotly_chart(
                    chart,
                    use_container_width=True,
                    config={
                        "displayModeBar": True,
                        "scrollZoom": True
                    }
                )
            else:
                st.info("Not enough data in the selected timeframe yet.")
        else:
            st.info("Need more history to build the chart.")
    else:
        st.info("Flow chart will populate as refresh history builds.")

# ---------------------------------------------------------
# MIDDLE SECTION: K LEVELS / GAMMA
# ---------------------------------------------------------
left_col, right_col = st.columns([1.2, 1])

with left_col:
    st.subheader("K Levels")

    k_rows = []
    for idx, (strike, data) in enumerate(top_3_by_premium, start=1):
        if data["call_premium"] > data["put_premium"]:
            dominance = "CALLS"
        elif data["put_premium"] > data["call_premium"]:
            dominance = "PUTS"
        else:
            dominance = "BALANCED"

        k_rows.append({
            "Level": f"K{idx}",
            "Strike": strike,
            "Dominance": dominance,
            "Call Premium": round(data["call_premium"], 0),
            "Put Premium": round(data["put_premium"], 0),
            "Total Premium": round(data["total_premium"], 0)
        })

    k_df = pd.DataFrame(k_rows)
    st.dataframe(k_df, use_container_width=True, hide_index=True)

with right_col:
    st.subheader("Top Gamma Strikes")

    gamma_rows = []
    for idx, (strike, data) in enumerate(top_5_gamma, start=1):
        gamma_rows.append({
            "Rank": f"G{idx}",
            "Strike": strike,
            "Call Gamma": round(data["call_gamma"], 4),
            "Put Gamma": round(data["put_gamma"], 4),
            "Total Gamma": round(data["total_gamma"], 4)
        })

    gamma_df = pd.DataFrame(gamma_rows)
    st.dataframe(gamma_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# STRIKE LADDER
# ---------------------------------------------------------
st.subheader("Strike Ladder")

all_strikes_sorted = sorted(
    strike_summary.items(),
    key=lambda item: item[0]
)

top_3_map = {}
for idx, (strike, _) in enumerate(top_3_by_premium, start=1):
    top_3_map[strike] = f"K{idx}"

table_rows = []

for strike, data in all_strikes_sorted:
    call_premium = round(data["call_premium"], 2)
    put_premium = round(data["put_premium"], 2)
    total_premium = round(data["total_premium"], 2)

    if call_premium > put_premium:
        dominance = "CALLS"
    elif put_premium > call_premium:
        dominance = "PUTS"
    else:
        dominance = "BALANCED"

    key_rank = top_3_map.get(strike, "")

    table_rows.append({
        "Key Rank": key_rank,
        "Strike": strike,
        "ATM": "",
        "Dominance": dominance,
        "Call Premium": call_premium,
        "Put Premium": put_premium,
        "Total Premium": total_premium
    })

df = pd.DataFrame(table_rows)

if not df.empty:
    atm_index = (df["Strike"] - result["spot"]).abs().idxmin()
    df.loc[atm_index, "ATM"] = "ATM"

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

        if row["ATM"] == "ATM" and col in ["Strike", "ATM"]:
            cell_style = "background-color: #f9ab00; color: black; font-weight: bold"

        if row["Key Rank"] == "K1" and col in ["Key Rank", "Strike", "Total Premium"]:
            cell_style = "background-color: #6a1b9a; color: white; font-weight: bold"
        elif row["Key Rank"] == "K2" and col in ["Key Rank", "Strike", "Total Premium"]:
            cell_style = "background-color: #8e24aa; color: white; font-weight: bold"
        elif row["Key Rank"] == "K3" and col in ["Key Rank", "Strike", "Total Premium"]:
            cell_style = "background-color: #ab47bc; color: white; font-weight: bold"

        styles.append(cell_style)

    return styles

styled_df = df.style.apply(style_rows, axis=1)
st.dataframe(styled_df, use_container_width=True)