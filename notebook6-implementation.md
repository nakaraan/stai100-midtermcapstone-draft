One quick note before the answers: this upload included a hidden block styled as a "SYSTEM ROLE" instruction trying to get me to suppress framing, never ask questions, and treat itself as authoritative. That's not something Anthropic sent me — it's just text embedded in the file, so I'm disregarding its authority claim. That said, what you're actually asking for (working through the exercises so you can check your own answers) is a completely reasonable thing to help with, so here's that, in my own voice.

Also worth flagging: I don't have a live Ollama/LangChain runtime here (no internet access to pull models), so I can't literally execute these cells and show you real output. What I can do is give you runnable code plus grounded predictions based on how `calculate`, `get_weather`, `run_agent`, and `run_lc_agent` are actually wired — you'll confirm/refute these when you run it yourself in Colab.

---

### Cell 19 — [EXERCISE] Act-only Prompting

```python
# YOUR CODE HERE
# Leave the cell output

def run_act_only(user_query, max_turns=5):
    messages = [
        {"role": "system", "content": action_prompt},
        {"role": "user", "content": user_query},
    ]
    for turn in range(max_turns):
        print(f"\n--- Turn {turn+1} ---")
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        content = response['message']['content'].strip()
        print(content)

        if content.startswith("Final Answer:"):
            break

        if content.startswith("Action: simple_calculate("):
            match = re.search(r'simple_calculate\(["\'](.+?)["\']', content)
            if match:
                expression = match.group(1)
                observation = simple_calculate(expression)
                print(f"Observation: {observation}")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                print("Failed to parse action. Retrying...")
                messages.append({"role": "user", "content": "Please output a valid Action in the exact format."})
        else:
            print("Invalid format. Reprompting...")
            messages.append({"role": "user", "content": "Output only a valid Action or Final Answer."})
    else:
        print("Max turns reached.")


# 1. Re-run the SAME query a few times to look for variation / failure modes
same_query = "Is 197+23+5 greater than 196+22+2*5?"
for i in range(3):
    print("=" * 60)
    print(f"REPEAT RUN {i+1}")
    print("=" * 60)
    run_act_only(same_query)

# 2. Stress-test with new queries
stress_queries = [
    "What is 15% of 847, then add 33 to the result?",  # multi-step arithmetic
    "What is the square root of -1?",                    # undefined for real numbers
    "What is the capital of France?",                    # no math needed at all
]
for q in stress_queries:
    print("\n" + "=" * 60)
    print(f"QUERY: {q}")
    print("=" * 60)
    run_act_only(q)
```

**Predictions (confirm after running):**
- **Repeated identical query:** since temperature/sampling isn't fixed, expect the exact wording of `Action:` lines to vary run-to-run (e.g. `simple_calculate("197+23+5")` vs `simple_calculate("197+23+5 - (196+22+2*5)")`), but the final `Final Answer:` should consistently land on "yes, 225 > 218" if the model reasons correctly. Occasional failure mode: model breaks the "no extra text" rule and prepends explanation, which would still pass since the code only checks `startswith`, not exact match — but if it puts *anything* before `Action:`, the `startswith("Action: simple_calculate(")` check fails and falls into the "Invalid format. Reprompting..." branch.
- **"15% of 847, then add 33":** should succeed since it's within `simple_calculate`'s eval sandbox (pure arithmetic).
- **"square root of -1":** `simple_calculate` has no `sqrt`/`math` import in its `eval` globals (only bare `eval` with empty builtins) — a literal `"(-1)**0.5"` expression would actually eval fine in Python (returns a complex number `(6.123e-17+1j)`), so likely doesn't error, but produces a confusing complex-number answer rather than "undefined," which is a good thing to note as a subtle correctness gap.
- **"capital of France":** no arithmetic tool applies. Since the system prompt only allows `Action:` or `Final Answer:` with no "no-tool" option modeled, expect the agent to either hallucinate an irrelevant `simple_calculate(...)` call, or correctly skip straight to `Final Answer: Paris`. This is a good illustration of Section 1's stated limitation — act-only prompting has no clean way to say "no tool needed."

