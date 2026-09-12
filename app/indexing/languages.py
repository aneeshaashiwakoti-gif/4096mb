"""
Multi-language detection engine for Sentinel.
Supports 15+ programming and configuration languages via file extension,
shebang inspection, and content heuristics.
"""

from pathlib import Path
import re
from typing import Optional, Tuple

LANGUAGE_EXTENSIONS = {
    # 1. Python
    ".py": "python", ".pyw": "python", ".pyi": "python",
    # 2. JavaScript
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    # 3. TypeScript
    ".ts": "typescript", ".mts": "typescript", ".cts": "typescript", ".tsx": "typescript",
    # 4. Java
    ".java": "java",
    # 5. C
    ".c": "c", ".h": "c",
    # 6. C++
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    # 7. C#
    ".cs": "csharp",
    # 8. Go
    ".go": "go",
    # 9. Rust
    ".rs": "rust",
    # 10. Ruby
    ".rb": "ruby", ".rake": "ruby",
    # 11. PHP
    ".php": "php", ".phtml": "php",
    # 12. Swift
    ".swift": "swift",
    # 13. Kotlin
    ".kt": "kotlin", ".kts": "kotlin",
    # 14. SQL
    ".sql": "sql",
    # 15. HTML & CSS
    ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss", ".less": "less",
    # 16. Shell
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    # 17. YAML / JSON / Config
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".ini": "ini",
    # 18. Markdown / Docs
    ".md": "markdown", ".rst": "restructuredtext",
}

SPECIAL_FILENAMES = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "cmakelists.txt": "cmake",
    ".env": "ini",
}


def detect_language(file_path: str, sample_content: Optional[str] = None) -> str:
    """
    Detect the programming or configuration language for a file.
    Uses extension, special filenames, and content heuristics.
    """
    p = Path(file_path)
    name_lower = p.name.lower()

    if name_lower in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[name_lower]

    ext = p.suffix.lower()
    if ext in LANGUAGE_EXTENSIONS:
        return LANGUAGE_EXTENSIONS[ext]

    if sample_content:
        # Shebang heuristics
        first_line = sample_content.splitlines()[0] if sample_content.splitlines() else ""
        if first_line.startswith("#!"):
            if "python" in first_line:
                return "python"
            if "node" in first_line or "deno" in first_line:
                return "javascript"
            if "bash" in first_line or "sh" in first_line or "zsh" in first_line:
                return "shell"
            if "ruby" in first_line:
                return "ruby"
            if "php" in first_line:
                return "php"

        # XML / HTML heuristic
        if sample_content.lstrip().startswith("<!DOCTYPE html") or sample_content.lstrip().startswith("<html"):
            return "html"
        if sample_content.lstrip().startswith("<?xml"):
            return "xml"

    return "plaintext"


def is_binary_file(sample_bytes: bytes) -> bool:
    """Check if byte sample contains null bytes (indicator of binary file)."""
    return b"\x00" in sample_bytes[:1024]
