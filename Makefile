IMAGE_NAME=order-recognition
DOCKERFILE=Dockerfile
PYTHON_MAIN=core/rabbimq.py

docker-build:
	docker build -t $(IMAGE_NAME) -f $(DOCKERFILE) .

docker-run:
	docker run -it --rm $(IMAGE_NAME)

install:
	poetry config virtualenvs.in-project true
	poetry install

run:
	poetry run python

test:
	poetry run pytest