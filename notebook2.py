# %% [markdown]
# ## Getting Started
# This is a Jupyter notebook. Download this .ipynb file locally/save a copy in your personal Google Drive account.
# 
# You can run these in two ways.
# 
# <br>
# 
# **Option 1: Google Colab**
# 
# *This is recommended, but sessions may disconnect after some time.*
# 
# *On the upper right, try to get `Change runtime type > T4 GPU` (if it's available) for GPU-enabled inference, instead of just `CPU`.*
# 
# Go to https://colab.research.google.com/
# 
# Click `File > Open notebook > Upload`  
# (Alternatively, click `File > Open notebook > Google Drive`)
# 
# <br>
# 
# **Option 2: Run the notebook locally**
# 
# In a Terminal with Python installed, run `pip install notebook`.
# 
# Then in the directory where the file was downloaded, run `jupyter notebook`.
# 
# <br>
# 
# ## Running a Cell
# To run a cell, click the Play button. (Or use Ctrl+Enter / Cmd+Enter)
# 
# - Code cells are generally in Python
# - Lines prefixed with `!` are shell commands (e.g. `!pip install`)
# - Text cells support Markdown formatting
# 
# On the toolbar to the left, you can view the Table of Contents and also run a specific section at once.

# %% [markdown]
# # **Week 2: Disambiguation & Structured Outputs**
# 

# %%
# Install the OpenAI Python SDK
%pip install openai --quiet

# %%
!sudo apt-get install zstd
!curl -fsSL https://ollama.com/install.sh | sh
!pip install ollama

# %%
import subprocess, time
subprocess.Popen(["ollama", "serve"])
time.sleep(5)

# %%
!ollama pull llama3.2:3b

# %%
from openai import OpenAI
import json, re

MODEL = "llama3.2:3b"

# Point the OpenAI SDK at the Ollama local endpoint
# Can be modified to make use of OpenAI's hosted API by changing the base_url and providing a valid api_key
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # required by the SDK; Ollama ignores the value
)

def complete(messages: list[dict], model: str = MODEL) -> str:
    """Send a chat completion request to the local Ollama server."""
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content

# Sanity check
print(complete([{"role": "user", "content": "Reply with only the word: ready"}]))

# %% [markdown]
# # Section 1. Extracting Structure from the Input
# 
# Raw user input is ambiguous. Before we can act on it, we need to identify *what* the user wants (intent) and gather the required details (slots).

# %% [markdown]
# ## 1.1 Intent Classification
# 
# Four design decisions:
# 
# 1. **Define Categories** — `BOOK_FLIGHT`, `MODIFY_BOOKING`, `CANCEL`, `FAQ` — each with a description
# 1. **System Prompt** — instructs the LLM to classify user input into the defined categories
# 1. **Few-Shot Examples** — provide labeled examples for each intent category
# 1. **Output Format** — JSON with `intent` and `confidence` fields; safe default to `FAQ` on low confidence or parse failure
# 
# | Intent | Description |
# | ------ | ----------- |
# | `BOOK_FLIGHT` | User wants to book a new flight |
# | `MODIFY_BOOKING` | User wants to change an existing booking |
# | `CANCEL` | User wants to cancel a booking |
# | `FAQ` | General question about flights or the service |

# %%
# ── 1. Define Categories ─────────────────────────────────────────────────
FLIGHT_INTENTS = {
    "BOOK_FLIGHT":    "User wants to book a new flight (e.g., 'I need a flight to Tokyo', 'Book me a seat to Manila')",
    "MODIFY_BOOKING": "User wants to change an existing booking (e.g., 'Change my flight to tomorrow', 'Upgrade to business')",
    "CANCEL":         "User wants to cancel a booking (e.g., 'Cancel my flight', 'I need to cancel my reservation')",
    "FAQ":            "General question about flights or the service (e.g., 'What is the baggage limit?', 'Do you fly to Osaka?')",
    "SEAT_UPGRADE":   "User wants to upgrade their seat to a higher-tier airplane seat (e.g. 'Get me a better seat', 'Change my seat to first-class')", # added by Wesner Almin III

}

# ── 2. System Prompt ──────────────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = (
    "You are an intent classifier for a flight booking assistant.\n\n"
    "Classify the user's message into EXACTLY ONE of these intents:\n"
    f"{"\n".join([f"- {k}: {v}" for k, v in FLIGHT_INTENTS.items()])}\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    '{"intent": "INTENT_NAME", "confidence": 0.95, "reasoning": "brief reason"}\n\n'
    "Rules:\n"
    "- intent must be one of the intent names above\n"
    "- confidence is a float between 0 and 1\n"
    "- choose the most likely intent if the message could fit multiple"
)

# ── 3. Few-Shot Examples ──────────────────────────────────────────────────
FEW_SHOT_EXAMPLES = [
    {"role": "user",      "content": "I need to book a flight to Tokyo"},
    {"role": "assistant", "content": '{"intent": "BOOK_FLIGHT", "confidence": 0.98, "reasoning": "User explicitly wants to book a flight"}'},
    {"role": "user",      "content": "Can I change my flight to next Friday?"},
    {"role": "assistant", "content": '{"intent": "MODIFY_BOOKING", "confidence": 0.96, "reasoning": "User wants to change an existing booking"}'},
    {"role": "user",      "content": "Cancel my reservation please"},
    {"role": "assistant", "content": '{"intent": "CANCEL", "confidence": 0.97, "reasoning": "User wants to cancel a booking"}'},
    {"role": "user",      "content": "What is the baggage allowance for economy?"},
    {"role": "assistant", "content": '{"intent": "FAQ", "confidence": 0.95, "reasoning": "User asking a general service question"}'},

    # the following are added by Wesner Almin III
    {"role": "user",      "content": "Upgrade my seat to premium economy"}, # added by user
    {"role": "assistant", "content": '{"intent": "SEAT_UPGRADE", "confidence": 0.95, "reasoning": "User wants to upgrade their seat tier to a better / more expensive option."}'}, # added by user
    {"role": "user",      "content": "I want a better seat, first class maybe?"}, # added by user
    {"role": "assistant", "content": '{"intent": "SEAT_UPGRADE", "confidence": 0.94, "reasoning": "Expressing dissatisfaction, the user wants a higher class-tier seat than what they currently have."}'}, # added by user
]

# ── 4. Output Format — JSON with safe default to FAQ ─────────────────────
def classify_intent(user_message: str, model: str = MODEL) -> dict:
    messages = [
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        *FEW_SHOT_EXAMPLES,
        {"role": "user", "content": user_message},
    ]
    response = complete(messages, model)

    try:
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in response")
        result = json.loads(match.group())
        intent = result.get("intent", "")
        confidence = float(result.get("confidence", 0.0))
        # Safe default: unknown intent or low confidence → FAQ
        if intent not in FLIGHT_INTENTS or confidence < 0.5:
            return {"intent": "FAQ", "confidence": 0.0,
                    "fallback": True, "raw": response}
        return result
    except (json.JSONDecodeError, ValueError):
        # Safe default: any parse failure → FAQ
        return {"intent": "FAQ", "confidence": 0.0,
                "fallback": True, "raw": response}


# %%
# ── Test ──────────────────────────────────────────────────────────────────
tests = [
    "I need to book a flight to Tokyo sometime next month",
    "Can you upgrade my seat to business class?",
    "I want to cancel my booking",
    "Do you have direct flights from Manila to Singapore?",
]

for msg in tests:
    result = classify_intent(msg)
    print(f"Input : {msg!r}")
    print(f"Intent: {result.get('intent')} ({float(result.get('confidence', 0)):.0%})")
    print(f"Reason: {result.get('reasoning', 'fallback')}")
    print()

# %%
# DEMO: Additional queries
tests = [
    "I want to go on a trip",
    "What can you do?",
    "Can you do my homework",
]

for msg in tests:
    result = classify_intent(msg)
    print(f"Input : {msg!r}")
    print(f"Intent: {result.get('intent')} ({float(result.get('confidence', 0)):.0%})")
    print(f"Reason: {result.get('reasoning', 'fallback')}")
    print()

# %% [markdown]
# ### [EXERCISE] Intent Classification
# 
# **Try it yourself:**
# 
# 1. **Test your own messages** — run `classify_intent()` on 3–5 messages of your own. Are the results what you expected?
# 2. **Add a new intent** — extend `FLIGHT_INTENTS` with a `SEAT_UPGRADE` intent. Write 2 few-shot examples and test it.
# 3. **Stress-test the fallback** — send a completely off-topic message (e.g. `"What's the weather like?"`). What intent is returned? What is the confidence score?
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

tests = [
    "Book me a flight to tokyo",
    "I'm hungry for some action",
    "I want a better seat than what I have",
    "Can you sing me a song?",
    "Does the airplane have food?",
]

for msg in tests:
    result = classify_intent(msg)
    print(f"Input : {msg!r}")
    print(f"Intent: {result.get('intent')} ({float(result.get('confidence', 0)):.0%})")
    print(f"Reason: {result.get('reasoning', 'fallback')}")
    print()

