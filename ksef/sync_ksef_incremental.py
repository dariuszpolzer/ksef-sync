import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import config
from ksef.auth import KSeFAuthClient
from ksef.downloader import KSeFDownloader
from ksef.export import KSeFExportClient
from ksef.http_client import HttpClient
from ksef.pdf_generator import generate_invoice_pdfs
from ksef.utils import ensure_dir, save_json

STATE_FILE = config.DATA_DIR / "state.json"
DEFAULT_DAYS_BACK = 7
OVERLAP_MINUTES = 5


def utc_now():
    return datetime.now(UTC)


def dt_to_iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso_z_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_state():
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict):
    ensure_dir(STATE_FILE.parent)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def determine_date_range():
    state = load_state()
    now_utc = utc_now()

    last_successful_to = state.get("last_successful_to")

    if last_successful_to:
        date_from = iso_z_to_dt(last_successful_to) - timedelta(minutes=OVERLAP_MINUTES)
        first_run = False
    else:
        date_from = now_utc - timedelta(days=DEFAULT_DAYS_BACK)
        first_run = True

    return {
        "date_from": date_from,
        "date_to": now_utc,
        "state": state,
        "first_run": first_run,
    }


def prepare_batch_for_jpk(
    batch_dir: Path,
    raw_dirs: list[str],
    batch_id: str,
    date_from: datetime,
    date_to: datetime,
    export_statuses: dict,
) -> dict:
    invoices_dir = batch_dir / "invoices"
    ensure_dir(invoices_dir)

    invoices = []
    seen = set()
    duplicate_files = []

    for raw_dir_txt in raw_dirs:
        raw_dir = Path(raw_dir_txt)

        for xml_path in sorted(raw_dir.rglob("*.xml")):
            filename = xml_path.name
            nr_ksef = xml_path.stem

            if filename in seen:
                duplicate_files.append(filename)
                continue

            seen.add(filename)

            target_path = invoices_dir / filename
            shutil.copy2(xml_path, target_path)

            invoices.append(
                {
                    "filename": filename,
                    "nr_ksef": nr_ksef,
                    "source_path": str(xml_path),
                    "target_path": str(target_path),
                }
            )

    invoices.sort(key=lambda x: x["filename"])

    manifest = {
        "batch": {
            "batch_id": batch_id,
            "source": "ksef_api_incremental",
            "created_at": dt_to_iso_z(utc_now()),
            "date_from": dt_to_iso_z(date_from),
            "date_to": dt_to_iso_z(date_to),
            "invoice_count": len(invoices),
            "has_duplicates": bool(duplicate_files),
            "duplicate_files": duplicate_files,
            "exports": {
                key: {
                    "subject_type": value["subject_type"],
                    "label": value["label"],
                    "reference_number": value["reference_number"],
                    "invoice_count": value["status"].get("package", {}).get("invoiceCount", 0),
                    "status_saved": f"logs/export_status_{key}.json",
                }
                for key, value in export_statuses.items()
            },
        },
        "storage": {
            "invoices_dir": "invoices",
            "raw_dir": "raw",
            "logs_dir": "logs",
            "pdf_dir": "pdf",
        },
        "invoices": invoices,
    }

    save_json(batch_dir / "manifest.json", manifest)
    return manifest


