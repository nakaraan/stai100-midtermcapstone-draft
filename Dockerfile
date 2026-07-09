# Builds a virtual env with all dependencies installed.
FROM python:3.11-slim AS builder

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


#Instantiates the runtime image
FROM python:3.11-slim AS runtime

RUN useradd --create-home --shell /bin/bash agentp

WORKDIR /app

# Prebuilt virtualenv only, no compilers or pip cache carried over.
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_P_API_URL=http://localhost:8000

COPY api/ ./api/
COPY app/ ./app/
COPY src/ ./src/
COPY config/ ./config/
COPY utils/ ./utils/

COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/healthcheck.py /healthcheck.py
RUN chmod +x /entrypoint.sh && chown -R agentp:agentp /app

USER agentp

# 8000 = backend, 8501 = UI.
EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python /healthcheck.py

ENTRYPOINT ["/entrypoint.sh"]
