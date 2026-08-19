# Frontend Core Library Contract

`src/lib/core/` provides shared infrastructure used by all 12 feature modules.

## Pipeline order (feature execution order in UI lifecycle)

```
auth → projects → ingestion → documents → search → chat → graph → literature → models → skills → settings → actions
```

The `AppShell` starts action polling on mount. Auth gates all routes.

## Key files

| File | Role |
|---|---|
| `api/client.ts` | Central HTTP + SSE client. Exports `api` (get/post/put/patch/delete) and `createSSEConnection`. Reads JWT from `auth/store`. Auto-redirects to `/auth/login` on 401. |
| `stores/toasts.ts` | Global toast notification queue. Auto-dismiss after 4 s. Used via `toasts.add(msg, type)`. |
| `components/layout/AppShell.svelte` | Root layout shell — Sidebar + main slot + ActionsDock + Toast overlay. Starts/stops action polling. |
| `components/layout/Sidebar.svelte` | Navigation sidebar with feature links. |
| `components/layout/Header.svelte` | Top header bar. |
| `components/ui/*` | Reusable primitives: Button, Modal, PasswordInput, Spinner, Toast. |

## Data flow

```
Route (+page.svelte / +page.ts)
  → Feature api.ts → core/api/client.ts → Backend REST / SSE
  → Feature store.ts (svelte writable) ← Component reads via $state / $store
  → Feature components render UI
```

- Components import from their own feature's `api.ts`, `store.ts`, `types.ts`
- `client.ts` is the ONLY module that calls `fetch()` (except `ingestion` and `literature` for file uploads/exports)
- Stores are plain `writable<T>` — no derived complexity at the core level

## Cross-feature rules

- `core/` never imports from `features/` except `auth/store.ts` (for token)
- Features never import from each other's stores
- `graph/types.ts` is the shared type hub — literature re-exports its types
- All SSE connections return an abort `() => void` function — components MUST call it on destroy
- `BASE_URL` comes from `VITE_API_URL` env var, defaults to `http://localhost:8000/api/v1`
