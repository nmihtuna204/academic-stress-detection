"""Reusable presentational components for the Streamlit frontend.

Every component here is pure markup built from the classes defined in
ui/theme.py: no session_state, no API calls, no scoring. Pages compose these
rather than hand-rolling HTML, so spacing and colour stay consistent.

Naming maps to the design system: AppCard -> `card`, SectionTitle ->
`section_title`, QuestionCard -> `question_card`, ProgressBar -> `progress_bar`,
InfoCard -> `feature_card`, ResultCard -> `result_hero`, RecommendationCard ->
`recommendation_card`.
"""

from __future__ import annotations

import html
import re
from contextlib import contextmanager

import streamlit as st

from ui import tokens as T
from ui.icons import icon
from utils import DISCLAIMER

_CALLOUT_ICON = {
    "info": "info",
    "success": "circle-check",
    "warning": "triangle-alert",
    "danger": "life-buoy",
}

# Leading emoji / pictograph plus any variation selector and trailing space.
_LEADING_EMOJI = re.compile(
    r"^[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]+\s*"
)


def _inline_md(text: str) -> str:
    """Minimal inline markdown -> HTML for short callout/label strings.

    Escapes first so caller text can never inject markup, then re-enables the
    small subset (**bold**, `code`, newlines) the copy actually uses.
    """
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text.replace("\n", "<br>")


