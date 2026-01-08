# Changelog

All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-01-08
### Added
- Token tracking with `chars/4` estimation
- `--max-tokens` CLI flag to skip files exceeding token budget
- Token count warnings at 128K, 200K, and 1M thresholds
- Always show token count in output
- CI linting with ruff and mypy
- New tests for token and formatting functions

### Changed
- Removed defensive exception handling - errors now surface clearly
- Removed ImportError fallbacks for Pillow/mutagen (required dependencies)
- Refactored `should_exclude()` into smaller helper functions for clarity

## [0.2.4] - 2025-05-25
### Fixed
- Python 3.9 type hints compatibility

## [0.2.3] - 2025-05-25
### Fixed
- CI workflow conditions for Python 3.8/3.9 compatibility

## [0.2.2] - 2025-05-25
### Fixed
- CI workflow improvements and pipx compatibility

## [0.2.1] - 2025-05-25
### Fixed
- UTF-8 encoding errors
- GitHub release automation

## [0.2.0] - 2025-05-25
### Added
- Enhanced verbose mode with detailed statistics:
  - Excluded files and directories summary
  - Top 10 largest files by size
  - File type distribution
  - Total size of processed files

## [0.1.1] - 2025-05-24
### Added
- `__main__` module for `python -m llmcontext`
- Logging instead of `print` for verbose output
- Warning when generated context exceeds ~1M tokens

## [0.1.0] - 2025-05-23

### Added

- Initial release
- Basic functionality for collecting project files
- Respects .gitignore patterns
- Binary file detection
- Binary file metadata extraction for common image and audio formats using Python modules only
- Markdown-formatted output for LLMs
- Command-line interface with basic options
- Detailed prompting system with --show-prompt option
