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


def test_cancel_succeeds_even_when_worker_already_dead(client, monkeypatch):
    monkeypatch.setattr(main, "handle_transcription", lambda *a, **k: True)
    job_id = client.post(
        "/transcribe",
        data=_form(),
        files={"media": ("tone.mp3", io.BytesIO(b"fake-mp3"), "audio/mpeg")},
    ).json()["pid"]

    r = client.post(f"/cancel?pid={job_id}")
    assert r.status_code == 200

    status = client.get(f"/status?pid={job_id}").json()
    assert status["phase"] == "Canceled"
    # a late worker write must not resurrect the job
    main.DB.update_transcription_status("Transcribing...", "", 40, job_id)
    assert client.get(f"/status?pid={job_id}").json()["phase"] == "Canceled"


def test_worker_argv_contract(monkeypatch, tmp_path):
    """handle_transcription's argv order must match transcribe_process.py."""
    import io as _io

    import utils

    captured = {}

    class FakeProc:
        pid = 4242

        def __init__(self, args, **kwargs):
            captured["args"] = args

    monkeypatch.setattr(utils.subprocess, "Popen", FakeProc)
    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(utils.DB, "set_process_pid", lambda *a: None)

    class FakeUpload:
        filename = "clip.mp3"
        file = _io.BytesIO(b"x" * 10)

    assert utils.handle_transcription(7, None, FakeUpload(), "en", "whisper_tiny", "none", "EL", "all")
    args = captured["args"]
    # transcribe_process.py reads: job_id, file_path, language, model,
    # translation, language_translation, file_export — in this order.
    assert args[1].endswith("transcribe_process.py")
    assert args[2] == "7"
    assert args[3].endswith("7_clip.mp3")
    assert args[4:] == ["en", "whisper_tiny", "none", "EL", "all"]


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
