"""Streamlit conversational UI for AGENT P.

Styled after sample_frontend.py (session-state chat history, sidebar, chat_message
rendering), but unlike that reference this UI never imports the agent, database,
or config modules directly — every turn is a single HTTP POST to the FastAPI
backend in api/main.py, so the UI and the agent stay fully decoupled.
"""

import csv
import io
import os
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.environ.get("AGENT_P_API_URL", "http://localhost:8000")
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"
REQUEST_TIMEOUT_SECONDS = 120

CONNECTION_ERROR_MESSAGE = (
    "I couldn't reach the AGENT P backend right now. Please confirm the API "
    f"is running at {API_BASE_URL} and try again."
)

st.set_page_config(page_title="AGENT P — Solar Analytics Assistant", page_icon="☀️")

# ── Session state ────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = f"session_{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None


def ask_agent(query: str) -> dict:
    """POST the query to AGENT P's FastAPI backend and return the parsed JSON body."""
    response = requests.post(
        CHAT_ENDPOINT,
        json={"query": query, "session_id": st.session_state.session_id},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _monthly_metrics_csv(monthly_metrics: dict) -> str:
    attr_names = sorted({attr for values in monthly_metrics.values() for attr in values})
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Month", *attr_names])
    for month in sorted(monthly_metrics, key=int):
        row = monthly_metrics[month]
        writer.writerow([month, *(row.get(attr, "") for attr in attr_names)])
    return buffer.getvalue()


st.title("☀️ AGENT P")
st.caption("Ask about solar irradiation, weather, or site feasibility for a location and date range.")

# ── Render chat history ──────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── Chat input ────────────────────────────────────────────────────────────────
prompt = st.chat_input("e.g. Monthly average irradiation from Feb to June 2022 at our Caloocan warehouse")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Checking NSRDB..."):
            try:
                result = ask_agent(prompt)
                answer = result.get("answer", "")
                # Only refresh the sidebar when the response actually resolved a
                # location. A guardrail rejection or a disambiguation round-trip
                # with nothing resolved yet must not blank out the last good
                # metrics view — `needs_clarification` alone isn't a safe signal
                # here since a guardrail rejection also defaults it to False.
                if result.get("location"):
                    st.session_state.last_result = result
            except requests.exceptions.RequestException:
                answer = CONNECTION_ERROR_MESSAGE
        st.write(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})

# ── Sidebar — retrieved solar metrics from the last resolved query ──────────
# Rendered last (not near the top) because Streamlit reruns this whole script
# top-to-bottom on every interaction: session_state.last_result is only updated
# by the chat-input handling above, so the sidebar must read it *after* that
# block runs in order to show the metrics from the turn that just completed.
with st.sidebar:
    st.header("Solar Metrics")
    st.caption(f"Session ID: `{st.session_state.session_id}`")
    st.divider()

    result = st.session_state.last_result
    if not result:
        st.caption("Ask a question to see retrieved site data here.")
    else:
        location = result.get("location")
        if location:
            label = location.get("name") or f"{location['latitude']}, {location['longitude']}"
            st.markdown(f"**Site:** {label}")
            st.caption(f"Lat/Lon: {location['latitude']}, {location['longitude']}")

        if result.get("year"):
            st.markdown(f"**Year:** {result['year']}")
        if result.get("start_month") and result.get("end_month"):
            st.markdown(f"**Months:** {result['start_month']}–{result['end_month']}")
        if result.get("attributes"):
            st.caption("Attributes: " + ", ".join(result["attributes"]))

        monthly_metrics = result.get("monthly_metrics")
        if monthly_metrics:
            st.divider()
            st.caption("Monthly averages")
            rows = []
            for month in sorted(monthly_metrics, key=int):
                row = {"Month": int(month)}
                row.update(monthly_metrics[month])
                rows.append(row)
            st.dataframe(rows, width="stretch", hide_index=True)

            st.download_button(
                "Download monthly summary (CSV)",
                data=_monthly_metrics_csv(monthly_metrics),
                file_name="agent_p_monthly_summary.csv",
                mime="text/csv",
            )
