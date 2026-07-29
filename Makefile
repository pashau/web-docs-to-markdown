.PHONY: install-dev lint format security audit check docker-build

install-dev:
    pip install -r requirements.txt
    pip install -r requirements-dev.txt

lint:
    ruff check .

format:
    ruff format .
    ruff check . --fix

security:
    bandit -c pyproject.toml -r web_docs_to_markdown

audit:
    pip-audit

docker-build:
    docker build -t web-docs-to-markdown:local .

check:
    ruff check .
    ruff format --check .
    bandit -c pyproject.toml -r web_docs_to_markdown
    pip-audit
