FROM python:3.11-slim AS builder

# Аргументы для прокси
ARG http_proxy=""
ARG https_proxy=""

RUN echo "http_proxy=${http_proxy}" && echo "https_proxy=${https_proxy}"

# Установка переменных окружения для прокси (если переданы)
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}

RUN apt-get update && apt-get upgrade -y --no-install-recommends curl
RUN apt-get install ffmpeg libsm6 libxext6 -y

# Установка poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
# Добавление poetry в PATH
ENV PATH="/root/.local/bin:$PATH"
COPY pyproject.toml poetry.lock README.md ./

# Установка poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
# Добавление poetry в PATH
ENV PATH="/root/.local/bin:$PATH"
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
ARG http_proxy=""
ARG https_proxy=""
ARG RMQ_AI_URL=""

# Установка переменных окружения для прокси (если переданы)
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV RMQ_AI_URL=${RMQ_AI_URL}

RUN sed -i "s|RMQ_AI_URL|${RMQ_AI_URL}|g" order_recognition/confs/config.py

# Настройка переменной окружения для python
ENV PATH="/.venv/bin:$PATH"
RUN poetry config virtualenvs.in-project true --local && \
    poetry lock && \
    poetry install --only main --no-interaction --no-ansi --no-cache

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY --from=builder /.venv /.venv
COPY --from=builder order_recognition/ ./order_recognition/

# Аргументы для прокси
ARG http_proxy=""
ARG https_proxy=""
ARG RMQ_AI_URL=""

# Установка переменных окружения для прокси (если переданы)
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV RMQ_AI_URL=${RMQ_AI_URL}

RUN echo "RMQ_AI_URL=${RMQ_AI_URL}" && echo "https_proxy=${https_proxy}"

RUN sed -i "s|RMQ_AI_URL|${RMQ_AI_URL}|g" order_recognition/confs/config.py

# Настройка переменной окружения для python
ENV PATH="/.venv/bin:$PATH"
RUN chmod -R g+rw /order_recognition
CMD ["python", "/order_recognition/core/rabbitmq.py"]
CMD ["python", "/order_recognition/core/rabbitmq.py"]
