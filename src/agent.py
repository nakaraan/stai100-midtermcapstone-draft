"""AGENT P orchestration loop — a ReAct-style agent for solar irradiance queries.

The loop shape follows the from-scratch ReAct pattern described for Cell 33's
`run_agent` in notebook6-implementation.md: the LLM alternates Thought / Action /
Observation turns over a small, bounded action set; a plain regex parses each
Action rather than depending on a framework's tool-calling layer; a failed tool
call is fed back as an Observation string instead of crashing the loop; and the
loop is bounded by `max_turns` with a graceful "couldn't finish" fallback.

The action set is domain-specific to AGENT P (fetch_solar_data / aggregate_monthly
/ finish) — the calculator and web-search tools from that notebook are
intentionally not reused, only the loop's shape.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from openai import OpenAI

from config.settings import get_settings
from src.database import get_irradiance_for_period
from src.guardrails import GuardrailViolation, sanitize_output, validate_input
from src.memory import SessionMemory, get_session_memory
from utils.telemetry import trace_agent, trace_llm, trace_tool

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts.yaml"
MAX_REACT_TURNS = 6
REQUIRED_FIELDS = ("latitude", "longitude", "year", "start_month", "end_month")

REACT_SYSTEM_PROMPT_TEMPLATE = (
    "You are AGENT P's execution planner. You have exactly these actions:\n"
    "  fetch_solar_data — pulls hourly NSRDB records for the resolved site/year/month range\n"
    "  aggregate_monthly — computes monthly averages from the records fetch_solar_data returned\n"
    "  finish — ends the task with your final answer\n\n"
    "Respond with EXACTLY ONE of the following each turn, nothing else:\n"
    "Thought: <your reasoning>\n"
    "Action: fetch_solar_data\n"
    "or\n"
    "Thought: <your reasoning>\n"
    "Action: aggregate_monthly\n"
    "or\n"
    "Thought: <your reasoning>\n"
    "Final Answer: <the complete answer for the user>\n\n"
    "Call fetch_solar_data exactly once, then aggregate_monthly exactly once, then finish. "
    "Never invent numbers yourself — only report figures that appeared in an Observation.\n\n"
    "Resolved parameters: {slots}"
)

_ACTION_PATTERN = re.compile(r"Action:\s*(fetch_solar_data|aggregate_monthly)", re.IGNORECASE)
_FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:\s*(.*)", re.DOTALL | re.IGNORECASE)


@lru_cache
def _load_prompts() -> dict:
    return yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))


def _client() -> OpenAI:
    settings = get_settings()
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


@trace_llm
def _call_llm(messages: list[dict], model: Optional[str] = None) -> tuple[str, dict]:
    """Send a chat completion request and return (text, token-usage dict)."""
    settings = get_settings()
    response = _client().chat.completions.create(model=model or settings.llm_model, messages=messages)
    usage = response.usage
    usage_dict = (
        {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }
        if usage
        else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    return response.choices[0].message.content or "", usage_dict


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response; None on any parse failure."""
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ── Step 1: Intent parsing ───────────────────────────────────────────────────

def _parse_intent(user_query: str) -> dict:
    prompt = _load_prompts()["intent_parser"]
    few_shot_messages = []
    for example in prompt.get("few_shot", []):
        few_shot_messages.append({"role": "user", "content": example["user"]})
        few_shot_messages.append({"role": "assistant", "content": json.dumps(example["output"])})

    messages = [
        {"role": "system", "content": prompt["system"]},
        *few_shot_messages,
        {"role": "user", "content": user_query},
    ]
    text, _usage = _call_llm(messages)
    parsed = _extract_json(text)
    if parsed is None:
        # Safe default: treat a parse failure as "nothing resolved" rather than guessing.
        return {field: None for field in ("location_name", *REQUIRED_FIELDS, "attributes")}
    return parsed


# ── Step 2: fill gaps from session memory, then disambiguate if still incomplete ──

def _fill_from_memory(slots: dict, memory: SessionMemory) -> dict:
    filled = dict(slots)
    location = memory.get_location()
    if location and filled.get("latitude") is None and filled.get("longitude") is None:
        filled["latitude"] = location.latitude
        filled["longitude"] = location.longitude
        filled["location_name"] = filled.get("location_name") or location.name
    if filled.get("year") is None:
        filled["year"] = memory.get_last_year()
    if not filled.get("attributes"):
        filled["attributes"] = memory.get_last_attributes()
    return filled


def _missing_fields(slots: dict) -> list[str]:
    return [field for field in REQUIRED_FIELDS if slots.get(field) is None]


def _generate_clarification(slots: dict, missing: list[str]) -> str:
    prompt = _load_prompts()["disambiguation"]
    known = {k: v for k, v in slots.items() if v is not None}
    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": f"Known so far: {json.dumps(known)}\nMissing: {missing}"},
    ]
    text, _usage = _call_llm(messages)
    return text.strip()


# ── Mathematical aggregation — invoked as the ReAct loop's own tool action ────

@trace_tool
def aggregate_monthly(records: list[dict], attributes: list[str]) -> dict:
    """Compute monthly averages per attribute from raw hourly NSRDB records."""
    attr_columns = {attr: _resolve_column_name(attr, records) for attr in attributes}
    by_month: dict[int, dict[str, list[float]]] = {}
    for record in records:
        month = record.get("Month")
        if month is None:
            continue
        bucket = by_month.setdefault(month, {attr: [] for attr in attributes})
        for attr, column in attr_columns.items():
            value = record.get(column)
            if isinstance(value, (int, float)):
                bucket[attr].append(value)

    return {
        month: {
            attr: (round(sum(values) / len(values), 2) if values else None)
            for attr, values in attr_values.items()
        }
        for month, attr_values in sorted(by_month.items())
    }


