"""Transcription de podcasts via Render FastAPI (Deepgram Nova-3).

Le pipeline ingest appelle ce module après filtrage thématique :
1. Récupère les articles avec source_type='podcast' et audio_url non null
2. Filtre par mots-clés (seuls les épisodes correspondant aux thèmes suivis sont transcrits)
3. Appelle POST /api/v1/transcribe/podcast sur Render FastAPI
4. Renvoie les transcripts pour insertion dans Neon (full_text)
"""

import logging
import os
import time

import httpx

from .render_extractor import render_api_base_url, render_api_secret

log = logging.getLogger(__name__)

# Coût Deepgram ~0.0043$/min → on plafonne pour éviter les surprises
DEFAULT_MAX_EPISODES = 5
DEFAULT_MAX_DURATION_SEC = 3600  # 1h max par épisode
KEYWORD_MATCH_THRESHOLD = 1  # au moins 1 keyword dans le titre/description


def render_transcribe_timeout() -> float:
    try:
        return float(os.getenv("TECHPULSE_RENDER_TRANSCRIBE_TIMEOUT", "180"))
    except ValueError:
        return 180.0


def render_transcribe_retries() -> int:
    try:
        return max(1, int(os.getenv("TECHPULSE_RENDER_TRANSCRIBE_RETRIES", "2")))
    except ValueError:
        return 2


def filter_podcast_episodes_for_transcription(
    articles: list[dict],
    keywords: list[str] | None = None,
    max_episodes: int = DEFAULT_MAX_EPISODES,
) -> list[dict]:
    """Sélectionne les épisodes podcast à transcrire.

    Stratégie :
    - Un épisode est éligible s'il a un audio_url et pas encore de full_text
    - Si keywords est fourni, l'épisode doit contenir au moins un keyword
      dans son titre ou description (filtre anti-bruit / anti-coût)
    - Si keywords est vide ou None, on transcrit les max_episodes les plus récents
      (comportement "podcast premium suivi systématiquement")
    """
    candidates = [
        a for a in articles
        if a.get("source_type") == "podcast"
        and a.get("audio_url")
        and not a.get("full_text")
    ]

    if not candidates:
        return []

    if keywords:
        kw_lower = [k.lower().strip() for k in keywords if k.strip()]
        if kw_lower:
            matched = []
            for article in candidates:
                haystack = (
                    (article.get("title") or "") + " " + (article.get("description") or "")
                ).lower()
                if any(kw in haystack for kw in kw_lower):
                    matched.append(article)
            candidates = matched

    # Trier par published_at desc (les plus récents d'abord)
    candidates.sort(key=lambda a: a.get("published_at") or 0, reverse=True)
    return candidates[:max_episodes]


def transcribe_podcast_episodes(
    articles: list[dict],
    keywords: list[str] | None = None,
    max_episodes: int = DEFAULT_MAX_EPISODES,
) -> list[dict]:
    """Transcrit les épisodes podcast éligibles via Render FastAPI.

    Returns: liste de {id, full_text, segments_json, duration_sec, speaker_count}
    """
    base_url = render_api_base_url()
    if not base_url:
        log.warning("[Podcast] TECHPULSE_RENDER_API_URL non configuré — skip transcription")
        return []

    episodes = filter_podcast_episodes_for_transcription(
        articles, keywords=keywords, max_episodes=max_episodes
    )

    if not episodes:
        log.info("[Podcast] Aucun épisode éligible à transcrire")
        return []

    log.info("[Podcast] %d épisode(s) à transcrire", len(episodes))

    headers = {}
    secret = render_api_secret()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    import json

    results: list[dict] = []
    for episode in episodes:
        episode_id = episode["id"]
        audio_url = episode["audio_url"]

        payload = {
            "audio_url": audio_url,
            "episode_id": episode_id,
            "language": "en",  # podcasts majoritairement anglais
            "max_duration_sec": DEFAULT_MAX_DURATION_SEC,
        }

        data = None
        last_error = None
        for attempt in range(1, render_transcribe_retries() + 1):
            try:
                resp = httpx.post(
                    f"{base_url}/api/v1/transcribe/podcast",
                    headers=headers,
                    json=payload,
                    timeout=render_transcribe_timeout(),
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as exc:
                last_error = exc
                if attempt < render_transcribe_retries():
                    time.sleep(3 * attempt)

        if data is None:
            log.warning(
                "[Podcast] Transcription échouée pour %s: %s",
                episode.get("title", "")[:60],
                last_error,
            )
            continue

        if not data.get("success"):
            log.warning(
                "[Podcast] Render a renvoyé success=false pour %s: %s",
                episode.get("title", "")[:60],
                data.get("error"),
            )
            continue

        transcript = data.get("transcript") or ""
        if len(transcript) < 100:
            log.warning("[Podcast] Transcript trop court pour %s", episode.get("title", "")[:60])
            continue

        # Sérialiser les segments pour stockage (timestamps + speakers)
        segments = data.get("segments") or []
        segments_json = json.dumps(segments) if segments else None

        results.append({
            "id": episode_id,
            "full_text": transcript[:20000],
            "segments_json": segments_json,
            "duration_sec": data.get("duration_sec"),
            "speaker_count": data.get("speaker_count"),
            "extraction_method": "deepgram_podcast",
        })
        log.info(
            "[Podcast] Transcrit %d chars (%.1fs, %d speakers) — %s",
            len(transcript),
            data.get("duration_sec") or 0,
            data.get("speaker_count") or 0,
            episode.get("title", "")[:60],
        )

    log.info("[Podcast] Transcrit %d / %d épisodes", len(results), len(episodes))
    return results
