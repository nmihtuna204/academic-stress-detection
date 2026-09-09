"""The single CSS source for the frontend — "calm companion" design system.

Tokens live in ui/tokens.py and are mirrored into CSS custom properties here so
that Python (charts) and the DOM never drift apart. `configure_page()` is the
first call on every page: it sets page config and injects the stylesheet.

Pure presentation — no state, no API, no scoring.

Selector policy: target `data-testid` attributes and `st-key-*` container
classes only. Streamlit's emotion hashes (`st-emotion-cache-1c7aczl`) change
between releases and must never be styled against.

The font is self-hosted (fully offline) from streamlit_app/static/fonts and
served via Streamlit static serving (enableStaticServing in .streamlit/config.toml).
"""

from __future__ import annotations

import streamlit as st

from ui import tokens as T

_FONT_FACES = "".join(
    "@font-face{font-family:'Be Vietnam Pro';font-style:normal;font-weight:%d;"
    "font-display:swap;src:url('app/static/fonts/BeVietnamPro-%d.ttf') "
    "format('truetype');}" % (w, w)
    for w in (400, 500, 600, 700)
)

_VARS = f"""
:root {{
  --font-sans:{T.FONT_STACK};
  --bg:{T.BG}; --surface:{T.SURFACE}; --surface-2:{T.SURFACE_2};
  --primary:{T.PRIMARY}; --primary-hover:{T.PRIMARY_HOVER};
  --primary-ink:{T.PRIMARY_INK}; --primary-soft:{T.PRIMARY_SOFT};
  --primary-btn:{T.PRIMARY_BTN}; --primary-btn-hover:{T.PRIMARY_BTN_HOVER};
  --secondary:{T.SECONDARY}; --secondary-ink:{T.SECONDARY_INK};
  --secondary-soft:{T.SECONDARY_SOFT};
  --accent:{T.ACCENT}; --accent-ink:{T.ACCENT_INK}; --accent-soft:{T.ACCENT_SOFT};
  --text:{T.TEXT}; --muted:{T.MUTED}; --border:{T.BORDER};
  --success:{T.SUCCESS}; --success-ink:{T.SUCCESS_INK}; --success-tint:{T.SUCCESS_TINT};
  --warning:{T.WARNING}; --warning-ink:{T.WARNING_INK}; --warning-tint:{T.WARNING_TINT};
  --danger:{T.DANGER}; --danger-ink:{T.DANGER_INK}; --danger-tint:{T.DANGER_TINT};
  --info:{T.INFO}; --info-ink:{T.INFO_INK}; --info-tint:{T.INFO_TINT};
  --r-sm:{T.RADIUS["sm"]}; --r-md:{T.RADIUS["md"]}; --r-lg:{T.RADIUS["lg"]};
  --r-xl:{T.RADIUS["xl"]}; --r-full:{T.RADIUS["full"]};
  --sh-xs:{T.SHADOW["xs"]}; --sh-sm:{T.SHADOW["sm"]};
  --sh-md:{T.SHADOW["md"]}; --sh-lg:{T.SHADOW["lg"]};
  --s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:20px;--s6:24px;--s7:32px;--s8:44px;--s9:60px;
  --ease:cubic-bezier(.22,.61,.36,1);
}}
"""

