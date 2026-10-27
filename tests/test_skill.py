"""
Drift guard for skills/txtify-transcribe: the skill hardcodes values from the
app (models, formats, extensions, status strings, language codes). If one of
those changes here, these fail so the skill (and its Agensi listing) gets
updated too. The real workflow is exercised by scripts/skill_e2e.sh.
"""

import json
import re
from pathlib import Path

import status
import utils
from deepl_languages import SOURCE_LANGUAGES, TARGET_LANGUAGES
from models import DEFAULT_MODEL, MODELS

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "txtify-transcribe"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
OPTIONS = (SKILL_DIR / "references" / "options.md").read_text(encoding="utf-8")


def _frontmatter():
    m = re.match(r"^---\n(.*?)\n---\n", SKILL, re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    return dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))


def test_frontmatter_has_agensi_fields():
    fm = _frontmatter()
    assert fm["name"] == "txtify-transcribe"
    assert re.fullmatch(r"\d+\.\d+\.\d+", fm["version"])
    for key in ("description", "summary", "tags", "keywords", "use_cases", "docs_url"):
        assert key in fm, key
    assert len(fm["summary"]) <= 300  # Agensi summary limit


def test_models_match_app():
    listed = re.search(r"\*\*Model\*\* \(`model`\): (.*?) Bigger", SKILL).group(1)
    assert set(re.findall(r"`(whisper_\w+)`", listed)) == set(MODELS)
    assert f"`{DEFAULT_MODEL}` (default)" in listed


def test_export_formats_match_download_preview():
    src = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    allowed = set(re.findall(r'"(\w+)"', re.search(r"if format not in \[(.*?)\]", src).group(1)))
    line = re.search(r"- `FMT` is one of (.*)", SKILL).group(1)
    assert set(re.findall(r"`(\w+)`", line)) - {"FMT", "v1", "v1.1"} == allowed


def test_listed_upload_types_match_app():
    line = re.search(r"File types: `([^`]*)`\. `mkv`/`avi`", SKILL).group(1)
    src = (ROOT / "src" / "utils.py").read_text(encoding="utf-8")
    accepted = re.search(r"valid_extensions = \[(.*?)\]", src).group(1)
    assert set(line.split()) | {"mkv", "avi"} == set(re.findall(r'"(\w+)"', accepted))
    assert not utils.is_valid_media_file("notes.txt")


def test_default_limits_are_unlimited():
    # The skill says newer builds default to no upload/duration limit.
    src = (ROOT / "src" / "utils.py").read_text(encoding="utf-8")
    assert 'os.getenv("MAX_UPLOAD_SIZE_MB", 0)' in src
    assert 'os.getenv("MAX_VIDEO_DURATION", 0)' in src


def test_status_json_is_compact(client):
    # The skill's poll loop matches the raw body on '"progress":"100"'.
    import main

    job = main.DB.insert_transcription("", "a.mp3", "en", "whisper_tiny", "none", "EN", "all", status.PROCESSING, "1")
    main.DB.update_transcription_status(status.COMPLETED, "2", 100, job)
    body = client.get(f"/status?pid={job}").text
    assert '"progress":"100"' in body and f'"phase":"{status.COMPLETED}"' in body


def test_status_strings_exist():
    for s in (status.COMPLETED, status.COMPLETED_TRANSLATION_FAILED, status.CANCELED, *status.IN_PROGRESS):
        assert f"`{s}`" in SKILL, s


def test_language_tables_match_app():
    asr = json.loads((ROOT / "static" / "supported_languages_ASR.json").read_text())["languages"]
    whisper = set(re.findall(r"^\| `([a-z]+)` \|", OPTIONS, re.M))
    assert whisper == set(asr)
    target = set(re.findall(r"^\| `([A-Z-]+)` \|", OPTIONS, re.M))
    assert target == set(TARGET_LANGUAGES)
    source_line = OPTIONS.split("## DeepL source languages")[1].split("##")[0]
    assert set(re.findall(r"`([A-Z-]+)`", source_line)) == set(SOURCE_LANGUAGES)


def test_relative_links_exist():
    for link in re.findall(r"\]\((?!https?://)([^)]+)\)", SKILL):
        assert (SKILL_DIR / link).exists(), link
