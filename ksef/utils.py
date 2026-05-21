import json
from pathlib import Path

SENSITIVE_KEY_PARTS = (
    "token",
    "authorization",
    "encryptedtoken",
    "accesstoken",
    "authenticationtoken",
    "aes_key",
    "aeskey",
    "iv_b64",
    "initializationvector",
    "encryptedSymmetricKey".lower(),
    "url",
    "downloadurl",
)


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def redact_secrets(data):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            normalized_key = str(key).replace("_", "").lower()
            if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
                result[key] = "***REDACTED***"
            else:
                result[key] = redact_secrets(value)
        return result

    if isinstance(data, list):
        return [redact_secrets(item) for item in data]

    return data


def save_json(path: Path, data, redact: bool = False):
    ensure_dir(path.parent)
    if redact:
        data = redact_secrets(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
