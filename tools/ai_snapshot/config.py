import re

OUTPUT_NAME = "ksef-sync_project_for_ai.txt"
MAX_TEXT_FILE_SIZE = 1_000_000

AI_INSTRUCTIONS = """# INSTRUKCJE DLA AI

To jest snapshot projektu Python ksef-sync.

Projekt służy do lokalnej synchronizacji / pobierania faktur z KSeF oraz przygotowania batchy danych,
które mogą być następnie wykorzystane przez projekt ksef-sync do wygenerowania JPK_V7M.

Analizuj projekt jako całość, nie jako zbiór niezależnych plików.

Ważne:
- Najpierw zrozum strukturę projektu, konfigurację i przepływ danych.
- Respektuj znaczniki FILE START / FILE END.
- Przy sugestiach podawaj dokładne ścieżki plików.
- Szczególnie sprawdzaj bezpieczeństwo tokenów, certyfikatów, kluczy, plików sesji i danych podatnika.
- Szczególnie sprawdzaj obsługę katalogów batchy: data/batches/<batch_id>/invoices, pdf, logs, manifest.json.
- Szczególnie sprawdzaj identyfikowalność faktur: NrKSeF, nazwa pliku, hash, manifest, status pobrania.
- Szczególnie sprawdzaj odporność na duplikaty, przerwane pobieranie, ponowne uruchomienie i błędy API.
- Szczególnie sprawdzaj, czy dane wejściowe dla ksef-sync są kompletne i czytelne.
- Nie zakładaj istnienia plików, których nie ma na liście.
- Nie przepisuj całego projektu, jeśli nie zostaniesz o to poproszony.
- Jeśli zauważysz możliwe sekrety, NIP-y, NrKSeF, dane kontrahentów lub dane prywatne, ostrzeż mnie.
"""

PROJECT_CONTEXT = """# PROJECT CONTEXT

Project name:
ksef-sync

Purpose:
Local Python CLI tool for synchronizing invoice data from KSeF and saving it into reproducible local batches.

Business purpose:
Preparing a controlled, auditable local archive of KSeF invoices that can be used by downstream tools,
especially ksef-sync, which reads KSeF XML invoices and generates JPK_V7M.

Expected relationship with ksef-sync:
- ksef-sync creates batch folders.
- ksef-sync may read invoices directly from a selected or latest ksef-sync batch.
- The README describes the downstream convention:
  ksef-sync/data/batches/<batch_id>/invoices
  ksef-sync/data/batches/<batch_id>/pdf
  ksef-sync/data/batches/<batch_id>/logs
  ksef-sync/data/batches/<batch_id>/manifest.json

Inputs:
- KSeF authentication/configuration files
- local runtime configuration
- selected period/date range
- optional existing local batch state

Outputs:
- KSeF invoice XML files
- optional PDF files
- batch manifest.json
- logs and diagnostic files
- local archive directories for later JPK processing

Type:
CLI / local automation tool.

Main downstream consumer:
ksef-sync, configured with input_dir pointing to data/batches/<batch_id>/invoices.

Important safety assumption:
This project may communicate with KSeF or handle credentials/tokens. Treat runtime config, keys, tokens,
session files, invoice XML, PDFs, manifests and logs as sensitive.
"""

CURRENT_STATUS = """# CURRENT STATUS

Status should be verified from the actual project snapshot.

Assumed from README-derived integration requirements:
- ksef-sync produces batch directories under data/batches/.
- Each batch should contain invoices/, pdf/, logs/ and manifest.json.
- Downstream ksef-sync can consume invoices/ as input_dir.

Do not assume that all features are implemented unless visible in the snapshot.
When reviewing code, explicitly check:
- KSeF authentication flow
- token/session storage
- invoice XML download
- PDF download, if implemented
- batch manifest creation
- retry/resume behavior
- duplicate detection
- logging and audit trail
- integration with ksef-sync input_dir convention
"""

PROJECT_ARCHITECTURE = """# PROJECT ARCHITECTURE

Expected main domains:
- configuration loading
- KSeF authentication/session management
- API client / transport layer
- invoice search/query by period
- invoice XML download
- optional PDF download
- batch creation and naming
- manifest generation
- logging and diagnostics
- local archive management
- integration handoff to ksef-sync

Expected important paths:
- main entrypoint, e.g. main.py, ksef_sync/main.py or equivalent
- config/configuration module
- API/client module
- auth/session module
- downloader/synchronizer module
- batch/manifest module
- data/batches/<batch_id>/invoices
- data/batches/<batch_id>/pdf
- data/batches/<batch_id>/logs
- data/batches/<batch_id>/manifest.json

The exact paths must be confirmed from the snapshot. Do not invent modules that are not present.
"""

