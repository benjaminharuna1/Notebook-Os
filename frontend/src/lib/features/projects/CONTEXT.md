# Projects Feature Contract

Project CRUD and workspace management.

## What it does

Manages research projects — each project is a workspace containing documents, chat sessions, graph, and literature data. Provides list, create, edit, and delete operations. The active project context is passed to most other features via route params.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/projects` | GET | List all projects |
| `/projects` | POST | Create project |
| `/projects/{id}` | GET | Get project details |
| `/projects/{id}` | PATCH | Update project name/description |
| `/projects/{id}` | DELETE | Delete project |

## State managed

No global store — projects fetched on route load. Active project determined by `[id]` route param.

## Components

No feature-specific components — project UI is in `routes/projects/`.

## Types

- `Project`: id, name, description, created_at, updated_at, doc_count
