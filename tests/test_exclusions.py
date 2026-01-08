"""Tests for gitignore pattern matching and exclusion logic."""

import pathlib
import llmcontext.llmcontext as lc


class TestFnmatchWithDoublestar:
    """Tests for the fnmatch_with_doublestar helper function."""

    def test_no_doublestar_falls_back_to_fnmatch(self):
        """Patterns without ** should work like regular fnmatch."""
        assert lc.fnmatch_with_doublestar("foo.txt", "*.txt") is True
        assert lc.fnmatch_with_doublestar("foo.py", "*.txt") is False
        assert lc.fnmatch_with_doublestar("test", "test") is True
        assert lc.fnmatch_with_doublestar("test.pyc", "*.py[cod]") is True

    def test_doublestar_prefix(self):
        """**/pattern should match pattern anywhere in the tree."""
        # Match at root
        assert lc.fnmatch_with_doublestar("foo", "**/foo") is True
        # Match in subdirectory
        assert lc.fnmatch_with_doublestar("a/foo", "**/foo") is True
        assert lc.fnmatch_with_doublestar("a/b/foo", "**/foo") is True
        assert lc.fnmatch_with_doublestar("a/b/c/foo", "**/foo") is True
        # Non-match
        assert lc.fnmatch_with_doublestar("a/bar", "**/foo") is False
        # With glob in suffix
        assert lc.fnmatch_with_doublestar("a/b/foo.txt", "**/foo.txt") is True
        assert lc.fnmatch_with_doublestar("a/b/foo.txt", "**/*.txt") is True

    def test_doublestar_suffix(self):
        """pattern/** should match anything under pattern."""
        assert lc.fnmatch_with_doublestar("build", "build/**") is True
        assert lc.fnmatch_with_doublestar("build/output", "build/**") is True
        assert lc.fnmatch_with_doublestar("build/a/b/c", "build/**") is True
        # Non-match
        assert lc.fnmatch_with_doublestar("other/build", "build/**") is False
        assert lc.fnmatch_with_doublestar("building", "build/**") is False

    def test_doublestar_middle(self):
        """a/**/b should match a/b, a/x/b, a/x/y/b, etc."""
        assert lc.fnmatch_with_doublestar("a/b", "a/**/b") is True
        assert lc.fnmatch_with_doublestar("a/x/b", "a/**/b") is True
        assert lc.fnmatch_with_doublestar("a/x/y/b", "a/**/b") is True
        assert lc.fnmatch_with_doublestar("a/x/y/z/b", "a/**/b") is True
        # Non-match
        assert lc.fnmatch_with_doublestar("b/a/b", "a/**/b") is False
        assert lc.fnmatch_with_doublestar("a/b/c", "a/**/b") is False

    def test_doublestar_with_glob(self):
        """Double star combined with regular globs."""
        # src/**/test matches paths that end with test under src/
        assert lc.fnmatch_with_doublestar("src/test", "src/**/test") is True
        assert lc.fnmatch_with_doublestar("src/foo/test", "src/**/test") is True
        # src/test/foo.py does NOT match src/**/test (path extends beyond test)
        assert lc.fnmatch_with_doublestar("src/test/foo.py", "src/**/test") is False
        # **/*.py matches any .py file
        assert lc.fnmatch_with_doublestar("a/b/test.py", "**/*.py") is True