DATA_FLOW = """# DATA FLOW

KSeF credentials / token / session configuration
    ↓
authentication and session initialization
    ↓
period/date-range invoice query
    ↓
invoice metadata retrieval
    ↓
invoice XML download
    ↓
optional PDF download
    ↓
local batch directory creation
    ↓
data/batches/<batch_id>/invoices
    ↓
data/batches/<batch_id>/pdf
    ↓
data/batches/<batch_id>/logs
    ↓
data/batches/<batch_id>/manifest.json
    ↓
downstream processing by ksef-sync using input_dir = .../batches/<batch_id>/invoices
"""

PIPELINE_ARCHITECTURE_CONTEXT = """# PIPELINE ARCHITECTURE

High level processing flow:

1. Configuration stage
   Includes:
   - local config loading
   - environment variables
   - credentials/certificate paths
   - selected period/date range
   - output batch root

2. Authentication stage
   Includes:
   - token/certificate/session handling
   - expiration checks
   - safe storage rules
   - clear error handling for failed auth

3. Query stage
   Includes:
   - KSeF invoice listing
   - pagination
   - date range handling
   - sales/purchase direction, if available
   - stable invoice identifiers

4. Download stage
   Includes:
   - XML invoice retrieval
   - optional PDF retrieval
   - retry and resume
   - checksum/hash capture
   - duplicate handling

5. Batch stage
   Includes:
   - timestamped batch id
   - invoices/ directory
   - pdf/ directory
   - logs/ directory
   - manifest.json
   - atomic writes where practical

6. Audit and quality stage
   Includes:
   - count of queried/downloaded/skipped/error invoices
   - manifest consistency
   - missing files detection
   - duplicate detection
   - clear status per invoice

7. Handoff stage
   Includes:
   - path for ksef-sync input_dir
   - optional latest batch detection
   - clear console summary
"""

SYSTEM_INVARIANTS = """# SYSTEM INVARIANTS

Critical rules that must not be violated:

1. Sensitive data
- KSeF tokens, certificates, keys, passwords, session locks and production configs must not be included in snapshots.
- Invoice XML, PDFs, generated reports and manifests may contain sensitive tax data.
- NIP, NrKSeF, invoice numbers, contractor names, e-mail addresses and phone numbers require care before sharing.

2. Local archive integrity
- Every downloaded invoice must be traceable to KSeF metadata.
- Every file saved in invoices/ should have a stable identity in manifest.json.
- Batch output should be reproducible and auditable.

3. Batch convention
- The downstream-compatible batch structure is:
  data/batches/<batch_id>/invoices
  data/batches/<batch_id>/pdf
  data/batches/<batch_id>/logs
  data/batches/<batch_id>/manifest.json
- ksef-sync consumes the invoices/ directory as input_dir.

4. No silent data loss
- Failed downloads must be visible in logs and manifest.
- Duplicates must be reported, not silently overwritten.
- Partial batches must be detectable.

5. Atomic and safe writes
- Avoid overwriting existing invoice files without explicit duplicate logic.
- Prefer temporary files plus rename for downloaded artifacts.
- Preserve existing successful downloads during retry/resume.

6. XML safety
- XML should not be parsed unsafely when parsing is required.
- If parsing KSeF XML, prefer defusedxml.
- Do not mutate original downloaded XML unless explicitly creating a normalized copy.

7. Downstream compatibility
- Invoice XML files must remain usable by ksef-sync.
- Do not change file naming or batch layout casually.
- manifest.json should help downstream traceability, not replace source XML.

8. Network behavior
- Any outbound communication must be explicit, limited to KSeF-related endpoints, and documented.
- No telemetry or unrelated network calls should be introduced.
"""

MODULE_RESPONSIBILITIES = """# MODULE RESPONSIBILITIES

Configuration module
- Load runtime settings.
- Validate required fields.
- Avoid hardcoded taxpayer data.
- Avoid exposing secrets in logs.

Authentication/session module
- Handle KSeF authentication only.
- Store and refresh tokens safely.
- Never print tokens, private keys or sensitive session data.

KSeF API client module
- Encapsulate HTTP/API calls.
- Handle pagination, retries and HTTP errors.
- Return structured errors rather than raw ambiguous exceptions.

Downloader/sync module
- Coordinate invoice metadata retrieval and file downloads.
- Preserve stable invoice identifiers.
- Avoid overwriting files incorrectly.
- Record download status.

Batch/manifest module
- Create data/batches/<batch_id>/ structure.
- Write manifest.json.
- Track counts, hashes, timestamps, status and source identifiers.
- Keep manifest compatible with downstream audit needs.

Logging module
- Write useful logs to batch logs/.
- Avoid logging secrets or full sensitive payloads.
- Make errors actionable.

Integration/handoff module
- Print or expose the invoices/ path for ksef-sync.
- Optionally support latest batch detection.
- Do not perform JPK tax mapping; that belongs to ksef-sync.

Tests
- Cover auth failure handling with mocks.
- Cover pagination and retry behavior.
- Cover duplicate/resume cases.
- Cover manifest consistency.
- Cover batch structure compatibility.
"""

