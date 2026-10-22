Write-Host "=== WarrantyMind Local Warranty Workflow ===" -ForegroundColor Cyan
if (-Not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    py -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-Not (Test-Path ".env")) {
    Copy-Item .env.example .env
}
Write-Host "Starting WarrantyMind on http://127.0.0.1:8000 ..." -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn warrantymind.main:app --host 127.0.0.1 --port 8000
