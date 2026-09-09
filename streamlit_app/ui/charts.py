"""Plotly figure builders for the results and history pages.

Every figure draws its colours from ui/tokens.py, renders on a transparent
paper so it sits flush on its card, and direct-labels its values — a reader
should never need to match a swatch against a legend to know what they are
looking at. Colour always accompanies a text label, never replaces one.

Pure presentation: these take already-computed numbers and return figures.
"""

from __future__ import annotations

import plotly.graph_objects as go

from ui import tokens as T

LEVEL_ORDER = ["Low", "Moderate", "High", "Severe"]

DASS_SEVERITY_COLORS = {
    "Normal": T.LEVEL_COLORS["Low"],
    "Mild": T.LEVEL_COLORS["Moderate"],
    "Moderate": T.LEVEL_COLORS["Moderate"],
    "Severe": T.LEVEL_COLORS["High"],
    "Extremely Severe": T.LEVEL_COLORS["Severe"],
}


def gauge_chart(level: str, confidence: float | None, level_labels: dict[str, str]) -> go.Figure:
    """Soft arc meter for the unified stress level.

    The needle sits mid-band rather than at a precise number: the underlying
    label is ordinal (Low..Severe), and a sharp pointer would imply a precision
    the model does not have.
    """
    value = LEVEL_ORDER.index(level) + 0.5
    fig = go.Figure(
        go.Indicator(
            mode="gauge",
            value=value,
            gauge={
                "axis": {
                    "range": [0, 4],
                    "tickvals": [0.5, 1.5, 2.5, 3.5],
                    "ticktext": [level_labels[lv] for lv in LEVEL_ORDER],
                    "tickfont": {"size": 12, "color": T.MUTED},
                    "tickwidth": 0,
                    "ticklen": 0,
                },
                "bar": {"color": "rgba(0,0,0,0)"},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [i, i + 1], "color": T.LEVEL_TINT[lv]}
                    for i, lv in enumerate(LEVEL_ORDER)
                ],
                "threshold": {
                    "line": {"color": T.LEVEL_COLORS[level], "width": 7},
                    "thickness": 0.85,
                    "value": value,
                },
            },
        )
    )
    subtitle = f"Confidence {confidence:.0%}" if confidence is not None else ""
    fig.update_layout(
        height=260,
        # "Very high" is the widest tick and sits hard against the right edge —
        # these margins are what stop it being clipped.
        margin=dict(t=26, b=6, l=62, r=62),
        annotations=[
            dict(
                text=(
                    f"<b>{level_labels[level]}</b>"
                    f"<br><span style='font-size:12px;color:{T.MUTED}'>{subtitle}</span>"
                ),
                x=0.5,
                y=0.02,
                showarrow=False,
                font=dict(size=24, color=T.LEVEL_INK[level], family=T.FONT_STACK),
            )
        ],
        **T.CHART_LAYOUT,
    )
    return fig


def dass_bar_chart(dass: dict, severity_labels: dict[str, str]) -> go.Figure:
    """Horizontal bars for the three DASS-21 subscales (0-42), direct-labeled."""
    rows = [
        ("Stress", dass["stress_score"], dass["stress_level_dass"]),
        ("Anxiety", dass["anxiety_score"], dass["anxiety_level"]),
        ("Depression", dass["depression_score"], dass["depression_level"]),
    ]
    fig = go.Figure(
        go.Bar(
            y=[r[0] for r in rows],
            x=[r[1] for r in rows],
            orientation="h",
            marker=dict(color=[DASS_SEVERITY_COLORS[r[2]] for r in rows], cornerradius=6),
            width=0.5,
            text=[f"  {r[1]} · {severity_labels[r[2]]}" for r in rows],
            textposition="outside",
            textfont=dict(size=13, color=T.TEXT),
            hovertemplate="%{y}: %{x} points<extra></extra>",
        )
    )
    fig.update_layout(
        height=225,
        margin=dict(t=8, b=8, l=8, r=8),
        xaxis=dict(
            range=[0, 56],
            title=dict(text="Score (0–42)", font=dict(size=11, color=T.MUTED)),
            showgrid=True,
            gridcolor="rgba(148,163,184,.16)",
            zeroline=False,
        ),
        yaxis=dict(showgrid=False, tickfont=dict(size=13)),
        bargap=0.35,
        **T.CHART_LAYOUT,
    )
    return fig


def radar_chart(axes: list[tuple[str, float]]) -> go.Figure:
    """Profile radar over normalised 0-100 psychometric axes.

    `axes` is [(label, value_0_to_100), ...]; the caller decides which axes it
    actually has data for, so the shape never implies a measurement that was
    not taken.
    """
    labels = [a[0] for a in axes]
    values = [a[1] for a in axes]
    # Close the polygon.
    labels_closed = labels + [labels[0]]
    values_closed = values + [values[0]]

    fig = go.Figure(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor="rgba(79,142,247,.16)",
            line=dict(color=T.PRIMARY, width=2.5),
            marker=dict(size=7, color=T.PRIMARY),
            hovertemplate="%{theta}: %{r:.0f}/100<extra></extra>",
        )
    )
    fig.update_layout(
        height=350,
        # Axis labels ("Perceived stress", "Depression") sit outside the polygon;
        # without these margins Plotly clips them at the card edge.
        margin=dict(t=54, b=44, l=96, r=96),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True, range=[0, 100], showline=False,
                gridcolor="rgba(148,163,184,.22)",
                tickvals=[25, 50, 75, 100],
                # Rings carry the scale; the numbers overlap the polygon and the
                # 0-100 range is already stated in the section hint.
                showticklabels=False,
            ),
            angularaxis=dict(
                gridcolor="rgba(148,163,184,.22)",
                linecolor="rgba(148,163,184,.32)",  # default is near-black: too harsh
                linewidth=1,
                tickfont=dict(size=12, color=T.TEXT),
            ),
        ),
        showlegend=False,
        **T.CHART_LAYOUT,
    )
    return fig


def trend_chart(points: list[tuple[str, str]], level_labels: dict[str, str]) -> go.Figure:
    """Stress level over time. `points` is [(time_label, level), ...] oldest first."""
    xs = [p[0] for p in points]
    ys = [LEVEL_ORDER.index(p[1]) + 1 for p in points]
    colors = [T.LEVEL_COLORS[p[1]] for p in points]

    fig = go.Figure(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines+markers",
            line=dict(color=T.PRIMARY, width=3, shape="spline", smoothing=0.6),
            marker=dict(size=13, color=colors, line=dict(width=2.5, color="#fff")),
            hovertemplate="%{x}<br>Level: %{text}<extra></extra>",
            text=[level_labels[p[1]] for p in points],
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(t=18, b=8, l=8, r=18),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color=T.MUTED)),
        yaxis=dict(
            range=[0.6, 4.4],
            tickvals=[1, 2, 3, 4],
            ticktext=[level_labels[lv] for lv in LEVEL_ORDER],
            gridcolor="rgba(148,163,184,.18)",
            tickfont=dict(size=12),
            zeroline=False,
        ),
        **T.CHART_LAYOUT,
    )
    return fig
