# ============================================================
# chart_engine.py
# Builds main Tr3ndy / Key Levels chart
# Added:
# - Gamma level overlays
# - Expected Move overlays
# ============================================================

import plotly.graph_objects as go


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _add_level(fig, level, label, color, dash="dash", width=2):
    level = _safe_float(level)

    if level is None:
        return

    fig.add_hline(
        y=level,
        line_width=width,
        line_dash=dash,
        line_color=color,
        annotation_text=label,
        annotation_position="right",
        annotation_font_color=color,
    )


def build_trendy_levels_chart(
    symbol,
    spot_price,
    trendy_edges,
    gamma_levels=None,
    expected_move=None
):
    spot_price = _safe_float(spot_price)

    fig = go.Figure()

    # ============================================================
    # SPOT PRICE MARKER
    # ============================================================

    if spot_price is not None:
        fig.add_trace(
            go.Scatter(
                x=[0],
                y=[spot_price],
                mode="markers+text",
                marker=dict(
                    size=16,
                    color="white",
                    line=dict(color="black", width=2),
                ),
                text=[f"{symbol} {spot_price:,.2f}"],
                textposition="top center",
                name="Spot",
            )
        )

        _add_level(
            fig=fig,
            level=spot_price,
            label=f"Spot {spot_price:,.2f}",
            color="white",
            dash="solid",
            width=3,
        )

    # ============================================================
    # TR3NDY DAILY LEVELS
    # ============================================================

    daily = trendy_edges.get("daily", {}) if trendy_edges else {}
    weekly = trendy_edges.get("weekly", {}) if trendy_edges else {}

    _add_level(fig, daily.get("supply"), "D Supply", "#ff4d4d", "dash", 2)
    _add_level(fig, daily.get("mid"), "D Mid", "#ffaa00", "dot", 2)
    _add_level(fig, daily.get("demand"), "D Demand", "#00ff99", "dash", 2)

    # ============================================================
    # TR3NDY WEEKLY LEVELS
    # ============================================================

    _add_level(fig, weekly.get("supply"), "W Supply", "#cc0000", "dash", 3)
    _add_level(fig, weekly.get("mid"), "W Mid", "#ffcc00", "dot", 3)
    _add_level(fig, weekly.get("demand"), "W Demand", "#00cc66", "dash", 3)

    # ============================================================
    # GAMMA LEVEL OVERLAYS
    # ============================================================

    if gamma_levels:
        gamma_map = [
            ("call_wall", "Call Wall", "#ff3333", "dash", 3),
            ("put_wall", "Put Wall", "#00ff66", "dash", 3),
            ("zero_gamma", "Zero Gamma", "#ffff00", "dot", 3),
            ("vol_trigger", "Vol Trigger", "#ff9900", "dashdot", 3),
            ("magnet", "Magnet", "#00ccff", "dot", 3),

            ("c1", "C1", "#ff6666", "dot", 2),
            ("c2", "C2", "#ff9999", "dot", 2),

            ("l1", "L1", "#66ff66", "dot", 2),
            ("l2", "L2", "#99ff99", "dot", 2),
        ]

        for key, label, color, dash, width in gamma_map:
            _add_level(
                fig=fig,
                level=gamma_levels.get(key),
                label=label,
                color=color,
                dash=dash,
                width=width,
            )

    # ============================================================
    # EXPECTED MOVE OVERLAYS
    # ============================================================

    if expected_move and not expected_move.get("error"):
        _add_level(
            fig=fig,
            level=expected_move.get("upper"),
            label="Expected High",
            color="#00ccff",
            dash="dot",
            width=2,
        )

        _add_level(
            fig=fig,
            level=expected_move.get("lower"),
            label="Expected Low",
            color="#00ccff",
            dash="dot",
            width=2,
        )

    # ============================================================
    # CHART RANGE
    # ============================================================

    all_levels = []

    if spot_price is not None:
        all_levels.append(spot_price)

    for group in [daily, weekly]:
        for key in ["supply", "mid", "demand"]:
            value = _safe_float(group.get(key))
            if value is not None:
                all_levels.append(value)

    if gamma_levels:
        for key in [
            "call_wall",
            "put_wall",
            "zero_gamma",
            "vol_trigger",
            "magnet",
            "c1",
            "c2",
            "l1",
            "l2",
        ]:
            value = _safe_float(gamma_levels.get(key))
            if value is not None:
                all_levels.append(value)

    if expected_move and not expected_move.get("error"):
        for key in ["upper", "lower"]:
            value = _safe_float(expected_move.get(key))
            if value is not None:
                all_levels.append(value)

    if all_levels:
        min_level = min(all_levels)
        max_level = max(all_levels)
        padding = max((max_level - min_level) * 0.15, 5)

        fig.update_yaxes(
            range=[
                min_level - padding,
                max_level + padding,
            ]
        )

    # ============================================================
    # LAYOUT
    # ============================================================

    fig.update_layout(
        title=f"{symbol} Key Levels",
        height=650,

        paper_bgcolor="black",
        plot_bgcolor="black",

        font=dict(
            color="white",
            size=14,
        ),

        xaxis=dict(
            visible=False,
            showgrid=False,
            zeroline=False,
        ),

        yaxis=dict(
            title="Price",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            zeroline=False,
            color="white",
            side="right",
        ),

        margin=dict(
            l=20,
            r=110,
            t=60,
            b=20,
        ),

        showlegend=False,
    )

    return fig