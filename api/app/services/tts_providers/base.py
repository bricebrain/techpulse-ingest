from dataclasses import dataclass

from app.schemas.tts import TTSSynthesizeRequest


@dataclass
class ProviderSynthesisResult:
    audio_bytes: bytes
    mime_type: str
    model: str
    voice: str
    response_format: str
    provider: str


class BaseTTSProvider:
    name: str

    async def synthesize(self, payload: TTSSynthesizeRequest) -> ProviderSynthesisResult:
        raise NotImplementedError
