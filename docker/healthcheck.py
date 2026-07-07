"""Docker HEALTHCHECK: the container is only healthy if both the FastAPI
backend and the Streamlit UI are answering."""

import sys
import urllib.request

ENDPOINTS = (
    "http://localhost:8000/health",
    "http://localhost:8501/_stcore/health",
)

for url in ENDPOINTS:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status != 200:
                sys.exit(1)
    except Exception:
        sys.exit(1)

sys.exit(0)
