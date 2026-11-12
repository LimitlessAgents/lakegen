.PHONY: help check fix test lint format

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: lint format-check test ## Run all checks (same as CI)

test: ## Run unit tests
	uv run pytest

lint: ## Run linter checks
	uv run ruff check .

format-check: ## Check formatting without modifying files
	uv run ruff format --check .

fix: ## Auto-fix linting issues and reformat code
	uv run ruff check --fix .
	uv run ruff format .
