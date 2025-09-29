"""
LLM Context Builder main implementation.

This module contains the core functionality for gathering project files
and formatting them for use with LLMs.
"""

import os
import argparse
import fnmatch
import pathlib
import sys
import traceback
import wave
import logging
from PIL import Image
from mutagen import File as _mutagen_file

logger = logging.getLogger(__name__)

# --- Configuration ---

# fmt: off
DEFAULT_EXCLUDES = [
    # Version control
    ".git", ".svn", ".hg", ".bzr",
    
    # Python environments and build artifacts
    "__pycache__", "*.pyc", "*.pyo", "*.pyd",
    ".pytest_cache", ".mypy_cache", ".tox",
    ".venv", "venv", "ENV", "env", "virtualenv",
    "venv.bak", "env.bak",
    
    # System files
    ".DS_Store", "Thumbs.db", "desktop.ini",
    
    # Compiled binaries
    "*.so", "*.o", "*.a", "*.dylib",
    "*.dll", "*.exe",
    
    # Language-specific artifacts
    "*.class", "*.jar", "*.war", "*.ear",  # Java
    "node_modules", "package-lock.json",   # Node.js
    "yarn.lock", "pnpm-lock.yaml",
    "vendor/bundle", ".bundle",            # Ruby
    "Gemfile.lock", "vendor", "composer.lock",  # PHP
    
    # Secrets and configs
    ".env", ".env.*", "*.pem", "*.key",
    
    # Build outputs
    "build", "dist", "target", "out",
    "bin", "release", "Debug", "Release",
    
    # Temporary files
    "*.log", "*.log.*", "*.tmp", "*.temp",
    "*.swp", "*.swo", "*.bak", "*.old",
    
    # IDE configurations
    ".idea", ".vscode", "*.sublime-workspace",
    "*.sublime-project", ".project",
    ".classpath", ".settings", "nbproject",
    
    # Documentation and coverage
    "coverage", ".coverage", "docs/_build", "site"
]
# fmt: on

BINARY_CHECK_CHUNK_SIZE = 1024

# Common binary file extensions
# fmt: off
BINARY_FILE_EXTENSIONS = [
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".ico", ".webp", ".svg",
    # Audio
    ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a",
    # Video
    ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv",
    # Documents
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    # Archives
    ".zip", ".rar", ".tar", ".gz", ".7z", ".bz2", ".xz",
    # Executables
    ".exe", ".dll", ".so", ".dylib", ".bin",
    # Database
    ".db", ".sqlite", ".sqlite3", ".mdb",
    # Other
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
]
# fmt: on

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv"}


def is_likely_binary(filepath: pathlib.Path) -> bool:
    """Determine if a file is likely binary through extension and content analysis.

    Args:
        filepath: Path to the file to check

    Returns:
        True if binary detection heuristics match, False otherwise
    """
    # Check by extension first (faster)
    if filepath.suffix.lower() in BINARY_FILE_EXTENSIONS:
        return True

    # Then check content if extension check didn't match
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(BINARY_CHECK_CHUNK_SIZE)
        return b"\x00" in chunk
    except OSError:
        return True
    except Exception:
        return True