_BASE = """
/* ---------- Canvas & rhythm ---------- */
.stApp { font-family:var(--font-sans); color:var(--text); background:var(--bg);
  -webkit-font-smoothing:antialiased; }
[data-testid="stMainBlockContainer"], .stMain .block-container {
  max-width:940px; padding-top:var(--s7); padding-bottom:var(--s9); }

/* Vietnamese stacks diacritics above AND below the x-height, so every text
   block needs more leading than a Latin-only design would use. */
.stApp h1 { font-size:2.1rem; font-weight:700; line-height:1.28; letter-spacing:-.02em;
  color:var(--text); }
.stApp h2 { font-size:1.5rem; font-weight:600; line-height:1.35; letter-spacing:-.01em; }
.stApp h3 { font-size:1.2rem; font-weight:600; line-height:1.4; }
.stApp h4 { font-size:1.02rem; font-weight:600; line-height:1.45; }
.stApp p, .stApp li { font-size:.97rem; line-height:1.75; color:var(--text); }
.stApp a { color:var(--primary-ink); text-decoration-thickness:1px;
  text-underline-offset:2px; }
.stApp code { background:var(--surface-2); border-radius:6px; padding:.1em .4em;
  font-size:.88em; color:var(--primary-ink); }
hr { border:none; border-top:1px solid var(--border); margin:var(--s7) 0; }

/* ---------- Strip Streamlit chrome for a product feel ---------- */
[data-testid="stDecoration"], [data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"] { display:none !important; }
#MainMenu, footer { visibility:hidden; height:0; }
header[data-testid="stHeader"] { background:transparent; height:0; }
/* Default filename-derived nav is replaced by ui/nav.py */
[data-testid="stSidebarNav"] { display:none !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background:var(--surface);
  border-right:1px solid var(--border); }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
  padding:var(--s5) var(--s4) var(--s6); }
[data-testid="stSidebarHeader"] { padding-bottom:0; }

/* ---------- Custom nav (st.page_link inside keyed containers) ---------- */
[class*="st-key-navitem-"] [data-testid="stPageLink"] a,
[class*="st-key-navactive-"] [data-testid="stPageLink"] a {
  border-radius:var(--r-sm); padding:.6rem .7rem; margin:1px 0;
  transition:background .18s var(--ease), color .18s var(--ease),
             transform .18s var(--ease); }
[class*="st-key-navitem-"] [data-testid="stPageLink"] a span,
[class*="st-key-navitem-"] [data-testid="stPageLink"] a p {
  color:var(--muted) !important; font-weight:500 !important; font-size:.92rem !important; }
[class*="st-key-navitem-"] [data-testid="stPageLink"] a:hover {
  background:var(--surface-2); transform:translateX(2px); }
[class*="st-key-navitem-"] [data-testid="stPageLink"] a:hover span,
[class*="st-key-navitem-"] [data-testid="stPageLink"] a:hover p {
  color:var(--text) !important; }
/* Active page */
[class*="st-key-navactive-"] [data-testid="stPageLink"] a { background:var(--primary-soft); }
[class*="st-key-navactive-"] [data-testid="stPageLink"] a span,
[class*="st-key-navactive-"] [data-testid="stPageLink"] a p {
  color:var(--primary-ink) !important; font-weight:600 !important; font-size:.92rem !important; }
.pt-nav-label { font-size:.7rem; font-weight:700; letter-spacing:.1em;
  text-transform:uppercase; color:var(--muted); padding:.2rem .5rem .4rem; }

/* ---------- Buttons ----------
   Addressed via data-testid; the legacy button[kind="..."] attribute is no
   longer emitted (verified against the live DOM). */
.stButton>button, .stFormSubmitButton>button, [data-testid^="stBaseButton-"] {
  border-radius:var(--r-full); font-weight:600; min-height:46px; padding:.5rem 1.5rem;
  font-family:var(--font-sans); font-size:.95rem; letter-spacing:.01em;
  transition:transform .18s var(--ease), box-shadow .18s var(--ease),
             background .18s var(--ease), border-color .18s var(--ease); }
/* Fill is --primary-btn, not --primary: white on the brand accent is 3.21:1
   and would fail AA at this label size. See ui/tokens.py. */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background:var(--primary-btn); border:1px solid var(--primary-btn); color:#fff;
  box-shadow:0 2px 10px rgba(47,99,189,.26); }
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background:var(--primary-btn-hover); border-color:var(--primary-btn-hover); color:#fff;
  transform:translateY(-2px); box-shadow:0 8px 22px rgba(47,99,189,.32); }
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background:var(--surface); border:1px solid var(--border); color:var(--text); }
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
  border-color:var(--primary); color:var(--primary-ink); background:var(--primary-soft);
  transform:translateY(-2px); }
button:active { transform:translateY(0) !important; }

/* ---------- Inputs ---------- */
.stTextArea textarea, .stTextInput input, .stNumberInput input {
  border-radius:var(--r-md) !important; font-family:var(--font-sans);
  font-size:.97rem; line-height:1.7; background:var(--surface);
  border-color:var(--border) !important;
  transition:border-color .18s var(--ease), box-shadow .18s var(--ease); }
.stTextArea textarea:focus, .stTextInput input:focus, .stNumberInput input:focus {
  border-color:var(--primary) !important;
  box-shadow:0 0 0 4px rgba(79,142,247,.14) !important; }
.stTextArea textarea::placeholder { color:#94A3B8; }
[data-baseweb="select"]>div { border-radius:var(--r-md) !important;
  border-color:var(--border) !important; }
label[data-testid="stWidgetLabel"] p { font-size:.9rem !important; font-weight:500;
  color:var(--text); }

/* ---------- Radios as large, tappable option cards ----------
   Streamlit >=1.5x emits [data-testid="stRadioOption"]; the older
   label[data-baseweb="radio"] no longer exists. Verified against the live DOM. */
[data-testid="stRadioGroup"] { gap:.45rem; width:100%; align-items:stretch; }
[data-testid="stRadioOption"] {
  background:var(--surface); border:1.5px solid var(--border); border-radius:var(--r-md);
  padding:.7rem .9rem; margin:0; width:100%; cursor:pointer;
  transition:border-color .16s var(--ease), background .16s var(--ease),
             box-shadow .16s var(--ease); }
[data-testid="stRadioOption"]:hover {
  border-color:var(--primary); background:var(--primary-soft); box-shadow:var(--sh-xs); }
[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {
  font-size:.93rem !important; line-height:1.5; margin:0; }
/* Selected option */
[data-testid="stRadioOption"]:has(input:checked) {
  border-color:var(--primary); background:var(--primary-soft);
  box-shadow:0 0 0 3px rgba(79,142,247,.12); }
[data-testid="stRadioOption"]:has(input:checked)
  div[data-testid="stMarkdownContainer"] p { font-weight:600; color:var(--primary-ink) !important; }

/* ---------- Checkbox ----------
   The visual box is the only non-testid <div> child of the label. */
[data-testid="stCheckbox"] label { align-items:center; }
[data-testid="stCheckbox"] label > div:not([data-testid]) { border-radius:7px !important; }
[data-testid="stCheckbox"] label p { font-size:.95rem !important; line-height:1.6; }

/* ---------- Pills (mood chips) ---------- */
[data-testid="stButtonGroup"] button { border-radius:var(--r-full) !important;
  font-weight:550; transition:transform .16s var(--ease), border-color .16s var(--ease); }
[data-testid="stButtonGroup"] button:hover { transform:translateY(-2px);
  border-color:var(--primary) !important; }

/* ---------- Forms & cards ----------
   `stVerticalBlockBorderWrapper` was removed upstream, so bordered containers
   are addressed by the stable `st-key-*` class their key emits instead. */
[data-testid="stForm"] { border:1px solid var(--border); border-radius:var(--r-xl);
  padding:var(--s6); background:var(--surface); box-shadow:var(--sh-sm); }
[class*="st-key-ptcard-"], [class*="st-key-qcard-"] {
  border-radius:var(--r-lg) !important; border-color:var(--border) !important;
  background:var(--surface); padding:var(--s5) !important; box-shadow:var(--sh-xs);
  transition:box-shadow .2s var(--ease), border-color .2s var(--ease); }
[class*="st-key-qcard-"]:hover { border-color:#CFDCEA !important;
  box-shadow:var(--sh-sm); }

/* ---------- Expander ---------- */
[data-testid="stExpander"] details { border:1px solid var(--border);
  border-radius:var(--r-lg); background:var(--surface); box-shadow:var(--sh-xs);
  overflow:hidden; }
[data-testid="stExpander"] summary { padding:.85rem 1.1rem; font-weight:600;
  font-size:.95rem; }
[data-testid="stExpander"] summary:hover { background:var(--surface-2);
  color:var(--primary-ink); }

/* ---------- Native alerts (kept for st.error / crisis path) ---------- */
[data-testid="stAlert"] { border-radius:var(--r-lg); border:none; padding:1rem 1.15rem;
  box-shadow:var(--sh-xs); }
[data-testid="stAlert"] p { font-size:.95rem; line-height:1.7; }

/* ---------- Metric ---------- */
[data-testid="stMetric"] { background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:var(--s5); box-shadow:var(--sh-xs); }
[data-testid="stMetricValue"] { font-size:1.7rem; font-weight:700; }

/* ---------- Sliders ---------- */
[data-testid="stSlider"] [role="slider"] { border-color:var(--primary) !important; }

/* ---------- Column alignment ---------- */
[data-testid="stHorizontalBlock"] { align-items:stretch; }

/* ---------- Focus visibility (keyboard a11y) ---------- */
*:focus-visible { outline:3px solid rgba(79,142,247,.55) !important; outline-offset:2px;
  border-radius:6px; }

/* ---------- Motion ---------- */
@keyframes ptFadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
@keyframes ptFadeIn { from{opacity:0} to{opacity:1} }
@keyframes ptPulseSoft { 0%,100%{opacity:.55} 50%{opacity:1} }
.pt-animate { animation:ptFadeUp .5s var(--ease) both; }
.pt-animate-1 { animation:ptFadeUp .5s var(--ease) .06s both; }
.pt-animate-2 { animation:ptFadeUp .5s var(--ease) .12s both; }
.pt-animate-3 { animation:ptFadeUp .5s var(--ease) .18s both; }
"""

