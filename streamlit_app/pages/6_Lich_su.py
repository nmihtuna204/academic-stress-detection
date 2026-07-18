"""History page: previous assessments for the current anonymized session id."""

import pandas as pd
import streamlit as st

from utils import (
    DASS_SEVERITY_VI,
    LEVEL_LABELS_VI,
    PSS_CATEGORY_VI,
    api_get,
    require_consent,
    show_disclaimer,
)

st.set_page_config(page_title="Lịch sử", page_icon="🕘", layout="wide")
require_consent()

st.title("🕘 Lịch sử đánh giá")

student_id = st.session_state.student_id
if not student_id:
    st.info(
        "Bạn chưa có lần đánh giá nào trong phiên này. Mã ẩn danh chỉ được tạo sau khi "
        "bạn chạy **Phân tích** lần đầu ở trang Kết quả."
    )
    st.page_link("pages/5_Ket_qua.py", label="Đi tới trang Kết quả", icon="📊")
    st.stop()

st.caption(f"Mã ẩn danh của bạn trong phiên này: `{student_id}`")

history = api_get(f"/history/{student_id}")
if history is None:
    st.info("Chưa tìm thấy dữ liệu cho mã này.")
    st.stop()

predictions = history.get("predictions", [])
responses = history.get("questionnaire_responses", [])
entries = history.get("text_entries", [])

if predictions:
    st.subheader("Các lần đánh giá")
    rows = []
    for p in predictions:
        rows.append(
            {
                "Thời điểm": p["created_at"][:16].replace("T", " "),
                "Kết quả AI": LEVEL_LABELS_VI.get(p["llm_predicted_label"], p["llm_predicted_label"] or "—"),
                "Theo bảng hỏi": LEVEL_LABELS_VI.get(p["ground_truth_label"], p["ground_truth_label"] or "—"),
                "Độ tin cậy": f"{p['llm_confidence']:.0%}" if p["llm_confidence"] is not None else "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

if responses:
    st.subheader("Điểm bảng hỏi qua các lần")
    rows = []
    for r in responses:
        rows.append(
            {
                "Thời điểm": r["created_at"][:16].replace("T", " "),
                "Trầm cảm (DASS)": f"{r['depression_score']} — {DASS_SEVERITY_VI.get(r['depression_level'], '')}" if r["depression_score"] is not None else "—",
                "Lo âu (DASS)": f"{r['anxiety_score']} — {DASS_SEVERITY_VI.get(r['anxiety_level'], '')}" if r["anxiety_score"] is not None else "—",
                "Căng thẳng (DASS)": f"{r['stress_score']} — {DASS_SEVERITY_VI.get(r['stress_level_dass'], '')}" if r["stress_score"] is not None else "—",
                "PSS-10": f"{r['pss_total_score']} — {PSS_CATEGORY_VI.get(r['pss_stress_category'], '')}" if r["pss_total_score"] is not None else "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

if entries:
    with st.expander(f"📝 Cảm nghĩ đã chia sẻ ({len(entries)})"):
        for e in entries:
            st.markdown(f"**{e['timestamp'][:16].replace('T', ' ')}** — {e['raw_text']}")
            if e.get("stress_keywords"):
                st.caption("Từ khóa: " + ", ".join(e["stress_keywords"]))
            st.divider()

if not (predictions or responses or entries):
    st.info("Chưa có dữ liệu nào được lưu.")

show_disclaimer()