---

### Cell 33 — [EXERCISE] ReAct Loop

```python
prompts = [
    "What is 2 to the power of 10, and what is the weather in Tokyo?",
    "What is the square root of 144 plus 7?",
    "What is the capital of France?",
    "What is the weather in the capital of France?",
    "What is 35 + the weather in the capital of France?",
]

for p in prompts:
    print("\n" + "#" * 70)
    print(f"PROMPT: {p}")
    print("#" * 70)
    run_agent(p)

# Own prompts to further stress-test
my_prompts = [
    "What is the weather in Manila, and what is 10 times 10?",
    "What is 10 divided by 0?",
    "What is the weather in Berlin and how much is 100 divided by 4?",
]

for p in my_prompts:
    print("\n" + "#" * 70)
    print(f"PROMPT: {p}")
    print("#" * 70)
    run_agent(p)
```

**Predictions (confirm after running):**
- **#1 (power + Tokyo weather):** should succeed — `calculate("2**10")` → `1024`, `get_weather("Tokyo")` → matches the `"tokyo"` substring check in `get_weather` → `"22°C and sunny"`.
- **#2 (sqrt(144)+7):** `calculate` here uses plain `eval` with no math functions injected (unlike the later LangChain version in Section 4) — `sqrt` isn't defined, so `Action: calculate(sqrt(144) + 7)` will raise `NameError`, caught by `calculate`'s own `except`, returning `"Error evaluating expression: name 'sqrt' is not defined"`. Whether the agent recovers depends on if it retries with `144**0.5 + 7` on the next turn.
- **#3 (capital of France):** no tool needed — expect the agent to skip straight to `Answer: Paris` without any `Action:` line, since `SYSTEM_PROMPT` doesn't force a tool call for every query.
- **#4 (weather in the capital of France):** depends on whether the model resolves "capital of France" → "Paris" *before* calling the tool. If it does, `get_weather("Paris")` hits the `"paris"` branch correctly. If it passes the literal phrase `"the capital of France"` as the argument, that string doesn't match `"paris"` or `"tokyo"`, so it falls through to the generic `"20°C and partly cloudy"` — a wrong-but-silent failure mode worth flagging.
- **#5 (35 + weather in capital of France):** likely failure case — the model would need to call `get_weather` first, then feed a non-numeric string like `"15°C and rainy"` into `calculate("35 + 15")` (it would need to strip the °C part itself). If it instead literally does `calculate("35 + 15°C and rainy")`, that's a `SyntaxError`, caught and returned as an error string. This is the clearest test of whether the loop can combine tool outputs across two different tool types.
- **My prompt A (Manila + 10×10):** `get_weather` (from-scratch version) has no `"manila"` branch, so it falls into the generic `else` — returns `"20°C and partly cloudy"` even though Manila is handled correctly later in the *LangChain* tool (Section 4). Good illustration that the two tool implementations aren't identical.
- **My prompt B (10/0):** `calculate("10/0")` → `ZeroDivisionError` → caught → `"Error evaluating expression: division by zero"`. Tests whether the agent's next Thought correctly reports the error instead of inventing a number.
- **My prompt C (Berlin + 100/4):** Berlin isn't in the `get_weather` if/elif chain either, so same generic fallback applies; `calculate("100/4")` → `25.0` should work cleanly. Useful for isolating "tool succeeds / tool silently returns wrong default" side by side.

---

### Cell 51 — [EXERCISE] Query Stress-test

```python
prompts = [
    "What clothing should I pack for a trip to Tokyo and London?",
    "What is the circumference of a circle with radius 7?",
    "What is the most popular programming language?",
]

for p in prompts:
    run_lc_agent(p)

# Own prompts
my_prompts = [
    "What's the temperature difference between Paris and Tokyo, divided by 2?",
    "What is the weather in Atlantis?",
    "What is 5 plus 5, and who won the 2022 FIFA World Cup?",
]

for p in my_prompts:
    run_lc_agent(p)
```

