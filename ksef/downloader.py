import json
import base64
import zipfile

from pathlib import Path
from cryptography.hazmat.primitives import padding as sym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class KSeFDownloader:
    def __init__(self, http, download_dir: Path):
        self.http = http
        self.download_dir = download_dir

    def download_file(self, url: str, output_path: Path):
        response = self.http.request("GET", url, stream=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    def load_crypto_material(self, crypto_json_path: Path):
        data = json.loads(crypto_json_path.read_text(encoding="utf-8"))

        aes_key = base64.b64decode(data["aes_key_b64"])
        iv = base64.b64decode(data["iv_b64"])

        if len(aes_key) not in (16, 24, 32):
            raise ValueError(
                f"Nieprawidłowa długość klucza AES: {len(aes_key)} bajtów. "
                "Sprawdź, czy aes_key_b64 jest zapisany jako Base64, a nie hex."
            )

        if len(iv) != 16:
            raise ValueError(
                f"Nieprawidłowa długość IV: {len(iv)} bajtów. Oczekiwano 16."
            )

        return aes_key, iv

    def decrypt_aes_cbc_pkcs7(
        self,
        encrypted_path: Path,
        decrypted_zip_path: Path,
        aes_key: bytes,
        iv: bytes
    ):
        ciphertext = encrypted_path.read_bytes()

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_plain = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = sym_padding.PKCS7(128).unpadder()
        plain = unpadder.update(padded_plain) + unpadder.finalize()

        decrypted_zip_path.parent.mkdir(parents=True, exist_ok=True)
        decrypted_zip_path.write_bytes(plain)
    def extract_zip(self, zip_path: Path, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)