_COMPONENTS = """
/* ================= Components emitted by ui/components.py ================= */

/* --- Page header --- */
.pt-header { margin:0 0 var(--s6); animation:ptFadeUp .5s var(--ease) both; }
.pt-eyebrow { display:inline-flex; align-items:center; gap:.4rem; font-size:.72rem;
  font-weight:700; letter-spacing:.11em; text-transform:uppercase;
  color:var(--primary-ink); background:var(--primary-soft); padding:.3rem .7rem;
  border-radius:var(--r-full); margin-bottom:.7rem; }
.pt-header h1 { display:flex; align-items:center; gap:.6rem; margin:0;
  font-size:2.1rem; font-weight:700; letter-spacing:-.02em; }
.pt-subtitle { color:var(--muted); font-size:1.02rem; line-height:1.7;
  margin:.6rem 0 0; max-width:64ch; }

/* --- Hero (home) --- */
.pt-hero { position:relative; overflow:hidden; border-radius:var(--r-xl);
  padding:var(--s8) var(--s7); margin-bottom:var(--s6);
  background:linear-gradient(135deg,#EAF2FE 0%,#EDF7F7 55%,#FEF9E7 100%);
  border:1px solid rgba(255,255,255,.8); box-shadow:var(--sh-sm);
  animation:ptFadeUp .55s var(--ease) both; }
.pt-hero::after { content:""; position:absolute; right:-70px; top:-70px; width:260px;
  height:260px; border-radius:50%; background:rgba(255,255,255,.42); }
.pt-hero-wave { position:absolute; right:-10px; bottom:-24px; opacity:.5;
  pointer-events:none; }
.pt-hero-inner { position:relative; z-index:1; max-width:60ch; }
.pt-hero .greet { font-size:1.05rem; font-weight:600; color:var(--primary-ink);
  margin:0 0 .5rem; display:flex; align-items:center; gap:.45rem; }
.pt-hero h1 { font-size:2.35rem; font-weight:700; line-height:1.24;
  letter-spacing:-.025em; margin:0 0 .7rem; color:#16233A; }
.pt-hero p { font-size:1.02rem; line-height:1.75; color:#334155; margin:0; }

/* --- Responsive card grid ---
   One grid beats N Streamlit columns: rows share a height automatically and
   the layout reflows without per-breakpoint rules. --min is set per call. */
.pt-grid { display:grid; gap:var(--s4); margin:var(--s2) 0 var(--s3);
  grid-template-columns:repeat(auto-fit,minmax(var(--min,220px),1fr)); }
.pt-grid > * { height:100%; }

/* --- Feature / info cards --- */
.pt-card { background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:var(--s5); box-shadow:var(--sh-xs); height:100%;
  transition:transform .2s var(--ease), box-shadow .2s var(--ease),
             border-color .2s var(--ease); }
.pt-card:hover { transform:translateY(-3px); box-shadow:var(--sh-md);
  border-color:#D3DEEA; }
.pt-card-ico { width:42px; height:42px; border-radius:13px; display:grid;
  place-items:center; margin-bottom:var(--s4); }
.pt-card h4 { margin:0 0 .35rem; font-size:1rem; font-weight:650; }
.pt-card p { margin:0; color:var(--muted); font-size:.9rem; line-height:1.65; }

/* --- Callout --- */
.pt-callout { display:flex; gap:.7rem; align-items:flex-start; border-radius:var(--r-md);
  padding:.95rem 1.1rem; margin:.5rem 0; font-size:.94rem; line-height:1.7;
  border:1px solid transparent; animation:ptFadeIn .4s var(--ease) both; }
.pt-callout .ico { margin-top:2px; }
.pt-callout.info { background:var(--info-tint); border-color:#D5E5FD; color:#1F3A5F; }
.pt-callout.info .ico { color:var(--info-ink); }
.pt-callout.success { background:var(--success-tint); border-color:#CFE9D2; color:#1F4620; }
.pt-callout.success .ico { color:var(--success-ink); }
.pt-callout.warning { background:var(--warning-tint); border-color:#F6E1BE; color:#5C3A0E; }
.pt-callout.warning .ico { color:var(--warning-ink); }
.pt-callout.danger { background:var(--danger-tint); border-color:#F6CFCC; color:#6E1E18; }
.pt-callout.danger .ico { color:var(--danger-ink); }
.pt-callout strong { font-weight:650; }

/* --- Consent card --- */
.pt-consent-list { list-style:none; padding:0; margin:0 0 var(--s3); }
.pt-consent-list li { display:flex; gap:.7rem; align-items:flex-start; padding:.55rem 0;
  font-size:.95rem; line-height:1.65; color:var(--text); }
.pt-consent-list li svg { margin-top:3px; color:var(--success-ink); }

/* --- Progress (questionnaires) --- */
.pt-progress-wrap { position:sticky; top:0; z-index:50; padding:.85rem 0 .7rem;
  background:linear-gradient(var(--bg) 78%,rgba(248,250,252,0)); margin-bottom:var(--s3); }
.pt-progress-top { display:flex; justify-content:space-between; align-items:baseline;
  margin-bottom:.45rem; }
.pt-progress-top .count { font-size:.9rem; font-weight:650; color:var(--text); }
.pt-progress-top .pct { font-size:.82rem; color:var(--muted); font-weight:500; }
.pt-progress-track { height:9px; border-radius:var(--r-full); background:#E6ECF3;
  overflow:hidden; }
.pt-progress-fill { height:100%; border-radius:var(--r-full);
  background:linear-gradient(90deg,var(--primary),#7FB2FA);
  transition:width .45s var(--ease); }
.pt-progress-fill.done { background:linear-gradient(90deg,var(--success),#A5D6A7); }

/* --- Question number chip --- */
.pt-qnum { display:inline-flex; align-items:center; justify-content:center;
  min-width:30px; height:30px; padding:0 .5rem; border-radius:var(--r-full);
  background:var(--primary-soft); color:var(--primary-ink); font-size:.82rem;
  font-weight:700; margin-bottom:.5rem; }
.pt-qtext { font-size:1rem; line-height:1.65; font-weight:500; margin:0 0 .7rem;
  color:var(--text); }

/* --- Result hero --- */
.pt-result-hero { border-radius:var(--r-xl); padding:var(--s7); margin-bottom:var(--s5);
  border:1px solid var(--border); box-shadow:var(--sh-sm);
  animation:ptFadeUp .5s var(--ease) both; }
.pt-result-hero .lvl { display:inline-flex; align-items:center; gap:.5rem;
  padding:.4rem .95rem; border-radius:var(--r-full); font-size:.85rem; font-weight:700;
  letter-spacing:.02em; margin-bottom:var(--s4); }
.pt-result-hero h2 { font-size:1.6rem; line-height:1.4; font-weight:650; margin:0 0 .6rem;
  letter-spacing:-.015em; }
.pt-result-hero p { font-size:1rem; line-height:1.8; color:#334155; margin:0; }

/* --- Factor chips (risk / protective) --- */
.pt-factors { display:flex; flex-wrap:wrap; gap:.45rem; margin-top:.3rem; }
.pt-factor { display:inline-flex; align-items:center; gap:.4rem; padding:.4rem .8rem;
  border-radius:var(--r-full); font-size:.85rem; font-weight:550; line-height:1.4; }
.pt-factor.risk { background:var(--warning-tint); color:var(--warning-ink);
  border:1px solid #F6E1BE; }
.pt-factor.protect { background:var(--success-tint); color:var(--success-ink);
  border:1px solid #CFE9D2; }

/* --- Recommendation cards --- */
.pt-rec { display:flex; gap:.9rem; align-items:flex-start; background:var(--surface);
  border:1px solid var(--border); border-radius:var(--r-lg); padding:var(--s5);
  box-shadow:var(--sh-xs); height:100%;
  transition:transform .2s var(--ease), box-shadow .2s var(--ease); }
.pt-rec:hover { transform:translateY(-3px); box-shadow:var(--sh-md); }
.pt-rec-ico { width:38px; height:38px; border-radius:12px; display:grid;
  place-items:center; flex:0 0 auto; background:var(--secondary-soft);
  color:var(--secondary-ink); }
.pt-rec-body h5 { margin:0 0 .25rem; font-size:.93rem; font-weight:650; color:var(--text); }
.pt-rec-body p { margin:0; font-size:.89rem; line-height:1.65; color:var(--muted); }

/* --- Stat tile --- */
.pt-stat { background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:var(--s5); box-shadow:var(--sh-xs); height:100%; }
.pt-stat .lbl { font-size:.79rem; color:var(--muted); font-weight:550;
  letter-spacing:.01em; }
.pt-stat .val { font-size:1.6rem; font-weight:700; line-height:1.2; margin-top:.25rem; }
.pt-stat .delta { font-size:.82rem; margin-top:.2rem; font-weight:550; }

/* --- Timeline (history) --- */
.pt-timeline { position:relative; padding-left:30px; margin-top:var(--s4); }
.pt-timeline::before { content:""; position:absolute; left:9px; top:6px; bottom:6px;
  width:2px; background:linear-gradient(var(--border),rgba(226,232,240,.2)); }
.pt-tl-item { position:relative; margin-bottom:var(--s4);
  animation:ptFadeUp .45s var(--ease) both; }
.pt-tl-dot { position:absolute; left:-30px; top:18px; width:20px; height:20px;
  border-radius:50%; border:3px solid var(--surface); box-shadow:0 0 0 1.5px var(--border); }
.pt-tl-card { background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:var(--s5); box-shadow:var(--sh-xs);
  transition:transform .2s var(--ease), box-shadow .2s var(--ease); }
.pt-tl-card:hover { transform:translateX(3px); box-shadow:var(--sh-sm); }
.pt-tl-time { font-size:.78rem; color:var(--muted); font-weight:550;
  display:flex; align-items:center; gap:.35rem; margin-bottom:.5rem; }
.pt-tl-row { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; }

/* --- Crisis block (utils.show_crisis) ---
   The one place that raises its voice: warmer and larger than any other card,
   but never a hazard-red alarm. */
[class*="st-key-ptcrisis"] {
  border-radius:var(--r-xl) !important; padding:var(--s6) var(--s7) !important;
  background:linear-gradient(135deg,#FDECEA,#FEF6EA 70%);
  border:1.5px solid #F6CFCC !important; box-shadow:var(--sh-md);
  margin:var(--s2) 0 var(--s4); }
[class*="st-key-ptcrisis"] p,
[class*="st-key-ptcrisis"] li { color:#5C1F1A; font-size:.98rem; line-height:1.8; }
[class*="st-key-ptcrisis"] strong { color:#7A1F17; }
.pt-crisis-head { display:flex; align-items:center; gap:.6rem; margin-bottom:.5rem;
  color:var(--danger-ink); font-weight:700; font-size:1.12rem; }

/* --- Level badge --- */
.pt-badge { display:inline-flex; align-items:center; gap:.35rem; padding:.28rem .7rem;
  border-radius:var(--r-full); font-size:.8rem; font-weight:650; line-height:1.4; }

/* --- Chips --- */
.pt-chips { display:flex; flex-wrap:wrap; gap:.4rem; }
.pt-chip { background:var(--secondary-soft); color:var(--secondary-ink);
  border:1px solid #D8ECEC; border-radius:var(--r-full); padding:.28rem .8rem;
  font-size:.83rem; font-weight:550; }

/* --- Empty state --- */
.pt-empty { text-align:center; padding:var(--s9) var(--s5); border:1.5px dashed #DCE4ED;
  border-radius:var(--r-xl); background:var(--surface); }
.pt-empty .ico { display:grid; place-items:center; width:56px; height:56px;
  margin:0 auto var(--s4); border-radius:18px; background:var(--primary-soft);
  color:var(--primary-ink); }
.pt-empty h4 { margin:0 0 .4rem; font-size:1.08rem; }
.pt-empty p { margin:0 auto; color:var(--muted); max-width:46ch; font-size:.93rem; }

/* --- Section title --- */
.pt-section { display:flex; align-items:center; gap:.55rem; margin:var(--s7) 0 var(--s4); }
.pt-section .ico { display:grid; place-items:center; width:32px; height:32px;
  border-radius:10px; background:var(--primary-soft); color:var(--primary-ink);
  flex:0 0 auto; }
.pt-section h3 { margin:0; font-size:1.15rem; font-weight:650; letter-spacing:-.01em; }
.pt-section .hint { font-size:.85rem; color:var(--muted); margin-left:auto;
  font-weight:500; }

/* --- Footer --- */
.pt-foot { margin-top:var(--s8); padding-top:var(--s5); border-top:1px solid var(--border);
  text-align:center; }
.pt-foot p { font-size:.82rem; color:var(--muted); margin:.5rem 0 0; }

/* --- Loading skeleton --- */
.pt-skeleton { border-radius:var(--r-lg); background:linear-gradient(90deg,
  var(--surface-2) 25%,#E9EFF5 37%,var(--surface-2) 63%);
  background-size:400% 100%; animation:ptShimmer 1.4s ease-in-out infinite; }
@keyframes ptShimmer { 0%{background-position:100% 50%} 100%{background-position:0 50%} }
"""

