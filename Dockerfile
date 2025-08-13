FROM python:3.11-slim AS builder

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg libsm6 libxext6 && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем только файлы, необходимые для установки зависимостей
COPY pyproject.toml poetry.lock README.md ./
COPY order_recognition/ ./order_recognition/

# Устанавливаем все Python-зависимости
RUN poetry config virtualenvs.in-project true && \
    poetry install --only main --no-interaction --no-ansi --no-cache

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv ./.venv

COPY order_recognition/ ./order_recognition/
COPY pyproject.toml poetry.lock ./
COPY app.py ./app.py

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8501
# CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
CMD ["python", "order_recognition/core/rabbitmq.py"]