def _resolve_column_name(attribute: str, records: list[dict]) -> str:
    """Map a lowercase attribute name (e.g. 'ghi') to its actual NSRDB CSV column."""
    if not records:
        return attribute.upper()
    for column in records[0]:
        if column.lower() == attribute.lower():
            return column
    return attribute.upper()


# ── Step 3: ReAct loop — Thought / Action / Observation over our own tools ───

def _run_react_loop(slots: dict) -> tuple[str, Optional[dict]]:
    """Run the Thought/Action/Observation loop. Returns (final_answer_text, monthly_metrics)."""
    system_prompt = REACT_SYSTEM_PROMPT_TEMPLATE.format(slots=json.dumps(slots))
    messages = [{"role": "system", "content": system_prompt}]
    fetched_records: Optional[list[dict]] = None
    aggregated: Optional[dict] = None

    for _turn in range(MAX_REACT_TURNS):
        text, _usage = _call_llm(messages)
        messages.append({"role": "assistant", "content": text})

        final_match = _FINAL_ANSWER_PATTERN.search(text)
        if final_match:
            return final_match.group(1).strip(), aggregated

        action_match = _ACTION_PATTERN.search(text)
        if not action_match:
            messages.append(
                {
                    "role": "user",
                    "content": "Please respond with exactly one Thought+Action, or a Thought+Final Answer.",
                }
            )
            continue

        action = action_match.group(1).lower()
        if action == "fetch_solar_data":
            try:
                fetched_records = get_irradiance_for_period(
                    latitude=slots["latitude"],
                    longitude=slots["longitude"],
                    year=slots["year"],
                    start_month=slots["start_month"],
                    end_month=slots["end_month"],
                    attributes=slots.get("attributes"),
                )
                observation = f"Retrieved {len(fetched_records)} hourly records."
            except Exception as exc:
                observation = f"fetch_solar_data failed: {exc}"
        else:  # aggregate_monthly
            if fetched_records is None:
                observation = "No records fetched yet — call fetch_solar_data first."
            else:
                aggregated = aggregate_monthly(fetched_records, slots.get("attributes") or ["ghi"])
                observation = f"Monthly averages: {json.dumps(aggregated)}"

        messages.append({"role": "user", "content": f"Observation: {observation}"})

    fallback = "I wasn't able to finish pulling and summarizing that data in time. Please try again."
    return fallback, aggregated


# ── Step 4: response generation ──────────────────────────────────────────────

def _generate_response(user_query: str, raw_answer: str) -> str:
    prompt = _load_prompts()["response_generator"]
    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": f"User asked: {user_query}\n\nDraft findings:\n{raw_answer}"},
    ]
    text, _usage = _call_llm(messages)
    return text.strip()


# ── Public entry point ───────────────────────────────────────────────────────

@dataclass
class AgentResponse:
    """Structured result of one AGENT P turn — the payload api/main.py serializes."""

    answer: str
    session_id: str
    needs_clarification: bool = False
    location: Optional[dict] = None
    year: Optional[int] = None
    start_month: Optional[int] = None
    end_month: Optional[int] = None
    attributes: Optional[list[str]] = None
    monthly_metrics: Optional[dict] = None


def _location_payload(slots: dict) -> Optional[dict]:
    latitude, longitude = slots.get("latitude"), slots.get("longitude")
    if latitude is None or longitude is None:
        return None
    return {"latitude": latitude, "longitude": longitude, "name": slots.get("location_name")}


@trace_agent
def handle_query(user_input: str, session_id: str = "default") -> AgentResponse:
    """Run one full AGENT P turn: guardrails -> intent -> disambiguation -> ReAct -> response."""
    memory = get_session_memory(session_id)

    try:
        clean_query = validate_input(user_input)
    except GuardrailViolation as exc:
        return AgentResponse(answer=str(exc), session_id=session_id)

    memory.remember_turn("user", clean_query)

    slots = _fill_from_memory(_parse_intent(clean_query), memory)

    missing = _missing_fields(slots)
    if missing:
        question = sanitize_output(_generate_clarification(slots, missing))
        memory.remember_turn("assistant", question)
        return AgentResponse(
            answer=question,
            session_id=session_id,
            needs_clarification=True,
            location=_location_payload(slots),
            year=slots.get("year"),
            start_month=slots.get("start_month"),
            end_month=slots.get("end_month"),
            attributes=slots.get("attributes"),
        )

    memory.remember_location(slots["latitude"], slots["longitude"], slots.get("location_name"))
    memory.remember_query(year=slots["year"], attributes=slots.get("attributes"))

    raw_answer, aggregated = _run_react_loop(slots)
    final_answer = sanitize_output(_generate_response(clean_query, raw_answer))

    memory.remember_turn("assistant", final_answer)
    return AgentResponse(
        answer=final_answer,
        session_id=session_id,
        location=_location_payload(slots),
        year=slots["year"],
        start_month=slots["start_month"],
        end_month=slots["end_month"],
        attributes=slots.get("attributes"),
        monthly_metrics=aggregated,
    )
