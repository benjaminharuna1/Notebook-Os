# Export Proposal — Getting the Researcher's Work Out of the App

**Status:** draft proposal — awaiting reviewer assignment and approval. FRTR-001 delivers this document only; the implementation proceeds under its own ticket once this is approved.
**Reviewer:** _unassigned_ — **name the approver here.** Until a person owns it, the gate cannot be satisfied. Sign-off is required before the implementation begins (see §13).
**Scope:** the whole sprint's export work. Every later export ticket implements what this document decides.
**Decision up front:** one server-side **Export Snapshot** assembled from SQLite, rendered on demand by thin
per-format writers, delivered as **two** artifacts — a **reference list** and a **session report** — plus a
project dossier that reuses the same reference list. No new dependencies. No network. No PDF pipeline.

> **The design covers both artifacts.** An earlier revision removed saved conversations from every
> artifact and deleted the §8 deleted-document rules, then wrote the omission into the contract
> ("documents only"). That contradicted the sprint's R3, which names two artifacts: a reference list and
> a session report. This proposal therefore designates the chat half as its own **conversation** resource
> — a session-scoped `.docx` report — with the deleted-document rule in force: a citation whose document
> is gone is kept, marked *not in this project any more*, and counted on the report's cover.
>
> **One placement decision.** The Export control lives on the Literature and Library pages rather than the
> project header.

**Core decision** — the snapshot, the renderers, and the deliberate rejection of a PDF pipeline — stands as
written.

---

## 1. The problem

**What this ticket delivers:** a written proposal a reviewer can read and approve in one sitting. It is the
sprint's first deliverable and its gate — every export ticket after this one implements what it decides.
Implementation is out of scope here (§10).

Everything the researcher produces inside NARA currently stays inside NARA. Today she can
get exactly one slice of her work out: the literature mapping. Her chat answers, her per-paper readings, the
citations those answers rest on, and every piece of provenance behind them are trapped in the app.

The goal of this sprint is that the researcher can walk away with her work. This document decides how.

---

## 2. What exists today

Not nothing. Two working exports, both literature-scoped, both already offline:

| What | Where | Emits |
|---|---|---|
| Literature workbook | `GET /projects/{id}/literature/export` → `literature/router.py:214` → `service.py:683` | `.xlsx`, 8 columns, openpyxl, in-memory `BytesIO` |
| APA reference list | `GET /projects/{id}/literature/references/export.docx` → `literature/router.py:237` → `service.py:739` | `.docx`, sorted + de-duplicated references, python-docx |

and on the frontend, both reach the researcher as a browser download via a blob URL
(`literature/api.ts:158` and `:197`) — triggered from **two different screens**:

- `.xlsx` — Literature tab, `exportExcel()` (`routes/projects/[id]/literature/+page.svelte:238`)
- `.docx` — project Documents list, `handleExportReferences()` (`documents/components/DocumentList.svelte:373`)

### What this tells us

1. **The mechanics are solved and proven.** Authenticated GET → in-memory render → `Content-Disposition`;
   the frontend already downloads it correctly in both the web build and the desktop shell.
2. **Nothing else is exportable.** Chat sessions, chat answers with their citations, per-paper metadata
   (DOI, journal, authors, year), literature entries, the knowledge graph, and project memory have no path out.
3. **Discovery is inconsistent.** Two artifacts, two different screens, two different names. The researcher has
   to know where each one hides.
4. **`verification_status`, `metadata_user_edited`, and `auto_generated` are in the schema but not in the
   export.** The information needed to be honest about data quality is stored and then thrown away.
5. **Two concrete defects** in the current path: the export endpoints are `async def` but call CPU-bound
   openpyxl/python-docx work inline, blocking the event loop (cf. `models/router.py`, which uses
   `run_in_threadpool`); and an empty project happily downloads a header-only spreadsheet rather than saying so.

---

## 3. Candidate approaches

### Approach A — Server-side snapshot + thin renderers

One backend module builds a single normalized **Export Snapshot** from SQLite: project, papers with full
metadata and provenance, literature entries, references, chat sessions with answers and their source
citations. Read-only, no network, no LLM. Then each output format is a small renderer that walks the same
snapshot: the `.xlsx` writer and the `.docx` writer, both using libraries already in
`backend/requirements.txt` (openpyxl, python-docx).

### Approach B — Client-side generation in the browser

The frontend fetches JSON it already has and builds the files in JavaScript with browser libraries
(`docx`, `xlsx`, `jspdf` from npm).

### Approach C — Data-only export

Emit interoperable data instead of documents: `BibTeX`/`RIS` for references, `CSV`/`JSON` for the matrix,
`Markdown` for transcripts. The researcher imports them into Zotero, a reference manager, or a script.

---

## 4. The four criteria

