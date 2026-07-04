from pydantic import BaseModel, Field


class PodcastTranscriptionRequest(BaseModel):
    audio_url: str = Field(..., min_length=1, description="URL du fichier audio à transcrire")
    episode_id: str = Field(..., min_length=1, description="Identifiant unique de l'épisode (hash côté Worker)")
    language: str = Field(default="en", description="Code langue attendu (en, fr, multi)")
    model: str | None = Field(default=None, description="Modèle Deepgram (défaut: nova-3)")
    min_speakers: int | None = Field(default=None, ge=1, le=10)
    max_speakers: int | None = Field(default=None, ge=1, le=10)
    max_duration_sec: int = Field(default=3600, ge=60, le=14400, description="Durée max à transcrire (sécurité coût)")


class PodcastSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None


class PodcastTranscriptionResponse(BaseModel):
    success: bool
    episode_id: str
    transcript: str | None = None
    segments: list[PodcastSegment] = Field(default_factory=list)
    duration_sec: float | None = None
    speaker_count: int | None = None
    model: str | None = None
    error: str | None = None