# %% [markdown]
# ## 1.2 Slot Filling
# 
# Four steps:
# 
# 1. **Define Required Slots** — `BOOK_FLIGHT` needs: `origin`, `destination`, `date`, `passengers`
# 2. **Extract Slots** — use the LLM to extract slot values from the initial message
# 3. **Track Completeness** — identify which slots are filled vs. missing
# 4. **Generate Follow-ups** — natural follow-up questions for missing slots
# 
# > Initial Message → Extract Slots → Check Completeness → Ask Follow-up or Proceed
# 
# Slot schema for `BOOK_FLIGHT`:
# 
# | Slot | Required | Description |
# | ---- | :------: | ----------- |
# | `origin` | **Yes** | Departure city or airport |
# | `destination` | **Yes** | Arrival city or airport |
# | `date` | **Yes** | Travel date |
# | `passengers` | **Yes** | Number of passengers |
# | `seat_class` | No | economy / business / first |

# %%
# ── 1. Define Required Slots ─────────────────────────────────────────────
SLOT_DEFINITIONS = {
    "BOOK_FLIGHT": {
        "origin":      {"description": "Departure city or airport (e.g., Manila, MNL)",  "required": True},
        "destination": {"description": "Arrival city or airport (e.g., Tokyo, NRT)",     "required": True},
        "date":        {"description": "Travel date in YYYY-MM-DD format",    "required": True},
        "passengers":  {"description": "Number of passengers",                            "required": True},
        "seat_class":  {"description": "Seat class: economy / business / first",         "required": False},
        "meal_preference":  {"description": "Meal preference: vegetarian / halal",         "required": False},

    },
    "MODIFY_BOOKING": {
        "booking_ref":      {"description": "Booking reference or confirmation number",  "required": False},
        "change_type":      {"description": "What to modify: date / seat / passengers",  "required": True},
        "new_value":        {"description": "The new value for the change",              "required": True},
    },
    "CANCEL": {
        "booking_ref": {"description": "Booking reference or confirmation number", "required": False},
        "reason":      {"description": "Reason for cancellation",                  "required": False},
    },
    "FAQ": {
        "topic": {"description": "The topic the user is asking about", "required": True},
    },
}

# ── 2. Extract Slots ──────────────────────────────────────────────────────
SLOT_EXTRACTION_TEMPLATE = (
    "You are a slot extraction assistant for a flight booking service.\n\n"
    "The user's intent is: {intent}\n\n"
    "Extract the following information from the user's message:\n{slot_definitions}\n\n"
    "Respond with ONLY a JSON object using the slot names as keys. "
    "Use null for any information not mentioned in the message."
)

def extract_slots(user_message: str, intent: str, model: str = MODEL) -> dict:
    slots     = SLOT_DEFINITIONS.get(intent, {})
    slot_desc = "\n".join([f"- {name}: {info['description']}" for name, info in slots.items()])
    prompt    = SLOT_EXTRACTION_TEMPLATE.format(intent=intent, slot_definitions=slot_desc)

    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": user_message}],
        model
    )
    # Match the first JSON object in the response
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            extracted = json.loads(match.group())
            return {name: extracted.get(name) for name in slots}
        except json.JSONDecodeError:
            pass
    return {name: None for name in slots}

# ── 3. Track Completeness ─────────────────────────────────────────────────
def get_missing_slots(intent: str, filled_slots: dict) -> list:
    """Return required slot names that are still None."""
    return [
        name for name, info in SLOT_DEFINITIONS.get(intent, {}).items()
        if info.get("required", False) and filled_slots.get(name) is None
    ]

# ── 4. Generate Follow-ups ────────────────────────────────────────────────
CLARIFICATION_PROMPT = (
    "You are a helpful flight booking assistant.\n\n"
    "The user wants to: {intent_description}\n"
    "Information already collected: {known_slots}\n"
    "You need to ask about: {missing_slot} — {slot_description}\n\n"
    "Write ONE short, natural, friendly question to collect this information.\n"
    "Do not use technical terms like 'slot'. Respond with ONLY the question."
)

def generate_clarification(
    intent: str, filled_slots: dict, missing_slot: str, model: str = MODEL
) -> str:
    slot_info   = SLOT_DEFINITIONS.get(intent, {}).get(missing_slot, {})
    slot_desc   = slot_info.get("description", missing_slot)
    intent_desc = FLIGHT_INTENTS.get(intent, intent)
    known       = {k: v for k, v in filled_slots.items() if v is not None}

    prompt = CLARIFICATION_PROMPT.format(
        intent_description=intent_desc,
        known_slots=json.dumps(known) if known else "nothing yet",
        missing_slot=missing_slot,
        slot_description=slot_desc,
    )
    return complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": "Please ask me."}],
        model
    ).strip()


# %%
# ── Test ──────────────────────────────────────────────────────────────────
test_cases = [
    # Partial message — destination and date extracted, origin/passengers missing
    ("I want to book a flight to Tokyo for two people on May 8, 2026", "BOOK_FLIGHT"),
    # Modify with ref
    ("Change my flight AB123 to next Friday",                "MODIFY_BOOKING"),
    # Cancel with no details
    ("Cancel my booking",                                    "CANCEL"),
]

for message, intent in test_cases:
    slots   = extract_slots(message, intent)
    missing = get_missing_slots(intent, slots)
    print(f"Message : {message!r}")
    print(f"Intent  : {intent}")
    print(f"Slots   :\n{json.dumps(slots, indent=2)}")
    print(f"Missing : {missing or 'none'}")
    if missing:
        q = generate_clarification(intent, slots, missing[0])
        print(f"Bot asks: {q}")
    print()

# %%
# DEMO
# ── Test ──────────────────────────────────────────────────────────────────
test_cases = [
    # No date
    ("I want to book a flight to Tokyo for two people", "BOOK_FLIGHT"),
    # Modify with ref
    ("Change my flight AB123 to next Friday",                "MODIFY_BOOKING"),
    # Cancel with no details
    ("Cancel my booking",                                    "CANCEL"),
]

for message, intent in test_cases:
    slots   = extract_slots(message, intent)
    missing = get_missing_slots(intent, slots)
    print(f"Message : {message!r}")
    print(f"Intent  : {intent}")
    print(f"Slots   :\n{json.dumps(slots, indent=2)}")
    print(f"Missing : {missing or 'none'}")
    if missing:
        q = generate_clarification(intent, slots, missing[0])
        print(f"Bot asks: {q}")
    print()

# %% [markdown]
# #### Clarification Dialogue
# 
# Five rules:
# 
# | Rule | Principle | Example |
# | ---- | --------- | ------- |
# | **One at a Time** | Ask one question per turn | Never fire a list of questions |
# | **Prioritize** | Most critical missing slot first | Ask for `origin` before `seat_class` |
# | **Natural Language** | Friendly phrasing | `"Where will you be flying from?"` not `"Provide origin_slot"` |

# %% [markdown]
# ### [EXERCISE] Slot Filling
# 
# **Try it yourself:**
# 
# 1. **Extract from a vague message** — run `extract_slots()` on `"I need to fly to Singapore sometime this week"`. Which slots are filled? Which are missing? What clarification question does the bot generate?
# 2. **Add a new optional slot** — add a `meal_preference` slot (e.g. `"vegetarian"`, `"halal"`) to the `BOOK_FLIGHT` schema. Test that it is extracted when mentioned in a message.
# 3. **Test date resolution** — run `extract_slots()` on a message with a relative date of your choice (e.g. `"next Monday"`, `"in two weeks"`). Does it resolve correctly to an absolute `YYYY-MM-DD` date?
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output


test_cases = [
    # Fly to singapore
    ("I need to fly to Singapore sometime this week", "BOOK_FLIGHT"),
    # Meal preference test
    ("Book me a flight to Saudi Arabia on Wednesday, and some halal food",                "BOOK_FLIGHT"),
    # Relative date
    ("Book me a flight from Manila to Tokyo set 5 days from now",                                    "BOOK_FLIGHT"),
]

for message, intent in test_cases:
    slots   = extract_slots(message, intent)
    missing = get_missing_slots(intent, slots)
    print(f"Message : {message!r}")
    print(f"Intent  : {intent}")
    print(f"Slots   :\n{json.dumps(slots, indent=2)}")
    print(f"Missing : {missing or 'none'}")
    if missing:
        q = generate_clarification(intent, slots, missing[0])
        print(f"Bot asks: {q}")
    print()

# %% [markdown]
# # Section 2. Error Handling

# %% [markdown]
# ## 2.1 Default Responses

# %% [markdown]
# #### Safe Default to FAQ Intent
# 
# `classify_intent()` returns `{"intent": "FAQ", "fallback": True}` when confidence is below 0.5 or the intent label is unrecognised. This ensures the pipeline never slot-fills on a misclassified input.

# %%
# DEMO: Additional queries
tests = [
    "I want to go to Japan?",
    "umm",
]

for msg in tests:
    result = classify_intent(msg)
    print(f"Input : {msg!r}")
    print(f"Intent: {result.get('intent')} ({float(result.get('confidence', 0)):.0%})")
    print(f"Reason: {result.get('reasoning', 'fallback')}")
    print()

