import argparse
import hashlib
import json
import logging
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import config
from ksef.auth import KSeFAuthClient
from ksef.build_index import build_batch_index
from ksef.downloader import KSeFDownloader
from ksef.export import KSeFExportClient
from ksef.http_client import HttpClient
from ksef.invoice_xml import classify_ksef_invoice_xml
from ksef.logging_config import configure_logging
from ksef.pdf_generator import generate_invoice_pdfs
from ksef.utils import ensure_dir, redact_secrets, save_json

logger = logging.getLogger(__name__)
CURRENT_BATCH_DIR: Path | None = None

WORKFLOW_STEPS = [
    "auth_done",
    "exports_started",
    "exports_completed",
    "parts_downloaded",
    "parts_decrypted",
    "batch_prepared",
    "pdf_done",
    "validated",
]


def print_menu():
    print("\n=== TRYB MANUALNY / DIAGNOSTYCZNY ===")

    print("\n[KSeF API]")
    print("1 - test uwierzytelnienia KSeF")
    print("2 - test eksportu/statusu (bez pobierania)")
    print("3 - pełny sync testowy (mały zakres)")

    print("\n[OFFLINE / LOKALNIE]")
    print("4 - generowanie PDF dla istniejącego batcha")
    print("5 - budowa index.html dla batcha")

    print("\n6 - wyjście")


def run_generate_pdf_for_batch():
    raw = input("Podaj batch_id: ").strip()

    if not raw:
        print("Brak batch_id")
        return

    batch_dir = config.BATCH_DIR / raw

    if not batch_dir.exists():
        print(f"Batch nie istnieje: {batch_dir}")
        return

    print("\nGenerowanie PDF...")
    pdf_report = generate_invoice_pdfs(batch_dir)

    print(f"PDF katalog: {pdf_report['pdf_dir']}")
    print(f"Wygenerowano PDF: {pdf_report['generated_count']}")
    print(f"Pominięto PDF: {pdf_report['skipped_count']}")

    if pdf_report["error_count"]:
        print(f"Błędy: {pdf_report['error_count']}")


def run_build_index_for_batch():
    raw = input("Podaj batch_id: ").strip()

    if not raw:
        print("Brak batch_id")
        return

    batch_dir = config.BATCH_DIR / raw

    if not batch_dir.exists():
        print(f"Batch nie istnieje: {batch_dir}")
        return

    print("\nBudowa index.html...")
    index_file = build_batch_index(batch_dir)

    print(f"Index HTML: {index_file}")


def run_auth_only():
    ensure_dir(config.AUTH_DIR)

    http = HttpClient()
    auth_client = KSeFAuthClient(http, config.AUTH_DIR)

    result = auth_client.authenticate()
    print("\nUwierzytelnienie OK")
    print(json.dumps(redact_secrets(result), ensure_ascii=False, indent=2))


def run_export_only(days_back: int):
    ensure_dir(config.AUTH_DIR)
    ensure_dir(config.EXPORT_DIR)

    http = HttpClient()
    auth_client = KSeFAuthClient(http, config.AUTH_DIR)
    export_client = KSeFExportClient(http, config.EXPORT_DIR)

    auth_result = auth_client.authenticate()
    access_token = auth_result["accessToken"]["token"]

    date_to = datetime.now(UTC)
    date_from = date_to - timedelta(days=days_back)

    export_init = export_client.start_export(access_token, date_from, date_to)
    export_ref = export_init["referenceNumber"]

    print(f"\nExport started: {export_ref}")

    export_status = export_client.wait_for_export(access_token, export_ref)
    save_json(config.EXPORT_DIR / "03_export_status_final.json", export_status, redact=True)

    parts = export_client.extract_part_urls(export_status)

    print("\nEksport zakończony.")
    print(json.dumps(export_status, ensure_ascii=False, indent=2))

    print(f"\nLiczba części paczki: {len(parts)}")
    for part in parts:
        print(f"Part {part['part_number']}: {part['url']}")


