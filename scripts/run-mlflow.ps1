Set-Location "$PSScriptRoot\.."
.\.venv\Scripts\Activate.ps1
mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri sqlite:///.mlflow/mlflow.db
