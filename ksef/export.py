import base64
from datetime import UTC, datetime

from config import BASE_URL, EXPORT_POLL_INTERVAL, SYMMETRIC_KEY_CERT_PATH
from ksef.export_crypto import KSeFExportCrypto
from ksef.utils import save_json


class KSeFExportClient:
    def __init__(self, http, export_dir):
        self.http = http
        self.export_dir = export_dir
        self.crypto = KSeFExportCrypto(SYMMETRIC_KEY_CERT_PATH)

    def iso_z(self, dt: datetime) -> str:
        return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def start_export(
        self,
        access_token: str,
        date_from: datetime,
        date_to: datetime,
        subject_type: str = "Subject2",
        export_key: str = "export",
    ):
        enc = self.crypto.prepare_export_encryption()

        url = f"{BASE_URL}/invoices/exports"

        headers = {"Authorization": f"Bearer {access_token}"}

        body = {
            "encryption": {
                "encryptedSymmetricKey": enc["encryptedSymmetricKey"],
                "initializationVector": enc["initializationVector"],
            },
            "filters": {
                "subjectType": subject_type,
                "dateRange": {
                    "dateType": "PermanentStorage",
                    "from": self.iso_z(date_from),
                    "to": self.iso_z(date_to),
                    "restrictToPermanentStorageHwmDate": True,
                },
            },
        }

        response = self.http.request("POST", url, headers=headers, json_body=body)
        data = response.json()

        save_json(self.export_dir / f"01_export_start_{export_key}.json", data)

        local_crypto = {
            "aes_key_b64": base64.b64encode(enc["aes_key_bytes"]).decode("ascii"),
            "iv_b64": base64.b64encode(enc["iv_bytes"]).decode("ascii"),
            "encryptedSymmetricKey": enc["encryptedSymmetricKey"],
            "initializationVector": enc["initializationVector"],
            "subjectType": subject_type,
            "exportKey": export_key,
        }

        save_json(self.export_dir / f"01a_export_crypto_local_{export_key}.json", local_crypto)

        return data

    def get_status(self, access_token: str, reference_number: str):
        url = f"{BASE_URL}/invoices/exports/{reference_number}"

        headers = {"Authorization": f"Bearer {access_token}"}

        response = self.http.request("GET", url, headers=headers)
        return response.json()

    def wait_for_export(self, access_token: str, reference_number: str, max_attempts=360):
        import time

        for attempt in range(1, max_attempts + 1):
            data = self.get_status(access_token, reference_number)
            save_json(self.export_dir / "02_export_status.json", data)

            status = data.get("status", {})
            code = status.get("code")
            desc = status.get("description", "")

            print(f"[EXPORT] próba={attempt} code={code} desc={desc}")

            if code == 200:
                return data

            if isinstance(code, int) and code >= 400 and code != 429:
                raise RuntimeError(f"Błąd eksportu: {data}")

            sleep_seconds = min(EXPORT_POLL_INTERVAL + attempt * 2, 60)
            print(f"[EXPORT] czekam {sleep_seconds}s przed kolejną próbą...")
            time.sleep(sleep_seconds)
        raise TimeoutError("Przekroczono czas oczekiwania na eksport.")

    def extract_part_urls(self, export_status: dict):
        package = export_status.get("package") or {}
        parts = package.get("parts") or []

        results = []

        for idx, part in enumerate(parts, start=1):
            url = part.get("url") or part.get("downloadUrl")

            if not url:
                continue

            results.append({"part_number": part.get("partNumber", idx), "url": url, "raw": part})

        return results
