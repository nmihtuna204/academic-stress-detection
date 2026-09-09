"""Inline Lucide icons (https://lucide.dev, ISC licence).

Streamlit cannot load an external icon font under a strict offline setup, and
emoji render inconsistently across Windows/macOS/Linux — so the icon set is
inlined as SVG path data. Each entry is the *inner* markup of a 24x24 Lucide
glyph; `icon()` wraps it in a sized, coloured <svg>.

Icons are decorative by default (`aria-hidden`); pass `title` when the glyph is
the only carrier of meaning, which adds an accessible name.
"""

from __future__ import annotations

# Inner markup of each 24x24 Lucide glyph, keyed by Lucide's own name.
_PATHS: dict[str, str] = {
    "house": (
        '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/>'
        '<path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 '
        '10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
    ),
    "message-circle": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "clipboard-list": (
        '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/>'
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
        '<path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>'
    ),
    "chart-bar": (
        '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M7 16h8"/>'
        '<path d="M7 11h12"/><path d="M7 6h3"/>'
    ),
    "graduation-cap": (
        '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 '
        '0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/>'
        '<path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>'
    ),
    "sparkles": (
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 '
        '9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 '
        '9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 '
        '6.135a.5.5 0 0 1-.963 0z"/>'
    ),
    "trending-up": (
        '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>'
    ),
    "shield-check": (
        '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 '
        '0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 '
        '1 1z"/><path d="m9 12 2 2 4-4"/>'
    ),
    "lock": (
        '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
    ),
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "circle-check": (
        '<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/>'
    ),
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "triangle-alert": (
        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 '
        '1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>'
    ),
    "life-buoy": (
        '<circle cx="12" cy="12" r="10"/><path d="m4.93 4.93 4.24 4.24"/>'
        '<path d="m14.83 9.17 4.24-4.24"/><path d="m14.83 14.83 4.24 4.24"/>'
        '<path d="m9.17 14.83-4.24 4.24"/><circle cx="12" cy="12" r="4"/>'
    ),
    "leaf": (
        '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 '
        '10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>'
    ),
    "wind": (
        '<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/>'
        '<path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>'
    ),
    "calendar-check": (
        '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/>'
        '<path d="M3 10h18"/><path d="m9 16 2 2 4-4"/>'
    ),
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "users": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    "book-open": (
        '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 '
        '4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>'
    ),
    "heart": (
        '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 '
        '2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "pen-line": (
        '<path d="M12 20h9"/><path d="M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 '
        '0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z"/>'
    ),
    "send": (
        '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 '
        '6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>'
    ),
    "activity": (
        '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 '
        '2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>'
    ),
    "brain": (
        '<path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 '
        '0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 '
        '6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/>'
    ),
    "trash-2": (
        '<path d="M3 6h18"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
    ),
}

# Nav uses Streamlit's built-in Material Symbols (st.page_link only accepts an
# emoji or a :material/name: token — it cannot take raw SVG).
MATERIAL = {
    "home": ":material/home:",
    "journal": ":material/edit_note:",
    "dass": ":material/checklist:",
    "pss": ":material/bar_chart:",
    "context": ":material/school:",
    "result": ":material/auto_awesome:",
    "history": ":material/timeline:",
}


def icon(name: str, size: int = 20, color: str = "currentColor", stroke: float = 2, title: str | None = None) -> str:
    """Return an inline <svg> string for a Lucide glyph.

    Unknown names render nothing rather than raising — a missing decorative
    icon must never take a page down.
    """
    body = _PATHS.get(name)
    if body is None:
        return ""
    a11y = f"<title>{title}</title>" if title else ""
    aria = 'role="img"' if title else 'aria-hidden="true" focusable="false"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round" {aria} '
        f'style="flex:0 0 auto;display:inline-block;vertical-align:middle">{a11y}{body}</svg>'
    )
