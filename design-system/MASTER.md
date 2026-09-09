# Design System — "Calm Companion"
### Academic stress screening application for university students

> This document is the **source of truth** for the product's visual language.
> Translation into code: tokens in `streamlit_app/ui/tokens.py` (Python — shared
> by both CSS and charts), CSS in `streamlit_app/ui/theme.py`.
> View every component with sample data:
> `streamlit run streamlit_app/preview.py --server.port 8502`.

---

## 1. Design principles

The target user is in a state of high cognitive load (tired, anxious). Every
visual decision serves **reducing cognitive load** and **creating a sense of
safety**. The emotional goal: *a companion*, not *a test*.

1. **Readable first, beautiful second.** Contrast ≥ WCAG AA; generous
   line-height.
2. **A single accent colour** (a soft blue) — avoid a vivid palette that
   stimulates.
3. **Never lead with a number.** The Results page opens with a plain,
   non-judgmental sentence; scores and charts sit behind it as supporting data.
4. **Colour is never the only channel of information.** A level always comes
   with a text label.
5. **Safety is the absolute priority.** The crisis flow is shown before anything
   else, in a warm tone rather than alarm red.

## 2. Colour palette (design tokens)

Source: `streamlit_app/ui/tokens.py`.

| Token | Hex | Used for |
|---|---|---|
| `--bg` | `#F8FAFC` | Canvas background |
| `--surface` | `#FFFFFF` | Cards, sidebar, inputs |
| `--surface-2` | `#F1F5F9` | Recessed background |
| `--border` | `#E2E8F0` | 1px borders |
| `--text` | `#1E293B` | Primary text (ink) |
| `--muted` | `#64748B` | Secondary text, captions |
| `--primary` | `#4F8EF7` | **Brand colour** — borders, soft fills, focus ring, chart lines |
| `--primary-btn` | `#2F63BD` | **Solid button fill** (white text) — see §6 |
| `--primary-ink` | `#2F63BD` | Accent text/icons on a light background |
| `--primary-soft` | `#EAF2FE` | Chip background, selected item |
| `--secondary` | `#A8DADC` | Secondary accent, hint icons |
| `--accent` | `#F9E79F` | Warm accent (step cards) |
| `--success` / `--success-ink` | `#81C784` / `#2E7D32` | Fill-border / text |
| `--warning` / `--warning-ink` | `#F6C177` / `#92400E` | Fill-border / text |
| `--danger` / `--danger-ink` | `#E57373` / `#B3261E` | Fill-border / text |

**The rule of three.** The pastel colours in the brief (`#81C784`, `#F6C177`)
**do not reach contrast at body text size** (2.01:1 and 1.64:1 on white). Each
state therefore has three variants: `*_TINT` for fills, the base colour for
borders and bars, and `*_INK` (darkened) for **all text and icons**. Never set
text in the base colour on a light background.

**Stress level colours** (always accompanied by a text label, softened from the
earlier version):
`Low #6FBF8B · Moderate #F0C674 · High #EFA06B · Very high #E58A8A`.
Text on these fills uses the corresponding `LEVEL_INK`.

## 3. Typography

- **Font:** **Be Vietnam Pro** (self-hosted offline, weights 400/500/600/700).
  Fallback: Segoe UI, system sans. The family was originally chosen for its
  full Vietnamese diacritic coverage; it is retained after the move to an
  English interface because the type design and the offline self-hosting still
  serve the product, and changing it would alter every measured contrast value
  in §7.
- **Type scale:** h1 33.6px/700 · h2 24px/600 · h3 19px/600 · body 15.5px/400 ·
  caption 13px/muted.
- **Body line-height 1.75** — deliberately generous. It was originally set to
  give Vietnamese stacked diacritics room to breathe; it is kept because loose
  leading measurably helps readers under cognitive load, which is principle 1.
- No ALL CAPS on buttons; no serif faces.

## 4. Spacing, radius, shadow, motion

- **Spacing** on a 4px scale: `--s1..s9` = 4/8/12/16/20/24/32/44/60.
- **Radius:** sm 12px · md 16px · lg 20px · xl 24px · full 999px.
- **Shadows** very light (`--sh-xs..lg`), never heavy black.
- **Content width:** `max-width: 940px`.
- **Motion:** fade-up 0.5s on entry, hover lift 2–3px, easing
  `cubic-bezier(.22,.61,.36,1)`. All of it is disabled under
  `prefers-reduced-motion: reduce`.

## 5. Component patterns

`streamlit_app/ui/components.py` — presentation only, never touches
session_state or the API.

| Component | Function |
|---|---|
| PageHeader | `page_header(title, subtitle, icon_name, eyebrow)` |
| Hero | `hero(greeting, title, body)` |
| SectionTitle | `section_title(title, icon_name, hint)` |
| AppCard | `card(key, title)` |
| InfoCard | `feature_card(...)` · grid: `feature_grid(items)` |
| StatTile | `stat_card(...)` · grid: `stat_grid(items)` |
| Callout | `callout(kind, text)` |
| ProgressBar | `progress_bar(answered, total)` |
| QuestionCard | `question_card(number, text)` |
| ResultCard | `result_hero(level, label, headline, body)` |
| Factors | `factor_list(items, kind)` |
| RecommendationCard | `recommendation_card(...)` · grid: `recommendation_grid(items)` |
| Timeline | `timeline()` + `timeline_item(...)` |
| EmptyState | `empty_state(icon_name, title, description)` |

