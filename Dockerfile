FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY triage ./triage
RUN uv sync --frozen --no-dev --extra server --extra local

ENV TRIAGE_INDEX_DIR=/data/index \
    FASTEMBED_CACHE_PATH=/data/models \
    TRIAGE_CONFIG=/config/issue-triage.yml \
    PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home triage && mkdir -p /data && chown triage /data
USER triage
VOLUME ["/data"]
EXPOSE 8000
# Inside the container the server must listen on all interfaces; publish the port to localhost only
# (compose.yaml) unless it sits behind a reverse proxy.
CMD ["triage", "--config", "/config/issue-triage.yml", "--index-dir", "/data/index", "serve", "--host", "0.0.0.0", "--port", "8000"]
