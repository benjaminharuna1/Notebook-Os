# Actions Feature Contract

Background action monitoring with global polling dock.

## What it does

Tracks all long-running background actions across the app (graph generation, literature builds, etc.). Displays a floating dock in the bottom-right corner showing active actions with progress bars. Supports pause/resume. Polled globally from `AppShell` every 1.5 seconds.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/actions` | GET | List all user actions |
| `/actions/{id}/pause` | POST | Pause an action |
| `/actions/{id}/resume` | POST | Resume an action |

## State managed

| Store / Export | Type | Purpose |
|---|---|---|
| `actions` | `ActionInfo[]` | All current actions |
| `startActionPolling()` | function | Start 1.5s interval polling |
| `stopActionPolling()` | function | Stop polling (called on AppShell destroy) |
| `refreshActions()` | async function | Fetch latest actions list |
| `pauseAction(id)` | async function | Pause + refresh |
| `resumeAction(id)` | async function | Resume + refresh |

## Components

| Component | Purpose |
|---|---|
| `ActionsDock.svelte` | Floating panel listing active actions with progress |

## Special patterns

- **Global polling**: Started in `AppShell.svelte` on mount, stopped on destroy
- **Polling interval**: 1500 ms default — covers graph gen, literature builds, etc.
- **Error-tolerant**: `refreshActions()` silently catches failures, keeps last known list
- **Action kinds**: `graph_generation`, `literature_build`, etc. — determined by backend `kind` field
