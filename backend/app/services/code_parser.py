"""Service for filtering and classifying source code files from repository trees."""
import os
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Set, Tuple
from app.core.config import settings

# Supported file extensions and their canonical language names
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "React JSX",
    ".ts": "TypeScript",
    ".tsx": "React TSX",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".toml": "TOML",
    ".txt": "Text",
    ".cfg": "Configuration",
    ".ini": "Configuration",
    ".properties": "Properties",
    ".xml": "XML",
    ".gradle": "Gradle",
}

PROJECT_METADATA_FILENAMES: Set[str] = {
    "readme", "readme.md", "readme.rst", "readme.txt", "pyproject.toml",
    "setup.cfg", "requirements.txt", "pipfile", "package.json", "composer.json",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "gradle.properties", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "makefile", "cmakelists.txt",
    "environment.yml", "environment.yaml", "tsconfig.json", "vite.config.js",
    "vite.config.ts", "webpack.config.js",
}

# Directories to unconditionally ignore
IGNORED_DIRECTORIES: Set[str] = {
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "target",
    "coverage",
    ".next",
    ".turbo",
    ".cache",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    "vendor",
    "bin",
    "obj",
    ".gradle",
    ".mvn",
}

# Specific filenames that should not be indexed (e.g. lockfiles, minified files)
IGNORED_FILENAMES: Set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "gemfile.lock",
    "composer.lock",
    "cargo.lock",
}


class CodeParser:
    """Handles source file detection, filtering, and limit enforcement."""

    @classmethod
    def get_language(cls, file_path: str) -> Optional[str]:
        """Return the detected programming language for a given file path, or None."""
        path = PurePosixPath(file_path)
        suffix = path.suffix.lower()
        return EXTENSION_LANGUAGE_MAP.get(suffix) or (
            "Configuration" if path.name.lower() in PROJECT_METADATA_FILENAMES else None
        )

    @classmethod
    def is_supported_source_file(cls, path: str, size: Optional[int] = None) -> bool:
        """
        Check if a file path belongs to a supported source code file.

        Verifies:
        1. Not inside an ignored directory.
        2. Filename is not a lockfile or minified file.
        3. Extension is in supported languages.
        4. Size (if known) does not exceed MAX_FILE_SIZE_BYTES.
        """
        posix_path = PurePosixPath(path)
        parts = posix_path.parts

        # 1. Ignore if any path segment matches an ignored directory
        for part in parts[:-1]:
            if part.lower() in IGNORED_DIRECTORIES or part.startswith("."):
                return False

        # 2. Check filename
        filename = posix_path.name.lower()
        if filename in IGNORED_FILENAMES:
            return False

        if filename.endswith(".min.js") or filename.endswith(".min.css") or filename.endswith(".map"):
            return False

        # Include common project documentation and dependency/config manifests.
        is_project_metadata = (
            filename in PROJECT_METADATA_FILENAMES
            or (filename.startswith("requirements-") and filename.endswith(".txt"))
            or filename.startswith("readme.")
        )

        # 3. Check extension or explicit project metadata filename
        suffix = posix_path.suffix.lower()
        if suffix not in EXTENSION_LANGUAGE_MAP and not is_project_metadata:
            return False

        # 4. Check individual file size limit
        if size is not None and size > settings.MAX_FILE_SIZE_BYTES:
            return False

        return True

    @classmethod
    def filter_tree(
        cls, tree_items: List[dict]
    ) -> Tuple[List[dict], int, bool, Optional[str]]:
        """
        Filter GitHub Git Tree blob items to candidate source files.

        Returns:
            Tuple containing:
            - items_to_download: list of selected tree dicts (up to MAX_SOURCE_FILES)
            - total_source_files_found: total candidate files discovered in tree
            - is_truncated: whether candidates exceeded MAX_SOURCE_FILES
            - truncation_reason: human-readable reason if truncated
        """
        candidate_items: List[dict] = []

        for item in tree_items:
            # We only inspect blobs (files), ignoring tree/submodules
            if item.get("type") != "blob":
                continue

            path = item.get("path", "")
            size = item.get("size")  # may be None in some tree responses

            if cls.is_supported_source_file(path, size):
                candidate_items.append(item)

        total_found = len(candidate_items)
        max_limit = settings.MAX_SOURCE_FILES

        if total_found > max_limit:
            selected_items = candidate_items[:max_limit]
            is_truncated = True
            truncation_reason = (
                f"Repository contains {total_found} source files. "
                f"Showing first {max_limit} files according to configured limit."
            )
        else:
            selected_items = candidate_items
            is_truncated = False
            truncation_reason = None

        return selected_items, total_found, is_truncated, truncation_reason

