# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN groupadd -r bot && useradd -r -g bot bot
RUN mkdir -p /app && chown -R bot:bot /app

WORKDIR /app

COPY --chown=bot:bot . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# По умолчанию запускает BankBot; переопределяется в docker-compose через CMD
CMD ["python", "run_bot.py", "bank"]
