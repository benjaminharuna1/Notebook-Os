# API Contract — Search, Chat, Graph

All endpoints are prefixed with `/api/v1`. All endpoints require JWT authentication via cookie or header.

## Search

```
POST /api/v1/search
  Body: {
    query: string,
    top_k?: number,           // default: 15
    project_id?: string,
    document_ids?: string[]
  }
  Response: {
    results: [{
      chunk_id: string,
      content: string,
      score: float,
      document_id: string,
      document_title: string,
      page_number: int
    }]
  }
```

## Chat

```
POST /api/v1/chat
  Body: {
    session_id?: string,
    message: string,
    project_id?: string,
    model?: string,
    slash_command?: string,
    regenerate?: boolean
  }
  Response: Server-Sent Events (SSE) stream
    data: { type: "chunk", content: "..." }
    data: { type: "sources", sources: [{ title, page, doc_id, snippet }] }
    data: { type: "done", session_id: "..." }
    data: { type: "error", detail: "..." }

GET /api/v1/chat/sessions?project_id=string
  Response: { sessions: ChatSession[] }

GET /api/v1/chat/sessions/{session_id}
  Response: { session: ChatSession, messages: ChatMessage[] }

PATCH /api/v1/chat/sessions/{session_id}
  Body: { title: string }

DELETE /api/v1/chat/sessions/{session_id}
```

## Graph

```
GET /api/v1/graph
  Query: ?document_ids=id1,id2&depth=2&project_id=string&force=false
  Response: { nodes: [{ id, label, x, y, ... }], edges: [{ source, target, weight }] }

POST /api/v1/graph/generate
  Body: { project_id, document_ids?, depth?, force? }
  Response: { id, kind, status, ... }

GET /api/v1/graph/history?project_id=string
  Response: { checkpoints: [{ id, created_at, is_favourite, ... }] }

GET /api/v1/graph/history/{checkpoint_id}
PATCH /api/v1/graph/history/{checkpoint_id}
DELETE /api/v1/graph/history/{checkpoint_id}

POST /api/v1/graph/search
  Body: { project_id, query }
  Response: { refined_query, ... }

POST /api/v1/graph/concepts/summary
  Body: { project_id, label }
  Response: SSE stream (concept summary with sources)

GET /api/v1/graph/themes?project_id=string&limit=5
  Response: { documents: [{ doc_id, doc_name, themes: [{ concept, count }] }] }

GET /api/v1/graph/concepts/tracked?project_id=string
POST /api/v1/graph/concepts/tracked  (Body: { project_id, concept })
DELETE /api/v1/graph/concepts/tracked/{concept_id}
```
