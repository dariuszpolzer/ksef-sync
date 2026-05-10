from pathlib import Path
from unittest.mock import Mock

import pytest

from ksef.auth import KSeFAuthClient


class FakeResponse:
    def __init__(self, data: dict):
        self._data = data

    def json(self) -> dict:
        return self._data


def make_client(tmp_path: Path) -> tuple[KSeFAuthClient, Mock]:
    http = Mock()
    client = KSeFAuthClient(http=http, auth_dir=tmp_path)
    return client, http


def test_get_challenge_calls_auth_challenge_endpoint(tmp_path: Path) -> None:
    client, http = make_client(tmp_path)

    http.request.return_value = FakeResponse(
        {
            "challenge": "abc",
            "timestampMs": 123456,
        }
    )

    result = client.get_challenge()

    assert result["challenge"] == "abc"
    assert result["timestampMs"] == 123456
    assert (tmp_path / "01_challenge.json").exists()

    method, url = http.request.call_args.args[:2]

    assert method == "POST"
    assert url.endswith("/auth/challenge")


def test_init_auth_posts_encrypted_token(tmp_path: Path) -> None:
    client, http = make_client(tmp_path)

    http.request.return_value = FakeResponse(
        {
            "authenticationToken": "auth-token",
            "referenceNumber": "ref-001",
        }
    )

    result = client.init_auth(
        challenge="challenge-001",
        encrypted_token="encrypted-token-001",
    )

    assert result["authenticationToken"] == "auth-token"
    assert result["referenceNumber"] == "ref-001"
    assert (tmp_path / "02_auth_init.json").exists()

    method, url = http.request.call_args.args[:2]
    kwargs = http.request.call_args.kwargs

    assert method == "POST"
    assert url.endswith("/auth/ksef-token")
    assert kwargs["json_body"]["challenge"] == "challenge-001"
    assert kwargs["json_body"]["encryptedToken"] == "encrypted-token-001"
    assert kwargs["json_body"]["contextIdentifier"]["type"] == "Nip"


def test_get_auth_status_uses_bearer_token(tmp_path: Path) -> None:
    client, http = make_client(tmp_path)

    http.request.return_value = FakeResponse(
        {
            "status": {
                "code": 200,
                "description": "OK",
            }
        }
    )

    result = client.get_auth_status(
        authentication_token="auth-token",
        reference_number="ref-001",
    )

    assert result["status"]["code"] == 200

    method, url = http.request.call_args.args[:2]
    kwargs = http.request.call_args.kwargs

    assert method == "GET"
    assert url.endswith("/auth/ref-001")
    assert kwargs["headers"]["Authorization"] == "Bearer auth-token"


def test_wait_for_auth_returns_when_status_200(tmp_path: Path, monkeypatch) -> None:
    client, _http = make_client(tmp_path)

    monkeypatch.setattr(
        client,
        "get_auth_status",
        lambda authentication_token, reference_number: {
            "status": {
                "code": 200,
                "description": "OK",
            }
        },
    )

    result = client.wait_for_auth(
        authentication_token="auth-token",
        reference_number="ref-001",
        max_attempts=1,
    )

    assert result["status"]["code"] == 200
    assert (tmp_path / "03_auth_status.json").exists()


def test_wait_for_auth_raises_on_error_status(tmp_path: Path, monkeypatch) -> None:
    client, _http = make_client(tmp_path)

    monkeypatch.setattr(
        client,
        "get_auth_status",
        lambda authentication_token, reference_number: {
            "status": {
                "code": 500,
                "description": "error",
            }
        },
    )

    with pytest.raises(RuntimeError):
        client.wait_for_auth(
            authentication_token="auth-token",
            reference_number="ref-001",
            max_attempts=1,
        )


def test_wait_for_auth_times_out(tmp_path: Path, monkeypatch) -> None:
    client, _http = make_client(tmp_path)

    monkeypatch.setattr("ksef.auth.time.sleep", lambda _: None)

    monkeypatch.setattr(
        client,
        "get_auth_status",
        lambda authentication_token, reference_number: {
            "status": {
                "code": 429,
                "description": "pending",
            }
        },
    )

    with pytest.raises(TimeoutError):
        client.wait_for_auth(
            authentication_token="auth-token",
            reference_number="ref-001",
            max_attempts=2,
        )


def test_redeem_posts_bearer_token(tmp_path: Path) -> None:
    client, http = make_client(tmp_path)

    http.request.return_value = FakeResponse(
        {
            "accessToken": "access-token",
        }
    )

    result = client.redeem(authentication_token="auth-token")

    assert result["accessToken"] == "access-token"
    assert (tmp_path / "04_redeem.json").exists()

    method, url = http.request.call_args.args[:2]
    kwargs = http.request.call_args.kwargs

    assert method == "POST"
    assert url.endswith("/auth/token/redeem")
    assert kwargs["headers"]["Authorization"] == "Bearer auth-token"


def test_authenticate_runs_full_flow(tmp_path: Path, monkeypatch) -> None:
    client, _http = make_client(tmp_path)

    monkeypatch.setattr(
        client,
        "get_challenge",
        lambda: {
            "challenge": "challenge-001",
            "timestampMs": 123456,
        },
    )
    monkeypatch.setattr(
        client,
        "encrypt_token",
        lambda token, timestamp_ms: "encrypted-token-001",
    )
    monkeypatch.setattr(
        client,
        "init_auth",
        lambda challenge, encrypted_token: {
            "authenticationToken": {
                "token": "auth-token",
            },
            "referenceNumber": "ref-001",
        },
    )
    monkeypatch.setattr(
        client,
        "wait_for_auth",
        lambda authentication_token, reference_number: {
            "status": {
                "code": 200,
            }
        },
    )
    monkeypatch.setattr(
        client,
        "redeem",
        lambda authentication_token: {
            "accessToken": "access-token",
        },
    )

    result = client.authenticate()

    assert result["accessToken"] == "access-token"
