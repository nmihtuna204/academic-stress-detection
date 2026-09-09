"""Build the pre-thesis defence deck as a .pptx.

Generated from a script for the same reason the report is: every figure quoted
here has to match `docs/RESULTS.md` and the report, and a slide deck maintained
by hand drifts away from both within a day.

Design follows the application's own tokens (streamlit_app/ui/tokens.py) so the
deck and the demo look like one piece of work.

Usage:
    python report/build_slides.py [--out report/PreThesis_Slides.pptx]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

REPORT_DIR = Path(__file__).resolve().parent
TARGET = REPORT_DIR / "PreThesis_Slides.pptx"

# --- palette, mirrored from streamlit_app/ui/tokens.py ---------------------
INK = RGBColor(0x1E, 0x29, 0x3B)
MUTED = RGBColor(0x64, 0x74, 0x8B)
PRIMARY = RGBColor(0x2F, 0x63, 0xBD)
ACCENT = RGBColor(0x4F, 0x8E, 0xF7)
SUCCESS = RGBColor(0x2E, 0x7D, 0x32)
WARNING = RGBColor(0x92, 0x40, 0x0E)
DANGER = RGBColor(0xB3, 0x26, 0x1E)
SURFACE = RGBColor(0xF1, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = "Calibri"

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.85)
CONTENT_W = SLIDE_W - 2 * MARGIN


def _txbox(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    return frame


def _para(frame, text, size, *, bold=False, color=INK, space_after=6,
          align=PP_ALIGN.LEFT, first=False, bullet_level=None):
    p = frame.paragraphs[0] if first else frame.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    if bullet_level is not None:
        p.level = bullet_level
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    return p


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def title_slide(prs, title, subtitle, meta):
    slide = blank(prs)
    bar = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(0.28))
    bar.fill.solid()
    bar.fill.fore_color.rgb = PRIMARY
    bar.line.fill.background()

    frame = _txbox(slide, MARGIN, Inches(2.1), CONTENT_W, Inches(2.6))
    _para(frame, title, 40, bold=True, color=INK, first=True, space_after=14)
    _para(frame, subtitle, 20, color=MUTED, space_after=28)
    for line in meta:
        _para(frame, line, 15, color=MUTED, space_after=4)
    return slide


def content_slide(prs, title, blocks, *, footer=None, eyebrow=None):
    """`blocks` is a list of (kind, text) where kind is head/body/bullet/note."""
    slide = blank(prs)

    top = Inches(0.55)
    if eyebrow:
        eb = _txbox(slide, MARGIN, top, CONTENT_W, Inches(0.3))
        _para(eb, eyebrow.upper(), 12, bold=True, color=ACCENT, first=True, space_after=0)
        top = Inches(0.9)

    tf = _txbox(slide, MARGIN, top, CONTENT_W, Inches(0.8))
    _para(tf, title, 30, bold=True, color=INK, first=True, space_after=0)

    rule = slide.shapes.add_shape(1, MARGIN, top + Inches(0.72), Inches(1.4), Emu(28575))
    rule.fill.solid()
    rule.fill.fore_color.rgb = ACCENT
    rule.line.fill.background()

    body = _txbox(slide, MARGIN, top + Inches(1.0), CONTENT_W, Inches(4.7))
    first = True
    for kind, text in blocks:
        if kind == "head":
            _para(body, text, 19, bold=True, color=PRIMARY, first=first, space_after=6)
        elif kind == "bullet":
            _para(body, "•  " + text, 17, color=INK, first=first, space_after=9)
        elif kind == "sub":
            _para(body, "     – " + text, 15, color=MUTED, first=first, space_after=6)
        elif kind == "note":
            _para(body, text, 15, color=MUTED, first=first, space_after=8)
        elif kind == "good":
            _para(body, "✓  " + text, 17, color=SUCCESS, first=first, space_after=9)
        elif kind == "bad":
            _para(body, "✗  " + text, 17, color=DANGER, first=first, space_after=9)
        elif kind == "warn":
            _para(body, "!  " + text, 17, color=WARNING, first=first, space_after=9)
        else:
            _para(body, text, 17, color=INK, first=first, space_after=9)
        first = False

    if footer:
        ff = _txbox(slide, MARGIN, Inches(6.7), CONTENT_W, Inches(0.4))
        _para(ff, footer, 12, color=MUTED, first=True, space_after=0)
    return slide


def table_slide(prs, title, headers, rows, *, eyebrow=None, footer=None, highlight=None):
    slide = blank(prs)

    top = Inches(0.55)
    if eyebrow:
        eb = _txbox(slide, MARGIN, top, CONTENT_W, Inches(0.3))
        _para(eb, eyebrow.upper(), 12, bold=True, color=ACCENT, first=True, space_after=0)
        top = Inches(0.9)

    tf = _txbox(slide, MARGIN, top, CONTENT_W, Inches(0.8))
    _para(tf, title, 30, bold=True, color=INK, first=True, space_after=0)

    shape = slide.shapes.add_table(
        len(rows) + 1, len(headers), MARGIN, top + Inches(1.0),
        CONTENT_W, Inches(0.42) * (len(rows) + 1),
    )
    table = shape.table

    for c, head in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = head
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT
        r = p.runs[0]
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.color.rgb = WHITE
        r.font.name = FONT
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY

    for i, row in enumerate(rows, start=1):
        for c, value in enumerate(row):
            cell = table.cell(i, c)
            cell.text = str(value)
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT
            r = p.runs[0]
            r.font.size = Pt(14)
            r.font.name = FONT
            emphasised = highlight is not None and i - 1 == highlight
            r.font.bold = emphasised
            r.font.color.rgb = PRIMARY if emphasised else INK
            cell.fill.solid()
            cell.fill.fore_color.rgb = SURFACE if i % 2 else WHITE

    if footer:
        ff = _txbox(slide, MARGIN, Inches(6.6), CONTENT_W, Inches(0.6))
        _para(ff, footer, 13, color=MUTED, first=True, space_after=0)
    return slide


def section_slide(prs, number, title, subtitle=""):
    slide = blank(prs)
    band = slide.shapes.add_shape(1, 0, Inches(2.4), SLIDE_W, Inches(2.4))
    band.fill.solid()
    band.fill.fore_color.rgb = PRIMARY
    band.line.fill.background()

    frame = _txbox(slide, MARGIN, Inches(2.75), CONTENT_W, Inches(1.8))
    _para(frame, number, 15, bold=True, color=RGBColor(0xC7, 0xDC, 0xFA), first=True, space_after=6)
    _para(frame, title, 34, bold=True, color=WHITE, space_after=6)
    if subtitle:
        _para(frame, subtitle, 16, color=RGBColor(0xDC, 0xEA, 0xFC), space_after=0)
    return slide


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------


def build(prs: Presentation) -> None:
    """The 15-slide defence deck.

    Rebuilt 2026-09-09 against the current state of the project. Every figure
    here is taken from an artefact in `data/eval/`, and where a measurement does
    not exist the slide says so rather than leaving a gap that reads as a
    result.

    The order is deliberate. The three genuinely unflattering findings -
    template-derived data, a safety rule that used to miss half its cases, and a
    proposed system with no reportable score - are volunteered rather than
    waited for. Two of the three are now the strongest slides in the deck,
    because the fix and the honest procedure behind it are more interesting than
    the original defect.
    """

    # ---------------------------------------------------------------- 1 title
    title_slide(
        prs,
        "An LLM-powered Application for Detecting Academic Stress Levels "
        "in Vietnamese University Students",
        "A layered screening system: validated instruments, a fine-tuned encoder, "
        "and a grounded language model behind a deterministic safety rule",
        [
            "Pre-thesis defence  ·  School of Computer Science and Engineering",
            "International University — VNU-HCM",
            "A screening and self-reflection aid. Not a diagnostic instrument.",
        ],
    )

    # ---------------------------------------------------------------- 2 problem
    content_slide(
        prs,
        "Two kinds of tool exist, and each is missing something",
        [
            ("head", "Validated questionnaires — DASS-21, PSS-10"),
            ("bullet", "Trusted and psychometrically sound."),
            ("sub", "The student receives a number and nothing else: no explanation, no next step."),
            ("head", "General-purpose chatbots"),
            ("bullet", "Conversational, and willing to give advice."),
            ("sub", "Anchored to no instrument, and they invent advice that has no source."),
            ("head", "The gap this project addresses"),
            ("bullet", "Keep the validated instrument as the authority; let the model explain "
                       "and suggest, grounded in a curated corpus rather than its own parameters."),
            ("warn", "In this domain a wrong answer is not a poor user experience. It is potential "
                     "harm — which is why the architecture is ordered the way the next slide shows."),
        ],
        eyebrow="the problem",
    )

    # ---------------------------------------------------------------- 3 objectives
    table_slide(
        prs,
        "Five objectives, and where each one actually stands",
        ["#", "Objective", "Status"],
        [
            ["O1", "Psychometric scoring, exact to the manual", "Met"],
            ["O2", "Fine-tune a Vietnamese encoder, compare against baselines", "Partly met"],
            ["O3", "Retrieval-augmented advice + component ablation", "Partly met"],
            ["O4", "Crisis detection, quantitatively evaluated", "Met"],
            ["O5", "Reproducible evaluation — no number without a script", "Met"],
        ],
        eyebrow="scope",
        footer="O2 and O3 are only partly met, and this slide says so before the results do. "
               "Slides 10 and 14 give the reasons: a provider quota limit, and an ablation that "
               "has not run.",
    )

    # ---------------------------------------------------------------- 4 architecture
    content_slide(
        prs,
        "Deterministic core, generative periphery",
        [
            ("head", "Crisis rule  →  Scoring  →  Classifier  →  Retrieval  →  Generation"),
            ("bullet", "The ordering is a safety property, not an engineering convenience."),
            ("sub", "The crisis rule runs before the model and before anything is written to disk."),
            ("sub", "Scoring is arithmetic: it always produces a result."),
            ("sub", "The classifier degrades to lexicon matching if the model is unavailable."),
            ("sub", "Retrieval and generation are last precisely because they can fail unpredictably."),
            ("good", "Read the pipeline left to right as decreasing reliability AND decreasing "
                     "authority. The most trustworthy component runs first and can pre-empt "
                     "everything after it."),
            ("note", "If generation fails the system returns its deterministic results and says why. "
                     "It does not return an error, and it does not guess."),
        ],
        eyebrow="architecture",
        footer="Figure: system architecture",
    )

    # ---------------------------------------------------------------- 5 data
    content_slide(
        prs,
        "The data, and a label that is my own invention",
        [
            ("bullet", "466 synthetic students · frozen split 326 / 70 / 70 · seed 42"),
            ("bullet", "Ground truth: four classes, from the MORE SEVERE of the DASS-21 stress "
                       "subscale and the PSS-10 category."),
            ("sub", "Deliberately conservative: in screening a false alarm is cheaper than a miss."),
            ("warn", "DASS-21 is validated. PSS-10 is validated. Combining them into one four-class "
                     "label is a decision of this project and carries no independent psychometric "
                     "validation. I state that rather than having solved it."),
            ("note", "The split is frozen and reused everywhere, because the classifier was "
                     "fine-tuned on its training portion — redrawing it would leak training data "
                     "into the test set."),
        ],
        eyebrow="data",
        footer="Test distribution — Low 16 · Moderate 23 · High 22 · Severe 9   "
               "(Figure 4.2: label distribution)",
    )

    # ---------------------------------------------------------------- 6 classifier
    content_slide(
        prs,
        "The classifier: PhoBERT, fine-tuned and fully offline",
        [
            ("bullet", "PhoBERT-base · AdamW, lr 2e-5, 4 epochs, best-epoch selection"),
            ("good", "Validation macro-F1 0.8403 at epoch 2, then a complete plateau — epochs 3 "
                     "and 4 add nothing, so epoch 2 is what ships."),
            ("good", "Held-out test: accuracy 0.800 / macro-F1 0.8013 on the three-class task."),
            ("head", "Two honest notes"),
            ("bullet", "It is a three-class model. In the unified four-class comparison its F1 on "
                       "Severe is zero BY CONSTRUCTION, not by failure."),
            ("bullet", "It runs entirely offline — no network, no third party. That matters for an "
                       "application handling private writing about mental health."),
        ],
        eyebrow="model",
        footer="Figure 4.3: training and validation curves",
    )

    # ---------------------------------------------------------------- 7 safety result
    table_slide(
        prs,
        "The safety rule: what it used to do, and what it does now",
        ["Held-out set (60 bilingual items)", "Before", "After"],
        [
            ["Precision", "0.600", "1.000"],
            ["Recall", "0.200", "0.867"],
            ["F1", "0.300", "0.929"],
            ["Explicit ideation", "6 / 12", "12 / 12"],
            ["Indirect ideation", "0 / 14", "11 / 14"],
            ["False positives (20 lethal-sounding idioms)", "4", "0"],
        ],
        eyebrow="safety",
        highlight=4,
        footer="The old rule matched fixed phrases. On phrasing it had never seen it scored recall "
               "0.200 — not the 0.500 previously published, which came partly from the test set "
               "sharing wording with the lexicon.",
    )

    # ---------------------------------------------------------------- 8 safety method
    content_slide(
        prs,
        "Fixing it honestly was harder than fixing it",
        [
            ("bad", "The twelve failures were already published. Adding them to the phrase list "
                    "would have been tuning against my own test set."),
            ("head", "The order is what makes the number mean something"),
            ("bullet", "1.  Wrote a NEW 60-item bilingual set and froze it, SHA-256 recorded, "
                       "before the new rule existed."),
            ("bullet", "2.  Rebuilt the rule around six constructs from suicide-risk assessment, "
                       "written from that taxonomy rather than from failing items."),
            ("bullet", "3.  Measured once. The first measurement is the one reported."),
            ("bullet", "4.  Demoted the two older sets to DEVELOPMENT sets."),
            ("good", "Re-measuring the held-out set afterwards gave IDENTICAL numbers — the "
                     "development work had no detectable effect on it."),
            ("warn", "I wrote both the patterns and the held-out set. An independent annotator "
                     "would be stronger evidence."),
        ],
        eyebrow="method",
        footer="Vietnamese perfect score (1.000/1.000) is a DEVELOPMENT number and is deliberately "
               "not the headline.",
    )

    # ---------------------------------------------------------------- 9 grounding
    content_slide(
        prs,
        "What stops the model inventing mental-health advice",
        [
            ("head", "Three mechanisms, in increasing order of strength"),
            ("bullet", "The prompt rule is absolute: the model may rephrase the retrieved material, "
                       "but may not add advice, techniques, services or phone numbers that are not "
                       "in it — even if it believes them true."),
            ("bullet", "Every suggestion cites the chunk it came from, by id. The service checks "
                       "those citations against what was actually retrieved and DISCARDS any the "
                       "model invented."),
            ("good", "If retrieval returns nothing, the generator is not called at all. The system "
                     "says advice is unavailable rather than filling the gap from its own parameters."),
            ("note", "That last one is the difference between a grounded system and a system that "
                     "merely prefers to be grounded."),
        ],
        eyebrow="rag",
        footer="Corpus: 23 curated chunks, multilingual embeddings, k = 4.",
    )

    # ---------------------------------------------------------------- 10 results
    table_slide(
        prs,
        "Main results — one frozen split, unified four-class label",
        ["System", "Accuracy", "Macro-F1"],
        [
            ["Majority class (floor)", "0.3286", "0.1237"],
            ["TF-IDF + Logistic Regression", "0.6857", "0.6816"],
            ["TF-IDF + SVM", "0.6571", "0.6524"],
            ["PhoBERT, fine-tuned", "0.6571", "0.5329"],
            ["LLM zero-shot", "0.5286", "0.5238"],
            ["Proposed (full pipeline)", "—", "not run"],
        ],
        eyebrow="results",
        highlight=1,
        footer="n = 70 · single seed · synthetic data · openai/gpt-oss-120b via Groq. "
               "The classical baseline wins, and slide 14 explains why that is a statement about "
               "the DATA rather than about transformers.",
    )

    # ---------------------------------------------------------------- 11 retrieval
    table_slide(
        prs,
        "The measurement that changed the system",
        ["Query construction", "MRR", "Recall@1"],
        [
            ["Matched lexicon keywords only  (original)", "0.509", "0.344"],
            ["The student's own sentence", "0.778", "0.656"],
            ["Sentence + keywords  (current)", "0.839", "0.719"],
        ],
        eyebrow="rag evaluation",
        highlight=2,
        footer="57 hand-labelled queries · overall MRR 0.787, Recall@5 0.903. The original code threw "
               "the student's sentence away and searched on matched keywords; appending the "
               "questionnaire label hurt every variant tested. The shape was chosen by running six "
               "candidates through the harness, not by intuition.",
    )

    # ---------------------------------------------------------------- 12 latency
    content_slide(
        prs,
        "Latency: the safety check is effectively free",
        [
            ("bullet", "DASS-21 + PSS-10 scoring     0.03 ms  (p50)"),
            ("bullet", "Crisis rule                          0.05 ms"),
            ("bullet", "Lexicon keyword match         0.07 ms"),
            ("bullet", "RAG retrieval, k = 4              28.0 ms"),
            ("bullet", "PhoBERT inference                59.3 ms"),
            ("good", "The entire deterministic pipeline costs under 90 ms at the median."),
            ("good", "Running the safety rule before everything else — including before persistence "
                     "— costs 0.05 ms. There is no performance argument against that ordering."),
            ("note", "Cold start is ≈ 21 s for both models, paid once per process, which is why the "
                     "API loads them lazily rather than in the startup hook. Generation latency and "
                     "token cost are not measured: each sample is a billable request."),
        ],
        eyebrow="performance",
        footer="Thirty runs per stage, CPU only. Figure 4.9: per-stage latency, p50 to p95.",
    )

    # ---------------------------------------------------------------- 13 trust
    content_slide(
        prs,
        "Why these numbers can be trusted",
        [
            ("good", "334 tests, all passing · 83 % coverage on the application package · CI runs "
                     "lint and the full suite."),
            ("good", "Frozen split · seeded generation · language-model responses cached by input "
                     "hash, so a repeated evaluation performs zero API calls and returns identical "
                     "results."),
            ("head", "The part that matters for a research artefact"),
            ("bullet", "No number in the report exists without a script that produced it."),
            ("bullet", "Where something has not been measured, the tooling writes an explicit "
                       "\"NOT RUN\" marker rather than letting a gap look like a zero."),
            ("head", "One example of that discipline paying for itself"),
            ("bullet", "The harness used to count failed model responses and then throw them away. "
                       "It now keeps and classifies them. On the very next run it recorded 32 "
                       "failures — of which 31 were rate-limit refusals and exactly ONE was "
                       "malformed JSON."),
            ("warn", "The report had claimed seven responses \"were not valid JSON\". That claim was "
                     "never evidence-based, and it has been corrected."),
        ],
        eyebrow="reproducibility",
    )

    # ---------------------------------------------------------------- 14 limitation
    content_slide(
        prs,
        "The limitation that matters most",
        [
            ("bullet", "All text is generated from 41 Vietnamese sentence templates."),
            ("good", "The standard leakage control passes perfectly: 466 distinct texts, ZERO "
                     "duplicates across splits."),
            ("bad", "That control is the wrong instrument here. Nearest-neighbour similarity of "
                    "each test item to its closest training item: median 0.799, and 34 of 70 test "
                    "items exceed 0.80 — under three different similarity measures."),
            ("head", "So the model is not being asked to detect stress"),
            ("bullet", "It is being asked to recognise templates it has already seen in a slightly "
                       "different arrangement. Every text-classification figure in this project is a "
                       "pipeline demonstration, not evidence of stress-detection ability."),
            ("note", "It is also the honest explanation for why TF-IDF wins on slide 10: a bag of "
                     "n-grams is exceptionally good at recognising recurring surface forms."),
        ],
        eyebrow="limitations",
        footer="Reproduce with: python scripts/check_leakage.py — it prints the closest train/test "
               "pairs verbatim so the measure can be judged rather than trusted.",
    )

    # ---------------------------------------------------------------- 15 close
    content_slide(
        prs,
        "Contributions, and what comes next",
        [
            ("head", "What this work contributes"),
            ("good", "A layered screening system in which the deterministic, trustworthy components "
                     "run first and can pre-empt the generative ones."),
            ("good", "Crisis-detection evaluation sets in both languages, measured without tuning "
                     "against them, with every error published verbatim."),
            ("good", "A demonstration that exact-duplicate checking is inadequate for "
                     "template-generated corpora, with the measurement to prove it."),
            ("good", "A harness in which a missing measurement LOOKS missing."),
            ("head", "What it does not yet have"),
            ("bad", "Real participants — zero. The ablation, blocked on provider quota rather than "
                    "on code. Faithfulness judging. Confidence intervals."),
            ("note", "That gap is the difference between demonstrating a pipeline and demonstrating "
                     "stress detection. It is where the thesis goes next."),
        ],
        eyebrow="conclusion",
        footer="Thank you — questions welcome.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(TARGET))
    args = parser.parse_args()

    prs = Presentation()
    build(prs)
    out = Path(args.out)
    prs.save(out)
    print(f"Wrote {out} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
