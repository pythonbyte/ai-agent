# Minimal runtime image for the WebSocket agent server.
FROM python:3.12-slim

WORKDIR /app

# Install package first (better layer caching when only config changes).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY config ./config
COPY docs ./docs

ENV PYTHONUNBUFFERED=1
EXPOSE 8765

# Must bind 0.0.0.0 so the published host port can reach the process.
CMD ["ai-agent", "--server", "--host", "0.0.0.0", "--port", "8765", "-c", "config/agent_config.yaml"]