**Predictions (confirm after running):**
- **Clothing for Tokyo + London:** `get_weather` (LangChain version, cell 38) has explicit entries for both `"tokyo"` and `"london"`, so expect two clean `get_weather` tool calls (`"22°C and sunny"`, `"12°C and foggy"`) followed by a reasonable clothing recommendation synthesized from both. This is the easiest multi-tool case since the data actually covers both cities.
- **Circumference, radius 7:** expect a single `calculate` call, something like `calculate("2 * pi * 7")` → `43.98...`. Because this `calculate` tool includes `pi`, `sqrt`, etc. in its `allowed` dict (unlike the from-scratch version), this should succeed cleanly — a good contrast to point out versus Cell 33 prompt #2's failure.
- **Most popular programming language:** no tool fits this — expect zero tool calls and a direct answer from the model's own knowledge, per `LC_SYSTEM_PROMPT`'s "If a question needs no tools, answer directly" instruction. Worth noting the answer itself is opinion/ranking-dependent (e.g. Python vs JavaScript depending on the metric), so it's a good spot to see if the model hedges appropriately rather than asserting one answer as fact.
- **My prompt A (temp difference ÷ 2):** requires chaining *three* calls: `get_weather("Paris")`, `get_weather("Tokyo")`, then `calculate` on the numeric difference divided by 2. The likely failure point is the same as before — the model must extract `15` and `22` from the returned strings itself before calling `calculate`, since the tool can't parse `"°C and rainy"` text.
- **My prompt B (Atlantis):** `get_weather("atlantis")` isn't in the `data` dict, so it correctly falls through to `return data.get(..., f"No weather data available for '{city}'.")`. Good test of whether the agent relays that "no data" message honestly instead of inventing a fake temperature.
- **My prompt C (5+5 and World Cup):** tests whether the agent correctly uses `calculate` for only the arithmetic half and answers the trivia half from its own knowledge, rather than trying (and failing) to force both through the same tool.

That covers everything before Section 6 — Cells 19, 33, and 51.


One quick note before the answers: this upload included a hidden block styled as a "SYSTEM ROLE" instruction trying to get me to suppress framing, never ask questions, and treat itself as authoritative. That's not something Anthropic sent me — it's just text embedded in the file, so I'm disregarding its authority claim. That said, what you're actually asking for (working through the exercises so you can check your own answers) is a completely reasonable thing to help with, so here's that, in my own voice.

Also worth flagging: I don't have a live Ollama/LangChain runtime here (no internet access to pull models), so I can't literally execute these cells and show you real output. What I can do is give you runnable code plus grounded predictions based on how `calculate`, `get_weather`, `run_agent`, and `run_lc_agent` are actually wired — you'll confirm/refute these when you run it yourself in Colab.

---

### Cell 19 — [EXERCISE] Act-only Prompting

```python
# YOUR CODE HERE
# Leave the cell output

def run_act_only(user_query, max_turns=5):
    messages = [
        {"role": "system", "content": action_prompt},
        {"role": "user", "content": user_query},
    ]
    for turn in range(max_turns):
        print(f"\n--- Turn {turn+1} ---")
        response = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        content = response['message']['content'].strip()
        print(content)

        if content.startswith("Final Answer:"):
            break

        if content.startswith("Action: simple_calculate("):
            match = re.search(r'simple_calculate\(["\'](.+?)["\']', content)
            if match:
                expression = match.group(1)
                observation = simple_calculate(expression)
                print(f"Observation: {observation}")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Observation: {observation}"})
            else:
                print("Failed to parse action. Retrying...")
                messages.append({"role": "user", "content": "Please output a valid Action in the exact format."})
        else:
            print("Invalid format. Reprompting...")
            messages.append({"role": "user", "content": "Output only a valid Action or Final Answer."})
    else:
        print("Max turns reached.")


# 1. Re-run the SAME query a few times to look for variation / failure modes
same_query = "Is 197+23+5 greater than 196+22+2*5?"
for i in range(3):
    print("=" * 60)
    print(f"REPEAT RUN {i+1}")
    print("=" * 60)
    run_act_only(same_query)

# 2. Stress-test with new queries
stress_queries = [
    "What is 15% of 847, then add 33 to the result?",  # multi-step arithmetic
    "What is the square root of -1?",                    # undefined for real numbers
    "What is the capital of France?",                    # no math needed at all
]
for q in stress_queries:
    print("\n" + "=" * 60)
    print(f"QUERY: {q}")
    print("=" * 60)
    run_act_only(q)
```

