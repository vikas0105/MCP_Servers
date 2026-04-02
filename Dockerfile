FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
COPY src /app/src
COPY templates /app/templates
COPY static /app/static
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
