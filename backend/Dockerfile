ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ARG BASE_IMAGE

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/
RUN if [ "$BASE_IMAGE" = "agent-backend:latest" ]; then \
      echo "Reusing backend dependencies from local image cache"; \
    else \
      pip install --no-cache-dir uv && uv pip install --system .; \
    fi
COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
