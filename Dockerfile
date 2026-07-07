# syntax=docker/dockerfile:1

# ---- Stage 1: build a venv with all dependencies -----------------------
# Kept separate from the runtime stage so build-only pip cache/wheel
# artifacts never end up in the final image.
FROM python:3.11-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ---- Stage 2: runtime image ---------------------------------------------
FROM python:3.11-slim AS runtime

RUN useradd --create-home --shell /bin/bash agentp

WORKDIR /app

# Prebuilt virtualenv only — no compilers or pip cache carried over.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_P_API_URL=http://localhost:8000

# Application code only — notebooks, sample files, and docs are not part of
# the runtime image (see .dockerignore for the full exclusion list).
COPY api/ ./api/
COPY app/ ./app/
COPY src/ ./src/
COPY config/ ./config/
COPY utils/ ./utils/

COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/healthcheck.py /healthcheck.py
RUN chmod +x /entrypoint.sh && chown -R agentp:agentp /app

USER agentp

# 8000 = FastAPI backend, 8501 = Streamlit UI.
EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python /healthcheck.py

ENTRYPOINT ["/entrypoint.sh"]