def should_exclude(
    path_obj_rel: pathlib.Path,
    path_obj_abs: pathlib.Path,
    gitignore_patterns: list[str],
    default_excludes: list[str],
    additional_cli_excludes: list[str],
) -> tuple[bool, str]:
    """Determine if a path should be excluded based on exclusion patterns.

    Returns tuple of (exclusion_decision, reason_string)
    """
    path_name = path_obj_rel.name
    path_str_rel_posix = path_obj_rel.as_posix()

    # Check default exclusion patterns
    for pattern in default_excludes:
        if (
            fnmatch.fnmatch(path_name, pattern)
            or path_name == pattern
            or pattern in path_obj_rel.parts
        ):
            return True, f"Default exclude: {pattern}"

    for pattern_val in additional_cli_excludes:
        if fnmatch.fnmatch(path_str_rel_posix, pattern_val):
            return True, f"CLI Exclude (path: {pattern_val})"
        if fnmatch.fnmatch(path_name, pattern_val):
            return True, f"CLI Exclude (name: {pattern_val})"

    is_current_item_dir = path_obj_abs.is_dir()
    for git_pattern_orig in gitignore_patterns:
        git_pattern = git_pattern_orig.strip()
        if not git_pattern or git_pattern.startswith("#"):
            continue

        anchored_pattern = git_pattern.startswith("/")
        if anchored_pattern:
            git_pattern = git_pattern.lstrip("/")

        is_dir_pattern = git_pattern.endswith("/")
        if is_dir_pattern:
            git_pattern = git_pattern.rstrip("/")

        if anchored_pattern:
            if path_str_rel_posix == git_pattern or path_str_rel_posix.startswith(
                git_pattern + "/"
            ):
                if is_dir_pattern:
                    return True, f".gitignore (anchored dir: {git_pattern_orig})"
                elif path_str_rel_posix == git_pattern:
                    return True, f".gitignore (anchored file: {git_pattern_orig})"
        else:
            if is_dir_pattern:
                if path_name == git_pattern and is_current_item_dir:
                    return True, f".gitignore (unanchored dir name: {git_pattern_orig})"
                try:
                    idx = path_obj_rel.parts.index(git_pattern)
                    if idx < len(path_obj_rel.parts) - 1:
                        return (
                            True,
                            f".gitignore (in unanchored dir: {git_pattern_orig})",
                        )
                    elif is_current_item_dir:
                        return (
                            True,
                            f".gitignore (unanchored dir itself: {git_pattern_orig})",
                        )
                except ValueError:
                    pass
            else:
                if "/" in git_pattern:
                    if fnmatch.fnmatch(path_str_rel_posix, git_pattern):
                        return (
                            True,
                            f".gitignore (relative path pattern: {git_pattern_orig})",
                        )
                else:
                    if fnmatch.fnmatch(path_name, git_pattern):
                        return (
                            True,
                            f".gitignore (basename pattern: {git_pattern_orig})",
                        )
    return False, ""


def read_gitignore_patterns(root_dir: pathlib.Path) -> list[str]:
    patterns = []
    gitignore_path = root_dir / ".gitignore"
    if gitignore_path.exists() and gitignore_path.is_file():
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        patterns.append(stripped)
        except OSError as e:
            logger.warning("Could not read .gitignore: %s", e)
    return patterns


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def extract_image_metadata(filepath: pathlib.Path) -> dict[str, str] | None:
    """Extract basic image geometry using Pillow."""
    if filepath.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    try:
        with Image.open(filepath) as img:
            width, height = img.size
            return {
                "Format": img.format or filepath.suffix.lstrip(".").upper(),
                "Width": str(width),
                "Height": str(height),
            }
    except Exception:
        return None


def extract_audio_metadata(filepath: pathlib.Path) -> dict[str, str] | None:
    """Extract basic audio metadata using the wave module or mutagen."""
    if filepath.suffix.lower() not in AUDIO_EXTENSIONS:
        return None
    if filepath.suffix.lower() == ".wav":
        return extract_wav_metadata(filepath)
    try:
        m = _mutagen_file(str(filepath))
        if m is None or not hasattr(m, "info"):
            return None
        info = m.info
        meta: dict[str, str] = {"Format": filepath.suffix.lstrip(".").upper()}
        if hasattr(info, "channels"):
            meta["Channels"] = str(info.channels)
        if hasattr(info, "length"):
            meta["Duration"] = f"{info.length:.2f}s"
        if hasattr(info, "sample_rate"):
            meta["SampleRate"] = str(info.sample_rate)
        return meta
    except Exception:
        return None


