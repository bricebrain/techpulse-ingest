from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.schemas.transcription import (
    PodcastTranscriptionRequest,
    PodcastTranscriptionResponse,
)
from app.services.transcription_service import transcription_service

router = APIRouter(prefix="/transcribe", tags=["Transcription"])
bearer = HTTPBearer(auto_error=False)


def verify_secret(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> None:
    if not settings.reddit_proxy_secret:
        return
    if not credentials or credentials.credentials != settings.reddit_proxy_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autorisé"
        )


@router.post(
    "/podcast",
    response_model=PodcastTranscriptionResponse,
    dependencies=[Depends(verify_secret)],
)
async def transcribe_podcast(
    payload: PodcastTranscriptionRequest,
) -> PodcastTranscriptionResponse:
    """Transcrit un épisode podcast via Deepgram Nova-3.

    Appelé par le pipeline ingest (GitHub Actions) après filtrage thématique.
    Renvoie le transcript complet + segments diarisés avec timestamps.
    """
    return transcription_service.transcribe_podcast(payload)
