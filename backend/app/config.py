"""Application settings, loaded from environment variables / backend/.env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # --- storage -----------------------------------------------------------
    data_dir: Path = BASE_DIR / "data"
    models_dir: Path = BASE_DIR / "models"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'attendance.db').as_posix()}"

    # --- security ----------------------------------------------------------
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 480
    admin_email: str = "admin@example.com"
    admin_password: str = "ChangeMe123!"
    # Fernet key used to encrypt face embeddings at rest. If empty, a key is
    # generated once and stored in data/embedding.key (keep it out of git!).
    embedding_key: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- vision ------------------------------------------------------------
    detector_score_threshold: float = 0.8
    # Cosine-similarity threshold recommended for OpenCV SFace. Re-calibrate on
    # your own data with evaluation/evaluate_lfw.py / evaluate_local.py.
    match_threshold: float = 0.363
    # Best student must beat the runner-up (a different student) by this margin.
    match_margin: float = 0.05
    min_face_px: int = 80
    min_blur_var: float = 40.0
    min_brightness: float = 50.0
    max_brightness: float = 220.0
    max_upload_bytes: int = 3_000_000
    max_embeddings_per_student: int = 30

    # --- live recognition / liveness ---------------------------------------
    votes_required: int = 3
    vote_window: int = 6
    liveness_required: bool = True
    liveness_yaw_threshold: float = 0.20
    track_ttl_seconds: float = 3.0

    # --- privacy -----------------------------------------------------------
    retention_days: int = 365

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
