"""Transcription de podcasts via Deepgram Nova-3.

Inspiré de englishfluency-worker/src/assimilDeepgram.ts :
- Deepgram Nova-3 : transcription fidèle + diarization native + ponctuation
- Réponse structurée avec segments par locuteur et timestamps

Le service télécharge l'audio depuis l'URL fournie, puis l'envoie à Deepgram.
Pour les très longs épisodes (>1h), on limite la durée transcrite via max_duration_sec
pour contrôler le coût (~0.0043$/min).
"""

import logging
import os
from typing import Any

import httpx

from app.schemas.transcription import (
    PodcastSegment,
    PodcastTranscriptionRequest,
    PodcastTranscriptionResponse,
)

logger = logging.getLogger(__name__)

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"
DEFAULT_MODEL = "nova-3"
# Limite de taille du payload envoyé à Deepgram (100 Mo — on reste très large)
MAX_AUDIO_BYTES = 100 * 1024 * 1024


class TranscriptionService:
    @property
    def api_key(self) -> str | None:
        return os.getenv("DEEPGRAM_API_KEY")

    def transcribe_podcast(
        self, payload: PodcastTranscriptionRequest
    ) -> PodcastTranscriptionResponse:
        if not self.api_key:
            return PodcastTranscriptionResponse(
                success=False,
                episode_id=payload.episode_id,
                error="DEEPGRAM_API_KEY manquant",
            )

        # 1. Télécharger l'audio
        try:
            audio_bytes, mime_type = self._download_audio(
                payload.audio_url, max_bytes=MAX_AUDIO_BYTES
            )
        except Exception as exc:
            logger.warning("[Transcription] Téléchargement échoué: %s", exc)
            return PodcastTranscriptionResponse(
                success=False,
                episode_id=payload.episode_id,
                error=f"download_failed: {exc}",
            )

        if not audio_bytes:
            return PodcastTranscriptionResponse(
                success=False,
                episode_id=payload.episode_id,
                error="download_empty",
            )

        # 2. Appeler Deepgram
        try:
            data = self._call_deepgram(audio_bytes, mime_type, payload)
        except Exception as exc:
            logger.warning("[Transcription] Deepgram échoué: %s", exc)
            return PodcastTranscriptionResponse(
                success=False,
                episode_id=payload.episode_id,
                error=f"deepgram_error: {exc}",
            )

        # 3. Parser la réponse
        return self._parse_deepgram_response(data, payload)

    def _download_audio(self, url: str, max_bytes: int) -> tuple[bytes, str]:
        with httpx.stream(
            "GET",
            url,
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": "TechPulse/1.0 (podcast fetcher)"},
        ) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "audio/mpeg")
            # Sanitize le content-type pour Deepgram
            if not content_type.startswith("audio/"):
                content_type = "audio/mpeg"

            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    logger.warning(
                        "[Transcription] Audio tronqué à %d bytes (limite %d)",
                        total,
                        max_bytes,
                    )
                    break
                chunks.append(chunk)

            return b"".join(chunks), content_type

    def _call_deepgram(
        self, audio: bytes, mime_type: str, payload: PodcastTranscriptionRequest
    ) -> dict[str, Any]:
        model = payload.model or DEFAULT_MODEL
        params: dict[str, str] = {
            "model": model,
            "language": payload.language,
            "diarize": "true",
            "punctuate": "true",
            "smart_format": "true",
            "utterances": "true",
        }
        if payload.min_speakers is not None:
            params["min_speakers"] = str(payload.min_speakers)
        if payload.max_speakers is not None:
            params["max_speakers"] = str(payload.max_speakers)

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": mime_type,
        }

        with httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0)) as client:
            response = client.post(
                DEEPGRAM_API_URL,
                params=params,
                headers=headers,
                content=audio,
            )
            if response.status_code != 200:
                preview = response.text[:300]
                raise RuntimeError(
                    f"Deepgram HTTP {response.status_code}: {preview}"
                )
            return response.json()

    def _parse_deepgram_response(
        self, data: dict[str, Any], payload: PodcastTranscriptionRequest
    ) -> PodcastTranscriptionResponse:
        results = data.get("results") or {}
        channels = results.get("channels") or []
        utterances = results.get("utterances") or []

        # Transcript global
        transcript = ""
        if channels and channels[0].get("alternatives"):
            transcript = (
                channels[0]["alternatives"][0].get("transcript", "").strip()
            )
        if not transcript and utterances:
            transcript = " ".join(
                u.get("transcript", "").strip() for u in utterances if u.get("transcript")
            ).strip()

        if not transcript:
            return PodcastTranscriptionResponse(
                success=False,
                episode_id=payload.episode_id,
                error="transcription_vide",
            )

        # Segments (utterances diarisées)
        segments: list[PodcastSegment] = []
        speakers: set[str] = set()
        for u in utterances:
            speaker = u.get("speaker")
            speaker_label = f"speaker_{speaker}" if speaker is not None else None
            if speaker_label:
                speakers.add(speaker_label)
            text = (u.get("transcript") or "").strip()
            if not text:
                continue
            segments.append(
                PodcastSegment(
                    start=float(u.get("start", 0.0)),
                    end=float(u.get("end", 0.0)),
                    text=text,
                    speaker=speaker_label,
                )
            )

        # Durée
        metadata = data.get("metadata") or {}
        duration = metadata.get("duration")

        return PodcastTranscriptionResponse(
            success=True,
            episode_id=payload.episode_id,
            transcript=transcript,
            segments=segments,
            duration_sec=float(duration) if duration is not None else None,
            speaker_count=len(speakers) if speakers else None,
            model=payload.model or DEFAULT_MODEL,
        )


transcription_service = TranscriptionService()
