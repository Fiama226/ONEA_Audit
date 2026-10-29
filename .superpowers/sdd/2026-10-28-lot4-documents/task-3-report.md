# Task 3 report

Status: done. pdf.py (GotenbergIndisponibleError, ConversionPdfError, convertir_en_pdf), CI gotenberg:8.37.0 service + GOTENBERG_URL, pytest marker gotenberg.
Tests: 904 passed, 1 skipped (integration, no Gotenberg locally); ruff, format, mypy strict, makemigrations --check clean.
Notes: settings GOTENBERG_URL/GOTENBERG_TIMEOUT/DOCUMENTS_PDFA read via getattr with defaults (T1 owns settings). Redirects disabled; 3xx/4xx/non-PDF -> ConversionPdfError. Integration test builds its own minimal docx (no dependency on T2 docx_avec).

## Fix note (review)
Bounded retry in pdf.py: 2 retries (backoff 15s, 30s) on 503 and ConnectionError only; Timeout, other 5xx and 4xx are not retried. Gotenberg CI service now has a health-cmd. Integration test also asserts pdfaid for pdfa=True. tests/documents: 15 passed, 2 skipped (no local Gotenberg); ruff/mypy clean.
