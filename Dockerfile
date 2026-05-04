# --- Base Stage ---
FROM python:3.10-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (needed for confluent-kafka and numpy)
RUN apt-get update && apt-get install -y \
    build-essential \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Final Stage ---
FROM base as final

# Copy project files
COPY SignalCoreAI/ ./SignalCoreAI/
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Expose FastAPI port
EXPOSE 8000

# Entrypoint script to handle multiple modes (API or Worker)
COPY <<EOF /app/entrypoint.sh
#!/bin/sh
if [ "\$MODE" = "worker" ]; then
    echo "Starting Kafka Consumer / RL Worker..."
    exec python backend/kafka_gateway.py
else
    echo "Starting FastAPI Gateway..."
    exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
fi
EOF

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
