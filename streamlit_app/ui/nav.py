"""Custom sidebar navigation.

Streamlit's built-in nav derives its labels from filenames, which turns them
into bare underscore-separated words and allows no icons. That nav is hidden in
ui/theme.py and rebuilt here from `st.page_link`, which accepts a proper label
and a Material Symbols icon.

Active state: each link is wrapped in a keyed `st.container`, so Streamlit emits
a stable `st-key-navitem-*` / `st-key-navactive-*` class that the stylesheet
hooks. The active page is passed in explicitly by each page — cheaper and more
reliable than inferring it from the script path.

The sidebar deliberately carries no brand lockup: the nav starts straight at the
step list.
"""

from __future__ import annotations

import streamlit as st

from ui.icons import MATERIAL, icon

# slug -> (path relative to the entrypoint, label, material icon)
PAGES: list[tuple[str, str, str, str]] = [
    ("home", "Home.py", "Home", MATERIAL["home"]),
    ("journal", "pages/1_Share_Feelings.py", "Share how you feel", MATERIAL["journal"]),
    ("dass", "pages/2_DASS_21.py", "DASS-21 questionnaire", MATERIAL["dass"]),
    ("pss", "pages/3_PSS_10.py", "PSS-10 questionnaire", MATERIAL["pss"]),
    ("context", "pages/4_Context.py", "Academic context", MATERIAL["context"]),
    ("result", "pages/5_Results.py", "Results", MATERIAL["result"]),
    ("history", "pages/6_History.py", "History", MATERIAL["history"]),
]


def render_sidebar(active: str) -> None:
    """Draw the sidebar: nav links and a reassurance footer.

    `active` is the slug of the page currently rendering (see PAGES).
    """
    with st.sidebar:
        st.markdown('<div class="pt-nav-label">Your journey</div>', unsafe_allow_html=True)

        for slug, path, label, ico in PAGES:
            prefix = "navactive" if slug == active else "navitem"
            with st.container(key=f"{prefix}-{slug}"):
                st.page_link(path, label=label, icon=ico)

        st.markdown(
            '<div style="margin-top:auto;padding:1.4rem .5rem .2rem;">'
            '<div style="display:flex;gap:.5rem;align-items:flex-start;'
            "background:var(--secondary-soft);border:1px solid #D8ECEC;"
            'border-radius:14px;padding:.75rem .85rem;">'
            f'<span style="color:var(--secondary-ink);margin-top:1px">{icon("lock", 15)}</span>'
            '<span style="font-size:.76rem;line-height:1.55;color:var(--secondary-ink)">'
            "Completely anonymous. You can stop at any time.</span></div></div>",
            unsafe_allow_html=True,
        )
