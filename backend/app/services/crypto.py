"""Encryption of face embeddings at rest (Fernet / AES-128-CBC + HMAC)."""
from pathlib import Path

import numpy as np
from cryptography.fernet import Fernet


class EmbeddingVault:
    def __init__(self, key: str, data_dir: Path):
        if not key:
            data_dir.mkdir(parents=True, exist_ok=True)
            key_file = data_dir / "embedding.key"
            if key_file.exists():
                key = key_file.read_text().strip()
            else:
                key = Fernet.generate_key().decode()
                key_file.write_text(key)
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, vector: np.ndarray) -> bytes:
        return self._fernet.encrypt(np.asarray(vector, dtype=np.float32).tobytes())

    def decrypt(self, blob: bytes) -> np.ndarray:
        return np.frombuffer(self._fernet.decrypt(blob), dtype=np.float32).copy()
