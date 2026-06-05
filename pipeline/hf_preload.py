"""Preload the embedding model used by ingestion."""

import logging
import os
import time

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hf-preload")

DEFAULT_MODEL = "BAAI/bge-m3"
ALLOW_PATTERNS = [
    "*.json",
    "*.txt",
    "*.model",
    "*.safetensors",
    "*.bin",
    "modules.json",
    "sentence_bert_config.json",
    "tokenizer.*",
    "vocab.*",
    "1_Pooling/*",
]


def preload_model(model_id: str, token: str | None, attempts: int = 4) -> None:
    try:
        snapshot_download(
            repo_id=model_id,
            allow_patterns=ALLOW_PATTERNS,
            local_files_only=True,
        )
        log.info("%s already available in local cache", model_id)
        return
    except LocalEntryNotFoundError:
        log.info("%s not fully cached, downloading", model_id)

    for attempt in range(1, attempts + 1):
        try:
            snapshot_download(
                repo_id=model_id,
                allow_patterns=ALLOW_PATTERNS,
                token=token,
                max_workers=1,
                resume_download=True,
            )
            log.info("%s downloaded", model_id)
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            sleep_seconds = min(90, 10 * 2 ** (attempt - 1))
            log.warning(
                "%s download failed on attempt %d/%d: %s. Retrying in %ds",
                model_id,
                attempt,
                attempts,
                exc,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)


def main() -> None:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    model_id = os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)
    preload_model(model_id, token)


if __name__ == "__main__":
    main()
