"""LangChain assessment chain: evidence -> structured stress assessment.

Input bundle: {raw_text, emotion_result, questionnaire_scores, stress_context,
retrieved_docs}. Output: `LlmAssessment` (predicted level, confidence,
Vietnamese reasoning, 3+ suggestions, risk flags) via a Pydantic output parser.

Privacy: only anonymized, non-identifying fields are ever placed in the
prompt - no student_id, no demographics beyond what the caller passes in the
stress context (which contains no identifiers by schema design).
"""

from __future__ import annotations

import logging

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import get_settings
from app.rag.retriever import RetrievedDoc
from app.schemas.models import EmotionResult, LlmAssessment, StressContextIn

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_VI = """\
Bạn là một trợ lý hỗ trợ sức khỏe tinh thần dành cho sinh viên đại học Việt Nam, \
với giọng điệu ấm áp, thấu cảm và không phán xét.

NHIỆM VỤ: Dựa trên các bằng chứng được cung cấp (chia sẻ của sinh viên, kết quả \
phân tích cảm xúc, điểm các thang đo sàng lọc DASS-21/PSS-10, bối cảnh học tập - \
sinh hoạt, và tài liệu tham khảo), hãy đưa ra đánh giá mức độ căng thẳng học đường.

NGUYÊN TẮC BẮT BUỘC:
1. Bạn KHÔNG phải bác sĩ và KHÔNG được chẩn đoán bệnh. Tuyệt đối không dùng các từ \
như "bạn bị trầm cảm", "bạn mắc rối loạn lo âu". Chỉ mô tả mức độ căng thẳng và \
gợi ý hướng hỗ trợ.
2. Phần giải thích (reasoning_vi) viết bằng tiếng Việt, xưng hô "bạn - mình", \
giọng gần gũi như một người anh/chị đi trước; nêu rõ những bằng chứng nào dẫn đến \
kết luận (ví dụ: điểm DASS-21, từ khóa trong chia sẻ, thiếu ngủ...).
3. Đưa ra ĐÚNG 3 gợi ý hành động (suggestions_vi) cụ thể, khả thi ngay trong tuần, \
ưu tiên dựa trên các tài liệu tham khảo được cung cấp và phù hợp với bối cảnh của \
chính sinh viên này (lịch học, giấc ngủ, nguồn lực hỗ trợ...).
4. Nếu thấy dấu hiệu đáng lo (ngủ quá ít kéo dài, tuyệt vọng, ý nghĩ tiêu cực về \
bản thân), thêm cờ cảnh báo vào risk_flags và khuyến khích tìm hỗ trợ chuyên nghiệp \
trong gợi ý.
5. Mức độ dự đoán (predicted_level) phải là một trong: Low, Moderate, High, Severe. \
Hãy cân nhắc TẤT CẢ bằng chứng; nếu các nguồn mâu thuẫn, giải thích vì sao bạn \
nghiêng về kết luận đã chọn và giảm confidence tương ứng.

{format_instructions}
"""

HUMAN_PROMPT_VI = """\
DỮ LIỆU ĐÁNH GIÁ (ẩn danh):

## 1. Chia sẻ của sinh viên
{raw_text}

## 2. Phân tích cảm xúc tự động (mô hình PhoBERT)
{emotion_summary}

## 3. Kết quả thang đo sàng lọc
{questionnaire_summary}

## 4. Bối cảnh học tập và nguồn lực
{context_summary}

## 5. Tài liệu tham khảo (trích từ cơ sở tri thức)
{retrieved_docs}

Hãy đưa ra đánh giá theo đúng định dạng JSON yêu cầu.
"""


def format_emotion(emotion: EmotionResult | None) -> str:
    if emotion is None:
        return "(không có dữ liệu văn bản)"
    lines = [
        f"- Nhãn cảm xúc chủ đạo: {emotion.emotion_label}",
        f"- Chiều hướng cảm xúc: {emotion.sentiment_polarity.value}",
    ]
    if emotion.model_stress_level is not None:
        lines.append(f"- Mức stress theo mô hình PhoBERT: {emotion.model_stress_level.value}")
    if emotion.stress_keywords:
        lines.append(f"- Từ khóa căng thẳng phát hiện được: {', '.join(emotion.stress_keywords)}")
    if emotion.emotion_scores:
        scores = ", ".join(f"{k}={v:.2f}" for k, v in emotion.emotion_scores.items())
        lines.append(f"- Điểm chi tiết: {scores}")
    return "\n".join(lines)


