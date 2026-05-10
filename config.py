import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("KSEF_BASE_URL", "https://api.ksef.mf.gov.pl/v2")
NIP = os.getenv("KSEF_NIP", "")
KSEF_TOKEN = os.getenv("KSEF_TOKEN", "")
PUBLIC_KEY_PATH = os.getenv("KSEF_PUBLIC_KEY_PATH", "./ksef_public_key.pem")
SYMMETRIC_KEY_CERT_PATH = os.getenv("KSEF_SYMMETRIC_KEY_CERT_PATH", "./ksef_symmetric_key.pem")

DATA_DIR = Path("./data")
AUTH_DIR = DATA_DIR / "auth"
EXPORT_DIR = DATA_DIR / "exports"
DOWNLOAD_DIR = DATA_DIR / "downloads"
BATCH_DIR = DATA_DIR / "batches"

HTTP_TIMEOUT = 60
AUTH_POLL_INTERVAL = 2
EXPORT_POLL_INTERVAL = 20

PDF_GENERATOR_DIR = os.getenv("KSEF_PDF_GENERATOR_DIR", "./pdf_generator/ksef-pdf-generator")

GENERATE_PDF = os.getenv("GENERATE_PDF", "false").lower() == "true"


def validate_config():
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
