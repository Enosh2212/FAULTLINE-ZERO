FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN groupadd --system app && useradd --system --gid app app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
ARG FZ_PYTHON_EXTRAS=""
RUN if [ "$FZ_PYTHON_EXTRAS" = "auth" ]; then pip install --no-cache-dir '.[auth]'; else pip install --no-cache-dir .; fi && python -m faultline.git_demo && mkdir -p /app/data && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3)" || exit 1
CMD ["uvicorn", "faultline.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
