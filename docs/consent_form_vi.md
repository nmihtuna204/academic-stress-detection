# PHIẾU THÔNG TIN VÀ ĐỒNG Ý THAM GIA NGHIÊN CỨU

**Tên đề tài:** Hệ thống hỗ trợ sàng lọc mức độ căng thẳng học đường ở sinh viên
đại học Việt Nam dựa trên mô hình ngôn ngữ lớn

**Người thực hiện:** [Họ tên sinh viên thực hiện đề tài] — [Khoa/Trường]
**Giảng viên hướng dẫn:** [Họ tên GVHD]
**Liên hệ:** [email liên hệ của nhóm nghiên cứu] — [số điện thoại nếu có]

---

## 1. Mục đích nghiên cứu

Nghiên cứu này xây dựng và đánh giá một ứng dụng hỗ trợ sinh viên **tự nhìn nhận
mức độ căng thẳng trong học tập**. Dữ liệu bạn cung cấp được dùng để đánh giá độ
chính xác và tính hữu ích của hệ thống, phục vụ đồ án tốt nghiệp/tiền tốt nghiệp.

## 2. Đây KHÔNG phải công cụ chẩn đoán y khoa

Kết quả mà ứng dụng đưa ra **chỉ mang tính sàng lọc, tham khảo và tự nhìn nhận**.
Ứng dụng không chẩn đoán bệnh, không thay thế bác sĩ hay chuyên gia tâm lý, và
không đưa ra bất kỳ quyết định điều trị nào. Nếu kết quả khiến bạn lo lắng, hãy
tìm đến phòng tham vấn tâm lý của trường hoặc cơ sở y tế chuyên khoa.

## 3. Bạn sẽ làm gì khi tham gia?

- Viết vài dòng chia sẻ cảm nghĩ về tuần vừa qua (tiếng Việt, tự do).
- Trả lời hai bảng hỏi chuẩn: DASS-21 (21 câu) và PSS-10 (10 câu).
- Cung cấp một số thông tin về bối cảnh học tập, sinh hoạt (không bắt buộc).
- Tổng thời gian dự kiến: **10–15 phút**.

## 4. Dữ liệu nào được thu thập, và được bảo vệ ra sao?

- **Không thu thập** họ tên, mã số sinh viên, số điện thoại, email, địa chỉ hay
  bất kỳ thông tin định danh trực tiếp nào.
- Mỗi người tham gia được gán một **mã ẩn danh ngẫu nhiên** (UUID); mọi dữ liệu
  chỉ gắn với mã này. Không ai — kể cả nhóm nghiên cứu — truy ngược được mã về
  danh tính của bạn.
- Nội dung chia sẻ có thể được gửi (dưới dạng ẩn danh) đến dịch vụ mô hình ngôn
  ngữ của **bên thứ ba đặt tại Hoa Kỳ** để phân tích. Không thông tin định danh
  nào đi kèm. Tại thời điểm triển khai hiện tại, dịch vụ đó là **Groq**
  (`api.groq.com`), chạy mô hình `gpt-oss-120b`. Nếu nhà cung cấp thay đổi, màn
  hình đồng ý trong ứng dụng sẽ tự hiển thị tên nhà cung cấp đang thực sự nhận
  dữ liệu — xem `llm_provider_identity()` trong `app/config.py`.
- Dữ liệu được lưu trên máy chủ của nhóm nghiên cứu, chỉ nhóm nghiên cứu và GVHD
  truy cập được, và chỉ dùng cho mục đích của đề tài này.

## 5. Lưu trữ và xóa dữ liệu

- Dữ liệu ẩn danh được lưu tối đa **12 tháng** sau khi bảo vệ đồ án, sau đó xóa
  vĩnh viễn.
- Kết quả công bố (nếu có) chỉ ở dạng thống kê tổng hợp, không thể nhận ra bất
  kỳ cá nhân nào.

## 6. Tính tự nguyện và quyền rút lui

- Việc tham gia là **hoàn toàn tự nguyện**. Bạn có thể dừng bất cứ lúc nào, ở
  bất kỳ bước nào, mà không cần nêu lý do và không chịu bất kỳ bất lợi nào.
- Nếu muốn xóa dữ liệu đã gửi, hãy liên hệ nhóm nghiên cứu kèm **mã ẩn danh**
  hiển thị trong ứng dụng (đây là cách duy nhất xác định được bản ghi của bạn).

## 7. Rủi ro và quy trình hỗ trợ khủng hoảng

Một số câu hỏi liên quan đến cảm xúc tiêu cực và có thể gợi lại trải nghiệm khó
chịu. Nếu trong quá trình tham gia:

- Ứng dụng nhận thấy dấu hiệu nguy cơ (ví dụ ý nghĩ tự làm hại bản thân), nó sẽ
  **dừng hiển thị kết quả phân tích** và hiển thị ngay thông tin hỗ trợ:
  - Đường dây nóng Ngày Mai: **096 306 1414**
  - Tổng đài quốc gia: **111** (miễn phí, 24/7)
  - Cấp cứu y tế: **115**
- Bạn cũng có thể liên hệ phòng tham vấn tâm lý của trường mình bất cứ lúc nào.
- Người thực hiện đề tài **không phải chuyên gia lâm sàng**; quy trình trên là
  chuyển hướng đến kênh hỗ trợ phù hợp, không phải can thiệp y tế.

## 8. Xác nhận đồng ý

Bằng việc tick vào ô "Tôi đồng ý" trong ứng dụng, bạn xác nhận rằng:

1. Bạn từ 18 tuổi trở lên và đang là sinh viên đại học/cao đẳng.
2. Bạn đã đọc và hiểu các thông tin trên.
3. Bạn hiểu đây là công cụ sàng lọc, không phải chẩn đoán.
4. Bạn tự nguyện đồng ý tham gia và cho phép lưu trữ dữ liệu **ẩn danh** cho
   mục đích nghiên cứu nêu trên.

*Phiếu này được hiển thị trong ứng dụng trước khi thu thập bất kỳ dữ liệu nào;
người tham gia có thể lưu lại một bản để đối chiếu.*
