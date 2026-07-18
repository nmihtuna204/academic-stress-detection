# Shared image for both the FastAPI backend and the Streamlit frontend.
FROM python:3.11-slim

WORKDIR /srv

# CPU-only torch keeps the image several GB smaller than the default wheel.
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY streamlit_app/ streamlit_app/
COPY scripts/ scripts/
COPY data/knowledge/ data/knowledge/

EXPOSE 8000 8501

# Default command runs the API; docker-compose overrides for the UI service.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