def main():
    config.validate_config()

    ensure_dir(config.DATA_DIR)
    ensure_dir(config.AUTH_DIR)
    ensure_dir(config.EXPORT_DIR)
    ensure_dir(config.BATCH_DIR)

    range_info = determine_date_range()
    date_from = range_info["date_from"]
    date_to = range_info["date_to"]
    state = range_info["state"]
    first_run = range_info["first_run"]

    print("Tryb przyrostowy KSeF")
    if first_run:
        print(f"Brak state.json — pobieram domyślnie ostatnie {DEFAULT_DAYS_BACK} dni.")
    else:
        print("Wczytano poprzedni stan.")

    print("Zakres pobierania:")
    print("  od:", dt_to_iso_z(date_from))
    print("  do:", dt_to_iso_z(date_to))

    if date_from >= date_to:
        print("Brak nowego zakresu do pobrania.")
        return

    http = HttpClient()
    auth_client = KSeFAuthClient(http, config.AUTH_DIR)
    export_client = KSeFExportClient(http, config.EXPORT_DIR)
    downloader = KSeFDownloader(http, config.BATCH_DIR)

    print("\n1. Uwierzytelnianie...")
    auth_result = auth_client.authenticate()
    access_token = auth_result["accessToken"]["token"]
    print("   OK")

    batch_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    batch_dir = config.BATCH_DIR / batch_id
    raw_dir = batch_dir / "raw"
    invoices_dir = batch_dir / "invoices"
    logs_dir = batch_dir / "logs"
    pdf_dir = batch_dir / "pdf"

    for d in (batch_dir, raw_dir, invoices_dir, logs_dir, pdf_dir):
        ensure_dir(d)

    exports_to_run = [
        ("sales", "Subject1", "sprzedaż"),
        ("purchase", "Subject2", "zakup/koszty"),
    ]

    all_parts = []
    export_statuses = {}

    print("\n2. Start eksportów...")

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

        save_json(logs_dir / f"export_status_{export_key}.json", export_status)

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

    if not all_parts:
        print("\nBrak części paczek w obu eksportach.")
        state["last_successful_to"] = dt_to_iso_z(date_to)
        state["last_run_had_files"] = False
        state["last_batch_id"] = None
        state["last_run_at"] = dt_to_iso_z(utc_now())
        save_state(state)
        print("Zaktualizowano state.json")
        return

    print("\n4. Pobieranie, odszyfrowanie i rozpakowanie...")
    extracted_dirs = []

    for part in all_parts:
        part_number = part["part_number"]
        package_url = part["url"]
        export_key = part["export_key"]
        label = part["label"]

        part_prefix = f"{export_key}_{part_number}"

        encrypted_file = raw_dir / f"{part_prefix}.zip.aes"
        decrypted_zip = raw_dir / f"{part_prefix}.zip"
        extracted_dir = raw_dir / part_prefix

        crypto_json = config.EXPORT_DIR / f"01a_export_crypto_local_{export_key}.json"
        aes_key, iv = downloader.load_crypto_material(crypto_json)

        print(f"   {label} / Part {part_number}: pobieranie...")
        downloader.download_file(package_url, encrypted_file)

        print(f"   {label} / Part {part_number}: odszyfrowanie...")
        downloader.decrypt_aes_cbc_pkcs7(encrypted_file, decrypted_zip, aes_key, iv)

        print(f"   {label} / Part {part_number}: rozpakowanie...")
        downloader.extract_zip(decrypted_zip, extracted_dir)

        extracted_dirs.append(str(extracted_dir))

    print("\n5. Przygotowanie batcha dla ksef2jpk...")
    manifest = prepare_batch_for_jpk(
        batch_dir=batch_dir,
        raw_dirs=extracted_dirs,
        batch_id=batch_id,
        date_from=date_from,
        date_to=date_to,
        export_statuses=export_statuses,
    )

    if getattr(config, "GENERATE_PDF", False):
        print("\n6. Generowanie PDF faktur...")
        pdf_report = generate_invoice_pdfs(batch_dir)

        manifest["pdf"] = pdf_report
        save_json(batch_dir / "manifest.json", manifest)

        print(f"   PDF katalog: {pdf_report['pdf_dir']}")
        print(f"   Wygenerowano PDF: {pdf_report['generated_count']}")
        print(f"   Pominięto PDF: {pdf_report['skipped_count']}")
        print(f"   Błędy PDF: {pdf_report.get('error_count', 0)}")

    state["last_successful_to"] = dt_to_iso_z(date_to)
    state["last_run_had_files"] = True
    state["last_batch_id"] = batch_id
    state["last_run_at"] = dt_to_iso_z(utc_now())
    state["last_exports"] = {
        key: value["reference_number"] for key, value in export_statuses.items()
    }

    save_state(state)

    print("\nGotowe.")
    print("Batch:", batch_dir)
    print("Faktur XML:", manifest["batch"]["invoice_count"])
    print("Manifest:", batch_dir / "manifest.json")
    print("State:", STATE_FILE)

    for d in extracted_dirs:
        print("Rozpakowano:", d)


if __name__ == "__main__":
    main()
