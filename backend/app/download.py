from __future__ import annotations

import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse

import requests

from .audio import AudioError
from .config import ALLOWED_SUFFIXES, MAX_UPLOAD_BYTES
from .ffmpeg_bin import ffmpeg_executable

log = logging.getLogger("keyprint")


def validate_url(raw: str) -> str:
    url = raw.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AudioError("请粘贴有效的 http 或 https 链接。")
    host = parsed.hostname
    if not host:
        raise AudioError("请粘贴有效的 http 或 https 链接。")
    if host.lower() in {"localhost"}:
        raise AudioError("不能拉取内网地址。")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise AudioError("这个链接解析不了。") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or not ip.is_global:
            raise AudioError("不能拉取内网地址。")
    return url


def download_source(url: str, dest_dir: Path) -> Path:
    url = validate_url(url)
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in ALLOWED_SUFFIXES:
        return _download_direct(url, dest_dir / f"source{suffix}")
    return _download_with_ytdlp(url, dest_dir)


def _download_direct(url: str, dest: Path) -> Path:
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        size = 0
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    dest.unlink(missing_ok=True)
                    raise AudioError("文件超过 80MB。请先剪短或压一下。")
                handle.write(chunk)
    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise AudioError("链接里没有下到文件。")
    return dest


def _download_with_ytdlp(url: str, dest_dir: Path) -> Path:
    ffmpeg_dir = str(Path(ffmpeg_executable()).parent)
    output = str(dest_dir / "source.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": output,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "overwrites": True,
        "max_filesize": MAX_UPLOAD_BYTES,
        "ffmpeg_location": ffmpeg_dir,
    }
    try:
        import yt_dlp
    except ImportError as exc:
        raise AudioError("本机还没有 yt-dlp，链接着不下来。") from exc

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
    except Exception as exc:
        raise AudioError("这个链接下不下来。请换 YouTube / B 站 / 音频直链，或直接上传文件。") from exc

    sources = [path for path in dest_dir.glob("source.*") if path.is_file()]
    if not sources:
        raise AudioError("链接里没有下到音频。")
    return sources[0]
