# Runbook — chạy project trơn tru cho buổi bảo vệ

Mọi lệnh chạy từ thư mục gốc project, trong **PowerShell**.
Mỗi bước dưới đây đã được chạy thật và xác minh ngày 2026-09-09.

---

## 0. Kiểm tra môi trường (chỉ làm lần đầu / máy mới)

```powershell
python --version                    # cần 3.11+  (máy này: 3.13)
python -c "import fastapi, streamlit, torch, chromadb; print('deps OK')"
```

Nếu thiếu package:

```powershell
pip install --user -r requirements.txt
```

Kiểm tra knowledge base đã nạp vào Chroma chưa (**phải là 23**):

```powershell
python -c "import sys; sys.path.insert(0,'.'); from app.rag.store import get_collection; print('chunks:', get_collection().count())"
```

Nếu ra `0`, nạp lại:

```powershell
python -m app.rag.ingest
```

---

## 1. Dọn cổng cũ (tránh port đã bị chiếm)

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8501 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## 2. Khởi động 2 tiến trình — **hai cửa sổ PowerShell riêng**

**Cửa sổ 1 — API (FastAPI):**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Đợi tới khi thấy `Application startup complete.`

**Cửa sổ 2 — giao diện (Streamlit):**

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m streamlit run streamlit_app/Home.py --server.port 8501
```

---

## 3. ⚠️ WARM — bước quan trọng nhất, đừng bỏ

Request đầu tiên phải nạp PhoBERT (~8s) + embedder (~11s) = **~25 giây màn hình trắng**.
Đốt nó ở đây, không đốt trên sân khấu.

**Cửa sổ 3:**

```powershell
python scripts/warm.py
```

**Kết quả mong đợi** (lần đầu dòng `health` sẽ mất ~25s — đó là bình thường):

```
  [ok]   health              0.0s   {'status': 'ok', ..., 'knowledge_chunks': 23}
  [ok]   PhoBERT + scoring   2.7s   headline label: High
  [ok]   retrieval                   4 passages
  [ok]   generation                  advice present, citations verified

  second health call: 0.03s  (warm)
Ready.
```

Script tự kiểm tra và **báo lỗi rõ ràng** nếu:

- không kết nối được API → nhắc bật uvicorn
- `knowledge_chunks: 0` → nhắc chạy `python -m app.rag.ingest`
- `[WARN] generation ... NOT available` → hết quota Groq, xem §6
- `second health call` vẫn chậm → chưa thật sự warm

---

## 4. Kiểm tra trước khi trình bày

```powershell
curl.exe -s http://127.0.0.1:8000/health
curl.exe -s http://127.0.0.1:8501/_stcore/health
```

Mong đợi: `{"status":"ok",...,"knowledge_chunks":23}` và `ok`.

Lần gọi thứ hai phải **dưới 1 giây**. Nếu vẫn ~25s là chưa warm.

**Mở app:**

```powershell
Start-Process "http://localhost:8501"
```

### Checklist trình duyệt (2 việc, hay bị quên)

1. **TẮT auto-translate** của Edge/Chrome — nếu không, giao diện lẫn Anh–Việt.
2. Muốn demo lại từ màn hình consent → mở **cửa sổ ẩn danh** (consent đã tick sẽ được nhớ).

---

## 5. Số liệu demo — dùng đúng những con số này

| Muốn ra | DASS-21 | PSS-10 |
|---|---|---|
| **High** (demo chính) | tất cả **2**, riêng **câu 17 & 21 = 0** | bất kỳ |
| Severe | tất cả **3**, riêng **17 & 21 = 0** | bất kỳ |
| Moderate | tất cả **0** | tất cả **0** |
| Low | tất cả **0** | câu **4, 5, 7, 8 = 4**, còn lại **0** |
| **Crisis** (cố ý) | tất cả **0**, riêng **17 & 21 = 3** | bất kỳ |

⚠️ **Câu 17 và 21 là hai câu rủi ro** ("I felt I wasn't worth much as a person" /
"I felt that life was meaningless"). Bấm **2** cho cả hai sẽ kích hoạt cảnh báo
khủng hoảng — đó là hành vi **đúng**, không phải lỗi.

**Demo crisis bằng free text** (mạnh hơn, không cần điền bảng):

```
I just want to sleep for a very long time and never wake up again.
```

Đây là false-negative #16 đã công bố trong báo cáo — rule cũ trượt, rule mới bắt được.

⚠️ Nút **Save** ở trang "Share how you feel" **không** gọi API.
Phân tích chỉ chạy khi bấm **"Analyse now"** ở trang **Results**.

---

## 6. Nếu hết quota LLM

```powershell
python scripts/check_llm.py     # mục 6 = hạn ngạch ngày thật
```

App vẫn chạy đầy đủ phần tất định và **hiện lý do** thay vì để trống.
Phương án dự phòng: mở `data/eval/llm_cache/` — 126 output thật của chính chain đó.

---

## 7. Dừng

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8501 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }
```

---

## Xử lý sự cố nhanh

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Trang trắng ~25s | Chưa warm | Chạy lại §3 |
| `knowledge_chunks: 0` | Chroma rỗng | `python -m app.rag.ingest` |
| Giao diện lẫn tiếng Việt | Trình duyệt tự dịch | Tắt auto-translate |
| Advice trống | Hết quota Groq | §6 |
| Nhảy vào màn hình crisis | Câu 17/21 ≥ 2 | Đặt về 0 hoặc 1 |
| `ModuleNotFoundError: app` | Chạy sai thư mục | `cd` về gốc project |
