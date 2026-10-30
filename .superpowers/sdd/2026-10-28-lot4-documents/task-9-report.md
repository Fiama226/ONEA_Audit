# Task 9 report

Status: DONE. Pages TemplatesPage, TemplateDetailPage, NumberingPage; UploadTemplateDialog, ActivateTemplateDialog, ContractFieldsPanel, AdminTabs; schemas template/numbering; fr.documentsAdmin.

Routes (deviation from brief, follows T8 skeleton): /administration/documents (list), /administration/documents/:type (detail), /administration/documents/numerotation. Parent guard is ADMIN-only; pages hide write actions for non-ADMIN (RAI read-only).

Tests: 21 passed (3 files), tsc and eslint clean. Not run: full suite, visual ui-designer review.

Concerns: contract doc "link" is a plain path (no served docs URL). Uploaded file name not asserted (MSW yields a Blob).

## Fix round
I1: own guard [ADMIN,RAI] on /administration/documents (routes.tsx, navigation.ts), sidebar entry, route and sidebar tests.
I2: unique keys and button names by full path (two-list test).
I3: apiUpload/apiDownload take an AbortSignal; closing the upload dialog aborts the request; lists refetched on settle.
Minors: exact tabs, ref guards, focus return, preview abort and stale errors, all versions via fetchAllPages.
Tests: documents, layouts, routes, api green.
