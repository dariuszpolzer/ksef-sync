import argparse
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import config
from ksef.auth import KSeFAuthClient
from ksef.build_index import build_batch_index
from ksef.downloader import KSeFDownloader
from ksef.export import KSeFExportClient
from ksef.http_client import HttpClient
from ksef.pdf_generator import generate_invoice_pdfs
from ksef.utils import ensure_dir, save_json


def print_menu():
    print("\nWybierz tryb:")
    print("1 - tylko uwierzytelnienie")
    print("2 - eksport za podany zakres dni")
    print("3 - pełny jednorazowy sync (auth -> export -> download -> decrypt -> unzip)")
    print("4 - wyjście")


# print("4 - uruchom sync_ksef_incremental.py")
# print("5 - wyjście")


def run_auth_only():
    ensure_dir(config.AUTH_DIR)

    http = HttpClient()
    auth_client = KSeFAuthClient(http, config.AUTH_DIR)

    result = auth_client.authenticate()
    print("\nUwierzytelnienie OK")
    print(json.dumps(result, ensure_ascii=False, indent=2))


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
    save_json(config.EXPORT_DIR / "03_export_status_final.json", export_status)

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

    for raw_dir_txt in raw_dirs:
        raw_dir = Path(raw_dir_txt)

        for xml_path in raw_dir.rglob("*.xml"):
            filename = xml_path.name
            target_path = invoices_dir / filename

            shutil.copy2(xml_path, target_path)

            nr_ksef = filename[:-4] if filename.lower().endswith(".xml") else filename

            invoices.append(
                {
                    "filename": filename,
                    "nr_ksef": nr_ksef,
                    "source_path": str(xml_path),
                    "target_path": str(target_path),
                }
            )

    invoices.sort(key=lambda x: x["filename"])

    duplicate_names = []
    seen = set()

    for inv in invoices:
        if inv["filename"] in seen:
            duplicate_names.append(inv["filename"])
        seen.add(inv["filename"])

    manifest = {
        "batch": {
            "batch_id": batch_id,
            "source": "ksef_api_export",
            "created_at": datetime.now(UTC).isoformat(),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "invoice_count": len(invoices),
            "has_duplicates": bool(duplicate_names),
            "duplicate_files": duplicate_names,
            "export_status_saved": "logs/03_export_status_final.json",
        },
        "storage": {
            "invoices_dir": "invoices",
            "raw_dir": "raw",
            "logs_dir": "logs",
        },
        "invoices": invoices,
    }

    save_json(batch_dir / "manifest.json", manifest)

    return manifest


def run_full_sync(days_back: int, year: int | None = None, month: int | None = None):
    ensure_dir(config.DATA_DIR)
    ensure_dir(config.AUTH_DIR)
    ensure_dir(config.EXPORT_DIR)
    ensure_dir(config.BATCH_DIR)

    http = HttpClient()
    auth_client = KSeFAuthClient(http, config.AUTH_DIR)
    export_client = KSeFExportClient(http, config.EXPORT_DIR)
    downloader = KSeFDownloader(http, config.BATCH_DIR)

    print("\n1. Uwierzytelnianie...")
    auth_result = auth_client.authenticate()
    access_token = auth_result["accessToken"]["token"]
    print("   OK")

    if year and month:
        date_from = datetime(year, month, 1, tzinfo=UTC)

        if month == 12:
            date_to = datetime(year + 1, 1, 1, tzinfo=UTC)
        else:
            date_to = datetime(year, month + 1, 1, tzinfo=UTC)
    else:
        date_to = datetime.now(UTC)
        date_from = date_to - timedelta(days=days_back)

    batch_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    batch_dir = config.BATCH_DIR / batch_id
    raw_dir = batch_dir / "raw"
    invoices_dir = batch_dir / "invoices"
    logs_dir = batch_dir / "logs"

    for d in (batch_dir, raw_dir, invoices_dir, logs_dir):
        ensure_dir(d)

    exports_to_run = [
        ("sales", "Subject1", "sprzedaż"),
        ("purchase", "Subject2", "zakup/koszty"),
    ]

    all_parts = []
    export_statuses = {}

    print("2. Start eksportów...")

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
        print("Brak części paczek w obu eksportach.")
        return

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

        print(f"   {part['label']} / Part {part_number}: pobieranie...")
        downloader.download_file(package_url, encrypted_file)

        print(f"   {part['label']} / Part {part_number}: odszyfrowanie...")
        downloader.decrypt_aes_cbc_pkcs7(encrypted_file, decrypted_zip, aes_key, iv)

        print(f"   {part['label']} / Part {part_number}: rozpakowanie...")
        downloader.extract_zip(decrypted_zip, extracted_dir)

        extracted_dirs.append(str(extracted_dir))

    print("\nGotowe.")
    print("Katalog batch:", batch_dir)

    for d in extracted_dirs:
        print("Rozpakowano:", d)

    print("\n5. Przygotowanie paczki dla ksef2jpk...")
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
        print("\n6. Generowanie PDF faktur...")

        pdf_report = generate_invoice_pdfs(batch_dir)

        manifest["pdf"] = pdf_report
        save_json(batch_dir / "manifest.json", manifest)

        print(f"   PDF katalog: {pdf_report['pdf_dir']}")
        print(f"   Wygenerowano PDF: {pdf_report['generated_count']}")
        print(f"   Pominięto PDF: {pdf_report['skipped_count']}")

        # subprocess.run(cmd, check=True)

        manifest["pdf"] = pdf_report
        save_json(batch_dir / "manifest.json", manifest)

        print(f"Okres: {year}-{month:02d}")
        print(f"   PDF katalog: {pdf_report['pdf_dir']}")
        print(f"   Wygenerowano PDF: {pdf_report['generated_count']}")
        print(f"   Pominięto PDF: {pdf_report['skipped_count']}")

        index_file = build_batch_index(batch_dir)
        print(f"   Index HTML: {index_file}")


def run_incremental_sync():
    import sync_ksef_incremental

    sync_ksef_incremental.main()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument(
        "--mode",
        choices=["menu", "auth", "export", "full-sync"],
        default="menu",
    )
    parser.add_argument("--days-back", type=int, default=7)

    args = parser.parse_args()

    config.validate_config()

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

    if args.mode == "auth":
        run_auth_only()
        return

    if args.mode == "export":
        run_export_only(args.days_back)
        return

    if args.mode == "full-sync":
        run_full_sync(
            days_back=args.days_back,
            year=year,
            month=month,
        )
        return

    while True:
        print_menu()
        choice = input("Twój wybór: ").strip()

        try:
            if choice == "1":
                run_auth_only()

            elif choice == "2":
                raw = input("Ile dni wstecz pobrać? [np. 7]: ").strip()
                days_back = int(raw or "7")
                run_export_only(days_back)

            elif choice == "3":
                raw = input("Ile dni wstecz pobrać? [np. 7]: ").strip()
                days_back = int(raw or "7")
                run_full_sync(days_back)

            elif choice == "4":
                print("Koniec.")
                break

            else:
                print("Nieznana opcja.")

        except Exception as e:
            print("\nWystąpił błąd:")
            print(str(e))


if __name__ == "__main__":
    main()
