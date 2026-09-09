"""Presentation layer for the Streamlit frontend ("calm companion" system).

- `tokens`     — palette, radii, shadows; the single source shared by CSS and charts.
- `theme`      — the stylesheet + `configure_page()`.
- `icons`      — inline Lucide SVGs and Material Symbols names for the nav.
- `components` — reusable markup helpers (cards, callouts, progress, timeline).
- `nav`        — the custom sidebar.

Nothing here touches session_state, the API, or scoring — pure [VISUAL].
"""
