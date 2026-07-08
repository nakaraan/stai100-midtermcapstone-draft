Set-Location "$PSScriptRoot\.."
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --reload --port 8000
