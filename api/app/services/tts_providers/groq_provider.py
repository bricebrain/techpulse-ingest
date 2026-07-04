import httpx

from app.core.config import settings
from app.schemas.tts import TTSSynthesizeRequest
from app.services.tts_providers.base import BaseTTSProvider, ProviderSynthesisResult

MIME_BY_FORMAT = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "opus": "audio/ogg",
    "pcm": "audio/L16",
}


class GroqTTSProvider(BaseTTSProvider):
    name = "groq"

    async def synthesize(self, payload: TTSSynthesizeRequest) -> ProviderSynthesisResult:
        api_key = settings.resolved_tts_api_key
        if not api_key:
            raise ValueError(
                "Aucune cle TTS configuree. Definis TTS_PROVIDER_API_KEY (ou GROQ_API_KEY)."
            )

        text = payload.text.strip()
        if not text:
            raise RuntimeError("Le texte a synthetiser est vide.")

        model = payload.model.strip() if payload.model else settings.tts_default_model
        voice = payload.voice.strip() if payload.voice else settings.tts_default_voice
        response_format = payload.response_format or settings.tts_default_response_format
        endpoint = f"{settings.tts_provider_base_url.rstrip('/')}/audio/speech"

        try:
            async with httpx.AsyncClient(timeout=settings.tts_request_timeout_sec) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "voice": voice,
                        "response_format": response_format,
                        "input": text,
                    },
                )
        except httpx.HTTPError as exc:
            raise RuntimeError("Provider TTS distant indisponible temporairement.") from exc

        if response.status_code >= 400:
            if response.status_code in (401, 403):
                raise ValueError("Cle API TTS invalide ou non autorisee.")
            raise RuntimeError(f"Erreur provider TTS (status {response.status_code}).")

        audio_bytes = response.content
        if not audio_bytes:
            raise RuntimeError("Le provider TTS a retourne un flux audio vide.")

        mime_type = response.headers.get("content-type") or MIME_BY_FORMAT.get(
            response_format, "application/octet-stream"
        )

        return ProviderSynthesisResult(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            model=model,
            voice=voice,
            response_format=response_format,
            provider=self.name,
        )