**Predictions (confirm after running):**
- **Repeated identical query:** since temperature/sampling isn't fixed, expect the exact wording of `Action:` lines to vary run-to-run (e.g. `simple_calculate("197+23+5")` vs `simple_calculate("197+23+5 - (196+22+2*5)")`), but the final `Final Answer:` should consistently land on "yes, 225 > 218" if the model reasons correctly. Occasional failure mode: model breaks the "no extra text" rule and prepends explanation, which would still pass since the code only checks `startswith`, not exact match — but if it puts *anything* before `Action:`, the `startswith("Action: simple_calculate(")` check fails and falls into the "Invalid format. Reprompting..." branch.
- **"15% of 847, then add 33":** should succeed since it's within `simple_calculate`'s eval sandbox (pure arithmetic).
- **"square root of -1":** `simple_calculate` has no `sqrt`/`math` import in its `eval` globals (only bare `eval` with empty builtins) — a literal `"(-1)**0.5"` expression would actually eval fine in Python (returns a complex number `(6.123e-17+1j)`), so likely doesn't error, but produces a confusing complex-number answer rather than "undefined," which is a good thing to note as a subtle correctness gap.
- **"capital of France":** no arithmetic tool applies. Since the system prompt only allows `Action:` or `Final Answer:` with no "no-tool" option modeled, expect the agent to either hallucinate an irrelevant `simple_calculate(...)` call, or correctly skip straight to `Final Answer: Paris`. This is a good illustration of Section 1's stated limitation — act-only prompting has no clean way to say "no tool needed."

---

### Cell 33 — [EXERCISE] ReAct Loop

```python
prompts = [
    "What is 2 to the power of 10, and what is the weather in Tokyo?",
    "What is the square root of 144 plus 7?",
    "What is the capital of France?",
    "What is the weather in the capital of France?",
    "What is 35 + the weather in the capital of France?",
]

for p in prompts:
    print("\n" + "#" * 70)
    print(f"PROMPT: {p}")
    print("#" * 70)
    run_agent(p)

# Own prompts to further stress-test
my_prompts = [
    "What is the weather in Manila, and what is 10 times 10?",
    "What is 10 divided by 0?",
    "What is the weather in Berlin and how much is 100 divided by 4?",
]

for p in my_prompts:
    print("\n" + "#" * 70)
    print(f"PROMPT: {p}")
    print("#" * 70)
    run_agent(p)
```

