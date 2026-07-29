FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip \
    && pip install -r /app/requirements.txt

RUN python -m playwright install --with-deps chromium \
    && chmod -R a+rwx /ms-playwright

COPY web_docs_to_markdown /app/web_docs_to_markdown
COPY config.example.yml /app/config.example.yml
COPY README.md /app/README.md

RUN useradd --create-home --shell /bin/bash appuser
USER appuser

CMD ["python", "-m", "web_docs_to_markdown", "--config", "/app/config.yml"]