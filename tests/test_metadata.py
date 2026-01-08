import base64
from pathlib import Path
import sys
import subprocess
import llmcontext.llmcontext as lc

# Base64 encoded minimal image and audio files
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
GIF_B64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
BMP_B64 = (
    "Qk06AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABABgAAAAAAAQAAADEDgAAxA4AAAAAAAAAAAAAAAAAAA=="
)
JPEG_B64 = "/9j/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/yQALCAABAAEBAREA/8wABgAQEAX/2gAIAQEAAD8A0s8g/9k="
WAV_B64 = (
    "UklGRjQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YRAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def write_binary(path: Path, data_b64: str) -> Path:
    data = base64.b64decode(data_b64)
    path.write_bytes(data)
    return path


def test_extract_image_metadata(tmp_path: Path) -> None:
    png = write_binary(tmp_path / "img.png", PNG_B64)
    gif = write_binary(tmp_path / "img.gif", GIF_B64)
    bmp = write_binary(tmp_path / "img.bmp", BMP_B64)
    jpg = write_binary(tmp_path / "img.jpg", JPEG_B64)

    assert lc.extract_image_metadata(png) == {
        "Format": "PNG",
        "Width": "1",
        "Height": "1",
    }
    assert lc.extract_image_metadata(gif) == {
        "Format": "GIF",
        "Width": "1",
        "Height": "1",
    }
    assert lc.extract_image_metadata(bmp) == {
        "Format": "BMP",
        "Width": "1",
        "Height": "1",
    }
    assert lc.extract_image_metadata(jpg) == {
        "Format": "JPEG",
        "Width": "1",
        "Height": "1",
    }


def test_extract_wav_metadata(tmp_path: Path) -> None:
    wav = write_binary(tmp_path / "sound.wav", WAV_B64)
    meta = lc.extract_wav_metadata(wav)
    assert meta and meta["Format"] == "WAV"
    assert meta["Channels"] == "1"
    assert meta["SampleRate"] == "8000"


def test_generate_context_and_cli(tmp_path: Path) -> None:
    write_binary(tmp_path / "img.png", PNG_B64)
    write_binary(tmp_path / "sound.wav", WAV_B64)
    (tmp_path / "hello.txt").write_text("hello")

    # Test compact format (default)
    ctx = lc.generate_project_context(tmp_path, [], None, False)
    assert "[BINARY:" in ctx  # Compact binary format
    assert "hello" in ctx

    out_file = tmp_path / "out.txt"
    proc = subprocess.run(
        [sys.executable, "-m", "llmcontext", str(tmp_path), str(out_file)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert out_file.read_text().startswith("# Project Context")

    # Test standard format
    ctx_std = lc.generate_project_context(
        tmp_path, [], None, False, output_format="standard"
    )
    assert "Format: PNG" in ctx_std
    assert "Format: WAV" in ctx_std
    assert "--- START PROJECT CONTEXT ---" in ctx_std


def test_estimate_tokens() -> None:
    """Test token estimation with default heuristic."""
    assert lc.estimate_tokens("") == 0
    assert lc.estimate_tokens("a" * 4) == 1
    assert lc.estimate_tokens("a" * 100) == 25
    assert lc.estimate_tokens("hello world") == 2  # 11 chars / 4 = 2


def test_estimate_tokens_model_specific() -> None:
    """Test model-specific token estimation heuristics."""
    text = "x" * 100

    # Default (GPT-like): chars/4
    assert lc.estimate_tokens(text) == 25

    # Claude: chars/3.5 = 28.57 -> 28
    assert lc.estimate_tokens(text, model="claude") == 28
    assert lc.estimate_tokens(text, model="Claude-3-Sonnet") == 28
    assert lc.estimate_tokens(text, model="anthropic-claude") == 28

    # Llama: chars/3.8 = 26.31 -> 26
    assert lc.estimate_tokens(text, model="llama") == 26
    assert lc.estimate_tokens(text, model="llama-3.1-70b") == 26
    assert lc.estimate_tokens(text, model="meta-llama") == 26

    # GPT models use default
    assert lc.estimate_tokens(text, model="gpt-4") == 25
    assert lc.estimate_tokens(text, model="gpt-4-turbo") == 25

    # Gemini uses same as GPT
    assert lc.estimate_tokens(text, model="gemini") == 25
    assert lc.estimate_tokens(text, model="gemini-3") == 25
    assert lc.estimate_tokens(text, model="google-gemini-pro") == 25


def test_format_token_count() -> None:
    """Test token count formatting."""
    assert lc.format_token_count(0) == "0"
    assert lc.format_token_count(999) == "999"
    assert lc.format_token_count(1000) == "1.0K"
    assert lc.format_token_count(1500) == "1.5K"
    assert lc.format_token_count(999_999) == "1000.0K"
    assert lc.format_token_count(1_000_000) == "1.00M"
    assert lc.format_token_count(1_500_000) == "1.50M"


def test_format_file_size() -> None:
    """Test file size formatting."""
    assert lc.format_file_size(0) == "0 B"
    assert lc.format_file_size(1023) == "1023 B"
    assert lc.format_file_size(1024) == "1.0 KB"
    assert lc.format_file_size(1536) == "1.5 KB"
    assert lc.format_file_size(1024 * 1024) == "1.0 MB"
    assert lc.format_file_size(int(1024 * 1024 * 1.5)) == "1.5 MB"


def test_max_tokens_skips_large_files(tmp_path: Path) -> None:
    """Test that --max-tokens skips files that would exceed the budget."""
    # Create a small file and a large file
    (tmp_path / "small.txt").write_text("x" * 100)  # ~25 tokens
    (tmp_path / "large.txt").write_text("y" * 1000)  # ~250 tokens

    # With max_tokens=100, only the small file should be included
    ctx = lc.generate_project_context(tmp_path, [], None, False, max_tokens=100)
    assert "small.txt" in ctx
    assert "large.txt" not in ctx


# --- Format Function Tests ---


def test_format_project_header() -> None:
    """Test project header formatting."""
    assert lc.format_project_header("compact") == "# Project Context\n"
    assert lc.format_project_header("standard") == "--- START PROJECT CONTEXT ---"


def test_format_project_footer() -> None:
    """Test project footer formatting."""
    assert lc.format_project_footer("compact") == ""
    assert lc.format_project_footer("standard") == "--- END PROJECT CONTEXT ---"


def test_format_file_header() -> None:
    """Test file header formatting."""
    assert lc.format_file_header("src/main.py", "compact") == "## FILE: src/main.py"
    assert (
        lc.format_file_header("src/main.py", "standard")
        == "--- START FILE: src/main.py ---"
    )


def test_format_file_footer() -> None:
    """Test file footer formatting."""
    assert lc.format_file_footer("src/main.py", "compact") == ""
    assert "END FILE" in lc.format_file_footer("src/main.py", "standard")


def test_format_binary_metadata_compact_image() -> None:
    """Test compact binary metadata for images."""
    meta = {"Format": "PNG", "Width": "256", "Height": "256"}
    result = lc.format_binary_metadata("logo.png", meta, "45.3 KB", "compact")
    assert result == ["[BINARY: PNG 256×256, 45.3 KB]"]


def test_format_binary_metadata_compact_audio() -> None:
    """Test compact binary metadata for audio with duration."""
    meta = {"Format": "WAV", "Duration": "2.34s", "Channels": "2"}
    result = lc.format_binary_metadata("sound.wav", meta, "1.2 MB", "compact")
    assert result == ["[BINARY: WAV 2.34s, 1.2 MB]"]


def test_format_binary_metadata_compact_no_meta() -> None:
    """Test compact binary metadata without extra metadata."""
    result = lc.format_binary_metadata("data.bin", None, "100 KB", "compact")
    assert result == ["[BINARY: 100 KB]"]


def test_format_binary_metadata_standard() -> None:
    """Test standard binary metadata format."""
    meta = {"Format": "PNG", "Width": "256", "Height": "256"}
    result = lc.format_binary_metadata("logo.png", meta, "45.3 KB", "standard")
    assert "--- BINARY FILE METADATA ---" in result
    assert "Path: logo.png" in result
    assert "Size: 45.3 KB" in result
    assert "Format: PNG" in result
    assert "Width: 256" in result


def test_compact_output_is_smaller(tmp_path: Path) -> None:
    """Verify compact format produces smaller output than standard."""
    (tmp_path / "test.py").write_text("print('hello world')")
    (tmp_path / "utils.py").write_text("def helper(): pass")

    compact = lc.generate_project_context(tmp_path, [], None, output_format="compact")
    standard = lc.generate_project_context(tmp_path, [], None, output_format="standard")

    assert len(compact) < len(standard)