COMMON_AI_PITFALLS = """# COMMON AI PITFALLS

Common mistakes to avoid when modifying this project:

1. Do not include production invoice XML, PDFs, manifests, logs or config files in AI snapshots.

2. Do not log or expose tokens, private keys, passwords, session IDs or certificate secrets.

3. Do not overwrite downloaded invoice files without a deliberate duplicate strategy.

4. Do not silently skip failed downloads.

5. Do not invent fallback NrKSeF or invoice identifiers.

6. Do not change the batch layout if ksef-sync depends on it.

7. Do not mix responsibilities:
- ksef-sync downloads and archives invoices.
- ksef-sync maps invoices to JPK_V7M.

8. Do not introduce unrelated outbound network communication.

9. Do not assume README status is complete; confirm implementation from files.

10. Do not use unsafe XML parsing for invoice XML if the project parses downloaded XML.

11. Do not hardcode taxpayer data, NIP, KSeF endpoint details or paths that should be configurable.

12. Do not hide partial batch state; it must be clear whether a batch is complete or incomplete.
"""

CRITICAL_BUSINESS_RULES = """# CRITICAL BUSINESS RULES

1. Batch identity
- Batch id should be stable and timestamp-based or explicitly provided.
- Batch directory should uniquely identify one synchronization run.

2. Invoice identity
- Prefer KSeF-provided stable identifiers, especially NrKSeF when available.
- Preserve invoice number, issue date, direction and counterparty metadata where available.
- File naming should avoid collisions.

3. Manifest
- manifest.json should contain enough information to audit:
  - batch id
  - run timestamp
  - selected period/date range
  - source/query parameters excluding secrets
  - invoice count summary
  - per-invoice status
  - XML/PDF paths
  - hashes/checksums where practical
  - errors/warnings

4. Download status
- Distinguish downloaded, skipped duplicate, failed, unavailable and retried.
- Failed entries should remain visible.

5. ksef-sync handoff
- The final XML directory for downstream JPK processing is:
  data/batches/<batch_id>/invoices.
- Do not require ksef-sync to read secrets or call KSeF.

6. Sensitive data handling
- Runtime config and downloaded artifacts are sensitive.
- Generated snapshots must exclude production data and secrets.

7. Re-run behavior
- Re-running the same period should not corrupt previous batches.
- Resume mode, if implemented, should preserve successful files and retry failed ones.

8. Error handling
- API errors, auth errors and malformed responses must be explicit.
- Do not mark a batch complete if critical downloads failed.
"""

SECRET_SENSITIVE_CONTEXT = """# SECRET / SENSITIVE DATA WARNINGS

ksef-sync can process or store sensitive data:
- KSeF tokens
- private keys / certificates
- session files
- config files with taxpayer identifiers
- NIP
- contractor names
- invoice numbers
- NrKSeF
- XML invoices
- PDF invoices
- manifest.json
- logs that may contain identifiers

Before sharing a snapshot, mask or exclude:
- config.json and local config variants
- .env files
- token/session files
- public/private keys and certificates
- data/batches
- production XML/PDF files
- generated reports and logs
- NIP, NrKSeF, invoice numbers, e-mail addresses and phone numbers
"""

DOMAIN_OBJECTS_CONTEXT = """# DOMAIN OBJECTS — KSEF-SYNC

Główne obiekty i pojęcia domenowe projektu:

- KSeF session
- authentication token
- invoice metadata
- invoice XML
- invoice PDF
- batch
- manifest.json
- export package
- sync result
- download status
- taxpayer context

Ważne pola/metadane:

- batch_id
- invoice_id
- ksef_reference_number
- invoice_number
- seller_nip
- buyer_nip
- issue_date
- acquisition_date
- xml_path
- pdf_path
- download_status
- error_code
- error_message
"""

