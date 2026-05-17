import subprocess  # nosec B404
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RENDER_SCRIPT = BASE_DIR / "pdf_generator" / "render_invoice.mjs"


def generate_invoice_pdfs(batch_dir: Path) -> dict:
    batch_dir = Path(batch_dir).resolve()

    invoices_dir = batch_dir / "invoices"
    pdf_dir = batch_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    skipped = []
    errors = []

    for xml_path in sorted(invoices_dir.glob("*.xml")):
        xml_path = xml_path.resolve()
        pdf_path = (pdf_dir / f"{xml_path.stem}.pdf").resolve()

        if pdf_path.exists():
            skipped.append(
                {
                    "xml": str(xml_path),
                    "pdf": str(pdf_path),
                    "reason": "PDF already exists",
                }
            )
            continue

        cmd = ["node", str(RENDER_SCRIPT), str(xml_path), str(pdf_path)]

        try:
            result = subprocess.run(  # nosec B603
                cmd,
                check=False,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr or result.stdout or "Node PDF generator failed")

            if pdf_path.exists():
                generated.append(
                    {
                        "xml": str(xml_path),
                        "pdf": str(pdf_path),
                    }
                )
            else:
                errors.append(
                    {
                        "xml": str(xml_path),
                        "pdf": str(pdf_path),
                        "error": "Node finished, but PDF file was not created",
                    }
                )

        except Exception as e:
            errors.append(
                {
                    "xml": str(xml_path),
                    "pdf": str(pdf_path),
                    "error": str(e),
                }
            )

    return {
        "pdf_dir": str(pdf_dir),
        "generated_count": len(generated),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "generated": generated,
        "skipped": skipped,
        "errors": errors,
    }
