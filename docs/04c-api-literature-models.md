# API Contract — Literature, Models, Skills, Settings, Actions

All endpoints are prefixed with `/api/v1`. All endpoints require JWT authentication via cookie or header.

## Literature

```
GET /api/v1/projects/{project_id}/literature/status
POST /api/v1/projects/{project_id}/literature/build
GET /api/v1/projects/{project_id}/literature/jobs/{job_id}

GET /api/v1/projects/{project_id}/literature/map
  Response: { nodes: [PaperNode], edges: [PaperEdge], clusters }

GET /api/v1/projects/{project_id}/literature/entries
GET /api/v1/projects/{project_id}/literature/entries/{paper_id}
PATCH /api/v1/projects/{project_id}/literature/entries/{paper_id}
POST /api/v1/projects/{project_id}/literature/entries/{paper_id}/regenerate
POST /api/v1/projects/{project_id}/literature/entries/{paper_id}/summarize

GET /api/v1/projects/{project_id}/literature/entries/{paper_id}/metadata
PATCH /api/v1/projects/{project_id}/literature/entries/{paper_id}/metadata
POST /api/v1/projects/{project_id}/literature/entries/{paper_id}/candidates/apply

POST /api/v1/projects/{project_id}/literature/regenerate
POST /api/v1/projects/{project_id}/literature/clusters/summary

GET /api/v1/projects/{project_id}/literature/export
  Response: XLSX binary download

GET /api/v1/projects/{project_id}/literature/references/export.docx
  Response: DOCX binary download (APA references list)
```

## Models

```
GET /api/v1/models
  Response: { available: ModelConfig[], active: ModelConfig }

POST /api/v1/models/switch
  Body: { model_id: string }  // format: "provider:model_name"

GET /api/v1/models/ollama/available
  Response: { models: string[] }

GET /api/v1/models/catalog
  Response: { recommendations, presets, downloads }

POST /api/v1/models/hf/download
  Body: { key: string }
  Response: download status

GET /api/v1/models/hf/downloads
  Response: { downloads: [...] }

GET /api/v1/local/status
  Response: { ollama_running, recommended_models, ... }
```

## Skills

```
GET /api/v1/skills
  Response: { skills: [{ skill: manifest, enabled, installed_at }] }

GET /api/v1/skills/catalog
  Response: { catalog: [{ skill: manifest, installed }] }

POST /api/v1/skills/install
  Body: { skill_id: string }

POST /api/v1/skills/{skill_id}/enable
  Body: { enabled: boolean }

DELETE /api/v1/skills/{skill_id}

POST /api/v1/skills/import
  Body: SkillManifest (custom skill definition)
```

## Settings

```
GET /api/v1/settings
  Response: { settings: { device_tier, default_llm, provider, chunk_size, ... } }

PUT /api/v1/settings
  Body: { ...partial settings update }
  Response: { settings: { ... } }
```

## Actions

```
GET /api/v1/actions
  Response: { actions: [{ id, kind, title, status, progress, stage, ... }] }

POST /api/v1/actions/{action_id}/pause
POST /api/v1/actions/{action_id}/resume
```
