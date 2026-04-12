# Stage 1: Build dependencies
FROM ghcr.io/astral-sh/uv:0.6-python3.12-bookworm-slim AS builder

WORKDIR /app

# Install CPU-only PyTorch to save ~1.5GB
ENV UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

RUN uv sync --frozen --no-dev

# Pre-download cross-encoder model so it's cached in the image
RUN uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Stage 2: Slim runtime
FROM python:3.12-slim-bookworm

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy cached Hugging Face model to user-accessible path
COPY --from=builder /root/.cache/huggingface /home/appuser/.cache/huggingface
RUN chown -R appuser:appuser /home/appuser/.cache

# Copy application code and data
COPY src/ src/
COPY data/ data/
COPY scripts/docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appuser /app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
