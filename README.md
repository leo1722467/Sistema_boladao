# Sistemao Bolado API

Backend service built with FastAPI, SQLAlchemy (async), Alembic, and JWT auth.

## Prerequisites
- Python 3.9+
- Poetry or pip

## Setup
```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

Set environment variables (PowerShell):
```powershell
$env:APP_DB_URL = "sqlite+aiosqlite:///./app.db"
$env:APP_JWT_SECRET = "change-me"
$env:APP_APP_PORT = "8081"
```

Run migrations:
```powershell
alembic upgrade head
```

Seed dev user:
```powershell
python -m scripts.seed
```

Run API:
```powershell
python -m app.main
```

Authenticate using PowerShell:
```powershell
$login = Invoke-RestMethod -Method POST -Uri "http://localhost:8081/auth/login" -Body (@{ email = "admin@example.com"; password = "admin123" } | ConvertTo-Json) -ContentType "application/json"
Invoke-RestMethod -Method GET -Uri "http://localhost:8081/auth/me" -Headers @{ Authorization = "Bearer $($login.access_token)" }
```