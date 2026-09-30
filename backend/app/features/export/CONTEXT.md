# export — getting the researcher's work out of the app

One job: read a project into an export snapshot and render it as the artifacts the researcher
takes away. Read-only, offline, no LLM, no network. Documents only — saved conversations and
answers are deliberately never part of an artifact.

## Inputs

| Input | Source | Notes |
|---|---|---|
| project_id | URL param | Scope to project |
| format | Query param | `docx` or `xlsx` |
| user_id | JWT | `get_current_user` |

## Process

1. **Snapshot** — `snapshot.build()` reads SQLite directly (documents, literature_entries). No other
   feature is imported, and `chat_*` tables are never read.
2. **Honesty pass** — missing metadata and the three blank states are resolved into explicit markers
   during snapshot assembly, so every renderer inherits them.
3. **Render** — the resource's renderer for the requested format walks the same snapshot.
4. **Refuse empties** — a project with no papers is a 400, never a header-only file.

CPU-bound rendering is pushed off the event loop with `run_in_threadpool` (as `models/router.py` does).

## Outputs

Two resources, each available as Word or Excel:

| Resource | `format=docx` | `format=xlsx` |
|---|---|---|
| **dossier** | Cover page stating what is missing, references, paper notes | Three sheets — `Summary`, `Paper notes`, `References` — mirroring those sections |
| **references** | The compiled APA bibliography, complete entries first, in a hanging-indent list | One row per reference with Authors/Year/Title/Journal/DOI/APA + its gaps |

Plus the shared `Snapshot` dataclass tree — papers + provenance and the unresolved list.

`references.compile()` is the single definition of the bibliography (de-duplicated, sorted
alphabetically, incomplete entries flagged) and `references.table()` the single definition of its
sheet layout, both used by the standalone export and the dossier alike.

## Key files

| File | Purpose |
|---|---|
| `snapshot.py` | Snapshot assembly + every honesty rule |
| `references.py` | APA bibliography: `compile`, `table`, and both renderers |
| `dossier.py` | `render_docx` + `render_xlsx` for the project write-up |
| `sheets.py` | Shared openpyxl sheet formatting |
| `router.py` | Two GET endpoints, `?format=docx\|xlsx`, returning a binary attachment |

## Honesty rules (the point of this feature)

- A paper with no recorded author exports as `(author unknown)`, never as a fabricated
  `Title, n.d.` citation.
- Every title is title-cased once, in the snapshot, via `core.titles.title_case` — standard Title
  Case, with a title written entirely in caps repaired rather than published. The reference list, the
  title column and the reading notes all read that one string. A title already embedded in a stored
  reference is repaired in place. Journal / venue names are left as stored.
- Provenance (`verified` / `ai-suggested` / `edited by you` / `never enriched`) is a column, from
  `verification_status` and `metadata_user_edited`.
- The three blank states are distinguished: `not generated yet`, `empty`, `cleared by you`.
- Because exports contain documents only, the surviving-document caveat is structural rather than
  cosmetic: every reference in an artifact points at a paper that is in the project at export time,
  so no artifact can contain a citation to a deleted document.
- The bibliography accounts for *every* paper. Entries are never dropped because they are
  incomplete; the complete ones come first and the rest follow under
  `References with incomplete metadata`, labelled with what is missing.

## Dependencies

`app.core.citations` — the single definition of the in-text citation and APA 7th-edition reference
(shared with `literature`). `app.core.papers.authors_from_row` — the single definition of how a
`documents` row yields authors (also shared with `literature`, so the two cannot drift).
`app.core.titles.title_case` — the single definition of title capitalisation (also used by
`literature` when it stores enriched metadata).
`documents`/`literature_entries` columns added by the literature feature's migrations are detected
via `PRAGMA table_info`, so a project that never opened the literature page still exports.

## Human check

- All tests pass: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- No cross-feature imports: `grep -r "from app.features" app/features/export/` finds only `export`
  importing itself
- Export a project with an unenriched paper and confirm the workbook says why
- Export the references as Word and as Excel and confirm both list the unenriched paper
