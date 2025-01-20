IMAGE_NAME=order-recognition
IMAGE_TAG=0.1.0
DOCKERFILE=Dockerfile
PYTHON_MAIN=core/rabbimq.py
# Чтение переменных из .env
include .env
export $(shell sed 's/=.*//' .env)

build:
	@echo "RMQ_AI_URL=$(RMQ_AI_URL)"
	@echo "SHTTP_PROXY=$(SHTTP_PROXY)"
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) --build-arg RMQ_AI_URL=$(RMQ_AI_URL) \
											   --build-arg SHTTP_PROXY=$(SHTTP_PROXY) \
											   --build-arg SHTTPS_PROXY=$(SHTTPS_PROXY) -f $(DOCKERFILE) .

run:
	docker run -it --rm $(IMAGE_NAME):$(IMAGE_TAG)

install:
	poetry install

test:
	poetry run pytest