**Predictions (confirm after running):**
- **#1 (power + Tokyo weather):** should succeed — `calculate("2**10")` → `1024`, `get_weather("Tokyo")` → matches the `"tokyo"` substring check in `get_weather` → `"22°C and sunny"`.
- **#2 (sqrt(144)+7):** `calculate` here uses plain `eval` with no math functions injected (unlike the later LangChain version in Section 4) — `sqrt` isn't defined, so `Action: calculate(sqrt(144) + 7)` will raise `NameError`, caught by `calculate`'s own `except`, returning `"Error evaluating expression: name 'sqrt' is not defined"`. Whether the agent recovers depends on if it retries with `144**0.5 + 7` on the next turn.
- **#3 (capital of France):** no tool needed — expect the agent to skip straight to `Answer: Paris` without any `Action:` line, since `SYSTEM_PROMPT` doesn't force a tool call for every query.
- **#4 (weather in the capital of France):** depends on whether the model resolves "capital of France" → "Paris" *before* calling the tool. If it does, `get_weather("Paris")` hits the `"paris"` branch correctly. If it passes the literal phrase `"the capital of France"` as the argument, that string doesn't match `"paris"` or `"tokyo"`, so it falls through to the generic `"20°C and partly cloudy"` — a wrong-but-silent failure mode worth flagging.
- **#5 (35 + weather in capital of France):** likely failure case — the model would need to call `get_weather` first, then feed a non-numeric string like `"15°C and rainy"` into `calculate("35 + 15")` (it would need to strip the °C part itself). If it instead literally does `calculate("35 + 15°C and rainy")`, that's a `SyntaxError`, caught and returned as an error string. This is the clearest test of whether the loop can combine tool outputs across two different tool types.
- **My prompt A (Manila + 10×10):** `get_weather` (from-scratch version) has no `"manila"` branch, so it falls into the generic `else` — returns `"20°C and partly cloudy"` even though Manila is handled correctly later in the *LangChain* tool (Section 4). Good illustration that the two tool implementations aren't identical.
- **My prompt B (10/0):** `calculate("10/0")` → `ZeroDivisionError` → caught → `"Error evaluating expression: division by zero"`. Tests whether the agent's next Thought correctly reports the error instead of inventing a number.
- **My prompt C (Berlin + 100/4):** Berlin isn't in the `get_weather` if/elif chain either, so same generic fallback applies; `calculate("100/4")` → `25.0` should work cleanly. Useful for isolating "tool succeeds / tool silently returns wrong default" side by side.

---

### Cell 51 — [EXERCISE] Query Stress-test

```python
prompts = [
    "What clothing should I pack for a trip to Tokyo and London?",
    "What is the circumference of a circle with radius 7?",
    "What is the most popular programming language?",
]

for p in prompts:
    run_lc_agent(p)

# Own prompts
my_prompts = [
    "What's the temperature difference between Paris and Tokyo, divided by 2?",
    "What is the weather in Atlantis?",
    "What is 5 plus 5, and who won the 2022 FIFA World Cup?",
]

for p in my_prompts:
    run_lc_agent(p)
```

**Predictions (confirm after running):**
- **Clothing for Tokyo + London:** `get_weather` (LangChain version, cell 38) has explicit entries for both `"tokyo"` and `"london"`, so expect two clean `get_weather` tool calls (`"22°C and sunny"`, `"12°C and foggy"`) followed by a reasonable clothing recommendation synthesized from both. This is the easiest multi-tool case since the data actually covers both cities.
- **Circumference, radius 7:** expect a single `calculate` call, something like `calculate("2 * pi * 7")` → `43.98...`. Because this `calculate` tool includes `pi`, `sqrt`, etc. in its `allowed` dict (unlike the from-scratch version), this should succeed cleanly — a good contrast to point out versus Cell 33 prompt #2's failure.
- **Most popular programming language:** no tool fits this — expect zero tool calls and a direct answer from the model's own knowledge, per `LC_SYSTEM_PROMPT`'s "If a question needs no tools, answer directly" instruction. Worth noting the answer itself is opinion/ranking-dependent (e.g. Python vs JavaScript depending on the metric), so it's a good spot to see if the model hedges appropriately rather than asserting one answer as fact.
- **My prompt A (temp difference ÷ 2):** requires chaining *three* calls: `get_weather("Paris")`, `get_weather("Tokyo")`, then `calculate` on the numeric difference divided by 2. The likely failure point is the same as before — the model must extract `15` and `22` from the returned strings itself before calling `calculate`, since the tool can't parse `"°C and rainy"` text.
- **My prompt B (Atlantis):** `get_weather("atlantis")` isn't in the `data` dict, so it correctly falls through to `return data.get(..., f"No weather data available for '{city}'.")`. Good test of whether the agent relays that "no data" message honestly instead of inventing a fake temperature.
- **My prompt C (5+5 and World Cup):** tests whether the agent correctly uses `calculate` for only the arithmetic half and answers the trivia half from its own knowledge, rather than trying (and failing) to force both through the same tool.

