# API Contract — Auth, Projects, Ingestion, Documents

All endpoints are prefixed with `/api/v1`. All endpoints (except auth) require JWT authentication via cookie or header.

## Auth

```
POST /api/v1/auth/register
  Body: { email: string, username: string, password: string }
  Response: { token: string, user: { id, email, username } }

POST /api/v1/auth/login
  Body: { identifier: string, password: string }
  Response: { token: string, user: { id, email, username } }
  Sets: HttpOnly access_token cookie

POST /api/v1/auth/logout
  Clears access_token cookie
  Response: { success: true }

GET /api/v1/auth/me
  Response: { id, email, username }
```

## Projects

```
POST /api/v1/projects
  Body: { name: string, description?: string }
  Response: Project { id, name, description, created_at, updated_at }

GET /api/v1/projects
  Response: { projects: Project[] }

GET /api/v1/projects/{project_id}
  Response: Project

PATCH /api/v1/projects/{project_id}
  Body: { name?: string, description?: string }
  Response: Project

DELETE /api/v1/projects/{project_id}
  Response: { success: true }
```

## Ingestion

```
POST /api/v1/ingest/file
  Content-Type: multipart/form-data
  Body: { file: File, project_id?: string }
  Response: { document_id: string, status: "processing", estimated_time: number }

GET /api/v1/ingest/status/{document_id}
  Response: { document_id: string, status: "pending"|"processing"|"indexed"|"failed"|"paused", progress: number, error?: string }

POST /api/v1/ingest/{document_id}/pause
POST /api/v1/ingest/{document_id}/resume
POST /api/v1/ingest/{document_id}/reprocess

POST /api/v1/ingest/reprocess
  Body: { document_ids: string[] }
  Response: { success: true, processed: number, errors: [] }
```

## Documents

```
GET /api/v1/documents
  Query: ?page=1&limit=20&search=string&file_type=string&project_id=string
  Response: { documents: Document[], total: number, page: number, pages: number }

GET /api/v1/documents/{document_id}
  Response: Document (full metadata + chunk_count)

DELETE /api/v1/documents/{document_id}
  Response: { success: true }

POST /api/v1/projects/{project_id}/documents/batch/delete
  Body: { document_ids: string[] }

GET /api/v1/projects/{project_id}/documents/{document_id}/file
  Response: FileResponse (PDF/DOCX/etc)

GET /api/v1/projects/{project_id}/documents/orphans
POST /api/v1/projects/{project_id}/documents/clean-orphans
```
