# export — getting the researcher's work out of the app

One job: read a project into an export snapshot and render it as the two artifacts the researcher
takes away. Read-only, offline, no LLM, no network.

## Inputs

| Input | Source | Notes |
|---|---|---|
| project_id | URL param | Scope to project |
| include_answers | Query param (dossier only) | Include saved chat answers |
| user_id | JWT | `get_current_user` |

## Process

1. **Snapshot** — `snapshot.build()` reads SQLite directly (documents, literature_entries,
   chat_sessions, chat_messages). No other feature is imported.
2. **Honesty pass** — missing metadata, the three blank states, and citations to deleted documents
   are resolved into explicit markers during snapshot assembly, so both renderers inherit them.
3. **Render** — `workbook.render()` and `dossier.render()` walk the same snapshot.
4. **Refuse empties** — a project with no papers is a 400, never a header-only file.

CPU-bound rendering is pushed off the event loop with `run_in_threadpool` (as `models/router.py` does).

## Outputs

| Output | Type | Notes |
|---|---|---|
| Snapshot | `Snapshot` dataclass tree | Papers + provenance, sessions + sources, unresolved list |
| Literature workbook | Binary (`.xlsx`) | 14 columns; adds Authors/Year/DOI/Journal + `Missing metadata` + `Source` to the previous 8 |
| Project dossier | Binary (`.docx`) | Cover page stating what is missing, references, paper notes, optional answers |

## Key files

| File | Purpose |
|---|---|
| `snapshot.py` | Snapshot assembly + every honesty rule |
| `workbook.py` | `.xlsx` renderer (openpyxl) |
| `dossier.py` | `.docx` renderer (python-docx) |
| `router.py` | Two GET endpoints, both returning a binary attachment |

## Honesty rules (the point of this feature)

- A paper with no recorded author exports as `(author unknown)`, never as a fabricated
  `Title, n.d.` citation.
- Provenance (`verified` / `ai-suggested` / `edited by you` / `never enriched`) is a column, from
  `verification_status` and `metadata_user_edited`.
- The three blank states are distinguished: `not generated yet`, `empty`, `cleared by you`.
- A source whose document was deleted keeps the citation captured at answer time and is marked
  `not in this project any more`, counted on the dossier's cover page. It is never silently dropped.
- The dossier's `References` section carries only complete references; papers with incomplete
  metadata are listed separately as `References with incomplete metadata`.

## Dependencies

`app.core.citations` — the single definition of the in-text citation and APA 7th-edition reference
(shared with `literature`). `documents`/`literature_entries` columns added by the literature
feature's migrations are detected via `PRAGMA table_info`, so a project that never opened the
literature page still exports.

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports: `grep -r "from app.features" app/features/export/` finds only `export`
  importing itself
- Export a project with an unenriched paper and confirm the workbook says why
