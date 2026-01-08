"""
LLM Context Builder - Generates project context for LLMs, respecting .gitignore.

This module provides functionality to gather all relevant files from a software
project into a single text file formatted for easy attachment to a Large Language
Model (LLM).
"""

from importlib.metadata import version

__version__ = version("llmcontext")

from llmcontext.llmcontext import (
    main,
    generate_project_context,
    is_likely_binary,
    should_exclude,
    read_gitignore_patterns,
    format_file_size,
    get_binary_metadata,
    extract_image_metadata,
    extract_wav_metadata,
    extract_audio_metadata,
    estimate_tokens,
    format_token_count,
    DEFAULT_EXCLUDES,
    BINARY_FILE_EXTENSIONS,
)

__all__ = [
    "__version__",
    "main",
    "generate_project_context",
    "is_likely_binary",
    "should_exclude",
    "read_gitignore_patterns",
    "format_file_size",
    "get_binary_metadata",
    "extract_image_metadata",
    "extract_wav_metadata",
    "extract_audio_metadata",
    "estimate_tokens",
    "format_token_count",
    "DEFAULT_EXCLUDES",
    "BINARY_FILE_EXTENSIONS",
]

if __name__ == "__main__":
    main()
