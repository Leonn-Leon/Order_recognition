FROM python:3.11-slim AS builder

# Аргументы для прокси
ARG SHTTP_PROXY=""
ARG SHTTPS_PROXY=""

# Установка переменных окружения для прокси (если переданы)
ENV SHTTP_PROXY=${SHTTP_PROXY}
ENV SHTTPS_PROXY=${SHTTPS_PROXY}

RUN echo "SHTTP_PROXY=${SHTTP_PROXY}" && echo "SHTTPS_PROXY=${SHTTPS_PROXY}"

RUN apt-get update && apt-get upgrade -y --no-install-recommends curl
RUN apt-get install ffmpeg libsm6 libxext6 -y

# Установка poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$PATH:/root/.local/bin"
# Добавление poetry в PATH
COPY pyproject.toml poetry.lock README.md ./
COPY order_recognition/ ./order_recognition/
RUN poetry config virtualenvs.in-project true --local && \
    poetry lock && \
    poetry install --only main --no-interaction --no-ansi --no-cache

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY --from=builder /.venv /.venv
COPY --from=builder order_recognition/ ./order_recognition/

# Аргументы для прокси
ARG SHTTP_PROXY=""
ARG SHTTPS_PROXY=""
ARG RMQ_AI_URL=""

# Установка переменных окружения для прокси (если переданы)
ENV SHTTP_PROXY=${SHTTP_PROXY}
ENV SHTTPS_PROXY=${SHTTPS_PROXY}
ENV RMQ_AI_URL=${RMQ_AI_URL}

RUN sed -i "s|RMQ_AI_URL|${RMQ_AI_URL}|g" order_recognition/confs/config.py

# Настройка переменной окружения для python
ENV PATH="/.venv/bin:$PATH"

RUN chmod -R g+rw /order_recognition
CMD ["python", "/order_recognition/core/rabbitmq.py"]
