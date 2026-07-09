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

_SECRET_PARAM_PATTERN = re.compile(
    r"(api[_-]?key|apikey|token|password|secret)=[^&\s'\"]+", re.IGNORECASE
)


def _ensure_mlflow_configured() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    if settings.mlflow_registry_uri:
        mlflow.set_registry_uri(settings.mlflow_registry_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)
    _configured = True


def redact_secrets(text: str) -> str:
    # Strip query-string secrets.
    return _SECRET_PARAM_PATTERN.sub(r"\1=***REDACTED***", text)


def _finalize(text: str) -> str:
    text = redact_secrets(text)
    if len(text) > _MAX_ATTR_LEN:
        return text[:_MAX_ATTR_LEN] + "...<truncated>"
    return text


def _truncate(value: Any) -> str:
    return _finalize(repr(value))


def _span_decorator(span_type: str, extra_attrs: Callable[[Any, tuple, dict], dict]):
    # Decorator for wrapping a function in an `mlflow.start_span` of `span_type`.

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

    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        usage = result[1]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if key in usage:
                attrs[key] = usage[key]
    return attrs


trace_agent = _span_decorator(SpanType.AGENT, _agent_attrs)
trace_tool = _span_decorator(SpanType.TOOL, _tool_attrs)
trace_llm = _span_decorator(SpanType.LLM, _llm_attrs)