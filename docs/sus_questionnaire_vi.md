# Bảng hỏi SUS (System Usability Scale) — bản tiếng Việt

Đánh giá mức độ dễ sử dụng của ứng dụng sau khi người tham gia hoàn thành một
lượt đánh giá đầy đủ. Mỗi câu trả lời theo thang 5 mức:

**1 — Hoàn toàn không đồng ý · 2 — Không đồng ý · 3 — Trung lập · 4 — Đồng ý · 5 — Hoàn toàn đồng ý**

| # | Phát biểu |
|---|-----------|
| 1 | Tôi nghĩ rằng tôi sẽ muốn sử dụng ứng dụng này thường xuyên. |
| 2 | Tôi thấy ứng dụng này phức tạp một cách không cần thiết. |
| 3 | Tôi thấy ứng dụng này dễ sử dụng. |
| 4 | Tôi nghĩ rằng tôi sẽ cần sự hỗ trợ của người có chuyên môn kỹ thuật mới dùng được ứng dụng này. |
| 5 | Tôi thấy các chức năng trong ứng dụng được kết hợp với nhau một cách hợp lý. |
| 6 | Tôi thấy ứng dụng này có quá nhiều điểm thiếu nhất quán. |
| 7 | Tôi hình dung rằng hầu hết mọi người sẽ học cách dùng ứng dụng này rất nhanh. |
| 8 | Tôi thấy ứng dụng này rất rườm rà, bất tiện khi sử dụng. |
| 9 | Tôi cảm thấy rất tự tin khi sử dụng ứng dụng này. |
| 10 | Tôi cần phải học nhiều thứ trước khi có thể bắt đầu dùng ứng dụng này. |

## Cách chấm điểm (chuẩn Brooke, 1996)

- Câu lẻ (1, 3, 5, 7, 9): *điểm đóng góp = điểm trả lời − 1*
- Câu chẵn (2, 4, 6, 8, 10): *điểm đóng góp = 5 − điểm trả lời*
- **SUS = tổng 10 điểm đóng góp × 2.5** → thang 0–100 (không phải phần trăm).

Chấm tự động: điền câu trả lời vào CSV có cột `respondent_id, q1..q10` rồi chạy

```bash
python -m app.eval.sus_score --csv <file.csv>
```

## Diễn giải điểm (theo Bangor et al., 2008; Sauro & Lewis)

| Khoảng điểm | Diễn giải |
|---|---|
| ≥ 84.1 | Xuất sắc (A) |
| 72.6 – 84.0 | Tốt (B) |
| 62.7 – 72.5 | Khá (C) — quanh mức trung bình 68 |
| 51.7 – 62.6 | Kém (D) |
| < 51.7 | Rất kém (F) |