_RESPONSIVE = """
/* ---------- Responsive ---------- */
@media (max-width:900px) {
  [data-testid="stMainBlockContainer"], .stMain .block-container {
    padding-left:1.05rem; padding-right:1.05rem; padding-top:var(--s5); }
  .stApp h1 { font-size:1.7rem; }
  .pt-hero { padding:var(--s6) var(--s5); }
  .pt-hero h1 { font-size:1.75rem; }
  .pt-hero p { font-size:.96rem; }
  .pt-hero::after { display:none; }
  .pt-header h1 { font-size:1.65rem; }
  .pt-result-hero { padding:var(--s6) var(--s5); }
  .pt-result-hero h2 { font-size:1.3rem; }
  [data-testid="stForm"] { padding:var(--s5) var(--s4); }
  /* Stacked columns need their own breathing room on small screens */
  [data-testid="stColumn"] { min-width:100% !important; }
  .pt-timeline { padding-left:24px; }
  .pt-tl-dot { left:-24px; width:16px; height:16px; }
}
@media (max-width:480px) {
  .pt-hero h1 { font-size:1.5rem; }
  .stApp h1 { font-size:1.45rem; }
  .pt-progress-top .pct { display:none; }
}

/* ---------- Respect reduced-motion ---------- */
@media (prefers-reduced-motion:reduce) {
  *, *::before, *::after { animation-duration:.001ms !important;
    animation-iteration-count:1 !important; transition-duration:.001ms !important; }
}

/* ---------- Print ---------- */
@media print {
  [data-testid="stSidebar"], .stButton, .pt-progress-wrap { display:none !important; }
  .stApp { background:#fff; }
}
"""

_CSS = "<style>" + _FONT_FACES + _VARS + _BASE + _COMPONENTS + _RESPONSIVE + "</style>"


def inject_theme() -> None:
    """Inject the shared stylesheet. Idempotent per run; call once per page."""
    st.markdown(_CSS, unsafe_allow_html=True)


def configure_page(page_title: str, page_icon: str, layout: str = "wide") -> None:
    """First Streamlit call on every page: set page config + inject the theme."""
    st.set_page_config(
        page_title=f"{page_title} · A calm space",
        page_icon=page_icon,
        layout=layout,
        # "auto", not "expanded": on a phone the sidebar is an overlay, and
        # forcing it open covers the entire screen on first load.
        initial_sidebar_state="auto",
    )
    inject_theme()
