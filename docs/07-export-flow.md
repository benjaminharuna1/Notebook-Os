# Export — Flow & Design

How a project leaves the app. Covers the layered design, the runtime path from a click to a saved
file, and the rules the shape is built to enforce.

---

## 1. What it is

Two project resources. `dossier` comes as Word or Excel; `references` also comes as RIS — the format a
reference manager imports directly. A third, session-scoped resource — `conversation` — exports one
saved chat session as Word:

| Resource | Formats | What the researcher gets |
|---|---|---|
| **dossier** | `docx`, `xlsx` | `docx`: cover page (what is missing), references, per-paper reading notes. `xlsx`: three sheets — `Summary`, `Paper notes`, `References` — mirroring those sections |
| **references** | `ris`, `docx`, `xlsx` | `ris`: one RIS record per paper, importable into Zotero/Mendeley/EndNote. `docx`: the APA list. `xlsx`: one row per reference: Authors / Year / Title / Source / DOI / APA / Missing metadata / Provenance |
| **conversation** | `docx` | One saved chat session: title, project, date and message count; the questions and answers in order; under each answer the sources it rested on, with a citation to a since-deleted document kept and marked |

Two properties are deliberate and load-bearing:

- **Offline.** No network, no LLM, no second process. SQLite in, bytes out.
- **The project resources contain documents only.** The dossier and references never read `chat_*`, so a
  saved conversation or answer cannot appear in them. A conversation is exported only through its own
  resource, where a citation whose document is gone is preserved and marked (`not in this project any
  more`) rather than dropped.

And two about the entry list itself, because the file has to be usable as a bibliography:

- **One entry per paper, never fewer.** A project of N papers exports N entries even when two of
  them describe the same work.
- **Every reference file states what it contains** — the project, the generation date and the entry
  count.

---

## 2. Where it sits

```
backend/app/
├── core/
│   ├── citations.py            # single definition of in-text citation + APA 7th reference
│   ├── papers.py               # single definition of how a documents row yields authors
│   └── titles.py               # single definition of title capitalisation
└── features/export/
    ├── router.py               # GET endpoints, ?format=docx|xlsx (conversation: docx)
    ├── snapshot.py             # reads SQLite; every honesty rule lives here
    ├── conversation.py         # one session: build + render_docx
    ├── sheets.py               # shared openpyxl sheet formatting
    ├── dossier.py              # render_docx + render_xlsx
    │                           #   (Summary / Paper notes / References)
    ├── references.py           # bibliography: compile + table + docx/xlsx renderers
    └── tests/test_export.py

frontend/src/lib/features/export/
├── api.ts                      # exportDossier() / exportReferences() / exportConversation()
└── components/ExportMenu.svelte # mounted on the Literature and Library pages
                                # conversation buttons live in ChatWindow.svelte (header)
                                # and Sidebar.svelte (per-session row)
```

Dependencies point one way: **nothing downstream ever queries, nothing upstream ever formats.**

---

## 3. Design flow

```
Svelte    ExportMenu.svelte  ──▶  features/export/api.ts
                                        │  downloadFile()
                                        ▼
HTTP      router.py               validate format · refuse empty project ·
                                  own media type + filename
                                        │
                                        ▼
Build     snapshot.py             read SQLite · apply the honesty rules ONCE
                                        │
Organise  references.compile()    de-duplicate · sort · flag incomplete
                                        │
Render    dossier.render_* / references.render_*                → bytes
                                        │
Deliver   Response  →  blob  →  saved file  →  toast
```

### Layer responsibilities

| Layer | Owns | Explicitly does not |
|---|---|---|
| **UI** (`ExportMenu.svelte`, `api.ts`) | Which resource and format the researcher picked | Know about papers, SQL, filenames |
| **Transport** (`router.py`) | Routing, auth, format validation, the empty-project refusal, media type + `Content-Disposition` | Build any content |
| **Snapshot** (`snapshot.py`) | The only database read; the only place missing data is interpreted | Render anything, or depend on other features |
| **Compilation** (`references.compile`) | Turning papers into a de-duplicated, sorted bibliography | Touch the database or a file format |
| **Renderers** (`dossier.py`, `references.py` — each exposes `render_docx` and `render_xlsx`) | Snapshot → bytes, in one format each | Query, decide policy, or import another feature |
| **Foundation** (`core/citations.py`, `core/papers.py`, `core/titles.py`) | How a citation is spelled; how a row yields authors; how a title is capitalised | Know about export at all |
| **Sheet plumbing** (`sheets.py`) | What an export sheet looks like (header band, freeze, widths, wrap) | Know what any column means |

