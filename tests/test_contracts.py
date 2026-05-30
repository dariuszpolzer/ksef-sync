import pytest

from ksef.contracts import (
    KSeFContractError,
    validate_auth_challenge,
    validate_export_status,
    validate_redeem,
)


def test_validate_auth_challenge_accepts_expected_shape() -> None:
    payload = validate_auth_challenge({"challenge": "abc", "timestampMs": 123})

    assert payload["challenge"] == "abc"


def test_validate_auth_challenge_rejects_missing_timestamp() -> None:
    with pytest.raises(KSeFContractError, match="timestampMs"):
        validate_auth_challenge({"challenge": "abc"})


def test_validate_redeem_requires_access_token() -> None:
    with pytest.raises(KSeFContractError, match="accessToken.token"):
        validate_redeem({"accessToken": {}})


def test_validate_export_status_accepts_package_parts() -> None:
    payload = validate_export_status(
        {
            "status": {"code": 200, "description": "OK"},
            "package": {"invoiceCount": 1, "parts": [{"partNumber": 1}]},
        }
    )

    assert payload["package"]["invoiceCount"] == 1


def test_validate_export_status_rejects_bad_parts_type() -> None:
    with pytest.raises(KSeFContractError, match="package.parts"):
        validate_export_status({"status": {"code": 200}, "package": {"parts": {}}})
