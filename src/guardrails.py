"""Input/output guardrails for AGENT P.

Two responsibilities, mirroring the guardrail split in the sample RAG app
(`is_on_topic()` / `output_validator()` in `sample_rag_app_implementation.md`):
  1. Reject user inputs that aren't about solar irradiation, weather, or location data.
  2. Prevent raw JSON error payloads, tracebacks, or exception dumps (e.g. a failed
     NREL API call) from leaking into a user-facing response.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

_ON_TOPIC_KEYWORDS = frozenset(
    {
        "solar", "irradiation", "irradiance", "insolation", "ghi", "dni", "dhi",
        "nsrdb", "nrel", "sun", "sunlight", "photovoltaic", "pv", "panel", "panels",
        "kwh", "kw", "watt", "watts", "energy yield",
        "weather", "climate", "temperature", "rainfall", "precipitation",
        "humidity", "wind", "cloud", "cloud cover",
        "location", "latitude", "longitude", "coordinates", "site", "warehouse",
        "region", "city", "province", "address", "rooftop", "roof",
        "monthly average", "annual average", "feasibility", "yield", "installation",
    }
)

_COORDINATE_PATTERN = re.compile(r"-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+")
_MONTH_YEAR_PATTERN = re.compile(
    r"\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|"
    r"sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?)\b|\b(19|20)\d{2}\b",
    re.IGNORECASE,
)

_JSON_ERROR_KEY_PATTERN = re.compile(
    r'"(error|errors|exception|traceback|stack_?trace|detail|status_code)"\s*:', re.IGNORECASE
)
_TRACEBACK_PATTERN = re.compile(r"traceback \(most recent call last\)", re.IGNORECASE)
_RAW_EXCEPTION_PATTERN = re.compile(r"\b\w*(Error|Exception)\b\s*:", re.IGNORECASE)

_FALLBACK_ERROR_MESSAGE = (
    "Something went wrong while pulling that solar data. Please try rephrasing your "
    "request (e.g. include a location and date range), or try again shortly."
)


class GuardrailViolation(ValueError):
    """Raised when user input fails the on-topic guardrail."""


def is_on_topic(text: str, classifier: Optional[Callable[[str], bool]] = None) -> bool:
    """Check whether `text` is about solar, weather, or location data.

    Literal keyword/pattern match first; if that fails and a `classifier` (e.g. an
    LLM-backed semantic check) is supplied, fall back to it. This mirrors the
    literal-then-semantic hybrid match pattern used for topic classification.
    """
    if not text or not text.strip():
        return False
    lowered = text.lower()
    if any(keyword in lowered for keyword in _ON_TOPIC_KEYWORDS):
        return True
    if _COORDINATE_PATTERN.search(text) and _MONTH_YEAR_PATTERN.search(text):
        return True
    if classifier is not None:
        return classifier(text)
    return False


def validate_input(text: str, classifier: Optional[Callable[[str], bool]] = None) -> str:
    """Raise GuardrailViolation if `text` isn't about solar/weather/location data.

    Returns the stripped input when it passes.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise GuardrailViolation("Input is empty.")
    if not is_on_topic(cleaned, classifier=classifier):
        raise GuardrailViolation(
            "AGENT P only answers questions about solar irradiation, weather, or "
            "location-based site data. Please rephrase your question around one of those topics."
        )
    return cleaned


def contains_raw_error_leak(text: str) -> bool:
    """Detect raw JSON error payloads, tracebacks, or exception dumps in candidate output."""
    if not text:
        return False
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            return True
    if _JSON_ERROR_KEY_PATTERN.search(text):
        return True
    if _TRACEBACK_PATTERN.search(text):
        return True
    if _RAW_EXCEPTION_PATTERN.search(text):
        return True
    return False


def sanitize_output(text: str) -> str:
    """Replace a leaked raw error with a safe, generic fallback message."""
    if contains_raw_error_leak(text):
        return _FALLBACK_ERROR_MESSAGE
    return text
