import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    allowed_origins_raw: str = "http://localhost:5173,http://127.0.0.1:5173"
    tts_provider_api_key: str | None = None
    tts_provider_base_url: str = "https://api.groq.com/openai/v1"
    tts_provider: str = "edge_tts"
    tts_default_model: str = "canopylabs/orpheus-v1-english"
    tts_default_voice: str = "autumn"
    tts_default_response_format: str = "wav"
    tts_request_timeout_sec: float = 45.0
    tts_kokoro_model_url: str | None = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx"
    tts_kokoro_voices_url: str | None = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
    tts_kokoro_model_name: str = "kokoro-v1.0.fp16.onnx"
    tts_kokoro_default_voice: str = "af_sarah"
    tts_kokoro_default_lang: str = "en-us"
    tts_kokoro_auto_download: bool = True

    # Hugging Face — Inference API (Parler-TTS, etc.)
    hf_token: str | None = None

    # Secret partagé avec le Worker Cloudflare pour sécuriser le proxy Reddit
    reddit_proxy_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def resolved_tts_api_key(self) -> str | None:
        if self.tts_provider_api_key and self.tts_provider_api_key.strip():
            return self.tts_provider_api_key.strip()

        legacy_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if legacy_key and legacy_key.strip():
            return legacy_key.strip()

        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