def prepare_batch_for_jpk(
    batch_dir: Path,
    raw_dirs: list[str],
    batch_id: str,
    date_from: datetime,
    date_to: datetime,
    export_status: dict | None = None,
) -> dict:
    """
    Przygotowuje paczkę dla ksef2jpk:
    - zbiera XML-e z raw/part_*
    - kopiuje je do invoices/
    - tworzy manifest.json
    """

    invoices_dir = batch_dir / "invoices"
    ensure_dir(invoices_dir)

    invoices = []
    duplicate_names = []
    seen = set()
    skipped_files = []

    for raw_dir_txt in raw_dirs:
        raw_dir = Path(raw_dir_txt)

        for xml_path in sorted(raw_dir.rglob("*.xml")):
            filename = xml_path.name

            classification = classify_ksef_invoice_xml(xml_path)
            if not classification["ok"]:
                skipped_files.append(
                    {
                        "filename": filename,
                        "source_path": str(xml_path),
                        "reason": classification["reason"],
                    }
                )
                continue

            if filename in seen:
                duplicate_names.append(filename)
                continue

            seen.add(filename)

            nr_ksef = filename[:-4] if filename.lower().endswith(".xml") else filename
            target_path = invoices_dir / filename

            shutil.copy2(xml_path, target_path)

            invoices.append(
                {
                    "filename": filename,
                    "nr_ksef": nr_ksef,
                    "source_path": str(xml_path),
                    "target_path": str(target_path),
                    "schema": classification["schema"],
                }
            )

    invoices.sort(key=lambda x: x["filename"])
    invoice_hashes = {
        f"invoice:{invoice['filename']}": {
            "path": invoice["target_path"],
            "sha256": sha256_file(Path(invoice["target_path"])),
        }
        for invoice in invoices
    }

    manifest = {
        "schema_version": 1,
        "tool": {
            "name": "ksef-sync",
            "command": "main.py sync",
        },
        "period": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "label": f"{date_from:%Y-%m}",
        },
        "inputs": {
            "raw_dirs": raw_dirs,
            "export_status": export_status,
        },
        "outputs": {
            "batch_dir": str(batch_dir),
            "manifest": str(batch_dir / "manifest.json"),
            "invoices_dir": str(invoices_dir),
            "skipped_files_report": str(batch_dir / "logs" / "skipped_invoices.json"),
        },
        "checks": {
            "invoice_count": len(invoices),
            "skipped_invoice_count": len(skipped_files),
            "duplicate_files": duplicate_names,
        },
        "hashes": invoice_hashes,
        "status": "prepared",
        "batch": {
            "batch_id": batch_id,
            "source": "ksef_api_export",
            "ksef": config.get_ksef_metadata(),
            "created_at": datetime.now(UTC).isoformat(),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "invoice_count": len(invoices),
            "skipped_invoice_count": len(skipped_files),
            "has_duplicates": bool(duplicate_names),
            "duplicate_files": duplicate_names,
            "skipped_files_report": "logs/skipped_invoices.json",
            "export_status_saved": "logs/03_export_status_final.json",
        },
        "storage": {
            "invoices_dir": "invoices",
            "raw_dir": "raw",
            "logs_dir": "logs",
        },
        "invoices": invoices,
    }

    save_json(batch_dir / "logs" / "skipped_invoices.json", skipped_files)
    save_json(batch_dir / "manifest.json", manifest)

    return manifest


def resolve_new_batch_dir(batch_id: str) -> tuple[str, Path]:
    candidate_id = batch_id
    candidate = config.BATCH_DIR / candidate_id
    counter = 1

    while candidate.exists():
        candidate_id = f"{batch_id}_{counter:02d}"
        candidate = config.BATCH_DIR / candidate_id
        counter += 1

    return candidate_id, candidate


