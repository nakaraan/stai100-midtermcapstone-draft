"""Reusable MLflow tracing decorators for AGENT P's LLMOps observability layer.

Adapted from the manual `mlflow.start_span(...)` blocks in the sample RAG app's
`logging_middleware.py` (see `sample_rag_app_implementation.md`), which wrapped a
single traced_chat() call with nested "chat_request" / "rag_retrieval" /
"llm_inference" spans. Here the same span-per-stage idea is generalized into three
decorators — `@trace_agent`, `@trace_tool`, `@trace_llm` — so any function can be
traced by annotation instead of hand-nesting `with mlflow.start_span(...)` blocks
at every call site.
"""

from __future__ import annotations

import functools
import re
import time
from typing import Any, Callable, TypeVar

import mlflow
from mlflow.entities import SpanType

from config.settings import get_settings

F = TypeVar("F", bound=Callable[..., Any])

_MAX_ATTR_LEN = 500
_configured = False

# Query-string secrets (e.g. NREL download URLs carry `api_key=...`) must never
# reach a trace attribute, since MLflow traces are viewed outside this process.
_SECRET_PARAM_PATTERN = re.compile(
    r"(api[_-]?key|apikey|token|password|secret)=[^&\s'\"]+", re.IGNORECASE
)


def _ensure_mlflow_configured() -> None:
    """Point MLflow at the configured tracking/registry URIs and experiment, once."""
    global _configured
    if _configured:
        return
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    if settings.mlflow_registry_uri:
        mlflow.set_registry_uri(settings.mlflow_registry_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)
    _configured = True


def _finalize(text: str) -> str:
    text = _SECRET_PARAM_PATTERN.sub(r"\1=***REDACTED***", text)
    if len(text) > _MAX_ATTR_LEN:
        return text[:_MAX_ATTR_LEN] + "...<truncated>"
    return text


def _truncate(value: Any) -> str:
    return _finalize(repr(value))


def _span_decorator(span_type: str, extra_attrs: Callable[[Any, tuple, dict], dict]):
    """Build a decorator that wraps a function in an `mlflow.start_span` of `span_type`.

    Handles both `@trace_x` and `@trace_x(name="...")` usage, records latency and
    success/error status on every call, and delegates to `extra_attrs(result, args,
    kwargs)` for span-specific attributes (e.g. token usage for LLM calls, record
    counts for tool calls).
    """

    def decorator(func: F | None = None, *, name: str | None = None) -> F:
        def wrap(fn: F) -> F:
            span_name = name or fn.__name__

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                _ensure_mlflow_configured()
                start = time.perf_counter()
                with mlflow.start_span(name=span_name, span_type=span_type) as span:
                    span.set_attribute("function", fn.__qualname__)
                    span.set_inputs({"args": _truncate(args), "kwargs": _truncate(kwargs)})
                    try:
                        result = fn(*args, **kwargs)
                    except Exception as exc:
                        span.set_attribute("status", "error")
                        span.set_attribute("error", _finalize(str(exc)))
                        raise
                    latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    span.set_attribute("status", "success")
                    span.set_attribute("latency_ms", latency_ms)
                    for key, value in extra_attrs(result, args, kwargs).items():
                        span.set_attribute(key, value)
                    span.set_outputs(_truncate(result))
                    return result

            return wrapper  # type: ignore[return-value]

        return wrap(func) if func is not None else wrap

    return decorator


def _agent_attrs(result: Any, args: tuple, kwargs: dict) -> dict:
    user_input = kwargs.get("user_input")
    if user_input is None:
        for arg in args:
            if isinstance(arg, str):
                user_input = arg
                break
    return {"user_input": _truncate(user_input)} if user_input is not None else {}


def _tool_attrs(result: Any, args: tuple, kwargs: dict) -> dict:
    attrs: dict[str, Any] = {}
    if isinstance(result, dict):
        attrs["result_keys"] = _truncate(list(result.keys()))
    elif isinstance(result, list):
        attrs["result_count"] = len(result)
    return attrs


def _llm_attrs(result: Any, args: tuple, kwargs: dict) -> dict:
    attrs: dict[str, Any] = {}
    model = kwargs.get("model")
    if model is not None:
        attrs["model"] = model
    # Mirrors the sample app's `complete_with_usage()` shape: (text, usage_dict).
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        usage = result[1]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key in usage:
                attrs[key] = usage[key]
    return attrs


trace_agent = _span_decorator(SpanType.AGENT, _agent_attrs)
"""Trace a top-level agent orchestration loop (parse -> tool calls -> synthesis).

Equivalent to the sample app's outer "chat_request" CHAIN span, but scoped as
SpanType.AGENT since this wraps the whole agentic turn, not just one chain step.
"""

trace_tool = _span_decorator(SpanType.TOOL, _tool_attrs)
"""Trace an external tool call (e.g. the NREL/NSRDB API request).

Equivalent to the sample app's "rag_retrieval" RETRIEVER span, generalized to
SpanType.TOOL for any external data-fetching call.
"""

trace_llm = _span_decorator(SpanType.LLM, _llm_attrs)
"""Trace a single LLM call, capturing model name and token usage when available.

Equivalent to the sample app's "llm_inference" LLM span.
"""
