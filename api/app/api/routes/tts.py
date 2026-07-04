from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from app.services.tts_service import (
    TTSConfigurationError,
    TTSProviderError,
    tts_service,
)

router = APIRouter(prefix="/tts", tags=["TTS"])
bearer = HTTPBearer(auto_error=False)


def verify_secret(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> None:
    """Même secret que le proxy Reddit — sécurise les routes Worker."""
    if not settings.reddit_proxy_secret:
        return
    if not credentials or credentials.credentials != settings.reddit_proxy_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autorisé")


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def synthesize_tts(payload: TTSSynthesizeRequest) -> TTSSynthesizeResponse:
    """Endpoint app mobile — retourne audio en base64."""
    try:
        return await tts_service.synthesize(payload)
    except TTSConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/podcast-segment", dependencies=[Depends(verify_secret)])
async def synthesize_podcast_segment(
    payload: TTSSynthesizeRequest,
) -> Response:
    """
    Endpoint Worker Cloudflare — retourne les bytes audio bruts.

    Le Worker envoie le texte d'un segment + la voix ("host" | "analyst").
    Le provider par défaut est parler_hf (HF Inference API).
    La réponse est du WAV binaire, que le Worker upload directement en R2.
    """
    # Forcer parler_hf si auto
    if payload.provider == "auto":
        payload = payload.model_copy(update={"provider": "parler_hf"})

    try:
        result = await tts_service.synthesize(payload)
    except TTSConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    import base64
    audio_bytes = base64.b64decode(result.audio_base64)

    return Response(
        content=audio_bytes,
        media_type=result.mime_type,
        headers={"X-Provider": result.provider_used, "X-Voice": result.voice},
    )