def format_questionnaires(dass_result: dict | None, pss_result: dict | None) -> str:
    if not dass_result and not pss_result:
        return "(chưa làm thang đo nào)"
    lines: list[str] = []
    if dass_result:
        lines.append("DASS-21 (điểm đã nhân đôi, phân loại chính thức):")
        for key, label in (("depression", "Trầm cảm"), ("anxiety", "Lo âu"), ("stress", "Căng thẳng")):
            sub = dass_result[key]
            lines.append(f"- {label}: {sub['score']} điểm — mức {sub['severity']}")
    if pss_result:
        lines.append(
            f"PSS-10: {pss_result['total_score']}/40 điểm — mức cảm nhận stress: {pss_result['category']}"
        )
    return "\n".join(lines)


def format_context(context: StressContextIn | None) -> str:
    if context is None:
        return "(không có thông tin bối cảnh)"
    lines: list[str] = []
    if context.study_hours_per_week is not None:
        lines.append(f"- Giờ học/tuần: {context.study_hours_per_week:g}")
    if context.is_exam_period is not None:
        lines.append(f"- Đang trong mùa thi: {'có' if context.is_exam_period else 'không'}")
    if context.assignment_workload is not None:
        lines.append(f"- Khối lượng bài tập (1-5): {context.assignment_workload}")
    if context.gpa is not None:
        lines.append(f"- GPA: {context.gpa:g}")
    if context.academic_pressure_source:
        lines.append(f"- Nguồn áp lực học tập: {', '.join(context.academic_pressure_source)}")
    if context.part_time_job is not None:
        lines.append(f"- Làm thêm: {'có' if context.part_time_job else 'không'}")
    if context.financial_stress is not None:
        lines.append(f"- Áp lực tài chính (1-5): {context.financial_stress}")
    if context.sleep_hours_avg is not None:
        lines.append(f"- Giờ ngủ trung bình/đêm: {context.sleep_hours_avg:g}")
    if context.sleep_quality is not None:
        lines.append(f"- Chất lượng giấc ngủ (1-5): {context.sleep_quality}")
    if context.social_support_level is not None:
        lines.append(f"- Mức hỗ trợ xã hội (1-5): {context.social_support_level}")
    if context.extracurricular_hours is not None:
        lines.append(f"- Giờ ngoại khóa/tuần: {context.extracurricular_hours:g}")
    if context.coping_strategies:
        lines.append(f"- Cách ứng phó hiện có: {', '.join(context.coping_strategies)}")
    if context.has_sought_help is not None:
        lines.append(f"- Đã từng tìm hỗ trợ tâm lý: {'có' if context.has_sought_help else 'chưa'}")
    if context.support_resource_awareness is not None:
        lines.append(
            f"- Biết đến các nguồn hỗ trợ của trường: {'có' if context.support_resource_awareness else 'chưa'}"
        )
    return "\n".join(lines) if lines else "(không có thông tin bối cảnh)"


def format_retrieved_docs(docs: list[RetrievedDoc]) -> str:
    if not docs:
        return "(không có tài liệu tham khảo)"
    blocks = []
    for i, doc in enumerate(docs, start=1):
        blocks.append(f"[Tài liệu {i} — {doc.source} / {doc.heading}]\n{doc.text}")
    return "\n\n".join(blocks)


def get_parser() -> PydanticOutputParser:
    return PydanticOutputParser(pydantic_object=LlmAssessment)


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
        )

    parser = get_parser()
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT_VI), ("human", HUMAN_PROMPT_VI)]
    ).partial(format_instructions=parser.get_format_instructions())
    return prompt | llm | parser


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
            "raw_text": raw_text.strip() if raw_text and raw_text.strip() else "(không có chia sẻ)",
            "emotion_summary": format_emotion(emotion),
            "questionnaire_summary": format_questionnaires(dass_result, pss_result),
            "context_summary": format_context(stress_context),
            "retrieved_docs": format_retrieved_docs(retrieved_docs),
        }
    )
