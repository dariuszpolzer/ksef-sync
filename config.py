import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

KSEF_SYSTEM_VERSION = os.getenv("KSEF_SYSTEM_VERSION", "2.0")
KSEF_API_VERSION = os.getenv("KSEF_API_VERSION", "2.5.0")
KSEF_INVOICE_SCHEMA_VERSION = os.getenv("KSEF_INVOICE_SCHEMA_VERSION", "FA(3)")
KSEF_INVOICE_SCHEMA_NAMESPACE = os.getenv(
    "KSEF_INVOICE_SCHEMA_NAMESPACE",
    "http://crd.gov.pl/wzor/2025/06/25/13775/",
)

KSEF_ENVIRONMENTS = {
    "test": {
        "code": "TE",
        "name": "test",
        "api_base_url": "https://api-test.ksef.mf.gov.pl/v2",
        "uses_real_data": False,
    },
    "demo": {
        "code": "TR",
        "name": "demo",
        "api_base_url": "https://api-demo.ksef.mf.gov.pl/v2",
        "uses_real_data": True,
    },
    "prod": {
        "code": "PRD",
        "name": "prod",
        "api_base_url": "https://api.ksef.mf.gov.pl/v2",
        "uses_real_data": True,
    },
}

KSEF_ENVIRONMENT_ALIASES = {
    "te": "test",
    "test": "test",
    "integracyjne": "test",
    "tr": "demo",
    "demo": "demo",
    "preprod": "demo",
    "przedprodukcyjne": "demo",
    "prd": "prod",
    "prod": "prod",
    "production": "prod",
    "produkcyjne": "prod",
}

KSEF_ENVIRONMENT = os.getenv("KSEF_ENVIRONMENT", "prod").strip().lower()


def normalize_environment(value: str) -> str:
    env = (value or "").strip().lower()
    try:
        return KSEF_ENVIRONMENT_ALIASES[env]
    except KeyError as exc:
        allowed = ", ".join(sorted(KSEF_ENVIRONMENT_ALIASES))
        raise RuntimeError(f"Nieznane KSEF_ENVIRONMENT={value!r}. Dozwolone: {allowed}") from exc


KSEF_ENVIRONMENT = normalize_environment(KSEF_ENVIRONMENT)
BASE_URL = os.getenv("KSEF_BASE_URL", KSEF_ENVIRONMENTS[KSEF_ENVIRONMENT]["api_base_url"])
NIP = os.getenv("KSEF_NIP", "")
KSEF_TOKEN = os.getenv("KSEF_TOKEN", "")
PUBLIC_KEY_PATH = os.getenv("KSEF_PUBLIC_KEY_PATH", "./ksef_public_key.pem")
SYMMETRIC_KEY_CERT_PATH = os.getenv("KSEF_SYMMETRIC_KEY_CERT_PATH", "./ksef_symmetric_key.pem")

TAX_RUNTIME_DIR = Path(os.getenv("TAX_RUNTIME_DIR", str(Path.home() / "Documents" / "tax-runtime")))
DATA_DIR = Path(os.getenv("KSEF_DATA_DIR", str(TAX_RUNTIME_DIR / "ksef-sync" / KSEF_ENVIRONMENT)))
AUTH_DIR = Path(os.getenv("KSEF_AUTH_DIR", DATA_DIR / "auth"))
EXPORT_DIR = Path(os.getenv("KSEF_EXPORT_DIR", DATA_DIR / "exports"))
DOWNLOAD_DIR = Path(os.getenv("KSEF_DOWNLOAD_DIR", DATA_DIR / "downloads"))
BATCH_DIR = Path(os.getenv("KSEF_BATCH_DIR", DATA_DIR / "batches"))
LOG_DIR = Path(os.getenv("KSEF_LOG_DIR", DATA_DIR / "logs"))

HTTP_TIMEOUT = int(os.getenv("KSEF_HTTP_TIMEOUT", "60"))
AUTH_POLL_INTERVAL = int(os.getenv("KSEF_AUTH_POLL_INTERVAL", "2"))
EXPORT_POLL_INTERVAL = int(os.getenv("KSEF_EXPORT_POLL_INTERVAL", "20"))
PDF_TIMEOUT_SECONDS = int(os.getenv("KSEF_PDF_TIMEOUT_SECONDS", "120"))

PDF_GENERATOR_DIR = os.getenv("KSEF_PDF_GENERATOR_DIR", "./pdf_generator/ksef-pdf-generator")

GENERATE_PDF = os.getenv("GENERATE_PDF", "false").lower() == "true"


def get_environment_config() -> dict:
    env = KSEF_ENVIRONMENTS[KSEF_ENVIRONMENT].copy()
    env["base_url"] = BASE_URL
    env["api_version"] = KSEF_API_VERSION
    env["system_version"] = KSEF_SYSTEM_VERSION
    return env


def get_ksef_metadata() -> dict:
    env = get_environment_config()
    return {
        "system_version": KSEF_SYSTEM_VERSION,
        "api_version": KSEF_API_VERSION,
        "environment": env["name"],
        "environment_code": env["code"],
        "base_url": env["base_url"],
        "schemas": {
            "invoice": {
                "logical_name": KSEF_INVOICE_SCHEMA_VERSION,
                "namespace": KSEF_INVOICE_SCHEMA_NAMESPACE,
            }
        },
    }


def validate_environment_config():
    env = KSEF_ENVIRONMENTS[KSEF_ENVIRONMENT]
    expected_base = env["api_base_url"].rstrip("/")
    actual_base = BASE_URL.rstrip("/")

    if not actual_base.endswith("/v2"):
        raise RuntimeError(f"KSEF_BASE_URL musi wskazywać API v2: {BASE_URL}")

    if actual_base != expected_base:
        raise RuntimeError(
            "KSEF_BASE_URL nie pasuje do KSEF_ENVIRONMENT="
            f"{KSEF_ENVIRONMENT}. Oczekiwano {expected_base}, otrzymano {actual_base}."
        )


def validate_config():
    validate_environment_config()

    missing = []
    if not NIP:
        missing.append("KSEF_NIP")
    if not KSEF_TOKEN:
        missing.append("KSEF_TOKEN")
    if not PUBLIC_KEY_PATH:
        missing.append("KSEF_PUBLIC_KEY_PATH")
    if not SYMMETRIC_KEY_CERT_PATH:
        missing.append("KSEF_SYMMETRIC_KEY_CERT_PATH")

    if missing:
        raise RuntimeError(f"Brak ustawień: {', '.join(missing)}")

    for name, path in (
        ("KSEF_PUBLIC_KEY_PATH", PUBLIC_KEY_PATH),
        ("KSEF_SYMMETRIC_KEY_CERT_PATH", SYMMETRIC_KEY_CERT_PATH),
    ):
        if not Path(path).exists():
            raise RuntimeError(f"Plik wskazany przez {name} nie istnieje: {path}")
