FROM python:3.12-slim AS test

WORKDIR /app
COPY requirements-test.txt ./
RUN python -m pip install --no-cache-dir -r requirements-test.txt
COPY app/ ./app/
COPY tests/ ./tests/
RUN python -m pytest -q tests

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/root/.cache/huggingface

WORKDIR /app
RUN python -m pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY evaluation/ ./evaluation/
COPY dados/conhecimento_fitness.txt ./dados/conhecimento_fitness.txt

RUN mkdir -p /app/data/chroma_db /app/outputs /root/.cache/huggingface
VOLUME ["/app/data/chroma_db", "/app/outputs", "/root/.cache/huggingface"]

CMD ["python", "-m", "app.main"]