### 4.1 Works fully offline on low-end hardware

| | Verdict |
|---|---|
| **A** | Passes. Snapshot reads SQLite; renderers are pure Python in-process. openpyxl and python-docx are already installed. No network, no second process, no browser engine. Cost is CPU + RAM for one file at a time. |
| **B** | Passes on offline, fails on low-end. Adds npm document libraries to the shipped bundle, and generation runs in the WebView on the same machine — so the peak cost lands in the renderer alongside the UI, on exactly the machine least able to spare it. |
| **C** | Passes best. Text serialization is the cheapest possible path, and the output is re-importable anywhere. |

Note the one place network appears today: `LiteratureService.status()` probes Crossref to warn about missing
metadata. Export must never consult it, and must degrade cleanly when the machine never has been online —
metadata in the snapshot is whatever is already in SQLite.

### 4.2 Honest output when data is missing

| | Verdict |
|---|---|
| **A** | **Passes, and this is the decisive advantage.** All provenance signals (`verification_status`, `metadata_user_edited`, `auto_generated`, the three-state blank vs. generated vs. edited) live in SQLite and are already read into service-layer dicts. Honesty is enforced in one place, in Python, before any renderer runs — so it cannot drift between artifacts. |
| **B** | Fails. The honesty rules would have to be reimplemented in TypeScript. Two implementations of "what a missing author looks like" is two chances to disagree, and the JS one would have no access to `verification_status` unless the API is widened for it. |
| **C** | Partial. Data formats have no room for a cover-page notice or an inline marker, but they do have room for fields — provenance can be a column. Still leaves the researcher to interpret what she got. |

The specific danger today, in both existing writers: `auto_citation()` (`service.py:375`) falls back to the
**first 30 characters of the title plus `n.d.`**, and `apa_reference()` (`service.py:1144`) emits
`Title (n.d.).` when there are no authors. Those are not placeholders — they look like real citations. A paper
whose metadata was never enriched exports as `Deep Learning Survey, n.d.`, which reads as a real undated work
rather than "we don't know who wrote this." Approach A is the only option that fixes this once, centrally.

### 4.3 Stays maintainable as the app grows