# %% [markdown]
# ### [EXERCISE] Default Responses
# 
# **Try it yourself:**
# 
# 1. **Trigger the FAQ fallback** — run `classify_intent()` on an off-topic or completely ambiguous message (e.g. `"umm"`, `"I dunno"`, `"help"`). Does it fall back to `FAQ`?
# 2. **Inspect the raw response** — print the full return dict including the `"fallback"` and `"raw"` keys. What did the LLM actually output before the fallback kicked in?
# 
# - [x] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

# DEMO: Additional queries
tests = [
    "HyperX soloist for the three peat",
]

for msg in tests:
    result = classify_intent(msg)
    print(f"Input : {msg!r}")
    print(f"Intent: {result.get('intent')} ({float(result.get('confidence', 0)):.0%})")
    print(f"Reason / fallback: {result.get('reasoning', 'fallback')}")
    print(f"Raw: {result.get('raw')}")

# %% [markdown]
# ## 2.2 Graceful Degradation

# %% [markdown]
# #### Handling Ambiguous Dates and Clarification
# 
# | Feature | Example | Handling |
# | --------- | ------- | -------- |
# | **Ambiguous Dates** | `"next Friday"` | Resolve relative to the current date |
# | **Clarification** | `"I need a flight"` | Ask follow-up questions for missing slots |

# %% [markdown]
# #### Resolving Relative Dates
# 
# Date expressions like *"today"*, *"tomorrow"*, or *"next Friday"* are relative — the LLM has no knowledge of the system clock, so it cannot resolve them on its own.
# 
# The fix is simple: **inject today's date into the slot extraction prompt.** The LLM already knows how to do date arithmetic; it just needs the anchor.
# 
# ```
# Today is 2026-05-19 (Tuesday).
# Extract the following slots …
# ```
# 
# With that one line added, `"next Tuesday"` becomes `"2026-05-26"`, `"sometime next month"` becomes `"2026-06-01"`, and so on — no extra library or tool-calling loop required.

# %%
import datetime

# ── Slot extraction prompt — now includes today's date as context ──────────
SLOT_EXTRACTION_TEMPLATE = (
    "You are a slot extraction assistant for a flight booking service.\n"
    "Today is {today} ({weekday}).\n\n"
    "The user's intent is: {intent}\n\n"
    "Extract the following information from the user's message:\n{slot_definitions}\n\n"
    "If a date field contains a relative expression (e.g. 'today', 'tomorrow', 'next Friday',\n"
    "'next month'), resolve it to an absolute YYYY-MM-DD date using today's date above.\n\n"
    "Respond with ONLY a JSON object using the slot names as keys. "
    "Use null for any information not mentioned in the message."
)

def extract_slots(user_message: str, intent: str, model: str = MODEL) -> dict:
    """Extract slots; the LLM resolves relative dates using today's date from the prompt."""
    slots     = SLOT_DEFINITIONS.get(intent, {})
    slot_desc = "\n".join([f"- {name}: {info['description']}" for name, info in slots.items()])

    today = datetime.date.today()
    prompt = SLOT_EXTRACTION_TEMPLATE.format(
        today   = today.isoformat(),
        weekday = today.strftime("%A"),
        intent  = intent,
        slot_definitions = slot_desc,
    )

    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": user_message}],
        model,
    )
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            extracted = json.loads(match.group())
            return {name: extracted.get(name) for name in slots}
        except json.JSONDecodeError:
            pass
    return {name: None for name in slots}



# %%
# ── Test ──────────────────────────────────────────────────────────────────
print(f"Running tests — today is {datetime.date.today()} ({datetime.date.today().strftime('%A')})")
print("=" * 54)

date_tests = [
    ("Book me a flight from Manila to Tokyo today, 1 passenger",  "BOOK_FLIGHT"),
    ("I need a flight to Singapore for tomorrow",                   "BOOK_FLIGHT"),
    ("Change my booking to next Friday",                            "MODIFY_BOOKING"),
    ("Book a flight to Seoul sometime next month",                  "BOOK_FLIGHT"),
    ("I want to fly to Bangkok in 3 days",                         "BOOK_FLIGHT"),
]

for msg, intent in date_tests:
    slots    = extract_slots(msg, intent)
    date_val = slots.get("date") or slots.get("new_value")
    print(f"Input : {msg!r}")
    print(f"date  => {date_val!r}")
    print()

# %%
# DEMO: additional queries
print(f"Running tests — today is {datetime.date.today()} ({datetime.date.today().strftime('%A')})")
print("=" * 54)

date_tests = [
    ("I need a flight to Korea for tomorrow",                   "BOOK_FLIGHT"),
    ("I want to fly to Bangkok in 2 days",                         "BOOK_FLIGHT"),
]

for msg, intent in date_tests:
    slots    = extract_slots(msg, intent)
    date_val = slots.get("date") or slots.get("new_value")
    print(f"Input : {msg!r}")
    print(f"date  => {date_val!r}")
    print()

# %% [markdown]
# ### [EXERCISE] — Graceful Degradation
# 
# Try a couple of prompts to see how well it's able to format the date.
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

print(f"Running tests — today is {datetime.date.today()} ({datetime.date.today().strftime('%A')})")
print("=" * 54)

date_tests = [
    ("I need a flight to Korea for tomorrow",                   "BOOK_FLIGHT"),
    ("I want to fly to Bangkok in 2 days",                         "BOOK_FLIGHT"),
    ("I want to fly to Shanghai in 240 days",                         "BOOK_FLIGHT"),
    ("I want to fly to Tokyo in 18 weeks",                         "BOOK_FLIGHT"),
    ("I want to fly to New York in 8 hours",                         "BOOK_FLIGHT"),
]

for msg, intent in date_tests:
    slots    = extract_slots(msg, intent)
    date_val = slots.get("date") or slots.get("new_value")
    print(f"Input : {msg!r}")
    print(f"date  => {date_val!r}")
    print()

# %% [markdown]
# ## 2.3 Edge Cases

# %%
# Edge case: origin == destination — slot extraction passes through; Pydantic (Section 3) catches it
msg = "I want to fly from Tokyo to Tokyo"
print(f"Input: {msg!r}")
print()

result = classify_intent(msg)
intent = result.get("intent")
print(f"Classified as : {intent} ({float(result.get('confidence', 0)):.0%})")

slots = extract_slots(msg, intent)
print(f"Extracted slots : {json.dumps(slots, indent=2)}")
print()
print("Slot extraction sees no problem — both 'origin' and 'destination' are populated.")
print("The model_validator in Section 3 raises:")
print("  ValueError: origin and destination cannot be the same city (Tokyo)")

# %%
# Edge case: multi-intent input — the classifier picks the dominant intent
msg = "Book a flight and a hotel"
print(f"Input: {msg!r}")
print()

result = classify_intent(msg)
intent = result.get("intent")
print(f"Classified as : {intent} ({float(result.get('confidence', 0)):.0%})")
print("The hotel request is silently dropped — only the flight intent survives.")
print()

slots   = extract_slots(msg, intent)
missing = get_missing_slots(intent, slots)
print(f"Extracted slots : {json.dumps(slots, indent=2)}")
print(f"Missing required: {missing}")
print()
print("In production: detect multiple booking objects in the input")
print("and split them into parallel disambiguation flows before slot filling.")

# %% [markdown]
# ### [EXERCISE] — Edge Cases
# 
# **Try it yourself:**
# 
# 1. **Write a new edge case** — pick one scenario and write a focused test for it:
#    - A message in a different language (e.g. `"Reservame un vuelo a Tokyo"`)
#    - A message that mixes 3 or more intents
#    - An unusually phrased future date (e.g. `"the day after New Year's"`)
# 2. **Observe the output** — does the pipeline handle it gracefully, fall back, or produce incorrect output? What would you change to handle it better?
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

# Edge case: multi-intent input — the classifier picks the dominant intent
msg = "東京からマニラへの20日後のフライトを予約してください。"
print(f"Input: {msg!r}")
print()

result = classify_intent(msg)
intent = result.get("intent")
print(f"Classified as : {intent} ({float(result.get('confidence', 0)):.0%})")
print("The intention to book a flight is correctly identified.")
print()

slots   = extract_slots(msg, intent)
missing = get_missing_slots(intent, slots)
print(f"Extracted slots : {json.dumps(slots, indent=2)}")
print(f"Missing required: {missing}")
print()
print("Slot extraction fails to identify the origin (Manila),")
print("And there correctly is no context for the number of passengers.")

# %% [markdown]
# # Section 3. Structuring the Output
# 
# Two steps:
# 
# **Define & Parse** — define a Pydantic model for each intent type (e.g. `FlightBooking`). Parse the LLM's JSON output against the model.
# 
# **Validate & Retry** — on validation failure, the **specific Pydantic error is fed back to the LLM** so it can correct the slots. Retry up to **3 attempts** before falling back to a human agent.
# 
# ```
# slots  →  Pydantic validate
#               │ fail
#               ▼
#         LLM( slots + error_msg )  →  corrected slots
#               │
#               ▼  (up to 3×)
#         Pydantic validate  →  FlightBooking  ✓
#               │ still failing after 3 attempts
#               ▼
#         Human agent prompted field-by-field
#         (Enter to keep current value, or type a correction)
# ```