def save_batch_status(batch_dir: Path, status: str, detail: str = "") -> None:
    save_json(
        batch_dir / "status.json",
        {
            "status": status,
            "detail": detail,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )


def load_workflow_state(batch_dir: Path) -> dict:
    state_path = batch_dir / "workflow_state.json"
    if not state_path.exists():
        return {"schema_version": 1, "steps": {}, "data": {}}

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("schema_version", 1)
    state.setdefault("steps", {})
    state.setdefault("data", {})
    return state


def save_workflow_state(batch_dir: Path, state: dict) -> None:
    state["updated_at"] = datetime.now(UTC).isoformat()
    save_json(batch_dir / "workflow_state.json", state)


def mark_workflow_step(
    batch_dir: Path,
    state: dict,
    step: str,
    status: str = "done",
    detail: str = "",
    data: dict | None = None,
) -> None:
    if step not in WORKFLOW_STEPS:
        raise ValueError(f"Unknown workflow step: {step}")

    state.setdefault("steps", {})[step] = {
        "status": status,
        "detail": detail,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if data:
        state.setdefault("data", {}).update(data)
    save_workflow_state(batch_dir, state)


def is_workflow_step_done(state: dict, step: str) -> bool:
    return state.get("steps", {}).get(step, {}).get("status") == "done"


def build_download_validation_report(batch_dir: Path, manifest: dict) -> dict:
    invoices_dir = batch_dir / manifest.get("storage", {}).get("invoices_dir", "invoices")
    manifest_invoices = manifest.get("invoices", [])
    invoice_files = sorted(invoices_dir.glob("*.xml")) if invoices_dir.exists() else []
    skipped_report = batch_dir / manifest.get("batch", {}).get(
        "skipped_files_report", "logs/skipped_invoices.json"
    )

    checks = [
        {
            "name": "invoices dir exists",
            "ok": invoices_dir.exists(),
            "detail": str(invoices_dir),
        },
        {
            "name": "invoice count matches manifest",
            "ok": len(invoice_files) == manifest.get("batch", {}).get("invoice_count"),
            "detail": f"files={len(invoice_files)} manifest={manifest.get('batch', {}).get('invoice_count')}",
        },
        {
            "name": "invoice list matches manifest count",
            "ok": len(manifest_invoices) == manifest.get("batch", {}).get("invoice_count"),
            "detail": f"list={len(manifest_invoices)} manifest={manifest.get('batch', {}).get('invoice_count')}",
        },
        {
            "name": "skipped invoices report exists",
            "ok": skipped_report.exists(),
            "detail": str(skipped_report),
        },
    ]

    return {
        "batch_dir": str(batch_dir),
        "created_at": datetime.now(UTC).isoformat(),
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }


def run_full_sync(
    days_back: int,
    year: int | None = None,
    month: int | None = None,
    resume_batch_id: str | None = None,
) -> bool:
    ensure_dir(config.DATA_DIR)
    ensure_dir(config.AUTH_DIR)
    ensure_dir(config.EXPORT_DIR)
    ensure_dir(config.BATCH_DIR)

    http = HttpClient()
    auth_client = KSeFAuthClient(http, config.AUTH_DIR)
    export_client = KSeFExportClient(http, config.EXPORT_DIR)
    downloader = KSeFDownloader(http, config.BATCH_DIR)

    if year and month:
        date_from = datetime(year, month, 1, tzinfo=UTC)

        if month == 12:
            date_to = datetime(year + 1, 1, 1, tzinfo=UTC)
        else:
            date_to = datetime(year, month + 1, 1, tzinfo=UTC)
    else:
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

    if resume_batch_id:
        batch_id = resume_batch_id
        batch_dir = config.BATCH_DIR / batch_id
    else:
        batch_id, batch_dir = resolve_new_batch_dir(datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))

    global CURRENT_BATCH_DIR
    CURRENT_BATCH_DIR = batch_dir

    raw_dir = batch_dir / "raw"
    invoices_dir = batch_dir / "invoices"
    logs_dir = batch_dir / "logs"

    for d in (batch_dir, raw_dir, invoices_dir, logs_dir):
        ensure_dir(d)

    workflow_state = load_workflow_state(batch_dir)

    save_batch_status(
        batch_dir, "running", "sync started" if not resume_batch_id else "sync resumed"
    )

    print("\n1. Uwierzytelnianie...")
    auth_result = auth_client.authenticate()
    access_token = auth_result["accessToken"]["token"]
    mark_workflow_step(batch_dir, workflow_state, "auth_done")
    print("   OK")

    exports_to_run = [
        ("sales", "Subject1", "sprzedaż"),
        ("purchase", "Subject2", "zakup/koszty"),
    ]

    all_parts = workflow_state.get("data", {}).get("all_parts", [])
    export_statuses = workflow_state.get("data", {}).get("export_statuses", {})

    if is_workflow_step_done(workflow_state, "exports_completed") and all_parts:
        print("2. Eksporty już zakończone, używam workflow_state.json.")
    else:
        all_parts = []
        export_statuses = {}
        print("2. Start eksportów...")
        mark_workflow_step(batch_dir, workflow_state, "exports_started")

        for export_key, subject_type, label in exports_to_run:
            print(f"   Start eksportu: {label} ({subject_type})")

            export_init = export_client.start_export(
                access_token,
                date_from,
                date_to,
                subject_type=subject_type,
                export_key=export_key,
            )

            export_ref = export_init["referenceNumber"]
            print(f"   Export reference [{label}]: {export_ref}")

            print(f"3. Oczekiwanie na eksport: {label}...")
            export_status = export_client.wait_for_export(access_token, export_ref)

            export_statuses[export_key] = {
                "subject_type": subject_type,
                "label": label,
                "reference_number": export_ref,
                "status": export_status,
            }

            save_json(logs_dir / f"export_status_{export_key}.json", export_status, redact=True)

            parts = export_client.extract_part_urls(export_status)
            invoice_count = export_status.get("package", {}).get("invoiceCount", 0)

            if not parts:
                print(f"   Brak części paczki dla: {label}")
                print(f"   Liczba faktur: {invoice_count}")
                continue

            for part in parts:
                part["export_key"] = export_key
                part["subject_type"] = subject_type
                part["label"] = label
                part["export_ref"] = export_ref
                all_parts.append(part)

        mark_workflow_step(
            batch_dir,
            workflow_state,
            "exports_completed",
            data={"export_statuses": export_statuses, "all_parts": all_parts},
        )

    if not all_parts:
        print("Brak części paczek w obu eksportach.")
        save_batch_status(batch_dir, "partial", "exports completed but no package parts found")
        return False

    print("4. Pobieranie, odszyfrowanie i rozpakowanie...")
    extracted_dirs = []

    for part in all_parts:
        part_number = part["part_number"]
        package_url = part["url"]
        export_key = part["export_key"]

        part_prefix = f"{export_key}_{part_number}"

        encrypted_file = raw_dir / f"{part_prefix}.zip.aes"
        decrypted_zip = raw_dir / f"{part_prefix}.zip"
        extracted_dir = raw_dir / f"{part_prefix}"

        crypto_json = config.EXPORT_DIR / f"01a_export_crypto_local_{export_key}.json"
        aes_key, iv = downloader.load_crypto_material(crypto_json)

        if extracted_dir.exists() and list(extracted_dir.rglob("*.xml")):
            print(f"   {part['label']} / Part {part_number}: pomijam, już rozpakowano.")
            extracted_dirs.append(str(extracted_dir))
            continue

        print(f"   {part['label']} / Part {part_number}: pobieranie...")
        if encrypted_file.exists():
            print("   Plik zaszyfrowany już istnieje.")
        else:
            downloader.download_file(package_url, encrypted_file)

        print(f"   {part['label']} / Part {part_number}: odszyfrowanie...")
        if decrypted_zip.exists():
            print("   ZIP już istnieje.")
        else:
            downloader.decrypt_aes_cbc_pkcs7(encrypted_file, decrypted_zip, aes_key, iv)

        print(f"   {part['label']} / Part {part_number}: rozpakowanie...")
        downloader.extract_zip(decrypted_zip, extracted_dir)

        extracted_dirs.append(str(extracted_dir))

    mark_workflow_step(batch_dir, workflow_state, "parts_downloaded")
    mark_workflow_step(
        batch_dir,
        workflow_state,
        "parts_decrypted",
        data={"extracted_dirs": extracted_dirs},
    )

    print("\nGotowe.")
    print("Katalog batch:", batch_dir)

    for d in extracted_dirs:
        print("Rozpakowano:", d)

    print("\n5. Przygotowanie paczki dla ksef2jpk...")
    if (
        is_workflow_step_done(workflow_state, "batch_prepared")
        and (batch_dir / "manifest.json").exists()
    ):
        manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
        print("   Paczka już przygotowana, używam istniejącego manifest.json.")
    else:
        manifest = prepare_batch_for_jpk(
            batch_dir=batch_dir,
            raw_dirs=extracted_dirs,
            batch_id=batch_id,
            date_from=date_from,
            date_to=date_to,
            export_status={
                "sales": export_statuses.get("sales"),
                "purchase": export_statuses.get("purchase"),
            },
        )
        mark_workflow_step(
            batch_dir,
            workflow_state,
            "batch_prepared",
            data={"manifest_path": str(batch_dir / "manifest.json")},
        )

    download_validation = build_download_validation_report(batch_dir, manifest)
    save_json(batch_dir / "download_validation_report.json", download_validation)
    if not download_validation["ok"]:
        save_batch_status(batch_dir, "partial", "download validation failed")
        return False

    manifest["batch"]["exports"] = {
        key: {
            "subject_type": value["subject_type"],
            "label": value["label"],
            "reference_number": value["reference_number"],
            "invoice_count": value["status"].get("package", {}).get("invoiceCount", 0),
        }
        for key, value in export_statuses.items()
    }

    save_json(batch_dir / "manifest.json", manifest)

    print("   OK")
    print(f"   XML faktur w invoices/: {manifest['batch']['invoice_count']}")

    if manifest["batch"]["has_duplicates"]:
        print("   ⚠ Wykryto duplikaty nazw XML:")
        for name in manifest["batch"]["duplicate_files"]:
            print(f"     - {name}")

    print(f"   Manifest: {batch_dir / 'manifest.json'}")

    if config.GENERATE_PDF:
        if is_workflow_step_done(workflow_state, "pdf_done"):
            print("\n6. PDF już oznaczone jako gotowe, pomijam generowanie.")
        else:
            print("\n6. Generowanie PDF faktur...")

            pdf_report = generate_invoice_pdfs(batch_dir)

            manifest["pdf"] = pdf_report
            save_json(batch_dir / "manifest.json", manifest)
            mark_workflow_step(
                batch_dir,
                workflow_state,
                "pdf_done",
                data={"pdf_report": pdf_report},
            )

            if year is not None and month is not None:
                print(format_period_label(year, month, date_from, date_to))
            else:
                print(f"Zakres: {date_from.date()} - {date_to.date()}")
            print(f"   PDF katalog: {pdf_report['pdf_dir']}")
            print(f"   Wygenerowano PDF: {pdf_report['generated_count']}")
            print(f"   Pominięto PDF: {pdf_report['skipped_count']}")

        if is_workflow_step_done(workflow_state, "validated"):
            print("   Walidacja końcowa już wykonana, pomijam.")
        else:
            index_file = build_batch_index(batch_dir)
            print(f"   Index HTML: {index_file}")

            final_validation = build_batch_validation_report(batch_dir)
            save_json(batch_dir / "validation_report.json", final_validation)
            if not final_validation["ok"]:
                save_batch_status(batch_dir, "partial", "final validation failed")
                return False
            mark_workflow_step(
                batch_dir,
                workflow_state,
                "validated",
                data={"validation_report_path": str(batch_dir / "validation_report.json")},
            )
    else:
        mark_workflow_step(
            batch_dir, workflow_state, "pdf_done", status="skipped", detail="PDF disabled"
        )
        mark_workflow_step(
            batch_dir, workflow_state, "validated", status="skipped", detail="PDF disabled"
        )

    save_batch_status(batch_dir, "success", "sync completed")

    return True


def run_incremental_sync():
    from ksef import sync_ksef_incremental

    sync_ksef_incremental.main()


def _check_writable_dir(path: Path) -> bool:
    ensure_dir(path)
    probe = path / ".healthcheck"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return True


def build_healthcheck_report() -> list[dict]:
    checks = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    for env_name, value in (
        ("KSEF_ENVIRONMENT", config.KSEF_ENVIRONMENT),
        ("KSEF_API_VERSION", config.KSEF_API_VERSION),
        ("KSEF_NIP", config.NIP),
        ("KSEF_TOKEN", config.KSEF_TOKEN),
        ("KSEF_PUBLIC_KEY_PATH", config.PUBLIC_KEY_PATH),
        ("KSEF_SYMMETRIC_KEY_CERT_PATH", config.SYMMETRIC_KEY_CERT_PATH),
    ):
        add(env_name, bool(value), "set" if value else "missing")

    try:
        config.validate_environment_config()
        add("KSEF environment config", True, config.BASE_URL)
    except Exception as exc:
        add("KSEF environment config", False, str(exc))

    for name, raw_path in (
        ("KSEF_PUBLIC_KEY_PATH file", config.PUBLIC_KEY_PATH),
        ("KSEF_SYMMETRIC_KEY_CERT_PATH file", config.SYMMETRIC_KEY_CERT_PATH),
    ):
        path = Path(raw_path)
        add(name, path.exists(), str(path))

    for name, path in (
        ("KSEF_DATA_DIR writable", config.DATA_DIR),
        ("KSEF_AUTH_DIR writable", config.AUTH_DIR),
        ("KSEF_EXPORT_DIR writable", config.EXPORT_DIR),
        ("KSEF_BATCH_DIR writable", config.BATCH_DIR),
        ("KSEF_LOG_DIR writable", config.LOG_DIR),
    ):
        try:
            _check_writable_dir(path)
            add(name, True, str(path))
        except Exception as exc:
            add(name, False, f"{path}: {exc}")

    add("Python", True, sys.version.split()[0])

    uv_path = shutil.which("uv")
    add("uv", bool(uv_path), uv_path or "not found in PATH")

    node_path = shutil.which("node")
    if config.GENERATE_PDF:
        add("node", bool(node_path), node_path or "required when GENERATE_PDF=true")
        pdf_generator_dir = Path(config.PDF_GENERATOR_DIR)
        add("PDF generator dir", pdf_generator_dir.exists(), str(pdf_generator_dir))
    else:
        add("node", True, node_path or "not required because GENERATE_PDF=false")

    return checks


def run_healthcheck() -> bool:
    checks = build_healthcheck_report()

    print("\n=== KSEF-SYNC HEALTHCHECK ===")
    for check in checks:
        status = "OK" if check["ok"] else "FAIL"
        print(f"[{status}] {check['name']}: {check['detail']}")

    ok = all(check["ok"] for check in checks)
    print("\nStatus:", "OK" if ok else "FAIL")
    return ok


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_latest_batch_dir(batch_root: Path = config.BATCH_DIR) -> Path:
    if not batch_root.exists():
        raise FileNotFoundError(f"Batch root does not exist: {batch_root}")

    batch_dirs = sorted([path for path in batch_root.iterdir() if path.is_dir()])
    if not batch_dirs:
        raise FileNotFoundError(f"No batch directories found in: {batch_root}")

    return batch_dirs[-1]


def resolve_batch_dir(batch_id: str | None) -> Path:
    if batch_id:
        batch_dir = config.BATCH_DIR / batch_id
        if not batch_dir.exists():
            raise FileNotFoundError(f"Batch does not exist: {batch_dir}")
        return batch_dir

    return find_latest_batch_dir()


def build_batch_validation_report(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir)
    checks = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    manifest_path = batch_dir / "manifest.json"
    add("manifest exists", manifest_path.exists(), str(manifest_path))

    if not manifest_path.exists():
        return {
            "batch_dir": str(batch_dir),
            "created_at": datetime.now(UTC).isoformat(),
            "ok": False,
            "checks": checks,
            "files": [],
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    invoices_dir = batch_dir / manifest.get("storage", {}).get("invoices_dir", "invoices")
    pdf_dir = batch_dir / "pdf"
    index_path = batch_dir / "index.html"

    manifest_invoices = manifest.get("invoices", [])
    invoice_files = sorted(invoices_dir.glob("*.xml")) if invoices_dir.exists() else []

    add("invoices dir exists", invoices_dir.exists(), str(invoices_dir))
    add(
        "invoice count matches manifest",
        len(invoice_files) == manifest.get("batch", {}).get("invoice_count"),
        f"files={len(invoice_files)} manifest={manifest.get('batch', {}).get('invoice_count')}",
    )
    add(
        "invoice list matches manifest count",
        len(manifest_invoices) == manifest.get("batch", {}).get("invoice_count"),
        f"list={len(manifest_invoices)} manifest={manifest.get('batch', {}).get('invoice_count')}",
    )
    ksef_metadata = manifest.get("batch", {}).get("ksef")
    add("KSeF metadata exists", isinstance(ksef_metadata, dict), str(ksef_metadata or "missing"))
    if isinstance(ksef_metadata, dict):
        for field_name in ("system_version", "api_version", "environment", "base_url"):
            add(
                f"KSeF metadata {field_name}",
                bool(ksef_metadata.get(field_name)),
                str(ksef_metadata.get(field_name, "")),
            )

    files = []
    for invoice in manifest_invoices:
        filename = invoice.get("filename", "")
        xml_path = invoices_dir / filename
        pdf_path = pdf_dir / f"{Path(filename).stem}.pdf"

        xml_exists = xml_path.exists()
        pdf_exists = pdf_path.exists()

        add(f"xml exists: {filename}", xml_exists, str(xml_path))
        add(f"pdf exists: {pdf_path.name}", pdf_exists, str(pdf_path))

        files.append(
            {
                "filename": filename,
                "xml_path": str(xml_path),
                "xml_sha256": sha256_file(xml_path) if xml_exists else None,
                "pdf_path": str(pdf_path),
                "pdf_sha256": sha256_file(pdf_path) if pdf_exists else None,
            }
        )

    add("index exists", index_path.exists(), str(index_path))

    pdf_report = manifest.get("pdf")
    if pdf_report:
        add(
            "pdf report has no errors",
            pdf_report.get("error_count", 0) == 0,
            f"errors={pdf_report.get('error_count', 0)}",
        )
        add(
            "pdf count matches invoices",
            len(list(pdf_dir.glob("*.pdf"))) == manifest.get("batch", {}).get("invoice_count"),
            (
                f"pdfs={len(list(pdf_dir.glob('*.pdf')))} "
                f"invoices={manifest.get('batch', {}).get('invoice_count')}"
            ),
        )

    ok = all(check["ok"] for check in checks)
    return {
        "batch_dir": str(batch_dir),
        "created_at": datetime.now(UTC).isoformat(),
        "ok": ok,
        "checks": checks,
        "files": files,
    }


def run_validate_batch(batch_id: str | None) -> bool:
    batch_dir = resolve_batch_dir(batch_id)
    report = build_batch_validation_report(batch_dir)
    report_path = batch_dir / "validation_report.json"
    save_json(report_path, report)

    print("\n=== KSEF-SYNC BATCH VALIDATION ===")
    print(f"Batch: {batch_dir}")
    print(f"Report: {report_path}")

    for check in report["checks"]:
        status = "OK" if check["ok"] else "FAIL"
        print(f"[{status}] {check['name']}: {check['detail']}")

    print("\nStatus:", "OK" if report["ok"] else "FAIL")
    return bool(report["ok"])


def directory_size_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def load_batch_summary(batch_dir: Path) -> dict:
    manifest_path = batch_dir / "manifest.json"
    validation_path = batch_dir / "validation_report.json"
    manifest = {}
    validation = {}

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if validation_path.exists():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))

    batch_info = manifest.get("batch", {})
    stat = batch_dir.stat()

    return {
        "batch_id": batch_dir.name,
        "path": str(batch_dir),
        "created_at": batch_info.get("created_at", ""),
        "date_from": batch_info.get("date_from", ""),
        "date_to": batch_info.get("date_to", ""),
        "invoice_count": batch_info.get("invoice_count", ""),
        "validated": validation.get("ok") if validation else "",
        "size_bytes": directory_size_bytes(batch_dir),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def list_batch_summaries(batch_root: Path = config.BATCH_DIR) -> list[dict]:
    if not batch_root.exists():
        return []

    return [
        load_batch_summary(batch_dir)
        for batch_dir in sorted([path for path in batch_root.iterdir() if path.is_dir()])
    ]


def run_list_batches() -> None:
    summaries = list_batch_summaries()

    print("\n=== KSEF-SYNC BATCHES ===")
    if not summaries:
        print(f"Brak batchy w: {config.BATCH_DIR}")
        return

    print(
        f"{'batch_id':<18} {'invoices':>8} {'valid':>7} {'size':>10} "
        f"{'date_from':<25} {'date_to':<25}"
    )
    print("-" * 95)

    for summary in reversed(summaries):
        validated = summary["validated"]
        valid_text = "yes" if validated is True else "no" if validated is False else "unknown"
        print(
            f"{summary['batch_id']:<18} "
            f"{str(summary['invoice_count']):>8} "
            f"{valid_text:>7} "
            f"{format_size(summary['size_bytes']):>10} "
            f"{summary['date_from'][:25]:<25} "
            f"{summary['date_to'][:25]:<25}"
        )


def batch_dirs_older_than(days: int, now: datetime | None = None) -> list[Path]:
    if days < 0:
        raise ValueError("--older-than-days musi być >= 0.")

    if now is None:
        now = datetime.now(UTC)

    if not config.BATCH_DIR.exists():
        return []

    cutoff = now - timedelta(days=days)
    candidates = []

    for batch_dir in config.BATCH_DIR.iterdir():
        if not batch_dir.is_dir():
            continue

        modified_at = datetime.fromtimestamp(batch_dir.stat().st_mtime, UTC)
        if modified_at < cutoff:
            candidates.append(batch_dir)

    return sorted(candidates)


def assert_safe_batch_delete_path(batch_dir: Path) -> None:
    root = config.BATCH_DIR.resolve()
    target = batch_dir.resolve()

    if target == root or not target.is_relative_to(root):
        raise ValueError(f"Niebezpieczna ścieżka do usunięcia: {target}")


def run_cleanup_batches(older_than_days: int, execute: bool) -> None:
    candidates = batch_dirs_older_than(older_than_days)

    mode = "EXECUTE" if execute else "DRY RUN"
    print("\n=== KSEF-SYNC BATCH CLEANUP ===")
    print(f"Mode: {mode}")
    print(f"Older than days: {older_than_days}")

    if not candidates:
        print("Brak batchy do usunięcia.")
        return

    total_size = sum(directory_size_bytes(path) for path in candidates)
    print(f"Kandydaci: {len(candidates)}")
    print(f"Rozmiar łączny: {format_size(total_size)}")

    for batch_dir in candidates:
        assert_safe_batch_delete_path(batch_dir)
        print(f"- {batch_dir} ({format_size(directory_size_bytes(batch_dir))})")

    if not execute:
        print("\nTo był dry-run. Dodaj --execute, żeby usunąć wskazane katalogi.")
        return

    for batch_dir in candidates:
        shutil.rmtree(batch_dir)

    print("\nUsunięto wskazane katalogi batchy.")


def format_period_label(year, month, date_from, date_to):
    if year is not None and month is not None:
        return f"Okres: {year}-{month:02d}"

    return f"Zakres: {date_from.date()} - {date_to.date()}"


def validate_period(year: int | None, month: int | None) -> None:
    if year is None and month is None:
        return

    if year is None or month is None:
        raise ValueError("Podaj jednocześnie --year i --month albo nie podawaj żadnego z nich.")

    if year < 2000 or year > 2100:
        raise ValueError("--year musi być z zakresu 2000-2100.")

    if month < 1 or month > 12:
        raise ValueError("--month musi być z zakresu 1-12.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "command",
        nargs="?",
        choices=[
            "menu",
            "auth",
            "export",
            "sync",
            "incremental",
            "validate",
            "validate-batch",
            "list-batches",
            "cleanup",
        ],
        help=(
            "Komenda. Nowe aliasy: validate=healthcheck, sync=full-sync. Stary --mode nadal działa."
        ),
    )
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--batch-id")
    parser.add_argument("--older-than-days", type=int, default=90)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--mode",
        choices=[
            "menu",
            "auth",
            "export",
            "full-sync",
            "incremental",
            "healthcheck",
            "validate-batch",
            "list-batches",
            "cleanup",
        ],
        default="menu",
    )
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--resume-batch-id")

    args = parser.parse_args(argv)

    if args.command:
        if args.mode != "menu":
            parser.error("Nie używaj jednocześnie komendy pozycyjnej i --mode.")
        command_to_mode = {
            "validate": "healthcheck",
            "sync": "full-sync",
        }
        args.mode = command_to_mode.get(args.command, args.command)

    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    log_file = configure_logging(config.LOG_DIR, args.mode)
    validate_period(args.year, args.month)

    if args.year and args.month:
        year = args.year
        month = args.month
    else:
        prev = datetime.now().replace(day=1)
        prev = (
            prev.replace(month=prev.month - 1)
            if prev.month > 1
            else prev.replace(year=prev.year - 1, month=12)
        )
        year = prev.year
        month = prev.month

    print(f"Okres: {year}-{month:02d}")
    print(f"Tryb: {args.mode}")
    print(f"Log: {log_file}")
    logger.info("Start mode=%s period=%s-%02d", args.mode, year, month)

    if args.mode == "healthcheck":
        if not run_healthcheck():
            return 1
        return 0

    if args.mode == "validate-batch":
        if not run_validate_batch(args.batch_id):
            return 1
        return 0

    if args.mode == "list-batches":
        run_list_batches()
        return 0

    if args.mode == "cleanup":
        run_cleanup_batches(args.older_than_days, args.execute)
        return 0

    if args.mode == "auth":
        config.validate_config()
        run_auth_only()
        return 0

    if args.mode == "export":
        config.validate_config()
        run_export_only(args.days_back)
        return 0

    if args.mode == "full-sync":
        config.validate_config()
        try:
            sync_ok = run_full_sync(
                days_back=args.days_back,
                year=year,
                month=month,
                resume_batch_id=args.resume_batch_id,
            )
        except Exception as exc:
            if CURRENT_BATCH_DIR is not None:
                save_batch_status(CURRENT_BATCH_DIR, "partial", str(exc))
            raise

        if not sync_ok:
            return 2
        return 0

    if args.mode == "incremental":
        config.validate_config()
        run_incremental_sync()
        return 0

    while True:
        print_menu()
        choice = input("Twój wybór: ").strip()

        try:
            if choice == "1":
                config.validate_config()
                run_auth_only()

            elif choice == "2":
                config.validate_config()
                raw = input("Ile dni wstecz sprawdzić eksport/status? [1]: ").strip()

                days_back = int(raw or "1")
                run_export_only(days_back)

            elif choice == "3":
                config.validate_config()
                raw = input("Ile dni wstecz pobrać w pełnym syncu testowym? [1]: ").strip()

                days_back = int(raw or "1")
                run_full_sync(days_back)

            elif choice == "4":
                run_generate_pdf_for_batch()

            elif choice == "5":
                run_build_index_for_batch()

            elif choice == "6":
                print("Koniec.")
                return 0

            else:
                print("Nieznana opcja.")

        except Exception as e:
            print("\nWystąpił błąd:")
            print(str(e))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logging.exception("Błąd krytyczny")
        print("\nBłąd krytyczny:")
        print(str(exc))
        sys.exit(1)
