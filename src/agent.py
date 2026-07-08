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

import ast
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from openai import OpenAI

from config.settings import get_settings
from src.database import get_irradiance_for_period
from src.guardrails import GuardrailViolation, sanitize_output, validate_input
from src.memory import SessionMemory, get_session_memory
from utils.telemetry import redact_secrets, trace_agent, trace_llm, trace_tool

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "config" / "prompts.yaml"
MAX_REACT_TURNS = 6
REQUIRED_FIELDS = ("latitude", "longitude", "year", "start_month", "end_month")

# Real coverage of the configured Himawari (Asia/Pacific) NSRDB endpoint —
# verified against NREL's docs. Used both to ground the intent-parser prompt
# and to reject an out-of-range year the model hallucinates, so the two can't
# drift apart the way the prompt text and reality already had once.
NSRDB_MIN_YEAR = 2016
NSRDB_MAX_YEAR = 2020

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
def _call_llm(
    messages: list[dict], model: Optional[str] = None, stop: Optional[list[str]] = None
) -> tuple[str, dict]:
    """Send a chat completion request and return (text, token-usage dict)."""
    settings = get_settings()
    response = _client().chat.completions.create(
        model=model or settings.llm_model, messages=messages, stop=stop, temperature=0.1
    )
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


# Small/local models routinely emit near-JSON rather than JSON: Python `None`/
# `True`/`False` instead of `null`/`true`/`false`, leading zeros on numbers
# (invalid JSON syntax), a missing comma between fields, or the fields split
# across several separate `{...}` fragments instead of one object. These
# patterns normalize the common cases before parsing rather than discarding
# the whole response over one formatting slip.
_MONTH_NAME_TO_NUMBER = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Smart/curly quotes instead of straight ASCII ones — a display as a "?"
# placeholder in a non-UTF-8 terminal is the usual tell, but the actual model
# output (and what our code receives) is real Unicode. Written as \uXXXX
# escapes rather than literal characters so this file stays plain ASCII and
# can't break on a non-UTF-8 read (a real failure mode hit while writing this).
_SMART_QUOTE_TRANSLATION = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",  # single quotes
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',  # double quotes
})
_BARE_NULL_PATTERN = re.compile(r"\bNone\b|\bNull\b")
_BARE_TRUE_PATTERN = re.compile(r"\bTrue\b")
_BARE_FALSE_PATTERN = re.compile(r"\bFalse\b")
_LEADING_ZERO_PATTERN = re.compile(r'(?<=[:\[,]\s)0+(\d)')
_MISSING_COMMA_PATTERN = re.compile(r'([\]\}"\'\d])(\s+)([\'"]\w+[\'"]\s*:)')
_ESCAPED_UNDERSCORE_PATTERN = re.compile(r"\\_")
# A string value that opens with one quote style and closes with the other,
# e.g. ['ghi"] or ["dni'] — normalize both sides to double quotes.
_MISMATCHED_QUOTE_PATTERN = re.compile(r"""['"](\w+)['"]""")
# A bare, entirely unquoted month name as a value ("start_month": January) is
# not valid JSON or Python syntax at all — quote it before either parser sees it.
_BARE_MONTH_NAME_PATTERN = re.compile(
    r"(:\s*)(" + "|".join(sorted(_MONTH_NAME_TO_NUMBER, key=len, reverse=True)) + r")\b(?![\"'\w])",
    re.IGNORECASE,
)
_JSON_FRAGMENT_PATTERN = re.compile(r"\{[^{}]*\}")
_LIST_BODY_PATTERN = re.compile(r"\[([^\[\]]*)\]")
_KEY_NULL_PAIR_PATTERN = re.compile(r'"(\w+)"\s*:\s*null')


def _fix_dict_like_lists(text: str) -> str:
    """Fix `"attributes": ["ghi": null, "dni": null]` — dict-style key:null
    pairs written inside list brackets, invalid in both JSON and Python.
    Keeps just the keys, e.g. ["ghi", "dni"], which is the obvious intent.
    Only touches list bodies matching this exact pattern, so a normal list
    like ["ghi", "dni"] or [1, 2, 3] is never touched.
    """

    def _fix_one(match: re.Match) -> str:
        body = match.group(1)
        keys = _KEY_NULL_PAIR_PATTERN.findall(body)
        if not keys:
            return match.group(0)
        return "[" + ", ".join(f'"{k}"' for k in keys) + "]"

    return _LIST_BODY_PATTERN.sub(_fix_one, text)