| | Verdict |
|---|---|
| **A** | Best. Two seams only: the snapshot, and each renderer. A new artifact (say, a graph export) is a new renderer over an existing snapshot — not a new query, not a new endpoint family, not duplicated honesty logic. Snapshot is built by reading SQLite directly, so the export feature does **not** import other features (the architecture's hard rule) — one extraction is required, see §9. |
| **B** | Worst. Every future artifact needs a JS implementation living in the frontend, far from the Python that knows what the data means. Twelve features × N formats of drift. |
| **C** | Cheap per artifact, but every new need is a new format and a new exporter, and the researcher still has to do the assembly herself. Cheap to add, expensive to use. |

### 4.4 What the researcher actually receives

| | Verdict |
|---|---|
| **A** | Best. A workbook she filters and sorts, and a document she can paste straight into a thesis chapter, with the caveats written on its own cover page. |
| **B** | Same artifacts in principle, but a browser-generated `.docx` will not match Word's own layout and cannot be spot-checked in CI. |
| **C** | Weakest. `.bib` into Zotero is genuinely useful for references — but nothing in a JSON or CSV transcript answers "what did I conclude about these papers." It moves the problem rather than solving it. |

---

## 5. Decision

**Approach A.** One snapshot, thin renderers, two `.docx`/`.xlsx` artifacts, no new dependencies.

It is the only candidate that passes all four criteria, and the reason is structural rather than aesthetic:
the honesty logic already exists in the data model and has to be enforced exactly once, in the layer that
reads the database. Building it in the browser would mean reimplementing it where the data is thinnest.

It also aligns with how this app already works. Offline-first, in-process, CPU-only, small dependencies,
CPU-bound work pushed off the event loop — that is the established pattern. Approach A extends the proven
export path; it does not introduce a new one.

---

## 6. The trade-off deliberately not taken

**We are not building print-perfect PDF export.** No headless Chromium, no pandoc, no WeasyPrint.

Taking PDF would mean either bundling a browser engine (hundreds of megabytes, against the entire premise of
shipping a small CPU-only desktop app) or shelling out to an external binary that may not exist on the
researcher's machine — which breaks "fully offline on low-end hardware" for the single most visible artifact
in the sprint. It would also force a second layout implementation to keep in sync with the `.docx` writer.

What she gets instead: the `.docx`, which Word and LibreOffice both turn into a PDF with one built-in command
she already knows. We are choosing to leave that last step to software that is already on her machine rather
than to add a heavyweight dependency to ours.

This is the trade-off being made consciously. If a reviewer disagrees, the cost arrives as a new renderer
inside the same snapshot architecture — which is exactly why the decision is affordable to revisit.

---

## 7. What the researcher gets

The sprint names **two artifacts**. Both are what she will walk away with; a third, the project dossier,
is planned alongside them.

### Artifact 1 — Reference list (`references`)

- **What she will receive:** the compiled APA bibliography — one entry per paper, never fewer, sorted
  alphabetically, complete entries first and the rest under *References with incomplete metadata*.
  She picks the format: **RIS** (imports straight into Zotero/Mendeley/EndNote), **Word** (the APA
  list), or **Excel** (one row per reference with its gaps and provenance). Every file states its
  project, generation date and entry count.
- **Where she starts:** the Export control on the Literature page or the Library page (`ExportMenu`),
  then the References row.
- **While it runs:** the trigger shows an inline spinner and is disabled; a success toast names the
  file.
- **When it fails:** the reason in a toast, verbatim; a partial file is never delivered.

### Artifact 2 — Session report (`conversation`)

- **What she will receive:** one saved chat session as a Word document — the session title, project,
  export date and message count; the questions and answers in order; and, under each answer, the
  sources it rested on. A citation whose document was deleted after the chat is kept, marked
  *not in this project any more*, and counted on the cover.
- **Where she starts:** the chat itself — an **Export** control in the chat header, or the download
  icon on the session's row in the sidebar. The report is session-scoped, so it starts where the
  session is rather than in the project Export menu.
- **While it runs:** the control shows an inline spinner and is disabled; a success toast names the
  file.
- **When it fails:** the reason in a toast, verbatim; an empty conversation is refused with an
  explanation rather than answered with an empty file.

### Also planned — Project dossier (`dossier`)

Not one of the sprint's two artifacts, but offered from the same Export control: the project write-up —
cover page (what is missing), the same compiled reference list, and the per-paper notes — as Word or
Excel. It reuses Artifact 1's compilation, so the dossier and the reference list can never disagree
about a reference.

### One honest guard on each

Exporting a project with no papers — or a conversation with no messages — is refused with an
explanation, never answered with an empty file. (Historically the `.xlsx` route silently produced a
header-only sheet, which is worse than a message because it looks like it worked.)

---

## 8. Honest output rules

This is the section the sprint is really about.

**Missing metadata.** A missing field must never be disguised as a plausible value.

- No fabricated identity. Where `auto_citation()` would currently invent `Title[0:30], n.d.`, the cell is
  marked as missing and the `Source` column says why. Same for `apa_reference()`'s `Title (n.d.).`
- Every row carries provenance from `verification_status` (`verified` / `ai` / `unverified`) plus
  `metadata_user_edited`, so a citation the AI guessed is never presented like one Crossref confirmed.
- **The three blank states are distinguished.** Today, "not generated yet", "generated as empty", and
  "you cleared this field" are all one blank cell. The dossier labels each: *not generated*, *empty*,
  *cleared by you*.
- The dossier's cover page states the unresolved count, so the caveats are readable before the content.

**Citations to deleted documents.** Deleting a document hard-deletes its literature entry and its
references (`documents/repository.py:50`), and the citation recorded in an exported chat answer was never a
foreign key — `chat_messages.sources` is a JSON blob holding a `document_id`. So a chat answer's citation can
point at a document that no longer exists, and today that citation would simply vanish from any export.

The rule: **an exported answer keeps the citation it was written with.** At answer time we capture the
citation label alongside the document id in `sources`. At export time, a source whose document is gone is
rendered as its captured label with a marker — *not in this project any more* — and counted on the cover page
under unresolved items. The researcher sees what the answer rested on and that the underlying paper is no
longer in her library. Nothing is silently dropped, and nothing is invented. A source with no document id
(a web fallback) never had a project document, so it is left unmarked.

---

## 9. How this stays maintainable

- **New feature:** `backend/app/features/export/` — `snapshot.py` (assemble from SQLite), `references.py`,
  `dossier.py`, `conversation.py` (one saved session), `router.py`. It reads SQLite directly rather than
  importing `literature` or `chat`, which honours the rule that features never import from each other.
- **One extraction required:** the APA/citation formatter currently lives in `literature/service.py`
  (`auto_citation`, `apa_reference`). Export must not fork it. Move it to a feature-neutral
  `app/core/citations.py` and have `literature` import from there — one definition of APA for the whole app.
- **New artifact later:** a new renderer over the same snapshot. No new query, no new honesty logic.
- **Cost, stated plainly:** the snapshot is a second read path over tables the services already read, so it
  can drift from them. Mitigated by keeping it pure-read and snapshot-shaped, and by the shared citation
  module being the single formatter both paths use.

---

## 10. Out of scope

**Implementation of the export feature is out of scope for this ticket (FRTR-001).** This document is the
ticket's deliverable; the implementation proceeds under its own ticket once this proposal is approved.

PDF generation (§6). Changing the frontend download mechanism — it already works in the web build and the
Electron shell, and `desktop/electron/preload.js` exposes no filesystem or save-dialog API, so a native
"save as" flow would be new scope on top of the export decision. Graph and literature-map data exports.
The knowledge-graph visual. Anything requiring network.

---

## 11. Reviewer checklist (the ticket's acceptance criteria)

| # | Criterion (verbatim from the ticket) | Where it is answered |
|---|---|---|
| 01 | Compares at least two distinct candidate approaches to export, each assessed against all four criteria: works fully offline on low-end hardware; honest output when data is missing; stays maintainable as the app grows; what the researcher receives in her hands | §3, §4 |
| 02 | Chooses one approach and defends it against the comparison; explicitly names the trade-off that was deliberately not taken, and why | §5, §6 |
| 03 | Describes both artifacts from the researcher's side: what she receives for each, where she starts each export, and what she sees while it runs and when it fails | §7 — the reference list (Artifact 1) and the session report (Artifact 2) |
| 04 | States how missing metadata and citations to deleted documents will be shown honestly in the output | §8 |
| 05 | Can be read and judged in one sitting (under 15 minutes) and is approved by a reviewer before any export implementation begins | §1–§10, and the review log below |

### Status (author's self-assessment — the reviewer closes 05)

- [x] 01 — two or more distinct approaches, each assessed against all four criteria: offline/low-end, honest output, maintainable, what she receives (§3, §4)
- [x] 02 — one approach chosen and defended; the deliberately-rejected trade-off named (§5, §6)
- [x] 03 — both artifacts described from the researcher's side: what she receives, where she starts, while it runs, when it fails (§7)
- [x] 04 — missing metadata and citations to deleted documents shown honestly (§8)
- [ ] 05 — readable in one sitting (under 15 minutes) and approved by a reviewer before implementation — readable; approver _unassigned_ (see §12, §13).

If this is approved, the implementation work is: the snapshot, the reference-list and dossier renderers,
the conversation renderer, the Export control and the two conversation buttons, the `core/citations.py`
extraction, and the `run_in_threadpool` fix on the existing export routes.

---

## 12. Review log

| Step | What happened |
|---|---|
| Proposal | Approach A chosen and defended (§5); the PDF trade-off named (§6). |
| Earlier revision | Saved conversations were removed from every artifact and the §8 deleted-document rules deleted; the contract was written as "documents only". |
| Review finding | The sprint's R3 names two artifacts — a reference list *and* a session report. The earlier revision had misread it as paper-only and left the deleted-document case unaddressed. |
| Resolution | This proposal designates the chat half its own `conversation` resource and reinstates the deleted-document rule (§8); §7 describes both artifacts from the researcher's side. |
| Scope | Implementation is out of scope for FRTR-001 (§10). It proceeds under its own ticket, from a separate branch, once this proposal is approved. |
| Sign-off | **Pending** — approver _unassigned_. |

Process note: the implementation was written ahead of this approval and is parked on its own branch,
`feat/export-implementation`, unmerged. Approving the proposal here is what permits that branch to merge —
so the sequencing boundary, decision before build, is restored at the merge, and FRTR-001 ships the
proposal only.

---

## 13. Open decisions (what the review is actually deciding)

Because the code was written ahead of approval, the review is not ratifying a plan — it is deciding five
things that are still open. The implementation sits on a separate, unmerged branch, so approval is a real
choice. Each decision is reversible, and the reversal cost is stated so that rejecting one is a real option
rather than "rip out 72 files".

| # | Decision | Options | Recommendation | Cost to reverse |
|---|---|---|---|---|
| 1 | **Merge sequencing** | (a) merge proposal and implementation together; (b) ship the proposal-only PR now, and open the implementation PR from `feat/export-implementation` after approval | **(b)** — restores what criterion 05 protects | none; it is ordering, not code |
| 2 | **PDF export** | (a) keep it deferred; (b) build it — bundled converter or a ReportLab re-layout | **(a) for now**, as its own ticket | (b) is hundreds of MB or a second layout: the §6 trade-off |
| 3 | **Conversation scope** | (a) current session only; (b) all sessions in the project | **(a)** | small — an endpoint family plus a UI entry point |
| 4 | **Conversation formats** | (a) `.docx` only; (b) add `.md` / `.xlsx` | **(a)**; `ConversationFormat` is the seam | small — one new renderer per format |
| 5 | **Resource boundary** | (a) the conversation is its own resource; (b) fold it back into the dossier | **(a)** — a deleted-document citation needs a resource that can mark it | small — `conversation.py`, one endpoint, two buttons |

If the reviewer rejects any of 2–5, the change is isolated: a new module, two UI mount points, and one
core extraction. Nothing here is a one-way door.
