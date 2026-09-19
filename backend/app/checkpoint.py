from __future__ import annotations

import logging

import requests

from .config import CHECKPOINT_DIR, CHECKPOINT_MIN_BYTES, CHECKPOINT_PATH, CHECKPOINT_URLS

log = logging.getLogger("keyprint")


def checkpoint_ready() -> bool:
    return CHECKPOINT_PATH.exists() and CHECKPOINT_PATH.stat().st_size >= CHECKPOINT_MIN_BYTES


def ensure_checkpoint() -> None:
    if checkpoint_ready():
        return

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = CHECKPOINT_PATH.with_suffix(".pth.part")
    log.info("Downloading piano checkpoint to %s", CHECKPOINT_PATH)
    last_error: Exception | None = None
    for url in CHECKPOINT_URLS:
        try:
            log.info("Trying checkpoint URL: %s", url)
            with requests.get(url, stream=True, timeout=120) as response:
                response.raise_for_status()
                downloaded = 0
                with tmp_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (20 * 1024 * 1024) < 1024 * 1024:
                            log.info("Checkpoint downloaded %s MB", downloaded // (1024 * 1024))
            if tmp_path.stat().st_size >= CHECKPOINT_MIN_BYTES:
                tmp_path.replace(CHECKPOINT_PATH)
                log.info("Checkpoint ready: %s MB", CHECKPOINT_PATH.stat().st_size // (1024 * 1024))
                return
            last_error = RuntimeError(f"file too small from {url}")
            tmp_path.unlink(missing_ok=True)
        except Exception as exc:
            last_error = exc
            tmp_path.unlink(missing_ok=True)
            log.warning("Checkpoint download failed from %s: %s", url, exc)

    raise RuntimeError(f"钢琴模型下载失败。请检查网络后重试。{last_error}")
