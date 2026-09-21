# Export Feature Contract

Exporting a project out of the app — the two artifacts the researcher takes away.

## What it does

Provides one `ExportMenu` mounted in the project header, offering the literature workbook (`.xlsx`)
and the project dossier (`.docx`). Both downloads go through the shared `downloadFile()` helper in
`core/api/client.ts`, so auth headers, the 401 redirect, and the `Content-Disposition` filename are
handled in one place.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/projects/{id}/export/workbook` | GET | Literature workbook (`.xlsx`) |
| `/projects/{id}/export/dossier` | GET | Project dossier (`.docx`); `?include_answers=true` adds saved answers |

## State managed

No store — the menu holds local `$state` for open/busy and the "include answers" checkbox.

## Special patterns

- **Downloads**: `exportWorkbook()` / `exportDossier()` return the saved filename, which the menu
  surfaces in a success toast
- **Refusals**: the backend answers a paper-less project with a 400 whose detail is shown verbatim
  as an error toast
- **Progress**: an inline spinner on the trigger while a render is in flight; the trigger is disabled
