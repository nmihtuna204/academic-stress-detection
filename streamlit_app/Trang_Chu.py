"""Home page: introduction and informed consent (required before any data entry)."""

import streamlit as st

from utils import init_state, show_disclaimer

st.set_page_config(
    page_title="Đánh giá stress học đường",
    page_icon="🎓",
    layout="wide",
)

init_state()

st.title("🎓 Đánh giá mức độ căng thẳng học đường")
st.caption("Dành cho sinh viên đại học Việt Nam — Đồ án tiền tốt nghiệp (Pre-thesis)")

show_disclaimer()

st.markdown(
    """
### Ứng dụng này làm gì?

1. **Chia sẻ cảm nghĩ** — bạn viết tự do về tuần vừa qua (tiếng Việt).
2. **Hai bảng hỏi chuẩn** — DASS-21 và PSS-10, dùng rộng rãi trong nghiên cứu tâm lý.
3. **Bối cảnh học tập** — lịch học, giấc ngủ, nguồn lực hỗ trợ của bạn.
4. **Kết quả** — hệ thống kết hợp mô hình ngôn ngữ (AI) với điểm bảng hỏi để ước lượng
   mức độ căng thẳng, giải thích lý do và gợi ý 3 hành động phù hợp với bạn.

### Dữ liệu của bạn được bảo vệ thế nào?

- Ứng dụng **không thu thập họ tên, MSSV hay thông tin định danh nào** — mỗi phiên được
  gán một mã ẩn danh ngẫu nhiên.
- Nội dung bạn chia sẻ chỉ dùng để phân tích trong ứng dụng và lưu trữ ẩn danh phục vụ
  nghiên cứu.
- Bạn có thể dừng tham gia bất cứ lúc nào bằng cách đóng trang.
"""
)

st.divider()
st.subheader("📋 Phiếu đồng ý tham gia")

with st.form("consent_form"):
    st.markdown(
        """
Tôi xác nhận rằng:
- Tôi từ 18 tuổi trở lên và là sinh viên đại học/cao đẳng.
- Tôi hiểu đây là **công cụ sàng lọc, không phải chẩn đoán y khoa**.
- Tôi tự nguyện tham gia và đồng ý cho lưu trữ dữ liệu **ẩn danh** phục vụ nghiên cứu.
"""
    )
    agreed = st.checkbox("Tôi đã đọc và **đồng ý** với các nội dung trên.")

    st.markdown("**Thông tin nền (không bắt buộc, phục vụ thống kê):**")
    col1, col2, col3 = st.columns(3)
    with col1:
        age = st.number_input("Tuổi", min_value=15, max_value=80, value=20)
        gender = st.selectbox("Giới tính", ["Nam", "Nữ", "Khác"], index=None, placeholder="Chọn...")
    with col2:
        year = st.selectbox("Sinh viên năm", [1, 2, 3, 4, 5, 6], index=None, placeholder="Chọn...")
        major = st.text_input("Ngành học", placeholder="VD: Công nghệ thông tin")
    with col3:
        university = st.text_input("Trường", placeholder="VD: ĐH Bách Khoa")

    submitted = st.form_submit_button("Bắt đầu ✅", type="primary")

if submitted:
    if not agreed:
        st.error("Bạn cần tick vào ô đồng ý để tiếp tục.")
    else:
        st.session_state.consented = True
        st.session_state.profile = {
            "age": int(age),
            "gender": gender,
            "year_of_study": int(year) if year else None,
            "major": major or None,
            "university": university or None,
        }
        st.success("Cảm ơn bạn! Hãy chuyển sang trang **Nhập cảm nghĩ** ở thanh bên trái. 👈")

if st.session_state.consented:
    st.page_link("pages/1_Nhap_cam_nghi.py", label="👉 Tiếp tục: Nhập cảm nghĩ", icon="📝")
