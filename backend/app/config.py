from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "jobs"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MAX_DURATION_SEC = 180
MAX_UPLOAD_BYTES = 80 * 1024 * 1024
SAMPLE_RATE = 16000
SPLIT_MIDI = 60  # C4: treble above, bass below

ALLOWED_SUFFIXES = {
    ".mp4",
    ".mov",
    ".webm",
    ".mkv",
    ".avi",
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".aac",
}

CHECKPOINT_DIR = Path.home() / "piano_transcription_inference_data"
CHECKPOINT_PATH = CHECKPOINT_DIR / "note_F1=0.9677_pedal_F1=0.9186.pth"
CHECKPOINT_URLS = [
    "https://hf-mirror.com/Genius-Society/piano_trans/resolve/main/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=true",
    "https://huggingface.co/Genius-Society/piano_trans/resolve/main/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=true",
    "https://zenodo.org/record/4034264/files/CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1",
]
CHECKPOINT_MIN_BYTES = 160_000_000
