from datetime import UTC, datetime
from pathlib import Path

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


def test_prepare_batch_for_jpk_skips_duplicate_xml_names(tmp_path: Path):
    batch_dir = tmp_path / "batch"
    raw_one = tmp_path / "raw_one"
    raw_two = tmp_path / "raw_two"

    raw_one.mkdir()
    raw_two.mkdir()

    (raw_one / "same.xml").write_text("<xml>first</xml>", encoding="utf-8")
    (raw_two / "same.xml").write_text("<xml>second</xml>", encoding="utf-8")

    manifest = main.prepare_batch_for_jpk(
        batch_dir=batch_dir,
        raw_dirs=[str(raw_one), str(raw_two)],
        batch_id="batch",
        date_from=datetime(2026, 5, 1, tzinfo=UTC),
        date_to=datetime(2026, 6, 1, tzinfo=UTC),
    )

    copied = (batch_dir / "invoices" / "same.xml").read_text(encoding="utf-8")

    assert copied == "<xml>first</xml>"
    assert manifest["batch"]["invoice_count"] == 1
    assert manifest["batch"]["has_duplicates"] is True
    assert manifest["batch"]["duplicate_files"] == ["same.xml"]
