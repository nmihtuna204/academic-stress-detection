"""LangChain assessment chain: evidence -> structured stress assessment.

Input bundle: {raw_text, emotion_result, questionnaire_scores, stress_context,
retrieved_docs}. Output: `LlmAssessment` (predicted level, confidence,
reasoning, 3+ suggestions, risk flags) via a Pydantic output parser.

Privacy: only anonymized, non-identifying fields are ever placed in the
prompt - no student_id, no demographics beyond what the caller passes in the
stress context (which contains no identifiers by schema design).
"""

from __future__ import annotations

import logging
import re

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.config import get_settings
from app.rag.retriever import RetrievedDoc
from app.schemas.models import EmotionResult, LlmAssessment, StressContextIn

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a mental-health support assistant for university students, with a warm, \
empathetic and non-judgmental tone.

TASK: Based on the evidence provided (the student's own words, automated emotion \
analysis, DASS-21/PSS-10 screening scores, academic and lifestyle context, and \
reference material), give an assessment of their academic stress level.

MANDATORY RULES:
1. You are NOT a clinician and must NOT diagnose. Never use phrasing such as \
"you have depression" or "you have an anxiety disorder". Only describe the level \
of stress and point towards sources of support.
2. Write the explanation (reasoning) in English, addressing the student directly \
as "you", in the voice of a supportive senior peer. State clearly which evidence \
led to your conclusion (e.g. DASS-21 scores, keywords in what they wrote, lack \
of sleep).
3. Give 3 concrete action suggestions (suggestions) that are achievable within \
the coming week and matched to this student's own context (study schedule, sleep, \
support resources). If the reference material in section 5 supports fewer than 3, \
give only those it supports - rule 4 outranks this count, and a short grounded \
answer is correct where a padded one is not.
4. GROUNDING - this rule is absolute. Every suggestion must be supported by the \
reference material in section 5 of the input. Do NOT introduce advice, techniques, \
services, phone numbers or clinical claims that are not present in that material, \
even if you believe them to be true. You may rephrase the material to fit this \
student, but you may not add to it. If section 5 is empty or does not cover what \
this student needs, say so plainly in the reasoning and give only the suggestions \
the material does support, rather than filling the gap from your own knowledge.
5. For every suggestion, cite the reference documents you drew it from. Populate \
the citations field with the exact document identifiers shown in section 5, in the \
form `filename.md::N`. Cite only identifiers that actually appear in section 5. If \
you could not ground a suggestion in any document, do not invent a citation.
6. If you see concerning signs (sustained lack of sleep, hopelessness, negative \
thoughts about self-worth), add a flag to risk_flags and encourage seeking \
professional support in the suggestions.
7. The predicted level (predicted_level) must be one of: Low, Moderate, High, \
Severe. Weigh ALL the evidence; if sources conflict, explain why you lean towards \
the conclusion you chose and lower the confidence accordingly.

{format_instructions}
"""

HUMAN_PROMPT = """\
ASSESSMENT DATA (anonymized):

## 1. What the student wrote
{raw_text}

## 2. Automated text analysis
{emotion_summary}

## 3. Screening scale results
{questionnaire_summary}

## 4. Academic context and resources
{context_summary}

## 5. Reference material (retrieved from the knowledge base)
{retrieved_docs}

Give your assessment in exactly the required JSON format.
"""


def format_emotion(emotion: EmotionResult | None) -> str:
    """Render the text-analysis block for the prompt.

    The absence of a classifier reading is stated explicitly rather than left
    as a missing line. PhoBERT only runs on Vietnamese input (see
    `app.nlp.emotion.analyze`), so on English text this block carries lexicon
    signal alone - and a reader given four bullet points with no model line has
    no way to tell "the model saw no stress" from "the model never ran". Those
    mean opposite things, and the generator must not confuse them.
    """
    if emotion is None:
        return "(no free-text data)"
    lines = [
        f"- Dominant emotion label: {emotion.emotion_label}",
        f"- Sentiment polarity: {emotion.sentiment_polarity.value}",
    ]
    if emotion.model_stress_level is not None:
        lines.append(f"- Stress level per the PhoBERT classifier: {emotion.model_stress_level.value}")
    else:
        lines.append(
            "- PhoBERT classifier: DID NOT RUN (it is Vietnamese-only and this text was not "
            "detected as Vietnamese). The absence of a model reading is not evidence of low "
            "stress; weigh the questionnaire and the student's own words instead."
        )
    if emotion.stress_keywords:
        lines.append(f"- Stress keywords detected: {', '.join(emotion.stress_keywords)}")
    if emotion.emotion_scores:
        scores = ", ".join(f"{k}={v:.2f}" for k, v in emotion.emotion_scores.items())
        lines.append(f"- Detailed scores: {scores}")
    return "\n".join(lines)


def format_questionnaires(dass_result: dict | None, pss_result: dict | None) -> str:
    if not dass_result and not pss_result:
        return "(no questionnaire completed)"
    lines: list[str] = []
    if dass_result:
        lines.append("DASS-21 (doubled scores, official classification):")
        for key, label in (("depression", "Depression"), ("anxiety", "Anxiety"), ("stress", "Stress")):
            sub = dass_result[key]
            lines.append(f"- {label}: {sub['score']} points — {sub['severity']}")
    if pss_result:
        lines.append(
            f"PSS-10: {pss_result['total_score']}/40 points — perceived stress: {pss_result['category']}"
        )
    return "\n".join(lines)


def format_context(context: StressContextIn | None) -> str:
    if context is None:
        return "(no context information)"
    lines: list[str] = []
    if context.study_hours_per_week is not None:
        lines.append(f"- Study hours/week: {context.study_hours_per_week:g}")
    if context.is_exam_period is not None:
        lines.append(f"- Currently in exam period: {'yes' if context.is_exam_period else 'no'}")
    if context.assignment_workload is not None:
        lines.append(f"- Assignment workload (1-5): {context.assignment_workload}")
    if context.gpa is not None:
        lines.append(f"- GPA: {context.gpa:g}")
    if context.academic_pressure_source:
        lines.append(f"- Sources of academic pressure: {', '.join(context.academic_pressure_source)}")
    if context.part_time_job is not None:
        lines.append(f"- Part-time job: {'yes' if context.part_time_job else 'no'}")
    if context.financial_stress is not None:
        lines.append(f"- Financial pressure (1-5): {context.financial_stress}")
    if context.sleep_hours_avg is not None:
        lines.append(f"- Average sleep hours/night: {context.sleep_hours_avg:g}")
    if context.sleep_quality is not None:
        lines.append(f"- Sleep quality (1-5): {context.sleep_quality}")
    if context.social_support_level is not None:
        lines.append(f"- Social support level (1-5): {context.social_support_level}")
    if context.extracurricular_hours is not None:
        lines.append(f"- Extracurricular hours/week: {context.extracurricular_hours:g}")
    if context.coping_strategies:
        lines.append(f"- Existing coping strategies: {', '.join(context.coping_strategies)}")
    if context.has_sought_help is not None:
        lines.append(
            f"- Has sought psychological support before: {'yes' if context.has_sought_help else 'no'}"
        )
    if context.support_resource_awareness is not None:
        lines.append(
            f"- Aware of university support resources: {'yes' if context.support_resource_awareness else 'no'}"
        )
    return "\n".join(lines) if lines else "(no context information)"


def format_retrieved_docs(docs: list[RetrievedDoc]) -> str:
    """Render the retrieved passages, each labelled with the id the model must cite.

    The chunk id is the citation handle, so it leads each block. Rule 5 of the
    system prompt tells the model to cite exactly these strings, which is what
    makes the returned citations checkable against what was actually retrieved.
    """
    if not docs:
        return (
            "(no reference material was retrieved for this student — per rule 4, do not "
            "substitute your own knowledge)"
        )
    blocks = []
    for doc in docs:
        identifier = doc.chunk_id or f"{doc.source}::?"
        blocks.append(f"[{identifier}] {doc.source} / {doc.heading}\n{doc.text}")
    return "\n\n".join(blocks)


def get_parser() -> PydanticOutputParser:
    return PydanticOutputParser(pydantic_object=LlmAssessment)


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def extract_json_object(message) -> str:
    """Reduce a chat reply to the JSON object inside it, for a strict parser.

    `PydanticOutputParser` already tolerates more than it looks like it does:
    measured against it directly, markdown fences (```json or bare), trailing
    prose after the object, and prose either side of a *fenced* object all
    parse fine. Two shapes do not, and both raise `OutputParserException` that
    costs the entire assessment:

        "Here is my assessment:" + JSON      unfenced preamble
        "<think>...</think>" + JSON          reasoning-model scratchpad

    The second is the one that matters here. The 2026-09-08 evaluation ran on
    `openai/gpt-oss-120b`, a reasoning-tuned model, and lost 7/70 full-pipeline
    responses and 9/30 ablation responses to parse failures, each falling back
    to a fixed "Moderate" label. Those replies were not retained (the failure
    path returned before writing the cache), so this is the probable cause
    rather than a confirmed one - `_full_one` now records failing replies so
    the next run settles it. Some failures are certainly genuine malformations
    that no unwrapping fixes; one observed example was `"confidence": 0. nine`.

    Nothing is repaired here, only unwrapped: a reply with no JSON object in it
    is passed through untouched so the parser still raises on real garbage.
    """
    content = getattr(message, "content", message)
    if isinstance(content, list):
        # Some providers return content blocks rather than a plain string.
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    text = _THINK_RE.sub("", str(content)).strip()
    text = _FENCE_RE.sub("", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else text


def build_chain(llm=None):
    """Build the LCEL chain prompt | llm | parser.

    Args:
        llm: optional LangChain chat model (tests inject a fake); defaults to
            ChatOpenAI configured from settings.
    """
    settings = get_settings()
    if llm is None:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            api_key=settings.openai_api_key,
            # None keeps the OpenAI default; a value routes to any
            # OpenAI-compatible provider (see Settings.openai_base_url).
            base_url=settings.openai_base_url or None,
            # Rate limits are pacing, not failure; retry with backoff.
            max_retries=settings.llm_max_retries,
        )

    parser = get_parser()
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
    ).partial(format_instructions=parser.get_format_instructions())
    return prompt | llm | RunnableLambda(extract_json_object) | parser


async def assess(
    raw_text: str | None,
    emotion: EmotionResult | None,
    dass_result: dict | None,
    pss_result: dict | None,
    stress_context: StressContextIn | None,
    retrieved_docs: list[RetrievedDoc],
    llm=None,
) -> LlmAssessment:
    """Run the assessment chain asynchronously and return structured output."""
    chain = build_chain(llm=llm)
    return await chain.ainvoke(
        {
            "raw_text": raw_text.strip() if raw_text and raw_text.strip() else "(nothing written)",
            "emotion_summary": format_emotion(emotion),
            "questionnaire_summary": format_questionnaires(dass_result, pss_result),
            "context_summary": format_context(stress_context),
            "retrieved_docs": format_retrieved_docs(retrieved_docs),
        }
    )