---

## 4. Runtime flow

**1. Trigger.** `ExportMenu` renders two rows (Dossier, References), each with a Word and an Excel
button. A click calls `exportDossier()` / `exportReferences()` in `features/export/api.ts`, which
builds `/projects/{id}/export/{resource}?format={fmt}`.

**2. Download plumbing.** `downloadFile()` in `core/api/client.ts` — the single place that calls
`fetch` for downloads. It attaches the JWT header and cookies, redirects to `/auth/login` on a 401,
and on any other error parses `{detail}` and throws it, so a backend refusal reaches the user
verbatim. On success: blob → temporary anchor → save, and it returns the filename for the toast.

**3. Endpoint.** `router.export_dossier` / `router.export_references` / `router.export_conversation`.
`format` is `Literal["docx","xlsx"]` (conversation: `Literal["docx"]`), so a bad value is rejected by
FastAPI before any work happens. The conversation endpoint builds its own `conversation.build()` and
404s a session the user does not own, 400s an empty one.

**4. Snapshot.** `snapshot.build(db, user_id, project_id)`:
- reads the project name;
- checks `PRAGMA table_info(documents)` to learn which paper columns exist — the literature feature
  adds several via migrations, so a project that never opened the Literature page lacks them;
- selects the project's PDF documents ordered by title, and builds a `Paper` each: authors (via
  `core.papers.authors_from_row`), `missing_fields`, `provenance`, `citation`, and `apa_reference`;
- **normalises the title** via `core.titles.title_case` — standard Title Case, repairing a title
  written entirely in caps — and uses that one title for the reference list, the title column and
  the reading notes alike;
- **the APA string** is the stored `documents.apa_reference` when present (written by literature
  enrichment or a user edit) — with its embedded title repaired in place, so an older reference
  stored while the title shouted does not keep shouting — otherwise derived on the fly via
  `core.citations.apa_reference()`;
- raises a 400 — *"This project has no papers to export yet."* — if there are no papers.

**5. Compile** (references only). `references.compile(snapshot)` — see §5.

**6. Render.** The resource module's renderer for the requested format: `dossier.render_docx` /
`dossier.render_xlsx`, `references.render_ris` / `references.render_docx` / `references.render_xlsx`.

All of them are CPU-bound and run inside `run_in_threadpool`, so the event loop stays free.

**7. Deliver.** Bytes plus the matching media type and
`Content-Disposition: attachment; filename="{project-slug}-{resource}.{ext}"`.

**8. Feedback.** A success toast names the saved file; failures surface the backend message.

---

## 5. The reference compile

`references.compile(snapshot)` is the shared step behind the standalone references export, its RIS
form, and the dossier's own reference section:

1. **one `Reference` per paper — never fewer**, so a project of N papers exports N entries even when
   two describe the same work. De-duplicating was tried and removed: it made the entry count disagree
   with what the researcher sees;
2. **sort** alphabetically by APA string, case-insensitively;
3. mark `complete = bool(authors)`;
4. expose `fields` — the attribution with each missing value placeholdered (see §6);
5. expose `gap` — the missing fields, or the provenance when there are none.

`Reference.gap` exists because the two artifacts once described the same gap differently
("never enriched" versus "authors, year, doi, journal"). There is a test pinning that they agree:
`test_dossier_and_references_export_describe_the_gap_identically`.

Rendering:

- **RIS** — one record per paper, always the same field order: `TY` (from `paper_type`, default
  `JOUR`), one `AU` per author, `PY`, `TI`, `JO`, optional `DO`, then the `ER  -` terminator. A
  missing attribution value is written as a placeholder rather than omitted, so entries stay uniform
  — except `DO`, which is dropped, because a manager would store `No DOI` as a literal DOI. The file
  opens with `#` header lines carrying the project, date and entry count; RIS has no comment syntax
  of its own, so that is a widely-supported convention.
- **Word** — complete entries first as hanging-indent numbered paragraphs; the rest under a level-2
  *"References with incomplete metadata"* heading, each with an italic `Incomplete: <gap>` note. The
  header line states the generation date and the entry count.
- **Excel** — one row per reference, complete or not, with the gap and the provenance in the last two
  columns, and a `Summary` sheet carrying the project, the date and the entry count. Nothing is
  dropped for being incomplete.

