import base64

from app.core.config import settings
from app.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from app.services.tts_providers.edge_provider import EdgeTTSProvider
from app.services.tts_providers.groq_provider import GroqTTSProvider
from app.services.tts_providers.parler_provider import ParlerHFProvider


class TTSConfigurationError(Exception):
    pass


class TTSProviderError(Exception):
    pass


class TTSService:
    def __init__(self) -> None:
        # Priorité : Edge-TTS (gratuit, voix neurales FR, sans clé)
        #           → Parler-HF (HF Inference API, si HF_TOKEN dispo)
        #           → Groq (Orpheus, si clé dispo)
        # Kokoro supprimé : trop lourd pour Render free (512 MB).
        # "kokoro" dans le schéma redirige vers edge_tts pour compatibilité.
        self._providers = {
            "edge_tts": EdgeTTSProvider(),
            "parler_hf": ParlerHFProvider(),
            "groq": GroqTTSProvider(),
        }

    @staticmethod
    def _normalize_provider_name(name: str | None) -> str:
        raw_name = (name or "").strip().lower()
        if raw_name in {"kokoro", "auto", ""}:
            return "edge_tts"
        return raw_name if raw_name in {"edge_tts", "parler_hf", "groq"} else "edge_tts"

    def _resolve_provider_order(self, requested_provider: str) -> list[str]:
        normalized = self._normalize_provider_name(requested_provider)
        if normalized in {"groq", "parler_hf", "edge_tts"}:
            return [normalized]

        preferred = self._normalize_provider_name(settings.tts_provider)
        return [preferred, "edge_tts"]

    async def synthesize(self, payload: TTSSynthesizeRequest) -> TTSSynthesizeResponse:
        errors: list[str] = []
        provider_order = self._resolve_provider_order(payload.provider)

        for provider_name in provider_order:
            provider = self._providers.get(provider_name)
            if not provider:
                errors.append(f"{provider_name}: provider non disponible")
                continue

            try:
                result = await provider.synthesize(payload)
                audio_base64 = base64.b64encode(result.audio_bytes).decode("utf-8")
                return TTSSynthesizeResponse(
                    audio_base64=audio_base64,
                    mime_type=result.mime_type,
                    model=result.model,
                    voice=result.voice,
                    response_format=result.response_format,
                    provider_used=result.provider,
                )
            except ValueError as exc:
                errors.append(f"{provider_name}: {exc}")
                if payload.provider == "groq":
                    raise TTSConfigurationError(str(exc)) from exc
            except RuntimeError as exc:
                errors.append(f"{provider_name}: {exc}")
                if payload.provider == "groq":
                    raise TTSProviderError(str(exc)) from exc

        if errors:
            raise TTSProviderError(" | ".join(errors))

        raise TTSProviderError("Aucun provider TTS disponible.")


tts_service = TTSService()
