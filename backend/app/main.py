"""FastAPI application factory."""
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .config import Settings, get_settings
from .database import Base, make_session_factory
from .models import User
from .routers import auth, courses, privacy, recognition, reports, sessions, students
from .security import hash_password
from .services.crypto import EmbeddingVault
from .services.face_engine import OpenCVFaceEngine
from .services.matcher import Gallery

log = logging.getLogger("attendance")


class LazyEngine:
    """Loads the ONNX models on first use so the API can start (and tests can run)
    before the models are downloaded."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._engine = None
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            if self._engine is None:
                self._engine = OpenCVFaceEngine(self._settings.models_dir, self._settings.detector_score_threshold)
            return self._engine


def create_app(settings: Settings | None = None, engine_provider=None) -> FastAPI:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    if settings.secret_key == "dev-only-change-me":
        log.warning("SECRET_KEY is the insecure default - set a real one in backend/.env")

    engine, session_factory = make_session_factory(settings.database_url)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Face Attendance API", version="2.0.0")
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.vault = EmbeddingVault(settings.embedding_key, settings.data_dir)
    app.state.gallery = Gallery(app.state.vault, settings.match_threshold, settings.match_margin)
    app.state.engine_provider = engine_provider or LazyEngine(settings)
    app.state.trackers = {}

    with session_factory() as db:  # seed the first admin
        if db.scalar(select(User).limit(1)) is None:
            db.add(
                User(
                    email=settings.admin_email.lower(),
                    name="Administrator",
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            db.commit()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (auth, students, courses, sessions, recognition, reports, privacy):
        app.include_router(r.router)

    @app.get("/api/health")
    def health():
        try:
            app.state.engine_provider()
            models = True
        except Exception:
            models = False
        return {"status": "ok", "models_loaded": models}

    return app


def get_app() -> FastAPI:
    """Entry point for:  uvicorn app.main:get_app --factory --reload"""
    return create_app()
