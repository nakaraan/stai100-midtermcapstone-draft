Updated todo list

I'm locating the RAG control path first, then I’ll trace storage, retrieval, prompts, and the app entry points directly from the code so the summary stays grounded in the implementation.

Searched for files matching `STAI-WEEK5-NEW` · `**/*.py`, 4 matches

Searched for regex `chroma|Chroma|vector|embed|embedding|retrieve|retrieval|prompt|system prompt|MLflow|mlflow|rag|RAG|similarity_search|similarity` (`**/*.py`), 57 results

Read [](file:///c%3A/Users/ADMIN/STAI-WEEK5-NEW/README.md)

I found the main RAG implementation in core.py and a traced wrapper in logging_middleware.py. Next I’m reading the concrete functions that load the handbook, retrieve chunks, and assemble the final answer so I can map the exact flow rather than infer it.

Read [](file:///c%3A/Users/ADMIN/STAI-WEEK5-NEW/core.py)

Read [](file:///c%3A/Users/ADMIN/STAI-WEEK5-NEW/app.py)

Read [](file:///c%3A/Users/ADMIN/STAI-WEEK5-NEW/logging_middleware.py)

Read [](file:///c%3A/Users/ADMIN/STAI-WEEK5-NEW/frontend.py)

The implementation is compact: ChromaDB stores the handbook, Ollama embeddings power both memory and handbook retrieval, and the app frontends both call the same traced chat wrapper. I have enough context to write the architecture map, but I’m doing one quick pass on dependencies to confirm the exact framework set before summarizing.

Searched for regex `FastAPI|Streamlit|mlflow|chromadb|langchain|openai|pypdf|ollama` (`**/requirements.txt`), 10 results

Read [](file:///c%3A/Users/ADMIN/STAI-WEEK5-NEW/requirements.txt)

The RAG path is implemented in core.py and exposed through both app.py and frontend.py, with MLflow tracing added in logging_middleware.py. The overall flow is: ingest the handbook PDF into a persistent Chroma vector store, retrieve semantically similar chunks with Ollama embeddings, wrap that context in a fixed system prompt, then call a local Ollama-backed chat model through the OpenAI client.

**1. Data Storage and Ingestion**

The handbook knowledge base is a persistent ChromaDB vector store, not SQL or a graph DB. In core.py, `_vectorstore = Chroma(...)` points at chroma_handbook_db, which persists to `chroma.sqlite3`. There is a second Chroma store for conversational memory in `data/memory/<student_id>/chroma.sqlite3` via `StudentMemory`.

The ingestion path is:
- core.py → **load_handbook()** checks whether the vector store is empty and loads the PDF once.
- core.py → **ingest_pdf()** reads student_handbook.pdf with `PdfReader`, extracts page text, splits it with `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)`, and writes the chunks into Chroma with `chunk_index` metadata.
- Embeddings use Ollama in two places:
  - Handbook RAG: `OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)`
  - Memory store: `OllamaEmbeddingFunction(url=.../api/embeddings, model_name=EMBED_MODEL)`

Critical snippet from core.py:

```python
_embeddings_model = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
_vectorstore = Chroma(persist_directory=HANDBOOK_DB_DIR, embedding_function=_embeddings_model)

def ingest_pdf(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> int:
    reader = PdfReader(file_path)
    raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_text(raw_text)
    if chunks:
        metadatas = [{"chunk_index": i} for i in range(len(chunks))]
        _vectorstore.add_texts(chunks, metadatas=metadatas)
    return len(chunks)
```

**2. The Retrieval Mechanism**

The core retrieval function is core.py → **rag_retrieve()**. It performs semantic similarity search with Chroma, using `similarity_search_with_score(query, k=k)`. The search is not hybrid and not text-to-SQL. It is purely embedding-based semantic retrieval.

Important details:
- The function always prepends the first handbook chunk via core.py → **_get_title_chunk()** by fetching `chunk_index = 0`.
- It uses an adaptive cutoff: after retrieving the top `k` results, it keeps additional chunks only if their score is within `score_margin` of the best score.
- It deduplicates chunk text before joining the final context.

Critical snippet from core.py:

```python
def rag_retrieve(query: str, k: int = 3, score_margin: float = 0.25) -> str:
    if _vectorstore._collection.count() == 0:
        return ""
    scored = _vectorstore.similarity_search_with_score(query, k=k)
    if not scored:
        return ""
    best_score = scored[0][1]
    docs = [doc for doc, score in scored if score - best_score <= score_margin]
    seen = set()
    unique_texts = []
    title_chunk = _get_title_chunk()
    if title_chunk:
        seen.add(title_chunk)
        unique_texts.append(title_chunk)
    for doc in docs:
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            unique_texts.append(doc.page_content)
    return "\n\n".join(unique_texts)
```

There is also a separate conversational memory retrieval path in core.py → **StudentMemory.recall()**, but that is not the handbook RAG store. It is another Chroma collection used to recall prior turns for a student session.

**3. Prompting and Generation**

The LLM is called through the OpenAI client, but against a local Ollama endpoint: `OpenAI(base_url=f"{OLLAMA_BASE_URL}/v1", api_key="ollama")`. The default chat model is `gemma3:1b`, and the embedding model is `nomic-embed-text`.

The generation path is:
- core.py → **build_messages()** creates the prompt payload.
- core.py → **complete()** and **complete_with_usage()** send the messages to the model.
- core.py → **FAQBot.chat_traced()** is the end-to-end RAG call path.

The exact system prompt in core.py is:

```python
SYSTEM_PROMPT = (
    "You are the Oakridge Academy Student Handbook FAQ assistant. "
    "Answer using ONLY the provided handbook context, but you may reasonably "
    "paraphrase or infer an answer if it's clearly supported by the context "
    "even if the exact wording differs (e.g. the handbook calls itself an "
    "'Academy', so treat questions about 'the school'/'the university'/'this "
    "institution' as referring to it). "
    "If the answer is genuinely not supported by the context, say you don't know. "
    "Do NOT write essays, assignments, or academic work for students.\n\n"
    "Earlier turns in this conversation are shown for context only. Always "
    "answer the CURRENT question using the handbook context given with it, even "
    "if a similar question was asked before — give the specific detail the "
    "current question asks for, don't just repeat an earlier answer."
)
```

The template used to feed retrieved context to the model is:

```python
def build_messages(context: str, question: str, history: list[tuple[str, str]] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for q, a in history or []:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"})
    return messages
```

The main generation flow in core.py is:

```python
def chat_traced(self, user_input: str) -> tuple[str, dict]:
    clean = self._input_guard(user_input)
    context = self._context_for(clean)
    history = self.memory.recall(clean) if len(clean.split()) > 4 else []
    raw, usage = complete_with_usage(build_messages(context, clean, history=history))
    safe = self._output_guard(raw)
    if not is_non_answer(safe):
        self.memory.remember(clean + " -> " + safe)
    return safe, usage
```

One important implementation detail: the traced wrapper used by the app and frontend, logging_middleware.py → **traced_chat()**, rebuilds messages without passing history into `build_messages()`. So the user-facing traced path uses RAG context, but not the conversation-history recall that `FAQBot.chat_traced()` would otherwise include.

**4. Integration and Tooling**

The pipeline is exposed in two ways:
- app.py provides a FastAPI service with `POST /chat/stream`.
- frontend.py provides a Streamlit chat UI.
Both call logging_middleware.py → **traced_chat()**, which is the shared integration point.

FastAPI path in app.py:
- `load_handbook_once()` runs on startup and ingests the handbook if needed.
- `/chat/stream` gets or creates a cached `FAQBot` per student ID.
- If guardrails raise `ValueError`, the endpoint returns a safe fallback SSE message.
- Otherwise it streams the answer with `stream_text()`.

Streamlit path in frontend.py:
- Initializes a per-session `FAQBot`.
- Calls `load_handbook()` once per session.
- Streams the answer chunk-by-chunk to the chat UI.

Observability and guardrails:
- logging_middleware.py wraps the request with MLflow spans:
  - `chat_request`
  - `rag_retrieval`
  - `llm_inference`
- It logs latency, token usage, model name, and estimated cost as one JSON line per request.
- There is no separate LangChain output parser around generation.
- The only structured parsing is the regex-based JSON extraction in core.py → **is_on_topic()** for topic classification.
- Guardrails in core.py include:
  - **is_integrity_violation()** keyword blocking for academic cheating / essay generation
  - **redact_pii()** input/output redaction
  - **is_on_topic()** LLM classifier for allowed handbook topics
  - **output_validator()** to block essay-like responses and redact output
  - **is_non_answer()** to avoid storing low-value responses in memory

Critical integration snippet from logging_middleware.py:

```python
def traced_chat(bot: FAQBot, user_input: str) -> str:
    start = time.perf_counter()
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    answer = None
    error = None

    try:
        with mlflow.start_span(name="chat_request", span_type="CHAIN") as chat_span:
            chat_span.set_attribute("user_input", user_input)

            clean = bot._input_guard(user_input)

            with mlflow.start_span(name="rag_retrieval", span_type="RETRIEVER") as rag_span:
                context = bot._context_for(clean)
                rag_span.set_attribute("context_chars", len(context))

            with mlflow.start_span(name="llm_inference", span_type="LLM") as llm_span:
                from core import build_messages, complete_with_usage
                raw, usage = complete_with_usage(build_messages(context, clean))
                llm_span.set_attribute("model", MODEL)
                llm_span.set_attribute("total_tokens", usage["total_tokens"])

            answer = bot._output_guard(raw)
            bot.memory.remember(clean + " -> " + answer)
            chat_span.set_attribute("answer", answer)
```

If you want, I can turn this into a modular production-ready refactor map next: component boundaries, service interfaces, and a file-by-file migration plan.

Created 4 todos