def _normalize_json_like(text: str) -> str:
    """Best-effort cleanup of common small-model JSON mistakes before parsing."""
    text = _ESCAPED_UNDERSCORE_PATTERN.sub("_", text)
    text = _BARE_NULL_PATTERN.sub("null", text)
    text = _BARE_TRUE_PATTERN.sub("true", text)
    text = _BARE_FALSE_PATTERN.sub("false", text)
    text = _BARE_MONTH_NAME_PATTERN.sub(r'\1"\2"', text)
    text = _fix_dict_like_lists(text)
    text = _LEADING_ZERO_PATTERN.sub(r"\1", text)
    text = _MISSING_COMMA_PATTERN.sub(r"\1,\2\3", text)
    # Only touches single-word tokens (\w+ can't span a space), so multi-word
    # string values like "warehouse location in Caloocan" are never touched.
    text = _MISMATCHED_QUOTE_PATTERN.sub(r'"\1"', text)
    return text


def _parse_json_fragment(fragment: str) -> Optional[dict]:
    """Try increasingly lenient strategies to parse one `{...}` fragment."""
    # Leading zeros (03) and missing commas are invalid in BOTH JSON and
    # Python syntax, so this normalization pass has to happen before either
    # parsing strategy below, not just the json.loads one.
    normalized = _normalize_json_like(fragment)

    for candidate in (fragment, normalized):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Python-literal fallback: ast.literal_eval natively accepts single quotes,
    # which covers cases json.loads never will. It needs Python's None/True/
    # False rather than JSON's null/true/false, which `normalized` now has.
    python_candidate = re.sub(r"\bnull\b", "None", normalized, flags=re.IGNORECASE)
    python_candidate = re.sub(r"\btrue\b", "True", python_candidate, flags=re.IGNORECASE)
    python_candidate = re.sub(r"\bfalse\b", "False", python_candidate, flags=re.IGNORECASE)
    try:
        parsed = ast.literal_eval(python_candidate)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, SyntaxError):
        pass
    return None


def _extract_json(text: str) -> Optional[dict]:
    """Pull structured fields out of an LLM response.

    Handles the response being split across multiple `{...}` fragments (seen
    in practice from small models) by parsing each independently and merging
    whatever succeeds, rather than only reading the first fragment.
    """
    text = text.translate(_SMART_QUOTE_TRANSLATION)
    fragments = _JSON_FRAGMENT_PATTERN.findall(text)
    if not fragments:
        return None

    merged: dict = {}
    for fragment in fragments:
        parsed = _parse_json_fragment(fragment)
        if parsed:
            merged.update(parsed)
    return merged or None