---

## 6. Design rules

- **One snapshot, many renderers.** A new artifact is a new renderer over an existing snapshot — no
  new query, no new endpoint family.
- **Honesty resolved once.** Markers and provenance are decided in the snapshot, so the Word and
  Excel forms cannot disagree about the same paper.
- **Single definition per concept.** APA in `core.citations`; authors in `core.papers`; title
  capitalisation in `core.titles`; the bibliography in `references.compile`; gap wording in
  `Reference.gap`; downloads in `downloadFile`.
- **One capitalisation plan.** A title is title-cased once, in the snapshot, and every artifact reads
  that same string — so a paper cannot be "DEEP LEARNING" in one place and "Deep Learning" in
  another.
- **No cross-feature imports.** The export feature reads SQLite directly rather than importing
  `literature` or `chat`, which is the architecture's hard rule (`AGENTS.md`).
- **Format is a parameter, not a code path** — two endpoints with `?format=`, not four endpoints.
- **Refuse, don't mislead.** An empty project is a 400, never a header-only spreadsheet that looks
  like it worked.

### Title capitalisation

Standard Title Case, applied to every reference title and every paper title in the artifacts:

| Input | Output |
|---|---|
| `deep learning for crop yield prediction` | `Deep Learning for Crop Yield Prediction` |
| `a survey of quantum machine learning methods` | `A Survey of Quantum Machine Learning Methods` |
| `the state of the art` | `The State of the Art` |
| `a survey of LLM agents in education` | `A Survey of LLM Agents in Education` |
| `COVID-19 severity in small samples` | `COVID-19 Severity in Small Samples` |
| `DEEP LEARNING FOR CROP YIELD PREDICTION` | `Deep Learning for Crop Yield Prediction` |
| `ARTIFICIAL INTELLIGENCE AND AI IN HEALTHCARE` | `Artificial Intelligence and AI in Healthcare` |

The rules live in `core/titles.py`:

- the first and last word always keep their capital, even when minor;
- minor words (`of`, `for`, `in`, `the`, `and`, …) stay lowercase in between;
- acronyms, tokens containing digits (`COVID-19`) and deliberate internal capitals (`iPhone`) are
  left alone;
- a title written **entirely** in caps is repaired, because shouting carries no case information —
  every word is rebuilt, keeping only named acronyms (the `_ACRONYMS` set) and digit-bearing tokens;
- a pure acronym phrase such as `AI IN ML` is left untouched: no word is long enough to prove the
  title was prose, so guessing would be likelier to mangle it than to help.

**Not normalised:** journal / venue names. They are container titles with their own conventions and
are far more likely to be legitimately stylised, so they are emitted as stored.

### Honesty vocabulary

Two vocabularies, for two different jobs — a citation has to look like a citation, a field has to
label itself.

A missing *attribution field* (`Reference.fields`, read by RIS, Word and Excel alike):

| Field | Placeholder |
|---|---|
| authors | `Unknown author` |
| year | `No date` |
| title | `Untitled` |
| source (venue) | `Unknown source` |
| doi | `No DOI` |

A *derivation* the app could not make:

| Situation | What the researcher sees |
|---|---|
| No author, so no citation can be built | `(author unknown)` instead of a fabricated `Title, n.d.` |
| Field never generated | `not generated yet` |
| Field generated but blank | `empty` |
| Field cleared by the user | `cleared by you` |
| Metadata never enriched | `never enriched` (provenance: `verified` / `ai-suggested` / `edited by you`) |
| Citation's document deleted after the chat | the captured citation label, kept and marked `not in this project any more`, and counted on the report's cover |

The workbooks carry a `Provenance` column and a `Missing metadata` column, so the metadata's
reliability travels with the data rather than living only in the prose. The column named `Source` in
the reference sheet is the publication venue — the "source" of the ticket's four attribution fields.

---

## 7. Decisions, and what was rejected

The design comes from `docs/proposals/export-approaches.md`. Three candidates were compared:
server-side snapshot + thin renderers, client-side generation in JavaScript, and data-only export
(BibTeX/JSON). The snapshot approach won because the honesty rules already live in the data model and
must be enforced in the one layer that reads it — building them in the browser would mean
reimplementing them where the data is thinnest, twice over two formats.

