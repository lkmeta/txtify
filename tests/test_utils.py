import pytest

import utils

SAMPLE = (
    "1\n"
    "00:00:00,000 --> 00:00:02,000\n"
    "Hello there\n"
    "\n"
    "2\n"
    "00:00:02,000 --> 00:00:04,500\n"
    "Γειά σου κόσμε\n"
)


def test_clean_filename():
    assert utils.clean_filename("my file (1).mp3") == "my_file_1_.mp3"
    assert utils.clean_filename("a//b\\c?.mp4") == "a_b_c_.mp4"
    assert utils.clean_filename("ok-name_1.mp3") == "ok-name_1.mp3"


@pytest.mark.parametrize(
    "name,valid",
    [
        ("a.mp3", True),
        ("a.MP4", True),
        ("a.m4a", True),
        ("a.wav", True),
        ("a.webm", True),
        ("a.exe", False),
        ("a.txt", False),
    ],
)
def test_is_valid_media_file(name, valid):
    assert utils.is_valid_media_file(name) is valid


@pytest.mark.parametrize(
    "url,valid",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://youtu.be/dQw4w9WgXcQ", True),
        ("http://example.com/video", False),
        ("not a url", False),
    ],
)
def test_is_valid_youtube_url(url, valid):
    assert utils.is_valid_youtube_url(url) is valid


def test_convert_to_srt(tmp_path):
    out = tmp_path / "t.srt"
    utils.convert_to_srt(SAMPLE, out)
    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:02,000\nHello there" in content
    assert "Γειά σου κόσμε" in content


def test_convert_to_vtt(tmp_path):
    out = tmp_path / "t.vtt"
    utils.convert_to_vtt(SAMPLE, out)
    content = out.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT\n")
    assert "00:00:00,000 --> 00:00:02,000\nHello there" in content


def test_convert_to_sbv(tmp_path):
    out = tmp_path / "t.sbv"
    utils.convert_to_sbv(SAMPLE, out)
    content = out.read_text(encoding="utf-8")
    assert "00:00:00.000,00:00:02.000\nHello there" in content
    assert "00:00:02.000,00:00:04.500\nΓειά σου κόσμε" in content


def test_cleanup_files_only_touches_own_job(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "OUTPUT_DIR", tmp_path)
    (tmp_path / "1").mkdir()
    (tmp_path / "1_audio.mp3").touch()
    (tmp_path / "1_logs.txt").touch()
    (tmp_path / "1.zip").touch()
    (tmp_path / "2_other.mp3").touch()  # concurrent job's input
    (tmp_path / "2.zip").touch()
    (tmp_path / "12_other.mp3").touch()  # id prefix must not glob-collide

    utils.cleanup_files(1)

    assert not (tmp_path / "1").exists()
    assert not (tmp_path / "1_audio.mp3").exists()
    assert not (tmp_path / "1_logs.txt").exists()
    assert not (tmp_path / "1.zip").exists()
    assert (tmp_path / "2_other.mp3").exists()
    assert (tmp_path / "2.zip").exists()
    assert (tmp_path / "12_other.mp3").exists()


def test_convert_to_mp3_streams_via_ffmpeg(tmp_path):
    import shutil as _shutil
    import subprocess as _subprocess

    if not _shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    wav = tmp_path / "clip.wav"
    _subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", str(wav)],
        check=True,
    )
    mp3 = utils.convert_to_mp3(wav)
    assert mp3.suffix == ".mp3" and mp3.stat().st_size > 0
    assert not wav.exists()


def test_convert_to_pdf_preserves_unicode(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    out = tmp_path / "t.pdf"
    utils.convert_to_pdf("Γειά σου κόσμε\nПривет мир\nHello world", out)
    text = pypdf.PdfReader(out).pages[0].extract_text()
    assert "Γειά σου κόσμε" in text
    assert "Привет мир" in text
    assert "?" not in text


def test_is_valid_youtube_url_rejects_playlists_and_channels():
    assert not utils.is_valid_youtube_url(
        "https://www.youtube.com/playlist?list=PL123"
    )
    assert not utils.is_valid_youtube_url("https://www.youtube.com/@somechannel")
    assert utils.is_valid_youtube_url("https://www.youtube.com/shorts/abc123DEF")


def test_kill_process_by_pid_kills_the_process_itself():
    import subprocess as _subprocess
    import time as _time

    proc = _subprocess.Popen(["sleep", "30"])
    assert utils.kill_process_by_pid(proc.pid) is True
    proc.wait(timeout=5)
    assert proc.returncode is not None
    _time.sleep(0)
    assert utils.kill_process_by_pid(proc.pid) is False