def extract_wav_metadata(filepath: pathlib.Path) -> dict[str, str] | None:
    try:
        with wave.open(str(filepath), "rb") as wf:
            channels = wf.getnchannels()
            framerate = wf.getframerate()
            frames = wf.getnframes()
            duration = frames / framerate if framerate else 0
            return {
                "Format": "WAV",
                "Channels": str(channels),
                "SampleRate": str(framerate),
                "Duration": f"{duration:.2f}s",
            }
    except Exception:
        return None


def get_binary_metadata(filepath: pathlib.Path) -> dict[str, str] | None:
    ext = filepath.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return extract_image_metadata(filepath)
    if ext in AUDIO_EXTENSIONS:
        meta = extract_audio_metadata(filepath)
        if meta:
            return meta
    return None


def generate_project_context(
    root_dir: pathlib.Path,
    cli_exclude_patterns: list[str],
    output_file_abs: pathlib.Path | None,
    verbose: bool = False,
) -> str:
    gitignore_patterns = read_gitignore_patterns(root_dir)
    combined_output_parts = ["--- START PROJECT CONTEXT ---"]
    processed_files_count = 0
    excluded_items_count = 0
    
    # Statistics for verbose mode
    excluded_items = []  # List of (path, reason) tuples
    file_sizes = []  # List of (path, size) tuples for processed files

    script_abs_path = pathlib.Path(__file__).resolve(strict=False)

    for dirpath_str, dirnames, filenames in os.walk(str(root_dir), topdown=True):
        dirpath_abs = pathlib.Path(dirpath_str)
        current_dirnames = list(dirnames)
        dirnames[:] = []

        for d_name in current_dirnames:
            dir_abs_loop = dirpath_abs / d_name
            dir_rel_loop = dir_abs_loop.relative_to(root_dir)
            is_excluded, reason = should_exclude(
                dir_rel_loop,
                dir_abs_loop,
                gitignore_patterns,
                DEFAULT_EXCLUDES,
                cli_exclude_patterns,
            )
            if not is_excluded:
                dirnames.append(d_name)
            else:
                excluded_items_count += 1
                excluded_items.append((dir_rel_loop.as_posix(), reason))
                if verbose:
                    logger.info(
                        "Excluding directory: %s (Reason: %s)",
                        dir_rel_loop.as_posix(),
                        reason,
                    )

        for filename in filenames:
            filepath_abs = dirpath_abs / filename
            if not filepath_abs.exists():
                continue

            filepath_rel = filepath_abs.relative_to(root_dir)
            filepath_rel_posix = filepath_rel.as_posix()

            if script_abs_path.exists() and filepath_abs == script_abs_path:
                excluded_items_count += 1
                excluded_items.append((filepath_rel_posix, "Self (script)"))
                if verbose:
                    logger.info(
                        "Excluding self (script): %s",
                        filepath_rel_posix,
                    )
                continue
            if output_file_abs and filepath_abs == output_file_abs:
                excluded_items_count += 1
                excluded_items.append((filepath_rel_posix, "Self (output file)"))
                if verbose:
                    logger.info(
                        "Excluding self (output file): %s",
                        filepath_rel_posix,
                    )
                continue

            is_excluded, reason = should_exclude(
                filepath_rel,
                filepath_abs,
                gitignore_patterns,
                DEFAULT_EXCLUDES,
                cli_exclude_patterns,
            )
            if is_excluded:
                excluded_items_count += 1
                excluded_items.append((filepath_rel_posix, reason))
                if verbose:
                    is_py = filepath_rel.suffix.lower() == ".py"
                    py_diag = (
                        " (Python file; check venv, build dir, gitignore)"
                        if is_py
                        else ""
                    )
                    logger.info(
                        "Excluding file: %s (Reason: %s)%s",
                        filepath_rel_posix,
                        reason,
                        py_diag,
                    )
                continue

            try:
                if not filepath_abs.is_file():
                    excluded_items_count += 1
                    excluded_items.append((filepath_rel_posix, "Non-file"))
                    if verbose:
                        logger.info(
                            "Skipping non-file: %s",
                            filepath_rel_posix,
                        )
                    continue

                file_size = filepath_abs.stat().st_size
                is_binary = is_likely_binary(filepath_abs)
                file_sizes.append((filepath_rel_posix, file_size))
                combined_output_parts.append(
                    f"--- START FILE: {filepath_rel_posix} ---"
                )

                if is_binary:
                    combined_output_parts.extend(
                        [
                            f"--- BINARY FILE METADATA ---",
                            f"Path: {filepath_rel_posix}",
                            f"Size: {format_file_size(file_size)}",
                        ]
                    )
                    extra_meta = get_binary_metadata(filepath_abs)
                    if extra_meta:
                        for k, v in extra_meta.items():
                            combined_output_parts.append(f"{k}: {v}")
                else:
                    try:
                        content = filepath_abs.read_text(
                            encoding="utf-8", errors="surrogateescape"
                        )
                        lang_hint = (
                            filepath_rel.suffix.lstrip(".")
                            if filepath_rel.suffix
                            else ""
                        )
                        combined_output_parts.extend(
                            [f"```{lang_hint}", content.strip(), "```"]
                        )
                    except OSError as e:
                        combined_output_parts.append(f"--- ERROR READING FILE: {e} ---")
                    except UnicodeDecodeError as e:
                        combined_output_parts.append(
                            f"--- ERROR READING FILE: Could not decode as UTF-8 ({e}). ---"
                        )

                combined_output_parts.append(
                    f"--- END FILE: {filepath_rel_posix} ---\n"
                )
                processed_files_count += 1

            except OSError as e:
                excluded_items_count += 1
                excluded_items.append((filepath_rel_posix, f"OSError: {e}"))
                if verbose:
                    logger.info(
                        "Warning: Could not access/process file %s: %s",
                        filepath_rel_posix,
                        e,
                    )
            except Exception as e:
                excluded_items_count += 1
                excluded_items.append((filepath_rel_posix, f"Error: {e}"))
                if verbose:
                    logger.info(
                        "Warning: Unexpected error processing file %s: %s",
                        filepath_rel_posix,
                        e,
                    )

    combined_output_parts.extend(["--- END PROJECT CONTEXT ---"])

    # Print summary statistics
    if verbose or processed_files_count > 0 or excluded_items_count > 0:
        logger.info(
            "Processed %s files, excluded %s files/directories.",
            processed_files_count,
            excluded_items_count,
        )

    # Print detailed verbose information
    if verbose:
        # Print excluded items summary
        if excluded_items:
            logger.info("\n--- EXCLUDED FILES AND DIRECTORIES ---")
            for path, reason in excluded_items:
                logger.info("  %s - %s", path, reason)
        
        # Print top 10 largest files by size
        if file_sizes:
            logger.info("\n--- TOP 10 LARGEST FILES ---")
            sorted_files = sorted(file_sizes, key=lambda x: x[1], reverse=True)[:10]
            for path, size in sorted_files:
                logger.info("  %s - %s", format_file_size(size), path)
        
        # Print file type distribution
        file_types = {}
        for path, _ in file_sizes:
            ext = pathlib.Path(path).suffix.lower() or "no extension"
            file_types[ext] = file_types.get(ext, 0) + 1
        
        if file_types:
            logger.info("\n--- FILE TYPE DISTRIBUTION ---")
            sorted_types = sorted(file_types.items(), key=lambda x: x[1], reverse=True)
            for ext, count in sorted_types:
                logger.info("  %s: %d files", ext, count)
        
        # Print total size of processed files
        total_size = sum(size for _, size in file_sizes)
        logger.info("\n--- TOTAL SIZE OF PROCESSED FILES ---")
        logger.info("  %s", format_file_size(total_size))

    return "\n".join(combined_output_parts)


