# Notebook AI OS Frontend

SvelteKit + TypeScript + Tailwind UI for the Notebook AI OS research assistant.

## Directory tree

```
frontend/src/
├── app.html                          ← HTML shell
├── app.css                           ← Global styles
├── lib/
│   ├── core/
│   │   ├── api/client.ts             ← Central fetch + SSE client
│   │   ├── stores/toasts.ts          ← Global toast notifications
│   │   └── components/
│   │       ├── layout/               ← AppShell, Header, Sidebar
│   │       └── ui/                   ← Button, Modal, Spinner, Toast, PasswordInput
│   └── features/                     ← 12 feature modules (see table)
├── routes/                           ← SvelteKit file-based routing
│   ├── +layout.svelte                ← Root layout (auth gate)
│   ├── +page.svelte                  ← Landing / project picker
│   ├── auth/login|register/
│   ├── chat/[sessionId]/
│   ├── graph/
│   ├── library/[docId]/
│   ├── projects/[id]/
│   ├── search/
│   ├── settings/
│   └── skills/
└── static/                           ← Favicon, static assets
```

## Feature routing table

| Route | Feature module | Purpose |
|---|---|---|
| `/auth/*` | `auth` | Login, register, JWT storage |
| `/` `/projects/[id]` | `projects` | Project CRUD, workspace switcher |
| `/chat/[sessionId]` | `chat` + `ingestion` | Chat with SSE streaming, session history |
| `/library/[docId]` | `documents` + `ingestion` | Document list, PDF viewer, upload queue |
| `/graph` | `graph` + `literature` | Knowledge graph, literature map, concept explorer |
| `/search` | `search` | Semantic + keyword search over documents |
| `/settings` | `settings` + `models` | Provider keys, chunk config, model switching |
| `/skills` | `skills` | Skill catalog, install, enable/disable |

## Key conventions

- **Framework**: SvelteKit (file-based routing), Svelte 5 runes (`$state`, `$derived`, `$props`)
- **Language**: TypeScript strict — every feature has `types.ts`
- **Styling**: Tailwind CSS utility-first, no component library
- **State**: Svelte writable stores (no Redux/SvelteKit stores hybrid)
- **API**: Single `client.ts` → `api.get/post/put/patch/delete` + `createSSEConnection`
- **Auth**: JWT token in `localStorage`, injected via `Authorization: Bearer` header
- **Streaming**: SSE for chat + graph/literature summaries — always return abort function
- **Polling**: Actions dock polls `/actions` every 1.5 s from `AppShell`
- **Imports**: Use `$lib/` alias — never relative paths across features

## How to add a new feature

1. Create `src/lib/features/<name>/` with `api.ts`, `types.ts`, `store.ts` (if needed)
2. Import `api` from `$lib/core/api/client` — never `fetch()` directly
3. Create route at `src/routes/<name>/+page.svelte` (or `+page.ts` for data loaders)
4. Add components inside `features/<name>/components/`
5. Register in Sidebar nav if user-visible
6. If the feature has a background job, add it to the actions polling loop

## Cross-feature rules

- Features NEVER import from each other's `store.ts` — only `types.ts` is shared
- `auth/store.ts` (`token`) is the sole exception — `client.ts` and `ingestion` read it
- All API calls go through `client.ts` — no direct `fetch()` outside file uploads
- Types shared across features live in `graph/types.ts` (graph + literature share models)
