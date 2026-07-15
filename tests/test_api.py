import io

import main


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_pages_render(client):
    for path in ["/", "/faq", "/contact"]:
        assert client.get(path).status_code == 200


def test_unknown_route_is_404(client):
    assert client.get("/does-not-exist").status_code == 404


def test_transcribe_invalid_youtube_url(client):
    r = client.post("/transcribe", data=_form(), files={})
    r = client.post("/transcribe", data={**_form(), "youtube_url": "http://not-youtube.com/x"})
    assert r.status_code == 400
    assert "Invalid YouTube URL" in r.json()["message"]


def test_transcribe_invalid_file_type(client):
    r = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("virus.exe", io.BytesIO(b"nope"), "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "Invalid file type" in r.json()["message"]


def test_transcribe_oversized_upload(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_SIZE_MB", 0)
    r = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("big.mp3", io.BytesIO(b"x" * 1024), "audio/mpeg")},
    )
    assert r.status_code == 400
    assert "exceeds" in r.json()["message"]


def test_transcribe_returns_job_id_and_status(client, monkeypatch):
    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: True)
    r = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("tone.mp3", io.BytesIO(b"fake-mp3"), "audio/mpeg")},
    )
    assert r.status_code == 200
    job_id = r.json()["pid"]

    r2 = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("tone.mp3", io.BytesIO(b"fake-mp3"), "audio/mpeg")},
    )
    assert r2.json()["pid"] == job_id + 1

    status = client.get(f"/status?pid={job_id}")
    assert status.status_code == 200
    assert status.json()["progress"] == "10"

    assert client.get("/status?pid=99999").status_code == 404


def test_download_endpoints_404_for_unknown_or_running_jobs(client, monkeypatch):
    assert client.get("/download?pid=99999").status_code == 404
    assert client.get("/downloadPreview?pid=99999&format=srt").status_code == 404

    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: True)
    job_id = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("tone.mp3", io.BytesIO(b"fake-mp3"), "audio/mpeg")},
    ).json()["pid"]
    # job exists but is still in progress
    assert client.get(f"/download?pid={job_id}").status_code == 404
    assert client.get(f"/downloadPreview?pid={job_id}&format=srt").status_code == 404


def test_transcribe_failure_returns_500(client, monkeypatch):
    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: False)
    r = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("tone.mp3", io.BytesIO(b"fake-mp3"), "audio/mpeg")},
    )
    assert r.status_code == 500


def _form():
    return {
        "language": "en",
        "model": "whisper_tiny",
        "translation": "none",
        "language_translation": "en",
    }