# %%
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal
import datetime

# ── FlightBooking — the Pydantic model for BOOK_FLIGHT ────────────────────
class FlightBooking(BaseModel):
    origin:      str           = Field(description="Departure city or airport")
    destination: str           = Field(description="Arrival city or airport")
    date:        datetime.date = Field(description="Travel date")
    passengers:  int           = Field(default=1, ge=1, description="Number of passengers")
    seat_class:  Optional[Literal["economy", "business", "first"]] = Field(default="economy")

    # Pydantic coerces any valid ISO string ("2025-06-15") to datetime.date automatically.
    # The validator below adds the business rule: the date must not be in the past.
    @field_validator("date", mode="before")
    @classmethod
    def date_must_be_future(cls, v) -> datetime.date:
        parsed = datetime.date.fromisoformat(str(v)) if not isinstance(v, datetime.date) else v
        if parsed < datetime.date.today():
            raise ValueError(f"travel date {parsed} is in the past")
        return parsed

    @field_validator("origin", "destination")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("cannot be empty")
        return v.strip().title()

    @model_validator(mode="after")
    def origin_differs_from_destination(self) -> "FlightBooking":
        if self.origin.lower() == self.destination.lower():
            raise ValueError(
                f"origin and destination cannot be the same city ({self.origin})"
            )
        return self

    @field_validator("passengers")
    @classmethod
    def max_group_size(cls, v):
        if v > 9:
            raise ValueError("group bookings are limited to 9 passengers")
        return v

# ── LLM-assisted slot fixer ───────────────────────────────────────────────
# NOTE: This is a simple implementation that re-prompts the LLM with the exact Pydantic error message.
# There is a high chance the LLM will hallucinate information.
FIX_SLOTS_PROMPT = (
    "You are a flight booking assistant. The slot values below failed schema validation.\n\n"
    f"Today is {datetime.date.today().isoformat()} ({datetime.date.today():%A}). "
    "Use this as context when fixing the date field. "
    "If the date is invalid or in the past, replace it with the current date in YYYY-MM-DD format.\n\n"
    "Current slots:\n{current_slots}\n\n"
    "Validation error:\n{error_message}\n\n"
    "Fix the slots so they satisfy the validation rules, then return ONLY "
    "a corrected JSON object with the same keys. Do not explain anything."
)

def fix_slots_with_llm(slots: dict, error_msg: str, model: str = MODEL) -> dict:
    """Re-prompt the LLM with the specific Pydantic error to get corrected slots."""
    prompt = FIX_SLOTS_PROMPT.format(
        current_slots=json.dumps(slots, indent=2),
        error_message=error_msg,
    )
    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": "Return the corrected JSON."}],
        model,
    )
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            fixed = json.loads(match.group())
            return {k: fixed.get(k) if fixed.get(k) is not None else v
                    for k, v in slots.items()}
        except json.JSONDecodeError:
            pass
    return slots


# ── Validate & Retry — LLM re-prompted with error; human fallback via input()
def validate_booking(slots: dict, model: str = MODEL, max_retries: int = 3):
    """
    Try to build a FlightBooking from slots.
    On each failure, feed the exact Pydantic error back to the LLM so it can
    correct the offending slot values, then retry.
    After max_retries, falls back to a human agent who is prompted field-by-field.

    Returns (FlightBooking | None, final_error_msg).
    """
    relevant = {
        k: v for k, v in slots.items()
        if k in FlightBooking.model_fields and v is not None
    }
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            return FlightBooking(**relevant), ""
        except Exception as e:
            last_error = str(e)
            print(f"  [attempt {attempt}/{max_retries}] Validation failed: {last_error}")

            if attempt < max_retries:
                print(f"  Re-prompting LLM with error...")
                relevant = fix_slots_with_llm(relevant, last_error, model)
                print(f"  LLM-corrected slots: {relevant}")

    # LLM couldn't fix it — escalate to human agent, one field at a time
    print("\n  All LLM attempts exhausted — escalating to human agent.")
    print(f"  Validation error: {last_error}\n")

    for field_name in FlightBooking.model_fields:
        current = relevant.get(field_name)
        answer = input(f"  [Human Agent] {field_name} (current: {current!r}): ").strip()
        if answer:
            relevant[field_name] = answer

    try:
        return FlightBooking(**relevant), ""
    except Exception as e:
        print(f"  Human correction still invalid: {e}")
        return None, str(e)


# %%
# ── Tests ─────────────────────────────────────────────────────────────────
print("--- Valid booking ---")
valid = {
    "origin": "Manila", "destination": "Tokyo",
    "date": "2026-08-15", "passengers": 2, "seat_class": "economy",
}
booking, err = validate_booking(valid)
if booking:
    print(booking.model_dump_json(indent=2))
    print(f"  date type: {type(booking.date)}")

print("\n--- Invalid: non-date string ---")
booking, err = validate_booking({**valid, "date": "banana"})
if not booking:
    print(f"Rejected: {err}")

# %%
# DEMO: additional queries
print("--- Valid booking ---")
data = {
    "origin": "Manila", "destination": "Tokyo",
    "date": "2025-08-15", "passengers": 2, "seat_class": "economy",  # Past date may be filled with the current
}
booking, err = validate_booking(data)
if booking:
    print(booking.model_dump_json(indent=2))
    print(f"  date type: {type(booking.date)}")



# %% [markdown]
# ## [EXERCISE] — Structuring the Output
# 
# **Try it yourself:**
# 
# 1. **Trigger the retry loop** — call `validate_booking()` with a slot dict where `origin` and `destination` are the same city (e.g. both `"Manila"`). Does the LLM correct it in one attempt? What error message does it receive?
# 2. **Add a new field validator** — extend `FlightBooking` with a validator that rejects `passengers > 9` (most airlines cap group bookings at 9). Test it with `"passengers": 12`.
# 3. **Build your own Pydantic model** — define a `HotelBooking` model with at least 3 required fields and 1 `@field_validator`. Adapt `validate_booking()` to use your new model and test it with valid and invalid data.
# 4. **Experiment with the prompts and validators** - it's possible that the LLM inserts its "best guess" of the fields (like the date). Try modifying the prompts and validation flow to experiment with different ways of handling this (e.g. keeping the field blank, or exhausting the retries)
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

print("--- Valid booking ---")
data = {
    "origin": "Manila", "destination": "Manila",
    "date": "2025-08-15", "passengers": 2, "seat_class": "economy",  # Past date may be filled with the current
}
booking, err = validate_booking(data)
if booking:
    print(booking.model_dump_json(indent=2))
    print(f"  date type: {type(booking.date)}")


# %%
# YOUR CODE HERE
# Leave the cell output

from pydantic import ValidationError

class HotelBooking(BaseModel):
    hotel_name: str
    check_in: datetime.date
    check_out: datetime.date
    guests: int = Field(ge=1)

    @field_validator("hotel_name")
    @classmethod
    def hotel_name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Hotel name cannot be empty.")
        return v.strip().title()

    @model_validator(mode="after")
    def dates_are_valid(self):
        if self.check_in < datetime.date.today():
            raise ValueError("The check-in date cannot be in the past.")

        if self.check_out <= self.check_in:
            raise ValueError("The check-out date must be after the check-in date")

        return self


def validate_booking(data: dict):
    try:
        booking = HotelBooking.model_validate(data)
        return booking, ""
    except ValidationError as e:
        return None, str(e)

# %%
# YOUR CODE HERE
# Leave the cell output

print("--- Valid booking ---")

data = {
    "hotel_name": "Grand Hyatt Manila",
    "check_in": "2026-07-10",
    "check_out": "2026-07-15",
    "guests": 2
}

booking, err = validate_booking(data)

if booking:
    print(booking.model_dump_json(indent=2))
else:
    print(err)



print("--- Invalid booking ---")

data = {
    "hotel_name": "",
    "check_in": "2026-07-15",
    "check_out": "2026-07-10",
    "guests": 2
}

booking, err = validate_booking(data)

if booking:
    print(booking.model_dump_json(indent=2))
else:
    print(err)

# %%
# FILLER/IRRELEVANT CELL: reset validate booking to normal (purely for keeping logic intact moving forward, throughout the notebook)
def validate_booking(slots: dict, model: str = MODEL, max_retries: int = 3):
    """
    Try to build a FlightBooking from slots.
    On each failure, feed the exact Pydantic error back to the LLM so it can
    correct the offending slot values, then retry.
    After max_retries, falls back to a human agent who is prompted field-by-field.

    Returns (FlightBooking | None, final_error_msg).
    """
    relevant = {
        k: v for k, v in slots.items()
        if k in FlightBooking.model_fields and v is not None
    }
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            return FlightBooking(**relevant), ""
        except Exception as e:
            last_error = str(e)
            print(f"  [attempt {attempt}/{max_retries}] Validation failed: {last_error}")

            if attempt < max_retries:
                print(f"  Re-prompting LLM with error...")
                relevant = fix_slots_with_llm(relevant, last_error, model)
                print(f"  LLM-corrected slots: {relevant}")

    # LLM couldn't fix it — escalate to human agent, one field at a time
    print("\n  All LLM attempts exhausted — escalating to human agent.")
    print(f"  Validation error: {last_error}\n")

    for field_name in FlightBooking.model_fields:
        current = relevant.get(field_name)
        answer = input(f"  [Human Agent] {field_name} (current: {current!r}): ").strip()
        if answer:
            relevant[field_name] = answer

    try:
        return FlightBooking(**relevant), ""
    except Exception as e:
        print(f"  Human correction still invalid: {e}")
        return None, str(e)


