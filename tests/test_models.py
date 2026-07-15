from models import save_final_transcription

SRT = (
    "1\n"
    "00:00:00,000 --> 00:00:02,000\n"
    "hello there\n"
    "\n"
    "2\n"
    "00:00:02,000 --> 00:00:04,000\n"
    "second line\n"
    "\n"
    "3\n"
    "00:00:04,000 --> 00:00:06,000\n"
    "third line\n"
)


def run(tmp_path, translated):
    srt_path = tmp_path / "in.srt"
    srt_path.write_text(SRT, encoding="utf-8")
    return save_final_transcription(
        str(srt_path), translated, str(tmp_path / "out.txt")
    )


def test_exact_match(tmp_path):
    blocks = run(tmp_path, "a\nb\nc")
    assert len(blocks) == 3
    assert "00:00:04,000 --> 00:00:06,000\nc" in blocks[2]


def test_deepl_merged_lines_pads(tmp_path):
    """Fewer translated lines than timestamps must not raise."""
    blocks = run(tmp_path, "a\nb")
    assert len(blocks) == 3


def test_padded_blocks_keep_srt_converter_aligned(tmp_path):
    """Padding must survive the srt/vtt/sbv converters: an empty pad line
    would be dropped by their filters and mispair every following block."""
    from utils import convert_to_srt

    blocks = run(tmp_path, "a\nb")  # one line short -> last block padded
    out = tmp_path / "padded.srt"
    convert_to_srt("\n".join(blocks), out)
    content = out.read_text(encoding="utf-8")
    assert "Invalid timestamp" not in content
    assert "00:00:00,000 --> 00:00:02,000\na" in content
    assert "00:00:02,000 --> 00:00:04,000\nb" in content
    assert "00:00:04,000 --> 00:00:06,000\n..." in content


def test_deepl_split_lines_merges_extras(tmp_path):
    """Extra translated lines fold into the last block instead of raising."""
    blocks = run(tmp_path, "a\nb\nc\nd\ne")
    assert len(blocks) == 3
    assert "c d e" in blocks[2]