Charts live in `ui/charts.py` (gauge · DASS bars · radar · trend) and take their
colours from the same token set, so charts and DOM can never drift apart.

**Grid instead of columns.** Rows of cards use a single CSS grid
(`repeat(auto-fit, minmax(--min, 1fr))`) rather than `st.columns`: cards in a row
automatically match height and wrap on narrow screens.

**Icons.** Lucide inline SVG (`ui/icons.py`) for content; Material Symbols for
navigation (`st.page_link` accepts only emoji or `:material/...:`). Emoji are used
only for *mood chips*, where the emoji is the content.

## 6. Technical notes (verified against the real DOM)

- Select by `data-testid` and `st-key-*` classes; **do not** rely on
  `st-emotion-cache-*` (it changes between versions).
- Streamlit ≥1.5x: radio options are `[data-testid="stRadioOption"]`
  (`label[data-baseweb="radio"]` was dropped); buttons are
  `[data-testid^="stBaseButton-"]` (`button[kind=...]` was dropped);
  `stVerticalBlockBorderWrapper` was dropped — bordered cards are targeted via
  the `key=` of `st.container`.
- The questionnaire pages **do not use `st.form`**: a form defers reruns until
  submit, which would freeze the progress bar at 0/21 for the whole session.
- Streamlit does **not** reload an already-imported module when you edit the
  file — restart the server after editing `ui/*.py`.

## 7. Contrast audit (WCAG AA — 4.5:1 body text, 3:1 large text/UI)

Measured values, computed with the WCAG 2.x formula:

| Colour pair (text / background) | Ratio | Verdict |
|---|---|---|
| `#1E293B` ink / `#FFFFFF` | 14.63:1 | ✅ AAA |
| `#1E293B` ink / `#F8FAFC` canvas | 13.98:1 | ✅ AAA |
| `#64748B` muted / `#FFFFFF` | 4.76:1 | ✅ AA |
| `#FFFFFF` / `#2F63BD` primary button | 5.77:1 | ✅ AA |
| `#FFFFFF` / `#254F99` button hover | 7.90:1 | ✅ AAA |
| `#2F63BD` primary-ink / `#FFFFFF` | 5.77:1 | ✅ AA |
| `#2F63BD` / `#EAF2FE` (nav selected) | 5.12:1 | ✅ AA |
| `#2C6E71` secondary-ink / `#FFFFFF` | 5.87:1 | ✅ AA |
| `#8A6D1F` accent-ink / `#FFFFFF` | 4.90:1 | ✅ AA |
| Info callout text `#1F3A5F` / `#EAF2FE` | 10.19:1 | ✅ AAA |
| Success callout text `#1F4620` / `#EDF7ED` | 9.78:1 | ✅ AAA |
| Warning callout text `#5C3A0E` / `#FEF6EA` | 9.48:1 | ✅ AAA |
| Danger callout text `#6E1E18` / `#FDECEA` | 9.86:1 | ✅ AAA |
| Low level badge `#2E7D32` / `#EDF7ED` | 4.67:1 | ✅ AA |
| Moderate level badge `#8A6D1F` / `#FEF6EA` | 4.57:1 | ✅ AA |
| High level badge `#A65523` / `#FDF0E7` | 4.76:1 | ✅ AA |
| Very high level badge `#B3261E` / `#FDECEA` | 5.72:1 | ✅ AA |
| ⚠️ `#FFFFFF` / `#4F8EF7` (base accent) | **3.21:1** | ❌ Not for white text on a button fill |
| ⚠️ `#81C784` base success / `#FFFFFF` | **2.01:1** | ❌ Borders and bars only |
| ⚠️ `#F6C177` base warning / `#FFFFFF` | **1.64:1** | ❌ Borders and bars only |

**The last three rows are why the rule of three in §2 exists.** `#4F8EF7` from
the brief works well as a brand colour, but white text on it reaches only
3.21:1 — below the 4.5:1 threshold for a 15px/600 button label (which does not
count as "large text" under WCAG). Solid buttons therefore use `#2F63BD`;
`#4F8EF7` remains the brand colour everywhere white text is not laid over it.

## 8. Anti-pattern — **rejected with reasons**

For the wellness domain, recommendation systems commonly suggest
**Neumorphism / Soft UI**. This project **rejects Neumorphism** because it relies
on low-contrast shadows on a same-tone background → almost certain to fail
WCAG AA. This is a mental-health tool used by people who are already tired;
readability is mandatory.

The chosen direction: **Accessible & Ethical + Minimalism**, borrowing from Soft
UI at the card level (light shadow, large radius). Held firm: no purple/pink
AI-style gradients; no emoji as navigation icons; hover ~180ms; contrast ≥ 4.5:1.
