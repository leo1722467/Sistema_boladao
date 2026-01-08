# Sistemao Bolado API

Backend service built with FastAPI, SQLAlchemy (async), Alembic, and JWT auth.

## Prerequisites
- Python 3.9+
- Poetry or pip

## Setup
```cmd
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Set environment variables (Command Prompt):
```cmd
set APP_DB_URL=sqlite+aiosqlite:///./app.db
set APP_JWT_SECRET=change-me
set APP_APP_PORT=8081
```

Run migrations:
```cmd
alembic upgrade head
```

Seed dev user:
```cmd
python -m scripts.seed
```

Run API:
```cmd
python -m app.main
```

Authenticate using Command Prompt (curl):
```cmd
curl -X POST ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}" ^
  http://localhost:8081/auth/login

rem Copy the access_token from the response above and use it here:
curl -X GET ^
  -H "Authorization: Bearer <ACCESS_TOKEN>" ^
  http://localhost:8081/auth/me
```
