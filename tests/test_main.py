from datetime import UTC, datetime
from pathlib import Path

import pytest

import main


def test_period_label_for_month_mode():
    label = main.format_period_label(
        year=2026,
        month=5,
        date_from=datetime(2026, 5, 1, tzinfo=UTC),
        date_to=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert label == "Okres: 2026-05"


def test_period_label_for_days_back_mode():
    label = main.format_period_label(
        year=None,
        month=None,
        date_from=datetime(2026, 5, 4, tzinfo=UTC),
        date_to=datetime(2026, 5, 11, tzinfo=UTC),
    )

    assert label == "Zakres: 2026-05-04 - 2026-05-11"


def test_validate_period_accepts_complete_month_period():
    main.validate_period(year=2026, month=5)


def test_validate_period_rejects_partial_period():
    with pytest.raises(ValueError, match="--year i --month"):
        main.validate_period(year=2026, month=None)


def test_validate_period_rejects_invalid_month():
    with pytest.raises(ValueError, match="1-12"):
        main.validate_period(year=2026, month=13)


def test_parse_args_maps_validate_command_to_healthcheck():
    args = main.parse_args(["validate"])

    assert args.mode == "healthcheck"


def test_parse_args_maps_sync_command_to_full_sync():
    args = main.parse_args(["sync", "--year", "2026", "--month", "4"])

    assert args.mode == "full-sync"
    assert args.year == 2026
    assert args.month == 4


def test_main_returns_error_when_full_sync_has_no_parts(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "configure_logging", lambda log_dir, mode: tmp_path / "test.log")
    monkeypatch.setattr(main.config, "validate_config", lambda: None)
    monkeypatch.setattr(
        main,
        "run_full_sync",
        lambda days_back, year, month, resume_batch_id=None: False,
    )

    result = main.main(["sync", "--year", "2026", "--month", "4"])

    assert result == 2


def test_build_healthcheck_report_passes_for_minimal_local_config(tmp_path, monkeypatch):
    public_key = tmp_path / "public.pem"
    symmetric_key = tmp_path / "symmetric.pem"
    public_key.write_text("public", encoding="utf-8")
    symmetric_key.write_text("symmetric", encoding="utf-8")

    monkeypatch.setattr(main.config, "NIP", "1234567890")
    monkeypatch.setattr(main.config, "KSEF_TOKEN", "token")
    monkeypatch.setattr(main.config, "PUBLIC_KEY_PATH", str(public_key))
    monkeypatch.setattr(main.config, "SYMMETRIC_KEY_CERT_PATH", str(symmetric_key))
    monkeypatch.setattr(main.config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main.config, "AUTH_DIR", tmp_path / "data" / "auth")
    monkeypatch.setattr(main.config, "EXPORT_DIR", tmp_path / "data" / "exports")
    monkeypatch.setattr(main.config, "BATCH_DIR", tmp_path / "data" / "batches")
    monkeypatch.setattr(main.config, "LOG_DIR", tmp_path / "data" / "logs")
    monkeypatch.setattr(main.config, "GENERATE_PDF", False)
    monkeypatch.setattr(main.shutil, "which", lambda name: f"/bin/{name}" if name == "uv" else None)

    report = main.build_healthcheck_report()

    assert all(check["ok"] for check in report)


def test_build_healthcheck_report_fails_on_missing_required_config(tmp_path, monkeypatch):
    monkeypatch.setattr(main.config, "NIP", "")
    monkeypatch.setattr(main.config, "KSEF_TOKEN", "")
    monkeypatch.setattr(main.config, "PUBLIC_KEY_PATH", str(tmp_path / "missing-public.pem"))
    monkeypatch.setattr(
        main.config, "SYMMETRIC_KEY_CERT_PATH", str(tmp_path / "missing-symmetric.pem")
    )
    monkeypatch.setattr(main.config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main.config, "AUTH_DIR", tmp_path / "data" / "auth")
    monkeypatch.setattr(main.config, "EXPORT_DIR", tmp_path / "data" / "exports")
    monkeypatch.setattr(main.config, "BATCH_DIR", tmp_path / "data" / "batches")
    monkeypatch.setattr(main.config, "LOG_DIR", tmp_path / "data" / "logs")
    monkeypatch.setattr(main.config, "GENERATE_PDF", False)
    monkeypatch.setattr(main.shutil, "which", lambda name: f"/bin/{name}" if name == "uv" else None)

    report = main.build_healthcheck_report()

    failed_names = {check["name"] for check in report if not check["ok"]}

    assert "KSEF_NIP" in failed_names
    assert "KSEF_TOKEN" in failed_names
    assert "KSEF_PUBLIC_KEY_PATH file" in failed_names
    assert "KSEF_SYMMETRIC_KEY_CERT_PATH file" in failed_names


def test_find_latest_batch_dir_returns_last_sorted_directory(tmp_path: Path):
    (tmp_path / "20260101T000000Z").mkdir()
    latest = tmp_path / "20260201T000000Z"
    latest.mkdir()

    assert main.find_latest_batch_dir(tmp_path) == latest


def test_build_batch_validation_report_passes_for_complete_batch(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    invoices_dir = batch_dir / "invoices"
    pdf_dir = batch_dir / "pdf"
    invoices_dir.mkdir(parents=True)
    pdf_dir.mkdir()

    (invoices_dir / "invoice.xml").write_text("<xml />", encoding="utf-8")
    (pdf_dir / "invoice.pdf").write_bytes(b"pdf")
    (batch_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    main.save_json(
        batch_dir / "manifest.json",
        {
            "batch": {
                "invoice_count": 1,
                "ksef": {
                    "system_version": "2.0",
                    "api_version": "2.5.0",
                    "environment": "prod",
                    "base_url": "https://api.ksef.mf.gov.pl/v2",
                },
            },
            "storage": {"invoices_dir": "invoices"},
            "invoices": [{"filename": "invoice.xml"}],
            "pdf": {"error_count": 0},
        },
    )

    report = main.build_batch_validation_report(batch_dir)

    assert report["ok"] is True
    assert report["files"][0]["xml_sha256"]
    assert report["files"][0]["pdf_sha256"]


def test_build_batch_validation_report_fails_when_pdf_missing(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    invoices_dir = batch_dir / "invoices"
    invoices_dir.mkdir(parents=True)

    (invoices_dir / "invoice.xml").write_text("<xml />", encoding="utf-8")
    (batch_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    main.save_json(
        batch_dir / "manifest.json",
        {
            "batch": {
                "invoice_count": 1,
                "ksef": {
                    "system_version": "2.0",
                    "api_version": "2.5.0",
                    "environment": "prod",
                    "base_url": "https://api.ksef.mf.gov.pl/v2",
                },
            },
            "storage": {"invoices_dir": "invoices"},
            "invoices": [{"filename": "invoice.xml"}],
            "pdf": {"error_count": 0},
        },
    )

    report = main.build_batch_validation_report(batch_dir)

    failed_names = {check["name"] for check in report["checks"] if not check["ok"]}

    assert report["ok"] is False
    assert "pdf exists: invoice.pdf" in failed_names


def test_format_size_uses_readable_units():
    assert main.format_size(500) == "500.0 B"
    assert main.format_size(2048) == "2.0 KB"


def test_list_batch_summaries_reads_manifest_and_validation(tmp_path: Path):
    batch_dir = tmp_path / "20260521T000000Z"
    batch_dir.mkdir()
    main.save_json(
        batch_dir / "manifest.json",
        {
            "batch": {
                "created_at": "2026-05-21T00:00:00+00:00",
                "date_from": "2026-04-01T00:00:00+00:00",
                "date_to": "2026-05-01T00:00:00+00:00",
                "invoice_count": 5,
            }
        },
    )
    main.save_json(batch_dir / "validation_report.json", {"ok": True})

    summaries = main.list_batch_summaries(tmp_path)

    assert summaries[0]["batch_id"] == "20260521T000000Z"
    assert summaries[0]["invoice_count"] == 5
    assert summaries[0]["validated"] is True


def test_batch_dirs_older_than_returns_old_directories(tmp_path: Path, monkeypatch):
    batch_root = tmp_path / "batches"
    batch_root.mkdir()
    old_batch = batch_root / "old"
    new_batch = batch_root / "new"
    old_batch.mkdir()
    new_batch.mkdir()

    old_timestamp = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
    new_timestamp = datetime(2026, 5, 1, tzinfo=UTC).timestamp()
    import os

    os.utime(old_batch, (old_timestamp, old_timestamp))
    os.utime(new_batch, (new_timestamp, new_timestamp))

    monkeypatch.setattr(main.config, "BATCH_DIR", batch_root)

    candidates = main.batch_dirs_older_than(
        90,
        now=datetime(2026, 5, 21, tzinfo=UTC),
    )

    assert candidates == [old_batch]


def test_assert_safe_batch_delete_path_rejects_paths_outside_batch_root(tmp_path, monkeypatch):
    batch_root = tmp_path / "batches"
    outside = tmp_path / "outside"
    batch_root.mkdir()
    outside.mkdir()

    monkeypatch.setattr(main.config, "BATCH_DIR", batch_root)

    with pytest.raises(ValueError):
        main.assert_safe_batch_delete_path(outside)


def test_prepare_batch_for_jpk_skips_duplicate_xml_names(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    raw_one = tmp_path / "raw_one"
    raw_two = tmp_path / "raw_two"

    raw_one.mkdir()
    raw_two.mkdir()

    invoice_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Faktura xmlns="http://crd.gov.pl/wzor/2025/06/25/13775/">
  <Podmiot1><DaneIdentyfikacyjne><NIP>6791444505</NIP></DaneIdentyfikacyjne></Podmiot1>
  <Podmiot2><DaneIdentyfikacyjne><NIP>1234567890</NIP></DaneIdentyfikacyjne></Podmiot2>
  <Fa>
    <P_1>2026-05-01</P_1>
    <P_2>FV/1/2026</P_2>
    <FaWiersz><P_7>Usluga</P_7><P_11>100</P_11><P_12>23</P_12></FaWiersz>
  </Fa>
</Faktura>
"""
    (raw_one / "same.xml").write_text(invoice_xml, encoding="utf-8")
    (raw_two / "same.xml").write_text(
        invoice_xml.replace("FV/1/2026", "FV/2/2026"), encoding="utf-8"
    )

    manifest = main.prepare_batch_for_jpk(
        batch_dir=batch_dir,
        raw_dirs=[str(raw_one), str(raw_two)],
        batch_id="batch",
        date_from=datetime(2026, 5, 1, tzinfo=UTC),
        date_to=datetime(2026, 6, 1, tzinfo=UTC),
    )

    copied = (batch_dir / "invoices" / "same.xml").read_text(encoding="utf-8")

    assert "FV/1/2026" in copied
    assert manifest["batch"]["invoice_count"] == 1
    assert manifest["batch"]["has_duplicates"] is True
    assert manifest["batch"]["duplicate_files"] == ["same.xml"]