def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _coerce_year(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _coerce_month(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 12 else None
    if isinstance(value, float) and value.is_integer():
        return int(value) if 1 <= value <= 12 else None
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in _MONTH_NAME_TO_NUMBER:
            return _MONTH_NAME_TO_NUMBER[stripped]
        try:
            as_int = int(stripped)
        except ValueError:
            return None
        return as_int if 1 <= as_int <= 12 else None
    return None


def _validate_slots(slots: dict) -> dict:
    """Coerce loosely-typed values and null out anything implausible.

    Small models sometimes return syntactically valid but semantically wrong
    output — coordinates in the wrong hemisphere, a year outside the dataset's
    real coverage, a start month after the end month. Nulling those fields
    routes back through the normal disambiguation path (re-ask) instead of
    silently proceeding with data that would fail, or worse, quietly return
    the wrong site's numbers.
    """
    validated = dict(slots)

    validated["latitude"] = _coerce_float(validated.get("latitude"))
    validated["longitude"] = _coerce_float(validated.get("longitude"))
    if validated["latitude"] is not None and not (-90 <= validated["latitude"] <= 90):
        validated["latitude"] = None
    if validated["longitude"] is not None and not (-180 <= validated["longitude"] <= 180):
        validated["longitude"] = None
    # A resolved site needs both coordinates together — a lone survivor is
    # more likely a partial hallucination than a usable fix.
    if validated["latitude"] is None or validated["longitude"] is None:
        validated["latitude"] = None
        validated["longitude"] = None

    validated["year"] = _coerce_year(validated.get("year"))
    if validated["year"] is not None and not (NSRDB_MIN_YEAR <= validated["year"] <= NSRDB_MAX_YEAR):
        validated["year"] = None

    validated["start_month"] = _coerce_month(validated.get("start_month"))
    validated["end_month"] = _coerce_month(validated.get("end_month"))
    if (
        validated["start_month"] is not None
        and validated["end_month"] is not None
        and validated["start_month"] > validated["end_month"]
    ):
        validated["start_month"] = None
        validated["end_month"] = None

    attributes = validated.get("attributes")
    if isinstance(attributes, str):
        validated["attributes"] = [attributes]

    return validated


# ── Step 1: Intent parsing ───────────────────────────────────────────────────

def _parse_intent(user_query: str) -> dict:
    prompt = _load_prompts()["intent_parser"]
    system_prompt = prompt["system"].format(min_year=NSRDB_MIN_YEAR, max_year=NSRDB_MAX_YEAR)
    few_shot_messages = []
    for example in prompt.get("few_shot", []):
        few_shot_messages.append({"role": "user", "content": example["user"]})
        few_shot_messages.append({"role": "assistant", "content": json.dumps(example["output"])})

    messages = [
        {"role": "system", "content": system_prompt},
        *few_shot_messages,
        {"role": "user", "content": user_query},
    ]
    text, _usage = _call_llm(messages)
    parsed = _extract_json(text)
    if parsed is None:
        # Safe default: treat a parse failure as "nothing resolved" rather than guessing.
        return {field: None for field in ("location_name", *REQUIRED_FIELDS, "attributes")}
    return _validate_slots(parsed)


# ── Step 2: fill gaps from session memory, then disambiguate if still incomplete ──

def _fill_from_memory(slots: dict, memory: SessionMemory) -> dict:
    filled = dict(slots)

    # Slots already resolved earlier in an in-progress clarification exchange
    # (e.g. start_month=2 from the original message) take priority over the
    # broader "last completed query" fallback below, since they're specific
    # to the exchange currently in flight.
    for key, value in memory.get_pending_slots().items():
        if filled.get(key) is None:
            filled[key] = value

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
        # Stop sequences catch a model continuing past its one allowed
        # Thought+Action and hallucinating the rest of the trace itself:
        # "Observation:" is the literal self-generated tool result, and
        # "\nThought:" catches it starting a second reasoning step in the same
        # completion (the first "Thought:" has no leading newline, so this
        # only fires on a repeat). Observed live with qwen2.5:7b, which is
        # creative enough to dodge either one alone with alternate phrasing.
        text, _usage = _call_llm(messages, stop=["Observation:", "\nThought:"])
        messages.append({"role": "assistant", "content": text})

        final_match = _FINAL_ANSWER_PATTERN.search(text)
        action_match = _ACTION_PATTERN.search(text)

        # A model that dodges both stop sequences (e.g. joining a second
        # Thought with a comma instead of a newline) can still cram a real
        # "Action:" and a hallucinated "Final Answer:" into one completion.
        # When both appear, the real action always comes first in practice —
        # honor it and dispatch the tool rather than only reacting to the
        # fake finish further down the same text.
        final_is_real = final_match and (not action_match or final_match.start() < action_match.start())

        if final_is_real:
            if aggregated is None:
                # A "Final Answer" before aggregate_monthly has actually run
                # is a simulated/hallucinated finish, not a real one — reject
                # it and force the model back through the real tools instead
                # of returning fabricated-adjacent content.
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "There is no real aggregated data yet, so that Final Answer isn't valid — "
                            "you have not actually called aggregate_monthly. Do not simulate tool "
                            "results yourself. Respond with exactly one Thought+Action to continue."
                        ),
                    }
                )
                continue
            return final_match.group(1).strip(), aggregated

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
                # redact_secrets matters here specifically: this text is fed
                # straight into the next LLM turn's messages, not just logged
                # to a trace — an unredacted API key would otherwise be sent
                # to whatever LLM backend is configured, including a hosted
                # third-party one if LLM_BASE_URL isn't a local model.
                observation = f"fetch_solar_data failed: {redact_secrets(str(exc))}"
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

    # A reply to our own clarifying question ("June", "2019", "month 6") is
    # on-topic by definition, even though it has no solar/location keywords
    # of its own — the strict guardrail only applies to a fresh query.
    if memory.is_awaiting_clarification():
        clean_query = (user_input or "").strip()
        if not clean_query:
            return AgentResponse(answer="I didn't catch that — could you say it again?", session_id=session_id)
    else:
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
        memory.set_awaiting_clarification(True)
        memory.remember_pending_slots(slots)
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

    memory.set_awaiting_clarification(False)
    memory.clear_pending_slots()
    memory.remember_location(slots["latitude"], slots["longitude"], slots.get("location_name"))
    memory.remember_query(year=slots["year"], attributes=slots.get("attributes"))

    raw_answer, aggregated = _run_react_loop(slots)
    if aggregated is None:
        # Enforced in code, not just prompted for: a small/local model will
        # sometimes hallucinate a plausible-sounding number here instead of
        # honestly relaying that the ReAct loop never got real data (observed
        # live — see conversation notes). Skipping the response-generation
        # LLM call entirely when there's nothing real to summarize guarantees
        # this can't happen, regardless of model quality.
        final_answer = (
            "I wasn't able to retrieve and summarize that solar data — the NSRDB "
            "request may have failed, timed out, or the site/date range couldn't be "
            "resolved. Please try again, or double-check the location and year."
        )
    else:
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
