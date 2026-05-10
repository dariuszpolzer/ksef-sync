from pathlib import Path
from unittest.mock import patch

from ksef.pdf_generator import generate_invoice_pdfs


def test_generate_invoice_pdfs_calls_subprocess(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch_001"
    invoices_dir = batch_dir / "invoices"
    pdf_dir = batch_dir / "pdf"

    invoices_dir.mkdir(parents=True)
    pdf_dir.mkdir(parents=True)

    (invoices_dir / "invoice_1.xml").write_text(
        "<xml>invoice</xml>",
        encoding="utf-8",
    )

    with patch("ksef.pdf_generator.subprocess.run") as mock_run:
        generate_invoice_pdfs(batch_dir)

        mock_run.assert_called_once()


def test_generate_invoice_pdfs_handles_empty_invoice_dir(
    tmp_path: Path,
) -> None:
    batch_dir = tmp_path / "batch_001"
    invoices_dir = batch_dir / "invoices"

    invoices_dir.mkdir(parents=True)

    with patch("ksef.pdf_generator.subprocess.run") as mock_run:
        generate_invoice_pdfs(batch_dir)

        mock_run.assert_not_called()
