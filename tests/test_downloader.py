from pathlib import Path
from zipfile import ZipFile

import pytest

from ksef.downloader import KSeFDownloader


def create_test_zip(zip_path: Path, files: dict[str, str]) -> None:
    with ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def make_downloader(tmp_path: Path) -> KSeFDownloader:
    return KSeFDownloader(http=None, download_dir=tmp_path)


def test_extract_zip_extracts_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    output_dir = tmp_path / "out"
    downloader = make_downloader(tmp_path)

    create_test_zip(
        zip_path,
        {
            "invoice1.xml": "<xml>ok</xml>",
            "invoice2.xml": "<xml>ok2</xml>",
        },
    )

    downloader.extract_zip(zip_path, output_dir)

    assert (output_dir / "invoice1.xml").exists()
    assert (output_dir / "invoice2.xml").exists()


def test_extract_zip_creates_output_directory(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    output_dir = tmp_path / "new_output"
    downloader = make_downloader(tmp_path)

    create_test_zip(zip_path, {"test.txt": "hello"})

    downloader.extract_zip(zip_path, output_dir)

    assert output_dir.exists()
    assert output_dir.is_dir()


@pytest.mark.security
def test_extract_zip_blocks_zip_slip(tmp_path: Path) -> None:
    zip_path = tmp_path / "malicious.zip"
    output_dir = tmp_path / "out"
    downloader = make_downloader(tmp_path)

    create_test_zip(zip_path, {"../../evil.txt": "hacked"})

    with pytest.raises(ValueError, match="Unsafe zip entry"):
        downloader.extract_zip(zip_path, output_dir)

    assert not (tmp_path / "evil.txt").exists()


@pytest.mark.security
def test_extract_zip_blocks_sibling_prefix_escape(tmp_path: Path) -> None:
    zip_path = tmp_path / "malicious.zip"
    output_dir = tmp_path / "out"
    downloader = make_downloader(tmp_path)

    create_test_zip(zip_path, {"../out2/evil.txt": "hacked"})

    with pytest.raises(ValueError, match="Unsafe zip entry"):
        downloader.extract_zip(zip_path, output_dir)

    assert not (tmp_path / "out2" / "evil.txt").exists()
