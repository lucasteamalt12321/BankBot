# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    curl \
    ca-certificates \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Optional HF Telegram egress proxy via sing-box (enabled by VPN_SUBSCRIPTION_URL)
ARG SING_BOX_VERSION=1.10.7
RUN curl -L "https://github.com/SagerNet/sing-box/releases/download/v${SING_BOX_VERSION}/sing-box-${SING_BOX_VERSION}-linux-amd64.tar.gz" \
    | tar -xz -C /tmp \
    && mv "/tmp/sing-box-${SING_BOX_VERSION}-linux-amd64/sing-box" /usr/local/bin/sing-box \
    && chmod +x /usr/local/bin/sing-box \
    && rm -rf "/tmp/sing-box-${SING_BOX_VERSION}-linux-amd64"

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN groupadd -r bot && useradd -r -g bot bot
RUN mkdir -p /app && chown -R bot:bot /app

WORKDIR /app

COPY --chown=bot:bot . .

# Health check (using the new health endpoint in run_bot.py)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# По умолчанию запускает BankBot через HF startup wrapper
CMD ["python", "scripts/start_hf.py"]