def main():
    """Command line interface entry point"""
    parser = argparse.ArgumentParser(
        prog="llmcontext",
        description="Gather project files into a single text block for LLM context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  llmcontext                      # Scan current dir, output to stdout
  llmcontext path/to/project      # Scan specific directory
  llmcontext . output.txt         # Scan current dir, write to file
  llmcontext -e "*.log" -v        # Exclude patterns with verbose output
""",
    )
    parser.add_argument(
        "root_dir",
        nargs="?",
        type=pathlib.Path,
        default=pathlib.Path("."),
        help="The root directory of the project to scan (default: current directory).",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        type=pathlib.Path,
        default=None,
        help="Optional: File path to write the output to. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Additional glob patterns to exclude. Can be used multiple times.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print detailed information about processed and excluded items to stderr.",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Print a suggested detailed LLM query to stderr after processing.",
    )
    # Version argument
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__import__('llmcontext').__version__}",
        help="Show the version number and exit",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
        stream=sys.stderr,
    )

    try:
        root_dir_abs = args.root_dir.resolve(strict=True)
    except FileNotFoundError:
        logger.error(
            "Error: Root directory '%s' not found or is not accessible.",
            args.root_dir,
        )
        sys.exit(1)
    if not root_dir_abs.is_dir():
        logger.error("Error: Root path '%s' is not a directory.", args.root_dir)
        sys.exit(1)

    output_file_abs_path = None
    if args.output_file:
        output_file_abs_path = pathlib.Path(args.output_file).resolve()

    try:
        output_text = generate_project_context(
            root_dir_abs, args.exclude, output_file_abs_path, args.verbose
        )

        token_estimate = len(output_text.split())
        if token_estimate > 1_000_000:
            logger.warning(
                "Generated context is approximately %s tokens which may exceed typical LLM limits",
                token_estimate,
            )

        if output_file_abs_path:
            try:
                output_file_abs_path.parent.mkdir(parents=True, exist_ok=True)
                output_file_abs_path.write_text(output_text, encoding="utf-8", errors="surrogateescape")
                if args.verbose:
                    logger.info(
                        "Output successfully written to: %s",
                        output_file_abs_path,
                    )
            except IOError as e:
                logger.error(
                    "Error: Could not write to output file %s: %s",
                    output_file_abs_path,
                    e,
                )
                sys.exit(1)
        else:
            print(output_text)

        if args.show_prompt:
            print("\n" + "-" * 80, file=sys.stderr)
            print(
                "SUGGESTED LLM QUERY (copy and paste this into your LLM interface after the context):",
                file=sys.stderr,
            )
            print("-" * 80, file=sys.stderr)
            print(
                """
Hello AI, I've provided the context for a software project above.
I am generally satisfied with the current state of this project, but I am seeking an expert "second opinion" to identify areas for further refinement, risk mitigation, and strategic improvement. Please assume the role of a seasoned principal engineer or software architect reviewing this codebase.

**Important: For this review, please ensure all your feedback and suggestions are provided textually, as descriptive text. Do not generate code diffs or direct code examples for any proposed changes. All recommendations, including those related to code or configuration, should be explained textually.**

Focus your analysis on the following, even if the project appears to be functioning well:

1.  **Proactive Risk Identification:**
    *   **Security:** Are there any subtle security vulnerabilities (e.g., related to dependencies, data handling, input validation, configuration, authentication/authorization nuances, or less common attack vectors like SSRF or ReDoS) that might have been overlooked?
    *   **Scalability & Performance:** Identify any potential (non-obvious) performance bottlenecks, inefficient data patterns, database query concerns under load, or areas that might not scale well under significantly increased load, data volume, or concurrent users.
    *   **Resilience & Reliability:** How might the system behave under partial failures, network interruptions, or unexpected external service degradations? Are there areas to improve fault tolerance, idempotent operations, or graceful degradation?

2.  **Code & Design Refinement:**
    *   **Simplification & Elegance:** Even if the code is correct, are there opportunities to simplify complex sections, reduce boilerplate, enhance clarity through better naming or structure, or make the design more intuitive and maintainable?
    *   **Modernization & Idiomatic Use:** Could newer language features, established design patterns, or standard library utilities enhance readability, conciseness, type safety, or performance in specific areas? Is the code idiomatic for the language(s) used?

3.  **Ecosystem Leverage & Future-Proofing:**
    *   **Libraries & Tools:**
        *   Are there any current dependencies that have better alternatives (more modern, performant, secure, better maintained, or with a more active community)?
        *   Could any custom-implemented logic be beneficially replaced by well-established third-party libraries or tools (e.g., for data validation, complex state management, API clients, background tasks, configuration, etc.) to improve robustness or reduce maintenance?
    *   **Testability & Test Strategy:**
        *   Beyond existing tests (if any are visible), what key areas or types of logic (e.g., complex business rules, integration points, error handling paths) would benefit most from enhanced testing strategies? Are there opportunities for property-based testing, mutation testing, or more comprehensive integration tests?
    *   **Observability & Operability:**
        *   How could the project's observability (structured logging, metrics, distributed tracing) be improved for easier debugging, performance monitoring, and understanding system behavior in a production environment?
        *   Are there aspects that would make the system easier to deploy, operate, or manage in production?
    *   **Architectural Considerations:** Are there any emerging architectural patterns or best practices that might be relevant for the project's future evolution (e.g., considerations for modularity, event-driven approaches for certain parts, API design evolution) without over-engineering?

4.  **General Areas for Enhancement (Beyond the Above):**
    *   Are there any other "blind spots" or areas for improvement that come to mind from your expert perspective? This could relate to documentation quality and completeness, developer experience (e.g., build times, local setup), or adherence to advanced best practices specific to the project's domain or technologies.

**Output Structure and Format for Suggestions:**
Please structure your analysis clearly with headings for each major point. For each item, if you identify an area of interest, briefly explain the potential issue/opportunity and suggest a high-level approach or specific tools/techniques to consider.

**Crucially, all suggestions, particularly those relating to code or configuration, must be presented in a descriptive, narrative text format. Do NOT provide code changes as unified diffs, complete code snippets intended for replacement, or direct, revised code examples.**

When providing concrete examples or referring to specific parts of the codebase, please describe the location (e.g., filename, function name, or relevant line numbers/range) and explain the proposed change or observation conceptually. The emphasis should be on textual explanation and actionable insights, not on generating code. Prioritize actionable insights.

**Guiding Questions for Deeper Reflection (Please ask 3-5 questions):**
To help me think more deeply about the project and its future, please conclude your analysis by posing 3 to 5 insightful questions. These questions should aim to:
    a) **Clarify Strategic Goals:** Help me articulate or reconsider the long-term vision or critical success factors for this project.
    b) **Uncover Hidden Constraints/Trade-offs:** Prompt me to think about non-obvious constraints (e.g., team skills, budget, time-to-market pressures) or trade-offs I might be implicitly making.
    c) **Explore Future Evolution:** Encourage consideration of how the project might need to evolve to meet future demands or changing requirements.
    d) **Challenge Assumptions:** Gently push me to re-evaluate any core assumptions underpinning the current design or approach.
    e) **Prioritize Next Steps:** Guide me towards identifying the most impactful areas for improvement based on my project's specific context and priorities.

Example themes for questions:
    *   "What is the anticipated growth in users/data/traffic over the next 1-2 years, and how might that impact the current architecture's choke points?"
    *   "If you had to onboard a new senior developer to this project tomorrow, what parts of the codebase or documentation do you anticipate would be the most challenging for them to grasp quickly?"
    *   "Are there any 'sacred cows' in the current design or technology stack that might be revisited if you were starting from scratch today, given current best practices?"
    *   "What's the biggest 'known unknown' or area of technical debt that keeps you up at night regarding this project, even if it's not an immediate problem?"
    *   "Considering the project's primary business objectives, which of the potential improvement areas we've discussed would deliver the most significant value or mitigate the most critical risk in the short to medium term?"

Let's explore how to elevate this project further!
""",
                file=sys.stderr,
            )
            print("-" * 80, file=sys.stderr)

    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
