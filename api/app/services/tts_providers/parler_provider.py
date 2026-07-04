"""
Provider TTS Parler-TTS via HF Inference API.

Le Worker Cloudflare ne peut pas appeler HF directement (conflit Cloudflare→Cloudflare).
Ce provider sert de proxy : Worker → FastAPI (Render) → HF Parler-TTS.

Modèle : parler-tts/parler-tts-mini-v1
La voix est contrôlée via une description en texte (ex: "A warm male French voice, no reverb").
Réponse HF : WAV bytes.
"""

import httpx

from app.core.config import settings
from app.schemas.tts import TTSSynthesizeRequest
from app.services.tts_providers.base import BaseTTSProvider, ProviderSynthesisResult

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/parler-tts/parler-tts-mini-v1"

# Descriptions de voix pour les rôles podcast (en anglais — langue d'entraînement du modèle)
VOICE_DESCRIPTIONS: dict[str, str] = {
    "host": (
        "A male French voice, warm and natural, speaking in a quiet podcast studio. "
        "No reverb, no echo, dry sound. Clear articulation, steady conversational pace."
    ),
    "analyst": (
        "A male French voice, deep and authoritative, speaking in a quiet podcast studio. "
        "No reverb, no echo, dry sound. Precise and deliberate articulation."
    ),
    # Fallback générique
    "default": (
        "A clear French voice speaking in a quiet studio. No reverb, dry sound."
    ),
}


class ParlerHFProvider(BaseTTSProvider):
    name = "parler_hf"

    def _get_token(self) -> str:
        token = settings.hf_token
        if not token:
            raise ValueError("HF_TOKEN non configuré — impossible d'appeler Parler-TTS.")
        return token

    def _resolve_description(self, voice: str | None) -> str:
        if not voice:
            return VOICE_DESCRIPTIONS["default"]
        key = voice.lower().strip()
        # Accepte "host", "analyst", ou une description libre
        if key in VOICE_DESCRIPTIONS:
            return VOICE_DESCRIPTIONS[key]
        # Si c'est une description libre (> 10 chars), l'utiliser directement
        if len(voice) > 10:
            return voice
        return VOICE_DESCRIPTIONS["default"]

    async def synthesize(self, payload: TTSSynthesizeRequest) -> ProviderSynthesisResult:
        text = payload.text.strip()
        if not text:
            raise RuntimeError("Le texte à synthétiser est vide.")

        token = self._get_token()
        description = self._resolve_description(payload.voice)

        timeout = httpx.Timeout(connect=15.0, read=90.0, write=10.0, pool=10.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    HF_INFERENCE_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"inputs": text, "parameters": {"description": description}},
                )

                if response.status_code == 503:
                    # Modèle en cours de chargement — HF retourne un JSON avec estimated_time
                    raise RuntimeError(
                        "Parler-TTS se charge sur HF (503). Réessaie dans 20-30s."
                    )

                if not response.is_success:
                    body = response.text[:300]
                    raise RuntimeError(
                        f"HF Parler-TTS erreur {response.status_code}: {body}"
                    )

                audio_bytes = response.content

        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Timeout HF Parler-TTS: {exc}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Erreur réseau HF Parler-TTS: {exc}") from exc

        return ProviderSynthesisResult(
            audio_bytes=audio_bytes,
            mime_type="audio/wav",
            model="parler-tts/parler-tts-mini-v1",
            voice=payload.voice or "default",
            response_format="wav",
            provider=self.name,
        )