FILE_METADATA_CONTEXT = """# FILE METADATA — KSEF-SYNC

Interpretacja metadanych plików w snapshotach AI:

- mtime oznacza lokalny czas modyfikacji pliku.
- sha256 może być używany do porównywania zmian między snapshotami.
- Puste pliki __init__.py są poprawnymi markerami pakietów Python.
- Pliki z katalogów runtime są pomijane ze względów bezpieczeństwa.
- Katalogi batches, logs, exports, auth i keys są traktowane jako potencjalnie wrażliwe.
- Pliki .env oraz lokalne tokeny sesji nie powinny trafiać do snapshotu.
- Manifesty batchy mogą zawierać dane faktur i także powinny być pomijane.
"""

FILE_METADATA_CONTEXT = """# FILE METADATA — KSEF-SYNC

Interpretacja metadanych plików:

- mtime oznacza czas ostatniej modyfikacji pliku.
- sha256 może być używany do wykrywania zmian między snapshotami.
- Puste __init__.py są poprawnymi markerami pakietów Python.
- Katalogi runtime i dane KSeF są pomijane.
- batches/, logs/, exports/, auth/, keys/ są traktowane jako wrażliwe.
- config.json oraz .env mogą zawierać sekrety.
- XML/PDF faktur nie powinny trafiać do snapshotów AI.
"""


MODULE_SUMMARY_CONTEXT = """# MODULE SUMMARY — KSEF-SYNC

tools/ai_snapshot/
- Generowanie snapshotów projektu dla AI.
- Łączenie struktury projektu, kodu i kontekstu domenowego.
- Pomijanie danych wrażliwych i runtime.

core/
- Główna logika synchronizacji z KSeF.

auth/
- Obsługa autoryzacji i tokenów.

batches/
- Batch processing pobranych dokumentów.

exports/
- Eksport XML/PDF/raportów.

logs/
- Logi operacyjne i diagnostyczne.

keys/
- Klucze i certyfikaty KSeF.

config/
- Konfiguracja środowiska i aplikacji.
"""

README_DERIVED_CONTEXT = """# README-DERIVED CONTEXT

The README describes a downstream JPK generator that:
- parses KSeF XML files
- recognizes sales and purchases
- maps data to VAT evidence
- builds JPK_V7M
- validates XML against the Ministry of Finance XSD
- generates HTML preview and quality reports

The important ksef-sync integration point is the batch convention:

ksef-sync/data/batches/
   <batch_id>/
      invoices/
      pdf/
      logs/
      manifest.json

For downstream processing, ksef-sync should receive:
input_dir = .../batches/<batch_id>/invoices
"""

ALWAYS_IGNORE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "data",
    "batches",
    "prod_data",
    "test_data",
    "old_test_data",
    "output",
    "outputs",
    "reports",
    "logs",
    "dist",
    "build",
}

SECRET_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    "config.json",
    "config.local.json",
    "settings.local.json",
    "secrets.json",
    "credentials.json",
    "token.json",
    "tokens.json",
    "session.json",
    "session_lock.json",
    "public_keys.json",
    "ksef_public_key.pem",
    "id_rsa",
    "id_rsa.pub",
}

SECRET_EXTENSIONS = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
}

EXTRA_IGNORE_FILES = {
    "git_init.txt",
    "project_for_ai.txt",
    "ksef_sync_project_for_ai.txt",
    "ksef-send_project_for_ai.txt",
    "ksef_send_project_for_ai.txt",
    "ksef-sync_project_for_ai.txt",
    OUTPUT_NAME,
}

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".dockerfile",
}

TEXT_FILENAMES = {
    ".gitignore",
    ".gitattributes",
    ".env.example",
    "Dockerfile",
    "Containerfile",
    "Makefile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

PRIORITY_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "pytest.ini",
    ".gitignore",
    ".gitattributes",
    "check.ps1",
    "fix.ps1",
    "main.py",
    "ksef_sync/main.py",
    "ksef_sync/__main__.py",
    "ksef_sync/config.py",
    "ksef_sync/client.py",
    "ksef_sync/auth.py",
    "ksef_sync/downloader.py",
    "ksef_sync/batch.py",
    "ksef_sync/manifest.py",
]

SECRET_PATTERNS = [
    (
        "possible_api_key_or_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|token|password|passwd|haslo|credential|session)\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"
        ),
    ),
    ("possible_private_key", re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("possible_certificate", re.compile(r"-----BEGIN CERTIFICATE-----")),
    (
        "possible_jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    ("possible_iban_pl", re.compile(r"\bPL\d{26}\b|\b\d{26}\b")),
    ("possible_polish_nip", re.compile(r"\b\d{10}\b")),
    ("possible_nr_ksef", re.compile(r"\b\d{10}-\d{8}-[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{2}\b")),
    ("possible_email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("possible_phone_pl", re.compile(r"(?<!\d)(?:\+48\s?)?(?:\d[\s-]?){9}(?!\d)")),
]
