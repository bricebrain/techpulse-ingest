"""
Provider TTS Microsoft Edge-TTS.

Utilise les voix neurales Microsoft via le même service que Edge browser.
Gratuit, sans clé API, voix françaises excellentes.

Voix podcast :
  host     → fr-FR-HenriNeural  (masculin, chaleureux)
  analyst  → fr-FR-HenriNeural  (même voix — Remy trop monotone)
  default  → fr-FR-HenriNeural

Sortie : MP3 (format natif Edge-TTS).
"""

import io

import edge_tts

from app.schemas.tts import TTSSynthesizeRequest
from app.services.tts_providers.base import BaseTTSProvider, ProviderSynthesisResult

VOICE_MAP: dict[str, str] = {
    "host":    "fr-FR-HenriNeural",
    "analyst": "fr-FR-HenriNeural",
    "default": "fr-FR-HenriNeural",
}


def _resolve_voice(voice: str | None) -> str:
    if not voice:
        return VOICE_MAP["default"]
    key = voice.lower().strip()
    return VOICE_MAP.get(key, VOICE_MAP["default"])


class EdgeTTSProvider(BaseTTSProvider):
    name = "edge_tts"

    async def synthesize(self, payload: TTSSynthesizeRequest) -> ProviderSynthesisResult:
        text = payload.text.strip()
        if not text:
            raise RuntimeError("Le texte à synthétiser est vide.")

        voice = _resolve_voice(payload.voice)

        # Rate optionnel via speed (0.5 → -50%, 2.0 → +100%)
        rate_pct = int((payload.speed - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"

        try:
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate_str)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
            audio_bytes = buffer.getvalue()
        except Exception as exc:
            raise RuntimeError(f"Edge-TTS erreur: {exc}") from exc

        if not audio_bytes:
            raise RuntimeError("Edge-TTS n'a retourné aucun audio.")

        return ProviderSynthesisResult(
            audio_bytes=audio_bytes,
            mime_type="audio/mpeg",
            model="edge-tts",
            voice=voice,
            response_format="mp3",
            provider=self.name,
        )
