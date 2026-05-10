import json
from pathlib import Path

from ksef.build_index import build_batch_index


def create_manifest(batch_dir: Path) -> None:
    manifest = {
        "batch": {
            "batch_id": batch_dir.name,
            "invoice_count": 1,
        },
        "invoices": [
            {
                "filename": "invoice_1.xml",
                "nr_ksef": "KSEF-TEST-001",
            }
        ],
    }

    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def create_invoice(batch_dir: Path, with_pdf: bool = True) -> None:
    invoices_dir = batch_dir / "invoices"
    pdf_dir = batch_dir / "pdf"

    invoices_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    (invoices_dir / "invoice_1.xml").write_text(
        "<xml>invoice</xml>",
        encoding="utf-8",
    )

    if with_pdf:
        (pdf_dir / "invoice_1.pdf").write_text(
            "fake pdf",
            encoding="utf-8",
        )


def test_build_batch_index_creates_html(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"
    batch_dir.mkdir()

    create_invoice(batch_dir)
    create_manifest(batch_dir)

    build_batch_index(batch_dir)

    assert (batch_dir / "index.html").exists()


def test_build_batch_index_contains_invoice_links(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"
    batch_dir.mkdir()

    create_invoice(batch_dir)
    create_manifest(batch_dir)

    build_batch_index(batch_dir)

    content = (batch_dir / "index.html").read_text(encoding="utf-8")

    assert "invoice_1.xml" in content
    assert "invoice_1.pdf" in content
    assert "KSEF-TEST-001" in content


def test_build_batch_index_handles_missing_pdf(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"
    batch_dir.mkdir()

    create_invoice(batch_dir, with_pdf=False)
    create_manifest(batch_dir)

    build_batch_index(batch_dir)

    content = (batch_dir / "index.html").read_text(encoding="utf-8")

    assert "invoice_1.xml" in content
    assert "KSEF-TEST-001" in content