class TestShouldExclude:
    """Tests for the should_exclude function."""

    def make_path(self, path_str: str, tmp_path: pathlib.Path) -> tuple:
        """Helper to create path objects for testing."""
        path_obj_rel = pathlib.Path(path_str)
        path_obj_abs = tmp_path / path_str
        path_obj_abs.parent.mkdir(parents=True, exist_ok=True)
        if path_str.endswith("/"):
            path_obj_abs.mkdir(parents=True, exist_ok=True)
            path_obj_rel = pathlib.Path(path_str.rstrip("/"))
            path_obj_abs = tmp_path / path_str.rstrip("/")
        else:
            path_obj_abs.touch()
        return path_obj_rel, path_obj_abs

    # --- Default Excludes Tests ---

    def test_default_excludes_exact_match(self, tmp_path: pathlib.Path):
        """Default excludes should match exact directory names."""
        path_rel, path_abs = self.make_path(".git/", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, [], lc.DEFAULT_EXCLUDES, []
        )
        assert excluded is True
        assert "Default exclude" in reason

    def test_default_excludes_glob_pattern(self, tmp_path: pathlib.Path):
        """Default excludes should match glob patterns like *.pyc."""
        path_rel, path_abs = self.make_path("module.pyc", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, [], lc.DEFAULT_EXCLUDES, []
        )
        assert excluded is True
        assert "Default exclude" in reason

    def test_default_excludes_in_path(self, tmp_path: pathlib.Path):
        """Files inside excluded directories should be excluded."""
        path_rel, path_abs = self.make_path(
            "__pycache__/module.cpython-39.pyc", tmp_path
        )
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, [], lc.DEFAULT_EXCLUDES, []
        )
        assert excluded is True

    # --- Gitignore Glob Pattern Tests ---

    def test_gitignore_glob_directory_pattern(self, tmp_path: pathlib.Path):
        """*.egg-info/ should match llmcontext.egg-info directory."""
        path_rel, path_abs = self.make_path("llmcontext.egg-info/", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, ["*.egg-info/"], [], []
        )
        assert excluded is True
        assert ".gitignore" in reason

    def test_gitignore_glob_file_inside_matched_dir(self, tmp_path: pathlib.Path):
        """Files inside *.egg-info/ directories should be excluded."""
        # First create the directory
        (tmp_path / "llmcontext.egg-info").mkdir(parents=True, exist_ok=True)
        path_rel, path_abs = self.make_path("llmcontext.egg-info/PKG-INFO", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, ["*.egg-info/"], [], []
        )
        assert excluded is True

    def test_gitignore_character_class_pattern(self, tmp_path: pathlib.Path):
        """*.py[cod] should match .pyc, .pyo, .pyd files."""
        for ext in ["pyc", "pyo", "pyd"]:
            path_rel, path_abs = self.make_path(f"module.{ext}", tmp_path)
            excluded, reason = lc.should_exclude(
                path_rel, path_abs, ["*.py[cod]"], [], []
            )
            assert excluded is True, f"*.py[cod] should match .{ext}"

    # --- Anchored Pattern Tests ---

    def test_gitignore_anchored_directory(self, tmp_path: pathlib.Path):
        """/build/ should only match build at root."""
        # Should match at root
        path_rel, path_abs = self.make_path("build/", tmp_path)
        excluded, reason = lc.should_exclude(path_rel, path_abs, ["/build/"], [], [])
        assert excluded is True

    def test_gitignore_anchored_with_glob(self, tmp_path: pathlib.Path):
        """/build*/ should match build, build-output, etc. at root."""
        for name in ["build", "build-output", "build123"]:
            (tmp_path / name).mkdir(parents=True, exist_ok=True)
            path_rel = pathlib.Path(name)
            path_abs = tmp_path / name
            excluded, reason = lc.should_exclude(
                path_rel, path_abs, ["/build*/"], [], []
            )
            assert excluded is True, f"/build*/ should match {name}"

    def test_gitignore_anchored_file_inside_dir(self, tmp_path: pathlib.Path):
        """Files inside /build/ should be excluded."""
        (tmp_path / "build").mkdir(parents=True, exist_ok=True)
        path_rel, path_abs = self.make_path("build/output.txt", tmp_path)
        excluded, reason = lc.should_exclude(path_rel, path_abs, ["/build/"], [], [])
        assert excluded is True

    # --- Double Star Pattern Tests ---

    def test_gitignore_doublestar_prefix(self, tmp_path: pathlib.Path):
        """**/node_modules should match node_modules anywhere."""
        for path_str in ["node_modules/", "src/node_modules/", "a/b/node_modules/"]:
            dir_path = tmp_path / path_str.rstrip("/")
            dir_path.mkdir(parents=True, exist_ok=True)
            path_rel = pathlib.Path(path_str.rstrip("/"))
            path_abs = dir_path
            excluded, reason = lc.should_exclude(
                path_rel, path_abs, ["**/node_modules/"], [], []
            )
            assert excluded is True, f"**/node_modules/ should match {path_str}"

    def test_gitignore_doublestar_suffix(self, tmp_path: pathlib.Path):
        """dist/** should match everything under dist."""
        (tmp_path / "dist").mkdir(parents=True, exist_ok=True)
        path_rel, path_abs = self.make_path("dist/bundle.js", tmp_path)
        excluded, reason = lc.should_exclude(path_rel, path_abs, ["dist/**"], [], [])
        assert excluded is True

    def test_gitignore_doublestar_middle(self, tmp_path: pathlib.Path):
        """src/**/test should match test dirs at any depth under src."""
        for path_str in ["src/test/", "src/foo/test/", "src/foo/bar/test/"]:
            dir_path = tmp_path / path_str.rstrip("/")
            dir_path.mkdir(parents=True, exist_ok=True)
            path_rel = pathlib.Path(path_str.rstrip("/"))
            path_abs = dir_path
            excluded, reason = lc.should_exclude(
                path_rel, path_abs, ["src/**/test/"], [], []
            )
            assert excluded is True, f"src/**/test/ should match {path_str}"

    # --- CLI Excludes Tests ---

    def test_cli_exclude_with_doublestar(self, tmp_path: pathlib.Path):
        """CLI excludes should support ** patterns."""
        path_rel, path_abs = self.make_path("a/b/secret.txt", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, [], [], ["**/secret.txt"]
        )
        assert excluded is True
        assert "CLI Exclude" in reason

    # --- Edge Cases ---

    def test_empty_gitignore_pattern(self, tmp_path: pathlib.Path):
        """Empty patterns should be ignored."""
        path_rel, path_abs = self.make_path("file.txt", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, ["", "  ", "# comment"], [], []
        )
        assert excluded is False

    def test_non_matching_pattern(self, tmp_path: pathlib.Path):
        """Non-matching patterns should not exclude."""
        path_rel, path_abs = self.make_path("important.txt", tmp_path)
        excluded, reason = lc.should_exclude(
            path_rel, path_abs, ["*.log", "temp/"], [], []
        )
        assert excluded is False
