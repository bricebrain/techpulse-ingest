"""Text cleaning helpers shared by ingestion and embeddings."""

import html
import re


HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
BOILERPLATE_PATTERNS = [
    re.compile(r"Article URL:\s*\S+", re.IGNORECASE),
    re.compile(r"Comments URL:\s*\S+", re.IGNORECASE),
    re.compile(r"Points:\s*\d+", re.IGNORECASE),
    re.compile(r"#\s*Comments:\s*\d+", re.IGNORECASE),
    re.compile(r"Like this video\?.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"Subscribe to .*? on YouTube:.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"Watch the latest full episodes.*$", re.IGNORECASE | re.DOTALL),
]


def clean_text(value: str | None) -> str:
    if not value:
        return ""

    text = html.unescape(value)
    text = HTML_TAG_RE.sub(" ", text)
    for pattern in BOILERPLATE_PATTERNS:
        text = pattern.sub(" ", text)
    text = text.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()


def select_representative_text(text: str, max_chars: int = 2_500) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned

    head_size = int(max_chars * 0.6)
    middle_size = int(max_chars * 0.2)
    tail_size = max_chars - head_size - middle_size
    middle_start = max(0, len(cleaned) // 2 - middle_size // 2)

    return " ".join([
        cleaned[:head_size],
        cleaned[middle_start:middle_start + middle_size],
        cleaned[-tail_size:],
    ])


def parse_engagement(text: str | None) -> tuple[int, int]:
    cleaned = html.unescape(text or "")
    points_match = re.search(r"Points:\s*(\d+)", cleaned, re.IGNORECASE)
    comments_match = re.search(r"#\s*Comments:\s*(\d+)", cleaned, re.IGNORECASE)
    points = int(points_match.group(1)) if points_match else 0
    comments = int(comments_match.group(1)) if comments_match else 0
    return points, comments
