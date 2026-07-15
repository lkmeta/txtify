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


def test_convert_to_pdf_preserves_unicode(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    out = tmp_path / "t.pdf"
    utils.convert_to_pdf("Γειά σου κόσμε\nПривет мир\nHello world", out)
    text = pypdf.PdfReader(out).pages[0].extract_text()
    assert "Γειά σου κόσμε" in text
    assert "Привет мир" in text
    assert "?" not in text
