# Convenience targets (POSIX make; on Windows use the underlying commands or Git Bash).

.PHONY: install seed test api ui eval compare ablation crisis-eval export lint docker-up docker-down

install:
	pip install -r requirements.txt

seed:
	python scripts/seed.py --rows 200

test:
	python -m pytest tests/ -q

api:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000

ui:
	streamlit run streamlit_app/Trang_Chu.py

eval:
	python -m app.eval.evaluate

compare:
	python -m app.eval.compare --dataset synthetic

ablation:
	python -m app.eval.ablation --dataset synthetic

crisis-eval:
	python -m app.eval.crisis_eval

export:
	python scripts/export_dataset.py --split
	python scripts/data_quality_report.py

lint:
	python -m ruff check app/ scripts/ streamlit_app/ tests/

docker-up:
	docker compose up --build

docker-down:
	docker compose down
