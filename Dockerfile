FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential  && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --no-deps

COPY src ./src

RUN mkdir -p /app/output
VOLUME ["/app/output"]

EXPOSE 8501
CMD ["streamlit", "run", "src/app.py"]