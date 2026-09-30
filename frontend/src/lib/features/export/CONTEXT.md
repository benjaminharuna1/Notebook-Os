# Export Feature Contract

Exporting a project out of the app — two resources, each in Word or Excel.

## What it does

Provides one `ExportMenu` mounted on the **Literature** page and the **Library** page (via
`DocumentList`), replacing the single-format export buttons that used to sit on each. It offers two
project resources, each with a Word and an Excel button:

| Resource | Word | Excel |
|---|---|---|
| **Dossier** | Cover page, references and paper notes | The literature matrix, one row per paper |
| **References** | The compiled APA bibliography | One row per reference, with its gaps |

A **conversation** report is a session-scoped third resource, offered where the session lives rather
than in the project menu: a download control in the chat header (`ChatWindow.svelte`) and a hover icon
on each session row in `Sidebar.svelte`. It exports the current session as Word.

Both project downloads and the conversation download go through the shared `downloadFile()` helper in
`core/api/client.ts`, so auth headers, the 401 redirect, and the `Content-Disposition` filename are
handled in one place.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/projects/{id}/export/dossier?format=docx\|xlsx` | GET | Dossier |
| `/projects/{id}/export/references?format=docx\|xlsx` | GET | Compiled APA bibliography |
| `/projects/{id}/export/conversation/{session_id}?format=docx` | GET | One saved chat session |

## State managed

No store — the menu holds local `$state` for open/busy.

## Special patterns

- **Downloads**: the export functions return the saved filename, which the menu surfaces in a
  success toast
- **Busy state**: one spinner behind the trigger, and every format button disabled, while any
  export is in flight
- **Refusals**: the backend answers a paper-less project with a 400 whose detail is shown verbatim
  as an error toast
