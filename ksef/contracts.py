from __future__ import annotations


class KSeFContractError(RuntimeError):
    pass


def require_dict(data: object, context: str) -> dict:
    if not isinstance(data, dict):
        raise KSeFContractError(f"{context}: oczekiwano obiektu JSON")
    return data


def require_path(data: dict, path: str, expected_type: type | tuple[type, ...]) -> object:
    current: object = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KSeFContractError(f"Brak wymaganego pola w odpowiedzi KSeF: {path}")
        current = current[part]

    if not isinstance(current, expected_type):
        raise KSeFContractError(f"Nieprawidłowy typ pola KSeF {path}: {type(current).__name__}")
    return current


def validate_auth_challenge(data: object) -> dict:
    payload = require_dict(data, "auth/challenge")
    require_path(payload, "challenge", str)
    require_path(payload, "timestampMs", int)
    return payload


def validate_auth_init(data: object) -> dict:
    payload = require_dict(data, "auth/ksef-token")
    auth_token = require_path(payload, "authenticationToken", (str, dict))
    if isinstance(auth_token, dict):
        require_path(auth_token, "token", str)
    require_path(payload, "referenceNumber", str)
    return payload


def validate_auth_status(data: object) -> dict:
    payload = require_dict(data, "auth/status")
    require_path(payload, "status.code", int)
    return payload


def validate_redeem(data: object) -> dict:
    payload = require_dict(data, "auth/token/redeem")
    access_token = require_path(payload, "accessToken", (str, dict))
    if isinstance(access_token, dict):
        try:
            require_path(access_token, "token", str)
        except KSeFContractError as exc:
            raise KSeFContractError(
                "Brak wymaganego pola w odpowiedzi KSeF: accessToken.token"
            ) from exc
    return payload


def validate_export_init(data: object) -> dict:
    payload = require_dict(data, "invoices/exports")
    require_path(payload, "referenceNumber", str)
    return payload


def validate_export_status(data: object) -> dict:
    payload = require_dict(data, "invoices/exports/status")
    require_path(payload, "status.code", int)
    package = payload.get("package")
    if package is not None:
        if not isinstance(package, dict):
            raise KSeFContractError("Nieprawidłowy typ pola KSeF package")
        invoice_count = package.get("invoiceCount")
        if invoice_count is not None and not isinstance(invoice_count, int):
            raise KSeFContractError("Nieprawidłowy typ pola KSeF package.invoiceCount")
        parts = package.get("parts")
        if parts is not None and not isinstance(parts, list):
            raise KSeFContractError("Nieprawidłowy typ pola KSeF package.parts")
    return payload
