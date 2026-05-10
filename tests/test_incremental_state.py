from pathlib import Path

from ksef import sync_ksef_incremental as inc


def test_load_state_returns_empty_dict_when_file_missing(
    tmp_path: Path, monkeypatch
) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(inc, "STATE_FILE", state_file)

    state = inc.load_state()

    assert state == {}


def test_save_state_creates_file(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(inc, "STATE_FILE", state_file)

    payload = {
        "last_successful_to": "2025-01-01T00:00:00Z",
    }

    inc.save_state(payload)

    assert state_file.exists()


def test_save_and_load_state_roundtrip(tmp_path: Path, monkeypatch) -> None:
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(inc, "STATE_FILE", state_file)

    payload = {
        "last_successful_to": "2025-01-01T00:00:00Z",
        "batch_id": "batch-001",
    }

    inc.save_state(payload)
    loaded = inc.load_state()

    assert loaded == payload