from app.audio import AudioError
from app.download import validate_url
from app.jobs import is_job_id
import pytest


def test_job_id_rejects_path_traversal():
    assert is_job_id("ab" * 16)
    assert not is_job_id("../etc/passwd")
    assert not is_job_id("ABCD" * 8)
    assert not is_job_id("")


def test_validate_url_blocks_loopback():
    with pytest.raises(AudioError):
        validate_url("http://127.0.0.1/secret.mp3")
    with pytest.raises(AudioError):
        validate_url("http://localhost/secret.mp3")
