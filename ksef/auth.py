import base64
import time
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from config import AUTH_POLL_INTERVAL, BASE_URL, KSEF_TOKEN, NIP, PUBLIC_KEY_PATH
from ksef.http_client import HttpClient
from ksef.utils import save_json


class KSeFAuthClient:
    def __init__(self, http: HttpClient, auth_dir):
        self.http = http
        self.auth_dir = auth_dir

    def load_public_key(self):
        cert_bytes = Path(PUBLIC_KEY_PATH).read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
        return cert.public_key()

    def get_challenge(self):
        url = f"{BASE_URL}/auth/challenge"
        response = self.http.request("POST", url)
        data = response.json()
        save_json(self.auth_dir / "01_challenge.json", data)
        return data

    def encrypt_token(self, token: str, timestamp_ms: int) -> str:
        payload = f"{token}|{timestamp_ms}".encode()
        public_key = self.load_public_key()

        encrypted = public_key.encrypt(
            payload,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(encrypted).decode("ascii")

    def init_auth(self, challenge: str, encrypted_token: str):
        url = f"{BASE_URL}/auth/ksef-token"
        body = {
            "challenge": challenge,
            "contextIdentifier": {"type": "Nip", "value": NIP},
            "encryptedToken": encrypted_token,
        }
        response = self.http.request("POST", url, json_body=body)
        data = response.json()
        save_json(self.auth_dir / "02_auth_init.json", data)
        return data

    def get_auth_status(self, authentication_token: str, reference_number: str):
        url = f"{BASE_URL}/auth/{reference_number}"
        headers = {"Authorization": f"Bearer {authentication_token}"}
        response = self.http.request("GET", url, headers=headers)
        return response.json()

    def wait_for_auth(self, authentication_token: str, reference_number: str, max_attempts=90):
        for attempt in range(1, max_attempts + 1):
            data = self.get_auth_status(authentication_token, reference_number)
            save_json(self.auth_dir / "03_auth_status.json", data)

            status = data.get("status", {})
            code = status.get("code")
            desc = status.get("description", "")
            print(f"[AUTH] próba={attempt} code={code} desc={desc}")

            if code == 200:
                return data

            if isinstance(code, int) and code >= 400 and code != 429:
                raise RuntimeError(f"Błąd uwierzytelnienia: {data}")

            time.sleep(AUTH_POLL_INTERVAL)

        raise TimeoutError("Przekroczono czas oczekiwania na zakończenie uwierzytelnienia.")

    def redeem(self, authentication_token: str):
        url = f"{BASE_URL}/auth/token/redeem"
        headers = {"Authorization": f"Bearer {authentication_token}"}
        response = self.http.request("POST", url, headers=headers)
        data = response.json()
        save_json(self.auth_dir / "04_redeem.json", data)
        return data

    def authenticate(self):
        challenge_data = self.get_challenge()
        challenge = challenge_data["challenge"]
        timestamp_ms = challenge_data["timestampMs"]

        encrypted_token = self.encrypt_token(KSEF_TOKEN, timestamp_ms)
        auth_init = self.init_auth(challenge, encrypted_token)

        # authentication_token = auth_init["authenticationToken"]
        # reference_number = auth_init["referenceNumber"]
        auth_token_data = auth_init["authenticationToken"]

        if isinstance(auth_token_data, dict):
            authentication_token = auth_token_data["token"]
        else:
            authentication_token = auth_token_data

        reference_number = auth_init["referenceNumber"]
        self.wait_for_auth(authentication_token, reference_number)
        redeem_data = self.redeem(authentication_token)
        return redeem_data
