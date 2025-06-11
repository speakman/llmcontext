import base64
from pathlib import Path
import sys
import subprocess
import llmcontext.llmcontext as lc

# Base64 encoded minimal image and audio files
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
GIF_B64 = "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
BMP_B64 = "Qk06AAAAAAAAADYAAAAoAAAAAQAAAAEAAAABABgAAAAAAAQAAADEDgAAxA4AAAAAAAAAAAAAAAAAAA=="
JPEG_B64 = "/9j/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/yQALCAABAAEBAREA/8wABgAQEAX/2gAIAQEAAD8A0s8g/9k="
WAV_B64 = "UklGRjQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YRAAAAAAAAAAAAAAAAAAAAAAAAAA"

def write_binary(path: Path, data_b64: str) -> Path:
    data = base64.b64decode(data_b64)
    path.write_bytes(data)
    return path

def test_extract_image_metadata(tmp_path: Path) -> None:
    png = write_binary(tmp_path / "img.png", PNG_B64)
    gif = write_binary(tmp_path / "img.gif", GIF_B64)
    bmp = write_binary(tmp_path / "img.bmp", BMP_B64)
    jpg = write_binary(tmp_path / "img.jpg", JPEG_B64)

    assert lc.extract_image_metadata(png) == {"Format": "PNG", "Width": "1", "Height": "1"}
    assert lc.extract_image_metadata(gif) == {"Format": "GIF", "Width": "1", "Height": "1"}
    assert lc.extract_image_metadata(bmp) == {"Format": "BMP", "Width": "1", "Height": "1"}
    assert lc.extract_image_metadata(jpg) == {"Format": "JPEG", "Width": "1", "Height": "1"}

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

    ctx = lc.generate_project_context(tmp_path, [], None, False)
    assert "Format: PNG" in ctx
    assert "Format: WAV" in ctx
    assert "hello" in ctx

    out_file = tmp_path / "out.txt"
    proc = subprocess.run(
        [sys.executable, "-m", "llmcontext", str(tmp_path), str(out_file)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert out_file.read_text().startswith("--- START PROJECT CONTEXT ---")
