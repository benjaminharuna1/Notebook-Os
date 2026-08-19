# Chat Feature Contract

Most complex frontend feature. Real-time SSE streaming chat with session management.

## What it does

Multi-session conversational interface for asking questions about indexed documents. Streams LLM responses token-by-token via SSE. Shows source citations inline.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/chat` | POST (SSE) | Send message, stream response |
| `/chat/sessions` | GET | List sessions (filtered by project) |
| `/chat/sessions/{id}` | GET | Load session with full message history |
| `/chat/sessions/{id}` | DELETE | Delete session |
| `/chat/sessions/{id}` | PATCH | Rename session title |

## State managed

| Store | Type | Purpose |
|---|---|---|
| `sessions` | `ChatSession[]` | All sessions for current project |
| `currentSessionId` | `string \| null` | Active session |
| `messages` | `ChatMessage[]` | Messages in current session |
| `streaming` | `boolean` | Whether SSE stream is active |

## Components

| Component | Purpose |
|---|---|
| `ChatWindow.svelte` | Main chat container, session list + message area |
| `ChatInput.svelte` | Text input with send button, slash command support |
| `ChatMessage.svelte` | Single message bubble with source citations |

## Special patterns

- **SSE streaming**: `streamChat()` wraps `createSSEConnection`. Returns abort function.
- **Regeneration**: Can regenerate last assistant response via `regenerate: true` option
- **Slash commands**: `slashCommand` param passed to backend for special actions
- **Source chunks**: `onSources` callback receives `SourceChunk[]` with title, page, apa_reference
- **Abort on destroy**: Components MUST call the returned abort function when unmounting mid-stream
- **Session auto-create**: New session created on first message, ID returned in `onDone` callback
