"""
Runs the exact save snippets from skills/txtify-transcribe/SKILL.md (step 6)
in `sh` against a stub HTTP server, so the filesystem-safety guarantees are
checked in CI without Docker: no write outside the approved folder (symlinks,
dangling or not), no overwrite, nothing left behind by failed or interrupted
downloads, one winner when writers race, and zips saved (after unzip -t) but
never extracted. scripts/skill_e2e.sh runs the same snippets against a real
image.
"""

import io
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "skills" / "txtify-transcribe" / "SKILL.md").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(
    not (shutil.which("curl") and shutil.which("unzip")), reason="needs curl and unzip"
)

SRT = "1\n00:00:00,032 --> 00:00:02,784\nthe quick brown fox jumps over the lazy dog.\n"


def _zip(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, SRT)
    return buf.getvalue()


GOOD_ZIP = _zip(["final_transcription.srt", "final_transcription.txt", "logs.txt"])


class Stub(BaseHTTPRequestHandler):
    """pid=1 ok, 404 not found, 7 truncated body, 9 hangs mid-body.
    /download: 1 good zip, 2 not a zip."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        pid = parse_qs(u.query).get("pid", [""])[0]
        if u.path == "/download":
            body = {"1": GOOD_ZIP, "2": b"not a zip at all"}.get(pid)
        else:
            body = SRT.encode() if pid in ("1", "7", "9") else None
        if body is None:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body) + (1000 if pid in ("7", "9") else 0)))
        self.end_headers()
        self.wfile.write(body[:10] if pid in ("7", "9") else body)
        self.wfile.flush()
        if pid == "9":
            time.sleep(30)


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _block(n):
    """Nth ```sh block under '### 6.' (indentation stripped), like skill_e2e.sh."""
    sec = SKILL.split("### 6.", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^( *)```sh\n(.*?)^\1```$", sec, re.S | re.M)
    indent, code = blocks[n - 1]
    return "\n".join(l[len(indent):] for l in code.splitlines())


SINGLE, ZIPSNIP = _block(1), _block(2)
CHECK_LINE = re.compile(r"^if \[ -e .*EXISTS.*$", re.M)


def _fill(code, base, out, job=1, name="talk"):
    assert "'" not in str(out)  # the skill forbids quotes in OUT
    return (code.replace("BASE=http://127.0.0.1:8011", f"BASE={base}")
            .replace("JOB=42", f"JOB={job}")
            .replace("OUT='/approved/folder'", f"OUT='{out}'")
            .replace("NAME=my-talk", f"NAME={name}"))


def run(code, **kw):
    r = subprocess.run(["sh", "-c", _fill(code, **kw)], capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout.strip()


def leftovers(d):
    return [p.name for p in Path(d).iterdir() if p.name.startswith(".txtify-")]


@pytest.fixture
def out(tmp_path):
    d = tmp_path / "out dir; a&b $x `y` *(z)"  # spaces + shell metacharacters
    d.mkdir()
    return d


# --- single export --------------------------------------------------------

def test_single_saves_complete_file(base, out):
    rc, msg = run(SINGLE, base=base, out=out)
    assert rc == 0 and msg.startswith("saved ")
    assert (out / "talk.srt").read_text() == SRT and not leftovers(out)


def test_single_refuses_existing_file(base, out):
    (out / "talk.srt").write_text("keep me")
    assert run(SINGLE, base=base, out=out) == (1, "EXISTS: ask the user")
    assert (out / "talk.srt").read_text() == "keep me"


@pytest.mark.parametrize("dangling", [True, False])
def test_single_refuses_symlink(base, out, tmp_path, dangling):
    target = tmp_path / "outside.srt"
    if not dangling:
        target.write_text("outside")
    (out / "talk.srt").symlink_to(target)
    assert run(SINGLE, base=base, out=out) == (1, "EXISTS: ask the user")
    assert target.exists() is (not dangling)
    if not dangling:
        assert target.read_text() == "outside"


@pytest.mark.parametrize("dangling", [True, False])
def test_single_ln_refuses_symlink_even_without_the_check(base, out, tmp_path, dangling):
    # Simulates a symlink appearing after the existence check (TOCTOU).
    target = tmp_path / "outside.srt"
    if not dangling:
        target.write_text("outside")
    (out / "talk.srt").symlink_to(target)
    rc, msg = run(CHECK_LINE.sub("", SINGLE), base=base, out=out)
    assert (rc, msg) == (1, "download failed or name taken")
    assert target.exists() is (not dangling) and not leftovers(out)
    if not dangling:
        assert target.read_text() == "outside"


def test_old_snippet_was_vulnerable(base, out, tmp_path):
    # The pre-fix snippet: '-e' misses the dangling link and 'curl -o' follows it.
    old = ("BASE=http://127.0.0.1:8011; JOB=42\nOUT='/approved/folder'; NAME=my-talk; FMT=srt\n"
           'if [ -e "$OUT/$NAME.$FMT" ]; then echo "EXISTS: ask the user"; else\n'
           '  curl -sf -o "$OUT/$NAME.$FMT" "$BASE/downloadPreview?pid=$JOB&format=$FMT"\nfi')
    target = tmp_path / "outside.srt"
    (out / "talk.srt").symlink_to(target)
    run(old, base=base, out=out)
    assert target.read_text() == SRT  # wrote outside the approved folder


@pytest.mark.parametrize("job", [404, 7])  # HTTP error, truncated body
def test_single_failed_download_leaves_nothing(base, out, job):
    assert run(SINGLE, base=base, out=out, job=job) == (1, "download failed or name taken")
    assert not (out / "talk.srt").exists() and not leftovers(out)


def test_single_interrupted_download_leaves_nothing(base, out):
    p = subprocess.Popen(["sh", "-c", _fill(SINGLE, base=base, out=out, job=9)],
                         stdout=subprocess.PIPE, start_new_session=True)
    time.sleep(1.5)
    assert leftovers(out)  # mid-download: only the temp file exists
    os.killpg(p.pid, signal.SIGINT)
    p.wait(timeout=10)
    assert not (out / "talk.srt").exists() and not leftovers(out)


def test_single_racing_writers_one_winner(base, out):
    procs = [subprocess.Popen(["sh", "-c", _fill(SINGLE, base=base, out=out)],
                              stdout=subprocess.PIPE, text=True) for _ in range(8)]
    results = [p.communicate(timeout=30)[0].strip() for p in procs]
    assert sum(r.startswith("saved ") for r in results) == 1, results
    assert (out / "talk.srt").read_text() == SRT and not leftovers(out)


def test_single_missing_or_unwritable_folder(base, out, tmp_path):
    assert run(SINGLE, base=base, out=tmp_path / "nope") == (1, "folder missing or not writable")
    assert not (tmp_path / "nope").exists()
    if os.geteuid() != 0:  # root ignores permission bits
        out.chmod(0o500)
        try:
            assert run(SINGLE, base=base, out=out) == (1, "folder missing or not writable")
        finally:
            out.chmod(0o700)


# --- zip export (saved, never extracted) --------------------------------

def test_zip_saved_not_extracted(base, out):
    rc, msg = run(ZIPSNIP, base=base, out=out)
    assert (rc, msg) == (0, f"saved {out}/talk.zip")
    assert (out / "talk.zip").read_bytes() == GOOD_ZIP
    assert sorted(p.name for p in out.iterdir()) == ["talk.zip"]  # nothing unpacked, no temp


@pytest.mark.parametrize("what", ["file", "dangling-link", "live-link"])
def test_zip_refuses_existing_name(base, out, tmp_path, what):
    target = tmp_path / "outside.zip"
    if what == "file":
        (out / "talk.zip").write_text("keep")
    else:
        if what == "live-link":
            target.write_text("outside")
        (out / "talk.zip").symlink_to(target)
    assert run(ZIPSNIP, base=base, out=out) == (1, "EXISTS: ask the user")
    assert target.exists() is (what == "live-link") and not leftovers(out)


def test_zip_ln_refuses_symlink_even_without_the_check(base, out, tmp_path):
    target = tmp_path / "outside.zip"
    (out / "talk.zip").symlink_to(target)
    assert run(CHECK_LINE.sub("", ZIPSNIP), base=base, out=out) == (1, "download failed or name taken")
    assert not target.exists() and not leftovers(out)


@pytest.mark.parametrize("job", [404, 2])  # HTTP error, not a zip
def test_zip_bad_download_saves_nothing(base, out, job):
    assert run(ZIPSNIP, base=base, out=out, job=job) == (1, "download failed or name taken")
    assert sorted(p.name for p in out.iterdir()) == []


def test_zip_racing_writers_one_winner(base, out):
    procs = [subprocess.Popen(["sh", "-c", _fill(ZIPSNIP, base=base, out=out)],
                              stdout=subprocess.PIPE, text=True) for _ in range(6)]
    results = [p.communicate(timeout=30)[0].strip() for p in procs]
    assert sum(r.startswith("saved ") for r in results) == 1, results
    assert (out / "talk.zip").read_bytes() == GOOD_ZIP and not leftovers(out)
