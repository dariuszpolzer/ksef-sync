import json
from pathlib import Path

from ksef.contracts import (
    validate_auth_challenge,
    validate_auth_init,
    validate_auth_status,
    validate_export_init,
    validate_export_status,
    validate_redeem,
)

FIXTURE_DIR = Path("tests/fixtures/json/ksef_api")


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_ksef_api_contract_fixtures_match_validators() -> None:
    cases = [
        ("auth_challenge_response.json", validate_auth_challenge),
        ("auth_init_response.json", validate_auth_init),
        ("auth_status_response.json", validate_auth_status),
        ("auth_redeem_response.json", validate_redeem),
        ("export_init_response.json", validate_export_init),
        ("export_status_response.json", validate_export_status),
        ("export_status_empty_response.json", validate_export_status),
    ]

    for filename, validator in cases:
        payload = load_fixture(filename)
        assert validator(payload) == payload


def test_ksef_rate_limit_fixture_has_retry_contract() -> None:
    payload = load_fixture("rate_limit_429.json")

    assert payload["http_status"] == 429
    assert int(payload["headers"]["Retry-After"]) > 0
    assert payload["body"]["status"]["code"] == 429