# %% [markdown]
# # Section 4. **Demo: End-to-End Pipeline Walkthrough**
# 
# | Step | Value |
# | ---- | ----- |
# | **Input** | `"I need to book a flight to Tokyo sometime next month for 2 passengers"` |
# | **Intent** | `BOOK_FLIGHT` (confidence: 0.96) |
# | **Extracted** | `destination="Tokyo"`, `date="next month"` |
# | **Missing** | `origin`, `exact_date`, `passengers`, `class` |
# | **Clarification** | `"Where will you be flying from?"` → `"Manila"` |
# | **Output** | Validated JSON with all booking parameters |

# %%
def run_disambiguation_pipeline(
    user_message: str,
    model: str = MODEL,
    verbose: bool = True,
) -> dict:
    """Complete 5-stage flight booking disambiguation pipeline."""
    SEP = "-" * 54

    # [1] Intent Classification ───────────────────────────────────────────
    if verbose: print(f"{SEP}\n[1] Intent Classification")
    intent_result = classify_intent(user_message, model)
    intent        = intent_result.get("intent", "FAQ")
    confidence    = float(intent_result.get("confidence", 0.0))
    if verbose: print(f"    => {intent} ({confidence:.0%})")

    # [2] Slot Extraction (relative dates resolved via LLM prompt injection) ──
    if verbose: print("[2] Slot Extraction")
    slots = extract_slots(user_message, intent, model)
    if verbose: print(f"    => {slots}")

    # [3] Slot Verification ───────────────────────────────────────────────
    if verbose: print("[3] Slot Verification")
    missing = get_missing_slots(intent, slots)
    if verbose: print(f"    => Missing required: {missing or 'none'}")

    # [4] Clarification Loop (up to 3 rounds via input(), or until slots filled)
    if verbose: print("[4] Clarification Loop")
    MAX_CLARIFICATION_ROUNDS = 3
    clarification_question = None
    for round_num in range(1, MAX_CLARIFICATION_ROUNDS + 1):
        missing = get_missing_slots(intent, slots)
        if not missing:
            break
        clarification_question = generate_clarification(intent, slots, missing[0], model)
        print(f"    Bot [{round_num}/{MAX_CLARIFICATION_ROUNDS}]: {clarification_question}")
        user_answer = input("    You: ").strip()
        if user_answer:
            extracted = extract_slots(user_answer, intent, model)
            for k, v in extracted.items():
                if v is not None and slots.get(k) is None:
                    slots[k] = v
        still_missing = get_missing_slots(intent, slots)
        if still_missing and verbose:
            print(f"    => Still missing: {still_missing}")
    missing = get_missing_slots(intent, slots)
    is_complete = not missing
    if missing:
        if verbose: print(f"    => Slots incomplete after {MAX_CLARIFICATION_ROUNDS} rounds: {missing}")
    else:
        if verbose: print("    => All required slots filled")

    # [5] Output Validation ───────────────────────────────────────────────
    validated_booking = None
    validation_error  = None
    if verbose: print("[5] Output Validation")
    if is_complete and intent == "BOOK_FLIGHT":
        booking, err = validate_booking(slots, model)
        if booking:
            validated_booking = booking.model_dump()
            if verbose: print(f"    => Valid: {validated_booking}")
        else:
            validation_error = err
            is_complete      = False
            if verbose: print(f"    => Validation failed — fallback to human agent")
    else:
        if verbose: print("    => Skipped (slots incomplete or non-booking intent)")

    return {
        "input":                  user_message,
        "intent":                 intent,
        "confidence":             confidence,
        "slots":                  slots,
        "missing_slots":          missing,
        "is_complete":            is_complete,
        "clarification_question": clarification_question,
        "validated_booking":      validated_booking,
        "validation_error":       validation_error,
    }

# %%
print("=" * 54)
print("DEMO: 'I need to book a flight to Tokyo sometime next month'")
print("=" * 54)
result = run_disambiguation_pipeline(
    "I need to book a flight to Tokyo sometime next month"
)

# ── Show the structured result ────────────────────────────────────────────
print("\nResult summary:")
print(f"  Intent      : {result['intent']} ({result['confidence']:.0%})")
print(f"  Extracted   : { {k:v for k,v in result['slots'].items() if v is not None} }")
print(f"  Missing     : {result['missing_slots']}")
print(f"  Bot asks    : {result['clarification_question']}")
print(f"  Validated   : {result['validated_booking']}")


# %%
# DEMO
print("=" * 54)
print("DEMO: 'I need to book a flight to Tokyo sometime next month'")
print("=" * 54)
result = run_disambiguation_pipeline(
    "I need to book a flight to Tokyo sometime next month"
)

# ── Show the structured result ────────────────────────────────────────────
print("\nResult summary:")
print(f"  Intent      : {result['intent']} ({result['confidence']:.0%})")
print(f"  Extracted   : { {k:v for k,v in result['slots'].items() if v is not None} }")
print(f"  Missing     : {result['missing_slots']}")
print(f"  Bot asks    : {result['clarification_question']}")
print(f"  Validated   : {result['validated_booking']}")


# %% [markdown]
# ## [EXERCISE] End-to-end Pipeline Walkthrough
# 
# Experiment with the complete pipeline.
# Run different prompts. Also try different settings for the max clarification rounds.
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

print("=" * 54)
print("Book me a flight from Manila to Jakarta next month for 2 passengers.'")
print("=" * 54)
result = run_disambiguation_pipeline(
    "Book me a flight from Manila to Jakarta next month for 2 passengers."
)

# ── Show the structured result ────────────────────────────────────────────
print("\nResult summary:")
print(f"  Intent      : {result['intent']} ({result['confidence']:.0%})")
print(f"  Extracted   : { {k:v for k,v in result['slots'].items() if v is not None} }")
print(f"  Missing     : {result['missing_slots']}")
print(f"  Bot asks    : {result['clarification_question']}")
print(f"  Validated   : {result['validated_booking']}")

# %%
print("=" * 54)
print("DEMO: 'I need to fly in an airplane with halal food, get me a flight to Iraq in exactly 2.5 days.'")
print("=" * 54)
result = run_disambiguation_pipeline(
    "I need to fly in an airplane with halal food, get me a flight to Iraq in exactly 2.5 days."
)

# ── Show the structured result ────────────────────────────────────────────
print("\nResult summary:")
print(f"  Intent      : {result['intent']} ({result['confidence']:.0%})")
print(f"  Extracted   : { {k:v for k,v in result['slots'].items() if v is not None} }")
print(f"  Missing     : {result['missing_slots']}")
print(f"  Bot asks    : {result['clarification_question']}")
print(f"  Validated   : {result['validated_booking']}")


# %%
print("=" * 54)
print("DEMO: 'Book me a flight from Manila to Haneda, Tokyo next month.'")
print("=" * 54)
result = run_disambiguation_pipeline(
    "Book me a flight from Manila to Haneda, Tokyo next month."
)

# ── Show the structured result ────────────────────────────────────────────
print("\nResult summary:")
print(f"  Intent      : {result['intent']} ({result['confidence']:.0%})")
print(f"  Extracted   : { {k:v for k,v in result['slots'].items() if v is not None} }")
print(f"  Missing     : {result['missing_slots']}")
print(f"  Bot asks    : {result['clarification_question']}")
print(f"  Validated   : {result['validated_booking']}")


# %% [markdown]
# # Section 5. **Food Ordering Disambiguation Chatbot**

# %% [markdown]
# **Requirements**
# 
# - Build disambiguation module for a food ordering chatbot
# - Detect ambiguous orders (e.g., "I want something spicy")
# - Generate clarifying questions to resolve ambiguity
# - Output structured order JSON with all required fields
# - Handle at least 5 different food-related intents
# 

# %% [markdown]
# ## 5.1 Extracting Structure from the Input

# %% [markdown]
# 
# 
# ### 5.1.1 Intent Classification
# 
# Four design decisions:
# 
# 1. **Define Categories** — 6 food-related intents, each with a description
# 2. **System Prompt** — instructs the LLM to classify user input into one category
# 3. **Few-Shot Examples** — 2 examples per intent (12 total)
# 4. **Output Format** — JSON with `intent` and `confidence` fields
# 
# | Intent | Description |
# | ------ | ----------- |
# | `ORDER_FOOD` | User wants to place a new food order |
# | `MODIFY_ORDER` | User wants to change an existing order |
# | `CANCEL_ORDER` | User wants to cancel an order |
# | `CHECK_STATUS` | User wants to know their order status |
# | `GET_RECOMMENDATION` | User wants food suggestions |
# | `CHECK_MENU` | User wants to browse what is available |

