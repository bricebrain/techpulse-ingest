from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.ai import router as ai_router
from app.api.routes.tts import router as tts_router
from app.api.routes.reddit import router as reddit_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.transcription import router as transcription_router
from app.core.config import settings


def create_application() -> FastAPI:
    app = FastAPI(
        title="TechPulse API",
        description="Backend FastAPI pour modules IA FinTech/ESG",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["System"])
    async def root() -> dict[str, str]:
        return {"message": "TechPulse API is running"}

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(ai_router, prefix="/api/v1")
    app.include_router(tts_router, prefix="/api/v1")
    app.include_router(reddit_router, prefix="/api/v1")
    app.include_router(extraction_router, prefix="/api/v1")
    app.include_router(transcription_router, prefix="/api/v1")

    return app


app = create_application()
