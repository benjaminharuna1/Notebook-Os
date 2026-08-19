# Auth Feature Contract

Authentication — JWT login, register, token persistence.

## What it does

Handles user registration and login. Stores JWT in `localStorage`. Provides `token`, `currentUser`, and `isAuthenticated` stores consumed by `client.ts` for all API requests. Routes unauthenticated users to `/auth/login`.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/register` | POST | Create new account |
| `/auth/login` | POST | Login (email or username) |
| `/auth/logout` | POST | Invalidate session |
| `/auth/me` | GET | Get current user profile |

## State managed

| Store | Type | Purpose |
|---|---|---|
| `token` | `string \| null` | JWT token — synced with localStorage |
| `currentUser` | `User \| null` | Logged-in user profile |
| `isAuthenticated` | `boolean` | Derived from token presence |

## Components

No feature-specific components — auth pages are in `routes/auth/login/` and `routes/auth/register/`.

## Special patterns

- **Token → localStorage sync**: `token.subscribe()` writes/removes from `localStorage`
- **401 auto-redirect**: `client.ts` redirects to `/auth/login` on any 401 response
- **Sole cross-feature import**: `auth/store.ts` is the only store imported by `core/api/client.ts`