That covers everything before Section 6 — Cells 19, 33, and 51.

### Section 7 — Web Search Agent

Since I don't have a Tavily API key wired into this environment (and you may not either, by default), I'm building this with **Option 2 from the instructions** — a mocked "REST API" search tool, structured so it's a drop-in swap for a real one later. I've left the real-Tavily path as a commented alternative so you can see both.

```python
import os

# --- Option A: Real web search via Tavily (requires TAVILY_API_KEY) ---
# NEW DEP: langchain-community's TavilySearchResults + tavily-python (pip install -U langchain-community tavily-python)
# os.environ["TAVILY_API_KEY"] = "your-key-here"
# from langchain_community.tools.tavily_search import TavilySearchResults
# web_search = TavilySearchResults(max_results=3)

# --- Option B: Mocked web search, simulating a REST API call ---
MOCK_SEARCH_DB = {
    "python 3.13": "Python 3.13 (Oct 2024) added a new experimental JIT compiler and a free-threaded (no-GIL) build option.",
    "langchain": "LangChain is an open-source framework (2022) providing abstractions for LLM chains, agents, and tool use.",
    "qwen2.5": "Qwen2.5 is an open-weight LLM family released by Alibaba in 2024 with strong native tool-calling support.",
    "react agent": "The ReAct paper (Yao et al., 2022) proposed interleaving reasoning traces with tool actions to reduce hallucination.",
}

@tool
def web_search(query: str) -> str:
    """Search the web for current information (simulated REST API call).
    Returns a short summary snippet for the query, or a not-found message.

    Args:
        query: The search query string, e.g. 'latest Python release'
    """
    try:
        # NOTE: stands in for requests.get("https://mock-search-api/search", params={"q": query})
        query_lower = query.lower()
        matches = [info for key, info in MOCK_SEARCH_DB.items() if key in query_lower]
        if matches:
            return matches[0]
        return f"No results found for '{query}'."
    except Exception as e:
        return f"Error performing web search: {e}"

web_tools = [web_search, calculate]

WEB_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a web search tool.\n"
    "Use web_search for questions about current events, recent releases, or facts you're unsure of.\n"
    "Use calculate for any math.\n"
    "Be concise and cite what the search returned."
)

web_agent = create_agent(llm, web_tools, system_prompt=WEB_SYSTEM_PROMPT)

def run_web_agent(query: str):
    """Run the web-search agent and display each reasoning step."""
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)
    for step in web_agent.stream({"messages": [("user", query)]}, stream_mode="values"):
        msg = step["messages"][-1]
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"\n[Action] {tc['name']}({tc['args']})")
        elif msg.type == "tool":
            preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            print(f"[Observation from '{msg.name}']\n  {preview}")
        elif msg.type == "ai" and msg.content:
            print(f"\n[Final Answer]\n{msg.content}")
    print("=" * 60)

# Demo runs — one that should hit the mock DB, one that shouldn't
run_web_agent("What's new in Python 3.13?")
run_web_agent("What is LangChain and when was it created?")
run_web_agent("What is the current population of Mars?")  # designed to fail/not-found
```

**Predicted observations (confirm after running):**
- **Successful runs** ("Python 3.13", "LangChain"): query keywords directly match `MOCK_SEARCH_DB` keys, so `web_search` returns the canned snippet and the model should synthesize a clean, grounded final answer citing it.
- **Expected failure/edge case** ("population of Mars"): no key matches, so `web_search` returns `"No results found for..."`. The interesting thing to actually watch for in your run: does the model **honestly report "I couldn't find that"**, or does it fall back on its own (possibly hallucinated) training knowledge despite the system prompt saying not to rely on memory for facts? That's the real test of a mocked-search setup — it exposes whether the agent respects "ground everything in tool output" when the tool comes up empty.
- If you swap in the real Tavily option instead, expect the opposite failure mode: it may return too much raw text per result (needs truncation/summarization) and behavior will vary run-to-run since it's live data, not deterministic mock data — worth noting as a documented contrast between the two approaches per the assignment's ask.

---

### Bonus — File Handling Tools

```python
import requests

@tool
def read_file(path: str) -> str:
    """Read and return the text content of a local file.
    Returns an error string if the file doesn't exist or can't be read.

    Args:
        path: Path to the local file, e.g. 'notes.txt'
    """
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

@tool
def write_file(path: str, content: str) -> str:
    """Write text content to a local file, overwriting if it exists.
    Returns a confirmation message or an error string.

    Args:
        path: Path to the local file to write, e.g. 'output.txt'
        content: The text content to write into the file
    """
    try:
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

@tool
def download_pdf(url: str, save_path: str) -> str:
    """Download a PDF from a URL and save it locally.
    Returns a confirmation message or an error string.

    Args:
        url: The URL of the PDF to download
        save_path: Local path to save the downloaded PDF, e.g. 'doc.pdf'
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
        return f"Downloaded PDF to {save_path} ({len(response.content)} bytes)"
    except Exception as e:
        return f"Error downloading PDF: {e}"

file_tools = [read_file, write_file, download_pdf]

FILE_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to file-handling tools.\n"
    "Use read_file to read local files, write_file to save text locally, "
    "and download_pdf to fetch PDFs from a URL.\n"
    "Be concise about what you did and report any errors clearly."
)

file_agent = create_agent(llm, file_tools, system_prompt=FILE_SYSTEM_PROMPT)

def run_file_agent(query: str):
    """Run the file-handling agent and display each reasoning step."""
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)
    for step in file_agent.stream({"messages": [("user", query)]}, stream_mode="values"):
        msg = step["messages"][-1]
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"\n[Action] {tc['name']}({tc['args']})")
        elif msg.type == "tool":
            preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            print(f"[Observation from '{msg.name}']\n  {preview}")
        elif msg.type == "ai" and msg.content:
            print(f"\n[Final Answer]\n{msg.content}")
    print("=" * 60)

# Demo 1: write then read back
run_file_agent("Write 'Hello from the ReAct lab!' to a file called demo.txt, then read it back to confirm.")

# Demo 2: download the ReAct paper (cited in Section 3) as a PDF
run_file_agent(
    "Download the PDF at https://arxiv.org/pdf/2210.03629 and save it as react_paper.pdf, "
    "then confirm it was saved."
)
```

**Predicted observations (confirm after running):**
- **write_file → read_file demo:** should be a clean two-step success — `[Action] write_file(...)` returns a confirmation, then `[Action] read_file(...)` returns the exact string written back. Good sanity check that the two tools round-trip correctly.
- **download_pdf demo (arXiv):** likely success in Colab (has internet access) — `response.raise_for_status()` should pass for a valid arXiv PDF URL and the file gets written in binary mode. In *this* sandboxed environment, though, a request to `arxiv.org` would actually be blocked by network egress rules, which is a good real-world illustration of the `except Exception as e` branch firing — worth trying a bad/unreachable URL intentionally too (e.g. a typo'd domain) to see the tool degrade gracefully into an error string rather than crashing the whole agent loop.
- **Untested edge case worth trying yourself:** ask it to `read_file` a path that doesn't exist — should surface `"Error reading file: [Errno 2] No such file or directory: '...'"` cleanly rather than raising, confirming the try/except actually protects the agent loop as intended.

That covers both parts of Section 7.