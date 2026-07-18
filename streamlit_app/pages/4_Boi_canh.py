"""Stress context page: academic stressors, lifestyle, coping resources."""

import streamlit as st

from utils import require_consent, show_disclaimer

st.set_page_config(page_title="Bối cảnh & nguồn lực", page_icon="🎒", layout="wide")
require_consent()

st.title("🎒 Bối cảnh học tập & nguồn lực của bạn")
st.markdown("Những thông tin này giúp hệ thống đưa ra gợi ý sát với hoàn cảnh của bạn hơn. Tất cả đều **không bắt buộc**.")

ctx = st.session_state.stress_context

with st.form("context_form"):
    st.subheader("📚 Học tập")
    col1, col2 = st.columns(2)
    with col1:
        study_hours = st.slider("Số giờ học mỗi tuần (cả trên lớp và tự học)", 0, 80, ctx.get("study_hours_per_week", 25))
        workload = st.select_slider(
            "Khối lượng bài tập/đồ án hiện tại",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("assignment_workload", 3),
            format_func=lambda x: {1: "1 — Rất nhẹ", 2: "2 — Nhẹ", 3: "3 — Vừa", 4: "4 — Nặng", 5: "5 — Rất nặng"}[x],
        )
        exam_period = st.toggle("Đang trong mùa thi / tuần cao điểm", value=ctx.get("is_exam_period", False))
    with col2:
        gpa_known = st.toggle("Khai báo GPA", value=ctx.get("gpa") is not None)
        gpa = st.number_input("GPA hiện tại (thang 4)", 0.0, 4.0, ctx.get("gpa") or 3.0, 0.1, disabled=not gpa_known)
        pressure_sources = st.multiselect(
            "Nguồn áp lực học tập chính",
            ["Thi cử", "Điểm số/GPA", "Đồ án/bài tập", "Kỳ vọng gia đình", "So sánh với bạn bè",
             "Tiếng Anh/chuẩn đầu ra", "Định hướng nghề nghiệp", "Nợ môn/học lại"],
            default=ctx.get("academic_pressure_source", []),
        )

    st.subheader("🌙 Sinh hoạt")
    col3, col4 = st.columns(2)
    with col3:
        sleep_hours = st.slider("Số giờ ngủ trung bình mỗi đêm", 3.0, 12.0, ctx.get("sleep_hours_avg", 7.0), 0.5)
        sleep_quality = st.select_slider(
            "Chất lượng giấc ngủ",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("sleep_quality", 3),
            format_func=lambda x: {1: "1 — Rất kém", 2: "2 — Kém", 3: "3 — Bình thường", 4: "4 — Tốt", 5: "5 — Rất tốt"}[x],
        )
    with col4:
        part_time = st.toggle("Đang làm thêm", value=ctx.get("part_time_job", False))
        financial = st.select_slider(
            "Mức áp lực tài chính",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("financial_stress", 2),
            format_func=lambda x: {1: "1 — Không đáng kể", 2: "2 — Ít", 3: "3 — Vừa", 4: "4 — Nhiều", 5: "5 — Rất nhiều"}[x],
        )

    st.subheader("🤝 Nguồn lực ứng phó")
    col5, col6 = st.columns(2)
    with col5:
        social_support = st.select_slider(
            "Mức hỗ trợ từ gia đình/bạn bè khi bạn gặp khó khăn",
            options=[1, 2, 3, 4, 5],
            value=ctx.get("social_support_level", 3),
            format_func=lambda x: {1: "1 — Rất ít", 2: "2 — Ít", 3: "3 — Vừa", 4: "4 — Nhiều", 5: "5 — Rất nhiều"}[x],
        )
        extracurricular = st.slider("Giờ hoạt động ngoại khóa/thể thao mỗi tuần", 0.0, 30.0, ctx.get("extracurricular_hours", 3.0), 0.5)
    with col6:
        coping = st.multiselect(
            "Bạn thường làm gì khi căng thẳng?",
            ["Tập thể dục/chơi thể thao", "Nghe nhạc/xem phim", "Trò chuyện với bạn bè",
             "Trò chuyện với gia đình", "Chơi game", "Ngủ", "Viết nhật ký", "Thiền/thư giãn",
             "Đi chơi/du lịch", "Ăn uống"],
            default=ctx.get("coping_strategies", []),
        )
        sought_help = st.toggle("Đã từng tìm đến hỗ trợ tâm lý chuyên nghiệp", value=ctx.get("has_sought_help", False))
        aware = st.toggle("Biết về phòng tham vấn tâm lý của trường", value=ctx.get("support_resource_awareness", False))

    submitted = st.form_submit_button("Lưu bối cảnh 💾", type="primary")

if submitted:
    st.session_state.stress_context = {
        "study_hours_per_week": float(study_hours),
        "is_exam_period": exam_period,
        "assignment_workload": workload,
        "gpa": float(gpa) if gpa_known else None,
        "academic_pressure_source": pressure_sources,
        "part_time_job": part_time,
        "financial_stress": financial,
        "sleep_hours_avg": float(sleep_hours),
        "sleep_quality": sleep_quality,
        "social_support_level": social_support,
        "extracurricular_hours": float(extracurricular),
        "coping_strategies": coping,
        "has_sought_help": sought_help,
        "support_resource_awareness": aware,
    }
    st.success("Đã lưu! Bạn đã sẵn sàng xem kết quả.")

if st.session_state.stress_context:
    st.page_link("pages/5_Ket_qua.py", label="👉 Tiếp tục: Xem kết quả", icon="📊")

show_disclaimer()
