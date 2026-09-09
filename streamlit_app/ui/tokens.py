"""Design tokens — the single source of truth for the visual language.

Kept in Python (not only CSS) so that chart code, which cannot read CSS custom
properties, draws from exactly the same palette as the DOM.

Direction: "calm companion" — a wellness product, not a clinical form.
Pure data: no Streamlit, no state, no I/O.
"""

from __future__ import annotations

# --- Core palette ---------------------------------------------------------
BG = "#F8FAFC"
SURFACE = "#FFFFFF"
SURFACE_2 = "#F1F5F9"

PRIMARY = "#4F8EF7"  # brand accent: borders, tints, focus rings, chart lines
PRIMARY_HOVER = "#3B7BE4"
PRIMARY_INK = "#2F63BD"  # darkened for text/icons on white (5.77:1, AA)
PRIMARY_SOFT = "#EAF2FE"

# Solid buttons need a darker fill than the brand accent. White on #4F8EF7 is
# only 3.21:1 — below the 4.5:1 floor for a 15px semibold label, which is not
# "large text" under WCAG. These two are measured at 5.77:1 and 7.53:1.
# #4F8EF7 stays the accent everywhere it does not sit behind white text.
PRIMARY_BTN = "#2F63BD"
PRIMARY_BTN_HOVER = "#254F99"

SECONDARY = "#A8DADC"
SECONDARY_INK = "#2C6E71"
SECONDARY_SOFT = "#EDF7F7"

ACCENT = "#F9E79F"
ACCENT_INK = "#8A6D1F"
ACCENT_SOFT = "#FEF9E7"

TEXT = "#1E293B"
MUTED = "#64748B"
BORDER = "#E2E8F0"

# --- Semantic states ------------------------------------------------------
# The spec's success/warning hues are pastel; at text size they fall below the
# 4.5:1 contrast floor on white. Each therefore ships as a trio: `*_TINT` for
# fills, the base hue for bars/borders, and `*_INK` (darkened, AA-compliant)
# for any glyph or label. Never render text in the base hue on a light surface.
SUCCESS = "#81C784"
SUCCESS_INK = "#2E7D32"
SUCCESS_TINT = "#EDF7ED"

WARNING = "#F6C177"
WARNING_INK = "#92400E"
WARNING_TINT = "#FEF6EA"

DANGER = "#E57373"
DANGER_INK = "#B3261E"
DANGER_TINT = "#FDECEA"

INFO = PRIMARY
INFO_INK = PRIMARY_INK
INFO_TINT = PRIMARY_SOFT

# --- Stress levels --------------------------------------------------------
# Softened from the old clinical reds/greens so a "High" result never reads as
# an alarm. Level is ALWAYS rendered next to its Vietnamese text label — colour
# is reinforcement, never the sole carrier of meaning.
LEVEL_COLORS = {
    "Low": "#6FBF8B",
    "Moderate": "#F0C674",
    "High": "#EFA06B",
    "Severe": "#E58A8A",
}
LEVEL_INK = {
    "Low": "#2E7D32",
    "Moderate": "#8A6D1F",
    "High": "#A65523",
    "Severe": "#B3261E",
}
LEVEL_TINT = {
    "Low": "#EDF7ED",
    "Moderate": "#FEF6EA",
    "High": "#FDF0E7",
    "Severe": "#FDECEA",
}

# --- Shape / depth --------------------------------------------------------
RADIUS = {"sm": "12px", "md": "16px", "lg": "20px", "xl": "24px", "full": "999px"}

SHADOW = {
    "xs": "0 1px 2px rgba(15,23,42,.04)",
    "sm": "0 2px 8px rgba(15,23,42,.05)",
    "md": "0 6px 20px rgba(15,23,42,.07)",
    "lg": "0 14px 40px rgba(15,23,42,.09)",
}

FONT_STACK = "'Be Vietnam Pro',-apple-system,'Segoe UI',Roboto,Arial,sans-serif"

# Transparent paper for Plotly so charts sit flush on their card.
CHART_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": FONT_STACK, "color": TEXT, "size": 13},
}
