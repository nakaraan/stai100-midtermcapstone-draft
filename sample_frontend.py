import uuid

import streamlit as st

from core import FAQBot, stream_text, load_handbook
from logging_middleware import traced_chat

st.set_page_config(page_title="Oakridge Academy FAQ Bot", page_icon="🎓")

# ── Session state ───────────────────────────────
if "student_id" not in st.session_state:
    st.session_state.student_id = f"student_{uuid.uuid4().hex[:8]}"
if "bot" not in st.session_state:
    st.session_state.bot = FAQBot(st.session_state.student_id)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "handbook_ingested" not in st.session_state:
    with st.spinner("Loading student handbook..."):
        load_handbook()
    st.session_state.handbook_ingested = True

# ── Sidebar ───────────────────────────────────────────
with st.sidebar:
    st.header("Knowledge Base")
    st.caption("Student Handbook (built-in)")
    st.divider()
    st.caption(f"Session ID: `{st.session_state.student_id}`")

st.title("Oakridge Academy FAQ Bot")
st.caption("Ask about academic policies, the code of conduct, dress code, or campus health & safety.")

# ── Render chat history ─────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── Chat input ────────────────────────────────────────────
prompt = st.chat_input("Ask a question about the student handbook...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        try:
            answer = traced_chat(st.session_state.bot, prompt)
            chunks = stream_text(answer)
        except ValueError:
            # Guardrail message
            chunks = iter([
                "I can't help with that request. I can only answer questions "
                "about the student handbook (academic policies, code of conduct, "
                "dress code, and campus health & safety)."
            ])

        # Streaming pipeline
        placeholder = st.empty()
        displayed = ""
        for chunk in chunks:
            displayed += chunk
            placeholder.markdown(displayed)

    st.session_state.messages.append({"role": "assistant", "content": displayed})
