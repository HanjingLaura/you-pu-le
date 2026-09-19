from functools import lru_cache


@lru_cache(maxsize=1)
def ffmpeg_executable() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
