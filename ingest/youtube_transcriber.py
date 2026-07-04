"""YouTube audio download (yt-dlp) + transcription (Whisper)."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper

        log.info("Loading Whisper small model...")
        _whisper_model = whisper.load_model("small")
        log.info("Whisper model loaded")
    return _whisper_model


def download_audio(video_url: str, output_path: str) -> bool:
    """Download audio from a YouTube video using yt-dlp."""
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format", "wav",
                "--audio-quality", "5",
                "--no-playlist",
                "--max-filesize", "100M",
                "--js-runtimes", "nodejs",
                "-o", output_path,
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            log.warning("yt-dlp failed for %s: %s", video_url, result.stderr[:200])
            return False
        return Path(output_path).exists()
    except subprocess.TimeoutExpired:
        log.warning("yt-dlp timeout for %s", video_url)
        return False
    except Exception as e:
        log.warning("yt-dlp error for %s: %s", video_url, e)
        return False


def transcribe_audio(audio_path: str, language: str | None = None) -> str | None:
    """Transcribe an audio file using Whisper."""
    try:
        model = _get_whisper_model()
        result = model.transcribe(
            audio_path,
            language=language,
            fp16=False,
        )
        text = result.get("text", "").strip()
        if len(text) < 20:
            return None
        return text
    except Exception as e:
        log.warning("Whisper error for %s: %s", audio_path, e)
        return None


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    import re

    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def transcribe_youtube_articles(articles: list[dict], max_videos: int = 4) -> list[dict]:
    """Transcribe YouTube articles. Returns list of {hash, full_text}."""
    yt_articles = [
        a for a in articles
        if (a.get("theme") == "youtube" or a.get("classified_theme") == "youtube")
        and extract_video_id(a["url"])
    ][:max_videos]

    if not yt_articles:
        log.info("No YouTube articles to transcribe")
        return []

    log.info("Transcribing %d YouTube videos...", len(yt_articles))
    results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for article in yt_articles:
            video_id = extract_video_id(article["url"])
            audio_path = os.path.join(tmpdir, f"{video_id}.wav")

            log.info("Downloading: %s", article["title"][:60])
            if not download_audio(article["url"], audio_path):
                continue

            log.info("Transcribing: %s", article["title"][:60])
            transcript = transcribe_audio(audio_path)
            if transcript:
                results.append({
                    "hash": article["hash"],
                    "full_text": transcript[:20000],
                })
                log.info("Transcribed %d chars", len(transcript))

            if os.path.exists(audio_path):
                os.remove(audio_path)

    log.info("Transcribed %d / %d videos", len(results), len(yt_articles))
    return results