# %% [markdown]
# #### [EXERCISE] Intent Classification
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

# ── 1. Define Categories ─────────────────────────────────────────────────
FOOD_INTENTS = {
    "ORDER_FOOD":    "User wants to place a new food order (e.g., 'I want to order ramen', 'Buy me drinks')",
    "MODIFY_ORDER": "User wants to change an existing order (e.g., 'Change my order to have no drinks', 'Wait, add a burger to my order')",
    "CANCEL_ORDER": "User wants to cancel an order (e.g., 'Please cancel my order', 'Nevermind, drop my current set of orders')",
    "CHECK_STATUS":         "User wants to know their order status (e.g., 'How's my order coming in?', 'Is it on the way yet?')",
    "GET_RECOMMENDATION":            "User wants food suggestions (e.g., 'Have any ideas what I should get?', 'What's the recommendation for today?')",
    "CHECK_MENU":   "User wants to browse what is available (e.g. 'What's on the menu right now?', 'What do they have available today')",

}

# ── 2. System Prompt ──────────────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = (
    "You are an intent classifier for a flight booking assistant.\n\n"
    "Classify the user's message into EXACTLY ONE of these intents:\n"
    f"{"\n".join([f"- {k}: {v}" for k, v in FOOD_INTENTS.items()])}\n\n"
    "Respond with ONLY a JSON object in this exact format:\n"
    '{"intent": "INTENT_NAME", "confidence": 0.95, "reasoning": "brief reason"}\n\n'
    "Rules:\n"
    "- intent must be one of the intent names above\n"
    "- confidence is a float between 0 and 1\n"
    "- choose the most likely intent if the message could fit multiple"
)

# ── 3. Few-Shot Examples ──────────────────────────────────────────────────
FEW_SHOT_EXAMPLES = [
    {"role": "user",      "content": "I want to order 2 piece chicken and kimchi rice from Bok Chicken Taft."},
    {"role": "assistant", "content": '{"intent": "ORDER_FOOD", "confidence": 0.98, "reasoning": "User explicitly wants 2x chicken with additional Kimchi Rice from Bok Chicken Taft"}'},
    {"role": "user",      "content": "Can I change my order to not have kimchi rice?"},
    {"role": "assistant", "content": '{"intent": "MODIFY_ORDER", "confidence": 0.96, "reasoning": "User wants to change an existing order"}'},
    {"role": "user",      "content": "Cancel my order now"},
    {"role": "assistant", "content": '{"intent": "CANCEL_ORDER", "confidence": 0.97, "reasoning": "User wants to cancel an order"}'},
    {"role": "user",      "content": "What's happening to my order"},
    {"role": "assistant", "content": '{"intent": "CHECK_STATUS", "confidence": 0.95, "reasoning": "User wants to know the status of their current order."}'},
    {"role": "user",      "content": "Get me something spicy"},
    {"role": "assistant", "content": '{"intent": "GET_RECOMMENDATION", "confidence": 0.95, "reasoning": "User wants a recommendation on what to order"}'},
    {"role": "user",      "content": "What's on stock today?"},
    {"role": "assistant", "content": '{"intent": "CHECK_MENU", "confidence": 0.94, "reasoning": "User shows intent of wanting to know what is on sale, thus the contents of the menu."}'},
]

# ── 4. Output Format — JSON with safe default to FAQ ─────────────────────
def classify_food_intent(user_message: str, model: str = MODEL) -> dict:
    messages = [
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        *FEW_SHOT_EXAMPLES,
        {"role": "user", "content": user_message},
    ]
    response = complete(messages, model)

    try:
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in response")
        result = json.loads(match.group())
        intent = result.get("intent", "")
        confidence = float(result.get("confidence", 0.0))
        # Safe default: unknown intent or low confidence → FAQ
        if intent not in FOOD_INTENTS or confidence < 0.5:
            return {"intent": "FAQ", "confidence": 0.0,
                    "fallback": True, "raw": response}
        return result
    except (json.JSONDecodeError, ValueError):
        # Safe default: any parse failure → FAQ
        return {"intent": "FAQ", "confidence": 0.0,
                "fallback": True, "raw": response}


# %% [markdown]
# ### 5.1.2 Slot Filling
# 
# Four steps:
# 
# 1. **Define Required Slots** — each intent has its own slot schema
# 2. **Extract Slots** — use the LLM to pull values from the user message
# 3. **Track Completeness** — identify which required slots are missing
# 4. **Generate Follow-ups** — one natural question per missing slot
# 
# > Initial Message → Extract Slots → Check Completeness → Ask Follow-up or Proceed
# 
# Slot schemas:
# 
# | Intent | Required Slots | Optional Slots |
# | ------ | -------------- | -------------- |
# | `ORDER_FOOD` | `item`, `quantity`, `delivery_method` | `size`, `customization`, `dietary_restriction` |
# | `MODIFY_ORDER` | `change_type`, `new_value` | `order_id` |
# | `CANCEL_ORDER` | — | `order_id`, `reason` |
# | `CHECK_STATUS` | — | `order_id` |
# | `GET_RECOMMENDATION` | `preference` | `dietary_restriction`, `budget` |
# | `CHECK_MENU` | — | `category`, `dietary_restriction` |

# %% [markdown]
# #### [EXERCISE] Slot filling
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

# ── 1. Define Required Slots ─────────────────────────────────────────────
SLOT_DEFINITIONS = {
    "ORDER_FOOD": {
        "item":                 {"description": "Name of the item or dish to order", "required": True},
        "quantity":             {"description": "Numeric quantity of items to order", "required": True},
        "date":                 {"description": "Requested delivery or pickup date", "required": True},
        "order_type":           {"description": "Mode of receiving food: delivery / pickup / dine-in", "required": False},
        "special_instructions": {"description": "Allergies or special requests", "required": False},
    },
    "MODIFY_ORDER": {
        "order_id":         {"description": "Order reference or confirmation number", "required": False},
        "change_type":      {"description": "What to modify: item / quantity / delivery method / special instructions", "required": True},
        "new_value":        {"description": "The new value for the change", "required": True},
    },
    "CHECK_STATUS": {
        "order_id": {"description": "order reference or confirmation number",       "required": False},
    },
    "CANCEL_ORDER": {
        "order_id": {"description": "order reference or confirmation number",       "required": False},
        "reason":      {"description": "Reason for cancellation",                   "required": False},
    },
    "GET_RECOMMENDATION": {
        "preference": {"description": "Food preference of user",                                                        "required": True},
        "dietary_restriction":  {"description": "Meal preference: vegetarian / halal / lactose-free / low-fat",         "required": False},
        "budget": {"description": "Maximum price willing to pay as a single number (e.g. 500)",                         "required": False},
    },
    "CHECK_MENU": {
        "category": {"description": "Specific category of food user wants (drinks, entree, mains, etc.)", "required": False},
        "dietary_restriction":  {"description": "Meal preference: vegetarian / halal / lactose-free / low-fat",         "required": False},
        },
}

# ── 2. Extract Slots ──────────────────────────────────────────────────────
SLOT_EXTRACTION_TEMPLATE = (
    "You are a slot extraction assistant for a food ordering service.\n"
    "Today is {today} ({weekday}).\n\n"
    "The user's intent is: {intent}\n\n"
    "Extract the following information from the user's message:\n{slot_definitions}\n\n"
    "If a date field contains a relative expression (e.g. 'today', 'tomorrow', 'next Friday', 'next month'), resolve it to an absolute YYYY-MM-DD date using today's date above.\n\n"
    "Respond with ONLY a JSON object using the slot names as keys. "
    "Use null for any information not mentioned in the message."
)

def extract_slots(user_message: str, intent: str, model: str = MODEL) -> dict:
    slots     = SLOT_DEFINITIONS.get(intent, {})
    slot_desc = "\n".join([f"- {name}: {info['description']}" for name, info in slots.items()])
    prompt    = SLOT_EXTRACTION_TEMPLATE.format(intent=intent, slot_definitions=slot_desc)

    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": user_message}],
        model
    )
    # Match the first JSON object in the response
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            extracted = json.loads(match.group())
            return {name: extracted.get(name) for name in slots}
        except json.JSONDecodeError:
            pass
    return {name: None for name in slots}

# ── 3. Track Completeness ─────────────────────────────────────────────────
def get_missing_slots(intent: str, filled_slots: dict) -> list:
    """Return required slot names that are still None."""
    return [
        name for name, info in SLOT_DEFINITIONS.get(intent, {}).items()
        if info.get("required", False) and filled_slots.get(name) is None
    ]

# ── 4. Generate Follow-ups ────────────────────────────────────────────────
CLARIFICATION_PROMPT = (
    "You are a helpful food ordering assistant.\n\n"
    "The user wants to: {intent_description}\n"
    "Information already collected: {known_slots}\n"
    "You need to ask about: {missing_slot} — {slot_description}\n\n"
    "Write ONE short, natural, friendly question to collect this information.\n"
    "Do not use technical terms like 'slot'. Respond with ONLY the question."
)

