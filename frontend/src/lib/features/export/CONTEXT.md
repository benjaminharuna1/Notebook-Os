# Export Feature Contract

Exporting a project out of the app — two resources, each in the formats that suit it.

## What it does

Provides one `ExportMenu` mounted on the **Literature** page and the **Library** page (via
`DocumentList`), replacing the single-format export buttons that used to sit on each. Each option
carries its own list of formats:

| Resource | Formats | What she gets |
|---|---|---|
| **Dossier** | Word, Excel | Cover page, references and paper notes / the literature matrix, one row per paper |
| **References** | RIS, Word, Excel | RIS records for Zotero/Mendeley/EndNote / the APA bibliography / one row per reference with its gaps |

RIS is offered for references only — it is the format a reference manager imports.

Conversations and answers are not part of any export.

All downloads go through the shared `downloadFile()` helper in `core/api/client.ts`, so auth
headers, the 401 redirect, and the `Content-Disposition` filename are handled in one place.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/projects/{id}/export/dossier?format=docx\|xlsx` | GET | Dossier |
| `/projects/{id}/export/references?format=ris\|docx\|xlsx` | GET | Reference list (RIS by default) |

## State managed

No store — the menu holds local `$state` for open/busy.

## Special patterns

- **Downloads**: the export functions return the saved filename, which the menu surfaces in a
  success toast
- **Busy state**: one spinner behind the trigger, and every format button disabled, while any
  export is in flight
- **Refusals**: the backend answers a paper-less project with a 400 whose detail is shown verbatim
  as an error toast
