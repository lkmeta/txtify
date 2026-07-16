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
    r = client.post(
        "/transcribe", data={**_form(), "youtube_url": "http://not-youtube.com/x"}
    )
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


def test_transcribe_requires_url_or_file(client):
    r = client.post("/transcribe", data=_form())
    assert r.status_code == 400
    assert "YouTube URL or a media file" in r.json()["message"]


def test_transcribe_rejects_unsupported_translation_combo(client):
    # source language whisper supports but DeepL doesn't
    r = client.post(
        "/transcribe",
        data={**_form(), "language": "hi", "translation": "deepl",
              "language_translation": "EN"},
        files={"media": ("a.mp3", io.BytesIO(b"x"), "audio/mpeg")},
    )
    assert r.status_code == 400
    assert "not supported" in r.json()["message"]

    # invalid target language
    r = client.post(
        "/transcribe",
        data={**_form(), "translation": "deepl", "language_translation": "XX"},
        files={"media": ("a.mp3", io.BytesIO(b"x"), "audio/mpeg")},
    )
    assert r.status_code == 400


def test_transcribe_allows_auto_source_translation(client, monkeypatch):
    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: True)
    r = client.post(
        "/transcribe",
        data={**_form(), "language": "auto", "translation": "deepl",
              "language_translation": "EL"},
        files={"media": ("a.mp3", io.BytesIO(b"x"), "audio/mpeg")},
    )
    assert r.status_code == 200


def test_transcribe_busy_returns_429(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_CONCURRENT_JOBS", 0)
    r = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("a.mp3", io.BytesIO(b"x"), "audio/mpeg")},
    )
    assert r.status_code == 429


def _completed_job(client, monkeypatch, tmp_path):
    """Insert a completed job with real export files in a temp OUTPUT_DIR."""
    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: True)
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    job_id = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("a.mp3", io.BytesIO(b"x"), "audio/mpeg")},
    ).json()["pid"]
    main.DB.update_transcription_status("Completed successfully!", "2.0", 100, job_id)
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    for ext in ("txt", "srt", "vtt", "sbv"):
        (job_dir / f"final_transcription.{ext}").write_text(
            f"content-{ext}", encoding="utf-8"
        )
    return job_id


def test_download_preview_serves_final_files(client, monkeypatch, tmp_path):
    job_id = _completed_job(client, monkeypatch, tmp_path)
    for fmt in ("txt", "srt", "vtt", "sbv"):
        r = client.get(f"/downloadPreview?pid={job_id}&format={fmt}")
        assert r.status_code == 200, fmt
        assert r.content.decode() == f"content-{fmt}"


def test_preview_missing_files_is_404(client, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    r = client.get("/preview?pid=12345")
    assert r.status_code == 404
    assert "Preview not found" in r.json()["message"]


def test_cancel_completed_job_is_400_and_keeps_files(client, monkeypatch, tmp_path):
    job_id = _completed_job(client, monkeypatch, tmp_path)
    r = client.post(f"/cancel?pid={job_id}")
    assert r.status_code == 400
    assert (tmp_path / str(job_id) / "final_transcription.txt").exists()


def test_cancel_running_job_marks_canceled(client, monkeypatch):
    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: True)
    monkeypatch.setattr(main, "kill_process_by_pid", lambda pid: False)
    monkeypatch.setattr(main, "cleanup_files", lambda pid: None)
    job_id = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("a.mp3", io.BytesIO(b"x"), "audio/mpeg")},
    ).json()["pid"]
    r = client.post(f"/cancel?pid={job_id}")
    assert r.status_code == 200
    assert main.DB.get_transcription(job_id)[8] == "Canceled"
