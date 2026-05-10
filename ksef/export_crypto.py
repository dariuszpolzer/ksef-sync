import base64
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


class KSeFExportCrypto:
    def __init__(self, cert_path: str):
        self.cert_path = cert_path

    def load_public_key(self):
        cert_bytes = Path(self.cert_path).read_bytes()
        cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
        return cert.public_key()

    def generate_aes_key(self) -> bytes:
        # AES-256
        return os.urandom(32)

    def generate_iv(self) -> bytes:
        # 16 bajtów dla AES-CBC
        return os.urandom(16)

    def encrypt_symmetric_key(self, aes_key: bytes) -> bytes:
        public_key = self.load_public_key()
        encrypted = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return encrypted

    def prepare_export_encryption(self) -> dict:
        aes_key = self.generate_aes_key()
        iv = self.generate_iv()
        encrypted_key = self.encrypt_symmetric_key(aes_key)

        return {
            "aes_key_bytes": aes_key,
            "iv_bytes": iv,
            "encrypted_key_bytes": encrypted_key,
            "encryptedSymmetricKey": base64.b64encode(encrypted_key).decode("ascii"),
            "initializationVector": base64.b64encode(iv).decode("ascii"),
        }
