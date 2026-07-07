#!/usr/bin/env bash
# Runs the FastAPI backend and Streamlit UI as sibling processes in one
# container. Either process exiting (crash or signal) brings the other down
# too, so Docker sees one failure instead of a silently half-dead container.
set -euo pipefail

api_pid=""
ui_pid=""

cleanup() {
    trap - SIGTERM SIGINT EXIT
    echo "Shutting down AGENT P..."
    [ -n "$api_pid" ] && kill -TERM "$api_pid" 2>/dev/null || true
    [ -n "$ui_pid" ] && kill -TERM "$ui_pid" 2>/dev/null || true
    wait "$api_pid" "$ui_pid" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT EXIT

echo "Starting FastAPI backend on :8000..."
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
api_pid=$!

echo "Starting Streamlit UI on :8501..."
python -m streamlit run app/ui.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &
ui_pid=$!

# Exit as soon as either process does, so the container's exit code reflects
# an actual failure instead of hanging on the surviving process.
wait -n "$api_pid" "$ui_pid"
exit $?
