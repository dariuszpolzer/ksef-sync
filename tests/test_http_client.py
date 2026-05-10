import pytest
import responses

from ksef.http_client import HttpClient, KSeFHttpError


@responses.activate
def test_request_get_returns_response() -> None:
    responses.get(
        "https://example.com/api/test",
        json={"status": "ok"},
        status=200,
    )

    client = HttpClient(timeout=1)

    response = client.request(
        "GET",
        "https://example.com/api/test",
        retries=1,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@responses.activate
def test_request_raises_error_on_404() -> None:
    responses.get(
        "https://example.com/api/missing",
        json={"error": "not found"},
        status=404,
    )

    client = HttpClient(timeout=1)

    with pytest.raises(KSeFHttpError, match="HTTP 404"):
        client.request(
            "GET",
            "https://example.com/api/missing",
            retries=1,
        )


@responses.activate
def test_request_raises_error_on_500_after_retries() -> None:
    responses.get(
        "https://example.com/api/error",
        json={"error": "server error"},
        status=500,
    )

    client = HttpClient(timeout=1)

    with pytest.raises(KSeFHttpError):
        client.request(
            "GET",
            "https://example.com/api/error",
            retries=1,
        )


@responses.activate
def test_request_retries_429_and_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr("ksef.http_client.time.sleep", lambda _: None)

    responses.get(
        "https://example.com/api/limited",
        json={"error": "too many requests"},
        status=429,
        headers={"Retry-After": "1"},
    )
    responses.get(
        "https://example.com/api/limited",
        json={"status": "ok"},
        status=200,
    )

    client = HttpClient(timeout=1)

    response = client.request(
        "GET",
        "https://example.com/api/limited",
        retries=2,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert len(responses.calls) == 2
