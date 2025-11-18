# Authentication Guide

A simple, kid-friendly guide to how authentication works in this project, where to look in the code, how to call endpoints, and how to fix common issues.

## What Authentication Means Here
- You prove who you are with an email and password.
- The server gives you tokens (special strings) that say “this is you”.
- You use these tokens when you talk to the server next time.
- For web pages, the token is saved in a cookie. For APIs, you send it in a header.

## The Important Pieces (Files)
- `app/api/auth.py` — Endpoints for login, token issuing, refresh, and getting your profile.
- `app/services/auth.py` — Logic to register users, check passwords, and create tokens.
- `app/core/security.py` — Helpers to hash passwords and create/verify JWT tokens.
- `app/core/middleware.py` — Checks every request to see if you’re allowed in (API: 401 JSON; Web: redirect to login).
- `app/core/authorization.py` — Roles (Admin, Agent, etc.) and helpers to restrict access by role.
- `app/web/router.py` — Web login form; sets the auth cookie and redirects to the dashboard.

## Tokens in Plain Words
- Access token: short-lived; used for most API calls and page access.
- Refresh token: longer-lived; used to get a new access token when it expires.
- Both tokens are JWTs signed with `HS256` using `settings.JWT_SECRET`.

## How Tokens Are Made
- In `app/services/auth.py` → `authenticate(...)`:
  1. Find user by email.
  2. Check password with bcrypt (`verify_password`).
  3. Create access token and refresh token (`create_jwt_token`).
- Helper functions in `app/core/security.py`:
  - `hash_password(password)` — creates a bcrypt hash.
  - `verify_password(plain, hashed)` — checks your password against the hash.
  - `create_jwt_token(subject, expires_in, claims)` — builds and signs a JWT with `sub`, `iat`, `exp`.
  - `verify_jwt_token(token)` — checks and decodes a JWT.

## Web vs API — How Do I Send Tokens?
- Web Flow (browser):
  - Submit login form to `POST /web/login`.
  - On success, the server sets a cookie called `access_token` and redirects you to `/dashboard`.
  - After that, protected pages can use the cookie to know you’re logged in.
- API Flow (client/tools/code):
  - Login via `POST /auth/login` (JSON) or `POST /auth/token` (form) to get tokens.
  - Send `Authorization: Bearer <ACCESS_TOKEN>` header for protected API endpoints.

## The Endpoints You’ll Use
- `POST /auth/login` → Body: `{ "email": "...", "password": "..." }` → Returns `{ access_token, refresh_token, token_type }`.
- `POST /auth/token` → OAuth2 form version of login → Returns tokens.
- `POST /auth/refresh` → Uses the current user (Bearer token required) to return new tokens.
- `GET /auth/me` → Returns info about the logged-in user (Bearer token required).
- `POST /web/login` → Web login form; sets cookie and redirects to `/dashboard`.
- `GET /web/logout` → Clears the cookie and redirects to `/`.

## Example Requests
- Login via API (Command Prompt):
  ```bash
  curl -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"test@example.com\",\"password\":\"test123456\"}"
  ```
- Use the token:
  ```bash
  curl http://localhost:8000/auth/me \
    -H "Authorization: Bearer <ACCESS_TOKEN>"
  ```
- Web login (browser):
  - Open `http://localhost:8000/`, submit the login form.
  - You’ll be redirected to `http://localhost:8000/dashboard` with the `access_token` cookie set.

## How the Middleware Guards You
- Defined in `app/core/middleware.py`:
  - Public paths (no auth needed): `"/", "/web/login", "/auth", "/static", "/docs", "/redoc", "/openapi.json", "/favicon.ico"`.
  - Protected paths: `"/admin", "/dashboard"` and all API paths like `"/api"`.
  - If you’re not authenticated:
    - API request → `401 {"detail":"Not authenticated"}`.
    - Web request → redirect to `/` (login).
- It checks for tokens in this order:
  1. `Authorization: Bearer <token>` header.
  2. `access_token` cookie.

## Getting the Current User Inside Endpoints
- `get_current_user` (in `app/api/auth.py`) expects the Bearer header.
- `get_current_user_any` accepts either Bearer header or cookie.
- Use them with FastAPI `Depends` inside your routes to protect endpoints.

## Roles and Permissions
- `app/core/authorization.py` contains `UserRole` and helpers like:
  - `require_admin_role`
  - `require_any_authenticated_role`
  - Decorator `@require_role(UserRole.ADMIN)` for admin-only endpoints.
- Typical usage:
  ```py
  from fastapi import Depends
  from app.core.authorization import require_admin_role

  @router.get("/admin-only")
  async def admin_only(auth_ctx = Depends(require_admin_role)):
      return {"ok": True}
  ```

## Troubleshooting (Start Here)
- 401 Unauthorized on API:
  - Did you set `Authorization: Bearer <ACCESS_TOKEN>`?
  - Is your access token expired? Use `/auth/refresh` or login again.
  - Is `settings.JWT_SECRET` consistent and set? Tokens won’t validate if secrets differ.
- 302 Redirect to `/` on web page:
  - You’re hitting a protected page without `access_token` cookie (login via `/web/login`).
  - Cookie path/domain flags might block cookies if you changed hosts/HTTPS.
- Login fails:
  - Email not found or wrong password.
  - User inactive (`auth.ativo` must be True).
- Mixed cookie and header:
  - If one is invalid, you still get blocked. Use one valid method consistently.

## Roadmap to Implement/Fix Auth
- Check configuration:
  - `settings.JWT_SECRET`, `ACCESS_EXPIRES_MIN`, `REFRESH_EXPIRES_DAYS`.
- Confirm login flows:
  - API login via `/auth/login` returns tokens.
  - Web login via `/web/login` sets cookie and redirects.
- Standardize clients:
  - APIs → always include `Authorization: Bearer <ACCESS_TOKEN>`.
  - Web pages → rely on the `access_token` cookie.
- Protect new pages:
  - Add `Depends(get_current_user_any)` to routes needing auth.
  - Extend `protected_paths` if you want middleware to auto-gate a path.
- Implement refresh:
  - Use `/auth/refresh` when access tokens expire.
- Add logout:
  - Use `/web/logout` to clear the cookie and return to login.
- Testing:
  - Run `pytest -q` and align tests with current payloads.

## Technologies Used
- FastAPI — endpoints and DI.
- Jinja2 — server-side templates.
- jose (python-jose) — create/verify JWT.
- passlib[bcrypt] — password hashing.
- SQLAlchemy (async) — database operations.
- Starlette middlewares — request ID, security headers, and authentication enforcement.
- Cookies + Bearer headers — carry auth tokens.

## Where to Look (Quick Links)
- Helpers: `app/core/security.py`
- Endpoints: `app/api/auth.py`
- Service: `app/services/auth.py`
- Web login/logout: `app/web/router.py`
- Middleware gates: `app/core/middleware.py`
- Roles/permissions: `app/core/authorization.py`
- Schemas: `app/schemas/auth.py`