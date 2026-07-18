"""Free-text entry page: the student's own words about their week."""

import streamlit as st

from utils import require_consent, show_disclaimer

st.set_page_config(page_title="Nhập cảm nghĩ", page_icon="📝", layout="wide")
require_consent()

st.title("📝 Chia sẻ cảm nghĩ của bạn")
st.markdown(
    """
Hãy viết tự do vài dòng (tiếng Việt) về **tuần vừa qua** của bạn: việc học, giấc ngủ,
cảm xúc, những điều khiến bạn lo lắng hoặc vui vẻ. Càng chi tiết, kết quả phân tích
càng sát với bạn.

*Gợi ý: Bạn đang ôn thi môn gì? Ngủ mấy tiếng? Có deadline nào dồn dập không?
Điều gì khiến bạn bận tâm nhất lúc này?*
"""
)

text = st.text_area(
    "Cảm nghĩ của bạn",
    value=st.session_state.raw_text,
    height=220,
    max_chars=4000,
    placeholder="Tuần này mình...",
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Lưu lại 💾", type="primary"):
        st.session_state.raw_text = text.strip()
        if st.session_state.raw_text:
            st.success("Đã lưu! Bạn có thể làm tiếp bảng hỏi DASS-21.")
        else:
            st.info("Bạn có thể bỏ trống phần này và chỉ làm bảng hỏi.")

if st.session_state.raw_text:
    st.caption(f"Đã lưu {len(st.session_state.raw_text)} ký tự.")

st.divider()
st.page_link("pages/2_DASS_21.py", label="👉 Tiếp tục: Bảng hỏi DASS-21", icon="📋")
show_disclaimer()
