# auth — user authentication

One job: register, login, and authenticate users via JWT tokens and cookies.

## Inputs

| Input | Source | Notes |
|---|---|---|
| RegisterRequest | `req.email, req.username, req.password` | POST /auth/register |
| LoginRequest | `req.identifier, req.password` | email or username accepted |
| Current user | `get_current_user` dependency | JWT cookie or header |

## Process

1. **Register** — check uniqueness (email, username), hash password, insert user + default settings, return JWT
2. **Login** — look up by email or username, verify password, set httponly cookie, return JWT
3. **Logout** — delete access_token cookie
4. **Me** — return current user from JWT

## Outputs

| Output | Type | Notes |
|---|---|---|
| AuthResponse | `{token, user: {id, email, username}}` | Returned on register/login |
| Current user dict | `{id, email, username}` | From /auth/me |

## Key files

| File | Purpose |
|---|---|
| `router.py` | FastAPI endpoints: register, login, logout, me |
| `service.py` | AuthService: registration, login, password verification |
| `schemas.py` | RegisterRequest, LoginRequest, AuthResponse |

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports
