# Stage 1: Build stage
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/root/.cargo/bin:${PATH}"

# Install system dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && curl -sSf https://sh.rustup.rs | sh -s -- -y \
    && . "$HOME/.cargo/env" \
    && pip install --no-cache-dir uv \
    && uv pip install --system pip setuptools wheel \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application
COPY . .

# Install the package in development mode
RUN uv pip install --system -e .

# Stage 2: Runtime stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Add build arguments for UID and GID with defaults
ARG USER_UID=1000
ARG USER_GID=1000

# Install runtime dependencies and create user with specified UID/GID
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g ${USER_GID} appuser \
    && useradd -u ${USER_UID} -g ${USER_GID} -s /bin/sh -m appuser

# Set working directory
WORKDIR /app

# Copy from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/whale_alert/. /app/whale_alert/
COPY --from=builder /app/generate_tg_session.py /app/generate_tg_session.py

# Create sessions directory and set permissions with correct ownership
RUN mkdir -p /app/sessions \
    && chown -R ${USER_UID}:${USER_GID} /app \
    && chmod -R 755 /app

# Switch to non-root user
USER ${USER_UID}

# Command to run the application
CMD ["python", "-m", "whale_alert"]
