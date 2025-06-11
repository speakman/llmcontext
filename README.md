# LLM Context Builder (`llmcontext`)

[![PyPI version](https://badge.fury.io/py/llmcontext.svg)](https://badge.fury.io/py/llmcontext)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/speakman/llmcontext/actions/workflows/ci.yml/badge.svg)](https://github.com/speakman/llmcontext/actions/workflows/ci.yml)

`llmcontext` is a command-line tool that gathers all relevant files from a software project into a single text file. This text file is formatted for easy attachment to a Large Language Model (LLM) to provide it with the necessary context for analysis, refactoring, or Q&A about the project.

The tool intelligently excludes common non-source files, respects `.gitignore` patterns, and identifies binary files to include only their metadata.

## Features

- **Comprehensive Context:** Includes file structure and content.
- **Intelligent Exclusions:**
  - Skips common version control, IDE, OS-specific, build artifact, and virtual environment directories/files by default.
  - Respects `.gitignore` files found in the project's root directory.
  - Allows custom exclusion patterns via command-line arguments.
 - **Binary File Handling:** Detects likely binary files and includes metadata such as image dimensions or audio duration instead of raw content. Only Python modules are used; no external command-line tools are required.
 - **Markdown Formatting:** Source code content is wrapped in Markdown code blocks, with language hints based on file extensions.
 - **LLM-Ready Output:** The output is formatted for easy consumption by large language models.
 - **Optional Suggested Prompt:** A comprehensive LLM query can be printed to `stderr` on demand.
- **All Dependencies Included:** Uses Python libraries only and installs required packages (Pillow and mutagen) automatically.
- **Cross-Platform:** Works on macOS, Linux, and Windows.

## Installation

The recommended way to install `llmcontext` is using `pipx`. `pipx` installs Python CLI applications in isolated environments, making them available globally without interfering with other Python projects or system Python.

1.  **Install `pipx`** (if you haven't already):

    - **macOS:**
      ```bash
      brew install pipx
      pipx ensurepath
      ```
    - **Linux:**
      ```bash
      python3 -m pip install --user pipx
      python3 -m pipx ensurepath
      ```
      (You might need to add `~/.local/bin` to your `PATH` if `pipx ensurepath` doesn't do it automatically or if you open a new terminal.)
    - **Windows (PowerShell):**
      ```powershell
      py -m pip install --user pipx
      py -m pipx ensurepath
      ```
      (Ensure Python's user scripts directory is in your PATH.)

    After running `pipx ensurepath`, you may need to open a new terminal session for the `PATH` changes to take effect.

2.  **Install `llmcontext` from source using `pipx`:**
    ```bash
    pipx install git+https://github.com/speakman/llmcontext.git
    ```

## Usage

```
llmcontext [ROOT_DIR] [OUTPUT_FILE] [OPTIONS]
```

**Arguments:**

- `ROOT_DIR`: (Optional) The root directory of the project to scan. Defaults to the current directory (`.`).
- `OUTPUT_FILE`: (Optional) File path to write the context to. If omitted, prints to standard output (stdout).

**Options:**

- `-e PATTERN`, `--exclude PATTERN`: Additional glob patterns to exclude files or directories (e.g., `'tests/*'`, `'*.log'`). Can be used multiple times. These are applied _after_ default and `.gitignore` exclusions.
- `-v`, `--verbose`: Print detailed information about processed and excluded files/directories to standard error (stderr).
- `--show-prompt`: Print a suggested detailed LLM query to `stderr` after processing.
- `--version`: Show the version number and exit.
- `-h`, `--help`: Show the help message and exit.

**Examples:**

1.  **Scan the current directory and print context to stdout:**

    ```bash
    llmcontext
    ```

2.  **Scan a specific project directory and print context to stdout:**

    ```bash
    llmcontext path/to/your/project
    ```

3.  **Scan the current directory and save context to `project_context.txt`:**

    ```bash
    llmcontext . project_context.txt
    ```

4.  **Scan a specific project directory and save context to `project_context.txt`:**

    ```bash
    llmcontext path/to/your/project project_context.txt
    ```

5.  **Scan, save to file, and also show the suggested LLM prompt:**

    ```bash
    llmcontext path/to/your/project context.txt --show-prompt
    ```

6.  **Using verbose mode and custom exclusions:**
    ```bash
    llmcontext --exclude "*.tmp" --exclude "docs/build/*" --verbose > context_output.txt
    ```

**Note:** During development, you can also run the tool using `python -m llmcontext` without installing it.

7.  Generate the context to a text file:
    ```bash
    llmcontext path/to/my/project my_project_llm_context.txt
    ```
8.  If you want a pre-written comprehensive prompt, run with `--show-prompt`:
    ```bash
    llmcontext path/to/my/project my_project_llm_context.txt --show-prompt
    # (Context goes to my_project_llm_context.txt, prompt to stderr)
    ```
9.  Upload or attach the generated context file to your preferred LLM chat interface
10. If you used `--show-prompt`, copy/paste the suggested prompt from stderr
11. Ask your specific question about the project

## How it Works

1.  **Walks Directory Tree:** Starts from the `ROOT_DIR`.
2.  **Applies Exclusions:**
    - Checks against `DEFAULT_EXCLUDES` (common patterns like `.git`, `node_modules`, `__pycache__`, etc.).
    - Reads and applies patterns from the `.gitignore` file in `ROOT_DIR`.
    - Applies any custom `--exclude` patterns.
    - Excludes the `OUTPUT_FILE` itself if specified.
3.  **Processes Files:**
    - For text files: Reads content with UTF-8 encoding (using surrogateescape error handling for better compatibility), wraps it in Markdown code blocks with a language hint.
    - For binary files: Notes its path and size.
4.  **Constructs Output:** Combines file metadata and content in a format optimized for consumption by LLMs.
5.  **Creates Directory Structure (if needed):** If an output file is specified, ensures the parent directory exists.
6.  **Shows Prompt (Optional):** If `--show-prompt` is used, a detailed suggested query for the LLM is printed to `stderr`.

## Pro Tips

- **Include Project Documentation:** Adding a comprehensive project description document (like `PROJECT.md`, `ARCHITECTURE.md`, or similar) to your project significantly improves LLM analysis results. This document should describe:

  - The project's purpose and high-level architecture
  - Key components and how they interact
  - Important design decisions and their rationales
  - External dependencies and integrations

  LLMs can better understand your codebase context when provided with this overview, resulting in more accurate and helpful responses to your questions.

- **Provide Good Questions:** When using the generated context with an LLM, be specific in your questions. Ask about particular aspects of the code, specific functionalities, or clearly defined improvements rather than general questions.

- **Target Specific Directories:** For large projects, consider running `llmcontext` on specific subdirectories rather than the entire project to focus the LLM's attention on relevant components.

## Contributing

Contributions are welcome! If you have suggestions for improvements or find a bug, please open an issue or submit a pull request to the [GitHub repository](https://github.com/speakman/llmcontext).

## License

This project is licensed under the MIT License.

