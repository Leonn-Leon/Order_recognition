PROJECT?=order-recognition
AGENT_IMAGE?=$(PROJECT)-agent
CLIENT_IMAGE?=$(PROJECT)-client
TAG?=latest

.PHONY: build build-agent build-client up down logs logs-agent logs-client ps clean

build: build-agent build-client ## Build all images

build-agent: ## Build agent image
	docker build -t $(AGENT_IMAGE):$(TAG) -f Dockerfile .

build-client: ## Build streamlit client image
	docker build -t $(CLIENT_IMAGE):$(TAG) -f Dockerfile.streamlit .

up: ## Start compose stack
	docker compose up -d --build

down: ## Stop compose stack
	docker compose down

logs: ## Tail all logs
	docker compose logs -f --tail=200

logs-agent: ## Tail agent logs
	docker logs -f order-agent

logs-client: ## Tail client logs
	docker logs -f order-client

ps: ## Show compose services
	docker compose ps

clean: ## Remove dangling images
	docker image prune -f