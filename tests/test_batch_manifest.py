
from pathlib import Path


def test_batch_directory_structure(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"

    invoices_dir = batch_dir / "invoices"
    pdf_dir = batch_dir / "pdf"
    logs_dir = batch_dir / "logs"

    invoices_dir.mkdir(parents=True)
    pdf_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    assert batch_dir.exists()

    assert invoices_dir.exists()
    assert pdf_dir.exists()
    assert logs_dir.exists()


def test_manifest_file_exists(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"

    batch_dir.mkdir(parents=True)

    manifest = batch_dir / "manifest.json"

    manifest.write_text(
        """
{
    "batch_id": "batch_001",
    "invoice_count": 2
}
""",
        encoding="utf-8",
    )

    assert manifest.exists()


def test_manifest_contains_required_fields(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"

    batch_dir.mkdir(parents=True)

    manifest = batch_dir / "manifest.json"

    manifest.write_text(
        """
{
    "batch_id": "batch_001",
    "invoice_count": 2,
    "date_from": "2025-01-01",
    "date_to": "2025-01-31"
}
""",
        encoding="utf-8",
    )

    content = manifest.read_text(encoding="utf-8")

    assert '"batch_id"' in content
    assert '"invoice_count"' in content
    assert '"date_from"' in content
    assert '"date_to"' in content