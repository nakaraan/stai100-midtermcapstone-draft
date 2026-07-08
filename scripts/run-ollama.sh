#!/usr/bin/env bash
if curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags --max-time 2 | grep -q 200; then
    echo "Ollama is already running on :11434 - nothing to do."
else
    ollama serve
fi
