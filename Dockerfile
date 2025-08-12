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
COPY pyproject.toml poetry.lock ./

# Устанавливаем все Python-зависимости, включая NLTK-данные
RUN poetry config virtualenvs.in-project true && \
    poetry install --only main --no-interaction --no-ansi --no-root && \
    poetry run python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /app/.venv ./.venv

COPY . .

#ARG RMQ_AI_URL

#RUN sed -i "s|RMQ_AI_URL|${RMQ_AI_URL}|g" order_recognition/confs/config.py

# Настраиваем PATH, чтобы система видела исполняемые файлы из .venv
ENV PATH="/app/.venv/bin:$PATH"

#
EXPOSE 8501

#CMD ["python", "-m", "order_recognition.core.rabbitmq"]
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]