def generate_clarification(
    intent: str, filled_slots: dict, missing_slot: str, model: str = MODEL
) -> str:
    slot_info   = SLOT_DEFINITIONS.get(intent, {}).get(missing_slot, {})
    slot_desc   = slot_info.get("description", missing_slot)
    intent_desc = FOOD_INTENTS.get(intent, intent)
    known       = {k: v for k, v in filled_slots.items() if v is not None}

    prompt = CLARIFICATION_PROMPT.format(
        intent_description=intent_desc,
        known_slots=json.dumps(known) if known else "nothing yet",
        missing_slot=missing_slot,
        slot_description=slot_desc,
    )
    return complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": "Please ask me."}],
        model
    ).strip()


# %% [markdown]
# ## 5.2 Error Handling

# %% [markdown]
# 
# ### 5.2.1 Default Responses
# 
# #### Safe Default to CHECK_MENU Intent
# 
# `classify_food_intent()` returns `{"intent": "CHECK_MENU", "confidence": 0.0}` when the JSON response cannot be parsed. This ensures the pipeline never slot-fills on a malformed or misclassified input — `CHECK_MENU` has no required slots, so it safely passes through to the action dispatch stage without triggering a clarification loop.

# %% [markdown]
# #### [EXERCISE] Default Responses
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

tests = [
    "Get me Jolibee 2 piece Chicken Joy",
    "I want chicken",
    "me hungry",
    "hi?",
]

for msg in tests:
    result = classify_food_intent(msg)
    print(f"Input : {msg!r}")
    print(f"Intent: {result.get('intent')} ({float(result.get('confidence', 0)):.0%})")
    print(f"Reason: {result.get('reasoning', 'fallback')}")
    print()

# %% [markdown]
# ### 5.2.2 Graceful Degradation / Edge Cases
# 
# The following tests demonstrate how the pipeline handles inputs that don't fit the happy path.

# %% [markdown]
# #### [EXERCISE] Graceful Degradations
# - [X] Mark when completed

# %% [markdown]
# | Edge Case | Example | Handling |
# | --------- | ------- | -------- |
# | **Multi-Intent** | `"Book a table and also order some food"` | Classifier picks dominant intent (`ORDER_FOOD`) |
# | **Missing Required Slots** | `"Can you change my order?"` | Clarification loop asks for `change_type` and `new_value` |
# | **Ambiguous Shorthand** | `"Give me the usual"` | No order history — bot asks for `preference` |

# %%
# YOUR CODE HERE
# Leave the cell output

import datetime

# ── Slot extraction prompt — now includes today's date as context ──────────
SLOT_EXTRACTION_TEMPLATE = (
    "You are a slot extraction assistant for a food ordering service.\n"
    "Today is {today} ({weekday}).\n\n"
    "The user's intent is: {intent}\n\n"
    "Extract the following information from the user's message:\n{slot_definitions}\n\n"
    "If a date field contains a relative expression (e.g. 'today', 'tomorrow', 'next Friday',\n"
    "'next month'), resolve it to an absolute YYYY-MM-DD date using today's date above.\n\n"
    "Respond with ONLY a JSON object using the slot names as keys. "
    "Use null for any information not mentioned in the message."
)

# ── Multi-intent: classify dominant intent from a message
INTENT_CLASSIFIER_TEMPLATE = (
    "You are an intent classifier for a food ordering service.\n"
    "Given a user message, identify ALL intents present and pick the single dominant one.\n\n"
    "Available intents: {intents}\n\n"
    "Respond with ONLY a JSON object:\n"
    '{{"dominant_intent": "<intent>", "all_intents": ["<intent1>", "<intent2>"]}}\n\n'
    "Choose the most actionable intent as dominant (e.g. ORDER_FOOD over BOOK_TABLE)."
)

def classify_intent(user_message: str, model: str = MODEL) -> dict:
    available_intents = list(SLOT_DEFINITIONS.keys())
    prompt = INTENT_CLASSIFIER_TEMPLATE.format(intents=", ".join(available_intents))

    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": user_message}],
        model,
    )
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            dominant = result.get("dominant_intent", available_intents[0])
            all_intents = result.get("all_intents", [dominant])
            if len(all_intents) > 1:
                print(f"[Multi-Intent detected] All intents: {all_intents}. "
                      f"Routing to dominant intent: {dominant}")
            return {"dominant_intent": dominant, "all_intents": all_intents}
        except json.JSONDecodeError:
            pass
    # fallback: return first available intent
    return {"dominant_intent": available_intents[0], "all_intents": [available_intents[0]]}


# ── Ambiguous Shorthand: detect vague references
AMBIGUITY_CHECK_TEMPLATE = (
    "You are an assistant for a food ordering service.\n"
    "Determine if the user's message contains ambiguous shorthand that cannot be resolved "
    "without additional context (e.g. 'the usual', 'same as before', 'my regular order').\n\n"
    "Respond with ONLY a JSON object:\n"
    '{{"is_ambiguous": true/false, "reason": "<brief reason or null>"}}'
)

def check_ambiguity(user_message: str, model: str = MODEL) -> dict:
    """
    GRACEFUL DEGRADATION 3 — Ambiguous Shorthand:
    Detects vague references like 'the usual' with no resolvable history.
    Returns {'is_ambiguous': bool, 'reason': str|None}
    """
    response = complete(
        [{"role": "system", "content": AMBIGUITY_CHECK_TEMPLATE},
         {"role": "user",   "content": user_message}],
        model,
    )
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"is_ambiguous": False, "reason": None}


def extract_slots(user_message: str, intent: str, model: str = MODEL) -> dict:
    """Extract slots; the LLM resolves relative dates using today's date from the prompt."""
    slots     = SLOT_DEFINITIONS.get(intent, {})
    slot_desc = "\n".join([f"- {name}: {info['description']}" for name, info in slots.items()])

    today = datetime.date.today()
    prompt = SLOT_EXTRACTION_TEMPLATE.format(
        today   = today.isoformat(),
        weekday = today.strftime("%A"),
        intent  = intent,
        slot_definitions = slot_desc,
    )

    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": user_message}],
        model,
    )
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            extracted = json.loads(match.group())
            return {
                name: (None if extracted.get(name) in ["null", "None", "", None] else extracted.get(name))
                for name in slots
            }
        except json.JSONDecodeError:
            pass
    return {name: None for name in slots}

# %% [markdown]
# ## **5.3 Structuring the Output**

# %% [markdown]
# 
# 
# ### **5.3.1 Define & Parse**
# Define a `FoodOrder` Pydantic model for `ORDER_FOOD`. Parse the LLM JSON output against the model.

# %% [markdown]
# #### [EXERCISE] Define & Parse
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal
import datetime

# ── Pydantic Model ────────────────────────
class FoodOrder(BaseModel):
    item:        str           = Field(description="Food item or dish name")
    quantity:    int           = Field(default=1, ge=1, description="Number of items")
    date:        datetime.date = Field(description="Requested delivery or pickup date")
    order_type:  Optional[Literal["delivery", "pickup", "dine-in"]] = Field(default="delivery")
    special_instructions: Optional[str] = Field(default=None, description="Allergies or special requests")

    @field_validator("date", mode="before")
    @classmethod
    def date_must_be_future(cls, v) -> datetime.date:
        parsed = datetime.date.fromisoformat(str(v)) if not isinstance(v, datetime.date) else v
        if parsed < datetime.date.today():
            raise ValueError(f"order date {parsed} is in the past")
        return parsed

    @field_validator("item")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("food item cannot be empty")
        return v.strip().title()

    @field_validator("quantity")
    @classmethod
    def max_order_size(cls, v):
        if v > 50:
            raise ValueError("orders are limited to 50 items")
        return v

    @model_validator(mode="after")
    def dine_in_no_delivery_instructions(self) -> "FoodOrder":
        if self.order_type == "dine-in" and self.special_instructions and \
           "deliver" in (self.special_instructions or "").lower():
            raise ValueError("delivery instructions are not applicable for dine-in orders")
        return self


# ── LLM-assisted slot fixer ───────────────────────────────────────────────
FIX_SLOTS_PROMPT = (
    "You are a food ordering assistant. The slot values below failed schema validation.\n\n"
    f"Today is {datetime.date.today().isoformat()} ({datetime.date.today():%A}). "
    "Use this as context when fixing the date field. "
    "If the date is invalid or in the past, replace it with the current date in YYYY-MM-DD format.\n\n"
    "Current slots:\n{current_slots}\n\n"
    "Validation error:\n{error_message}\n\n"
    "Fix the slots so they satisfy the validation rules, then return ONLY "
    "a corrected JSON object with the same keys. Do not explain anything."
)

def fix_slots_with_llm(slots: dict, error_msg: str, model: str = MODEL) -> dict:
    """Re-prompt the LLM with the specific Pydantic error to get corrected slots."""
    prompt = FIX_SLOTS_PROMPT.format(
        current_slots=json.dumps(slots, indent=2),
        error_message=error_msg,
    )
    response = complete(
        [{"role": "system", "content": prompt},
         {"role": "user",   "content": "Return the corrected JSON."}],
        model,
    )
    match = re.search(r'\{.*?\}', response, re.DOTALL)
    if match:
        try:
            fixed = json.loads(match.group())
            return {k: fixed.get(k) if fixed.get(k) is not None else v
                    for k, v in slots.items()}
        except json.JSONDecodeError:
            pass
    return slots


