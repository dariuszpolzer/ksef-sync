from pathlib import Path

from ksef.utils import ensure_dir, save_json


def test_ensure_dir_creates_directory(tmp_path: Path) -> None:
    target = tmp_path / "new_dir"

    ensure_dir(target)

    assert target.exists()
    assert target.is_dir()


def test_save_json_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    payload = {"status": "ok", "count": 2}

    save_json(target, payload)

    assert target.exists()
    assert target.read_text(encoding="utf-8")


def test_save_json_writes_expected_data(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    payload = {"status": "ok", "count": 2}

    save_json(target, payload)

    content = target.read_text(encoding="utf-8")

    assert '"status": "ok"' in content
    assert '"count": 2' in content
