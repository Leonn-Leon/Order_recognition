Проект: распознавание материалов в заявках клиента
---

Описание
— Сервис получает сообщения из RabbitMQ, извлекает и нормализует текст письма (XML/HTML/JSON в base64), выделяет товарные позиции с помощью LLM‑парсера, сопоставляет им материалы из подготовленного справочника и возвращает результат через RPC‑механику. Предусмотрена отдельная очередь для сохранения подтверждений (ground truth), которые записываются в CSV.

Архитектура
- Ядро сервиса:
  - `order_recognition/core/rabbitmq.py` — подключение к брокеру, потребители очередей, RPC‑ответы, обработка сохранений (очередь 2).
  - `order_recognition/core/worker.py` — правила скоринга и поиск по справочнику.
  - `order_recognition/core/distance.py` — обёртка над воркером для UI/вспомогательных вызовов.
  - `order_recognition/core/hash2text.py` — декодирование `email` из двойного base64, разбор XML/JSON, извлечение текста из HTML.
  - `order_recognition/core/deepseek_parser.py` — LLM‑парсер товарных позиций.
  - `order_recognition/core/rabbit_rpc_client.py` — RPC‑клиент для вызова воркера.
  - `order_recognition/core/utils.py` — нормализация параметров.
  - `order_recognition/utils/data_text_processing.py` — очистка текста письма и минимальная нормализация запроса.
  - `order_recognition/utils/logger.py` — простой логгер в файл.
  - `order_recognition/confs/config.py` — конфигурация брокера: имена обменника и ключей маршрутизации.
- Данные:
  - `order_recognition/data/mats_with_features.csv` — подготовленный справочник материалов с признаками.
  - `order_recognition/data/method2.csv` — накопитель подтверждённых соответствий (заполняется через очередь 2).

Очереди
- exchange: `ai` (direct)
- routing keys:
  - `orderrecognition.find_request` → очередь 1 (`get_message` по умолчанию) — обработка входящих писем, RPC‑ответ с позициями.
  - `orderrecognition.save_truth` → очередь 2 — сохранение подтверждений в `method2.csv`.
  - Дополнительная очередь `find_request_result` объявляется по мере необходимости; по умолчанию не используется.

Docker и запуск
- Состав:
  - `Dockerfile` — агент (воркер, потребитель RabbitMQ), запускает `python order_recognition/core/rabbitmq.py`.
  - `Dockerfile.streamlit` — лёгкий веб‑клиент на Streamlit (`streamlit_rmq_client.py`) для ручной проверки.
  - `docker-compose.yml` — поднимает три сервиса: `rabbitmq`, `agent`, `client`.

Быстрый старт
1) Требования: Docker 24+, Docker Compose V2.
2) Запуск:
```
make up
```
3) Проверка:
- UI: открыть http://localhost:8585 — это Streamlit‑клиент, отправляющий RPC‑запрос в агент.
- RabbitMQ UI: http://localhost:15672 (guest/guest).

Остановка
```
make down
```

Сборка образов вручную
```
make build-agent
make build-client
```

Управление и диагностика
```
make logs        # все логи через docker compose
make logs-agent  # логи агента
make logs-client # логи клиента
make ps          # статус сервисов
```

Переменные окружения
- `RMQ_AI_URL` — AMQP‑строка подключения (пример: `amqp://guest:guest@rabbitmq:5672/%2F`).
  Задаётся в `docker-compose.yml` для `agent` и `client`.

API сообщений
- Очередь 1 (find_request):
  - Вход: `{ "email": <base64-double-encoded XML/JSON with fileContent> }`
  - Ответ (RPC): `{ "positions": [ { "request_text": ..., "material1_id": ..., "weight_1": ... }, ... ] }`
- Очередь 2 (save_truth):
  - Вход: `{ "req_number": "...", "positions": [ { "position_id": "...", "true_material": "...", "true_ei": "...", "true_value": "...", "spec_mat": "..." }, ... ] }`
  - Действие: дозапись строк в `order_recognition/data/method2.csv`.

Примечания по качеству кода
- Валидация входных сообщений и устойчивость к форматам email делегированы в `hash2text.text_from_hash` и `data_text_processing.clean_email_content`.
- Правила сопоставления параметров и скоринга инкапсулированы в `worker.py` и переиспользуются в UI‑логике.
- Очередь `find_request_result` оставлена как задел под дальнейшую интеграцию, по умолчанию не используется.