**Deliberately rejected: print-perfect PDF.** A headless Chromium or pandoc dependency would add
hundreds of megabytes to an app whose premise is small, offline and CPU-only, and would be the least
likely thing to work on the low-end hardware the app targets. The `.docx` opens in Word or
LibreOffice, either of which exports PDF in one built-in step.

**Changed after approval:** the Export control lives on the Literature and Library pages rather than
the project header. Conversations were first removed from the export entirely; they are now exported
through their own session-scoped `conversation` resource, which reinstates the deleted-document rule
from §8 (see the review note at the top of `export-approaches.md`).

---

## 8. Tensions, and how they were resolved

Three real tensions were identified in this design and then fixed rather than left as caveats:

| Tension | Resolution |
|---|---|
| `workbook.py` rendered the dossier as xlsx while `dossier.py` rendered it as docx — asymmetric naming, and unlike `references.py`, which kept both formats in one module. | **One module per resource.** `dossier.py` now exposes `render_docx` and `render_xlsx`; `workbook.py` is gone. The router's dispatch is now identical for both endpoints. |
| The dossier's Excel form was a bare per-paper matrix while its Word form was a document — two different things under one name. | **The Excel dossier is the dossier.** It is a three-sheet workbook — `Summary`, `Paper notes`, `References` — mirroring the Word sections one-for-one. The per-paper matrix survives intact as the `Paper notes` sheet. |
| The snapshot is a **second read path** over tables the services also read, so the two can drift. | **Shared the part that can actually diverge:** `core/papers.authors_from_row` is now the single definition of how a `documents` row yields authors, used by both `literature` and `export`. |

The failure mode the last fix prevents is not hypothetical: extracting that function immediately
broke three literature tests, because the old export copy returned early on the common
`authors = '[]'` case and skipped the `documents.author` fallback. One definition makes that class of
bug impossible rather than merely unlikely.

What remains, honestly:

- The snapshot still reads `documents` itself rather than going through a shared repository, because
  features must not import each other. It is pure-read, and every field it interprets now comes from
  a shared definition.
- Sheet styling lives in `sheets.py`, so a new column means touching two places (the rows in
  `dossier.py`/`references.py` and the widths list). Acceptable for a fixed, small set of columns.

---

## 9. Verification

```bash
cd backend && .venv\Scripts\python.exe -m pytest -q      # full suite
cd backend && .venv\Scripts\python.exe -m pytest app/features/export -q
cd frontend && npm run build
```

Worth keeping green:

| Test | Guards |
|---|---|
| `test_router_serves_both_resources_in_both_formats` | The resource × format matrix, media types, filenames |
| `test_router_refuses_project_without_papers` | The 400 instead of an empty file |
| `test_references_compile_is_one_per_paper_and_sorted` | N papers → N entries, duplicates included |
| `test_ris_lists_one_record_per_paper_in_a_consistent_field_order` | RIS structure and uniform field order |
| `test_ris_marks_every_missing_field_with_a_placeholder` | RIS never emits a blank or fabricated value |
| `test_reference_sheet_cells_are_never_blank` | Same rule for the spreadsheet |
| `test_every_reference_file_states_project_date_and_entry_count` | The file says what it contains, in all three formats |
| `test_router_serves_references_as_ris` | RIS reachable over HTTP with the right media type |
| `test_missing_author_is_marked_not_fabricated` | The honesty rule that matters most |
| `test_three_blank_states_are_distinguished` | `not generated yet` vs `empty` vs `cleared by you` |
| `test_dossier_carries_the_same_sections_in_both_formats` | Word and Excel stay the same document |
| `test_dossier_and_references_export_describe_the_gap_identically` | No drift between artifacts |
| `test_references_repair_an_all_caps_title` | Shouting titles are repaired, not published |
| `test_references_repair_a_shouting_title_already_stored_in_the_reference` | Older stored references get fixed too |
| `test_dossier_never_includes_conversations` | Documents-only, enforced not just assumed |
| `test_conversation_export_includes_questions_and_answers` | The session report carries the transcript and its citations |
| `test_conversation_export_marks_citation_to_deleted_document` | The R3 rule: a citation to a deleted document is kept and marked, not dropped |
| `test_router_refuses_empty_conversation` | An empty session is a 400, not an empty file |
| `test_router_404s_for_missing_conversation` | A session is exported only by its owner |
| `test_dossier_xlsx_notes_sheet_keeps_the_historical_column_order` | Existing users' columns don't move |