# --------------------------------------------------------------------------
# Headers
# --------------------------------------------------------------------------
def page_header(
    title: str,
    subtitle: str | None = None,
    icon_name: str | None = None,
    eyebrow: str | None = None,
) -> None:
    """Consistent page header: optional eyebrow pill + icon + title + subtitle."""
    eyebrow_html = (
        f'<div class="pt-eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ""
    )
    icon_html = (
        f'<span style="color:var(--primary-ink)">{icon(icon_name, 28)}</span>'
        if icon_name
        else ""
    )
    sub_html = f'<p class="pt-subtitle">{_inline_md(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f'<div class="pt-header">{eyebrow_html}'
        f"<h1>{icon_html}{html.escape(title)}</h1>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def hero(greeting: str, title: str, body: str) -> None:
    """Warm welcome block for the home page."""
    st.markdown(
        f'<div class="pt-hero"><div class="pt-hero-inner">'
        f'<p class="greet">{icon("heart", 18)} {html.escape(greeting)}</p>'
        f"<h1>{html.escape(title)}</h1><p>{_inline_md(body)}</p>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def section_title(title: str, icon_name: str | None = None, hint: str | None = None) -> None:
    """Section heading with an icon tile and an optional right-aligned hint."""
    ico = f'<span class="ico">{icon(icon_name, 17)}</span>' if icon_name else ""
    hint_html = f'<span class="hint">{html.escape(hint)}</span>' if hint else ""
    st.markdown(
        f'<div class="pt-section">{ico}<h3>{html.escape(title)}</h3>{hint_html}</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------
@contextmanager
def card(key: str, title: str | None = None):
    """AppCard — bordered content container (context manager).

    `key` must be unique on the page: Streamlit turns it into a stable
    `st-key-ptcard-<key>` class, which is what the stylesheet hooks. Upstream
    removed the old `stVerticalBlockBorderWrapper` test-id, and the emotion
    hashes that replaced it are not safe to style against.
    """
    box = st.container(border=True, key=f"ptcard-{key}")
    with box:
        if title:
            st.markdown(f"#### {title}")
        yield box


_TONES = {
    "primary": (T.PRIMARY_SOFT, T.PRIMARY_INK),
    "secondary": (T.SECONDARY_SOFT, T.SECONDARY_INK),
    "accent": (T.ACCENT_SOFT, T.ACCENT_INK),
    "success": (T.SUCCESS_TINT, T.SUCCESS_INK),
}


def feature_card_html(icon_name: str, title: str, body: str, tone: str = "primary") -> str:
    """InfoCard markup — icon tile + title + short description."""
    bg, fg = _TONES.get(tone, _TONES["primary"])
    return (
        f'<div class="pt-card">'
        f'<div class="pt-card-ico" style="background:{bg};color:{fg}">{icon(icon_name, 21)}</div>'
        f"<h4>{html.escape(title)}</h4><p>{_inline_md(body)}</p></div>"
    )


def feature_card(icon_name: str, title: str, body: str, tone: str = "primary") -> None:
    """Render a single InfoCard."""
    st.markdown(feature_card_html(icon_name, title, body, tone), unsafe_allow_html=True)


def grid(items: list[str], min_width: int = 220) -> None:
    """Lay out pre-built card markup in one responsive CSS grid.

    Streamlit columns are separate DOM subtrees, so sibling cards cannot share a
    height and each column needs its own mobile breakpoint. A single grid gives
    equal-height rows for free and reflows on narrow screens by itself.
    """
    if not items:
        return
    st.markdown(
        f'<div class="pt-grid" style="--min:{min_width}px">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def feature_grid(items: list[tuple[str, str, str, str]], min_width: int = 220) -> None:
    """Grid of InfoCards. `items` is [(icon, title, body, tone), ...]."""
    grid([feature_card_html(*i) for i in items], min_width)


def stat_card_html(label: str, value: str, delta: str | None = None, tone: str = "neutral") -> str:
    """Stat tile markup: label + big value + optional delta line."""
    tone_color = {
        "neutral": "var(--muted)",
        "success": "var(--success-ink)",
        "warning": "var(--warning-ink)",
        "danger": "var(--danger-ink)",
        "accent": "var(--primary-ink)",
    }.get(tone, "var(--muted)")
    delta_html = (
        f'<div class="delta" style="color:{tone_color}">{html.escape(delta)}</div>'
        if delta else ""
    )
    return (
        f'<div class="pt-stat"><div class="lbl">{html.escape(label)}</div>'
        f'<div class="val">{html.escape(value)}</div>{delta_html}</div>'
    )


def stat_card(label: str, value: str, delta: str | None = None, tone: str = "neutral") -> None:
    """Render a single stat tile."""
    st.markdown(stat_card_html(label, value, delta, tone), unsafe_allow_html=True)


def stat_grid(items: list[tuple[str, str, str | None, str]], min_width: int = 190) -> None:
    """Grid of stat tiles. `items` is [(label, value, delta, tone), ...]."""
    grid([stat_card_html(*i) for i in items], min_width)


# --------------------------------------------------------------------------
# Feedback
# --------------------------------------------------------------------------
def callout(kind: str, text: str) -> None:
    """Soft-tinted callout. kind in {info, success, warning, danger}.

    Any leading emoji in `text` is dropped: the component draws its own Lucide
    glyph, and several source strings (DISCLAIMER, the crisis copy) already
    begin with one, which would otherwise render two icons side by side.
    """
    kind = kind if kind in _CALLOUT_ICON else "info"
    body = _LEADING_EMOJI.sub("", text).lstrip()
    st.markdown(
        f'<div class="pt-callout {kind}">'
        f'<span class="ico">{icon(_CALLOUT_ICON[kind], 18)}</span>'
        f"<span>{_inline_md(body)}</span></div>",
        unsafe_allow_html=True,
    )


def empty_state(icon_name: str, title: str, description: str) -> None:
    """Centered empty-state block."""
    st.markdown(
        f'<div class="pt-empty"><div class="ico">{icon(icon_name, 26)}</div>'
        f"<h4>{html.escape(title)}</h4><p>{_inline_md(description)}</p></div>",
        unsafe_allow_html=True,
    )


def chips(items: list[str]) -> None:
    """A row of read-only pill chips."""
    if not items:
        return
    inner = "".join(f'<span class="pt-chip">{html.escape(str(i))}</span>' for i in items)
    st.markdown(f'<div class="pt-chips">{inner}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Questionnaire pieces
# --------------------------------------------------------------------------
def progress_bar(answered: int, total: int, noun: str = "item") -> None:
    """Sticky progress indicator: "Item 5 / 21" + percentage + filled track."""
    pct = int(round(100 * answered / total)) if total else 0
    done = " done" if answered >= total else ""
    st.markdown(
        f'<div class="pt-progress-wrap"><div class="pt-progress-top">'
        f'<span class="count">{html.escape(noun.capitalize())} {answered} / {total}</span>'
        f'<span class="pct">{pct}%</span></div>'
        f'<div class="pt-progress-track" role="progressbar" aria-valuenow="{answered}" '
        f'aria-valuemin="0" aria-valuemax="{total}" '
        f'aria-label="Questionnaire completion progress">'
        f'<div class="pt-progress-fill{done}" style="width:{pct}%"></div></div></div>',
        unsafe_allow_html=True,
    )


def question_label(number: int, text: str) -> None:
    """Number chip + question text, rendered above the radio group."""
    st.markdown(
        f'<div class="pt-qnum">{number}</div>'
        f'<p class="pt-qtext">{html.escape(text)}</p>',
        unsafe_allow_html=True,
    )


@contextmanager
def question_card(number: int, text: str):
    """QuestionCard — bordered card holding one question and its options."""
    box = st.container(border=True, key=f"qcard-{number}")
    with box:
        question_label(number, text)
        yield box


# --------------------------------------------------------------------------
# Result pieces
# --------------------------------------------------------------------------
def level_badge(level: str, label: str) -> str:
    """Return badge markup for a stress level (colour + text label together)."""
    return (
        f'<span class="pt-badge" style="background:{T.LEVEL_TINT.get(level, T.SURFACE_2)};'
        f'color:{T.LEVEL_INK.get(level, T.MUTED)}">{icon("activity", 14)}'
        f"{html.escape(label)}</span>"
    )


def result_hero(level: str, label: str, headline: str, body: str) -> None:
    """The single most important block in the app.

    Leads with a plain-language, non-alarming sentence; the level badge sits
    above it as reinforcement rather than as the headline itself.
    """
    tint = T.LEVEL_TINT.get(level, T.SURFACE_2)
    ink = T.LEVEL_INK.get(level, T.TEXT)
    st.markdown(
        f'<div class="pt-result-hero" style="background:linear-gradient(135deg,{tint},#FFFFFF 70%)">'
        f'<span class="lvl" style="background:{tint};color:{ink}">'
        f'{icon("activity", 15)} Level: {html.escape(label)}</span>'
        f"<h2>{html.escape(headline)}</h2><p>{_inline_md(body)}</p></div>",
        unsafe_allow_html=True,
    )


def factor_list(items: list[str], kind: str = "risk") -> None:
    """Risk (`risk`) or protective (`protect`) factors as tinted chips."""
    if not items:
        return
    ico = "triangle-alert" if kind == "risk" else "shield-check"
    inner = "".join(
        f'<span class="pt-factor {kind}">{icon(ico, 14)}{html.escape(str(i))}</span>'
        for i in items
    )
    st.markdown(f'<div class="pt-factors">{inner}</div>', unsafe_allow_html=True)


def recommendation_card_html(icon_name: str, title: str, body: str) -> str:
    """RecommendationCard markup — one suggested action."""
    return (
        f'<div class="pt-rec"><div class="pt-rec-ico">{icon(icon_name, 19)}</div>'
        f'<div class="pt-rec-body"><h5>{html.escape(title)}</h5>'
        f"<p>{_inline_md(body)}</p></div></div>"
    )


def recommendation_card(icon_name: str, title: str, body: str) -> None:
    """Render a single RecommendationCard."""
    st.markdown(recommendation_card_html(icon_name, title, body), unsafe_allow_html=True)


def recommendation_grid(items: list[tuple[str, str, str]], min_width: int = 240) -> None:
    """Grid of RecommendationCards. `items` is [(icon, title, body), ...]."""
    grid([recommendation_card_html(*i) for i in items], min_width)


def timeline_item(time_label: str, level: str, badge_html: str, detail: str) -> None:
    """One entry in the history timeline."""
    dot = T.LEVEL_COLORS.get(level, T.BORDER)
    st.markdown(
        f'<div class="pt-tl-item"><div class="pt-tl-dot" style="background:{dot}"></div>'
        f'<div class="pt-tl-card">'
        f'<div class="pt-tl-time">{icon("clock", 13)}{html.escape(time_label)}</div>'
        f'<div class="pt-tl-row">{badge_html}</div>'
        f'<p style="margin:.6rem 0 0;font-size:.88rem;color:var(--muted);line-height:1.6">'
        f"{_inline_md(detail)}</p></div></div>",
        unsafe_allow_html=True,
    )


@contextmanager
def timeline():
    """Wrap timeline_item() calls so the connecting rail renders behind them."""
    st.markdown('<div class="pt-timeline">', unsafe_allow_html=True)
    yield
    st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Layout helpers
# --------------------------------------------------------------------------
def section_divider() -> None:
    """A subtle horizontal rule using the border token."""
    st.markdown(
        '<hr style="border:none;border-top:1px solid var(--border);margin:2rem 0;">',
        unsafe_allow_html=True,
    )


def spacer(height: int = 16) -> None:
    """Vertical whitespace, in px."""
    st.markdown(f'<div style="height:{height}px"></div>', unsafe_allow_html=True)


def app_footer() -> None:
    """Standard page footer: medical disclaimer + provenance note."""
    st.markdown('<div class="pt-foot">', unsafe_allow_html=True)
    callout("warning", DISCLAIMER)
    st.markdown(
        "<p>Pre-thesis project · A screening tool, not a substitute for medical diagnosis.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
