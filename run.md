Cửa sổ 1 — API

cd "C:\Users\Minh Tuan\Documents\CLaude Code\Pre-Thesis"
$env:PYTHONIOENCODING = "utf-8"
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000


Cửa sổ 2 — Giao diện

cd "C:\Users\Minh Tuan\Documents\CLaude Code\Pre-Thesis"
$env:PYTHONIOENCODING = "utf-8"
python -m streamlit run streamlit_app/Home.py --server.port 8501




Cửa sổ 3 — WARM ⚠️ bước quan trọng nhất

cd "C:\Users\Minh Tuan\Documents\CLaude Code\Pre-Thesis"
python scripts/warm.py


Kết quả đúng (lần đầu dòng health mất ~25s là bình thường):


  [ok]   health              0.0s   {'status': 'ok', ..., 'knowledge_chunks': 23}
  [ok]   PhoBERT + scoring   2.7s   headline label: High
  [ok]   retrieval                   4 passages
  [ok]   generation                  advice present, citations verified
  second health call: 0.03s  (warm)
Ready.
Script tự chẩn đoán thay vì để bạn đoán: không kết nối được API → nhắc bật uvicorn; knowledge_chunks: 0 → nhắc python -m app.rag.ingest; hết quota → [WARN] generation NOT available; còn chậm → STILL COLD.

Nó cũng cố ý đặt câu 17 & 21 = 0 để warm đi qua đường bình thường, không nhảy vào crisis (nếu nhảy thì retrieval và LLM không được warm).

Mở app

Start-Process "http://localhost:8501"




Dừng

Get-NetTCPConnection -State Listen -LocalPort 8000,8501 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Stop-Process -Id $_ -Force }