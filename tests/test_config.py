import pytest

import config


def test_normalize_environment_accepts_aliases() -> None:
    assert config.normalize_environment("TE") == "test"
    assert config.normalize_environment("demo") == "demo"
    assert config.normalize_environment("PRD") == "prod"


def test_normalize_environment_rejects_unknown_environment() -> None:
    with pytest.raises(RuntimeError, match="Nieznane KSEF_ENVIRONMENT"):
        config.normalize_environment("sandbox")


def test_get_ksef_metadata_contains_environment_and_api_version() -> None:
    metadata = config.get_ksef_metadata()

    assert metadata["system_version"]
    assert metadata["api_version"]
    assert metadata["environment"] in {"test", "demo", "prod"}
    assert metadata["base_url"].endswith("/v2")
