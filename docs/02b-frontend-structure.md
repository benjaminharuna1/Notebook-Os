# Frontend Structure

```
frontend/
├── src/
│   ├── app.css                        # Global design tokens & resets
│   ├── app.html                       # SvelteKit HTML shell
│   │
│   ├── lib/
│   │   ├── core/                      # Shared non-feature code
│   │   │   ├── api/
│   │   │   │   └── client.ts          # Base fetch wrapper (auth, errors, SSE)
│   │   │   ├── components/
│   │   │   │   ├── ui/                # Headless/generic UI primitives
│   │   │   │   └── layout/            # AppShell, Sidebar, Header
│   │   │   └── stores/
│   │   │       └── toasts.ts          # Global notification store
│   │   │
│   │   └── features/                  # ← FEATURE-BASED MODULES (12 features)
│   │       │
│   │       ├── auth/                  # Login/register UI
│   │       │   ├── api.ts
│   │       │   └── components/
│   │       │
│   │       ├── projects/              # Project selector/CRUD UI
│   │       │   ├── api.ts
│   │       │   └── components/
│   │       │
│   │       ├── ingestion/             # File upload & processing status
│   │       │   ├── api.ts
│   │       │   ├── store.ts
│   │       │   ├── types.ts
│   │       │   └── components/
│   │       │       ├── FileDropzone.svelte
│   │       │       ├── UploadQueue.svelte
│   │       │       └── UploadProgress.svelte
│   │       │
│   │       ├── documents/             # Document library
│   │       │   ├── api.ts
│   │       │   ├── store.ts
│   │       │   ├── types.ts
│   │       │   └── components/
│   │       │       ├── DocumentList.svelte
│   │       │       ├── DocumentCard.svelte
│   │       │       └── DocumentDetail.svelte
│   │       │
│   │       ├── search/                # Semantic search
│   │       │   ├── api.ts
│   │       │   ├── store.ts
│   │       │   ├── types.ts
│   │       │   └── components/
│   │       │       ├── SearchBar.svelte
│   │       │       └── SearchResults.svelte
│   │       │
│   │       ├── chat/                  # AI chat interface
│   │       │   ├── api.ts             # SSE streaming client
│   │       │   ├── store.ts           # Sessions + messages state
│   │       │   ├── types.ts
│   │       │   └── components/
│   │       │       ├── ChatWindow.svelte
│   │       │       ├── ChatMessage.svelte
│   │       │       ├── ChatInput.svelte
│   │       │       ├── ChatSidebar.svelte
│   │       │       └── SourceCitation.svelte
│   │       │
│   │       ├── graph/                 # Knowledge graph visualization
│   │       │   ├── api.ts
│   │       │   ├── store.ts
│   │       │   ├── types.ts
│   │       │   └── components/
│   │       │       ├── KnowledgeGraph.svelte
│   │       │       └── GraphControls.svelte
│   │       │
│   │       ├── literature/            # Literature mapping UI
│   │       │   ├── api.ts
│   │       │   └── components/
│   │       │
│   │       ├── models/                # Model selector & switching
│   │       │   ├── api.ts
│   │       │   ├── store.ts
│   │       │   ├── types.ts
│   │       │   └── components/
│   │       │       ├── ModelSelector.svelte
│   │       │       └── ModelBadge.svelte
│   │       │
│   │       ├── skills/                # Skill catalog & management UI
│   │       │   ├── api.ts
│   │       │   └── components/
│   │       │
│   │       ├── settings/              # User preferences UI
│   │       │   ├── api.ts
│   │       │   └── components/
│   │       │
│   │       └── actions/               # Background action status UI
│   │           ├── api.ts
│   │           └── components/
│   │
│   └── routes/                        # SvelteKit file-based routing
│       ├── +layout.svelte             # Root layout (AppShell)
│       ├── +page.svelte               # / → redirects to /chat
│       ├── login/                     # /login — auth page
│       │   └── +page.svelte
│       ├── chat/
│       │   ├── +page.svelte           # /chat — main chat view
│       │   └── [sessionId]/
│       │       └── +page.svelte       # /chat/:id — specific session
│       ├── library/
│       │   ├── +page.svelte           # /library — document browser
│       │   └── [docId]/
│       │       └── +page.svelte       # /library/:id — document detail
│       ├── search/
│       │   └── +page.svelte           # /search — semantic search
│       ├── graph/
│       │   └── +page.svelte           # /graph — knowledge graph
│       └── settings/
│           └── +page.svelte           # /settings — user preferences
│
├── static/
├── package.json
├── svelte.config.js
└── vite.config.ts
```