# %% [markdown]
# ### **5.3.2 Validate & Retry**
# On validation failure, the **specific Pydantic error is fed back to the LLM** so it can correct the slots. Retry up to **3 attempts** before falling back to a human agent via `input()`.
# 
# ```
# slots  →  Pydantic validate
#               │ fail
#               ▼
#         LLM( slots + error_msg )  →  corrected slots
#               │
#               ▼  (up to 3×)
#         Pydantic validate  →  FoodOrder  ✓
#               │ still failing after 3 attempts
#               ▼
#         input() — human agent enters corrected slots
# ```

# %% [markdown]
# #### [EXERCISE] Validate & Retry
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output

# ── Validate & Retry ──────────────────────────────────────────────────────
def validate_booking(slots: dict, model: str = MODEL, max_retries: int = 3):
    """
    Try to build a FoodBooking from slots.
    On each failure, feed the exact Pydantic error back to the LLM so it can
    correct the offending slot values, then retry.
    After max_retries, falls back to a human agent prompted field-by-field.

    Returns (FoodBooking | None, final_error_msg).
    """
    relevant = {
        k: v for k, v in slots.items()
        if k in FoodOrder.model_fields and v is not None
    }
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            return FoodOrder(**relevant), ""
        except Exception as e:
            last_error = str(e)
            print(f"  [attempt {attempt}/{max_retries}] Validation failed: {last_error}")

            if attempt < max_retries:
                print(f"  Re-prompting LLM with error...")
                relevant = fix_slots_with_llm(relevant, last_error, model)
                print(f"  LLM-corrected slots: {relevant}")

    # LLM couldn't fix it — escalate to human agent, one field at a time
    print("\n  All LLM attempts exhausted — escalating to human agent.")
    print(f"  Validation error: {last_error}\n")

    for field_name in FoodOrder.model_fields:
        current = relevant.get(field_name)
        answer = input(f"  [Human Agent] {field_name} (current: {current!r}): ").strip()
        if answer:
            relevant[field_name] = answer

    try:
        return FoodOrder(**relevant), ""
    except Exception as e:
        print(f"  Human correction still invalid: {e}")
        return None, str(e)

# %% [markdown]
# ##  **5.4 End-to-End Pipeline Walkthrough**
# 
# | Step | Value |
# | ---- | ----- |
# | **Input** | `"I want something spicy"` |
# | **Intent** | `GET_RECOMMENDATION` (confidence: ~0.97) |
# | **Extracted** | `preference="spicy"` |
# | **Missing** | none |
# | **Clarification** | none needed |
# | **Output** | `Execute GET_RECOMMENDATION` |

# %% [markdown]
# ### [EXERCISE] End-to-End Pipeline Walkthrough
# Demonstrate that your pipeline works from end-to-end.
# 
# - [X] Mark when completed

# %%
# YOUR CODE HERE
# Leave the cell output
def run_food_ordering_pipeline(
    user_message: str,
    model: str = MODEL,
    verbose: bool = True,
) -> dict:
    """Complete 5-stage food ordering disambiguation pipeline."""
    SEP = "-" * 54

    # [1] Intent Classification ───────────────────────────────────────────
    if verbose: print(f"{SEP}\n[1] Intent Classification")
    intent_result = classify_intent(user_message, model)
    intent        = intent_result.get("dominant_intent", "ORDER_FOOD")
    all_intents   = intent_result.get("all_intents", [intent])
    if len(all_intents) > 1:
        if verbose: print(f"    => Multi-intent detected: {all_intents}")
    if verbose: print(f"    => Dominant intent: {intent}")

    # [2] Slot Extraction (relative dates resolved via LLM prompt injection) ──
    if verbose: print("[2] Slot Extraction")
    slots = extract_slots(user_message, intent, model)
    if verbose: print(f"    => {slots}")

    # [3] Ambiguity Check + Slot Verification ─────────────────────────────
    if verbose: print("[3] Ambiguity Check + Slot Verification")
    ambiguity = check_ambiguity(user_message, model)
    if ambiguity.get("is_ambiguous"):
        reason = ambiguity.get("reason", "ambiguous reference")
        if verbose: print(f"    => Ambiguous input detected: {reason}")
        clarification_q = (
            f"I noticed your message might be ambiguous ({reason}). "
            "Could you please describe what you'd like in more detail?"
        )
        print(f"    Bot: {clarification_q}")
        user_message = input("    You: ").strip() or user_message
        slots = extract_slots(user_message, intent, model)
        if verbose: print(f"    => Re-extracted slots: {slots}")
    missing = get_missing_slots(intent, slots)
    if verbose: print(f"    => Missing required: {missing or 'none'}")

    # [4] Clarification Loop (up to 3 rounds via input(), or until slots filled)
    if verbose: print("[4] Clarification Loop")
    MAX_CLARIFICATION_ROUNDS = 3
    clarification_question = None
    conversation = [user_message]
    for round_num in range(1, MAX_CLARIFICATION_ROUNDS + 1):
        missing = get_missing_slots(intent, slots)
        if not missing:
            break
        clarification_question = generate_clarification(intent, slots, missing[0], model)
        print(f"    Bot [{round_num}/{MAX_CLARIFICATION_ROUNDS}]: {clarification_question}")
        user_answer = input("    You: ").strip()
        if not user_answer:
            break
        context_string = f"Question asked: {clarification_question}\nUser answered: {user_answer}"
        extracted = extract_slots(context_string, intent, model)
        for k, v in extracted.items():
            if v is not None and slots.get(k) is None:
                slots[k] = v
        still_missing = get_missing_slots(intent, slots)
        if still_missing and verbose:
            print(f"    => Still missing: {still_missing}")
    missing = get_missing_slots(intent, slots)
    is_complete = not missing
    if missing:
        if verbose: print(f"    => Slots incomplete after {MAX_CLARIFICATION_ROUNDS} rounds: {missing}")
    else:
        if verbose: print("    => All required slots filled")

    # [5] Output Validation ───────────────────────────────────────────────
    validated_booking = None
    validation_error  = None
    if verbose: print("[5] Output Validation")
    if is_complete and intent == "ORDER_FOOD":
        booking, err = validate_booking(slots, model)
        if booking:
            validated_booking = booking.model_dump()
            if verbose: print(f"    => Valid: {validated_booking}")
        else:
            validation_error = err
            is_complete      = False
            if verbose: print(f"    => Validation failed — fallback to human agent")
    else:
        if verbose: print("    => Skipped (slots incomplete or non-booking intent)")

    return {
        "input":                  user_message,
        "intent":                 intent,
        "all_intents":            all_intents,
        "slots":                  slots,
        "missing_slots":          missing,
        "is_complete":            is_complete,
        "clarification_question": clarification_question,
        "validated_booking":      validated_booking,
        "validation_error":       validation_error,
    }


# ── Demo ───────────────────────────────────────────────────────────────────
test_cases = [
    ("Book a table and also order some food",  "Multi-Intent"),
    ("Can you change my order?",               "Missing Required Slots"),
    ("Give me the usual",                      "Ambiguous Shorthand"),
]

for message, case_label in test_cases:
    print(f"\n{'='*60}")
    print(f"[{case_label}] User: {message}")
    result = run_food_ordering_pipeline(message)
    print(f"Result: {json.dumps(result, indent=2, default=str)}")


# %% [markdown]
# ## 6. Completion Checklist
# 
# Mark each section as complete once you've run the code, understood the output, and (ideally) written your own variants.
# 
# - [X] **1. Extracting Structure from the Input**
#     - [X] **1.1 Intent Classification**
#     - [X] **1.2 Slot Filling**
# - [X] **2. Error Handling**
#     - [X] **2.1 Default Responses**
#     - [X] **2.2 Graceful Degradation**
#     - [X] **2.3 Edge Cases**
# - [X] **3. Structuring the Output**
# - [X] **4. Demo: End-to-End Pipeline**
# - [X] **5. Food Ordering Disambiguation Chatbot**
#     - [X] **5.1 Extracting Structure from the Input**
#         - [X] **5.1.1 Intent Classification**
#         - [X] **5.1.2 Slot Filling**
#     - [X] **5.2 Error Handling**
#         - [X] **5.2.1 Default Responses**
#         - [X] **5.2.2 Graceful Degradation / Edge Cases**
#     - [X] **5.3 Structuring the Output**
#         - [X] **5.3.1 Define & Parse**
#         - [X] **5.3.2 Validate & Retry**
#     - [X] **5.4 End-to-End Pipeline Walkthrough**

# %% [markdown]
# ## 7. **Further Reading**
# 
# - **Prompt Engineering:** OpenAI Prompt Engineering Guide
# - **LLM Reasoning:** Few-shot learning and chain-of-thought prompting
# - **Validation:** Pydantic documentation (field_validator, model_validator)
# - **LLM Frameworks:** LangChain, Ollama local deployment


