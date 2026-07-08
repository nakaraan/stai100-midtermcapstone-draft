#!/usr/bin/env bash
cd "$(dirname "$0")/.."
source .venv/bin/activate
mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///.mlflow/mlflow.db
